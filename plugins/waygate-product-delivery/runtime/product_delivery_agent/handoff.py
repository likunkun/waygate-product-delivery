"""Codex Goal handoff generation."""

from __future__ import annotations

from typing import Any

from product_delivery_agent.confirmation_policy import USER_CONFIRMATION_TARGETS


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

    implementation_baseline = state.get("implementation_baseline") or {}
    baseline_summary = None
    if implementation_baseline.get("status") == "ready":
        baseline_summary = {
            "baseline_sha256": implementation_baseline.get("baseline_sha256"),
            "artifact_path": implementation_baseline.get("artifact_path"),
            "prototype_path": implementation_baseline.get("prototype_path"),
            "product_domain_sha256": implementation_baseline.get(
                "product_domain_sha256"
            ),
            "visual_policy_sha256": implementation_baseline.get(
                "visual_policy_sha256"
            ),
        }
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
        "implementation_baseline": baseline_summary,
        "current_task_prompt_path": (
            "artifacts/current-task-prompt.md" if baseline_summary else None
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
    baseline = handoff.get("implementation_baseline")
    if isinstance(baseline, dict):
        lines.extend(
            [
                "",
                "你正在实现用户已确认的 UI 产品基线，不是在重新设计。",
                "原型是权威输入；禁止自行增删、移动、合并或重设计可见 UI。",
                "无法按原型实现时停止当前 TASK 并发起 CR，不得静默降级。",
                "检查失败时修复生产实现，不得修改冻结原型、mask 或阈值。",
                "Implementation baseline: " + str(baseline["baseline_sha256"]),
                "Implementation baseline artifact: "
                + str(baseline["artifact_path"]),
                "Current task prompt: "
                + str(handoff["current_task_prompt_path"]),
            ]
        )
    return "\n".join(lines)


def render_current_task_prompt(
    task: dict[str, Any],
    implementation_baseline: dict[str, Any],
) -> str:
    """Render only the prototype units bound to the current task."""
    lines = [
        "# Current Prototype-Bound TASK",
        "",
        f"Task: {task['task_id']} — {task['title']}",
        f"Description: {task['description']}",
        f"Verification: {task['verification']}",
    ]
    if task.get("ui_impact") == "none":
        lines.extend(
            [
                "UI impact: none",
                "Reason: " + str(task.get("ui_impact_reason") or ""),
            ]
        )
        return "\n".join(lines) + "\n"

    baseline_hash = implementation_baseline.get("baseline_sha256")
    lines.extend(
        [
            "UI impact: prototype_bound",
            "Implementation baseline: " + str(baseline_hash),
            "Prototype HTML: "
            + str(implementation_baseline.get("prototype_path")),
            "Visual policy: "
            + str(implementation_baseline.get("visual_policy_sha256")),
            "",
            "你正在实现用户已确认的 UI 产品基线，不是在重新设计。",
            "必须保持绑定页面的 route、区域层级、控件顺序、关键状态和交互结果一致。",
            "允许调整内部代码架构；禁止自行重设计可见 UI。",
            "完成前必须生成生产截图、语义快照和一致性证据。",
            "",
            "## Bound Prototype Units",
        ]
    )
    unit_map = {
        (
            unit.get("surface_id"),
            unit.get("state_id"),
            unit.get("viewport_class"),
        ): unit
        for unit in implementation_baseline.get("units", [])
    }
    for binding in task.get("prototype_bindings", []):
        for viewport in binding.get("viewport_classes", []):
            key = (
                binding.get("surface_id"),
                binding.get("state_id"),
                viewport,
            )
            unit = unit_map.get(key)
            if unit is None:
                raise HandoffError(f"current task references unknown baseline unit: {key}")
            lines.extend(
                [
                    f"- Surface: {unit['surface_id']}",
                    f"  State: {unit['state_id']}",
                    f"  Viewport: {unit['viewport_class']}",
                    f"  Route: {unit['route']}",
                    "  Reference screenshot: "
                    + str(unit["prototype_screenshot_path"]),
                    "  Regions: " + ", ".join(binding["region_ids"]),
                    "  Interactions: "
                    + ", ".join(binding["interaction_ids"]),
                ]
            )
    return "\n".join(lines) + "\n"


def _confirmation_results(state: dict[str, Any]) -> dict[str, bool]:
    confirmations = state.get("user_confirmations", {})
    ui = state.get("ui_prototype", {})
    return {
        name: (
            bool(ui.get("confirmed_by_user"))
            if name == "ui_prototype"
            else name in confirmations
        )
        for name in sorted(USER_CONFIRMATION_TARGETS)
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
