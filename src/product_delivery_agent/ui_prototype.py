"""UI prototype review gate validation."""

from __future__ import annotations

from typing import Any

from product_delivery_agent.evidence_artifacts import (
    EvidenceArtifactError,
    stable_json_hash,
    validate_png,
)

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
PROTOTYPE_CONTRACT_VERSION = "v1"
ACCESSIBLE_NAME_MATCH_MODES = {"exact", "contains", "role_only"}
REGION_RELATIONS = {"contains", "precedes", "adjacent_to"}
INTERACTION_RELATIONS = {"opens", "navigates_to", "updates"}


class UIPrototypeError(RuntimeError):
    """Raised when a prototype contract cannot be frozen."""


def build_prototype_contract(
    project_root: str | Any,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate and hash the critical UI contract confirmed with a prototype."""
    if contract.get("contract_version") != PROTOTYPE_CONTRACT_VERSION:
        raise UIPrototypeError("prototype contract_version must be v1")
    surfaces = contract.get("surfaces")
    screenshot_paths = contract.get("prototype_screenshot_paths")
    if not isinstance(surfaces, list) or not surfaces:
        raise UIPrototypeError("prototype contract requires surfaces")
    if not isinstance(screenshot_paths, list) or not screenshot_paths:
        raise UIPrototypeError("prototype contract requires prototype_screenshot_paths")

    seen_surfaces: set[str] = set()
    seen_regions: set[str] = set()
    seen_interactions: set[str] = set()
    for index, surface in enumerate(surfaces, start=1):
        if not isinstance(surface, dict):
            raise UIPrototypeError(f"surface {index} must be an object")
        for field_name in ("surface_id", "route", "state_id"):
            if not _has_values(surface.get(field_name)):
                raise UIPrototypeError(f"surface {index} missing {field_name}")
        surface_id = str(surface["surface_id"])
        if surface_id in seen_surfaces:
            raise UIPrototypeError(f"duplicate surface_id: {surface_id}")
        seen_surfaces.add(surface_id)
        if not _has_values(surface.get("required_viewports")):
            raise UIPrototypeError(f"surface {surface_id} missing required_viewports")

        regions = surface.get("critical_regions")
        if not isinstance(regions, list) or not regions:
            raise UIPrototypeError(f"surface {surface_id} requires critical_regions")
        surface_region_ids: set[str] = set()
        for region in regions:
            if not isinstance(region, dict):
                raise UIPrototypeError(f"surface {surface_id} region must be object")
            region_id = str(region.get("region_id") or "")
            if not region_id:
                raise UIPrototypeError(f"surface {surface_id} region missing region_id")
            if region_id in seen_regions:
                raise UIPrototypeError(f"duplicate region_id: {region_id}")
            seen_regions.add(region_id)
            surface_region_ids.add(region_id)
            if not _has_values(region.get("semantic_role")):
                raise UIPrototypeError(f"region {region_id} missing semantic_role")
            name_match = region.get("accessible_name_match")
            if not isinstance(name_match, dict) or name_match.get("mode") not in ACCESSIBLE_NAME_MATCH_MODES:
                raise UIPrototypeError(f"region {region_id} has invalid accessible_name_match")
            if name_match.get("mode") != "role_only" and not _has_values(name_match.get("value")):
                raise UIPrototypeError(f"region {region_id} missing accessible name value")
            if region.get("visibility") not in {"visible", "conditionally_visible"}:
                raise UIPrototypeError(f"region {region_id} has invalid visibility")
        _validate_region_hierarchy(surface_id, regions, surface_region_ids)

        relationships = surface.get("critical_relationships")
        if not isinstance(relationships, list) or not relationships:
            raise UIPrototypeError(f"surface {surface_id} requires critical_relationships")
        for relationship in relationships:
            source = relationship.get("source_region_id")
            target = relationship.get("target_region_id")
            if source not in surface_region_ids or target not in surface_region_ids:
                raise UIPrototypeError(f"surface {surface_id} relationship references unknown region")
            if relationship.get("relation") not in REGION_RELATIONS:
                raise UIPrototypeError(f"surface {surface_id} has invalid region relation")

        interactions = surface.get("critical_interactions")
        if not isinstance(interactions, list) or not interactions:
            raise UIPrototypeError(f"surface {surface_id} requires critical_interactions")
        for interaction in interactions:
            interaction_id = str(interaction.get("interaction_id") or "")
            if not interaction_id or interaction_id in seen_interactions:
                raise UIPrototypeError(f"duplicate or missing interaction_id: {interaction_id}")
            seen_interactions.add(interaction_id)
            if interaction.get("entry_region_id") not in surface_region_ids:
                raise UIPrototypeError(f"interaction {interaction_id} entry region is unknown")
            if interaction.get("target_region_id") not in surface_region_ids:
                raise UIPrototypeError(f"interaction {interaction_id} target region is unknown")
            if interaction.get("expected_relation") not in INTERACTION_RELATIONS:
                raise UIPrototypeError(f"interaction {interaction_id} has invalid expected_relation")
            if not _has_values(interaction.get("action")):
                raise UIPrototypeError(f"interaction {interaction_id} missing action")

    try:
        screenshots = [validate_png(project_root, path) for path in screenshot_paths]
    except EvidenceArtifactError as cause:
        raise UIPrototypeError(str(cause)) from cause
    canonical = {
        "contract_version": PROTOTYPE_CONTRACT_VERSION,
        "surfaces": surfaces,
        "prototype_screenshot_paths": screenshot_paths,
    }
    return {
        **canonical,
        "status": "ready",
        "contract_sha256": stable_json_hash(canonical),
        "prototype_screenshots": screenshots,
        "prototype_screenshot_set_sha256": stable_json_hash(screenshots),
    }


def _validate_region_hierarchy(
    surface_id: str,
    regions: list[dict[str, Any]],
    region_ids: set[str],
) -> None:
    parents: dict[str, str | None] = {}
    sibling_orders: set[tuple[str | None, int]] = set()
    for region in regions:
        region_id = str(region["region_id"])
        parent = region.get("parent_region_id")
        if parent is not None and parent not in region_ids:
            raise UIPrototypeError(
                f"surface {surface_id} region {region_id} parent region is unknown"
            )
        parents[region_id] = parent
        order = region.get("display_order")
        if order is None:
            continue
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise UIPrototypeError(f"region {region_id} has invalid display_order")
        key = (parent, order)
        if key in sibling_orders:
            raise UIPrototypeError(
                f"surface {surface_id} has conflicting display_order"
            )
        sibling_orders.add(key)

    for region_id in parents:
        visited: set[str] = set()
        cursor: str | None = region_id
        while cursor is not None:
            if cursor in visited:
                raise UIPrototypeError(
                    f"surface {surface_id} region hierarchy cycle detected"
                )
            visited.add(cursor)
            cursor = parents.get(cursor)


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
            "- User Confirmation: bound to final product_baseline confirmation",
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
