"""Local artifact and state protocol for product delivery projects."""

from __future__ import annotations

import json
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.gatekeeper import (
    PLUGIN_VERSION,
    TERMINAL_STATUSES,
    normalize_state_protocol,
    review_input_hash,
)

ARTIFACT_ROOT = ".product-delivery"
WAYGATE_PLUGIN_NAME = "waygate-product-delivery"

CORE_ARTIFACTS = {
    "product_brief": "product-brief.md",
    "version_scope": "version-scope.md",
    "ui_prototype_review": "ui-prototype-review.md",
    "non_ui_behavior_contract": "non-ui-behavior-contract.md",
    "test_coverage_audit": "test-coverage-audit.md",
    "handoff": "handoff.md",
}

AUTHORIZED_REVIEW_TYPES = [
    "scenario",
    "test",
    "test_coverage",
    "test_implementation",
    "ui_conformance",
]

V1022_RUNTIME_VERSION = re.compile(
    r"^1\.0\.22(?:\+codex\.[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)


def current_runtime_provenance() -> dict[str, str]:
    """Return the identity of the runtime allowed to activate a delivery."""
    package_root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for source_path in sorted(package_root.glob("*.py")):
        digest.update(source_path.name.encode("utf-8"))
        digest.update(source_path.read_bytes())
    return {
        "plugin_name": WAYGATE_PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "package_root_sha256": digest.hexdigest(),
    }


def runtime_status(state: dict[str, Any], raw_state: dict[str, Any]) -> str:
    """Classify whether an active delivery was activated by this runtime."""
    if not state.get("active"):
        return "inactive"
    receipt = raw_state.get("runtime_provenance")
    if not isinstance(receipt, dict):
        return "legacy_unverified"
    expected = current_runtime_provenance()
    if receipt != expected:
        return "invalid_runtime"
    if not isinstance(raw_state.get("delivery_id"), str) or not raw_state["delivery_id"]:
        return "legacy_unverified"
    if not isinstance(raw_state.get("multi_agent_policy"), dict):
        return "legacy_unverified"
    if not isinstance(raw_state.get("host_goal_owner"), dict):
        return "legacy_unverified"
    journal = raw_state.get("transition_journal") or {}
    events = journal.get("events") if isinstance(journal, dict) else None
    if not isinstance(events, list) or not any(
        event.get("transition_name") == "delivery_activated"
        for event in events
        if isinstance(event, dict)
    ):
        return "legacy_unverified"
    return "verified_waygate"


def initialize_workspace(
    project_root: str | Path,
    *,
    project_type: str | None = None,
) -> dict[str, Any]:
    """Create the local product-delivery workspace without overwriting state."""
    root = Path(project_root)
    workspace = root / ARTIFACT_ROOT
    templates_dir = workspace / "templates"
    artifacts_dir = workspace / "artifacts"

    templates_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _ensure_templates(templates_dir)

    state_path = workspace / "state.json"
    terminal_history = False
    if state_path.is_file():
        try:
            raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw_state = {}
        terminal_history = (
            isinstance(raw_state, dict)
            and raw_state.get("status") in TERMINAL_STATUSES
        )
    existing_state = load_state(root)
    if existing_state:
        state = _merge_missing_protocol_fields(existing_state)
    else:
        state = _new_state(project_type)

    if terminal_history:
        return state
    write_state(root, state)
    return state


def load_state(
    project_root: str | Path,
    *,
    fallback_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load state from disk, preferring it over any chat-context fallback."""
    state_path = Path(project_root) / ARTIFACT_ROOT / "state.json"
    if state_path.exists():
        with state_path.open("r", encoding="utf-8") as state_file:
            return _merge_missing_protocol_fields(json.load(state_file))
    return dict(fallback_state or {})


def write_state(project_root: str | Path, state: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist product-delivery state as formatted JSON."""
    workspace = Path(project_root) / ARTIFACT_ROOT
    workspace.mkdir(parents=True, exist_ok=True)

    next_state = normalize_state_protocol(dict(state))
    next_state["updated_at"] = _timestamp()

    state_path = workspace / "state.json"
    temp_path = state_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as state_file:
        json.dump(next_state, state_file, indent=2, sort_keys=True)
        state_file.write("\n")
    os.replace(temp_path, state_path)
    return next_state


def new_delivery_state(project_type: str | None = None) -> dict[str, Any]:
    """Return a fresh delivery protocol state without prior feature data."""
    return _new_state(project_type)


def _new_state(project_type: str | None) -> dict[str, Any]:
    return {
        "delivery_id": uuid.uuid4().hex,
        "active": False,
        "stage": "initialized",
        "project_type": project_type,
        "blocked_until": [],
        "blocking_gates": {},
        "open_spec_draft_ready": False,
        "scenario_matrix_draft_ready": False,
        "open_spec_freeze": {
            "approved_by_user": False,
            "approved_at": None,
            "confirmation_artifact_path": None,
        },
        "multi_agent_reviews": {
            "scenario": {
                "status": "missing",
                "artifact": None,
            },
            "test": {
                "status": "missing",
                "artifact": None,
            },
            "test_coverage": {
                "status": "missing",
                "artifact": None,
            },
            "test_implementation": {
                "status": "missing",
                "artifact": None,
            },
            "ui_conformance": {
                "status": "missing",
                "artifact": None,
            },
        },
        "multi_agent_policy": {
            "mode": "authorization_pending",
            "evidence_requirement": "mode_selection_required",
            "execution_authorization": "pending",
            "authorization_scope": "current_delivery",
            "authorization_source": None,
            "authorization_delivery_id": None,
            "authorization_feature_slug": None,
            "authorized_review_types": [],
        },
        "ui_prototype": {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
        },
        "prototype_contract": {
            "status": "missing",
        },
        "prototype_design_bundle": {
            "status": "missing",
        },
        "prototype_production_conformance": {
            "status": "missing",
            "records": [],
        },
        "planned_e2e_obligations": {
            "accepted": False,
            "accepted_by_user": False,
            "obligations": [],
            "exemptions": [],
        },
        "executed_browser_evidence": {
            "status": "missing",
            "records": [],
        },
        "executed_behavior_evidence": {
            "status": "missing",
            "records": [],
        },
        "closure_validation": {
            "status": "not_run",
            "errors": [],
        },
        "user_confirmations": {},
        "pending_confirmations": {},
        "confirmation_readiness": {
            "product_baseline": "draft",
            "test_coverage_plan": "blocked_on_product_baseline",
        },
        "user_change_requests": [],
        "pending_user_decisions": {},
        "delivery_goal": None,
        "host_goal_authorization": {
            "status": "not_authorized",
        },
        "host_goal_owner": {
            "schema_version": "v1",
            "status": "not_initialized",
            "delivery_id": None,
            "feature_slug": None,
            "coordinator_thread_id": None,
            "generation": 0,
            "pending_claim": None,
        },
        "host_goal_binding": {
            "status": "not_required",
        },
        "confirmation_points": {
            artifact_name: {
                "confirmed": False,
                "artifact_path": f"artifacts/{template_file}",
            }
            for artifact_name, template_file in CORE_ARTIFACTS.items()
        },
        "artifact_paths": {
            artifact_name: f"artifacts/{template_file}"
            for artifact_name, template_file in CORE_ARTIFACTS.items()
        },
        "freeze": {
            "frozen": False,
            "scope_version": None,
        },
        "updated_at": _timestamp(),
    }


def _merge_missing_protocol_fields(state: dict[str, Any]) -> dict[str, Any]:
    is_terminal_history = state.get("status") in TERMINAL_STATUSES
    merged = normalize_state_protocol(dict(state))
    if not is_terminal_history:
        merged.setdefault("delivery_id", _legacy_delivery_id(merged))
    merged.setdefault("active", False)
    merged.setdefault("stage", "initialized")
    merged.setdefault("project_type", None)
    merged.setdefault("blocked_until", [])
    merged.setdefault("blocking_gates", {})
    merged.setdefault("open_spec_draft_ready", False)
    merged.setdefault("scenario_matrix_draft_ready", False)
    merged.setdefault(
        "open_spec_freeze",
        {
            "approved_by_user": False,
            "approved_at": None,
            "confirmation_artifact_path": None,
        },
    )
    merged.setdefault(
        "multi_agent_reviews",
        {
            "scenario": {
                "status": "missing",
                "artifact": None,
            },
            "test": {
                "status": "missing",
                "artifact": None,
            },
            "test_coverage": {
                "status": "missing",
                "artifact": None,
            },
            "test_implementation": {
                "status": "missing",
                "artifact": None,
            },
            "ui_conformance": {
                "status": "missing",
                "artifact": None,
            },
        },
    )
    policy = merged.setdefault(
        "multi_agent_policy",
        {
            "mode": "authorization_pending",
            "evidence_requirement": "mode_selection_required",
            "execution_authorization": "pending",
            "authorization_scope": "current_delivery",
            "authorization_source": None,
            "authorization_delivery_id": merged.get("delivery_id"),
            "authorization_feature_slug": merged.get("feature_slug"),
            "authorized_review_types": [],
        },
    )
    if not is_terminal_history and "execution_authorization" not in policy:
        legacy_mode = policy.get("mode")
        policy.update(
            {
                "evidence_requirement": (
                    "structured_role_simulation"
                    if legacy_mode == "role_simulation_allowed"
                    else "spawned_subagents"
                ),
                "execution_authorization": "legacy_unverified",
                "authorization_scope": "current_delivery",
                "authorization_source": "legacy_state_migration",
                "authorization_delivery_id": merged.get("delivery_id"),
                "authorization_feature_slug": merged.get("feature_slug"),
                "authorized_review_types": [],
            }
        )
        merged["next_gate"] = "multi_agent_mode_selection"
        merged.setdefault("pending_user_decisions", {})["multi_agent_mode"] = {
            "status": "pending",
            "reason": "legacy authorization could not be verified",
        }
    if not is_terminal_history:
        policy.setdefault("authorization_delivery_id", merged.get("delivery_id"))
        policy.setdefault("authorization_feature_slug", merged.get("feature_slug"))
    merged["multi_agent_reviews"].setdefault(
        "scenario",
        {
            "status": "missing",
            "artifact": None,
        },
    )
    merged["multi_agent_reviews"].setdefault(
        "test",
        {
            "status": "missing",
            "artifact": None,
        },
    )
    merged["multi_agent_reviews"].setdefault(
        "test_coverage",
        {
            "status": "missing",
            "artifact": None,
        },
    )
    merged["multi_agent_reviews"].setdefault(
        "test_implementation",
        {
            "status": "missing",
            "artifact": None,
        },
    )
    merged["multi_agent_reviews"].setdefault(
        "ui_conformance",
        {
            "status": "missing",
            "artifact": None,
        },
    )
    merged.setdefault(
        "ui_prototype",
        {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
        },
    )
    merged.setdefault("prototype_contract", {"status": "missing"})
    if not is_terminal_history and "prototype_design_bundle" not in merged:
        if _legacy_v1022_confirmed_ui_state(merged):
            merged["prototype_design_bundle"] = {
                "status": "legacy_grandfathered",
                "enforcement": "on_next_prototype_revision",
            }
        else:
            merged["prototype_design_bundle"] = {"status": "missing"}
    merged.setdefault(
        "prototype_production_conformance",
        {
            "status": "missing",
            "records": [],
        },
    )
    merged.setdefault(
        "planned_e2e_obligations",
        {
            "accepted": False,
            "accepted_by_user": False,
            "obligations": [],
            "exemptions": [],
        },
    )
    merged.setdefault(
        "executed_browser_evidence",
        {
            "status": "missing",
            "records": [],
        },
    )
    merged.setdefault(
        "closure_validation",
        {
            "status": "not_run",
            "errors": [],
        },
    )
    merged.setdefault("user_confirmations", {})
    merged.setdefault("pending_confirmations", {})
    merged.setdefault(
        "confirmation_readiness",
        {
            "product_baseline": "draft",
            "test_coverage_plan": "blocked_on_product_baseline",
        },
    )
    merged.setdefault("user_change_requests", [])
    merged.setdefault("pending_user_decisions", {})
    merged.setdefault("delivery_goal", None)
    if "host_goal_authorization" not in merged:
        merged["host_goal_authorization"] = {
            "status": (
                "legacy_unverified"
                if not is_terminal_history
                and (merged.get("handoff") or merged.get("delivery_goal"))
                else "not_authorized"
            ),
            "authorization_source": "legacy_state_migration",
        }
    if "host_goal_binding" not in merged:
        if not is_terminal_history and (
            merged.get("handoff") or merged.get("delivery_goal")
        ):
            merged["host_goal_binding"] = {
                "schema_version": "v1",
                "status": "legacy_unverified",
                "delivery_id": merged.get("delivery_id"),
                "feature_slug": merged.get("feature_slug"),
                "launch_package_hash": (
                    (merged.get("delivery_goal") or {}).get(
                        "launch_package_hash"
                    )
                ),
                "resume_gate": merged.get("next_gate"),
                "migration_source": "pre_v1024_active_state",
            }
            merged["next_gate"] = "host_goal_recovery"
        else:
            merged["host_goal_binding"] = {"status": "not_required"}
    if "host_goal_owner" not in merged:
        if is_terminal_history:
            merged["host_goal_owner"] = {
                "schema_version": "v1",
                "status": "not_required",
                "delivery_id": merged.get("delivery_id"),
                "feature_slug": merged.get("feature_slug"),
                "coordinator_thread_id": None,
                "generation": 0,
                "pending_claim": None,
            }
        elif merged.get("active"):
            merged["host_goal_owner"] = {
                "schema_version": "v1",
                "status": "legacy_unverified",
                "delivery_id": merged.get("delivery_id"),
                "feature_slug": merged.get("feature_slug"),
                "coordinator_thread_id": None,
                "generation": 0,
                "resume_gate": merged.get("next_gate"),
                "migration_source": "pre_v1026_active_state",
                "pending_claim": None,
            }
            if merged.get("handoff") or merged.get("delivery_goal"):
                merged["next_gate"] = "host_goal_owner_recovery"
        else:
            merged["host_goal_owner"] = {
                "schema_version": "v1",
                "status": "not_required",
                "delivery_id": merged.get("delivery_id"),
                "feature_slug": merged.get("feature_slug"),
                "coordinator_thread_id": None,
                "generation": 0,
                "pending_claim": None,
            }
    merged.setdefault("confirmation_points", {})
    merged.setdefault("artifact_paths", {})
    merged.setdefault("freeze", {"frozen": False, "scope_version": None})

    if not is_terminal_history:
        _migrate_layered_confirmation_state(merged)

    for artifact_name, template_file in CORE_ARTIFACTS.items():
        artifact_path = f"artifacts/{template_file}"
        merged["artifact_paths"].setdefault(artifact_name, artifact_path)
        merged["confirmation_points"].setdefault(
            artifact_name,
            {
                "confirmed": False,
                "artifact_path": artifact_path,
            },
        )
    return merged


def _migrate_layered_confirmation_state(state: dict[str, Any]) -> None:
    pending = state.setdefault("pending_confirmations", {})
    legacy_ui_pending = pending.pop("ui_prototype", None)
    if legacy_ui_pending:
        state.setdefault("legacy_pending_confirmations", []).append(
            {
                "target": "ui_prototype",
                "record": legacy_ui_pending,
                "migration_reason": (
                    "replaced_by_layered_product_baseline_confirmation"
                ),
                "migrated_at": _timestamp(),
            }
        )
    ui = state.get("ui_prototype")
    if isinstance(ui, dict) and (
        ui.get("confirmation_status") == "pending_user_confirmation"
        or ui.get("pending_confirmation_nonce")
    ):
        ui["confirmation_status"] = "superseded_by_product_baseline"
        ui.pop("pending_confirmation_nonce", None)

    blockers = state.setdefault("blocked_until", [])
    blockers[:] = [
        blocker
        for blocker in blockers
        if blocker
        not in {
            "pending_user_confirmation",
            "planned_e2e_user_confirmation",
            "ui_html_prototype_confirmation",
            "ui_prototype_user_confirmation",
            "user_confirmed_freeze",
        }
    ]
    if not legacy_ui_pending:
        return
    if "product_baseline_user_confirmation" not in blockers:
        blockers.append("product_baseline_user_confirmation")

    scenario_review = state.get("multi_agent_reviews", {}).get("scenario", {})
    review_is_current = scenario_review.get("status") == "passed" and scenario_review.get(
        "input_snapshot_hash"
    ) == review_input_hash(state, "scenario")
    readiness = state.setdefault("confirmation_readiness", {})
    if review_is_current:
        readiness["product_baseline"] = "ready_for_preparation"
        state["next_gate"] = "product_baseline_confirmation_preparation"
        return

    if scenario_review.get("status") == "passed":
        state["multi_agent_reviews"]["scenario"] = {
            **scenario_review,
            "status": "stale",
            "stale_reason": "layered_confirmation_migration",
        }
        if "stale_multi_agent_scenario_review" not in blockers:
            blockers.append("stale_multi_agent_scenario_review")
    elif "multi_agent_scenario_review" not in blockers:
        blockers.append("multi_agent_scenario_review")
    readiness["product_baseline"] = "blocked_on_scenario_review"
    state["next_gate"] = "multi_agent_scenario_review"


def _legacy_v1022_confirmed_ui_state(state: dict[str, Any]) -> bool:
    if not state.get("active") or state.get("project_type") != "ui":
        return False
    versions = [
        value.strip()
        for key in ("runtime_version", "plugin_version")
        if isinstance((value := state.get(key)), str) and value.strip()
    ]
    if not versions or not all(
        V1022_RUNTIME_VERSION.fullmatch(value) for value in versions
    ):
        return False
    ui = state.get("ui_prototype") or {}
    if not ui.get("confirmed_by_user"):
        return False
    confirmations = state.get("user_confirmations") or {}
    return bool(
        confirmations.get("ui_prototype")
        or confirmations.get("product_baseline")
        or (state.get("open_spec_freeze") or {}).get("approved_by_user")
    )


def _legacy_delivery_id(state: dict[str, Any]) -> str:
    material = {
        "feature_slug": state.get("feature_slug"),
        "activation_source": state.get("activation_source"),
        "stage": state.get("stage"),
        "updated_at": state.get("updated_at"),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "legacy-" + hashlib.sha256(encoded).hexdigest()[:16]


def _ensure_templates(templates_dir: Path) -> None:
    for artifact_name, template_file in CORE_ARTIFACTS.items():
        template_path = templates_dir / template_file
        if not template_path.exists():
            title = artifact_name.replace("_", " ").title()
            template_path.write_text(
                f"# {title}\n\nStatus: Draft\n\n## Notes\n\n",
                encoding="utf-8",
            )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
