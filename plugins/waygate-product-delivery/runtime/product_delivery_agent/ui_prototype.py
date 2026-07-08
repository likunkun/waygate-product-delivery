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
UI_CHANGE_TYPES = {
    "incremental_existing_surface",
    "new_surface_in_existing_product",
    "greenfield_ui",
    "non_ui",
}
INCREMENTAL_BASELINE_FIELDS = (
    "baseline_feature_slug",
    "baseline_surface_paths",
    "baseline_user_journey",
    "continuity_mapping",
    "prototype_delta_summary",
)
GENERIC_NEW_SURFACE_JUSTIFICATIONS = {
    "new page",
    "new surface",
    "new ui",
    "needed",
    "required",
    "新增页面",
    "新页面",
    "需要新页面",
}


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
        "ui_change_type",
    ):
        if not _has_values(review.get(field_name)):
            missing.append(field_name)
    if review.get("ui_change_type") and review.get("ui_change_type") not in UI_CHANGE_TYPES:
        missing.append("ui_change_type")

    taxonomy = review.get("taxonomy")
    if not isinstance(taxonomy, dict):
        missing.append("taxonomy")
        return missing

    for taxonomy_field in UI_PROTOTYPE_TAXONOMY:
        if not _has_values(taxonomy.get(taxonomy_field)):
            missing.append(f"taxonomy:{taxonomy_field}")
    _validate_continuity_fields(review, missing)
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
        f"UI Change Type: {review.get('ui_change_type', '')}",
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
            "## Baseline Continuity",
            f"- Baseline Feature: {review.get('baseline_feature_slug', '')}",
            f"- Baseline Journey: {review.get('baseline_user_journey', '')}",
            "",
            "### Baseline Surface Paths",
            *_bullets(review.get("baseline_surface_paths", [])),
            "",
            "### Continuity Mapping",
            *_bullets(review.get("continuity_mapping", [])),
            "",
            "### Prototype Delta Summary",
            *_bullets(review.get("prototype_delta_summary", [])),
            "",
            "### New Surface Justification",
            _render_new_surface_justification(review.get("new_surface_justification")),
            f"- User Confirmation: {bool(review.get('new_surface_user_confirmation'))}",
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


def _validate_continuity_fields(review: dict[str, Any], missing: list[str]) -> None:
    change_type = review.get("ui_change_type")
    if change_type == "incremental_existing_surface":
        for field_name in INCREMENTAL_BASELINE_FIELDS:
            if not _has_values(review.get(field_name)):
                missing.append(field_name)
        for field_name in ("continuity_mapping", "prototype_delta_summary"):
            if _contains_parallel_surface_replacement(review.get(field_name)):
                missing.append(f"{field_name}:parallel_surface_replacement")
    elif change_type in {"new_surface_in_existing_product", "greenfield_ui"}:
        if not _has_meaningful_new_surface_justification(
            review.get("new_surface_justification")
        ):
            missing.append("new_surface_justification")
        if review.get("new_surface_user_confirmation") is not True:
            missing.append("new_surface_user_confirmation")


def _has_meaningful_new_surface_justification(value: Any) -> bool:
    if isinstance(value, dict):
        required = (
            "reason",
            "why_existing_surface_insufficient",
            "navigation_impact",
        )
        return all(_has_values(value.get(field_name)) for field_name in required)
    if isinstance(value, list):
        return len(value) >= 2 and all(
            isinstance(item, str) and _meaningful_text(item) for item in value
        )
    if isinstance(value, str):
        return _meaningful_text(value)
    return False


def _meaningful_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.lower() in GENERIC_NEW_SURFACE_JUSTIFICATIONS:
        return False
    if len(text) < 24:
        return False
    return True


def _contains_parallel_surface_replacement(value: Any) -> bool:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    else:
        values = []
    for item in values:
        text = item.lower()
        if any(
            allowed_negation in text
            for allowed_negation in (
                "does not replace",
                "do not replace",
                "not replace",
                "keeps",
                "keep the",
                "不替代",
                "不取代",
                "沿用",
                "保留",
            )
        ):
            continue
        if any(
            term in text
            for term in (
                "standalone",
                "parallel",
                "replace",
                "replacement",
                "instead of the existing",
                "独立",
                "平行",
                "替代",
                "取代",
                "另起",
            )
        ):
            return True
    return False


def _render_new_surface_justification(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_bullets(value))
    if isinstance(value, str) and value.strip():
        return f"- {value}"
    return "- None"


def _has_values(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, str) and item.strip() for item in value)
    return False


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]
