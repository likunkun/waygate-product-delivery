"""Canonical prototype design integrity bundle validation."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from product_delivery_agent.evidence_artifacts import (
    EvidenceArtifactError,
    load_json_artifact,
    resolve_project_path,
    sha256_file,
    stable_json_hash,
    validate_png,
)


BUNDLE_VERSION = "v1"
UI_CHANGE_TYPES = {
    "incremental_existing_surface",
    "new_surface_in_existing_product",
    "greenfield_ui",
}
PRODUCT_CONTEXT_DIMENSIONS = (
    "global_shell",
    "navigation",
    "visual_language",
    "information_density",
    "component_system",
    "responsive_behavior",
)
CLEAN_RUNTIME_FLAGS = (
    "annotation_nodes_present",
    "review_assets_loaded",
    "review_mode_available",
)
SEMANTIC_SNAPSHOT_VERSION = "prototype-semantic-snapshot-v1"
BROWSER_PREFLIGHT_VERSION = "prototype-browser-preflight-v1"
DESIGN_EVIDENCE_VERSION = "prototype-design-evidence-v1"
DESIGN_SYSTEM_VERSION = "prototype-design-system-v1"
SEMANTIC_ROLES = {
    "alert",
    "banner",
    "complementary",
    "contentinfo",
    "dialog",
    "form",
    "main",
    "navigation",
    "region",
    "search",
    "status",
}
VISIBILITY_STATES = {"visible", "hidden"}
STYLE_PROBES_BY_DIMENSION = {
    "global_shell": {"layout_structure", "spacing_scale"},
    "navigation": {"entry_path", "active_state"},
    "visual_language": {"color_tokens", "typography_tokens"},
    "information_density": {"density_scale", "grouping"},
    "component_system": {"component_variant", "control_shape"},
    "responsive_behavior": {"breakpoint_behavior", "reflow_order"},
}
FORBIDDEN_CLEAN_HTML_MARKERS = (
    ("prototype-annotation-overlay", "prototype annotation overlay"),
    ("waygate-annotation-overlay", "Waygate annotation overlay"),
    ("prototype-review-overlay", "prototype review overlay"),
    ("waygate-review-overlay", "Waygate review overlay"),
    ("data-prototype-annotation", "prototype annotation data attribute"),
    ("data-waygate-review", "Waygate review data attribute"),
    ("data-annotation-", "annotation data attribute"),
    ("data-clean-region-id", "review anchor data attribute"),
    ("data-clean-surface-reference", "review anchor data attribute"),
)


class PrototypeDesignError(RuntimeError):
    """Raised when a prototype design integrity bundle is invalid."""


def build_prototype_design_bundle(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    prototype_contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate prototype design evidence and return canonical integrity hashes."""
    try:
        return _build_prototype_design_bundle(
            project_root,
            payload,
            prototype_contract=prototype_contract,
        )
    except PrototypeDesignError:
        raise
    except (EvidenceArtifactError, OSError, ValueError) as cause:
        raise PrototypeDesignError(str(cause)) from cause


def _build_prototype_design_bundle(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    prototype_contract: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PrototypeDesignError("prototype design payload must be an object")
    if payload.get("bundle_version") != BUNDLE_VERSION:
        raise PrototypeDesignError("prototype design bundle_version must be v1")

    ui_change_type = payload.get("ui_change_type")
    if ui_change_type not in UI_CHANGE_TYPES:
        raise PrototypeDesignError("prototype design ui_change_type is invalid")

    contract = _contract_requirements(prototype_contract)
    prototype_contract_identity = _prototype_contract_identity(prototype_contract)
    clean_surface, clean_artifacts = _normalize_clean_surface(
        project_root,
        payload.get("clean_surface"),
        contract,
    )
    product_context, context_artifacts = _normalize_product_context(
        project_root,
        payload.get("product_context_contract"),
        ui_change_type,
        contract,
    )
    callouts = _normalize_callouts(
        payload.get("intended_product_ui_callouts"),
        contract,
    )
    review_annotation_set, review_artifact = _normalize_review_annotation_set(
        project_root,
        payload.get("review_annotation_set"),
        clean_surface["prototype_path"],
        clean_artifacts["clean_prototype_resolved_path"],
        contract,
    )

    normalized_payload = {
        "bundle_version": BUNDLE_VERSION,
        "ui_change_type": ui_change_type,
        "clean_surface": clean_surface,
        "product_context_contract": product_context,
        "intended_product_ui_callouts": callouts,
        "review_annotation_set": review_annotation_set,
    }
    artifact_metadata = {
        "clean_prototype": clean_artifacts["clean_prototype"],
        "semantic_snapshot": clean_artifacts["semantic_snapshot"],
        "browser_preflight_probe": clean_artifacts[
            "browser_preflight_probe"
        ],
        "clean_screenshots": clean_artifacts["clean_screenshots"],
        "baseline_snapshots": context_artifacts["baseline_snapshots"],
        "design_system_artifact": context_artifacts["design_system_artifact"],
        "design_evidence_artifacts": context_artifacts[
            "design_evidence_artifacts"
        ],
        "review_annotation_artifact": review_artifact,
    }
    required_coverage_matrix = _build_coverage_matrix(
        contract,
        clean_surface,
        product_context,
        clean_artifacts["clean_screenshots"],
    )
    design_audit = _build_design_audit(
        normalized_payload,
        artifact_metadata,
        required_coverage_matrix,
    )

    product_payload = dict(normalized_payload)
    product_payload.pop("review_annotation_set")
    product_artifacts = dict(artifact_metadata)
    product_artifacts.pop("review_annotation_artifact")
    product_domain = {
        "normalized_payload": product_payload,
        "artifact_metadata": product_artifacts,
        "required_coverage_matrix": required_coverage_matrix,
        "prototype_contract_identity": prototype_contract_identity,
    }
    product_domain_sha256 = stable_json_hash(product_domain)

    review_domain = {
        "product_domain_sha256": product_domain_sha256,
        "design_audit": design_audit,
        "review_annotation_set": {
            "normalized_value": review_annotation_set,
            "artifact_metadata": review_artifact,
        }
        if review_annotation_set is not None
        else None,
    }
    review_domain_sha256 = stable_json_hash(review_domain)
    bundle_sha256 = stable_json_hash(
        {
            "product_domain_sha256": product_domain_sha256,
            "review_domain_sha256": review_domain_sha256,
        }
    )

    return {
        "bundle_version": normalized_payload["bundle_version"],
        "ui_change_type": normalized_payload["ui_change_type"],
        "clean_surface": deepcopy(normalized_payload["clean_surface"]),
        "product_context_contract": deepcopy(
            normalized_payload["product_context_contract"]
        ),
        "intended_product_ui_callouts": deepcopy(
            normalized_payload["intended_product_ui_callouts"]
        ),
        "review_annotation_set": deepcopy(
            normalized_payload["review_annotation_set"]
        ),
        "status": "ready",
        "normalized_payload": deepcopy(normalized_payload),
        "artifact_metadata": deepcopy(artifact_metadata),
        "required_coverage_matrix": deepcopy(required_coverage_matrix),
        "design_audit": deepcopy(design_audit),
        "prototype_contract_identity": deepcopy(prototype_contract_identity),
        "product_domain_sha256": product_domain_sha256,
        "review_domain_sha256": review_domain_sha256,
        "bundle_sha256": bundle_sha256,
    }


def _prototype_contract_identity(
    prototype_contract: dict[str, Any],
) -> dict[str, Any]:
    canonical_contract = {
        "contract_version": prototype_contract.get("contract_version"),
        "surfaces": prototype_contract.get("surfaces"),
        "prototype_screenshot_paths": prototype_contract.get(
            "prototype_screenshot_paths"
        ),
    }
    runtime_hash = stable_json_hash(canonical_contract)
    declared_hash = prototype_contract.get("contract_sha256")
    if not isinstance(declared_hash, str) or not declared_hash.strip():
        declared_hash = None
    return {
        "contract_sha256": declared_hash or runtime_hash,
        "runtime_computed_contract_sha256": runtime_hash,
        "contract_sha256_verified": (
            declared_hash == runtime_hash if declared_hash is not None else None
        ),
    }


def _contract_requirements(prototype_contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(prototype_contract, dict):
        raise PrototypeDesignError("prototype_contract must be an object")
    surfaces = prototype_contract.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise PrototypeDesignError("prototype_contract requires surfaces")

    runtime_order: list[tuple[str, str, str]] = []
    runtime_regions: dict[tuple[str, str, str], tuple[str, ...]] = {}
    context_order: list[tuple[str, str, str]] = []
    surface_regions: dict[tuple[str, str], tuple[str, ...]] = {}
    region_states: dict[str, set[str]] = {}
    surface_ids: list[str] = []
    state_ids: set[str] = set()
    all_region_ids: set[str] = set()
    region_contracts: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    relationship_contracts: dict[tuple[str, str], list[dict[str, str]]] = {}

    for index, surface in enumerate(surfaces, start=1):
        if not isinstance(surface, dict):
            raise PrototypeDesignError(f"prototype contract surface {index} must be an object")
        surface_id = _required_string(
            surface.get("surface_id"),
            f"prototype contract surface {index} missing surface_id",
        )
        state_id = _required_string(
            surface.get("state_id"),
            f"prototype contract surface {surface_id} missing state_id",
        )
        surface_key = (surface_id, state_id)
        if surface_key in surface_regions:
            raise PrototypeDesignError(
                f"duplicate prototype contract surface state: {surface_key}"
            )

        viewports = _string_list(
            surface.get("required_viewports"),
            f"prototype contract surface {surface_id} requires required_viewports",
        )
        regions = surface.get("critical_regions")
        if not isinstance(regions, list) or not regions:
            raise PrototypeDesignError(
                f"prototype contract surface {surface_id} requires critical_regions"
            )
        region_ids: list[str] = []
        surface_region_contracts: dict[str, dict[str, Any]] = {}
        for region in regions:
            if not isinstance(region, dict):
                raise PrototypeDesignError(
                    f"prototype contract surface {surface_id} region must be an object"
                )
            region_id = _required_string(
                region.get("region_id"),
                f"prototype contract surface {surface_id} region missing region_id",
            )
            if region_id in region_ids:
                raise PrototypeDesignError(
                    f"duplicate prototype contract region_id: {region_id}"
                )
            region_ids.append(region_id)
            surface_region_contracts[region_id] = {
                "semantic_role": region.get("semantic_role"),
                "accessible_name_match": deepcopy(
                    region.get("accessible_name_match")
                ),
                "visibility": region.get("visibility"),
                "parent_region_id": region.get("parent_region_id"),
                "display_order": region.get("display_order"),
            }
            region_states.setdefault(region_id, set()).add(state_id)
            all_region_ids.add(region_id)

        surface_regions[surface_key] = tuple(region_ids)
        region_contracts[surface_key] = surface_region_contracts
        relationships = surface.get("critical_relationships")
        relationship_contracts[surface_key] = [
            {
                "source_region_id": str(item.get("source_region_id") or ""),
                "relation": str(item.get("relation") or ""),
                "target_region_id": str(item.get("target_region_id") or ""),
            }
            for item in relationships or []
            if isinstance(item, dict)
        ]
        surface_ids.append(surface_id)
        state_ids.add(state_id)
        for viewport in viewports:
            key = (surface_id, state_id, viewport)
            if key in runtime_regions:
                raise PrototypeDesignError(
                    f"duplicate prototype contract viewport coverage: {key}"
                )
            runtime_order.append(key)
            runtime_regions[key] = tuple(region_ids)
        for dimension in PRODUCT_CONTEXT_DIMENSIONS:
            context_order.append((surface_id, state_id, dimension))

    return {
        "runtime_order": runtime_order,
        "runtime_regions": runtime_regions,
        "context_order": context_order,
        "surface_regions": surface_regions,
        "region_contracts": region_contracts,
        "relationship_contracts": relationship_contracts,
        "region_states": region_states,
        "surface_ids": tuple(surface_ids),
        "state_ids": tuple(sorted(state_ids)),
        "region_ids": tuple(sorted(all_region_ids)),
    }


def _normalize_clean_surface(
    project_root: str | Path,
    value: Any,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise PrototypeDesignError("prototype design requires clean_surface")

    prototype_path = _normalized_path(
        value.get("prototype_path"),
        "clean_surface prototype_path is required",
    )
    try:
        prototype_resolved = resolve_project_path(project_root, prototype_path)
    except EvidenceArtifactError as cause:
        raise PrototypeDesignError(str(cause)) from cause
    _validate_clean_prototype_html(prototype_resolved)
    prototype_metadata = {
        "path": prototype_path,
        "sha256": sha256_file(prototype_resolved),
    }

    semantic_snapshot_path = _normalized_path(
        value.get("semantic_snapshot_path"),
        "clean_surface semantic_snapshot_path is required",
    )
    try:
        semantic_value, semantic_metadata = load_json_artifact(
            project_root,
            semantic_snapshot_path,
        )
    except EvidenceArtifactError as cause:
        raise PrototypeDesignError(str(cause)) from cause
    semantic_by_key = _normalize_semantic_snapshot(semantic_value, contract)

    probe_path = _normalized_path(
        value.get("browser_preflight_probe_path"),
        "clean_surface browser preflight probe path is required",
    )
    try:
        probe_value, probe_metadata = load_json_artifact(
            project_root,
            probe_path,
        )
    except EvidenceArtifactError as cause:
        raise PrototypeDesignError(str(cause)) from cause

    checks = value.get("runtime_checks")
    if not isinstance(checks, list) or not checks:
        raise PrototypeDesignError("clean_surface requires runtime_checks")
    payload_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    screenshot_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            raise PrototypeDesignError(f"runtime check {index} must be an object")
        surface_id = _required_string(
            check.get("surface_id"),
            f"runtime check {index} missing surface_id",
        )
        state_id = _required_string(
            check.get("state_id"),
            f"runtime check {index} missing state_id",
        )
        viewport = _required_string(
            check.get("viewport"),
            f"runtime check {index} missing viewport",
        )
        key = (surface_id, state_id, viewport)
        required_regions = contract["runtime_regions"].get(key)
        if required_regions is None:
            raise PrototypeDesignError(
                f"runtime check {index} is not in prototype contract: {key}"
            )
        if key in payload_by_key:
            raise PrototypeDesignError(f"duplicate runtime check: {key}")

        screenshot_path = _normalized_path(
            check.get("clean_screenshot_path"),
            f"runtime check {index} clean_screenshot_path is required",
        )
        try:
            screenshot = validate_png(project_root, screenshot_path)
        except EvidenceArtifactError as cause:
            raise PrototypeDesignError(str(cause)) from cause
        payload_by_key[key] = {
            "surface_id": surface_id,
            "state_id": state_id,
            "viewport": viewport,
            "clean_screenshot_path": screenshot_path,
        }
        screenshot_by_key[key] = {
            "surface_id": surface_id,
            "state_id": state_id,
            "viewport": viewport,
            "artifact": screenshot,
        }

    missing_keys = [
        key for key in contract["runtime_order"] if key not in payload_by_key
    ]
    if missing_keys:
        raise PrototypeDesignError(
            "clean_surface missing runtime coverage: "
            + ", ".join(map(str, missing_keys))
        )

    normalized_by_key = _normalize_browser_preflight_probe(
        probe_value,
        prototype_path=prototype_path,
        semantic_metadata=semantic_metadata,
        semantic_by_key=semantic_by_key,
        payload_by_key=payload_by_key,
        screenshot_by_key=screenshot_by_key,
        contract=contract,
    )

    return (
        {
            "prototype_path": prototype_path,
            "semantic_snapshot_path": semantic_snapshot_path,
            "browser_preflight_probe_path": probe_path,
            "runtime_checks": [
                normalized_by_key[key] for key in contract["runtime_order"]
            ],
        },
        {
            "clean_prototype": prototype_metadata,
            "clean_prototype_resolved_path": prototype_resolved,
            "semantic_snapshot": {
                **semantic_metadata,
                "schema_version": SEMANTIC_SNAPSHOT_VERSION,
                "state_count": len(semantic_by_key),
            },
            "browser_preflight_probe": {
                **probe_metadata,
                "schema_version": BROWSER_PREFLIGHT_VERSION,
                "observation_count": len(normalized_by_key),
            },
            "clean_screenshots": [
                screenshot_by_key[key] for key in contract["runtime_order"]
            ],
        },
    )


def _validate_clean_prototype_html(prototype_path: Path) -> None:
    try:
        html = prototype_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        raise PrototypeDesignError("clean prototype HTML must be UTF-8") from cause
    lowered = html.lower()
    for marker, label in FORBIDDEN_CLEAN_HTML_MARKERS:
        if marker in lowered:
            raise PrototypeDesignError(
                f"clean prototype contains forbidden {label}"
            )
    if ".product-delivery/artifacts/review-only/" in lowered:
        raise PrototypeDesignError(
            "clean prototype contains forbidden review-only artifact import"
        )
    if re.search(
        r"[?&](?:waygate_review|prototype_review|prototype_annotation|annotation_review|mode)="
        r"(?:waygate_review|prototype_review|prototype_annotation|annotation_review)"
        r"(?:[&#\"']|$)",
        lowered,
    ):
        raise PrototypeDesignError(
            "clean prototype contains forbidden review query mode"
        )


def _normalize_semantic_snapshot(
    value: dict[str, Any],
    contract: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    _require_exact_keys(
        value,
        {"schema_version", "states"},
        "semantic snapshot",
    )
    if value.get("schema_version") != SEMANTIC_SNAPSHOT_VERSION:
        raise PrototypeDesignError(
            f"semantic snapshot schema_version must be {SEMANTIC_SNAPSHOT_VERSION}"
        )
    states = value.get("states")
    if not isinstance(states, list) or not states:
        raise PrototypeDesignError("semantic snapshot requires states")

    normalized_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, state in enumerate(states, start=1):
        if not isinstance(state, dict):
            raise PrototypeDesignError(
                f"semantic snapshot state {index} must be an object"
            )
        _require_exact_keys(
            state,
            {"surface_id", "state_id", "viewport", "regions"},
            f"semantic snapshot state {index}",
        )
        surface_id = _required_string(
            state.get("surface_id"),
            f"semantic snapshot state {index} missing surface_id",
        )
        state_id = _required_string(
            state.get("state_id"),
            f"semantic snapshot state {index} missing state_id",
        )
        viewport = _required_string(
            state.get("viewport"),
            f"semantic snapshot state {index} missing viewport",
        )
        key = (surface_id, state_id, viewport)
        required_regions = contract["runtime_regions"].get(key)
        if required_regions is None:
            raise PrototypeDesignError(
                f"semantic snapshot state {index} is not in prototype contract: {key}"
            )
        if key in normalized_by_key:
            raise PrototypeDesignError(f"duplicate semantic snapshot state: {key}")

        regions = state.get("regions")
        if not isinstance(regions, list) or not regions:
            raise PrototypeDesignError(
                f"semantic snapshot state {index} requires non-empty regions"
            )
        normalized_regions: list[dict[str, Any]] = []
        seen_regions: set[str] = set()
        seen_orders: set[int] = set()
        for region_index, region in enumerate(regions, start=1):
            if not isinstance(region, dict):
                raise PrototypeDesignError(
                    f"semantic snapshot state {index} region {region_index} must be an object"
                )
            _require_exact_keys(
                region,
                {
                    "region_id",
                    "semantic_role",
                    "accessible_name",
                    "visibility",
                    "display_order",
                    "bounds",
                    "controls",
                    "interaction_state",
                },
                f"semantic snapshot state {index} region {region_index}",
            )
            region_id = _required_string(
                region.get("region_id"),
                f"semantic snapshot state {index} region {region_index} missing region_id",
            )
            if region_id in seen_regions:
                raise PrototypeDesignError(
                    f"duplicate semantic snapshot region_id: {region_id}"
                )
            seen_regions.add(region_id)
            semantic_role = _required_string(
                region.get("semantic_role"),
                f"semantic snapshot region {region_id} requires semantic_role",
            )
            if semantic_role not in SEMANTIC_ROLES:
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} semantic_role is invalid"
                )
            accessible_name = _required_string(
                region.get("accessible_name"),
                f"semantic snapshot region {region_id} requires accessible_name",
            )
            visibility = _required_string(
                region.get("visibility"),
                f"semantic snapshot region {region_id} requires visibility",
            )
            if visibility not in VISIBILITY_STATES:
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} visibility is invalid"
                )
            display_order = region.get("display_order")
            if (
                isinstance(display_order, bool)
                or not isinstance(display_order, int)
                or display_order < 1
            ):
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} display_order must be a positive integer"
                )
            if display_order in seen_orders:
                raise PrototypeDesignError(
                    f"semantic snapshot state {index} display_order values must be unique"
                )
            seen_orders.add(display_order)
            bounds = _normalize_bounds(
                region.get("bounds"),
                f"semantic snapshot region {region_id} bounds",
            )
            controls_value = region.get("controls")
            if not isinstance(controls_value, list):
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} controls must be a list"
                )
            controls = [
                _required_string(
                    control,
                    f"semantic snapshot region {region_id} controls require names",
                )
                for control in controls_value
            ]
            if len(controls) != len(set(controls)):
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} controls must be unique"
                )
            interaction_state = _required_string(
                region.get("interaction_state"),
                f"semantic snapshot region {region_id} requires interaction_state",
            )
            normalized_regions.append(
                {
                    "region_id": region_id,
                    "semantic_role": semantic_role,
                    "accessible_name": accessible_name,
                    "visibility": visibility,
                    "display_order": display_order,
                    "bounds": bounds,
                    "controls": controls,
                    "interaction_state": interaction_state,
                }
            )

        missing_regions = sorted(set(required_regions) - seen_regions)
        if missing_regions:
            raise PrototypeDesignError(
                f"semantic snapshot state {index} missing critical regions: {missing_regions}"
            )
        _validate_snapshot_region_contracts(
            normalized_regions,
            contract["region_contracts"][(surface_id, state_id)],
            contract["relationship_contracts"][(surface_id, state_id)],
        )
        normalized_by_key[key] = {
            "surface_id": surface_id,
            "state_id": state_id,
            "viewport": viewport,
            "regions": sorted(
                normalized_regions,
                key=lambda item: item["display_order"],
            ),
        }

    missing_keys = [
        key for key in contract["runtime_order"] if key not in normalized_by_key
    ]
    if missing_keys:
        raise PrototypeDesignError(
            "semantic snapshot missing state/viewport coverage: "
            + ", ".join(map(str, missing_keys))
        )
    return normalized_by_key


def _validate_snapshot_region_contracts(
    regions: list[dict[str, Any]],
    region_contracts: dict[str, dict[str, Any]],
    relationships: list[dict[str, str]],
) -> None:
    regions_by_id = {region["region_id"]: region for region in regions}
    for region_id, frozen in region_contracts.items():
        observed = regions_by_id[region_id]
        semantic_role = frozen.get("semantic_role")
        if semantic_role and observed["semantic_role"] != semantic_role:
            raise PrototypeDesignError(
                f"semantic snapshot region {region_id} semantic_role does not match prototype contract"
            )

        name_match = frozen.get("accessible_name_match")
        if isinstance(name_match, dict):
            mode = name_match.get("mode")
            expected = str(name_match.get("value") or "")
            actual = observed["accessible_name"]
            if mode == "exact" and actual.casefold() != expected.casefold():
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} accessible name does not match prototype contract"
                )
            if mode == "contains" and expected.casefold() not in actual.casefold():
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} accessible name does not contain prototype contract value"
                )

        frozen_visibility = frozen.get("visibility")
        if (
            frozen_visibility in {None, "visible"}
            and observed["visibility"] != "visible"
        ):
            raise PrototypeDesignError(
                f"semantic snapshot region {region_id} visibility does not match prototype contract"
            )

        frozen_order = frozen.get("display_order")
        if (
            isinstance(frozen_order, int)
            and not isinstance(frozen_order, bool)
            and frozen_order > 0
            and observed["display_order"] != frozen_order
        ):
            raise PrototypeDesignError(
                f"semantic snapshot region {region_id} display order does not match prototype contract"
            )

        parent_region_id = frozen.get("parent_region_id")
        if parent_region_id:
            parent = regions_by_id.get(str(parent_region_id))
            if parent is None or not _bounds_contain(
                parent["bounds"], observed["bounds"]
            ):
                raise PrototypeDesignError(
                    f"semantic snapshot region {region_id} hierarchy does not match prototype contract"
                )

    for relationship in relationships:
        source = regions_by_id.get(relationship["source_region_id"])
        target = regions_by_id.get(relationship["target_region_id"])
        if source is None or target is None:
            continue
        relation = relationship["relation"]
        if relation == "precedes" and not (
            source["display_order"] < target["display_order"]
        ):
            raise PrototypeDesignError(
                "semantic snapshot relationship precedes does not match prototype contract"
            )
        if relation == "adjacent_to" and abs(
            source["display_order"] - target["display_order"]
        ) != 1:
            raise PrototypeDesignError(
                "semantic snapshot relationship adjacent_to does not match prototype contract"
            )
        if relation == "contains" and not _bounds_contain(
            source["bounds"], target["bounds"]
        ):
            raise PrototypeDesignError(
                "semantic snapshot relationship contains does not match prototype contract"
            )


def _bounds_contain(
    outer: dict[str, int | float],
    inner: dict[str, int | float],
) -> bool:
    return bool(
        inner["x"] >= outer["x"]
        and inner["y"] >= outer["y"]
        and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
        and inner["y"] + inner["height"] <= outer["y"] + outer["height"]
    )


def _normalize_bounds(value: Any, label: str) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise PrototypeDesignError(f"{label} must be an object")
    _require_exact_keys(value, {"x", "y", "width", "height"}, label)
    normalized: dict[str, int | float] = {}
    for field_name in ("x", "y", "width", "height"):
        field_value = value.get(field_name)
        if (
            isinstance(field_value, bool)
            or not isinstance(field_value, (int, float))
            or not math.isfinite(field_value)
        ):
            raise PrototypeDesignError(f"{label} {field_name} must be finite")
        if field_name in {"width", "height"} and field_value <= 0:
            raise PrototypeDesignError(f"{label} {field_name} must be positive")
        normalized[field_name] = field_value
    return normalized


def _normalize_browser_preflight_probe(
    value: dict[str, Any],
    *,
    prototype_path: str,
    semantic_metadata: dict[str, Any],
    semantic_by_key: dict[tuple[str, str, str], dict[str, Any]],
    payload_by_key: dict[tuple[str, str, str], dict[str, Any]],
    screenshot_by_key: dict[tuple[str, str, str], dict[str, Any]],
    contract: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    _require_exact_keys(
        value,
        {
            "schema_version",
            "prototype_path",
            "semantic_snapshot_sha256",
            "observations",
        },
        "browser preflight",
    )
    if value.get("schema_version") != BROWSER_PREFLIGHT_VERSION:
        raise PrototypeDesignError(
            f"browser preflight schema_version must be {BROWSER_PREFLIGHT_VERSION}"
        )
    if value.get("prototype_path") != prototype_path:
        raise PrototypeDesignError(
            "browser preflight prototype_path must match clean prototype"
        )
    if value.get("semantic_snapshot_sha256") != semantic_metadata.get("sha256"):
        raise PrototypeDesignError(
            "browser preflight semantic_snapshot_sha256 must match semantic snapshot artifact"
        )
    observations = value.get("observations")
    if not isinstance(observations, list) or not observations:
        raise PrototypeDesignError("browser preflight requires observations")

    normalized_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            raise PrototypeDesignError(
                f"browser preflight observation {index} must be an object"
            )
        _require_exact_keys(
            observation,
            {
                "surface_id",
                "state_id",
                "viewport",
                "semantic_state_sha256",
                "clean_screenshot_path",
                "clean_screenshot_sha256",
                "observed_region_ids",
                "document_ready",
                "console_errors",
                "network_errors",
                "annotation_nodes_present",
                "review_assets_loaded",
                "review_mode_available",
            },
            f"browser preflight observation {index}",
        )
        key = (
            _required_string(
                observation.get("surface_id"),
                f"browser preflight observation {index} missing surface_id",
            ),
            _required_string(
                observation.get("state_id"),
                f"browser preflight observation {index} missing state_id",
            ),
            _required_string(
                observation.get("viewport"),
                f"browser preflight observation {index} missing viewport",
            ),
        )
        if key not in contract["runtime_regions"]:
            raise PrototypeDesignError(
                f"browser preflight observation {index} is not in prototype contract: {key}"
            )
        if key in normalized_by_key:
            raise PrototypeDesignError(
                f"duplicate browser preflight observation: {key}"
            )
        semantic_state = semantic_by_key[key]
        if observation.get("semantic_state_sha256") != stable_json_hash(
            semantic_state
        ):
            raise PrototypeDesignError(
                f"browser preflight observation {index} does not match semantic snapshot identity"
            )
        observed_region_ids = _string_list(
            observation.get("observed_region_ids"),
            f"browser preflight observation {index} requires observed_region_ids",
        )
        semantic_region_ids = [
            region["region_id"] for region in semantic_state["regions"]
        ]
        if set(observed_region_ids) != set(semantic_region_ids):
            raise PrototypeDesignError(
                f"browser preflight observation {index} region identity does not match semantic snapshot"
            )
        if observation.get("document_ready") is not True:
            raise PrototypeDesignError(
                f"browser preflight observation {index} document_ready must be true"
            )
        for error_field in ("console_errors", "network_errors"):
            if observation.get(error_field) != []:
                raise PrototypeDesignError(
                    f"browser preflight observation {index} {error_field} must be empty"
                )
        for field_name in CLEAN_RUNTIME_FLAGS:
            if observation.get(field_name) is not False:
                raise PrototypeDesignError(
                    f"browser preflight observation {index} {field_name} must be false"
                )

        payload_check = payload_by_key[key]
        screenshot = screenshot_by_key[key]["artifact"]
        if observation.get("clean_screenshot_path") != payload_check.get(
            "clean_screenshot_path"
        ):
            raise PrototypeDesignError(
                f"browser preflight observation {index} clean_screenshot_path does not match payload"
            )
        if observation.get("clean_screenshot_sha256") != screenshot.get("sha256"):
            raise PrototypeDesignError(
                f"browser preflight observation {index} clean_screenshot_sha256 does not match artifact"
            )
        normalized_by_key[key] = {
            "surface_id": key[0],
            "state_id": key[1],
            "viewport": key[2],
            "status": "passed",
            "clean_screenshot_path": payload_check["clean_screenshot_path"],
            "observed_region_ids": semantic_region_ids,
            "annotation_nodes_present": False,
            "review_assets_loaded": False,
            "review_mode_available": False,
        }

    missing_keys = [
        key for key in contract["runtime_order"] if key not in normalized_by_key
    ]
    if missing_keys:
        raise PrototypeDesignError(
            "browser preflight missing state/viewport coverage: "
            + ", ".join(map(str, missing_keys))
        )
    return normalized_by_key


def _normalize_product_context(
    project_root: str | Path,
    value: Any,
    ui_change_type: str,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise PrototypeDesignError("prototype design requires product_context_contract")
    rows = value.get("coverage_rows")
    if not isinstance(rows, list) or not rows:
        raise PrototypeDesignError("product_context_contract requires coverage_rows")

    required_keys = set(contract["context_order"])
    normalized_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    evidence_registry: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise PrototypeDesignError(f"product context row {index} must be an object")
        surface_id = _required_string(
            row.get("surface_id"),
            f"product context row {index} missing surface_id",
        )
        state_id = _required_string(
            row.get("state_id"),
            f"product context row {index} missing state_id",
        )
        dimension = _required_string(
            row.get("dimension"),
            f"product context row {index} missing dimension",
        )
        key = (surface_id, state_id, dimension)
        if key not in required_keys:
            raise PrototypeDesignError(
                f"product context row {index} is not in prototype contract: {key}"
            )
        if key in normalized_by_key:
            raise PrototypeDesignError(f"duplicate product context row: {key}")

        status = row.get("status")
        surface_region_ids = contract["surface_regions"][(surface_id, state_id)]
        surface_region_set = set(surface_region_ids)
        if status == "passed":
            covered_region_ids = _string_list(
                row.get("covered_region_ids"),
                f"product context row {index} requires covered_region_ids",
            )
            unknown_regions = sorted(set(covered_region_ids) - surface_region_set)
            if unknown_regions:
                raise PrototypeDesignError(
                    f"product context row {index} references unknown contract region: "
                    + ", ".join(unknown_regions)
                )
            evidence_refs = _normalize_design_evidence_refs(
                project_root,
                row.get("evidence_refs"),
                ui_change_type=ui_change_type,
                surface_id=surface_id,
                state_id=state_id,
                dimension=dimension,
                required_region_ids=covered_region_ids,
                contract=contract,
                evidence_registry=evidence_registry,
                label=f"product context row {index}",
            )
            normalized_by_key[key] = {
                "surface_id": surface_id,
                "state_id": state_id,
                "dimension": dimension,
                "status": "passed",
                "evidence_refs": evidence_refs,
                "covered_region_ids": [
                    region_id
                    for region_id in surface_region_ids
                    if region_id in set(covered_region_ids)
                ],
            }
        elif status == "exempted":
            exception = row.get("exception")
            if not isinstance(exception, dict):
                raise PrototypeDesignError(
                    f"product context row {index} exempted status requires exception"
                )
            normalized_exception = {
                "requirement_ids": sorted(
                    _string_list(
                        exception.get("requirement_ids"),
                        f"product context row {index} exception requires requirement_ids",
                    )
                ),
                "scenario_ids": sorted(
                    _string_list(
                        exception.get("scenario_ids"),
                        f"product context row {index} exception requires scenario_ids",
                    )
                ),
                "rationale": _required_string(
                    exception.get("rationale"),
                    f"product context row {index} exception requires rationale",
                ),
                "replacement_evidence_refs": _normalize_design_evidence_refs(
                    project_root,
                    exception.get("replacement_evidence_refs"),
                    ui_change_type=ui_change_type,
                    surface_id=surface_id,
                    state_id=state_id,
                    dimension=dimension,
                    required_region_ids=list(surface_region_ids),
                    contract=contract,
                    evidence_registry=evidence_registry,
                    label=f"product context row {index} exception",
                ),
                "review_disposition": exception.get("review_disposition"),
            }
            if normalized_exception["review_disposition"] != "accepted":
                raise PrototypeDesignError(
                    f"product context row {index} exception review_disposition must be accepted"
                )
            normalized_by_key[key] = {
                "surface_id": surface_id,
                "state_id": state_id,
                "dimension": dimension,
                "status": "exempted",
                "exception": normalized_exception,
            }
        else:
            raise PrototypeDesignError(
                f"product context row {index} status must be passed or exempted"
            )

    missing_keys = [
        key for key in contract["context_order"] if key not in normalized_by_key
    ]
    if missing_keys:
        raise PrototypeDesignError(
            "product_context_contract missing product context coverage: "
            + ", ".join(map(str, missing_keys))
        )

    baseline_snapshots: list[dict[str, Any]] = []
    design_system_artifact: dict[str, Any] | None = None
    normalized = {
        "coverage_rows": [
            normalized_by_key[key] for key in contract["context_order"]
        ]
    }
    if ui_change_type == "greenfield_ui":
        if value.get("baseline_identity") not in (None, {}):
            raise PrototypeDesignError(
                "greenfield_ui requires design_system_artifact_path instead of baseline_identity"
            )
        design_system_path, design_system_artifact = _load_design_system_artifact(
            project_root,
            value.get("design_system_artifact_path"),
            "greenfield_ui requires design_system_artifact_path",
        )
        normalized["design_system_artifact_path"] = design_system_path
    else:
        if (
            ui_change_type == "incremental_existing_surface"
            and value.get("design_system_artifact_path") not in (None, "")
        ):
            raise PrototypeDesignError(
                f"{ui_change_type} requires baseline_identity instead of design_system_artifact_path"
            )
        normalized_baseline, baseline_snapshots = _normalize_baseline_identity(
            project_root,
            value.get("baseline_identity"),
            ui_change_type,
        )
        normalized["baseline_identity"] = normalized_baseline
        if ui_change_type == "new_surface_in_existing_product":
            design_system_path, design_system_artifact = (
                _load_design_system_artifact(
                    project_root,
                    value.get("design_system_artifact_path"),
                    "new_surface_in_existing_product requires design_system_artifact_path",
                )
            )
            normalized["design_system_artifact_path"] = design_system_path
            justification = value.get("new_surface_justification")
            if not isinstance(justification, dict):
                raise PrototypeDesignError(
                    "new_surface_in_existing_product requires new_surface_justification"
                )
            normalized["new_surface_justification"] = {
                "reason": _required_string(
                    justification.get("reason"),
                    "new_surface_justification requires reason",
                ),
                "why_existing_surface_insufficient": _required_string(
                    justification.get("why_existing_surface_insufficient"),
                    "new_surface_justification requires why_existing_surface_insufficient",
                ),
                "navigation_impact": _required_string(
                    justification.get("navigation_impact"),
                    "new_surface_justification requires navigation_impact",
                ),
            }

    return normalized, {
        "baseline_snapshots": baseline_snapshots,
        "design_system_artifact": design_system_artifact,
        "design_evidence_artifacts": [
            evidence_registry[path] for path in sorted(evidence_registry)
        ],
    }


def _normalize_baseline_identity(
    project_root: str | Path,
    value: Any,
    ui_change_type: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(value, dict):
        raise PrototypeDesignError(f"{ui_change_type} requires baseline_identity")
    snapshot_paths = sorted(
        _string_list(
            value.get("baseline_snapshot_paths"),
            "baseline_identity requires baseline_snapshot_paths",
        )
    )
    snapshots = []
    for snapshot_path in snapshot_paths:
        try:
            snapshots.append(validate_png(project_root, snapshot_path))
        except EvidenceArtifactError as cause:
            raise PrototypeDesignError(str(cause)) from cause
    return {
        "canonical_baseline_id": _required_string(
            value.get("canonical_baseline_id"),
            "baseline_identity requires canonical_baseline_id",
        ),
        "baseline_feature_slug": _required_string(
            value.get("baseline_feature_slug"),
            "baseline_identity requires baseline_feature_slug",
        ),
        "baseline_surface_paths": sorted(
            _string_list(
                value.get("baseline_surface_paths"),
                "baseline_identity requires baseline_surface_paths",
            )
        ),
        "baseline_snapshot_paths": snapshot_paths,
    }, snapshots


def _load_design_system_artifact(
    project_root: str | Path,
    value: Any,
    message: str,
) -> tuple[str, dict[str, Any]]:
    path = _normalized_path(value, message)
    try:
        artifact, metadata = load_json_artifact(
            project_root,
            path,
            artifact_only=False,
        )
    except EvidenceArtifactError as cause:
        raise PrototypeDesignError(str(cause)) from cause
    _require_exact_keys(
        artifact,
        {"schema_version", "name", "token_sets"},
        "design system",
    )
    if artifact.get("schema_version") != DESIGN_SYSTEM_VERSION:
        raise PrototypeDesignError(
            f"design system schema_version must be {DESIGN_SYSTEM_VERSION}"
        )
    _required_string(artifact.get("name"), "design system requires name")
    _string_list(
        artifact.get("token_sets"),
        "design system requires token_sets",
    )
    return path, {
        **metadata,
        "schema_version": DESIGN_SYSTEM_VERSION,
    }


def _normalize_design_evidence_refs(
    project_root: str | Path,
    value: Any,
    *,
    ui_change_type: str,
    surface_id: str,
    state_id: str,
    dimension: str,
    required_region_ids: list[str],
    contract: dict[str, Any],
    evidence_registry: dict[str, dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise PrototypeDesignError(
            f"{label} requires structured evidence_refs"
        )
    normalized = []
    seen_paths: set[str] = set()
    for index, ref in enumerate(value, start=1):
        if not isinstance(ref, dict):
            raise PrototypeDesignError(
                f"{label} evidence ref {index} must be structured evidence"
            )
        _require_exact_keys(
            ref,
            {"artifact_path", "artifact_sha256"},
            f"{label} evidence ref {index}",
        )
        artifact_path = _normalized_path(
            ref.get("artifact_path"),
            f"{label} evidence ref {index} requires artifact_path",
        )
        if artifact_path in seen_paths:
            raise PrototypeDesignError(
                f"{label} evidence_refs must use unique artifact paths"
            )
        seen_paths.add(artifact_path)
        declared_hash = _required_sha256(
            ref.get("artifact_sha256"),
            f"{label} evidence ref {index} artifact_sha256",
        )
        try:
            artifact, metadata = load_json_artifact(
                project_root,
                artifact_path,
            )
        except EvidenceArtifactError as cause:
            raise PrototypeDesignError(str(cause)) from cause
        if metadata["sha256"] != declared_hash:
            raise PrototypeDesignError(
                f"{label} evidence ref {index} artifact_sha256 does not match artifact"
            )
        normalized_artifact = _validate_design_evidence_artifact(
            artifact,
            ui_change_type=ui_change_type,
            surface_id=surface_id,
            state_id=state_id,
            dimension=dimension,
            required_region_ids=required_region_ids,
            contract=contract,
            label=f"{label} evidence ref {index}",
        )
        evidence_registry[artifact_path] = {
            **metadata,
            "schema_version": DESIGN_EVIDENCE_VERSION,
            "evidence_id": normalized_artifact["evidence_id"],
            "ui_change_type": ui_change_type,
            "surface_id": surface_id,
            "state_id": state_id,
            "dimension": dimension,
        }
        normalized.append(
            {
                "artifact_path": artifact_path,
                "artifact_sha256": declared_hash,
            }
        )
    return sorted(normalized, key=lambda item: item["artifact_path"])


def _validate_design_evidence_artifact(
    value: dict[str, Any],
    *,
    ui_change_type: str,
    surface_id: str,
    state_id: str,
    dimension: str,
    required_region_ids: list[str],
    contract: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        {
            "schema_version",
            "evidence_id",
            "ui_change_type",
            "surface_id",
            "state_id",
            "dimension",
            "region_ids",
            "claims",
            "style_probes",
            "context_mapping",
        },
        label,
    )
    if value.get("schema_version") != DESIGN_EVIDENCE_VERSION:
        raise PrototypeDesignError(
            f"{label} schema_version must be {DESIGN_EVIDENCE_VERSION}"
        )
    evidence_id = _required_string(
        value.get("evidence_id"),
        f"{label} requires evidence_id",
    )
    expected_fields = {
        "ui_change_type": ui_change_type,
        "surface_id": surface_id,
        "state_id": state_id,
        "dimension": dimension,
    }
    for field_name, expected in expected_fields.items():
        if value.get(field_name) != expected:
            raise PrototypeDesignError(
                f"{label} {field_name} must match product context row"
            )
    region_ids = _string_list(
        value.get("region_ids"),
        f"{label} requires region_ids",
    )
    surface_region_ids = set(contract["surface_regions"][(surface_id, state_id)])
    if not set(region_ids).issubset(surface_region_ids):
        raise PrototypeDesignError(f"{label} region_ids must match clean surface")
    if not set(required_region_ids).issubset(set(region_ids)):
        raise PrototypeDesignError(
            f"{label} does not cover required region_ids"
        )
    _string_list(value.get("claims"), f"{label} requires claims")
    probes = value.get("style_probes")
    if not isinstance(probes, list) or not probes:
        raise PrototypeDesignError(f"{label} requires style probes")
    allowed_probes = STYLE_PROBES_BY_DIMENSION[dimension]
    seen_probes: set[str] = set()
    for probe_index, probe in enumerate(probes, start=1):
        if not isinstance(probe, dict):
            raise PrototypeDesignError(
                f"{label} style probe {probe_index} must be an object"
            )
        _require_exact_keys(
            probe,
            {"probe", "expected", "observed"},
            f"{label} style probe {probe_index}",
        )
        probe_name = _required_string(
            probe.get("probe"),
            f"{label} style probe {probe_index} requires probe",
        )
        if probe_name not in allowed_probes:
            raise PrototypeDesignError(
                f"{label} style probe {probe_name} is not allowed for {dimension}"
            )
        if probe_name in seen_probes:
            raise PrototypeDesignError(f"{label} style probes must be unique")
        seen_probes.add(probe_name)
        expected = _required_string(
            probe.get("expected"),
            f"{label} style probe {probe_name} requires expected",
        )
        observed = _required_string(
            probe.get("observed"),
            f"{label} style probe {probe_name} requires observed",
        )
        if observed != expected:
            raise PrototypeDesignError(
                f"{label} style probe {probe_name} did not match"
            )
    context_mapping = value.get("context_mapping")
    if not isinstance(context_mapping, dict):
        raise PrototypeDesignError(f"{label} requires context_mapping")
    _validate_mode_context_mapping(
        context_mapping,
        ui_change_type=ui_change_type,
        dimension=dimension,
        contract=contract,
        label=label,
    )
    return {"evidence_id": evidence_id}


def _validate_mode_context_mapping(
    value: dict[str, Any],
    *,
    ui_change_type: str,
    dimension: str,
    contract: dict[str, Any],
    label: str,
) -> None:
    if ui_change_type == "incremental_existing_surface":
        if dimension == "global_shell":
            _mapping_region_ids(
                value,
                "baseline_shell_region_ids",
                contract,
                label,
            )
        elif dimension == "navigation":
            _mapping_string(value, "ordinary_entry_path", label)
            _mapping_string(value, "navigation_mapping", label)
        elif dimension == "information_density":
            _mapping_string(value, "density_inheritance_mapping", label)
        elif dimension == "component_system":
            _mapping_string(value, "component_inheritance_mapping", label)
    elif ui_change_type == "new_surface_in_existing_product":
        if dimension == "global_shell":
            _mapping_region_ids(
                value,
                "existing_shell_region_ids",
                contract,
                label,
            )
        elif dimension == "navigation":
            _mapping_string(value, "ordinary_entry_path", label)
            _mapping_string(value, "navigation_integration", label)
        elif dimension == "component_system":
            _mapping_string(value, "design_system_integration", label)
    elif ui_change_type == "greenfield_ui" and dimension == "component_system":
        mappings = value.get("cross_page_state_consistency")
        if not isinstance(mappings, list) or len(mappings) < 2:
            raise PrototypeDesignError(
                f"{label} requires cross-page/state design-system consistency evidence"
            )
        seen: set[tuple[str, str]] = set()
        token_hashes: set[str] = set()
        for index, mapping in enumerate(mappings, start=1):
            if not isinstance(mapping, dict):
                raise PrototypeDesignError(
                    f"{label} cross-page/state mapping {index} must be an object"
                )
            key = (
                _required_string(
                    mapping.get("surface_id"),
                    f"{label} cross-page/state mapping {index} requires surface_id",
                ),
                _required_string(
                    mapping.get("state_id"),
                    f"{label} cross-page/state mapping {index} requires state_id",
                ),
            )
            if key in seen:
                raise PrototypeDesignError(
                    f"{label} cross-page/state mappings must be unique"
                )
            seen.add(key)
            token_hashes.add(
                _required_sha256(
                    mapping.get("token_set_sha256"),
                    f"{label} cross-page/state token_set_sha256",
                )
            )
        required_states = set(contract["surface_regions"])
        if not required_states.issubset(seen) or len(token_hashes) != 1:
            raise PrototypeDesignError(
                f"{label} cross-page/state design-system consistency evidence is incomplete"
            )


def _mapping_string(value: dict[str, Any], field_name: str, label: str) -> str:
    return _required_string(
        value.get(field_name),
        f"{label} context_mapping requires {field_name}",
    )


def _mapping_region_ids(
    value: dict[str, Any],
    field_name: str,
    contract: dict[str, Any],
    label: str,
) -> list[str]:
    region_ids = _string_list(
        value.get(field_name),
        f"{label} context_mapping requires {field_name}",
    )
    if not set(region_ids).issubset(set(contract["region_ids"])):
        raise PrototypeDesignError(
            f"{label} context_mapping {field_name} contains unknown region IDs"
        )
    return region_ids


def _normalize_callouts(
    value: Any,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PrototypeDesignError("intended_product_ui_callouts must be a list")
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, callout in enumerate(value, start=1):
        if not isinstance(callout, dict):
            raise PrototypeDesignError(f"callout {index} must be an object")
        callout_id = _required_string(
            callout.get("callout_id"),
            f"callout {index} missing callout_id",
        )
        if callout_id in seen_ids:
            raise PrototypeDesignError(f"duplicate callout_id: {callout_id}")
        seen_ids.add(callout_id)
        state_id = _required_string(
            callout.get("state_id"),
            f"callout {callout_id} missing state_id",
        )
        region_id = _required_string(
            callout.get("region_id"),
            f"callout {callout_id} missing region_id",
        )
        if region_id not in contract["region_states"] or state_id not in contract[
            "region_states"
        ][region_id]:
            raise PrototypeDesignError(
                f"callout {callout_id} state_id and region_id must match prototype contract"
            )
        normalized.append(
            {
                "callout_id": callout_id,
                "requirement_ids": sorted(
                    _string_list(
                        callout.get("requirement_ids"),
                        f"callout {callout_id} requires requirement_ids",
                    )
                ),
                "scenario_ids": sorted(
                    _string_list(
                        callout.get("scenario_ids"),
                        f"callout {callout_id} requires scenario_ids",
                    )
                ),
                "actor_roles": sorted(
                    _string_list(
                        callout.get("actor_roles"),
                        f"callout {callout_id} requires actor_roles",
                    )
                ),
                "trigger": _required_string(
                    callout.get("trigger"),
                    f"callout {callout_id} requires trigger",
                ),
                "lifecycle": _required_string(
                    callout.get("lifecycle"),
                    f"callout {callout_id} requires lifecycle",
                ),
                "dismissal_or_persistence": _required_string(
                    callout.get("dismissal_or_persistence"),
                    f"callout {callout_id} requires dismissal_or_persistence",
                ),
                "state_id": state_id,
                "region_id": region_id,
            }
        )
    return sorted(normalized, key=lambda item: item["callout_id"])


class _ReviewAnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {
            name.lower(): value or ""
            for name, value in attrs
        }
        if "data-annotation-id" in attributes:
            attributes["tag"] = tag.lower()
            self.anchors.append(attributes)


def _normalize_review_annotation_set(
    project_root: str | Path,
    value: Any,
    prototype_path: str,
    prototype_resolved: Path,
    contract: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if value is None:
        return None, None
    if not isinstance(value, dict):
        raise PrototypeDesignError("review_annotation_set must be an object or none")
    annotations = value.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        raise PrototypeDesignError("review_annotation_set requires annotations")

    artifact_path = _normalized_path(
        value.get("artifact_path"),
        "review_annotation_set artifact_path is required",
    )
    if Path(artifact_path).suffix.lower() != ".html":
        raise PrototypeDesignError("review annotation artifact must be an .html file")
    review_relative_root = Path(".product-delivery/artifacts/review-only")
    try:
        Path(artifact_path).relative_to(review_relative_root)
    except ValueError as cause:
        raise PrototypeDesignError(
            "review annotation artifact must be under .product-delivery/artifacts/review-only"
        ) from cause
    try:
        artifact_resolved = resolve_project_path(
            project_root,
            artifact_path,
            artifact_only=True,
        )
    except EvidenceArtifactError as cause:
        raise PrototypeDesignError(str(cause)) from cause
    review_root = (
        Path(project_root).resolve()
        / ".product-delivery"
        / "artifacts"
        / "review-only"
    ).resolve()
    try:
        artifact_resolved.relative_to(review_root)
    except ValueError as cause:
        raise PrototypeDesignError(
            "review annotation artifact must be under .product-delivery/artifacts/review-only"
        ) from cause
    if artifact_resolved == prototype_resolved:
        raise PrototypeDesignError(
            "review annotation artifact must differ from clean prototype path"
        )
    try:
        clean_html = prototype_resolved.read_text(encoding="utf-8").lower()
    except UnicodeDecodeError as cause:
        raise PrototypeDesignError("clean prototype HTML must be UTF-8") from cause
    if (
        artifact_path.lower() in clean_html
        or artifact_resolved.name.lower() in clean_html
    ):
        raise PrototypeDesignError(
            "review annotation artifact must not be imported into clean product HTML"
        )

    clean_surface_reference = _normalized_path(
        value.get("clean_surface_reference"),
        "review_annotation_set clean_surface_reference is required",
    )
    if clean_surface_reference != prototype_path:
        raise PrototypeDesignError(
            "review_annotation_set clean_surface_reference must equal prototype_path"
        )

    seen_ids: set[str] = set()
    normalized_annotations: list[dict[str, Any]] = []
    for index, annotation in enumerate(annotations, start=1):
        if not isinstance(annotation, dict):
            raise PrototypeDesignError(f"review annotation {index} must be an object")
        annotation_id = _required_string(
            annotation.get("annotation_id"),
            f"review annotation {index} missing annotation_id",
        )
        if annotation_id in seen_ids:
            raise PrototypeDesignError(f"duplicate annotation_id: {annotation_id}")
        seen_ids.add(annotation_id)
        target_region_id = _required_string(
            annotation.get("target_region_id"),
            f"review annotation {annotation_id} missing target_region_id",
        )
        if target_region_id not in contract["region_states"]:
            raise PrototypeDesignError(
                f"review annotation {annotation_id} target_region_id is not in prototype contract"
            )
        normalized_annotations.append(
            {
                "annotation_id": annotation_id,
                "target_region_id": target_region_id,
                "text": _required_string(
                    annotation.get("text"),
                    f"review annotation {annotation_id} requires text",
                ),
            }
        )

    try:
        review_html = artifact_resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        raise PrototypeDesignError(
            "review annotation artifact must be UTF-8 HTML"
        ) from cause
    parser = _ReviewAnchorParser()
    parser.feed(review_html)
    anchors_by_id: dict[str, dict[str, str]] = {}
    for anchor in parser.anchors:
        annotation_id = anchor.get("data-annotation-id", "").strip()
        if not annotation_id:
            raise PrototypeDesignError(
                "review annotation external anchor requires data-annotation-id"
            )
        if annotation_id in anchors_by_id:
            raise PrototypeDesignError(
                f"duplicate review annotation external anchor: {annotation_id}"
            )
        anchors_by_id[annotation_id] = anchor
    expected_ids = {item["annotation_id"] for item in normalized_annotations}
    if set(anchors_by_id) != expected_ids:
        raise PrototypeDesignError(
            "review annotation artifact external anchor mapping is incomplete"
        )
    for annotation in normalized_annotations:
        annotation_id = annotation["annotation_id"]
        target_region_id = annotation["target_region_id"]
        anchor = anchors_by_id[annotation_id]
        clean_region_id = anchor.get("data-clean-region-id", "").strip()
        if clean_region_id not in contract["region_states"]:
            raise PrototypeDesignError(
                f"review annotation {annotation_id} external anchor references unknown clean region"
            )
        if clean_region_id != target_region_id:
            raise PrototypeDesignError(
                f"review annotation {annotation_id} external anchor clean region does not match target_region_id"
            )
        if anchor.get("data-clean-surface-reference", "").strip() != prototype_path:
            raise PrototypeDesignError(
                f"review annotation {annotation_id} external anchor must reference clean surface"
            )
        if anchor.get("href", "").strip() != (
            f"{prototype_path}#{target_region_id}"
        ):
            raise PrototypeDesignError(
                f"review annotation {annotation_id} external anchor href must target clean region"
            )

    normalized = {
        "artifact_path": artifact_path,
        "clean_surface_reference": clean_surface_reference,
        "annotations": sorted(
            normalized_annotations,
            key=lambda item: item["annotation_id"],
        ),
    }
    return normalized, {
        "path": artifact_path,
        "sha256": sha256_file(artifact_resolved),
    }


def _build_coverage_matrix(
    contract: dict[str, Any],
    clean_surface: dict[str, Any],
    product_context: dict[str, Any],
    screenshots: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    checks_by_key = {
        (check["surface_id"], check["state_id"], check["viewport"]): check
        for check in clean_surface["runtime_checks"]
    }
    screenshots_by_key = {
        (item["surface_id"], item["state_id"], item["viewport"]): item
        for item in screenshots
    }
    rows_by_key = {
        (row["surface_id"], row["state_id"], row["dimension"]): row
        for row in product_context["coverage_rows"]
    }
    runtime_matrix = []
    for key in contract["runtime_order"]:
        check = checks_by_key[key]
        runtime_matrix.append(
            {
                "surface_id": key[0],
                "state_id": key[1],
                "viewport": key[2],
                "status": "passed",
                "required_region_ids": list(contract["runtime_regions"][key]),
                "observed_region_ids": check["observed_region_ids"],
                "clean_screenshot_sha256": screenshots_by_key[key]["artifact"][
                    "sha256"
                ],
            }
        )

    context_matrix = []
    for key in contract["context_order"]:
        row = rows_by_key[key]
        matrix_row = {
            "surface_id": key[0],
            "state_id": key[1],
            "dimension": key[2],
            "status": row["status"],
        }
        if row["status"] == "passed":
            matrix_row["covered_region_ids"] = row["covered_region_ids"]
            matrix_row["evidence_refs"] = row["evidence_refs"]
        else:
            matrix_row["exception"] = row["exception"]
        context_matrix.append(matrix_row)
    return {
        "runtime_checks": runtime_matrix,
        "product_context": context_matrix,
    }


def _build_design_audit(
    normalized_payload: dict[str, Any],
    artifact_metadata: dict[str, Any],
    required_coverage_matrix: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    context_rows = required_coverage_matrix["product_context"]
    annotations = normalized_payload["review_annotation_set"]
    deterministic_checks = {
        "semantic_snapshot_schema_valid": bool(
            artifact_metadata["semantic_snapshot"].get("sha256")
        ),
        "browser_preflight_bound": bool(
            artifact_metadata["browser_preflight_probe"].get("sha256")
        ),
        "clean_html_annotation_separated": True,
        "runtime_state_viewport_coverage_complete": bool(
            required_coverage_matrix["runtime_checks"]
        ),
        "review_external_anchor_mapping_valid": (
            annotations is None
            or artifact_metadata["review_annotation_artifact"] is not None
        ),
        "structured_design_evidence_resolved": bool(
            artifact_metadata["design_evidence_artifacts"]
        ),
        "mode_specific_product_context_valid": True,
    }
    return {
        "audit_version": "prototype-design-integrity-v1",
        "status": (
            "passed" if all(deterministic_checks.values()) else "failed"
        ),
        "ui_change_type": normalized_payload["ui_change_type"],
        "deterministic_checks": deterministic_checks,
        "runtime_coverage_complete": True,
        "product_context_coverage_complete": True,
        "required_runtime_check_count": len(
            required_coverage_matrix["runtime_checks"]
        ),
        "passed_runtime_check_count": len(
            required_coverage_matrix["runtime_checks"]
        ),
        "required_product_context_row_count": len(context_rows),
        "passed_product_context_row_count": sum(
            row["status"] == "passed" for row in context_rows
        ),
        "accepted_exemption_count": sum(
            row["status"] == "exempted" for row in context_rows
        ),
        "callout_count": len(
            normalized_payload["intended_product_ui_callouts"]
        ),
        "annotation_count": len(annotations["annotations"]) if annotations else 0,
        "artifact_count": (
            3
            + len(artifact_metadata["clean_screenshots"])
            + len(artifact_metadata["baseline_snapshots"])
            + len(artifact_metadata["design_evidence_artifacts"])
            + int(artifact_metadata["design_system_artifact"] is not None)
            + int(artifact_metadata["review_annotation_artifact"] is not None)
        ),
        "required_coverage_matrix_sha256": stable_json_hash(
            required_coverage_matrix
        ),
    }


def _normalized_path(value: Any, message: str) -> str:
    path = _required_string(value, message)
    return Path(path).as_posix()


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise PrototypeDesignError(
            f"{label} fixed schema missing fields: {', '.join(missing)}"
        )
    if unexpected:
        raise PrototypeDesignError(
            f"{label} fixed schema has unexpected fields: {', '.join(unexpected)}"
        )


def _required_string(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrototypeDesignError(message)
    return value.strip()


def _required_sha256(value: Any, label: str) -> str:
    normalized = _required_string(value, f"{label} is required")
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise PrototypeDesignError(f"{label} must be a lowercase SHA-256")
    return normalized


def _string_list(value: Any, message: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PrototypeDesignError(message)
    normalized = []
    for item in value:
        normalized.append(_required_string(item, message))
    if len(normalized) != len(set(normalized)):
        raise PrototypeDesignError(f"{message}; values must be unique")
    return normalized
