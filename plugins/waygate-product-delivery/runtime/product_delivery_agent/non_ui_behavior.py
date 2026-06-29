"""Non-UI behavior contract gate validation."""

from __future__ import annotations

from typing import Any

NON_UI_BEHAVIOR_TAXONOMY = (
    "entry_points",
    "inputs_outputs",
    "exceptions",
    "recovery",
    "permissions",
    "long_tasks",
    "state_transitions",
    "boundary_conditions",
)


def validate_non_ui_behavior_contract(contract: dict[str, Any]) -> list[str]:
    """Return missing fields for the non-UI behavior contract gate."""
    missing: list[str] = []
    for field_name in (
        "contract_name",
        "entry_points",
        "inputs",
        "outputs",
        "behavior_paths",
        "negative_boundary_records",
        "limitations",
    ):
        if not _has_values(contract.get(field_name)):
            missing.append(field_name)

    taxonomy = contract.get("taxonomy")
    if not isinstance(taxonomy, dict):
        missing.append("taxonomy")
        return missing

    for taxonomy_field in NON_UI_BEHAVIOR_TAXONOMY:
        if not _has_values(taxonomy.get(taxonomy_field)):
            missing.append(f"taxonomy:{taxonomy_field}")
    return missing


def render_non_ui_behavior_contract(contract: dict[str, Any]) -> str:
    """Render the behavior contract as a local Markdown artifact."""
    taxonomy = contract["taxonomy"]
    lines = [
        "# Non-UI Behavior Contract",
        "",
        "Status: Draft",
        "",
        f"Contract: {contract['contract_name']}",
        "",
        "## Entry Points",
        *_bullets(contract["entry_points"]),
        "",
        "## Inputs",
        *_bullets(contract["inputs"]),
        "",
        "## Outputs",
        *_bullets(contract["outputs"]),
        "",
        "## Scenario Taxonomy",
    ]
    for taxonomy_field in NON_UI_BEHAVIOR_TAXONOMY:
        lines.extend(
            [
                "",
                f"### {taxonomy_field.replace('_', ' ').title()}",
                *_bullets(taxonomy[taxonomy_field]),
            ]
        )
    lines.extend(
        [
            "",
            "## Behavior Evidence Candidates",
            *_bullets(contract["behavior_paths"]),
            "",
            "## Negative Boundary Records",
            *_bullets(contract["negative_boundary_records"]),
            "",
            "## Accepted Limitations",
            *_bullets(contract["limitations"]),
            "",
        ]
    )
    return "\n".join(lines)


def _has_values(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, str) and item.strip() for item in value)
    return False


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]
