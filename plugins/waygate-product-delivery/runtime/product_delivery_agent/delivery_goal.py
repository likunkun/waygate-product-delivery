"""Goal-driven implementation closure helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from product_delivery_agent.gatekeeper import state_requires_delivery_goal


class DeliveryGoalError(RuntimeError):
    """Raised when the implementation goal cannot advance or stop."""


REQUIRED_TASK_FIELDS = ("task_id", "title", "description", "verification")


def normalize_planned_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize a planned implementation task queue."""
    if not tasks:
        raise DeliveryGoalError("planned TASK queue is required")
    normalized = []
    seen: set[str] = set()
    for index, task in enumerate(tasks, start=1):
        missing = [
            field_name
            for field_name in REQUIRED_TASK_FIELDS
            if not _has_value(task.get(field_name))
        ]
        if missing:
            raise DeliveryGoalError(
                f"planned task row {index} missing fields: "
                + ", ".join(missing)
            )
        task_id = str(task["task_id"])
        if task_id in seen:
            raise DeliveryGoalError(f"duplicate planned task: {task_id}")
        seen.add(task_id)
        normalized.append(
            {
                "task_id": task_id,
                "title": str(task["title"]),
                "description": str(task["description"]),
                "verification": str(task["verification"]),
                "planned_task_hash": str(
                    task.get("planned_task_hash") or _stable_hash(
                        {
                            "task_id": task_id,
                            "title": str(task["title"]),
                            "description": str(task["description"]),
                            "verification": str(task["verification"]),
                        }
                    )
                ),
            }
        )
    return normalized


def planned_tasks_from_coverage(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive a conservative TASK queue from the coverage audit rows."""
    rows = state.get("test_coverage_audit", {}).get("rows", [])
    task_ids = []
    for row in rows:
        task_id = row.get("task")
        if _has_value(task_id) and task_id not in task_ids:
            task_ids.append(task_id)
    if not task_ids:
        return []
    return [
        {
            "task_id": task_id,
            "title": task_id,
            "description": f"Complete {task_id} from the frozen coverage matrix.",
            "verification": "Run required handoff commands.",
        }
        for task_id in task_ids
    ]


def build_delivery_goal(
    *,
    feature_slug: str | None,
    scope: str,
    planned_tasks: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    """Create an active Product Delivery implementation goal."""
    tasks = normalize_planned_tasks(planned_tasks)
    return {
        "status": "active",
        "objective": (
            "Implement the frozen Product Delivery scope for "
            + str(feature_slug or "current feature")
            + " through formal closure."
        ),
        "scope": scope,
        "planned_tasks": tasks,
        "completed_tasks": [],
        "task_completion_artifacts": {},
        "current_task_cursor": tasks[0]["task_id"],
        "closure_required": True,
        "closure_validation_required": True,
        "e2e_evidence_required": True,
        "created_at": created_at,
        "next_action": tasks[0]["task_id"],
    }


def derive_remaining_tasks(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return planned tasks not yet recorded as complete."""
    goal = state.get("delivery_goal") or {}
    completed = set(goal.get("completed_tasks", []))
    return [
        task
        for task in goal.get("planned_tasks", [])
        if task.get("task_id") not in completed
    ]


def record_task_completion(
    state: dict[str, Any],
    task_id: str,
    artifact: dict[str, Any],
    *,
    completed_at: str,
) -> dict[str, Any]:
    """Return a state copy with one planned task recorded complete."""
    next_state = dict(state)
    goal = dict(next_state.get("delivery_goal") or {})
    if goal.get("status") not in {"active", "implementation_in_progress"}:
        raise DeliveryGoalError("active delivery goal is required before TASK completion")
    planned = {task["task_id"]: task for task in goal.get("planned_tasks", [])}
    if task_id not in planned:
        raise DeliveryGoalError(f"task is not in planned TASK queue: {task_id}")
    cursor = goal.get("current_task_cursor")
    if cursor != task_id:
        raise DeliveryGoalError(
            f"task completion must match current task cursor: {cursor}"
        )
    _validate_task_artifact(task_id, planned[task_id], artifact)
    completed = list(goal.get("completed_tasks", []))
    if task_id in completed:
        raise DeliveryGoalError(f"task already completed: {task_id}")
    if task_id not in completed:
        completed.append(task_id)
    goal["completed_tasks"] = completed
    task_artifacts = dict(goal.get("task_completion_artifacts", {}))
    task_artifacts[task_id] = {
        **artifact,
        "completed_at": completed_at,
    }
    goal["task_completion_artifacts"] = task_artifacts
    remaining = [
        task
        for task in goal.get("planned_tasks", [])
        if task.get("task_id") not in set(completed)
    ]
    if remaining:
        goal["status"] = "implementation_in_progress"
        goal["current_task_cursor"] = remaining[0]["task_id"]
        goal["next_action"] = remaining[0]["task_id"]
        next_state["status"] = "implementation_in_progress"
        next_state["stage"] = "implementation_in_progress"
    else:
        goal["status"] = "implementation_tasks_complete"
        goal["current_task_cursor"] = None
        goal["next_action"] = "record_executed_evidence_and_closure"
        next_state["status"] = "implementation_tasks_complete"
        next_state["stage"] = "implementation_tasks_complete"
    next_state["delivery_goal"] = goal
    return next_state


def assert_goal_can_stop(state: dict[str, Any]) -> dict[str, Any]:
    """Raise unless the active goal can stop or complete safely."""
    goal = state.get("delivery_goal")
    if not goal:
        if state_requires_delivery_goal(state):
            raise DeliveryGoalError(
                "active delivery goal is required after handoff or terminal state"
            )
        return {
            "status": "allowed",
            "reason": "no delivery goal is active",
            "remaining_tasks": [],
        }
    remaining = derive_remaining_tasks(state)
    if remaining:
        task_ids = [task["task_id"] for task in remaining]
        raise DeliveryGoalError("remaining TASKs block stop: " + ", ".join(task_ids))
    if (
        state.get("status") != "closed"
        or state.get("closure_validation", {}).get("status") != "passed"
    ):
        raise DeliveryGoalError(
            "closure validator has not passed; goal must stay active"
        )
    return {
        "status": "allowed",
        "reason": "all tasks complete and closure validator passed",
        "remaining_tasks": [],
    }


def mark_goal_closure_failed(state: dict[str, Any]) -> dict[str, Any]:
    """Keep the implementation goal active after closure validation failure."""
    if not state.get("delivery_goal"):
        return state
    next_state = dict(state)
    goal = {
        **next_state["delivery_goal"],
        "status": "active",
        "next_action": "fix_closure_evidence",
    }
    next_state["delivery_goal"] = goal
    return next_state


def mark_goal_complete(state: dict[str, Any], *, completed_at: str) -> dict[str, Any]:
    """Mark the delivery goal complete after all closure gates pass."""
    if not state.get("delivery_goal"):
        return state
    remaining = derive_remaining_tasks(state)
    if remaining:
        task_ids = [task["task_id"] for task in remaining]
        raise DeliveryGoalError(
            "closure cannot complete while TASKs remain: " + ", ".join(task_ids)
        )
    next_state = dict(state)
    goal = {
        **next_state["delivery_goal"],
        "status": "complete",
        "current_task_cursor": None,
        "next_action": "goal_complete",
        "completed_at": completed_at,
    }
    next_state["delivery_goal"] = goal
    return next_state


def render_implementation_goal(goal: dict[str, Any]) -> str:
    """Render a delivery goal artifact."""
    lines = [
        "# Implementation Goal",
        "",
        f"Status: {goal['status']}",
        f"Objective: {goal['objective']}",
        f"Current Task Cursor: {goal['current_task_cursor']}",
        "",
        "## Stop Rules",
        "- Do not stop while planned TASKs remain.",
        "- Do not complete the goal before closure validator passes.",
        "- If closure fails, keep the goal active and fix closure evidence.",
        "",
    ]
    return "\n".join(lines)


def render_task_queue(goal: dict[str, Any]) -> str:
    """Render the planned TASK queue."""
    lines = [
        "# Task Queue",
        "",
        "| task_id | title | verification | status |",
        "| --- | --- | --- | --- |",
    ]
    completed = set(goal.get("completed_tasks", []))
    for task in goal["planned_tasks"]:
        status = "complete" if task["task_id"] in completed else "pending"
        lines.append(
            "| {task_id} | {title} | {verification} | {status} |".format(
                status=status,
                **task,
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_stop_guard_result(result: dict[str, Any]) -> str:
    """Render the stop guard result."""
    lines = [
        "# Stop Guard Result",
        "",
        f"- status: {result['status']}",
        f"- reason: {result['reason']}",
        "- remaining_tasks:",
    ]
    remaining = result.get("remaining_tasks", [])
    if remaining:
        lines.extend(f"  - {task}" for task in remaining)
    else:
        lines.append("  - None")
    lines.append("")
    return "\n".join(lines)


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_task_artifact(
    task_id: str,
    planned_task: dict[str, Any],
    artifact: dict[str, Any],
) -> None:
    if not isinstance(artifact, dict):
        raise DeliveryGoalError("task completion artifact is required")
    required = [
        "artifact_path",
        "artifact_sha256",
        "verification_command",
        "verification_exit_code",
        "verification_output",
        "planned_task_hash",
    ]
    missing = [
        field_name
        for field_name in required
        if artifact.get(field_name) is None
        or (isinstance(artifact.get(field_name), str) and not artifact.get(field_name).strip())
    ]
    if missing:
        raise DeliveryGoalError(
            "task completion artifact missing fields: " + ", ".join(missing)
        )
    if artifact.get("planned_task_hash") != planned_task.get("planned_task_hash"):
        raise DeliveryGoalError(f"planned_task_hash mismatch for {task_id}")
    if artifact.get("verification_command") != planned_task.get("verification"):
        raise DeliveryGoalError(f"verification_command mismatch for {task_id}")
    if artifact.get("verification_exit_code") != 0:
        raise DeliveryGoalError(f"verification failed for {task_id}")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
