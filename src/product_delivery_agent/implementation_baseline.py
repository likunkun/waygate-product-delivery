"""Prototype-bound implementation baseline and task conformance helpers."""

from __future__ import annotations

import math
import struct
import zlib
from copy import deepcopy
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


class ImplementationBaselineError(RuntimeError):
    """Raised when implementation baseline evidence is invalid."""


class _PNGDimensionsMismatch(ImplementationBaselineError):
    """Raised before decoding a production PNG with unexpected dimensions."""


class _PNGResourceLimitError(ImplementationBaselineError):
    """Raised when PNG evidence exceeds bounded decoder resources."""


BASELINE_VERSION = "v1"
VISUAL_POLICY_VERSION = "v1"
TASK_CONFORMANCE_VERSION = "v2"
LEGACY_TASK_CONFORMANCE_VERSIONS = frozenset({"v1", TASK_CONFORMANCE_VERSION})
TASK_SEMANTIC_SNAPSHOT_VERSION = "task-production-semantic-snapshot-v1"
DEFAULT_VISUAL_POLICY = {
    "policy_version": VISUAL_POLICY_VERSION,
    "critical_region_max_diff_ratio": 0.02,
    "full_surface_max_diff_ratio": 0.05,
    "pixel_threshold": 0.2,
    "geometry_tolerance_px": 4,
    "geometry_tolerance_viewport_ratio": 0.01,
    "dynamic_masks": [],
}
VISUAL_PIXEL_FAILURE_CODES = frozenset(
    {"critical_region_pixel_diff", "full_surface_pixel_diff"}
)
VISUAL_ADJUDICABLE_FAILURE_CODES = frozenset(
    {*VISUAL_PIXEL_FAILURE_CODES, "geometry_mismatch"}
)
VISUAL_ADJUDICABLE = "visual_adjudicable"
HARD_BLOCKING = "hard_blocking"

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
_MAX_PNG_FILE_BYTES = 16 * 1024 * 1024
_MAX_PNG_PIXELS = 16_000_000
_MAX_PNG_DECODED_BYTES = 64 * 1024 * 1024


def implementation_baseline_required(state: dict[str, Any]) -> bool:
    """Return whether the delivery opted into the V1.0.28 UI policy."""
    policy = state.get("implementation_baseline_policy") or {}
    return bool(
        state.get("project_type") == "ui"
        and policy.get("policy_version") == BASELINE_VERSION
        and policy.get("status") == "required"
    )


def validate_implementation_baseline(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a canonical persisted implementation baseline."""
    if not isinstance(value, dict) or value.get("status") != "ready":
        raise ImplementationBaselineError(
            "canonical implementation baseline must have status ready"
        )
    body = {
        key: deepcopy(item)
        for key, item in value.items()
        if key not in {"status", "baseline_sha256"}
    }
    if value.get("baseline_sha256") != stable_json_hash(body):
        raise ImplementationBaselineError(
            "canonical implementation baseline hash is invalid"
        )
    if value.get("baseline_version") != BASELINE_VERSION:
        raise ImplementationBaselineError(
            f"canonical implementation baseline version must be {BASELINE_VERSION}"
        )
    if not isinstance(value.get("units"), list) or not value["units"]:
        raise ImplementationBaselineError(
            "canonical implementation baseline units are required"
        )
    return deepcopy(value)


def validate_task_prototype_conformance(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a canonical persisted task conformance artifact."""
    if not isinstance(value, dict) or value.get("status") not in {
        "passed",
        "failed",
        "inconclusive",
        "accepted_by_user",
    }:
        raise ImplementationBaselineError(
            "canonical task prototype conformance status is invalid"
        )
    body = {
        key: deepcopy(item)
        for key, item in value.items()
        if key not in {"status", "evidence_sha256"}
    }
    if value.get("evidence_sha256") != stable_json_hash(body):
        raise ImplementationBaselineError(
            "canonical task prototype conformance evidence hash is invalid"
        )
    if value.get("conformance_version") not in LEGACY_TASK_CONFORMANCE_VERSIONS:
        raise ImplementationBaselineError(
            "canonical task prototype conformance version is invalid"
        )
    if value.get("status") == "passed" and (
        value.get("environment_status") != "stable"
        or value.get("failures")
        or value.get("failure_codes")
    ):
        raise ImplementationBaselineError(
            "canonical task prototype conformance passed status is inconsistent"
        )
    if value.get("status") == "accepted_by_user":
        if not task_conformance_is_adjudicable_visual_failure(value):
            raise ImplementationBaselineError(
                "user-adjudicated task conformance must contain only adjudicable visual failures"
            )
        adjudication = value.get("visual_adjudication")
        if not isinstance(adjudication, dict) or not all(
            isinstance(adjudication.get(field), str) and adjudication[field].strip()
            for field in (
                "artifact_path",
                "artifact_sha256",
                "decision_id",
                "source",
            )
        ):
            raise ImplementationBaselineError(
                "user-adjudicated task conformance requires canonical adjudication evidence"
            )
    return deepcopy(value)


def task_conformance_is_adjudicable_visual_failure(value: dict[str, Any]) -> bool:
    """Return whether stable conformance failed only on user-adjudicable visuals."""
    codes = value.get("failure_codes")
    if not (
        isinstance(value, dict)
        and value.get("environment_status") == "stable"
        and isinstance(codes, list)
        and codes
    ):
        return False
    if value.get("conformance_version") == "v1":
        return set(codes).issubset(VISUAL_PIXEL_FAILURE_CODES)
    eligibility = value.get("adjudication_eligibility")
    failures = value.get("failures")
    if not (
        isinstance(failures, list)
        and failures
        and all(
            isinstance(failure, dict)
            and failure.get("failure_class") == VISUAL_ADJUDICABLE
            for failure in failures
        )
    ):
        return False
    visual_codes = _failure_codes(failures)
    return bool(
        isinstance(eligibility, dict)
        and eligibility.get("eligible") is True
        and eligibility.get("visual_failure_codes") == visual_codes
        and not eligibility.get("hard_failure_codes")
        and codes == visual_codes
    )


def task_conformance_is_visual_only_failure(value: dict[str, Any]) -> bool:
    """Compatibility alias for the broadened visual-adjudication predicate."""
    return task_conformance_is_adjudicable_visual_failure(value)


def task_conformance_visual_deviations(
    value: dict[str, Any],
    *,
    adjudication_artifact_sha256: str,
) -> list[dict[str, Any]]:
    """Render normalized visual deviations for final UI review evidence."""
    if not task_conformance_is_adjudicable_visual_failure(value):
        return []
    is_v2 = value.get("conformance_version") == TASK_CONFORMANCE_VERSION
    rows: list[dict[str, Any]] = []
    for record in value.get("records") or []:
        if not isinstance(record, dict):
            continue
        common = {
            "task_id": value.get("task_id"),
            "adjudication_artifact_sha256": adjudication_artifact_sha256,
            "surface_id": record.get("surface_id"),
            "state_id": record.get("state_id"),
            "viewport_class": record.get("viewport_class"),
        }
        full_ratio = record.get("full_surface_diff_ratio")
        full_max = record.get("full_surface_max_diff_ratio")
        if isinstance(full_ratio, (int, float)) and isinstance(full_max, (int, float)) and full_ratio > full_max:
            rows.append(
                {
                    **common,
                    **({"deviation_type": "pixel"} if is_v2 else {}),
                    "scope": "full_surface",
                    "region_id": None,
                    "diff_ratio": full_ratio,
                    "max_diff_ratio": full_max,
                }
            )
        for region in record.get("critical_region_results") or []:
            if not isinstance(region, dict):
                continue
            ratio = region.get("diff_ratio")
            maximum = region.get("max_diff_ratio")
            if isinstance(ratio, (int, float)) and isinstance(maximum, (int, float)) and ratio > maximum:
                rows.append(
                    {
                        **common,
                        **({"deviation_type": "pixel"} if is_v2 else {}),
                        "scope": "critical_region",
                        "region_id": region.get("region_id"),
                        "diff_ratio": ratio,
                        "max_diff_ratio": maximum,
                    }
                )
        if is_v2:
            for geometry in record.get("geometry_results") or []:
                if (
                    not isinstance(geometry, dict)
                    or geometry.get("failure_class") != VISUAL_ADJUDICABLE
                ):
                    continue
                rows.append(
                    {
                        **common,
                        "deviation_type": "geometry",
                        "scope": "geometry_region",
                        "region_id": geometry.get("region_id"),
                        "prototype_bounds": deepcopy(
                            geometry.get("prototype_bounds")
                        ),
                        "production_bounds": deepcopy(
                            geometry.get("production_bounds")
                        ),
                        "delta": deepcopy(geometry.get("delta")),
                        "tolerance": deepcopy(geometry.get("tolerance")),
                        "viewport_overflow": deepcopy(
                            geometry.get("viewport_overflow")
                        ),
                        "classification_reason": geometry.get(
                            "classification_reason"
                        ),
                    }
                )
    return rows


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


def build_task_prototype_conformance(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    implementation_baseline: dict[str, Any],
    planned_task: dict[str, Any],
) -> dict[str, Any]:
    """Build objective task-level semantic and visual conformance evidence."""
    failures: list[dict[str, Any]] = []
    baseline_hash = implementation_baseline.get("baseline_sha256")
    planned_task_hash = planned_task.get("planned_task_hash")
    if implementation_baseline.get("status") != "ready":
        _record_failure(failures, "baseline_not_ready", "ready baseline is required")
    if payload.get("implementation_baseline_sha256") != baseline_hash:
        _record_failure(
            failures,
            "baseline_hash_mismatch",
            "task evidence must match the current implementation baseline",
        )
    if payload.get("planned_task_hash") != planned_task_hash:
        _record_failure(
            failures,
            "planned_task_hash_mismatch",
            "task evidence must match the current planned task",
        )
    if planned_task.get("ui_impact") != "prototype_bound":
        _record_failure(
            failures,
            "task_not_prototype_bound",
            "task conformance is only valid for prototype-bound tasks",
        )

    environment_status = payload.get("environment_status")
    environment_reason = payload.get("environment_reason")
    if environment_status == "inconclusive":
        if not isinstance(environment_reason, str) or not environment_reason.strip():
            _record_failure(
                failures,
                "environment_reason_missing",
                "inconclusive capture environment requires a reason",
            )
        _record_failure(
            failures,
            "environment_inconclusive",
            str(environment_reason or "capture environment was inconclusive"),
        )
        return _finish_task_conformance(
            baseline_hash=baseline_hash,
            planned_task=planned_task,
            environment_status="inconclusive",
            environment_reason=environment_reason,
            records=[],
            failures=failures,
            forced_status=(
                "inconclusive"
                if "environment_reason_missing" not in _failure_codes(failures)
                else "failed"
            ),
        )
    if environment_status != "stable":
        _record_failure(
            failures,
            "environment_status_invalid",
            "environment_status must be stable or inconclusive",
        )

    expected_units = _bound_units(implementation_baseline, planned_task, failures)
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        _record_failure(
            failures,
            "evidence_missing",
            "stable task conformance requires production records",
        )
        raw_records = []
    records_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, record in enumerate(raw_records, start=1):
        if not isinstance(record, dict):
            _record_failure(
                failures,
                "evidence_invalid",
                f"task conformance record {index} must be an object",
            )
            continue
        key = _unit_key(record)
        if key in records_by_key:
            _record_failure(
                failures,
                "duplicate_unit_evidence",
                f"duplicate task conformance record: {key}",
                unit_key=key,
            )
            continue
        records_by_key[key] = record

    hydrated_records: list[dict[str, Any]] = []
    for key, bound in expected_units.items():
        record = records_by_key.get(key)
        if record is None:
            _record_failure(
                failures,
                "evidence_missing",
                f"missing task conformance record: {key}",
                unit_key=key,
            )
            continue
        hydrated_records.append(
            _validate_task_unit(
                project_root,
                record,
                unit=bound["unit"],
                binding=bound["binding"],
                visual_policy=implementation_baseline.get("visual_policy") or {},
                failures=failures,
            )
        )
    for key in sorted(set(records_by_key) - set(expected_units)):
        _record_failure(
            failures,
            "unexpected_unit_evidence",
            f"task conformance record is not bound to the task: {key}",
            unit_key=key,
        )

    return _finish_task_conformance(
        baseline_hash=baseline_hash,
        planned_task=planned_task,
        environment_status=str(environment_status or "missing"),
        environment_reason=environment_reason,
        records=hydrated_records,
        failures=failures,
    )


def _bound_units(
    baseline: dict[str, Any],
    task: dict[str, Any],
    failures: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    units = {_unit_key(unit): unit for unit in baseline.get("units", []) if isinstance(unit, dict)}
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    bindings = task.get("prototype_bindings")
    if not isinstance(bindings, list) or not bindings:
        _record_failure(
            failures,
            "prototype_bindings_missing",
            "prototype-bound task requires bindings",
        )
        return result
    for binding in bindings:
        if not isinstance(binding, dict):
            _record_failure(
                failures,
                "prototype_binding_invalid",
                "prototype binding must be an object",
            )
            continue
        for viewport in binding.get("viewport_classes") or []:
            key = (
                str(binding.get("surface_id") or ""),
                str(binding.get("state_id") or ""),
                str(viewport or ""),
            )
            unit = units.get(key)
            if unit is None:
                _record_failure(
                    failures,
                    "prototype_binding_stale",
                    f"prototype binding does not exist in baseline: {key}",
                    unit_key=key,
                )
            elif key in result:
                _record_failure(
                    failures,
                    "prototype_binding_duplicate",
                    f"prototype binding is duplicated: {key}",
                    unit_key=key,
                )
            else:
                result[key] = {"unit": unit, "binding": binding}
    return result


def _validate_task_unit(
    project_root: str | Path,
    record: dict[str, Any],
    *,
    unit: dict[str, Any],
    binding: dict[str, Any],
    visual_policy: dict[str, Any],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    key = _unit_key(unit)
    local_failures: list[dict[str, Any]] = []
    if record.get("production_route") != unit.get("route"):
        _record_failure(
            local_failures,
            "route_mismatch",
            "production route does not match the prototype route",
            unit_key=key,
        )

    prototype_image = production_image = None
    snapshot = None
    snapshot_metadata: dict[str, Any] | None = None
    try:
        prototype_image = _decode_png(
            project_root,
            str(unit.get("prototype_screenshot_path") or ""),
        )
        if prototype_image["sha256"] != unit.get("prototype_screenshot_sha256"):
            raise ImplementationBaselineError("prototype screenshot hash is stale")
        if (
            prototype_image["width"] != unit.get("prototype_screenshot_width")
            or prototype_image["height"] != unit.get("prototype_screenshot_height")
        ):
            raise ImplementationBaselineError("prototype screenshot dimensions are stale")
        production_image = _decode_png(
            project_root,
            str(record.get("production_screenshot_path") or ""),
            reuse_pixels_from=prototype_image,
            expected_width=prototype_image["width"],
            expected_height=prototype_image["height"],
        )
    except _PNGDimensionsMismatch as cause:
        _record_failure(
            local_failures,
            "screenshot_dimensions_mismatch",
            str(cause),
            unit_key=key,
        )
    except _PNGResourceLimitError as cause:
        _record_failure(
            local_failures,
            "png_resource_limit",
            str(cause),
            unit_key=key,
        )
    except (EvidenceArtifactError, ImplementationBaselineError, OSError) as cause:
        _record_failure(
            local_failures,
            "evidence_missing",
            str(cause),
            unit_key=key,
        )
    try:
        snapshot, snapshot_metadata = load_json_artifact(
            project_root,
            str(record.get("semantic_snapshot_path") or ""),
        )
    except (EvidenceArtifactError, OSError) as cause:
        _record_failure(
            local_failures,
            "evidence_missing",
            str(cause),
            unit_key=key,
        )

    critical_results: list[dict[str, Any]] = []
    geometry_results: list[dict[str, Any]] = []
    full_surface_diff_ratio: float | None = None
    pixel_diff_artifact_path: str | None = None
    if prototype_image is not None and production_image is not None:
        if (
            prototype_image["width"] != production_image["width"]
            or prototype_image["height"] != production_image["height"]
        ):
            _record_failure(
                local_failures,
                "screenshot_dimensions_mismatch",
                "production screenshot dimensions must match the prototype",
                unit_key=key,
            )
        else:
            pixel_diff_artifact_path = _write_pixel_diff_artifact(
                project_root,
                prototype_image,
                production_image,
            )
            prototype_regions = {
                region.get("region_id"): region
                for region in unit.get("prototype_regions", [])
                if isinstance(region, dict)
            }
            mask_boxes = [
                prototype_regions[region_id]["bounds"]
                for region_id in unit.get("dynamic_mask_region_ids", [])
                if region_id in prototype_regions
            ]
            full_surface_diff_ratio = _pixel_diff_ratio(
                prototype_image,
                production_image,
                threshold=float(visual_policy.get("pixel_threshold", 0.2)),
                excluded_boxes=mask_boxes,
            )
            if full_surface_diff_ratio > float(
                visual_policy.get("full_surface_max_diff_ratio", 0.05)
            ):
                _record_failure(
                    local_failures,
                    "full_surface_pixel_diff",
                    "full-surface pixel difference exceeds the frozen threshold",
                    unit_key=key,
                )
            for region_id in binding.get("region_ids") or []:
                prototype_region = prototype_regions.get(region_id)
                if prototype_region is None:
                    _record_failure(
                        local_failures,
                        "region_missing",
                        f"prototype region is missing from baseline: {region_id}",
                        unit_key=key,
                        region_id=region_id,
                    )
                    continue
                ratio = _pixel_diff_ratio(
                    prototype_image,
                    production_image,
                    threshold=float(visual_policy.get("pixel_threshold", 0.2)),
                    include_box=prototype_region.get("bounds"),
                    excluded_boxes=mask_boxes,
                )
                critical_results.append(
                    {
                        "region_id": region_id,
                        "diff_ratio": ratio,
                        "max_diff_ratio": float(
                            visual_policy.get("critical_region_max_diff_ratio", 0.02)
                        ),
                        "masked": region_id
                        in set(unit.get("dynamic_mask_region_ids", [])),
                    }
                )
                if ratio > float(
                    visual_policy.get("critical_region_max_diff_ratio", 0.02)
                ):
                    _record_failure(
                        local_failures,
                        "critical_region_pixel_diff",
                        "critical-region pixel difference exceeds the frozen threshold",
                        unit_key=key,
                        region_id=region_id,
                    )

    if snapshot is not None and production_image is not None:
        geometry_results = _validate_task_semantics(
            snapshot,
            unit=unit,
            binding=binding,
            production_image=production_image,
            visual_policy=visual_policy,
            failures=local_failures,
        )
    _validate_computed_style_comparisons(
        record.get("computed_style_comparisons"),
        binding=binding,
        unit_key=key,
        failures=local_failures,
    )
    failures.extend(local_failures)
    return {
        "surface_id": key[0],
        "state_id": key[1],
        "viewport_class": key[2],
        "production_route": record.get("production_route"),
        "production_screenshot_path": record.get("production_screenshot_path"),
        "production_screenshot_sha256": (
            production_image.get("sha256") if production_image else None
        ),
        "semantic_snapshot_path": record.get("semantic_snapshot_path"),
        "semantic_snapshot_sha256": (
            snapshot_metadata.get("sha256") if snapshot_metadata else None
        ),
        "computed_style_comparisons": deepcopy(
            record.get("computed_style_comparisons") or []
        ),
        "full_surface_diff_ratio": full_surface_diff_ratio,
        "full_surface_max_diff_ratio": float(
            visual_policy.get("full_surface_max_diff_ratio", 0.05)
        ),
        "critical_region_results": critical_results,
        "geometry_results": geometry_results,
        "pixel_diff_artifact_path": pixel_diff_artifact_path,
        "failure_codes": _failure_codes(local_failures),
    }


def _validate_task_semantics(
    snapshot: dict[str, Any],
    *,
    unit: dict[str, Any],
    binding: dict[str, Any],
    production_image: dict[str, Any],
    visual_policy: dict[str, Any],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    key = _unit_key(unit)
    geometry_results: list[dict[str, Any]] = []
    if snapshot.get("schema_version") != TASK_SEMANTIC_SNAPSHOT_VERSION:
        _record_failure(
            failures,
            "semantic_snapshot_invalid",
            f"semantic snapshot schema must be {TASK_SEMANTIC_SNAPSHOT_VERSION}",
            unit_key=key,
        )
    if (
        snapshot.get("surface_id") != unit.get("surface_id")
        or snapshot.get("state_id") != unit.get("state_id")
    ):
        _record_failure(
            failures,
            "semantic_identity_mismatch",
            "semantic snapshot surface/state does not match the baseline unit",
            unit_key=key,
        )
    if snapshot.get("route") != unit.get("route"):
        _record_failure(
            failures,
            "route_mismatch",
            "semantic snapshot route does not match the prototype route",
            unit_key=key,
        )
    viewport = snapshot.get("viewport")
    if not isinstance(viewport, dict) or (
        viewport.get("class") != unit.get("viewport_class")
        or viewport.get("width") != production_image["width"]
        or viewport.get("height") != production_image["height"]
    ):
        _record_failure(
            failures,
            "viewport_mismatch",
            "semantic viewport must match the production screenshot and bound viewport",
            unit_key=key,
        )
        viewport = {
            "width": production_image["width"],
            "height": production_image["height"],
        }

    raw_regions = snapshot.get("regions")
    observed_regions: dict[str, dict[str, Any]] = {}
    if isinstance(raw_regions, list):
        for region in raw_regions:
            if not isinstance(region, dict) or not isinstance(region.get("region_id"), str):
                continue
            region_id = region["region_id"]
            if region_id in observed_regions:
                _record_failure(
                    failures,
                    "semantic_snapshot_invalid",
                    f"semantic region is duplicated: {region_id}",
                    unit_key=key,
                    region_id=region_id,
                )
            observed_regions[region_id] = region
    else:
        _record_failure(
            failures,
            "semantic_snapshot_invalid",
            "semantic snapshot regions must be a list",
            unit_key=key,
        )

    requirements = {
        region.get("region_id"): region
        for region in unit.get("critical_regions", [])
        if isinstance(region, dict)
    }
    prototype_regions = {
        region.get("region_id"): region
        for region in unit.get("prototype_regions", [])
        if isinstance(region, dict)
    }
    for region_id in binding.get("region_ids") or []:
        observed = observed_regions.get(region_id)
        requirement = requirements.get(region_id) or {}
        prototype = prototype_regions.get(region_id) or {}
        if observed is None:
            _record_failure(
                failures,
                "region_missing",
                f"production semantic snapshot is missing region: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
            continue
        if observed.get("matched_count") != 1 or observed.get("visible") is not True:
            _record_failure(
                failures,
                "region_visibility_mismatch",
                f"production region must be uniquely visible: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        expected_role = requirement.get("semantic_role") or prototype.get("semantic_role")
        if observed.get("role") != expected_role:
            _record_failure(
                failures,
                "region_semantics_mismatch",
                f"production region role differs from prototype: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        if not _accessible_name_matches(
            observed.get("accessible_name"),
            requirement.get("accessible_name_match") or {
                "mode": "exact",
                "value": prototype.get("accessible_name"),
            },
        ):
            _record_failure(
                failures,
                "accessible_name_mismatch",
                f"production accessible name differs from prototype: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        expected_parent = requirement.get(
            "parent_region_id", prototype.get("parent_region_id")
        )
        if observed.get("parent_region_id") != expected_parent:
            _record_failure(
                failures,
                "region_hierarchy_mismatch",
                f"production region hierarchy differs from prototype: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        expected_order = requirement.get("display_order", prototype.get("display_order"))
        if observed.get("display_order") != expected_order:
            _record_failure(
                failures,
                "region_order_mismatch",
                f"production region order differs from prototype: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        expected_controls = set(prototype.get("controls") or [])
        observed_controls = observed.get("key_controls")
        if not isinstance(observed_controls, list) or not expected_controls.issubset(
            set(observed_controls)
        ):
            _record_failure(
                failures,
                "required_controls_missing",
                f"production region is missing required controls: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        if observed.get("interaction_state") != prototype.get("interaction_state"):
            _record_failure(
                failures,
                "interaction_state_mismatch",
                f"production interaction state differs from prototype: {region_id}",
                unit_key=key,
                region_id=region_id,
            )
        box = observed.get("bounding_box")
        prototype_box = prototype.get("bounds")
        geometry = _assess_geometry(
            prototype_box,
            box,
            viewport,
            visual_policy,
            visible=observed.get("visible") is True,
        )
        geometry_results.append({"region_id": region_id, **geometry})
        if geometry["classification"] in {"soft_invalid", "hard_invalid"}:
            _record_failure(
                failures,
                "geometry_invalid",
                f"production region geometry is invalid: {region_id}",
                unit_key=key,
                region_id=region_id,
                failure_class=geometry["failure_class"],
                classification_reason=geometry["classification_reason"],
            )
        elif geometry["classification"] == "mismatch":
            _record_failure(
                failures,
                "geometry_mismatch",
                f"production region geometry exceeds frozen tolerance: {region_id}",
                unit_key=key,
                region_id=region_id,
                failure_class=VISUAL_ADJUDICABLE,
                classification_reason=geometry["classification_reason"],
            )

    bound_regions = set(binding.get("region_ids") or [])
    required_relationships = {
        (
            relationship.get("source_region_id"),
            relationship.get("relation"),
            relationship.get("target_region_id"),
        )
        for relationship in unit.get("critical_relationships", [])
        if isinstance(relationship, dict)
        and (
            relationship.get("source_region_id") in bound_regions
            or relationship.get("target_region_id") in bound_regions
        )
    }
    observed_relationships = {
        (
            relationship.get("source_region_id"),
            relationship.get("relation"),
            relationship.get("target_region_id"),
        )
        for relationship in snapshot.get("relationships", [])
        if isinstance(relationship, dict) and relationship.get("observed") is True
    }
    if required_relationships - observed_relationships:
        _record_failure(
            failures,
            "relationship_missing",
            "production semantic relationships do not cover the task binding",
            unit_key=key,
        )

    interactions = {
        item.get("interaction_id"): item
        for item in snapshot.get("interactions", [])
        if isinstance(item, dict) and isinstance(item.get("interaction_id"), str)
    }
    requirements_by_interaction = {
        item.get("interaction_id"): item
        for item in unit.get("critical_interactions", [])
        if isinstance(item, dict)
    }
    for interaction_id in binding.get("interaction_ids") or []:
        observed = interactions.get(interaction_id)
        requirement = requirements_by_interaction.get(interaction_id) or {}
        if (
            observed is None
            or observed.get("observed") is not True
            or not isinstance(observed.get("result"), str)
            or not observed["result"].strip()
            or observed.get("relation") != requirement.get("expected_relation")
            or observed.get("target_region_id") != requirement.get("target_region_id")
        ):
            _record_failure(
                failures,
                "interaction_missing",
                f"production interaction result differs from prototype: {interaction_id}",
                unit_key=key,
            )
    return geometry_results


def _validate_computed_style_comparisons(
    value: Any,
    *,
    binding: dict[str, Any],
    unit_key: tuple[str, str, str],
    failures: list[dict[str, Any]],
) -> None:
    comparisons: dict[str, dict[str, Any]] = {}
    if isinstance(value, list):
        for comparison in value:
            if not isinstance(comparison, dict):
                continue
            region_id = comparison.get("region_id")
            if isinstance(region_id, str) and region_id not in comparisons:
                comparisons[region_id] = comparison
    for region_id in binding.get("region_ids") or []:
        comparison = comparisons.get(region_id)
        if comparison is None:
            _record_failure(
                failures,
                "computed_style_missing",
                f"computed-style comparison is missing: {region_id}",
                unit_key=unit_key,
                region_id=region_id,
            )
            continue
        prototype = comparison.get("prototype")
        production = comparison.get("production")
        if not isinstance(prototype, dict) or not prototype or not isinstance(production, dict):
            _record_failure(
                failures,
                "computed_style_missing",
                f"computed-style maps are invalid: {region_id}",
                unit_key=unit_key,
                region_id=region_id,
            )
        elif prototype != production:
            _record_failure(
                failures,
                "computed_style_mismatch",
                f"computed-style fingerprint differs from prototype: {region_id}",
                unit_key=unit_key,
                region_id=region_id,
            )


def _decode_png(
    project_root: str | Path,
    artifact_path: str,
    *,
    reuse_pixels_from: dict[str, Any] | None = None,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> dict[str, Any]:
    path = resolve_project_path(project_root, artifact_path, artifact_only=True)
    if path.stat().st_size > _MAX_PNG_FILE_BYTES:
        raise _PNGResourceLimitError("PNG file exceeds the decoder size limit")
    metadata = validate_png(project_root, artifact_path)
    if (
        expected_width is not None
        and expected_height is not None
        and (
            metadata["width"] != expected_width
            or metadata["height"] != expected_height
        )
    ):
        raise _PNGDimensionsMismatch(
            "production screenshot dimensions must match the prototype"
        )
    if metadata["width"] * metadata["height"] > _MAX_PNG_PIXELS:
        raise _PNGResourceLimitError("PNG pixel count exceeds the decoder limit")
    if (
        reuse_pixels_from is not None
        and metadata["sha256"] == reuse_pixels_from.get("sha256")
        and metadata["width"] == reuse_pixels_from.get("width")
        and metadata["height"] == reuse_pixels_from.get("height")
    ):
        return {**metadata, "pixels": reuse_pixels_from["pixels"]}
    data = path.read_bytes()
    offset = 8
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
        offset += length + 12
    if ihdr is None:
        raise ImplementationBaselineError("PNG IHDR is missing")
    width, height, bit_depth, color_type, compression, filter_method, interlace = ihdr
    if bit_depth != 8 or color_type not in {2, 6}:
        raise ImplementationBaselineError(
            "task conformance PNG must be 8-bit RGB or RGBA"
        )
    if compression != 0 or filter_method != 0 or interlace != 0:
        raise ImplementationBaselineError(
            "task conformance PNG must use standard compression/filtering and be non-interlaced"
        )
    channels = 3 if color_type == 2 else 4
    stride = width * channels
    expected_decoded_bytes = height * (stride + 1)
    if expected_decoded_bytes > _MAX_PNG_DECODED_BYTES:
        raise _PNGResourceLimitError(
            "PNG decoded data exceeds the decoder size limit"
        )
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(
            bytes(compressed),
            expected_decoded_bytes + 1,
        )
    except zlib.error as cause:
        raise ImplementationBaselineError("PNG IDAT stream is invalid") from cause
    if len(decoded) > expected_decoded_bytes or decoder.unconsumed_tail:
        raise _PNGResourceLimitError(
            "PNG decompressed data exceeds its declared dimensions"
        )
    if not decoder.eof or decoder.unused_data:
        raise ImplementationBaselineError("PNG IDAT stream is invalid")
    if len(decoded) != expected_decoded_bytes:
        raise ImplementationBaselineError("PNG decoded data length is invalid")

    previous = bytearray(stride)
    rgba = bytearray()
    cursor = 0
    for _ in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        if filter_type not in {0, 1, 2, 3, 4}:
            raise ImplementationBaselineError("PNG row filter is unsupported")
        filtered = decoded[cursor : cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(filtered):
            left = row[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            else:
                predictor = _paeth_predictor(left, above, upper_left)
            row[index] = (value + predictor) & 0xFF
        if channels == 4:
            rgba.extend(row)
        else:
            for pixel_offset in range(0, len(row), 3):
                rgba.extend(row[pixel_offset : pixel_offset + 3])
                rgba.append(255)
        previous = row
    return {
        **metadata,
        "pixels": bytes(rgba),
        "sha256": sha256_file(path),
    }


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _write_pixel_diff_artifact(
    project_root: str | Path,
    prototype: dict[str, Any],
    production: dict[str, Any],
) -> str:
    relative = (
        ".product-delivery/artifacts/task-conformance/"
        f"pixel-diff-{prototype['sha256'][:10]}-{production['sha256'][:10]}.png"
    )
    path = Path(project_root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    width = int(prototype["width"])
    height = int(prototype["height"])
    before = prototype["pixels"]
    after = production["pixels"]
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            index = (y * width + x) * 4
            changed = before[index : index + 4] != after[index : index + 4]
            rows.extend((255, 0, 0, 255) if changed else (0, 0, 0, 0))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
    )
    image += chunk(b"IDAT", zlib.compress(bytes(rows)))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)
    return relative


def _pixel_diff_ratio(
    prototype: dict[str, Any],
    production: dict[str, Any],
    *,
    threshold: float,
    include_box: dict[str, Any] | None = None,
    excluded_boxes: list[dict[str, Any]] | None = None,
) -> float:
    width = int(prototype["width"])
    height = int(prototype["height"])
    prototype_pixels = prototype["pixels"]
    production_pixels = production["pixels"]
    include = _integer_box(include_box, width, height) if include_box else (0, 0, width, height)
    excluded = [
        _integer_box(box, width, height)
        for box in (excluded_boxes or [])
        if isinstance(box, dict)
    ]
    different = total = 0
    start_x, start_y, end_x, end_y = include
    channel_limit = threshold * 255
    for y in range(start_y, end_y):
        for x in range(start_x, end_x):
            if any(left <= x < right and top <= y < bottom for left, top, right, bottom in excluded):
                continue
            total += 1
            offset = (y * width + x) * 4
            if any(
                abs(prototype_pixels[offset + channel] - production_pixels[offset + channel])
                > channel_limit
                for channel in range(4)
            ):
                different += 1
    return round(different / total, 10) if total else 0.0


def _integer_box(
    box: dict[str, Any] | None,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    value = box or {}
    left = max(0, min(width, math.floor(float(value.get("x", 0)))))
    top = max(0, min(height, math.floor(float(value.get("y", 0)))))
    right = max(left, min(width, math.ceil(float(value.get("x", 0)) + float(value.get("width", width)))))
    bottom = max(top, min(height, math.ceil(float(value.get("y", 0)) + float(value.get("height", height)))))
    return left, top, right, bottom


def _assess_geometry(
    prototype: Any,
    production: Any,
    viewport: dict[str, Any],
    visual_policy: dict[str, Any],
    *,
    visible: bool,
) -> dict[str, Any]:
    fixed = float(visual_policy.get("geometry_tolerance_px", 4))
    ratio = float(visual_policy.get("geometry_tolerance_viewport_ratio", 0.01))
    horizontal_tolerance = max(fixed, float(viewport["width"]) * ratio)
    vertical_tolerance = max(fixed, float(viewport["height"]) * ratio)
    tolerance = {
        "horizontal_px": horizontal_tolerance,
        "vertical_px": vertical_tolerance,
    }
    empty_overflow = {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}
    base = {
        "prototype_bounds": _normalized_geometry_box(prototype),
        "production_bounds": _normalized_geometry_box(production),
        "delta": {"x": None, "y": None, "width": None, "height": None},
        "tolerance": tolerance,
        "viewport_overflow": empty_overflow,
    }
    if not isinstance(prototype, dict) or any(
        value is None for value in base["prototype_bounds"].values()
    ):
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "prototype_bounds_invalid",
        }
    if not isinstance(production, dict):
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "bounds_missing",
        }
    raw_values = [production.get(field) for field in ("x", "y", "width", "height")]
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in raw_values
    ):
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "bounds_not_numeric",
        }
    if not all(math.isfinite(float(value)) for value in raw_values):
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "non_finite_bounds",
        }
    x, y, width, height = (float(value) for value in raw_values)
    if width <= 0 or height <= 0:
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "non_positive_size",
        }
    if not visible:
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "region_not_visible",
        }

    prototype_values = base["prototype_bounds"]
    delta = {
        field: float(production[field]) - float(prototype_values[field])
        for field in ("x", "y", "width", "height")
    }
    overflow = {
        "left": max(0.0, -x),
        "top": max(0.0, -y),
        "right": max(0.0, x + width - float(viewport["width"])),
        "bottom": max(0.0, y + height - float(viewport["height"])),
    }
    base = {**base, "delta": delta, "viewport_overflow": overflow}
    has_overflow = any(value > 0 for value in overflow.values())
    if has_overflow:
        intersects_viewport = bool(
            min(x + width, float(viewport["width"])) - max(x, 0.0) > 0
            and min(y + height, float(viewport["height"])) - max(y, 0.0) > 0
        )
        within_tolerance = bool(
            overflow["left"] <= horizontal_tolerance
            and overflow["right"] <= horizontal_tolerance
            and overflow["top"] <= vertical_tolerance
            and overflow["bottom"] <= vertical_tolerance
        )
        if intersects_viewport and within_tolerance:
            return {
                **base,
                "classification": "soft_invalid",
                "failure_class": VISUAL_ADJUDICABLE,
                "classification_reason": "viewport_boundary_overflow_within_tolerance",
            }
        return {
            **base,
            "classification": "hard_invalid",
            "failure_class": HARD_BLOCKING,
            "classification_reason": "outside_viewport_tolerance",
        }

    matches = bool(
        abs(delta["x"]) <= horizontal_tolerance
        and abs(delta["width"]) <= horizontal_tolerance
        and abs(delta["y"]) <= vertical_tolerance
        and abs(delta["height"]) <= vertical_tolerance
    )
    if matches:
        return {
            **base,
            "classification": "exact",
            "failure_class": None,
            "classification_reason": "within_geometry_tolerance",
        }
    return {
        **base,
        "classification": "mismatch",
        "failure_class": VISUAL_ADJUDICABLE,
        "classification_reason": "geometry_delta_exceeds_tolerance",
    }


def _normalized_geometry_box(value: Any) -> dict[str, float | None]:
    if not isinstance(value, dict):
        return {field: None for field in ("x", "y", "width", "height")}
    result: dict[str, float | None] = {}
    for field in ("x", "y", "width", "height"):
        item = value.get(field)
        result[field] = (
            float(item)
            if isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            else None
        )
    return result


def _accessible_name_matches(value: Any, matcher: dict[str, Any]) -> bool:
    if not isinstance(value, str):
        return False
    expected = str(matcher.get("value") or "")
    mode = matcher.get("mode")
    if mode == "role_only":
        return True
    if mode == "exact":
        return value.casefold() == expected.casefold()
    if mode == "contains":
        return expected.casefold() in value.casefold()
    return False


def _finish_task_conformance(
    *,
    baseline_hash: Any,
    planned_task: dict[str, Any],
    environment_status: str,
    environment_reason: Any,
    records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    forced_status: str | None = None,
) -> dict[str, Any]:
    visual_failures = [
        failure
        for failure in failures
        if failure.get("failure_class") == VISUAL_ADJUDICABLE
    ]
    hard_failures = [
        failure
        for failure in failures
        if failure.get("failure_class") == HARD_BLOCKING
    ]
    adjudication_eligibility = {
        "eligible": bool(
            environment_status == "stable" and visual_failures and not hard_failures
        ),
        "visual_failure_codes": _failure_codes(visual_failures),
        "hard_failure_codes": _failure_codes(hard_failures),
    }
    body = {
        "conformance_version": TASK_CONFORMANCE_VERSION,
        "implementation_baseline_sha256": baseline_hash,
        "task_id": planned_task.get("task_id"),
        "planned_task_hash": planned_task.get("planned_task_hash"),
        "environment_status": environment_status,
        "environment_reason": environment_reason,
        "records": records,
        "failures": failures,
        "failure_codes": _failure_codes(failures),
        "adjudication_eligibility": adjudication_eligibility,
    }
    status = forced_status or ("failed" if failures else "passed")
    return {
        **body,
        "status": status,
        "evidence_sha256": stable_json_hash(body),
    }


def _record_failure(
    failures: list[dict[str, Any]],
    code: str,
    message: str,
    *,
    unit_key: tuple[Any, Any, Any] | None = None,
    region_id: str | None = None,
    failure_class: str | None = None,
    classification_reason: str | None = None,
) -> None:
    resolved_class = failure_class or (
        VISUAL_ADJUDICABLE
        if code in VISUAL_ADJUDICABLE_FAILURE_CODES
        else HARD_BLOCKING
    )
    failure = {
        "code": code,
        "message": message,
        "failure_class": resolved_class,
        "classification_reason": classification_reason or code,
    }
    if unit_key is not None:
        failure["surface_id"] = unit_key[0]
        failure["state_id"] = unit_key[1]
        failure["viewport_class"] = unit_key[2]
    if region_id is not None:
        failure["region_id"] = region_id
    failures.append(failure)


def _failure_codes(failures: list[dict[str, Any]]) -> list[str]:
    result = []
    for failure in failures:
        code = str(failure.get("code") or "")
        if code and code not in result:
            result.append(code)
    return result


def _unit_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value.get("surface_id") or ""),
        str(value.get("state_id") or ""),
        str(value.get("viewport_class") or ""),
    )


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
