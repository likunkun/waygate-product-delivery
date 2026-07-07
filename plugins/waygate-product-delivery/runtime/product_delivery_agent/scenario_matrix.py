"""Scenario matrix validation and rendering."""

from __future__ import annotations

from typing import Any


class ScenarioMatrixError(RuntimeError):
    """Raised when a scenario matrix cannot be accepted."""


REQUIRED_SCENARIO_FIELDS = (
    "scenario_id",
    "role",
    "user_story",
    "journey",
    "path_type",
    "risk_level",
    "blocking_level",
    "review_status",
    "negative_boundary",
    "planned_e2e_case",
)


def validate_scenario_matrix(rows: list[dict[str, Any]]) -> None:
    """Validate draft scenario matrix rows before multi-agent review."""
    if not rows:
        raise ScenarioMatrixError("scenario matrix requires at least one row")
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = [
            field_name
            for field_name in REQUIRED_SCENARIO_FIELDS
            if not _has_value(row.get(field_name))
        ]
        if missing:
            raise ScenarioMatrixError(
                f"row {index} missing scenario fields: " + ", ".join(missing)
            )
        scenario_id = str(row["scenario_id"])
        if scenario_id in seen_ids:
            raise ScenarioMatrixError(f"duplicate scenario_id: {scenario_id}")
        seen_ids.add(scenario_id)


def render_scenario_matrix(rows: list[dict[str, Any]]) -> str:
    """Render scenario matrix rows as Markdown."""
    lines = [
        "# Scope Scenario Matrix",
        "",
        "Scope means version boundary and scenario mapping, not a scope-control failure finding.",
        "",
        "| Scenario | Role | Story | Journey ID | Journey | Acceptance Anchors | Path | Risk | Blocking | Review | Boundary | Planned Behavior Evidence / Tests |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        render_row = {
            **row,
            "journey_id": row.get("journey_id", ""),
            "acceptance_anchors": row.get("acceptance_anchors", ""),
        }
        lines.append(
            "| {scenario_id} | {role} | {user_story} | {journey_id} | "
            "{journey} | {acceptance_anchors} | {path_type} | {risk_level} | "
            "{blocking_level} | {review_status} | {negative_boundary} | "
            "{planned_e2e_case} |".format(**render_row)
        )
    lines.append("")
    return "\n".join(lines)


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
