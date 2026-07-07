"""Local artifact and state protocol for product delivery projects."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.gatekeeper import normalize_state_protocol

ARTIFACT_ROOT = ".product-delivery"

CORE_ARTIFACTS = {
    "product_brief": "product-brief.md",
    "version_scope": "version-scope.md",
    "ui_prototype_review": "ui-prototype-review.md",
    "non_ui_behavior_contract": "non-ui-behavior-contract.md",
    "test_coverage_audit": "test-coverage-audit.md",
    "handoff": "handoff.md",
}


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
        },
        "multi_agent_policy": {
            "mode": "spawned_subagents_required",
        },
        "ui_prototype": {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
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
        },
    )
    merged.setdefault(
        "multi_agent_policy",
        {
            "mode": "spawned_subagents_required",
        },
    )
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
    merged.setdefault(
        "ui_prototype",
        {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
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
