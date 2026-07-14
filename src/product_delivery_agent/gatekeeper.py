"""Runtime gatekeeping for Product Delivery state transitions."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    FULL_STACK_BROWSER_E2E,
    INDEPENDENT_SEGMENT_PATH_KINDS,
    build_prototype_production_conformance,
)
from product_delivery_agent.evidence_artifacts import (
    EvidenceArtifactError,
    load_json_artifact,
    sha256_file,
)
from product_delivery_agent.ui_prototype import UIPrototypeError, build_prototype_contract
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
CANONICAL_SCHEMA_VERSION = "v0.11"
PLUGIN_VERSION = "1.0.22"
IMPLEMENTATION_STATUSES = {
    "implementation_ready",
    "implementation_goal_active",
    "implementation_in_progress",
    "implementation_tasks_complete",
    "implementation_blocked",
}


def stable_state_hash(value: Any) -> str:
    """Return a stable hash for protocol state fragments."""
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def scenario_input_hash(state: dict[str, Any]) -> str:
    """Hash the current product/scenario package reviewed before confirmation."""
    scenario_matrix = state.get("scenario_matrix") or {}
    return stable_state_hash(
        {
            "feature_slug": state.get("feature_slug"),
            "open_spec_draft_ready": bool(state.get("open_spec_draft_ready")),
            "scenario_matrix_draft_ready": bool(
                state.get("scenario_matrix_draft_ready")
            ),
            "scenario_rows": scenario_matrix.get("rows", []),
            "surface": surface_input_hash(state),
        }
    )


def surface_input_hash(state: dict[str, Any]) -> str:
    """Hash product surface facts without user-confirmation metadata."""
    if state.get("project_type") == "non_ui":
        contract = state.get("non_ui_behavior_contract") or {}
        contract_facts = {
            key: contract.get(key)
            for key in (
                "contract_name",
                "entry_points",
                "inputs",
                "outputs",
                "taxonomy",
                "behavior_paths",
                "negative_boundary_records",
                "limitations",
                "contract_artifact_path",
                "artifact_hash",
            )
        }
        return stable_state_hash(
            {"project_type": "non_ui", "contract": contract_facts}
        )
    ui = state.get("ui_prototype") or {}
    review = state.get("ui_prototype_review") or {}
    return stable_state_hash(
        {
            "project_type": "ui",
            "prototype_path": ui.get("prototype_path"),
            "artifact_hash": ui.get("artifact_hash"),
            "artifact_version": ui.get("artifact_version"),
            "prototype_revision": ui.get("prototype_revision"),
            "prototype_contract_hash": ui.get("prototype_contract_hash"),
            "prototype_screenshot_set_hash": ui.get(
                "prototype_screenshot_set_hash"
            ),
            "ui_change_type": review.get("ui_change_type") or ui.get("ui_change_type"),
            "baseline_feature_slug": (
                review.get("baseline_feature_slug") or ui.get("baseline_feature_slug")
            ),
            "baseline_surface_paths": (
                review.get("baseline_surface_paths")
                or ui.get("baseline_surface_paths")
                or []
            ),
            "baseline_user_journey": (
                review.get("baseline_user_journey") or ui.get("baseline_user_journey")
            ),
            "continuity_mapping": review.get("continuity_mapping") or [],
            "prototype_delta_summary": review.get("prototype_delta_summary") or [],
        }
    )


def product_baseline_hash(state: dict[str, Any]) -> str:
    """Hash the requirement, scenario, and product-surface baseline."""
    return stable_state_hash(
        {
            "feature_slug": state.get("feature_slug"),
            "scenario": scenario_input_hash(state),
            "surface": surface_input_hash(state),
        }
    )


def planned_e2e_input_hash(state: dict[str, Any]) -> str:
    """Hash planned test obligations without user-confirmation state."""
    planned = state.get("planned_e2e_obligations") or {}
    return stable_state_hash(
        {
            "obligations": planned.get("obligations", []),
            "exemptions": planned.get("exemptions", []),
            "accepted": bool(planned.get("accepted")),
            "artifact_path": planned.get("artifact_path"),
        }
    )


def coverage_audit_input_hash(state: dict[str, Any]) -> str:
    """Hash coverage audit content relevant to planned review gates."""
    audit = state.get("test_coverage_audit") or {}
    return stable_state_hash(
        {
            "passed": bool(audit.get("passed")),
            "matrix_range": audit.get("matrix_range"),
            "latest_test_case": audit.get("latest_test_case"),
            "rows": audit.get("rows", []),
            "negative_guard_records": audit.get("negative_guard_records", []),
        }
    )


def test_coverage_user_semantics_hash(state: dict[str, Any]) -> str:
    """Hash user-visible coverage semantics, excluding internal test hardening."""
    planned = state.get("planned_e2e_obligations") or {}
    obligations = []
    for obligation in planned.get("obligations", []):
        obligations.append(
            {
                key: obligation.get(key)
                for key in (
                    "scenario_id",
                    "user_story",
                    "journey",
                    "acceptance_criteria",
                    "visible_exception",
                    "test_layer",
                    "exemption_status",
                    "baseline_entry_path",
                    "required_actor_roles",
                    "path_kind",
                    "ordinary_entry_path",
                    "data_state_contract",
                )
            }
        )
    audit = state.get("test_coverage_audit") or {}
    rows = []
    for row in audit.get("rows", []):
        rows.append(
            {
                key: row.get(key)
                for key in (
                    "fr",
                    "nfr",
                    "us",
                    "journey",
                    "acceptance_criteria",
                    "test_layer",
                    "evidence_type",
                    "coverage_status",
                    "exemption_status",
                    "critical",
                )
            }
        )
    obligation_semantics = {
        stable_state_hash(record): record for record in obligations
    }
    row_semantics = {stable_state_hash(record): record for record in rows}
    exemptions = list(planned.get("exemptions", []))
    exemption_semantics = {
        stable_state_hash(record): record for record in exemptions
    }
    return stable_state_hash(
        {
            "product_baseline": product_baseline_hash(state),
            "obligations": [
                obligation_semantics[key] for key in sorted(obligation_semantics)
            ],
            "exemptions": [
                exemption_semantics[key] for key in sorted(exemption_semantics)
            ],
            "coverage_rows": [row_semantics[key] for key in sorted(row_semantics)],
        }
    )


def test_coverage_plan_hash(state: dict[str, Any]) -> str:
    """Hash the complete reviewed test-plan snapshot for confirmation evidence."""
    reviews = state.get("multi_agent_reviews") or {}
    return stable_state_hash(
        {
            "user_semantics": test_coverage_user_semantics_hash(state),
            "planned_e2e": planned_e2e_input_hash(state),
            "coverage_audit": coverage_audit_input_hash(state),
            "reviews": {
                review_type: {
                    "status": reviews.get(review_type, {}).get("status"),
                    "review_id": reviews.get(review_type, {}).get("review_id"),
                    "artifact_version": reviews.get(review_type, {}).get(
                        "artifact_version"
                    ),
                    "input_snapshot_hash": reviews.get(review_type, {}).get(
                        "input_snapshot_hash"
                    ),
                    "review_mode": reviews.get(review_type, {}).get("review_mode"),
                }
                for review_type in ("test", "test_coverage")
            },
        }
    )


def review_input_hash(state: dict[str, Any], review_type: str) -> str:
    """Hash the current input package a review type is supposed to judge."""
    if review_type == "scenario":
        return scenario_input_hash(state)
    if review_type in {"test", "test_coverage"}:
        return stable_state_hash(
            {
                "scenario": scenario_input_hash(state),
                "surface": surface_input_hash(state),
                "planned_e2e": planned_e2e_input_hash(state),
                "coverage_audit": coverage_audit_input_hash(state),
            }
        )
    if review_type == "test_implementation":
        return stable_state_hash(
            {
                "planned_e2e": planned_e2e_input_hash(state),
                "executed_browser_evidence": state.get("executed_browser_evidence"),
                "executed_behavior_evidence": state.get("executed_behavior_evidence"),
            }
        )
    if review_type == "ui_conformance":
        return stable_state_hash(
            {
                "surface": surface_input_hash(state),
                "prototype_contract": state.get("prototype_contract"),
                "prototype_production_conformance": state.get(
                    "prototype_production_conformance"
                ),
                "executed_browser_evidence": state.get(
                    "executed_browser_evidence"
                ),
            }
        )
    return stable_state_hash({"review_type": review_type})


def requirements_e2e_confirmation_hash(state: dict[str, Any]) -> str:
    """Compatibility alias for the reviewed test coverage plan hash."""
    return test_coverage_plan_hash(state)


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
        if not _is_legacy_terminal_closure(state):
            contract = _as_dict(state.get("prototype_contract"))
            conformance = _as_dict(state.get("prototype_production_conformance"))
            if contract.get("status") != "ready":
                errors.append("prototype_contract.status=ready")
            if conformance.get("status") != "passed":
                errors.append("prototype_production_conformance.status=passed")
            if not _review_is_current(state, "ui_conformance"):
                errors.append("multi_agent_ui_conformance_review")
            if feature_closure.get(
                "prototype_conformance"
            ) != prototype_conformance_closure_binding(state):
                errors.append("canonical_prototype_conformance_binding")
    errors.extend(canonical_closure_integrity_errors(state))
    return errors


def canonical_closure_integrity_errors(state: dict[str, Any]) -> list[str]:
    """Return missing canonical validator identity and artifact binding errors."""
    if not _is_closure_like_state(state):
        return []

    closure_validation = _as_dict(state.get("closure_validation"))
    feature_closure = _as_dict(state.get("feature_closure"))
    errors: list[str] = []
    legacy_terminal = _is_legacy_terminal_closure(state)

    if closure_validation.get("validator") != CANONICAL_VALIDATOR:
        errors.append("canonical_closure_validation")
    if (
        not legacy_terminal
        and closure_validation.get("canonical_schema_version")
        != CANONICAL_SCHEMA_VERSION
    ):
        errors.append("canonical_closure_schema_version")
    if not legacy_terminal and closure_validation.get("plugin_version") != PLUGIN_VERSION:
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


def _is_legacy_terminal_closure(state: dict[str, Any]) -> bool:
    if state.get("status") not in TERMINAL_STATUSES:
        return False
    validation = _as_dict(state.get("closure_validation"))
    return (
        validation.get("status") == "passed"
        and validation.get("validator") == CANONICAL_VALIDATOR
        and validation.get("canonical_schema_version") in {"v0.10"}
        and validation.get("plugin_version") in {"1.0.15"}
    )


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
    execution_authorization = _as_dict(
        normalized.get("multi_agent_policy")
    ).get("execution_authorization")
    _append_if(
        blockers,
        execution_authorization in {"pending", "legacy_unverified", "invalidated"},
        "multi_agent_mode_authorization",
    )
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
    _append_review_blocker(blockers, normalized, "scenario")
    product_confirmation = normalized.get("user_confirmations", {}).get(
        "product_baseline", {}
    )
    _append_if(
        blockers,
        not normalized.get("open_spec_freeze", {}).get("approved_by_user")
        or not product_confirmation
        or product_confirmation.get("artifact_hash")
        != product_baseline_hash(normalized),
        "product_baseline_user_confirmation",
    )

    project_type = normalized.get("project_type")
    layered_confirmation = bool(normalized.get("confirmation_readiness"))
    if project_type not in VALID_PROJECT_TYPES:
        blockers.append("project_type_decision")
    elif project_type == "ui":
        ui = normalized.get("ui_prototype", {})
        _append_if(
            blockers,
            not ui.get("generated") or not ui.get("reviewed_by_agent"),
            "ui_html_prototype_review",
        )
        if not layered_confirmation:
            confirmation = normalized.get("user_confirmations", {}).get(
                "ui_prototype", {}
            )
            _append_if(
                blockers,
                not ui.get("confirmed_by_user")
                or not confirmation
                or "ui_prototype" in normalized.get("pending_confirmations", {})
                or _ui_prototype_confirmation_is_stale(
                    ui, confirmation, project_root
                ),
                "ui_prototype_user_confirmation",
            )
    elif project_type == "non_ui":
        contract = normalized.get("non_ui_behavior_contract") or {}
        confirmation = normalized.get("user_confirmations", {}).get(
            "non_ui_behavior_contract", {}
        )
        _append_if(
            blockers,
            not contract
            or (
                not layered_confirmation
                and (
                    not contract.get("confirmed_by_user")
                    or not confirmation
                    or confirmation.get("artifact_hash")
                    != surface_input_hash(normalized)
                )
            ),
            "non_ui_behavior_contract_confirmation",
        )

    planned = normalized.get("planned_e2e_obligations", {})
    _append_if(
        blockers,
        not planned.get("accepted") or not planned.get("obligations"),
        "planned_e2e_obligations",
    )
    if not layered_confirmation:
        _append_if(
            blockers,
            not planned.get("accepted_by_user")
            or "planned_e2e_obligations"
            not in normalized.get("user_confirmations", {}),
            "planned_e2e_user_confirmation",
        )
    test_confirmation = normalized.get("user_confirmations", {}).get(
        "test_coverage_plan", {}
    )
    _append_if(
        blockers,
        not test_confirmation
        or test_confirmation.get("user_semantics_hash")
        != test_coverage_user_semantics_hash(normalized),
        "test_coverage_plan_user_confirmation",
    )
    _append_review_blocker(blockers, normalized, "test")
    _append_review_blocker(blockers, normalized, "test_coverage")
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


def _append_review_blocker(
    blockers: list[str],
    state: dict[str, Any],
    review_type: str,
) -> None:
    review = (state.get("multi_agent_reviews") or {}).get(review_type) or {}
    generic = f"multi_agent_{review_type}_review"
    stale = f"stale_multi_agent_{review_type}_review"
    if review.get("status") == "stale":
        _append_if(blockers, True, stale)
        return
    if review.get("status") != "passed":
        _append_if(blockers, True, generic)
        return
    snapshot_hash = review.get("input_snapshot_hash")
    if not snapshot_hash or snapshot_hash != review_input_hash(state, review_type):
        _append_if(blockers, True, stale)


def _review_is_current(state: dict[str, Any], review_type: str) -> bool:
    review = (state.get("multi_agent_reviews") or {}).get(review_type) or {}
    if review.get("status") != "passed":
        return False
    snapshot_hash = review.get("input_snapshot_hash")
    return bool(snapshot_hash) and snapshot_hash == review_input_hash(state, review_type)


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
    scoped_claims: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        text = _read_candidate(path)
        if path.is_relative_to(open_spec_dir):
            scoped_claims.append(text)
        else:
            scoped_claims.append(_feature_scoped_claim_text(text, str(feature_slug)))
    claim_text = "\n".join(part for part in scoped_claims if part)
    if not claim_text:
        return []
    lowered = claim_text.lower()
    errors: list[str] = []
    executed = _as_dict(state.get("executed_browser_evidence"))
    if executed.get("status") != "passed" and _contains_executed_claim(lowered):
        errors.append("docs_ahead_of_executed_evidence")
    closure_validation = _as_dict(state.get("closure_validation"))
    if (
        closure_validation.get("status") != "passed"
        and _contains_closure_claim(lowered)
    ):
        errors.append("docs_ahead_of_closure_validation")
    return errors


def _feature_scoped_claim_text(text: str, feature_slug: str) -> str:
    selected: list[str] = []
    active_heading_level: int | None = None
    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+", line)
        if heading:
            level = len(heading.group(1))
            if _line_contains_feature_slug(line, feature_slug):
                active_heading_level = level
                selected.append(line)
            elif active_heading_level is not None and level > active_heading_level:
                selected.append(line)
            else:
                active_heading_level = None
            continue
        if active_heading_level is not None or _line_contains_feature_slug(
            line, feature_slug
        ):
            selected.append(line)
    return "\n".join(selected)


def _line_contains_feature_slug(line: str, feature_slug: str) -> bool:
    token_boundary = r"A-Za-z0-9._-"
    return bool(
        re.search(
            rf"(?<![{token_boundary}]){re.escape(feature_slug)}(?![{token_boundary}])",
            line,
        )
    )


def _contains_executed_claim(text: str) -> bool:
    return bool(
        re.search(r"\bstatus\s*[:=][^\n]*\bexecuted\b", text)
        or any(term in text for term in ("execution complete", "已执行", "完成验证"))
    )


def _contains_closure_claim(text: str) -> bool:
    without_fail_closed = text.replace("fail closed", "")
    return bool(
        re.search(r"\bstatus\s*[:=][^\n]*\bclosed\b", without_fail_closed)
        or any(
            term in without_fail_closed
            for term in ("closure in progress", "closure complete", "闭包完成")
        )
    )


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
    evidence_key = (
        "executed_browser_evidence"
        if project_type == "ui"
        else "executed_behavior_evidence"
    )
    executed = state.get(evidence_key, {})
    if executed.get("status") != "passed":
        raise GatekeeperError(f"{evidence_key} must pass before closure")
    _assert_executed_covers_planned(planned, executed.get("records", []))
    if not _review_is_current(state, "test_implementation"):
        raise GatekeeperError(
            "multi_agent_test_implementation_review is required before closure"
        )
    if project_type == "ui":
        _assert_ui_executed_evidence_is_full_stack(planned, executed.get("records", []))
        _assert_ui_role_path_segment_evidence(planned, executed.get("records", []))
        _assert_ui_prototype_conformance_current(
            state,
            closure_artifact,
            project_root,
        )
    _assert_closure_covers_executed(closure_artifact, planned, executed)


def _assert_ui_prototype_conformance_current(
    state: dict[str, Any],
    closure_artifact: dict[str, Any],
    project_root: str | Path | None,
) -> None:
    if project_root is None:
        raise GatekeeperError(
            "project_root is required to validate prototype production conformance"
        )
    root = Path(project_root)
    ui = _as_dict(state.get("ui_prototype"))
    contract = _as_dict(state.get("prototype_contract"))
    conformance = _as_dict(state.get("prototype_production_conformance"))
    if not ui.get("confirmed_by_user"):
        raise GatekeeperError("confirmed prototype contract is required before closure")
    if contract.get("status") != "ready":
        raise GatekeeperError("prototype_contract must be current before closure")
    if conformance.get("status") != "passed":
        raise GatekeeperError(
            "prototype_production_conformance must pass before closure"
        )
    if not has_transition(state, "prototype_production_conformance_recorded"):
        raise GatekeeperError(
            "prototype_production_conformance canonical transition is required"
        )

    prototype_path = ui.get("prototype_path")
    if not _non_empty_string(prototype_path):
        raise GatekeeperError("canonical UI prototype path is required before closure")
    resolved_prototype = root / str(prototype_path)
    if not resolved_prototype.is_file() or _sha256(resolved_prototype) != ui.get(
        "artifact_hash"
    ):
        raise GatekeeperError("canonical UI prototype hash changed before closure")

    try:
        contract_payload, contract_metadata = load_json_artifact(
            root,
            _workspace_artifact_path(contract.get("artifact_path")),
        )
        rebuilt_contract = build_prototype_contract(root, contract_payload)
    except (EvidenceArtifactError, UIPrototypeError) as cause:
        raise GatekeeperError(f"prototype contract is stale: {cause}") from cause
    if not _non_empty_string(contract.get("artifact_sha256")):
        raise GatekeeperError("prototype contract artifact hash is required before closure")
    if contract_metadata["sha256"] != contract.get("artifact_sha256"):
        raise GatekeeperError("prototype contract artifact hash changed before closure")
    if rebuilt_contract.get("contract_sha256") != contract.get("contract_sha256"):
        raise GatekeeperError("prototype contract hash changed before closure")
    if rebuilt_contract.get("prototype_screenshot_set_sha256") != contract.get(
        "prototype_screenshot_set_sha256"
    ):
        raise GatekeeperError("prototype screenshot set changed before closure")
    if ui.get("prototype_contract_hash") != contract.get("contract_sha256"):
        raise GatekeeperError("confirmed prototype contract hash is stale")
    if ui.get("prototype_screenshot_set_hash") != contract.get(
        "prototype_screenshot_set_sha256"
    ):
        raise GatekeeperError("confirmed prototype screenshot set hash is stale")

    try:
        conformance_payload, conformance_metadata = load_json_artifact(
            root,
            _workspace_artifact_path(conformance.get("artifact_path")),
        )
        rebuilt_conformance = build_prototype_production_conformance(
            root,
            conformance_payload,
            canonical_prototype=ui,
            prototype_contract=rebuilt_contract,
            executed_browser_evidence=state.get("executed_browser_evidence") or {},
        )
    except (EvidenceArtifactError, CoverageAuditError) as cause:
        raise GatekeeperError(
            f"production screenshot or semantic snapshot is stale: {cause}"
        ) from cause
    if conformance_metadata["sha256"] != conformance.get("artifact_sha256"):
        raise GatekeeperError("prototype production conformance manifest hash changed")
    if rebuilt_conformance.get("evidence_sha256") != conformance.get(
        "evidence_sha256"
    ):
        raise GatekeeperError("prototype production conformance evidence hash changed")
    if not _review_is_current(state, "ui_conformance"):
        raise GatekeeperError(
            "multi_agent_ui_conformance_review is required before closure"
        )

    expected_binding = prototype_conformance_closure_binding(state)
    if closure_artifact.get("prototype_conformance") != expected_binding:
        raise GatekeeperError(
            "closure prototype_conformance must match canonical UI evidence"
        )


def prototype_conformance_closure_binding(state: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical v0.11 UI conformance binding for closure artifacts."""
    ui = _as_dict(state.get("ui_prototype"))
    contract = _as_dict(state.get("prototype_contract"))
    conformance = _as_dict(state.get("prototype_production_conformance"))
    review = _as_dict((state.get("multi_agent_reviews") or {}).get("ui_conformance"))
    return {
        "prototype_revision": ui.get("prototype_revision"),
        "prototype_sha256": ui.get("artifact_hash"),
        "prototype_contract_sha256": contract.get("contract_sha256"),
        "prototype_screenshot_set_sha256": contract.get(
            "prototype_screenshot_set_sha256"
        ),
        "conformance_evidence_sha256": conformance.get("evidence_sha256"),
        "conformance_artifact_sha256": conformance.get("artifact_sha256"),
        "ui_conformance_review_sha256": review.get("input_snapshot_hash"),
        "covered_surface_ids": conformance.get("covered_surface_ids"),
        "covered_region_ids": conformance.get("covered_region_ids"),
    }


def _workspace_artifact_path(value: Any) -> str:
    path = str(value or "")
    if path.startswith("artifacts/"):
        return f".product-delivery/{path}"
    return path


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


def _assert_ui_executed_evidence_is_full_stack(
    planned: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    records_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        records_by_key.setdefault(
            (record.get("obligation_id"), record.get("test_id")),
            [],
        ).append(record)
    weak = []
    for obligation in planned:
        key = (obligation.get("obligation_id"), obligation.get("test_id"))
        matching = records_by_key.get(key, [])
        if not any(
            record.get("evidence_strength") == FULL_STACK_BROWSER_E2E
            for record in matching
        ):
            weak.append(f"{key[0]}:{key[1]}")
    if weak:
        raise GatekeeperError(
            "UI planned E2E obligation requires full_stack_browser_e2e evidence: "
            + ", ".join(weak)
        )


def _assert_ui_role_path_segment_evidence(
    planned: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    records_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        records_by_key.setdefault(
            (record.get("obligation_id"), record.get("test_id")),
            [],
        ).append(record)
    segment_owners: dict[str, str] = {}
    duplicate_segments: list[str] = []
    errors: list[str] = []
    for obligation in planned:
        obligation_id = str(obligation.get("obligation_id") or "")
        test_id = str(obligation.get("test_id") or "")
        key = (obligation_id, test_id)
        matching = records_by_key.get(key, [])
        required_roles = _string_set(obligation.get("required_actor_roles"))
        if not required_roles:
            errors.append(f"{obligation_id}:{test_id}:required_actor_roles")
            continue
        missing_record_fields = []
        for record in matching:
            for field_name in (
                "executed_actor_roles",
                "primary_actor_role",
                "actor_identity_evidence",
                "ordinary_path_observed",
                "execution_segment_id",
                "test_title_or_step",
            ):
                if not _has_evidence_value(record.get(field_name)):
                    missing_record_fields.append(field_name)
        if missing_record_fields:
            errors.append(
                f"{obligation_id}:{test_id}:missing "
                + ",".join(sorted(set(missing_record_fields)))
            )
            continue
        executed_roles = {
            _normalize_actor_role(role)
            for record in matching
            for role in _string_list(record.get("executed_actor_roles"))
        }
        missing_roles = sorted(required_roles - executed_roles)
        if missing_roles:
            errors.append(
                f"{obligation_id}:{test_id}:actor role "
                + ",".join(missing_roles)
            )
        if not any(record.get("ordinary_path_observed") is True for record in matching):
            errors.append(f"{obligation_id}:{test_id}:ordinary_path_observed")
        path_kind = str(obligation.get("path_kind") or "")
        if path_kind in INDEPENDENT_SEGMENT_PATH_KINDS:
            segments = [
                str(record.get("execution_segment_id") or "").strip()
                for record in matching
                if str(record.get("execution_segment_id") or "").strip()
            ]
            if not segments:
                errors.append(f"{obligation_id}:{test_id}:execution_segment_id")
                continue
            owner = f"{obligation_id}:{test_id}"
            segment = segments[0]
            previous = segment_owners.get(segment)
            if previous and previous != owner:
                duplicate_segments.append(f"{segment} ({previous}, {owner})")
            segment_owners[segment] = owner
    if duplicate_segments:
        errors.append("duplicate execution_segment_id: " + ", ".join(duplicate_segments))
    if errors:
        raise GatekeeperError(
            "UI role-accurate browser evidence required: " + "; ".join(errors)
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


def _has_evidence_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, bool):
        return True
    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def _string_set(value: Any) -> set[str]:
    return {_normalize_actor_role(item) for item in _string_list(value)}


def _normalize_actor_role(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


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
