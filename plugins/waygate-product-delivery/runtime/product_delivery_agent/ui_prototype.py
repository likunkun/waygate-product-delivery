"""UI prototype review gate validation."""

from __future__ import annotations

from typing import Any

UI_PROTOTYPE_TAXONOMY = (
    "roles",
    "main_paths",
    "exceptions",
    "recovery",
    "permissions",
    "long_tasks",
    "mobile",
    "keyboard",
    "negative_scope_boundaries",
)


def validate_ui_prototype_review(review: dict[str, Any]) -> list[str]:
    """Return missing review fields for the UI prototype gate."""
    missing: list[str] = []
    for field_name in (
        "prototype_path",
        "pages",
        "states",
        "journeys",
        "limitations",
        "browser_e2e_candidates",
        "negative_scope_guard_candidates",
    ):
        if not _has_values(review.get(field_name)):
            missing.append(field_name)

    taxonomy = review.get("taxonomy")
    if not isinstance(taxonomy, dict):
        missing.append("taxonomy")
        return missing

    for taxonomy_field in UI_PROTOTYPE_TAXONOMY:
        if not _has_values(taxonomy.get(taxonomy_field)):
            missing.append(f"taxonomy:{taxonomy_field}")
    return missing


def render_ui_prototype_review(review: dict[str, Any]) -> str:
    """Render the review record as a local Markdown artifact."""
    taxonomy = review["taxonomy"]
    lines = [
        "# UI Prototype Review",
        "",
        "Status: Draft",
        "",
        f"Prototype: {review['prototype_path']}",
        "",
        "## Pages",
        *_bullets(review["pages"]),
        "",
        "## States",
        *_bullets(review["states"]),
        "",
        "## Journeys",
        *_bullets(review["journeys"]),
        "",
        "## Scenario Taxonomy",
    ]
    for taxonomy_field in UI_PROTOTYPE_TAXONOMY:
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
            "## Prototype Limitations",
            *_bullets(review["limitations"]),
            "",
            "## Browser E2E Candidates",
            *_bullets(review["browser_e2e_candidates"]),
            "",
            "## Negative Scope Guard Candidates",
            *_bullets(review["negative_scope_guard_candidates"]),
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
