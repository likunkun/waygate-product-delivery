"""Continuation guard for active Product Delivery main flow."""

from __future__ import annotations

from typing import Any

from product_delivery_agent.confirmation_policy import (
    pending_user_confirmation_blockers,
)
from product_delivery_agent.delivery_goal import derive_remaining_tasks
from product_delivery_agent.gatekeeper import (
    closure_integrity_errors,
    derive_blockers,
    implementation_integrity_errors,
)
from product_delivery_agent.host_goal import (
    canonical_closure_passed,
    current_codex_thread_id,
)


EXTERNAL_BLOCKER_MARKERS = (
    "external",
    "environment",
    "dependency",
    "credential",
    "secret",
    "network",
    "database",
    "port",
)
REPEATED_FAILURE_MARKERS = (
    "consecutive_failure",
    "repeated_failure",
    "failed_three_times",
    "three_failed_attempts",
)
USER_WAIT_MARKERS = (
    "user_clarification",
    "requirements_clarification",
    "awaiting_user",
    "needs_user",
    "human_input",
    "manual_confirmation",
)


def derive_continuation_status(state: dict[str, Any]) -> dict[str, Any]:
    """Classify whether an active Product Delivery flow may stop."""
    if not state or not state.get("active"):
        return _decision(
            "inactive",
            can_stop=True,
            reason="product delivery is inactive",
        )

    blocking_errors = _state_integrity_errors(state)
    if blocking_errors:
        return _decision(
            "blocked",
            can_stop=False,
            reason="product delivery state is blocked",
            blockers=blocking_errors,
            next_action=state.get("next_gate"),
        )

    if _is_complete(state):
        return _decision(
            "complete",
            can_stop=True,
            reason="product delivery closure is complete",
            next_action=state.get("next_gate"),
        )

    pending_decisions = state.get("pending_user_decisions") or {}
    policy = state.get("multi_agent_policy") or {}
    startup_blockers = []
    if "multi_agent_mode" in pending_decisions or policy.get(
        "execution_authorization"
    ) in {"pending", "legacy_unverified", "invalidated"}:
        startup_blockers.append("pending_user_decision:multi_agent_mode")
    if startup_blockers:
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="waiting for startup review mode authorization",
            blockers=startup_blockers,
            next_action="startup_mode_selection",
        )

    pending = _pending_confirmation_blockers(state)
    if pending:
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="waiting for user confirmation",
            blockers=pending,
            next_action=state.get("next_gate"),
        )

    host_goal_decision = _host_goal_owner_continuation_decision(
        state
    ) or _host_goal_continuation_decision(state)
    if host_goal_decision:
        return host_goal_decision

    blocker_names = _string_list(state.get("blocked_until"))
    derived_blockers = derive_blockers(state)
    derived_stale_blockers = [
        blocker for blocker in derived_blockers if blocker.startswith("stale_")
    ]
    review_gate = _review_gate_from_blockers(blocker_names + derived_stale_blockers)
    if review_gate:
        return _decision(
            "must_continue",
            can_stop=False,
            reason="stale or missing review gate requires refresh",
            blockers=[review_gate["blocker"]],
            next_action=review_gate["next_action"],
        )
    if "stale_requirements_e2e_confirmation" in blocker_names + derived_stale_blockers:
        product_baseline_stale = "product_baseline_user_confirmation" in derived_blockers
        return _decision(
            "must_continue",
            can_stop=False,
            reason="stale layered confirmation requires review and preparation",
            blockers=["stale_requirements_e2e_confirmation"],
            next_action=(
                "product_baseline_confirmation_preparation"
                if product_baseline_stale
                else "test_coverage_confirmation_preparation"
            ),
        )
    user_wait = _matching_blockers(blocker_names, USER_WAIT_MARKERS)
    if user_wait or state.get("paused"):
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="waiting for user clarification or manual resume",
            blockers=user_wait or ["paused"],
            next_action=state.get("next_gate"),
        )

    external_blockers = _matching_blockers(blocker_names, EXTERNAL_BLOCKER_MARKERS)
    repeated_failures = _matching_blockers(blocker_names, REPEATED_FAILURE_MARKERS)
    if external_blockers or repeated_failures:
        blockers = external_blockers + repeated_failures
        return _decision(
            "blocked",
            can_stop=True,
            reason="blocked by external state or repeated failures",
            blockers=blockers,
            next_action=state.get("next_gate"),
        )

    remaining_tasks = derive_remaining_tasks(state)
    if remaining_tasks:
        task_ids = [str(task.get("task_id")) for task in remaining_tasks]
        return _decision(
            "must_continue",
            can_stop=False,
            reason="planned TASKs remain",
            blockers=[f"remaining_task:{task_id}" for task_id in task_ids],
            next_action=_next_goal_action(state) or task_ids[0],
            remaining_tasks=task_ids,
        )

    next_action = _next_goal_action(state) or state.get("next_gate")
    if _has_text(next_action):
        return _decision(
            "must_continue",
            can_stop=False,
            reason="next Product Delivery gate is ready",
            blockers=[f"next_gate:{next_action}"],
            next_action=str(next_action),
        )

    return _decision(
        "blocked",
        can_stop=True,
        reason="active Product Delivery state has no next gate",
        blockers=["next_gate_missing"],
    )


def _decision(
    status: str,
    *,
    can_stop: bool,
    reason: str,
    blockers: list[str] | None = None,
    next_action: Any = None,
    remaining_tasks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "can_stop": can_stop,
        "reason": reason,
        "blockers": blockers or [],
        "next_action": str(next_action) if _has_text(next_action) else None,
        "remaining_tasks": remaining_tasks or [],
    }


def _state_integrity_errors(state: dict[str, Any]) -> list[str]:
    errors = list(state.get("protocol_errors") or [])
    closure_validation = state.get("closure_validation") or {}
    if state.get("status") == "closure_failed":
        errors.extend(_string_list(closure_validation.get("errors")))
    elif closure_integrity_errors(state):
        errors.extend(closure_integrity_errors(state))
    if state.get("status") == "implementation_blocked":
        errors.extend(implementation_integrity_errors(state))
    return _dedupe(errors)


def _is_complete(state: dict[str, Any]) -> bool:
    closure_validation = state.get("closure_validation") or {}
    feature_closure = state.get("feature_closure") or {}
    delivery_goal = state.get("delivery_goal") or {}
    internal_complete = (
        closure_validation.get("status") == "passed"
        and feature_closure.get("status") == "passed"
        and delivery_goal.get("status") == "complete"
    )
    if not internal_complete:
        return False
    binding = state.get("host_goal_binding") or {}
    if binding.get("status") in {None, "not_required"}:
        return True
    return binding.get("status") == "complete"


def _host_goal_continuation_decision(
    state: dict[str, Any],
) -> dict[str, Any] | None:
    if not (state.get("handoff") or state.get("delivery_goal")):
        return None
    binding = state.get("host_goal_binding") or {}
    status = binding.get("status")
    if status in {
        "activation_pending",
        "creation_ready",
        "verification_pending",
    }:
        return _decision(
            "must_continue",
            can_stop=False,
            reason="Codex Host Goal activation is required",
            blockers=[f"host_goal:{status}"],
            next_action="host_goal_activation",
        )
    if status in {"legacy_unverified", "reactivation_required"}:
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="Codex Host Goal requires explicit recovery authorization",
            blockers=[f"host_goal:{status}"],
            next_action="host_goal_reactivation_authorization",
        )
    if status == "blocked":
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="Codex Host Goal is blocked pending explicit user resume",
            blockers=["host_goal:blocked"],
            next_action="host_goal_resume_required",
        )
    if status == "unavailable":
        return _decision(
            "blocked",
            can_stop=True,
            reason="Codex Host Goal tools are unavailable",
            blockers=["autonomous_continuation_unavailable"],
            next_action="use_goal_capable_codex_host",
        )
    if canonical_closure_passed(state) and status != "complete":
        return _decision(
            "must_continue",
            can_stop=False,
            reason="canonical closure passed but Host Goal is not complete",
            blockers=[f"host_goal:{status or 'missing'}"],
            next_action="complete_host_goal",
        )
    return None


def _host_goal_owner_continuation_decision(
    state: dict[str, Any],
) -> dict[str, Any] | None:
    if not (state.get("handoff") or state.get("delivery_goal")):
        return None
    owner = state.get("host_goal_owner") or {}
    binding = state.get("host_goal_binding") or {}
    owner_status = owner.get("status")
    coordinator_thread_id = owner.get("coordinator_thread_id")
    binding_owner_thread_id = binding.get("owner_thread_id")
    observed_thread_id = (binding.get("host_identifiers") or {}).get("threadId")
    current_thread_id = current_codex_thread_id()
    if owner_status != "claimed":
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="Codex Host Goal coordinator ownership requires recovery",
            blockers=[f"host_goal_owner:{owner_status or 'missing'}"],
            next_action="host_goal_owner_recovery",
        )
    if binding_owner_thread_id != coordinator_thread_id or (
        observed_thread_id and observed_thread_id != coordinator_thread_id
    ):
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="Codex Host Goal binding belongs to a different thread",
            blockers=["host_goal_owner:thread_mismatch"],
            next_action="host_goal_owner_recovery",
        )
    if not current_thread_id or current_thread_id != coordinator_thread_id:
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="current Codex thread does not own the delivery Host Goal",
            blockers=["host_goal_owner:current_thread_mismatch"],
            next_action="host_goal_owner_recovery",
        )
    return None


def _pending_confirmation_blockers(state: dict[str, Any]) -> list[str]:
    return pending_user_confirmation_blockers(state)


def _review_gate_from_blockers(blockers: list[str]) -> dict[str, str] | None:
    ordered = (
        ("stale_multi_agent_scenario_review", "multi_agent_scenario_review"),
        ("multi_agent_scenario_review", "multi_agent_scenario_review"),
        ("stale_multi_agent_test_coverage_review", "multi_agent_test_coverage_review"),
        ("multi_agent_test_coverage_review", "multi_agent_test_coverage_review"),
        ("stale_multi_agent_test_review", "multi_agent_test_review"),
        ("multi_agent_test_review", "multi_agent_test_review"),
    )
    for blocker, next_action in ordered:
        if blocker in blockers:
            return {"blocker": blocker, "next_action": next_action}
    return None


def _matching_blockers(blockers: list[str], markers: tuple[str, ...]) -> list[str]:
    matched = []
    for blocker in blockers:
        lowered = blocker.lower()
        if any(marker in lowered for marker in markers):
            matched.append(blocker)
    return matched


def _next_goal_action(state: dict[str, Any]) -> str | None:
    goal = state.get("delivery_goal") or {}
    for key in ("next_action", "current_task_cursor"):
        value = goal.get(key)
        if _has_text(value) and value != "goal_complete":
            return str(value)
    implementation = state.get("implementation") or {}
    value = implementation.get("current_task")
    if _has_text(value) and value != "COMPLETE":
        return str(value)
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if _has_text(item)]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
