"""Codex Goal handoff generation."""

from __future__ import annotations

from typing import Any


class HandoffError(RuntimeError):
    """Raised when Codex Goal handoff cannot be generated."""


def build_codex_goal_handoff(
    state: dict[str, Any],
    *,
    scope: str,
    non_goals: list[str] | None = None,
    verification_commands: list[str] | None = None,
    prohibited_work: list[str] | None = None,
    planned_tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build closure-ready handoff data from validated workflow state."""
    if not scope.strip():
        raise HandoffError("handoff scope is required")
    commands = list(verification_commands or [])
    if not commands:
        raise HandoffError("verification commands are required")

    coverage = state.get("test_coverage_audit", {})
    if not coverage.get("passed"):
        raise HandoffError("passing coverage audit is required before handoff")

    handoff = {
        "scope": scope,
        "non_goals": list(non_goals or []),
        "confirmation_results": _confirmation_results(state),
        "matrix_range": coverage["matrix_range"],
        "latest_test_case": coverage["latest_test_case"],
        "coverage_matrix": list(coverage.get("rows", [])),
        "browser_e2e_obligations": list(
            coverage.get("browser_e2e_obligations", [])
        ),
        "behavior_evidence_obligations": list(
            coverage.get("behavior_evidence_obligations", [])
        ),
        "negative_guard_records": list(coverage.get("negative_guard_records", [])),
        "required_commands": commands,
        "prohibited_work": list(prohibited_work or []),
        "planned_tasks": list(planned_tasks or []),
        "current_task_cursor": (
            planned_tasks[0]["task_id"] if planned_tasks else None
        ),
        "cr_supersession_rules": [
            "Acceptance feedback after freeze must create or update a CR.",
            "Scope changes after freeze must return to version scope confirmation.",
            "Test gaps after freeze must create or update a CR.",
            "Superseded closure artifacts must link to the triggering CR.",
        ],
        "closure_required_after_implementation": True,
    }
    handoff["codex_goal_prompt"] = render_codex_goal_prompt(handoff)
    return handoff


def render_handoff_document(handoff: dict[str, Any]) -> str:
    """Render handoff data as Markdown."""
    lines = [
        "# Codex Goal Handoff",
        "",
        "Status: Frozen",
        "",
        "## Scope",
        handoff["scope"],
        "",
        "## Non-Goals",
        *_bullets(handoff["non_goals"]),
        "",
        "## Confirmation Results",
        *_bullets(
            [
                f"{name}: {'confirmed' if confirmed else 'not confirmed'}"
                for name, confirmed in handoff["confirmation_results"].items()
            ]
        ),
        "",
        "## Closure Readiness",
        f"- Matrix Range: {handoff['matrix_range']}",
        f"- Latest Test Case: {handoff['latest_test_case']}",
        "",
        "## Browser E2E Obligations",
        *_bullets(handoff["browser_e2e_obligations"]),
        "",
        "## Behavior Evidence Obligations",
        *_bullets(handoff["behavior_evidence_obligations"]),
        "",
        "## Negative Guard Records",
        *_bullets(handoff["negative_guard_records"]),
        "",
        "## Required Commands",
        *_bullets(handoff["required_commands"]),
        "",
        "## Planned TASK Queue",
        *_task_bullets(handoff["planned_tasks"]),
        "",
        "## Prohibited Work",
        *_bullets(handoff["prohibited_work"]),
        "",
        "## CR Supersession Rules",
        *_bullets(handoff["cr_supersession_rules"]),
        "",
        "## Codex Goal Prompt",
        handoff["codex_goal_prompt"],
        "",
    ]
    return "\n".join(lines)


def render_codex_goal_prompt(handoff: dict[str, Any]) -> str:
    """Render the prompt intended for an implementation Codex goal."""
    lines = [
        "Implement the frozen Product Delivery version.",
        "",
        f"Scope: {handoff['scope']}",
        "Non-goals: " + "; ".join(handoff["non_goals"]),
        f"Coverage matrix: {handoff['matrix_range']}",
        f"Latest test case: {handoff['latest_test_case']}",
        "Browser E2E obligations: "
        + "; ".join(handoff["browser_e2e_obligations"]),
        "Behavior evidence obligations: "
        + "; ".join(handoff["behavior_evidence_obligations"]),
        "Negative guard records: " + "; ".join(handoff["negative_guard_records"]),
        "Required commands: " + "; ".join(handoff["required_commands"]),
        "Planned TASK queue: "
        + "; ".join(task["task_id"] for task in handoff["planned_tasks"]),
        "Current task cursor: " + str(handoff["current_task_cursor"]),
        "不要在 TASK 未完成时停止。",
        "每轮结束前必须检查 remaining TASK 和 closure guard。",
        "不要在 closure validator 未通过时 complete goal。",
        "Prohibited work: " + "; ".join(handoff["prohibited_work"]),
        "Formal closure remains required after implementation.",
    ]
    return "\n".join(lines)


def _confirmation_results(state: dict[str, Any]) -> dict[str, bool]:
    confirmations = state.get("confirmation_points", {})
    return {
        name: bool(record.get("confirmed"))
        for name, record in confirmations.items()
    }


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _task_bullets(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- None"]
    return [
        "- {task_id}: {title} ({verification})".format(**task)
        for task in items
    ]
