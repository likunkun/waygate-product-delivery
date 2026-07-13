"""Local artifact and state protocol for product delivery projects."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.gatekeeper import TERMINAL_STATUSES, normalize_state_protocol

ARTIFACT_ROOT = ".product-delivery"

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

    existing_state = load_state(root)
    if existing_state:
        state = _merge_missing_protocol_fields(existing_state)
    else:
        state = _new_state(project_type)

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
            "authorized_review_types": [],
        },
        "execution_model_policy": {
            "mode": "authorization_pending",
            "authorization_status": "pending",
            "authorization_scope": "current_delivery",
            "authorization_source": None,
            "resolved_profiles": None,
            "resolved_profiles_hash": None,
            "profile_sources": [],
            "selected_profile": None,
            "profile_hash": None,
            "main_thread_requirement": None,
            "main_thread_observation": {"status": "pending"},
            "current_stage_assignment": None,
            "stage_agent_assignments": [],
            "pending_switch": None,
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
        "pending_user_decisions": {},
        "delivery_goal": None,
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
                "authorized_review_types": [],
            }
        )
        merged["next_gate"] = "multi_agent_mode_selection"
        merged.setdefault("pending_user_decisions", {})["multi_agent_mode"] = {
            "status": "pending",
            "reason": "legacy authorization could not be verified",
        }
    if not is_terminal_history and "execution_model_policy" not in merged:
        merged["execution_model_policy"] = {
            "mode": "authorization_pending",
            "authorization_status": "legacy_unverified",
            "authorization_scope": "current_delivery",
            "authorization_source": "legacy_state_migration",
            "resolved_profiles": None,
            "resolved_profiles_hash": None,
            "profile_sources": [],
            "selected_profile": None,
            "profile_hash": None,
            "main_thread_requirement": None,
            "main_thread_observation": {"status": "pending"},
            "current_stage_assignment": None,
            "stage_agent_assignments": [],
            "pending_switch": None,
        }
        merged["next_gate"] = "startup_mode_selection"
        merged.setdefault("pending_user_decisions", {})["execution_mode"] = {
            "status": "pending",
            "reason": "legacy model execution mode could not be verified",
        }
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
    merged.setdefault("pending_user_decisions", {})
    merged.setdefault("delivery_goal", None)
    merged.setdefault("confirmation_points", {})
    merged.setdefault("artifact_paths", {})
    merged.setdefault("freeze", {"frozen": False, "scope_version": None})

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
