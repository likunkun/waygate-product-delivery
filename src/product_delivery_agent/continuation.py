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

    pending = _pending_confirmation_blockers(state)
    if pending:
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="waiting for user confirmation",
            blockers=pending,
            next_action=state.get("next_gate"),
        )

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
        return _decision(
            "must_continue",
            can_stop=False,
            reason="stale requirements and planned E2E confirmation requires refresh",
            blockers=["stale_requirements_e2e_confirmation"],
            next_action="requirements_e2e_user_confirmation",
        )
    if state.get("next_gate") == "requirements_e2e_user_confirmation" and (
        "user_confirmed_freeze" in derived_blockers
        or "planned_e2e_user_confirmation" in derived_blockers
    ):
        return _decision(
            "wait_for_user",
            can_stop=True,
            reason="waiting for requirements and planned E2E confirmation",
            blockers=[
                blocker
                for blocker in ("user_confirmed_freeze", "planned_e2e_user_confirmation")
                if blocker in derived_blockers
            ],
            next_action="requirements_e2e_user_confirmation",
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
    return (
        closure_validation.get("status") == "passed"
        and feature_closure.get("status") == "passed"
        and delivery_goal.get("status") == "complete"
    )


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
