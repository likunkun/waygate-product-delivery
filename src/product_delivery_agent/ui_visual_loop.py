"""Development-time chrome comparison against a frozen prototype brief."""

from __future__ import annotations

import argparse
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from product_delivery_agent.evidence_artifacts import (
    EvidenceArtifactError,
    load_json_artifact,
    stable_json_hash,
    validate_png,
)
from product_delivery_agent.implementation_baseline import (
    TASK_SEMANTIC_SNAPSHOT_VERSION,
    _assess_geometry,
)

VISUAL_LOOP_POLICY_VERSION = "v1"
VISUAL_LOOP_PLAN_VERSION = "v1"
VISUAL_LOOP_EVIDENCE_VERSION = "v1"
DATA_ROLES = frozenset(
    {
        "table",
        "list",
        "grid",
        "chart",
        "metric",
        "collection",
        "status-value",
    }
)
CAPTURE_BACKED_STATE_KEYS = ("ui_capture_registry", "ui_evidence_policy")


class VisualLoopError(ValueError):
    """Raised when a development visual loop cannot be prepared or compared."""


def ui_visual_loop_required(state: dict[str, Any]) -> bool:
    """Return whether a new 1.0.42 UI delivery uses chrome visual loops."""
    policy = state.get("ui_visual_loop_policy") or {}
    return bool(
        state.get("project_type") == "ui"
        and policy.get("policy_version") == VISUAL_LOOP_POLICY_VERSION
        and policy.get("status") == "required"
        and policy.get("introduced_in") == "1.0.42"
    )


def default_ui_visual_loop_policy(*, status: str) -> dict[str, str]:
    return {
        "policy_version": VISUAL_LOOP_POLICY_VERSION,
        "status": status,
        "introduced_in": "1.0.42",
    }


def infer_content_kind(region: dict[str, Any]) -> str:
    explicit = region.get("content_kind")
    if explicit in {"chrome", "data"}:
        return str(explicit)
    role = str(region.get("semantic_role") or region.get("role") or "").lower()
    return "data" if role in DATA_ROLES else "chrome"


def build_visual_loop_plan(
    *,
    delivery_id: str,
    feature_slug: str,
    task_id: str,
    planned_task: dict[str, Any],
    implementation_baseline: dict[str, Any],
    surface_id: str,
    state_id: str,
    viewport_class: str,
    region_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build an immutable one-unit development comparison plan."""
    if planned_task.get("task_id") != task_id:
        raise VisualLoopError("visual loop task_id must match the planned task")
    if planned_task.get("ui_impact") != "prototype_bound":
        raise VisualLoopError("visual loop is only available for prototype-bound tasks")
    unit, binding = _bound_unit(
        implementation_baseline,
        planned_task,
        surface_id,
        state_id,
        viewport_class,
    )
    requested = list(binding["region_ids"] if region_ids is None else region_ids)
    if not requested:
        raise VisualLoopError("visual loop requires at least one bound region")
    unknown = [region_id for region_id in requested if region_id not in binding["region_ids"]]
    if unknown:
        raise VisualLoopError(
            "visual loop region_ids cannot expand beyond the task binding: "
            + ", ".join(unknown)
        )
    duplicate = sorted(
        {region_id for region_id in requested if requested.count(region_id) > 1}
    )
    if duplicate:
        raise VisualLoopError("visual loop region_ids must be unique")
    regions = []
    for region_id in requested:
        prototype = _prototype_region(unit, region_id)
        regions.append(
            {
                "region_id": region_id,
                "content_kind": infer_content_kind(prototype),
                "semantic_role": prototype.get("semantic_role"),
                "display_order": prototype.get("display_order"),
                "bounds": deepcopy(prototype.get("bounds")),
            }
        )
    plan = {
        "plan_version": VISUAL_LOOP_PLAN_VERSION,
        "plan_id": uuid.uuid4().hex,
        "delivery_id": delivery_id,
        "feature_slug": feature_slug,
        "task_id": task_id,
        "planned_task_hash": planned_task.get("planned_task_hash"),
        "implementation_baseline_sha256": implementation_baseline.get("baseline_sha256"),
        "surface_id": surface_id,
        "state_id": state_id,
        "viewport_class": viewport_class,
        "route": unit.get("route"),
        "prototype_screenshot_path": unit.get("prototype_screenshot_path"),
        "region_ids": requested,
        "regions": regions,
        "closure_valid": False,
    }
    plan["plan_sha256"] = stable_json_hash(
        {key: value for key, value in plan.items() if key != "plan_id"}
    )
    return plan


def compare_visual_loop(
    project_root: str | Path,
    plan: dict[str, Any],
    manifest: dict[str, Any],
    *,
    visual_policy: dict[str, Any],
) -> dict[str, Any]:
    """Compare one production unit to the prototype brief without pixel gates."""
    if plan.get("plan_version") != VISUAL_LOOP_PLAN_VERSION:
        raise VisualLoopError("visual loop plan_version must be v1")
    if manifest.get("plan_id") != plan.get("plan_id"):
        raise VisualLoopError("visual loop manifest plan_id does not match the prepared plan")
    screenshot_path = str(manifest.get("production_screenshot_path") or "")
    snapshot_path = str(manifest.get("semantic_snapshot_path") or "")
    try:
        screenshot = validate_png(project_root, screenshot_path)
        snapshot, snapshot_meta = load_json_artifact(project_root, snapshot_path)
    except (EvidenceArtifactError, OSError) as cause:
        raise VisualLoopError(str(cause)) from cause

    failures: list[dict[str, Any]] = []
    data_findings: list[dict[str, Any]] = []
    if snapshot.get("schema_version") != TASK_SEMANTIC_SNAPSHOT_VERSION:
        _note(
            failures,
            "semantic_snapshot_invalid",
            f"semantic snapshot schema must be {TASK_SEMANTIC_SNAPSHOT_VERSION}",
        )
    if (
        snapshot.get("surface_id") != plan.get("surface_id")
        or snapshot.get("state_id") != plan.get("state_id")
    ):
        _note(
            failures,
            "semantic_identity_mismatch",
            "semantic snapshot surface/state does not match the visual loop plan",
        )
    production_route = manifest.get("production_route") or snapshot.get("route")
    if production_route != plan.get("route"):
        _note(failures, "route_mismatch", "production route does not match the prototype route")

    viewport = snapshot.get("viewport") if isinstance(snapshot.get("viewport"), dict) else {}
    if viewport.get("class") != plan.get("viewport_class"):
        _note(
            failures,
            "viewport_mismatch",
            "semantic viewport class must match the bound viewport",
        )
    observed_regions = _observed_regions(snapshot, failures)
    region_results = []
    for expected in plan.get("regions") or []:
        region_id = expected["region_id"]
        observed = observed_regions.get(region_id)
        kind = expected.get("content_kind") or "chrome"
        if observed is None or observed.get("matched_count") != 1 or observed.get("visible") is not True:
            _note(
                failures,
                "region_missing",
                f"production semantic snapshot is missing region: {region_id}",
                region_id=region_id,
                content_kind=kind,
            )
            region_results.append(
                {
                    "region_id": region_id,
                    "content_kind": kind,
                    "status": "missing",
                }
            )
            continue
        expected_role = expected.get("semantic_role")
        if expected_role and observed.get("role") != expected_role:
            _note(
                failures,
                "region_semantics_mismatch",
                f"production region role differs from prototype: {region_id}",
                region_id=region_id,
                content_kind=kind,
            )
        expected_order = expected.get("display_order")
        if expected_order is not None and observed.get("display_order") != expected_order:
            _note(
                failures,
                "region_order_mismatch",
                f"production region order differs from prototype: {region_id}",
                region_id=region_id,
                content_kind=kind,
            )
        box = observed.get("bounding_box", observed.get("bounds"))
        geometry = _assess_geometry(
            expected.get("bounds"),
            box,
            {
                "width": viewport.get("width") or screenshot["width"],
                "height": viewport.get("height") or screenshot["height"],
            },
            visual_policy,
            visible=True,
        )
        if kind == "data":
            if geometry["classification"] in {"mismatch", "soft_invalid", "hard_invalid"}:
                data_findings.append(
                    {
                        "code": "data_geometry_changed",
                        "region_id": region_id,
                        "message": (
                            "data container size or position differs from the prototype brief"
                        ),
                        "geometry": geometry,
                    }
                )
            region_results.append(
                {
                    "region_id": region_id,
                    "content_kind": "data",
                    "status": "present",
                    "geometry": geometry,
                }
            )
            continue
        if geometry["classification"] in {"soft_invalid", "hard_invalid", "mismatch"}:
            _note(
                failures,
                "geometry_mismatch",
                f"chrome region geometry exceeds frozen tolerance: {region_id}",
                region_id=region_id,
                content_kind="chrome",
            )
        region_results.append(
            {
                "region_id": region_id,
                "content_kind": "chrome",
                "status": "compared",
                "geometry": geometry,
            }
        )

    pixel_diagnostic = _pixel_diagnostic(
        project_root,
        str(plan.get("prototype_screenshot_path") or ""),
        screenshot_path,
        screenshot,
    )
    if pixel_diagnostic.get("ratio") is not None and pixel_diagnostic["ratio"] > 0.02:
        data_findings.append(
            {
                "code": "pixel_diagnostic_above_legacy_threshold",
                "message": (
                    "prototype/production pixel difference exceeds the retired 2% "
                    "threshold; this is diagnostic only"
                ),
                "ratio": pixel_diagnostic["ratio"],
            }
        )

    next_fix = _rank_next_fix(failures, data_findings)
    status = "passed" if not failures else "failed"
    evidence = {
        "evidence_version": VISUAL_LOOP_EVIDENCE_VERSION,
        "plan_id": plan["plan_id"],
        "plan_sha256": plan.get("plan_sha256"),
        "task_id": plan.get("task_id"),
        "planned_task_hash": plan.get("planned_task_hash"),
        "implementation_baseline_sha256": plan.get("implementation_baseline_sha256"),
        "surface_id": plan.get("surface_id"),
        "state_id": plan.get("state_id"),
        "viewport_class": plan.get("viewport_class"),
        "status": status,
        "closure_valid": False,
        "production_screenshot_path": screenshot_path,
        "production_screenshot_sha256": screenshot["sha256"],
        "semantic_snapshot_path": snapshot_path,
        "semantic_snapshot_sha256": snapshot_meta["sha256"],
        "region_results": region_results,
        "failure_codes": [item["code"] for item in failures],
        "failures": failures,
        "data_findings": data_findings,
        "next_fix": next_fix,
        "pixel_diagnostic": pixel_diagnostic,
    }
    evidence["evidence_sha256"] = stable_json_hash(evidence)
    return evidence


def validate_task_visual_loop_records(
    state: dict[str, Any],
    planned_task: dict[str, Any],
) -> None:
    """Require a passed chrome loop for every bound unit of the current task."""
    if not (
        ui_visual_loop_required(state)
        and planned_task.get("ui_impact") == "prototype_bound"
    ):
        return
    baseline = state.get("implementation_baseline") or {}
    records = ((state.get("ui_visual_loop") or {}).get("records") or {}).get(
        planned_task.get("task_id")
    )
    if not isinstance(records, dict):
        raise VisualLoopError(
            "passed visual loop records are required before TASK completion"
        )
    expected_keys = []
    for binding in planned_task.get("prototype_bindings") or []:
        for viewport in binding.get("viewport_classes") or []:
            expected_keys.append(
                _unit_key(binding.get("surface_id"), binding.get("state_id"), viewport)
            )
    for key in expected_keys:
        record = records.get(key)
        if not isinstance(record, dict) or record.get("status") != "passed":
            raise VisualLoopError(
                f"passed visual loop is required for bound unit {key} before TASK completion"
            )
        if record.get("implementation_baseline_sha256") != baseline.get("baseline_sha256"):
            raise VisualLoopError(
                "visual loop does not match the current implementation baseline"
            )
        if record.get("planned_task_hash") != planned_task.get("planned_task_hash"):
            raise VisualLoopError("visual loop does not match the current planned task")
        if record.get("closure_valid") is True:
            raise VisualLoopError("visual loop evidence cannot be closure-valid")


def assert_no_capture_backed_delivery(project_root: str | Path) -> None:
    """Refuse to install 1.0.42 over a capture-registry delivery."""
    root = Path(project_root)
    candidates = [
        root / ".product-delivery" / "state.json",
        root / ".product-delivery" / "current.json",
    ]
    current = root / ".product-delivery" / "current.json"
    if current.is_file():
        try:
            pointer = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pointer = {}
        if isinstance(pointer, dict):
            for key in ("state_path", "canonical_state_path"):
                value = pointer.get(key)
                if isinstance(value, str) and value:
                    candidates.append(root / value)
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as cause:
            raise VisualLoopError(
                f"cannot read delivery state at {path}: {cause}"
            ) from cause
        if not isinstance(payload, dict):
            continue
        present = [key for key in CAPTURE_BACKED_STATE_KEYS if payload.get(key)]
        nested = payload.get("current") if isinstance(payload.get("current"), dict) else {}
        present.extend(key for key in CAPTURE_BACKED_STATE_KEYS if nested.get(key))
        if present:
            raise VisualLoopError(
                "1.0.42 refuses capture-backed active deliveries; finish or abandon "
                "with the original runtime before installing"
            )


def run_compare_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare one production unit to a prototype visual-loop plan."
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    root = Path(args.project_root)
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        evidence = compare_visual_loop(
            root,
            plan,
            manifest,
            visual_policy=plan.get("visual_policy")
            or {
                "geometry_tolerance_px": 4,
                "geometry_tolerance_viewport_ratio": 0.01,
            },
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, VisualLoopError) as cause:
        print(json.dumps({"status": "error", "error": str(cause)}, indent=2))
        return 2
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "passed" else 1


def _bound_unit(
    baseline: dict[str, Any],
    planned_task: dict[str, Any],
    surface_id: str,
    state_id: str,
    viewport_class: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    units = {
        _unit_key(unit.get("surface_id"), unit.get("state_id"), unit.get("viewport_class")): unit
        for unit in baseline.get("units") or []
        if isinstance(unit, dict)
    }
    key = _unit_key(surface_id, state_id, viewport_class)
    unit = units.get(key)
    if unit is None:
        raise VisualLoopError(f"visual loop references unknown baseline unit: {key}")
    for binding in planned_task.get("prototype_bindings") or []:
        if not isinstance(binding, dict):
            continue
        if binding.get("surface_id") != surface_id or binding.get("state_id") != state_id:
            continue
        if viewport_class in (binding.get("viewport_classes") or []):
            return unit, binding
    raise VisualLoopError(f"visual loop unit is not bound to the current task: {key}")


def _prototype_region(unit: dict[str, Any], region_id: str) -> dict[str, Any]:
    for collection_name in ("prototype_regions", "critical_regions"):
        for region in unit.get(collection_name) or []:
            if isinstance(region, dict) and region.get("region_id") == region_id:
                return region
    raise VisualLoopError(f"prototype region is missing from baseline: {region_id}")


def _observed_regions(
    snapshot: dict[str, Any],
    failures: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw = snapshot.get("regions")
    observed: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, list):
        _note(failures, "semantic_snapshot_invalid", "semantic snapshot regions must be a list")
        return observed
    for region in raw:
        if not isinstance(region, dict) or not isinstance(region.get("region_id"), str):
            continue
        region_id = region["region_id"]
        if region_id in observed:
            _note(
                failures,
                "semantic_snapshot_invalid",
                f"semantic region is duplicated: {region_id}",
                region_id=region_id,
            )
            continue
        observed[region_id] = region
    return observed


def _pixel_diagnostic(
    project_root: str | Path,
    prototype_path: str,
    production_path: str,
    production_meta: dict[str, Any],
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "compared": False,
        "ratio": None,
        "prototype_sha256": None,
        "production_sha256": production_meta.get("sha256"),
    }
    if not prototype_path:
        return diagnostic
    try:
        prototype_meta = validate_png(project_root, prototype_path, artifact_only=False)
    except (EvidenceArtifactError, OSError):
        return diagnostic
    diagnostic["prototype_sha256"] = prototype_meta["sha256"]
    if (
        prototype_meta["width"] != production_meta["width"]
        or prototype_meta["height"] != production_meta["height"]
    ):
        diagnostic["note"] = "screenshot dimensions differ; pixel ratio is not compared"
        return diagnostic
    diagnostic["compared"] = True
    diagnostic["ratio"] = 1.0 if prototype_meta["sha256"] != production_meta["sha256"] else 0.0
    return diagnostic


def _rank_next_fix(
    failures: list[dict[str, Any]],
    data_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ranked = []
    priority = {
        "region_missing": 0,
        "region_semantics_mismatch": 1,
        "region_order_mismatch": 2,
        "geometry_mismatch": 3,
        "route_mismatch": 4,
        "viewport_mismatch": 5,
    }
    for item in sorted(failures, key=lambda row: priority.get(row["code"], 9)):
        ranked.append(
            {
                "kind": "chrome_fix",
                "code": item["code"],
                "region_id": item.get("region_id"),
                "message": item["message"],
            }
        )
    for item in data_findings:
        ranked.append(
            {
                "kind": "data_finding",
                "code": item["code"],
                "region_id": item.get("region_id"),
                "message": item["message"],
            }
        )
    return ranked


def _note(
    bucket: list[dict[str, Any]],
    code: str,
    message: str,
    **extra: Any,
) -> None:
    record = {"code": code, "message": message}
    record.update({key: value for key, value in extra.items() if value is not None})
    bucket.append(record)


def _unit_key(surface_id: Any, state_id: Any, viewport_class: Any) -> str:
    return f"{surface_id}::{state_id}::{viewport_class}"
