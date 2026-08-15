"""Prototype-bound implementation baseline and task conformance helpers."""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from product_delivery_agent.evidence_artifacts import (
    EvidenceArtifactError,
    load_json_artifact,
    stable_json_hash,
)


class ImplementationBaselineError(RuntimeError):
    """Raised when implementation baseline evidence is invalid."""


BASELINE_VERSION = "v1"
VISUAL_POLICY_VERSION = "v1"
DEFAULT_VISUAL_POLICY = {
    "policy_version": VISUAL_POLICY_VERSION,
    "critical_region_max_diff_ratio": 0.02,
    "full_surface_max_diff_ratio": 0.05,
    "pixel_threshold": 0.2,
    "geometry_tolerance_px": 4,
    "geometry_tolerance_viewport_ratio": 0.01,
    "dynamic_masks": [],
}

_THRESHOLD_FIELDS = (
    "critical_region_max_diff_ratio",
    "full_surface_max_diff_ratio",
    "pixel_threshold",
    "geometry_tolerance_px",
    "geometry_tolerance_viewport_ratio",
)
_MASK_FIELDS = {
    "surface_id",
    "state_id",
    "viewport_class",
    "region_ids",
}


def normalize_visual_policy(
    policy: dict[str, Any] | None,
    prototype_contract: dict[str, Any],
) -> dict[str, Any]:
    """Return a strict visual policy bound to known prototype regions."""
    raw = dict(policy or {})
    allowed = set(DEFAULT_VISUAL_POLICY)
    unexpected = sorted(set(raw) - allowed)
    if unexpected:
        raise ImplementationBaselineError(
            "visual policy has unexpected fields: " + ", ".join(unexpected)
        )
    if raw.get("policy_version", VISUAL_POLICY_VERSION) != VISUAL_POLICY_VERSION:
        raise ImplementationBaselineError(
            f"visual policy policy_version must be {VISUAL_POLICY_VERSION}"
        )

    normalized = deepcopy(DEFAULT_VISUAL_POLICY)
    for field_name in _THRESHOLD_FIELDS:
        if field_name not in raw:
            continue
        value = raw[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ImplementationBaselineError(
                f"visual policy {field_name} must be a non-negative finite number"
            )
        if value > DEFAULT_VISUAL_POLICY[field_name]:
            raise ImplementationBaselineError(
                f"visual policy {field_name} cannot be relaxed beyond the default"
            )
        normalized[field_name] = value

    normalized["dynamic_masks"] = _normalize_dynamic_masks(
        raw.get("dynamic_masks", []),
        prototype_contract,
    )
    return normalized


def build_implementation_baseline(
    project_root: str | Path,
    canonical_bundle: dict[str, Any],
    prototype_contract: dict[str, Any],
    visual_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the immutable prototype slice consumed by implementation tasks."""
    if canonical_bundle.get("status") != "ready":
        raise ImplementationBaselineError("ready prototype design bundle is required")
    if prototype_contract.get("status") != "ready":
        raise ImplementationBaselineError("ready prototype contract is required")

    clean_surface = _required_dict(
        canonical_bundle.get("clean_surface"),
        "prototype bundle clean_surface is required",
    )
    artifact_metadata = _required_dict(
        canonical_bundle.get("artifact_metadata"),
        "prototype bundle artifact_metadata is required",
    )
    try:
        semantic_snapshot, _ = load_json_artifact(
            project_root,
            _required_string(
                clean_surface.get("semantic_snapshot_path"),
                "prototype semantic snapshot path is required",
            ),
        )
    except EvidenceArtifactError as cause:
        raise ImplementationBaselineError(str(cause)) from cause

    semantic_by_key = _semantic_states_by_key(semantic_snapshot)
    checks_by_key = _runtime_checks_by_key(clean_surface.get("runtime_checks"))
    screenshots_by_key = _screenshots_by_key(
        artifact_metadata.get("clean_screenshots")
    )
    normalized_policy = normalize_visual_policy(visual_policy, prototype_contract)
    masks_by_key = {
        (
            mask["surface_id"],
            mask["state_id"],
            mask["viewport_class"],
        ): list(mask["region_ids"])
        for mask in normalized_policy["dynamic_masks"]
    }

    units = []
    for surface in prototype_contract.get("surfaces") or []:
        surface_id = _required_string(
            surface.get("surface_id"),
            "prototype contract surface_id is required",
        )
        state_id = _required_string(
            surface.get("state_id"),
            f"prototype contract surface {surface_id} state_id is required",
        )
        for viewport in surface.get("required_viewports") or []:
            key = (surface_id, state_id, str(viewport))
            check = checks_by_key.get(key)
            semantic_state = semantic_by_key.get(key)
            screenshot = screenshots_by_key.get(key)
            if check is None or semantic_state is None or screenshot is None:
                raise ImplementationBaselineError(
                    "prototype baseline missing unit evidence: " + repr(key)
                )
            unit = {
                "surface_id": surface_id,
                "state_id": state_id,
                "viewport_class": str(viewport),
                "route": _required_string(
                    surface.get("route"),
                    f"prototype contract surface {surface_id} route is required",
                ),
                "prototype_path": clean_surface["prototype_path"],
                "prototype_screenshot_path": check["clean_screenshot_path"],
                "prototype_screenshot_sha256": screenshot["sha256"],
                "prototype_screenshot_width": screenshot["width"],
                "prototype_screenshot_height": screenshot["height"],
                "region_ids": [
                    region["region_id"]
                    for region in surface.get("critical_regions") or []
                ],
                "interaction_ids": [
                    interaction["interaction_id"]
                    for interaction in surface.get("critical_interactions") or []
                ],
                "critical_regions": deepcopy(surface.get("critical_regions") or []),
                "critical_relationships": deepcopy(
                    surface.get("critical_relationships") or []
                ),
                "critical_interactions": deepcopy(
                    surface.get("critical_interactions") or []
                ),
                "prototype_regions": deepcopy(semantic_state["regions"]),
                "dynamic_mask_region_ids": masks_by_key.get(key, []),
            }
            units.append(unit)

    clean_prototype = _required_dict(
        artifact_metadata.get("clean_prototype"),
        "clean prototype artifact metadata is required",
    )
    body = {
        "baseline_version": BASELINE_VERSION,
        "product_domain_sha256": _required_string(
            canonical_bundle.get("product_domain_sha256"),
            "prototype product domain hash is required",
        ),
        "bundle_sha256": _required_string(
            canonical_bundle.get("bundle_sha256"),
            "prototype bundle hash is required",
        ),
        "prototype_contract_sha256": _required_string(
            prototype_contract.get("contract_sha256"),
            "prototype contract hash is required",
        ),
        "prototype_screenshot_set_sha256": _required_string(
            prototype_contract.get("prototype_screenshot_set_sha256"),
            "prototype screenshot set hash is required",
        ),
        "prototype_path": clean_surface["prototype_path"],
        "prototype_sha256": _required_string(
            clean_prototype.get("sha256"),
            "clean prototype hash is required",
        ),
        "semantic_snapshot_path": clean_surface["semantic_snapshot_path"],
        "design_system_artifact": deepcopy(
            artifact_metadata.get("design_system_artifact")
        ),
        "visual_policy": normalized_policy,
        "visual_policy_sha256": stable_json_hash(normalized_policy),
        "units": units,
    }
    return {
        **body,
        "status": "ready",
        "baseline_sha256": stable_json_hash(body),
    }


def _normalize_dynamic_masks(
    masks: Any,
    prototype_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(masks, list):
        raise ImplementationBaselineError("visual policy dynamic_masks must be a list")
    units: dict[tuple[str, str, str], set[str]] = {}
    for surface in prototype_contract.get("surfaces") or []:
        surface_id = str(surface.get("surface_id") or "")
        state_id = str(surface.get("state_id") or "")
        region_ids = {
            str(region.get("region_id") or "")
            for region in surface.get("critical_regions") or []
        }
        for viewport in surface.get("required_viewports") or []:
            units[(surface_id, state_id, str(viewport))] = region_ids

    normalized = []
    seen: set[tuple[str, str, str]] = set()
    for index, mask in enumerate(masks, start=1):
        if not isinstance(mask, dict) or set(mask) != _MASK_FIELDS:
            raise ImplementationBaselineError(
                f"dynamic mask {index} must contain exactly: "
                + ", ".join(sorted(_MASK_FIELDS))
            )
        key = (
            _required_string(mask.get("surface_id"), f"dynamic mask {index} surface_id is required"),
            _required_string(mask.get("state_id"), f"dynamic mask {index} state_id is required"),
            _required_string(
                mask.get("viewport_class"),
                f"dynamic mask {index} viewport_class is required",
            ),
        )
        if key not in units:
            raise ImplementationBaselineError(
                f"dynamic mask {index} references unknown surface state viewport"
            )
        if key in seen:
            raise ImplementationBaselineError(f"duplicate dynamic mask: {key}")
        seen.add(key)
        region_ids = mask.get("region_ids")
        if (
            not isinstance(region_ids, list)
            or not region_ids
            or not all(isinstance(item, str) and item.strip() for item in region_ids)
            or len(region_ids) != len(set(region_ids))
        ):
            raise ImplementationBaselineError(
                f"dynamic mask {index} region_ids must be unique non-empty strings"
            )
        unknown = sorted(set(region_ids) - units[key])
        if unknown:
            raise ImplementationBaselineError(
                f"dynamic mask {index} references unknown region: "
                + ", ".join(unknown)
            )
        normalized.append(
            {
                "surface_id": key[0],
                "state_id": key[1],
                "viewport_class": key[2],
                "region_ids": list(region_ids),
            }
        )
    return normalized


def _semantic_states_by_key(snapshot: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    states = snapshot.get("states")
    if not isinstance(states, list) or not states:
        raise ImplementationBaselineError("prototype semantic snapshot requires states")
    result = {}
    for state in states:
        if not isinstance(state, dict):
            raise ImplementationBaselineError("prototype semantic state must be an object")
        key = (
            str(state.get("surface_id") or ""),
            str(state.get("state_id") or ""),
            str(state.get("viewport") or ""),
        )
        if key in result:
            raise ImplementationBaselineError(f"duplicate prototype semantic state: {key}")
        result[key] = state
    return result


def _runtime_checks_by_key(checks: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    if not isinstance(checks, list) or not checks:
        raise ImplementationBaselineError("prototype baseline requires runtime checks")
    return {
        (
            str(check.get("surface_id") or ""),
            str(check.get("state_id") or ""),
            str(check.get("viewport") or ""),
        ): check
        for check in checks
        if isinstance(check, dict)
    }


def _screenshots_by_key(value: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ImplementationBaselineError("prototype baseline requires clean screenshots")
    result = {}
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get("artifact"), dict):
            raise ImplementationBaselineError("clean screenshot metadata is invalid")
        key = (
            str(record.get("surface_id") or ""),
            str(record.get("state_id") or ""),
            str(record.get("viewport") or ""),
        )
        result[key] = record["artifact"]
    return result


def _required_dict(value: Any, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ImplementationBaselineError(message)
    return value


def _required_string(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImplementationBaselineError(message)
    return value.strip()
