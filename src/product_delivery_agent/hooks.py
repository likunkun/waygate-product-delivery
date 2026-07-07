"""Hook-facing recovery guardrails for active product delivery projects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, CORE_ARTIFACTS
from product_delivery_agent.confirmation_policy import (
    confirmed_user_confirmation_targets,
    pending_user_confirmation_blockers,
)
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.gatekeeper import (
    closure_integrity_errors,
    implementation_integrity_errors,
    normalize_state_protocol,
)


@dataclass(frozen=True)
class HookResult:
    """Reviewable output from a hook or guardrail check."""

    active: bool
    silent: bool
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    passed: bool = True


def build_resume_context(project_root: str | Path) -> HookResult:
    """Build state context for session start or resume hooks."""
    state = _load_valid_state(project_root)
    if not _is_active(state):
        return _silent()
    invalid = _protocol_failure_result(state)
    if invalid:
        return invalid
    return HookResult(
        active=True,
        silent=False,
        message=_state_summary(state, stage_label="stage"),
    )


def build_prompt_context(project_root: str | Path) -> HookResult:
    """Build prompt-time context for active projects."""
    state = _load_valid_state(project_root)
    if not _is_active(state):
        return _silent()
    invalid = _protocol_failure_result(state)
    if invalid:
        return invalid
    return HookResult(
        active=True,
        silent=False,
        message=_state_summary(state, stage_label="current_stage"),
    )


def check_pre_compaction(project_root: str | Path) -> HookResult:
    """Check that active workflow state is durable before compaction."""
    root = Path(project_root)
    state_path = root / ARTIFACT_ROOT / "state.json"
    if not state_path.exists():
        if (root / ARTIFACT_ROOT).exists():
            return HookResult(
                active=True,
                silent=False,
                passed=False,
                warnings=["Product delivery state is missing before compaction."],
                missing_items=["state.json"],
            )
        return _silent()

    try:
        state = normalize_state_protocol(_read_state_file(state_path))
    except (OSError, json.JSONDecodeError):
        return HookResult(
            active=True,
            silent=False,
            passed=False,
            warnings=["Product delivery state is not readable before compaction."],
            missing_items=["state.json valid JSON"],
        )

    if not _is_active(state):
        return _silent()

    invalid = _protocol_failure_result(state)
    if invalid:
        return invalid

    missing = []
    if not state.get("updated_at"):
        missing.append("state.updated_at")

    return HookResult(
        active=True,
        silent=False,
        passed=not missing,
        message="pre_compaction_state_check=passed" if not missing else "",
        warnings=[] if not missing else ["Product delivery state is incomplete."],
        missing_items=missing,
    )


def check_stop_guardrail(project_root: str | Path) -> HookResult:
    """Report missing artifacts or confirmations before an active project stops."""
    state = _load_valid_state(project_root)
    if not _is_active(state):
        return _silent()

    invalid = _protocol_failure_result(state)
    if invalid:
        return invalid

    continuation = derive_continuation_status(state)
    if continuation["status"] == "wait_for_user":
        return HookResult(
            active=True,
            silent=False,
            passed=True,
            message="continuation_guard=wait_for_user",
            missing_items=continuation["blockers"],
        )
    if continuation["status"] == "complete":
        return HookResult(
            active=True,
            silent=False,
            passed=True,
            message="continuation_guard=complete",
        )

    missing = _missing_stop_items(Path(project_root), state)
    if not continuation["can_stop"]:
        missing.extend(continuation["blockers"])
    return HookResult(
        active=True,
        silent=False,
        passed=not missing,
        message=(
            "stop_guardrail=passed"
            if not missing
            else f"continuation_guard={continuation['status']}"
        ),
        warnings=[] if not missing else [_stop_guard_warning(continuation)],
        missing_items=missing,
    )


def check_final_summary_guardrail(project_root: str | Path) -> HookResult:
    """Check whether an active main flow may produce a final summary."""
    return check_stop_guardrail(project_root)


def _silent() -> HookResult:
    return HookResult(active=False, silent=True)


def _load_valid_state(project_root: str | Path) -> dict[str, Any]:
    state_path = Path(project_root) / ARTIFACT_ROOT / "state.json"
    if not state_path.exists():
        return {}
    try:
        return normalize_state_protocol(_read_state_file(state_path))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_state_file(state_path: Path) -> dict[str, Any]:
    with state_path.open("r", encoding="utf-8") as state_file:
        return json.load(state_file)


def _is_active(state: dict[str, Any]) -> bool:
    return bool(state.get("active"))


def _protocol_failure_result(state: dict[str, Any]) -> HookResult | None:
    protocol_errors = list(state.get("protocol_errors", []))
    if state.get("status") == "implementation_blocked" or protocol_errors:
        if not protocol_errors:
            protocol_errors = implementation_integrity_errors(state)
        return HookResult(
            active=True,
            silent=False,
            passed=False,
            message="product_delivery_implementation_state=blocked",
            warnings=["Product delivery implementation state is invalid."],
            missing_items=protocol_errors,
        )

    errors = list(state.get("closure_validation", {}).get("errors", []))
    if state.get("status") != "closure_failed" and not closure_integrity_errors(state):
        return None
    if not errors:
        errors = closure_integrity_errors(state)
    return HookResult(
        active=True,
        silent=False,
        passed=False,
        message="product_delivery_closure_state=blocked",
        warnings=["Product delivery closure state is invalid."],
        missing_items=errors,
    )


def _state_summary(state: dict[str, Any], *, stage_label: str) -> str:
    parts = [
        f"{stage_label}={state.get('stage', 'unknown')}",
        f"project_type={state.get('project_type') or 'unselected'}",
    ]
    if state.get("next_gate"):
        parts.append(f"next_gate={state['next_gate']}")

    continuation = derive_continuation_status(state)
    parts.append(f"continuation={continuation['status']}")
    if continuation.get("next_action"):
        parts.append(f"next_action={continuation['next_action']}")

    confirmed = confirmed_user_confirmation_targets(state)
    pending = [
        blocker.removeprefix("pending_confirmation:")
        for blocker in pending_user_confirmation_blockers(state)
    ]
    if confirmed:
        parts.append("confirmed=" + ",".join(confirmed))
    if pending:
        parts.append("pending=" + ",".join(pending))

    skill_records = sorted(state.get("skill_records", {}))
    if skill_records:
        parts.append("skill_records=" + ",".join(skill_records))

    return "; ".join(parts)


def _stop_guard_warning(continuation: dict[str, Any]) -> str:
    if continuation["status"] == "must_continue":
        return "Product Delivery main flow has an actionable next gate."
    if continuation["status"] == "blocked":
        return "Product Delivery state is blocked."
    return "Missing product delivery evidence before stop."


def _missing_stop_items(project_root: Path, state: dict[str, Any]) -> list[str]:
    required = ["product_brief", "version_scope"]
    project_type = state.get("project_type")
    if project_type == "ui":
        required.append("ui_prototype_review")
    elif project_type == "non_ui":
        required.append("non_ui_behavior_contract")
    else:
        return ["confirmation:project_type"]

    missing: list[str] = []
    artifact_paths = state.get("artifact_paths", {})
    for artifact_name in required:
        artifact_path = artifact_paths.get(
            artifact_name,
            f"artifacts/{CORE_ARTIFACTS[artifact_name]}",
        )
        if not (project_root / ARTIFACT_ROOT / artifact_path).is_file():
            missing.append(f"artifact:{artifact_name}")

    return missing
