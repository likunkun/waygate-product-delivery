"""Runtime gatekeeping for Product Delivery state transitions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from product_delivery_agent.transition_journal import (
    has_transition,
    journal_integrity_errors,
)


class GatekeeperError(RuntimeError):
    """Raised when a Product Delivery gate is not ready."""


UI_SUBTYPES = {"web", "web_ui", "web_system", "frontend", "ui_system"}
VALID_PROJECT_TYPES = {"ui", "non_ui"}
TERMINAL_STATUSES = {"closed", "closed_local_product_delivery", "complete", "completed"}
CANONICAL_VALIDATOR = "product_delivery_agent.finalization"
CANONICAL_SCHEMA_VERSION = "v0.10"
PLUGIN_VERSION = "1.0.11"
IMPLEMENTATION_STATUSES = {
    "implementation_ready",
    "implementation_goal_active",
    "implementation_in_progress",
    "implementation_tasks_complete",
    "implementation_blocked",
}


def normalize_project_type(raw: Any) -> tuple[str | None, str | None]:
    """Normalize legacy project type values into protocol values."""
    if raw is None:
        return None, None
    value = str(raw).strip()
    if value in VALID_PROJECT_TYPES:
        return value, None
    if value in UI_SUBTYPES:
        return "ui", value
    return value, None


def normalize_state_protocol(state: dict[str, Any]) -> dict[str, Any]:
    """Return a state copy with recoverable legacy protocol drift normalized."""
    normalized = dict(state)
    project_type, project_subtype = normalize_project_type(normalized.get("project_type"))
    normalized["project_type"] = project_type
    if project_subtype:
        normalized["project_subtype"] = project_subtype
    closure_errors = closure_integrity_errors(normalized)
    if closure_errors:
        normalized["status"] = "closure_failed"
        if not isinstance(normalized.get("closure_validation"), dict):
            normalized["closure_validation"] = {}
        normalized["closure_validation"] = {
            **normalized["closure_validation"],
            "status": "closure_failed",
            "errors": closure_errors,
        }
        normalized["blocking_gates"] = {
            **(normalized.get("blocking_gates") or {}),
            "closure": False,
        }
        normalized["stage"] = "closure_failed"
        normalized["next_gate"] = "feature_closure_after_implementation"
    else:
        implementation_errors = implementation_integrity_errors(normalized)
        if implementation_errors:
            normalized["status"] = "implementation_blocked"
            normalized["stage"] = "implementation_blocked"
            normalized["next_gate"] = "codex_goal_handoff"
            normalized["protocol_errors"] = implementation_errors
            normalized["blocking_gates"] = {
                **(normalized.get("blocking_gates") or {}),
                "implementation": False,
                "pre_handoff": False,
            }
    return normalized


def validate_state_invariants(state: dict[str, Any]) -> None:
    """Validate protocol invariants that must never be hand-edited past."""
    project_type, _project_subtype = normalize_project_type(state.get("project_type"))
    if project_type not in VALID_PROJECT_TYPES and project_type is not None:
        raise GatekeeperError("project_type must be ui or non_ui")
    closure_errors = closure_integrity_errors(state)
    if closure_errors:
        raise GatekeeperError(
            "closure-like state requires: " + ", ".join(closure_errors)
        )
    implementation_errors = implementation_integrity_errors(state)
    if implementation_errors:
        raise GatekeeperError(
            "implementation state requires: " + ", ".join(implementation_errors)
        )


def state_requires_delivery_goal(state: dict[str, Any]) -> bool:
    """Return whether the current state is past the handoff boundary."""
    if not state:
        return False
    if _is_closure_like_state(state):
        return True
    if state.get("handoff"):
        return True
    if state.get("status") in IMPLEMENTATION_STATUSES:
        return True
    implementation = state.get("implementation") or {}
    return bool(
        implementation.get("current_task")
        or implementation.get("completed_tasks")
    )


def implementation_integrity_errors(state: dict[str, Any]) -> list[str]:
    """Return missing canonical implementation requirements for active work."""
    if not _has_implementation_markers(state):
        return []

    errors: list[str] = []
    handoff = _as_dict(state.get("handoff"))
    delivery_goal = _as_dict(state.get("delivery_goal"))
    authorization = _as_dict(state.get("implementation_launch_authorization"))

    if not handoff:
        errors.append("canonical_handoff")
    if not delivery_goal:
        errors.append("implementation_without_delivery_goal")
    if delivery_goal and authorization.get("status") != "authorized":
        errors.append("implementation_launch_authorization")
    if delivery_goal and authorization:
        if authorization.get("feature_slug") != state.get("feature_slug"):
            errors.append("stale_implementation_launch_authorization")
        if delivery_goal.get("launch_package_hash") and (
                authorization.get("launch_package_hash")
            != delivery_goal.get("launch_package_hash")
        ):
            errors.append("stale_implementation_launch_authorization")
        errors.extend(_task_state_consistency_errors(state, delivery_goal))
    if handoff and delivery_goal and not has_transition(state, "handoff_generated"):
        errors.append("canonical_handoff_transition")
    if delivery_goal and delivery_goal.get("completed_tasks"):
        if not has_transition(state, "task_completed"):
            errors.append("canonical_task_transition")
    errors.extend(journal_integrity_errors(state))
    return _dedupe(errors)


def closure_integrity_errors(state: dict[str, Any]) -> list[str]:
    """Return missing terminal closure requirements for closure-like states."""
    if not _is_closure_like_state(state):
        return []

    errors: list[str] = []
    closure_validation = _as_dict(state.get("closure_validation"))
    feature_closure = _as_dict(state.get("feature_closure"))
    delivery_goal = _as_dict(state.get("delivery_goal"))
    project_type = normalize_project_type(state.get("project_type"))[0]

    if closure_validation.get("status") != "passed":
        errors.append("closure_validation.status=passed")
    if feature_closure.get("status") != "passed":
        errors.append("feature_closure.status=passed")
    if delivery_goal.get("status") != "complete":
        errors.append("delivery_goal.status=complete")
    if project_type not in VALID_PROJECT_TYPES:
        errors.append("project_type=ui_or_non_ui")
    elif project_type == "ui":
        executed = _as_dict(state.get("executed_browser_evidence"))
        if executed.get("status") != "passed":
            errors.append("executed_browser_evidence.status=passed")
    errors.extend(canonical_closure_integrity_errors(state))
    return errors


def canonical_closure_integrity_errors(state: dict[str, Any]) -> list[str]:
    """Return missing canonical validator identity and artifact binding errors."""
    if not _is_closure_like_state(state):
        return []

    closure_validation = _as_dict(state.get("closure_validation"))
    feature_closure = _as_dict(state.get("feature_closure"))
    errors: list[str] = []

    if closure_validation.get("validator") != CANONICAL_VALIDATOR:
        errors.append("canonical_closure_validation")
    if closure_validation.get("canonical_schema_version") != CANONICAL_SCHEMA_VERSION:
        errors.append("canonical_closure_schema_version")
    if closure_validation.get("plugin_version") != PLUGIN_VERSION:
        errors.append("canonical_closure_plugin_version")
    if (
        closure_validation.get("feature_slug")
        and closure_validation.get("feature_slug") != state.get("feature_slug")
    ):
        errors.append("current_feature_closure_validation")
    closure_hash = closure_validation.get("closure_artifact_sha256")
    if not _non_empty_string(closure_hash):
        errors.append("canonical_closure_artifact_sha256")
    if not _non_empty_string(closure_validation.get("result_artifact")):
        errors.append("canonical_closure_result_artifact")
    source_path = feature_closure.get("source_artifact_path")
    source_hash = feature_closure.get("source_artifact_sha256")
    if not _non_empty_string(source_path):
        errors.append("canonical_closure_source_artifact")
    if not _non_empty_string(source_hash):
        errors.append("canonical_closure_source_artifact_sha256")
    if _non_empty_string(closure_hash) and _non_empty_string(source_hash):
        if closure_hash != source_hash:
            errors.append("canonical_closure_artifact_hash_mismatch")
    if (
        _non_empty_string(source_path)
        and _non_empty_string(source_hash)
        and not str(source_path).startswith("inline:")
    ):
        path = Path(source_path)
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != source_hash:
                errors.append("canonical_closure_artifact_hash_mismatch")
    errors.extend(journal_integrity_errors(state))
    if not has_transition(state, "closure_validated"):
        errors.append("canonical_closure_transition")
    if not has_transition(state, "goal_completed"):
        errors.append("canonical_goal_completion_transition")
    return _dedupe(errors)


def _is_closure_like_state(state: dict[str, Any]) -> bool:
    status = state.get("status")
    if status in TERMINAL_STATUSES:
        return True
    if _as_dict(state.get("blocking_gates")).get("closure") is True:
        return True
    implementation = _as_dict(state.get("implementation"))
    if implementation.get("current_task") == "COMPLETE":
        return True
    if _as_dict(state.get("delivery_goal")).get("status") == "complete":
        return True
    return False


def _has_implementation_markers(state: dict[str, Any]) -> bool:
    status = state.get("status")
    if status in IMPLEMENTATION_STATUSES:
        return True
    implementation = _as_dict(state.get("implementation"))
    current_task = implementation.get("current_task")
    if isinstance(current_task, str) and current_task.startswith("TASK-"):
        return True
    completed = implementation.get("completed_tasks")
    return isinstance(completed, list) and bool(completed)


def _task_state_consistency_errors(
    state: dict[str, Any],
    delivery_goal: dict[str, Any],
) -> list[str]:
    implementation = _as_dict(state.get("implementation"))
    errors: list[str] = []
    implementation_completed = implementation.get("completed_tasks")
    goal_completed = delivery_goal.get("completed_tasks")
    if isinstance(implementation_completed, list) and implementation_completed:
        if list(implementation_completed) != list(goal_completed or []):
            errors.append("delivery_goal_task_state_mismatch")
    current_task = implementation.get("current_task")
    if isinstance(current_task, str) and current_task.startswith("TASK-"):
        if current_task != delivery_goal.get("current_task_cursor"):
            errors.append("delivery_goal_task_state_mismatch")
    return errors


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def derive_blockers(
    state: dict[str, Any],
    project_root: str | Path | None = None,
    *,
    launch_package_hash: str | None = None,
) -> list[str]:
    """Derive current blockers from structured state, ignoring hand-edited lists."""
    normalized = normalize_state_protocol(state)
    blockers: list[str] = []
    for error in normalized.get("protocol_errors", []):
        _append_if(blockers, True, error)
    closure_validation = _as_dict(normalized.get("closure_validation"))
    if closure_validation.get("status") == "closure_failed":
        for error in closure_validation.get("errors", []):
            _append_if(blockers, True, error)
    _append_if(blockers, not normalized.get("feature_slug"), "feature_slug")
    _append_if(
        blockers,
        not normalized.get("open_spec_draft_ready"),
        "open_spec_current_feature",
    )
    _append_if(
        blockers,
        not normalized.get("scenario_matrix_draft_ready")
        or not normalized.get("scenario_matrix", {}).get("draft_ready"),
        "scenario_matrix_draft",
    )
    _append_if(
        blockers,
        normalized.get("multi_agent_reviews", {})
        .get("scenario", {})
        .get("status")
        != "passed",
        "multi_agent_scenario_review",
    )
    _append_if(
        blockers,
        not normalized.get("open_spec_freeze", {}).get("approved_by_user")
        or "open_spec_freeze" not in normalized.get("user_confirmations", {}),
        "user_confirmed_freeze",
    )

    project_type = normalized.get("project_type")
    if project_type not in VALID_PROJECT_TYPES:
        blockers.append("project_type_decision")
    elif project_type == "ui":
        ui = normalized.get("ui_prototype", {})
        confirmation = normalized.get("user_confirmations", {}).get("ui_prototype", {})
        _append_if(
            blockers,
            not ui.get("generated") or not ui.get("reviewed_by_agent"),
            "ui_html_prototype_review",
        )
        _append_if(
            blockers,
            not ui.get("confirmed_by_user")
            or not confirmation
            or "ui_prototype" in normalized.get("pending_confirmations", {})
            or _ui_prototype_confirmation_is_stale(ui, confirmation, project_root),
            "ui_prototype_user_confirmation",
        )
    elif project_type == "non_ui":
        _append_if(
            blockers,
            "non_ui_behavior_contract" not in normalized,
            "non_ui_behavior_contract_confirmation",
        )

    planned = normalized.get("planned_e2e_obligations", {})
    _append_if(
        blockers,
        not planned.get("accepted") or not planned.get("obligations"),
        "planned_e2e_obligations",
    )
    _append_if(
        blockers,
        not planned.get("accepted_by_user")
        or "planned_e2e_obligations" not in normalized.get("user_confirmations", {}),
        "planned_e2e_user_confirmation",
    )
    _append_if(
        blockers,
        normalized.get("multi_agent_reviews", {}).get("test", {}).get("status")
        != "passed",
        "multi_agent_test_review",
    )
    if project_type == "ui":
        _append_if(
            blockers,
            normalized.get("multi_agent_reviews", {})
            .get("test_coverage", {})
            .get("status")
            != "passed",
            "multi_agent_test_coverage_review",
        )
    _append_if(
        blockers,
        not normalized.get("test_coverage_audit", {}).get("passed"),
        "test_coverage_audit",
    )
    authorization = normalized.get("implementation_launch_authorization", {})
    if authorization.get("status") != "authorized":
        blockers.append("implementation_launch_authorization")
    elif launch_package_hash and authorization.get("launch_package_hash") != launch_package_hash:
        blockers.append("stale_implementation_launch_authorization")
    for error in docs_ahead_of_state_errors(normalized, project_root):
        _append_if(blockers, True, error)

    return blockers


def docs_ahead_of_state_errors(
    state: dict[str, Any],
    project_root: str | Path | None,
) -> list[str]:
    """Return blockers when docs claim execution/closure ahead of state."""
    if project_root is None:
        return []
    root = Path(project_root)
    feature_slug = state.get("feature_slug")
    if not _non_empty_string(feature_slug):
        return []
    candidates = [
        root / "ROADMAP.md",
        root / "task_plan.md",
        root / "progress.md",
        root / "findings.md",
    ]
    open_spec_dir = root / "docs" / "open-spec" / str(feature_slug)
    if open_spec_dir.is_dir():
        candidates.extend(
            open_spec_dir / name
            for name in (
                "05-development-plan.md",
                "06-test-cases.md",
                "08-stage-handoff.md",
            )
        )
    claim_text = "\n".join(
        _read_candidate(path)
        for path in candidates
        if path.is_file()
    )
    if not claim_text or str(feature_slug) not in claim_text:
        return []
    lowered = claim_text.lower()
    errors: list[str] = []
    executed_terms = ("executed", "status=executed", "已执行", "完成验证")
    closure_terms = ("closed", "closure in progress", "closure complete", "闭包完成")
    executed = _as_dict(state.get("executed_browser_evidence"))
    if executed.get("status") != "passed" and any(term in lowered for term in executed_terms):
        errors.append("docs_ahead_of_executed_evidence")
    closure_validation = _as_dict(state.get("closure_validation"))
    if closure_validation.get("status") != "passed" and any(
        term in lowered for term in closure_terms
    ):
        errors.append("docs_ahead_of_closure_validation")
    return errors


def assert_pre_handoff_ready(
    state: dict[str, Any],
    project_root: str | Path | None = None,
    *,
    launch_package_hash: str | None = None,
) -> None:
    """Require all pre-implementation gates before Codex Goal handoff."""
    validate_state_invariants(state)
    blockers = derive_blockers(
        state,
        project_root,
        launch_package_hash=launch_package_hash,
    )
    if blockers:
        raise GatekeeperError(
            "pre-handoff gate blocked: " + ", ".join(sorted(blockers))
        )


def assert_pre_closure_ready(
    state: dict[str, Any],
    closure_artifact: dict[str, Any],
    project_root: str | Path | None = None,
) -> None:
    """Require executed evidence and closure fields to match planned coverage."""
    validate_state_invariants(state)
    project_type = normalize_project_type(state.get("project_type"))[0]
    if project_type not in VALID_PROJECT_TYPES:
        raise GatekeeperError("project_type must be ui or non_ui before closure")
    if not state.get("handoff"):
        raise GatekeeperError("handoff is required before closure")
    if state_requires_delivery_goal(state) and not state.get("delivery_goal"):
        raise GatekeeperError("delivery_goal is required before closure")
    if not state.get("test_coverage_audit", {}).get("passed"):
        raise GatekeeperError("passed test coverage audit is required before closure")

    planned = _unexempted_planned_obligations(state)
    executed = state.get("executed_browser_evidence", {})
    if project_type == "ui":
        if executed.get("status") != "passed":
            raise GatekeeperError("executed_browser_evidence must pass before closure")
        _assert_executed_covers_planned(planned, executed.get("records", []))
        _assert_closure_covers_executed(closure_artifact, planned, executed)
        if (
            state.get("multi_agent_reviews", {})
            .get("test_implementation", {})
            .get("status")
            != "passed"
        ):
            raise GatekeeperError(
                "multi_agent_test_implementation_review is required before closure"
            )


def assert_executed_evidence_covers_planned(
    state: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    """Validate executed records against the current planned E2E obligations."""
    planned = _unexempted_planned_obligations(state)
    if not planned:
        return
    _assert_executed_covers_planned(planned, records)


def render_closure_validator_result(
    status: str,
    errors: list[str],
    *,
    feature_slug: str | None = None,
    plugin_version: str = PLUGIN_VERSION,
) -> str:
    """Render closure validator status as an artifact."""
    lines = [
        "# Closure Validator Result",
        "",
        f"- status: {status}",
        f"- validator: {CANONICAL_VALIDATOR}",
        f"- canonical_schema_version: {CANONICAL_SCHEMA_VERSION}",
        f"- plugin_version: {plugin_version}",
        f"- feature_slug: {feature_slug or ''}",
        "- errors:",
    ]
    if errors:
        lines.extend(f"  - {error}" for error in errors)
    else:
        lines.append("  - None")
    lines.append("")
    return "\n".join(lines)


def _unexempted_planned_obligations(state: dict[str, Any]) -> list[dict[str, Any]]:
    planned = state.get("planned_e2e_obligations", {})
    exemptions = {
        record.get("object_id")
        for record in planned.get("exemptions", [])
        if record.get("allows_closure") is True
    }
    obligations = []
    for obligation in planned.get("obligations", []):
        if obligation.get("exemption_status") == "approved":
            if (
                obligation.get("scenario_id") in exemptions
                or obligation.get("obligation_id") in exemptions
                or obligation.get("test_id") in exemptions
            ):
                continue
        obligations.append(obligation)
    return obligations


def _assert_executed_covers_planned(
    planned: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    record_keys = {
        (record.get("obligation_id"), record.get("test_id"))
        for record in records
    }
    missing = [
        f"{obligation.get('obligation_id')}:{obligation.get('test_id')}"
        for obligation in planned
        if (obligation.get("obligation_id"), obligation.get("test_id"))
        not in record_keys
    ]
    if missing:
        raise GatekeeperError(
            "planned E2E obligation missing executed evidence: "
            + ", ".join(missing)
        )


def _assert_closure_covers_executed(
    closure_artifact: dict[str, Any],
    planned: list[dict[str, Any]],
    executed: dict[str, Any],
) -> None:
    required_tc = {obligation["test_id"] for obligation in planned}
    required_stories = {obligation["user_story"] for obligation in planned}
    required_journeys = {obligation["journey"] for obligation in planned}
    required_paths = {
        record["evidence_path"] for record in executed.get("records", [])
    }

    _assert_contains(
        set(closure_artifact.get("e2e_covered_tc", [])),
        required_tc,
        "closure e2e_covered_tc",
    )
    _assert_contains(
        set(closure_artifact.get("covered_user_stories", [])),
        required_stories,
        "closure covered_user_stories",
    )
    _assert_contains(
        set(closure_artifact.get("covered_journeys", [])),
        required_journeys,
        "closure covered_journeys",
    )
    _assert_contains(
        set(closure_artifact.get("e2e_evidence_paths", [])),
        required_paths,
        "closure e2e_evidence_paths",
    )


def _assert_contains(actual: set[str], required: set[str], label: str) -> None:
    missing = sorted(required - actual)
    if missing:
        raise GatekeeperError(label + " missing: " + ", ".join(missing))


def _read_candidate(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _append_if(blockers: list[str], condition: bool, blocker: str) -> None:
    if condition and blocker not in blockers:
        blockers.append(blocker)


def _ui_prototype_confirmation_is_stale(
    ui: dict[str, Any],
    confirmation: dict[str, Any],
    project_root: str | Path | None,
) -> bool:
    expected_hash = ui.get("artifact_hash")
    confirmed_hash = confirmation.get("artifact_hash")
    if not expected_hash or confirmed_hash != expected_hash:
        return True
    if confirmation.get("prototype_revision") != ui.get("prototype_revision"):
        return True
    prototype_path = ui.get("prototype_path")
    if project_root is None or not prototype_path:
        return False
    path = Path(prototype_path)
    if not path.is_absolute():
        path = Path(project_root) / path
    if not path.is_file():
        return True
    return _sha256(path) != expected_hash


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
