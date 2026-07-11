"""Test coverage audit validation and rendering."""

from __future__ import annotations

import hashlib
import json
import re
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


class CoverageAuditError(RuntimeError):
    """Raised when the coverage audit cannot pass."""


REQUIRED_TRACE_FIELDS = (
    "fr",
    "nfr",
    "us",
    "journey",
    "acceptance_criteria",
    "task",
)

REQUIRED_ROW_FIELDS = (
    "tc_id",
    "test_layer",
    "evidence_type",
    "coverage_status",
    "exemption_status",
    "obligation_ref",
)

UI_BROWSER_E2E_LAYERS = {"browser_e2e"}
NON_UI_BEHAVIOR_EVIDENCE_LAYERS = {"api_e2e", "service_e2e", "cli_e2e"}
NON_UI_PLANNED_EVIDENCE_LAYERS = {
    "unit",
    "runtime_integration",
    "gatekeeper",
    "packaging_smoke",
    "static_contract",
    "release_gate",
    "api_e2e",
    "service_e2e",
    "cli_e2e",
}

REQUIRED_PLANNED_OBLIGATION_FIELDS = (
    "obligation_id",
    "scenario_id",
    "test_id",
    "user_story",
    "journey",
    "visible_exception",
    "test_layer",
    "semantic_assertions",
    "expected_artifact_pattern",
    "exemption_status",
)
REQUIRED_ACTION_ASSERTION_FIELDS = (
    "item_id",
    "action_entry",
    "expected_real_surface",
    "assertion_target",
    "semantic_depth",
)
REQUIRED_UI_PLANNED_OBLIGATION_FIELDS = (
    "required_actor_roles",
    "path_kind",
    "ordinary_entry_path",
    "data_state_contract",
)
ACCEPTED_UI_PATH_KINDS = {
    "primary_happy_path",
    "visible_exception",
    "permission_denial",
    "negative_scope_guard",
    "responsive_accessibility",
    "business_api_probe",
}
INDEPENDENT_SEGMENT_PATH_KINDS = {
    "primary_happy_path",
    "visible_exception",
    "permission_denial",
}
GENERIC_ACTOR_ROLES = {
    "actor",
    "allowed_role",
    "allowed_roles",
    "allowed role",
    "allowed roles",
    "all",
    "any",
    "user",
    "users",
    "admin_or_teacher",
    "teacher_or_admin",
    "admin/teacher",
    "teacher/admin",
}
ACCEPTED_SEMANTIC_DEPTHS = {
    "real_surface",
    "real_behavior",
    "functional_panel",
    "user_journey",
}
FALSE_POSITIVE_SEMANTIC_DEPTHS = {
    "marker_only",
    "function_name_only",
    "static_panel_only",
    "first_button_only",
}
FALSE_POSITIVE_TEXT_TERMS = {
    "marker exists",
    "function name",
    "function-name",
    "static explanation",
    "static panel",
    "static-only",
    "first visible button",
    "first button",
}

REQUIRED_EXEMPTION_FIELDS = (
    "exemption_id",
    "object_id",
    "exemption_type",
    "reason",
    "risk_impact",
    "alternative_evidence",
    "approved_by",
    "approval_source",
    "approved_at",
    "valid_scope",
)

REQUIRED_BROWSER_EVIDENCE_FIELDS = (
    "test_id",
    "obligation_id",
    "command",
    "exit_code",
    "trace_path",
    "screenshot_path",
    "console_errors",
    "network_errors",
    "semantic_assertions",
    "evidence_path",
    "evidence_strength",
    "acceptance_url",
    "api_health_url",
    "api_health_identity",
    "network_probe_summary",
    "mocked_routes",
    "probe_artifact_path",
    "executed_actor_roles",
    "primary_actor_role",
    "actor_identity_evidence",
    "ordinary_path_observed",
    "execution_segment_id",
    "test_title_or_step",
)

FULL_STACK_BROWSER_E2E = "full_stack_browser_e2e"
MOCKED_API_BROWSER_E2E = "mocked_api_browser_e2e"
STATIC_OR_PROTOTYPE_BROWSER_CHECK = "static_or_prototype_browser_check"
ACCEPTED_BROWSER_EVIDENCE_STRENGTHS = {
    FULL_STACK_BROWSER_E2E,
    MOCKED_API_BROWSER_E2E,
    STATIC_OR_PROTOTYPE_BROWSER_CHECK,
}
SEMANTIC_SURFACE_SCHEMA_VERSION = "ui-semantic-surface-v1"


def build_prototype_production_conformance(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    canonical_prototype: dict[str, Any],
    prototype_contract: dict[str, Any],
    executed_browser_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Validate production UI observations against the confirmed contract."""
    canonical_revision = canonical_prototype.get("prototype_revision")
    if payload.get("prototype_revision") != canonical_revision:
        raise CoverageAuditError("production evidence must match canonical prototype revision")
    contract_hash = prototype_contract.get("contract_sha256")
    if not contract_hash or payload.get("prototype_contract_hash") != contract_hash:
        raise CoverageAuditError("production evidence must match canonical prototype contract")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise CoverageAuditError("prototype production conformance requires records")

    browser_records = executed_browser_evidence.get("records") or []
    browser_segments = {
        (record.get("acceptance_url"), record.get("execution_segment_id"))
        for record in browser_records
        if record.get("evidence_strength") == FULL_STACK_BROWSER_E2E
    }
    surfaces = prototype_contract.get("surfaces") or []
    required_by_key = {
        (surface.get("surface_id"), surface.get("state_id"), viewport): surface
        for surface in surfaces
        for viewport in surface.get("required_viewports", [])
    }
    records_by_key: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    hydrated: list[dict[str, Any]] = []
    screenshot_hashes: dict[str, tuple[Any, Any, Any]] = {}

    for index, record in enumerate(records, start=1):
        key = (
            record.get("surface_id"),
            record.get("state_id"),
            record.get("viewport_class"),
        )
        surface = required_by_key.get(key)
        if not surface:
            raise CoverageAuditError(f"conformance record {index} is not in prototype contract")
        if key in records_by_key:
            raise CoverageAuditError(f"duplicate conformance record: {key}")
        if (record.get("acceptance_url"), record.get("execution_segment_id")) not in browser_segments:
            raise CoverageAuditError(
                f"conformance record {index} must bind current full-stack execution segment"
            )
        if record.get("production_route") != surface.get("route"):
            raise CoverageAuditError(
                f"conformance record {index} production route must match prototype contract"
            )
        try:
            screenshot = validate_png(
                project_root,
                record.get("production_screenshot_path", ""),
            )
            snapshot, snapshot_metadata = load_json_artifact(
                project_root,
                record.get("semantic_snapshot_path", ""),
            )
        except EvidenceArtifactError as cause:
            raise CoverageAuditError(str(cause)) from cause
        if screenshot["sha256"] in screenshot_hashes:
            raise CoverageAuditError("different visual states cannot reuse the same PNG capture")
        screenshot_hashes[screenshot["sha256"]] = key
        _validate_semantic_surface_snapshot(index, record, surface, snapshot, screenshot)
        _validate_conformance_results(index, surface, record)

        raw_component_refs = record.get("production_component_refs")
        if not isinstance(raw_component_refs, list) or not raw_component_refs:
            raise CoverageAuditError(
                f"conformance record {index} requires production component refs"
            )
        component_refs = []
        for component in raw_component_refs:
            if (
                not isinstance(component, dict)
                or not component.get("path")
                or not component.get("kind")
                or not component.get("note")
            ):
                raise CoverageAuditError(f"conformance record {index} has invalid component ref")
            try:
                component_path = resolve_project_path(project_root, component["path"])
            except EvidenceArtifactError as cause:
                raise CoverageAuditError(str(cause)) from cause
            component_refs.append({**component, "sha256": sha256_file(component_path)})

        next_record = {
            **record,
            "production_screenshot": screenshot,
            "semantic_snapshot_sha256": snapshot_metadata["sha256"],
            "production_component_refs": component_refs,
        }
        records_by_key[key] = next_record
        hydrated.append(next_record)

    missing_keys = sorted(set(required_by_key) - set(records_by_key))
    if missing_keys:
        raise CoverageAuditError(
            "prototype production conformance missing surface states: "
            + ", ".join(map(str, missing_keys))
        )
    covered_regions = sorted(
        {
            region["region_id"]
            for surface in surfaces
            for region in surface.get("critical_regions", [])
        }
    )
    evidence_body = {
        "prototype_revision": canonical_revision,
        "prototype_sha256": canonical_prototype.get("artifact_hash"),
        "prototype_contract_hash": contract_hash,
        "covered_surface_ids": sorted({surface["surface_id"] for surface in surfaces}),
        "covered_state_ids": sorted({surface["state_id"] for surface in surfaces}),
        "covered_region_ids": covered_regions,
        "records": hydrated,
    }
    return {
        **evidence_body,
        "status": "passed",
        "evidence_sha256": stable_json_hash(evidence_body),
    }


def _validate_semantic_surface_snapshot(
    index: int,
    record: dict[str, Any],
    surface: dict[str, Any],
    snapshot: dict[str, Any],
    screenshot: dict[str, Any],
) -> None:
    if snapshot.get("schema_version") != SEMANTIC_SURFACE_SCHEMA_VERSION:
        raise CoverageAuditError(f"conformance record {index} semantic snapshot schema is invalid")
    if snapshot.get("acceptance_url") != record.get("acceptance_url"):
        raise CoverageAuditError(f"conformance record {index} semantic acceptance URL mismatch")
    if snapshot.get("execution_segment_id") != record.get("execution_segment_id"):
        raise CoverageAuditError(f"conformance record {index} semantic execution segment mismatch")
    viewport = snapshot.get("viewport") or {}
    if viewport.get("class") != record.get("viewport_class"):
        raise CoverageAuditError(f"conformance record {index} viewport class mismatch")
    if viewport.get("width") != screenshot["width"] or viewport.get("height") != screenshot["height"]:
        raise CoverageAuditError(f"conformance record {index} PNG dimensions mismatch viewport")
    region_records = snapshot.get("regions")
    if not isinstance(region_records, list):
        raise CoverageAuditError(f"conformance record {index} semantic regions are invalid")
    snapshot_regions: dict[str, dict[str, Any]] = {}
    for region in region_records:
        if not isinstance(region, dict) or not _valid_semantic_region(region, viewport):
            raise CoverageAuditError(
                f"conformance record {index} semantic region schema is invalid"
            )
        region_id = region["region_id"]
        if region_id in snapshot_regions:
            raise CoverageAuditError(
                f"conformance record {index} semantic region id is duplicated"
            )
        snapshot_regions[region_id] = region

    required_regions = {region["region_id"]: region for region in surface["critical_regions"]}
    if set(required_regions) - set(snapshot_regions):
        raise CoverageAuditError(
            f"conformance record {index} semantic snapshot missing regions: "
            + ", ".join(sorted(set(required_regions) - set(snapshot_regions)))
        )
    for region_id, requirement in required_regions.items():
        observed = snapshot_regions[region_id]
        if observed.get("matched_count") != 1 or observed.get("visible") is not True:
            raise CoverageAuditError(
                f"conformance record {index} semantic region is not uniquely visible: {region_id}"
            )
        if observed.get("role") != requirement.get("semantic_role"):
            raise CoverageAuditError(
                f"conformance record {index} semantic role mismatch: {region_id}"
            )
        if not _accessible_name_matches(
            observed.get("accessible_name"),
            requirement.get("accessible_name_match") or {},
        ):
            raise CoverageAuditError(
                f"conformance record {index} accessible name mismatch: {region_id}"
            )
        if "parent_region_id" in requirement and observed.get(
            "parent_region_id"
        ) != requirement.get("parent_region_id"):
            raise CoverageAuditError(
                f"conformance record {index} parent region mismatch: {region_id}"
            )
        if "display_order" in requirement and observed.get(
            "display_order"
        ) != requirement.get("display_order"):
            raise CoverageAuditError(
                f"conformance record {index} display order mismatch: {region_id}"
            )

    required_relationships = {
        (item["source_region_id"], item["relation"], item["target_region_id"])
        for item in surface["critical_relationships"]
    }
    observed_relationships = {
        (item.get("source_region_id"), item.get("relation"), item.get("target_region_id"))
        for item in snapshot.get("relationships", [])
        if isinstance(item, dict) and item.get("observed") is True
    }
    if required_relationships - observed_relationships:
        raise CoverageAuditError(
            f"conformance record {index} semantic relationships are incomplete"
        )
    required_interactions = {
        item["interaction_id"] for item in surface["critical_interactions"]
    }
    observed_interactions = {
        item.get("interaction_id")
        for item in snapshot.get("interactions", [])
        if isinstance(item, dict)
        and item.get("observed") is True
        and isinstance(item.get("result"), str)
        and item.get("result").strip()
    }
    if required_interactions - observed_interactions:
        raise CoverageAuditError(
            f"conformance record {index} semantic interactions are incomplete"
        )


def _valid_semantic_region(
    region: dict[str, Any],
    viewport: dict[str, Any],
) -> bool:
    required = (
        "region_id",
        "matched_count",
        "visible",
        "role",
        "accessible_name",
        "parent_region_id",
        "display_order",
        "bounding_box",
        "key_controls",
        "interaction_state",
    )
    if any(field not in region for field in required):
        return False
    if not isinstance(region.get("region_id"), str) or not region["region_id"].strip():
        return False
    if not isinstance(region.get("matched_count"), int) or isinstance(
        region.get("matched_count"), bool
    ):
        return False
    if not isinstance(region.get("visible"), bool):
        return False
    if not isinstance(region.get("role"), str) or not region["role"].strip():
        return False
    if not isinstance(region.get("accessible_name"), str):
        return False
    if region.get("parent_region_id") is not None and not isinstance(
        region.get("parent_region_id"), str
    ):
        return False
    if not isinstance(region.get("display_order"), int) or isinstance(
        region.get("display_order"), bool
    ):
        return False
    if not isinstance(region.get("key_controls"), list) or not all(
        isinstance(item, str) and item.strip() for item in region["key_controls"]
    ):
        return False
    if not isinstance(region.get("interaction_state"), str) or not region[
        "interaction_state"
    ].strip():
        return False
    box = region.get("bounding_box")
    if not isinstance(box, dict):
        return False
    values = [box.get(name) for name in ("x", "y", "width", "height")]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        return False
    x, y, width, height = values
    return bool(
        x >= 0
        and y >= 0
        and width > 0
        and height > 0
        and x + width <= viewport.get("width", -1)
        and y + height <= viewport.get("height", -1)
    )


def _accessible_name_matches(value: Any, matcher: dict[str, Any]) -> bool:
    if not isinstance(value, str):
        return False
    mode = matcher.get("mode")
    expected = str(matcher.get("value") or "")
    if mode == "role_only":
        return True
    if mode == "exact":
        return value == expected
    if mode == "contains":
        return expected in value
    return False


def _validate_conformance_results(
    index: int,
    surface: dict[str, Any],
    record: dict[str, Any],
) -> None:
    required_regions = {region["region_id"] for region in surface["critical_regions"]}
    observed_regions = {
        result.get("region_id")
        for result in record.get("region_results", [])
        if isinstance(result, dict) and result.get("observed") is True
    }
    if required_regions - observed_regions:
        raise CoverageAuditError(f"conformance record {index} missing region results")
    required_relationships = {
        (
            item["source_region_id"],
            item["relation"],
            item["target_region_id"],
        )
        for item in surface["critical_relationships"]
    }
    observed_relationships = {
        (
            item.get("source_region_id"),
            item.get("relation"),
            item.get("target_region_id"),
        )
        for item in record.get("relationship_results", [])
        if isinstance(item, dict) and item.get("observed") is True
    }
    if required_relationships - observed_relationships:
        raise CoverageAuditError(f"conformance record {index} missing relationship results")
    required_interactions = {
        item["interaction_id"] for item in surface["critical_interactions"]
    }
    observed_interactions = {
        item.get("interaction_id")
        for item in record.get("interaction_results", [])
        if isinstance(item, dict) and item.get("observed") is True
    }
    if required_interactions - observed_interactions:
        raise CoverageAuditError(f"conformance record {index} missing interaction results")


def build_coverage_audit(
    *,
    project_type: str,
    rows: list[dict[str, Any]],
    downstream_inputs: dict[str, list[str]] | None = None,
    inherited_limitations: list[str] | None = None,
    negative_guard_records: list[str] | None = None,
) -> dict[str, Any]:
    """Validate coverage rows and return a closure-ready audit record."""
    if project_type not in {"ui", "non_ui"}:
        raise CoverageAuditError("project_type must be selected before audit")
    if not rows:
        raise CoverageAuditError("coverage matrix requires at least one row")

    downstream = downstream_inputs or {}
    guards = list(negative_guard_records or [])
    _validate_required_fields(rows)
    tc_numbers = _validate_continuous_tc_range(rows)
    _validate_trace_anchors(rows)
    _validate_semantic_markers(rows)
    _validate_critical_gaps(rows)
    _validate_project_evidence(project_type, rows, downstream)
    _validate_negative_guards(project_type, downstream, guards)

    matrix_range = f"TC-V008-{tc_numbers[0]:03d}..TC-V008-{tc_numbers[-1]:03d}"
    latest_test_case = f"TC-V008-{tc_numbers[-1]:03d}"
    audit = {
        "passed": True,
        "matrix_range": matrix_range,
        "latest_test_case": latest_test_case,
        "coverage_status": "passed",
        "rows": [dict(row) for row in rows],
        "inherited_limitations": list(inherited_limitations or []),
        "negative_guard_records": guards,
        "browser_e2e_obligations": list(
            downstream.get("browser_e2e_candidates", [])
        ),
        "behavior_evidence_obligations": list(
            downstream.get("behavior_evidence_candidates", [])
        ),
    }
    return audit


def render_coverage_audit(audit: dict[str, Any]) -> str:
    """Render the coverage audit as a Markdown artifact."""
    lines = [
        "# Test Coverage Audit",
        "",
        "Status: Passed",
        "",
        f"Matrix Range: {audit['matrix_range']}",
        f"Latest Test Case: {audit['latest_test_case']}",
        "",
        "## Coverage Matrix",
        "",
        "| TC | Layer | Evidence | Marker | Status | Exemption | Obligation |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in audit["rows"]:
        lines.append(
            "| {tc_id} | {test_layer} | {evidence_type} | {semantic_marker} | "
            "{coverage_status} | {exemption_status} | {obligation_ref} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Inherited Limitations",
            *_bullets(audit["inherited_limitations"]),
            "",
            "## Negative Guard Records",
            *_bullets(audit["negative_guard_records"]),
            "",
        ]
    )
    return "\n".join(lines)


def build_planned_e2e_obligations(
    obligations: list[dict[str, Any]],
    exemptions: list[dict[str, Any]] | None = None,
    *,
    project_type: str = "ui",
) -> dict[str, Any]:
    """Validate implementation-prep E2E obligations without requiring evidence."""
    if not obligations:
        raise CoverageAuditError("planned E2E obligations require at least one row")
    exemption_records = list(exemptions or [])
    _validate_planned_obligations(obligations, project_type=project_type)
    _validate_structured_exemptions(exemption_records)
    exempted_ids = {record["object_id"] for record in exemption_records}
    for obligation in obligations:
        if obligation["exemption_status"] not in {"none", "approved"}:
            raise CoverageAuditError("exemption_status must be none or approved")
        if (
            obligation["exemption_status"] == "approved"
            and obligation["scenario_id"] not in exempted_ids
        ):
            raise CoverageAuditError(
                "approved exemption missing for scenario_id: "
                + obligation["scenario_id"]
            )
    return {
        "accepted": True,
        "accepted_by_user": False,
        "obligations": [dict(row) for row in obligations],
        "exemptions": exemption_records,
    }


def build_executed_browser_evidence(
    project_root: str | Path,
    records: list[dict[str, Any]],
    *,
    planned_obligations: list[dict[str, Any]] | None = None,
    exemptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate executed browser evidence and attach content hashes."""
    if not records:
        raise CoverageAuditError("executed browser evidence requires records")
    planned_by_key = _planned_obligations_by_key(
        planned_obligations or [],
        exemptions or [],
    )
    if planned_by_key:
        _validate_executed_records_cover_planned(records, planned_by_key)
    root = Path(project_root)
    hydrated = []
    for index, record in enumerate(records, start=1):
        probe = _validate_browser_evidence_record(root, index, record)
        evidence_path = root / record["evidence_path"]
        if not evidence_path.is_file():
            raise CoverageAuditError(
                f"evidence_path does not exist: {record['evidence_path']}"
            )
        probe_path = root / record["probe_artifact_path"]
        next_record = dict(record)
        next_record["evidence_sha256"] = _sha256(evidence_path)
        next_record["probe_artifact_sha256"] = _sha256(probe_path)
        next_record["probe_artifact_summary"] = {
            "acceptance_url": probe.get("acceptance_url"),
            "api_health_url": probe.get("api_health_url"),
            "api_health_identity": probe.get("api_health_identity"),
            "business_api_request_count": len(probe.get("business_api_requests") or []),
        }
        planned = planned_by_key.get(
            (record.get("obligation_id"), record.get("test_id"))
        )
        if planned:
            next_record["scenario_id"] = planned["scenario_id"]
            next_record["user_story"] = planned["user_story"]
            next_record["journey"] = planned["journey"]
        hydrated.append(next_record)
    return {
        "status": "passed",
        "records": hydrated,
    }


def _validate_required_fields(rows: list[dict[str, Any]]) -> None:
    missing = []
    for index, row in enumerate(rows, start=1):
        for field_name in REQUIRED_ROW_FIELDS:
            if not _has_value(row.get(field_name)):
                missing.append(f"row {index} missing {field_name}")
    if missing:
        raise CoverageAuditError("missing coverage fields: " + ", ".join(missing))


def _validate_continuous_tc_range(rows: list[dict[str, Any]]) -> list[int]:
    numbers = []
    for row in rows:
        match = re.fullmatch(r"TC-V008-(\d{3})", str(row.get("tc_id", "")))
        if not match:
            raise CoverageAuditError(f"invalid TC identifier: {row.get('tc_id')}")
        numbers.append(int(match.group(1)))

    expected = list(range(min(numbers), max(numbers) + 1))
    if sorted(numbers) != expected or min(numbers) != 1:
        raise CoverageAuditError("coverage matrix must use a continuous TC range")
    return expected


def _validate_trace_anchors(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for field_name in REQUIRED_TRACE_FIELDS:
            if not _has_value(row.get(field_name)):
                raise CoverageAuditError(
                    f"missing trace anchor {field_name} for {row.get('tc_id')}"
                )


def _validate_semantic_markers(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if _is_critical(row) and not _has_value(row.get("semantic_marker")):
            raise CoverageAuditError(
                f"missing semantic marker for {row.get('tc_id')}"
            )


def _validate_critical_gaps(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if (
            _is_critical(row)
            and row.get("coverage_status") == "missing"
            and row.get("exemption_status") in {"", None, "none"}
        ):
            raise CoverageAuditError(
                f"unexempted critical coverage gap for {row.get('tc_id')}"
            )


def _validate_project_evidence(
    project_type: str,
    rows: list[dict[str, Any]],
    downstream: dict[str, list[str]],
) -> None:
    if project_type == "ui":
        for obligation in downstream.get("browser_e2e_candidates", []):
            matching = [row for row in rows if row["obligation_ref"] == obligation]
            if not any(
                row["test_layer"] in UI_BROWSER_E2E_LAYERS
                and row["evidence_type"] == "browser_e2e"
                and _covered_or_exempted(row)
                for row in matching
            ):
                raise CoverageAuditError(
                    f"missing browser E2E for UI obligation: {obligation}"
                )
    else:
        for obligation in downstream.get("behavior_evidence_candidates", []):
            matching = [row for row in rows if row["obligation_ref"] == obligation]
            if not any(
                row["test_layer"] in NON_UI_BEHAVIOR_EVIDENCE_LAYERS
                and row["evidence_type"] == "behavior_evidence"
                and _covered_or_exempted(row)
                for row in matching
            ):
                raise CoverageAuditError(
                    "missing API/service/CLI behavior evidence for obligation: "
                    + obligation
                )


def _validate_negative_guards(
    project_type: str,
    downstream: dict[str, list[str]],
    guard_records: list[str],
) -> None:
    key = (
        "negative_scope_guard_candidates"
        if project_type == "ui"
        else "negative_boundary_candidates"
    )
    missing = [
        candidate
        for candidate in downstream.get(key, [])
        if candidate not in guard_records
    ]
    if missing:
        raise CoverageAuditError(
            "missing inherited negative guard records: " + ", ".join(missing)
        )


def _covered_or_exempted(row: dict[str, Any]) -> bool:
    return row["coverage_status"] == "covered" or row["exemption_status"] not in {
        "",
        None,
        "none",
    }


def _is_critical(row: dict[str, Any]) -> bool:
    return bool(row.get("critical", True))


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_planned_obligations(
    obligations: list[dict[str, Any]],
    *,
    project_type: str,
) -> None:
    if project_type not in {"ui", "non_ui"}:
        raise CoverageAuditError("project_type must be ui or non_ui")
    for index, obligation in enumerate(obligations, start=1):
        missing = []
        for field_name in REQUIRED_PLANNED_OBLIGATION_FIELDS:
            value = obligation.get(field_name)
            if field_name == "semantic_assertions":
                if not _has_list_values(value):
                    missing.append(field_name)
            elif not _has_value(value):
                missing.append(field_name)
        if missing:
            raise CoverageAuditError(
                f"planned obligation row {index} missing fields: "
                + ", ".join(missing)
            )
        test_layer = obligation["test_layer"]
        if project_type == "ui" and test_layer != "browser_e2e":
            raise CoverageAuditError("UI planned obligation must target browser_e2e")
        if project_type == "ui" and not _has_value(
            obligation.get("baseline_entry_path")
        ):
            raise CoverageAuditError(
                f"planned obligation row {index} missing fields: baseline_entry_path"
            )
        if project_type == "ui":
            _validate_ui_planned_obligation(index, obligation)
        if project_type == "non_ui" and test_layer not in NON_UI_PLANNED_EVIDENCE_LAYERS:
            raise CoverageAuditError(
                "non-UI planned obligation must target one of "
                + ", ".join(sorted(NON_UI_PLANNED_EVIDENCE_LAYERS))
            )
        _validate_obligation_action_assertions(index, obligation)


def _validate_ui_planned_obligation(index: int, obligation: dict[str, Any]) -> None:
    missing = []
    for field_name in REQUIRED_UI_PLANNED_OBLIGATION_FIELDS:
        value = obligation.get(field_name)
        if field_name == "required_actor_roles":
            if not _string_list(value):
                missing.append(field_name)
        elif not _has_structured_value(value):
            missing.append(field_name)
    if missing:
        raise CoverageAuditError(
            f"planned obligation row {index} missing fields: "
            + ", ".join(missing)
        )
    path_kind = str(obligation.get("path_kind", "")).strip()
    if path_kind not in ACCEPTED_UI_PATH_KINDS:
        raise CoverageAuditError(
            f"planned obligation row {index} path_kind must be one of "
            + ", ".join(sorted(ACCEPTED_UI_PATH_KINDS))
        )
    roles = {_normalize_actor_role(role) for role in _string_list(obligation.get("required_actor_roles"))}
    if path_kind == "primary_happy_path" and roles <= GENERIC_ACTOR_ROLES:
        raise CoverageAuditError(
            f"planned obligation row {index} primary_happy_path requires a concrete actor role"
        )


def _validate_obligation_action_assertions(
    index: int,
    obligation: dict[str, Any],
) -> None:
    coverage_items = _string_list(obligation.get("coverage_items"))
    action_assertions = obligation.get("action_assertions")
    false_positive_guards = _string_list(obligation.get("false_positive_guards"))
    if not coverage_items:
        raise CoverageAuditError(
            f"planned obligation row {index} missing fields: coverage_items"
        )
    if not isinstance(action_assertions, list) or not action_assertions:
        raise CoverageAuditError(
            f"planned obligation row {index} missing fields: action_assertions"
        )
    if not false_positive_guards:
        raise CoverageAuditError(
            f"planned obligation row {index} missing fields: false_positive_guards"
        )

    assertion_by_item: dict[str, list[dict[str, Any]]] = {}
    for assertion_index, assertion in enumerate(action_assertions, start=1):
        if not isinstance(assertion, dict):
            raise CoverageAuditError(
                f"planned obligation row {index} action assertion {assertion_index} "
                "must be object"
            )
        missing = [
            field_name
            for field_name in REQUIRED_ACTION_ASSERTION_FIELDS
            if not _has_value(assertion.get(field_name))
        ]
        if missing:
            raise CoverageAuditError(
                f"planned obligation row {index} action assertion {assertion_index} "
                "missing fields: "
                + ", ".join(missing)
            )
        item_id = assertion["item_id"]
        assertion_by_item.setdefault(item_id, []).append(assertion)
        if item_id not in coverage_items:
            raise CoverageAuditError(
                f"planned obligation row {index} action assertion references "
                f"unknown coverage item: {item_id}"
            )
        semantic_depth = assertion["semantic_depth"]
        if semantic_depth in FALSE_POSITIVE_SEMANTIC_DEPTHS:
            raise CoverageAuditError(
                f"planned obligation row {index} has false-positive action "
                f"assertion for {item_id}: {semantic_depth}"
            )
        if semantic_depth not in ACCEPTED_SEMANTIC_DEPTHS:
            raise CoverageAuditError(
                f"planned obligation row {index} action assertion semantic_depth "
                f"must be one of {', '.join(sorted(ACCEPTED_SEMANTIC_DEPTHS))}"
            )
        _reject_false_positive_action_text(index, item_id, assertion)

    missing_items = [
        item
        for item in coverage_items
        if item not in assertion_by_item
    ]
    if missing_items:
        raise CoverageAuditError(
            f"planned obligation row {index} missing action assertions for "
            "coverage items: "
            + ", ".join(missing_items)
        )


def _reject_false_positive_action_text(
    row_index: int,
    item_id: str,
    assertion: dict[str, Any],
) -> None:
    haystack = " ".join(
        [
            assertion.get("action_entry", ""),
            assertion.get("expected_real_surface", ""),
            assertion.get("assertion_target", ""),
        ]
    ).lower()
    if any(term in haystack for term in FALSE_POSITIVE_TEXT_TERMS):
        raise CoverageAuditError(
            f"planned obligation row {row_index} has false-positive action "
            f"assertion for {item_id}"
        )


def _validate_structured_exemptions(exemptions: list[dict[str, Any]]) -> None:
    for index, exemption in enumerate(exemptions, start=1):
        missing = [
            field_name
            for field_name in REQUIRED_EXEMPTION_FIELDS
            if not _has_value(exemption.get(field_name))
        ]
        if "allows_closure" not in exemption:
            missing.append("allows_closure")
        elif not isinstance(exemption["allows_closure"], bool):
            raise CoverageAuditError("allows_closure must be boolean")
        if missing:
            raise CoverageAuditError(
                f"exemption row {index} missing fields: " + ", ".join(missing)
            )


def _validate_browser_evidence_record(
    root: Path,
    index: int,
    record: dict[str, Any],
) -> dict[str, Any]:
    missing = []
    for field_name in REQUIRED_BROWSER_EVIDENCE_FIELDS:
        value = record.get(field_name)
        if field_name in {"console_errors", "network_errors"}:
            if not isinstance(value, list):
                missing.append(field_name)
        elif field_name == "network_probe_summary":
            if not isinstance(value, dict) or not value:
                missing.append(field_name)
        elif field_name == "mocked_routes":
            if not isinstance(value, list):
                missing.append(field_name)
        elif field_name == "executed_actor_roles":
            if not _string_list(value):
                missing.append(field_name)
        elif field_name == "actor_identity_evidence":
            if not isinstance(value, dict) or not value:
                missing.append(field_name)
        elif field_name == "ordinary_path_observed":
            if not isinstance(value, bool):
                missing.append(field_name)
        elif field_name == "semantic_assertions":
            if not _has_list_values(value):
                missing.append(field_name)
        elif field_name == "exit_code":
            if value != 0:
                raise CoverageAuditError("browser evidence exit_code must be 0")
        elif not _has_value(value):
            missing.append(field_name)
    if missing:
        raise CoverageAuditError(
            f"browser evidence row {index} missing fields: " + ", ".join(missing)
        )
    primary_role = _normalize_actor_role(record["primary_actor_role"])
    executed_roles = {_normalize_actor_role(role) for role in record["executed_actor_roles"]}
    if primary_role not in executed_roles:
        raise CoverageAuditError(
            f"browser evidence row {index} primary_actor_role must be included in executed_actor_roles"
        )
    strength = record["evidence_strength"]
    if strength not in ACCEPTED_BROWSER_EVIDENCE_STRENGTHS:
        raise CoverageAuditError(
            "browser evidence row "
            f"{index} evidence_strength must be one of "
            + ", ".join(sorted(ACCEPTED_BROWSER_EVIDENCE_STRENGTHS))
        )
    _validate_mocked_routes(index, record["mocked_routes"], strength=strength)
    probe = _load_probe_artifact(root, index, record["probe_artifact_path"])
    if strength == FULL_STACK_BROWSER_E2E:
        _validate_full_stack_probe(index, record, probe)
    return probe


def _load_probe_artifact(root: Path, index: int, probe_artifact_path: str) -> dict[str, Any]:
    path = root / probe_artifact_path
    if not path.is_file():
        raise CoverageAuditError(
            f"browser evidence row {index} probe_artifact_path does not exist: "
            + probe_artifact_path
        )
    try:
        probe = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageAuditError(
            f"browser evidence row {index} probe_artifact_path is not valid JSON"
        ) from exc
    if not isinstance(probe, dict):
        raise CoverageAuditError(
            f"browser evidence row {index} probe_artifact_path must contain an object"
        )
    return probe


def _validate_mocked_routes(
    index: int,
    routes: list[Any],
    *,
    strength: str,
) -> None:
    for route_index, route in enumerate(routes, start=1):
        if not isinstance(route, dict):
            raise CoverageAuditError(
                f"browser evidence row {index} mocked_routes row {route_index} must be object"
            )
        missing = [
            field_name
            for field_name in ("mechanism", "pattern", "classification")
            if not _has_value(route.get(field_name))
        ]
        if "is_business_api" not in route:
            missing.append("is_business_api")
        elif not isinstance(route["is_business_api"], bool):
            raise CoverageAuditError(
                f"browser evidence row {index} mocked_routes row {route_index} "
                "is_business_api must be boolean"
            )
        if missing:
            raise CoverageAuditError(
                f"browser evidence row {index} mocked_routes row {route_index} "
                "missing fields: "
                + ", ".join(missing)
            )
        if (
            strength == FULL_STACK_BROWSER_E2E
            and _is_business_api_mock(route)
            and not _has_value(route.get("exemption_ref"))
        ):
            raise CoverageAuditError(
                f"browser evidence row {index} has unexempted business API mock: "
                + str(route.get("pattern"))
            )


def _validate_full_stack_probe(
    index: int,
    record: dict[str, Any],
    probe: dict[str, Any],
) -> None:
    for field_name in ("acceptance_url", "api_health_url", "api_health_identity"):
        if not _has_value(probe.get(field_name)):
            raise CoverageAuditError(
                f"browser evidence row {index} probe missing {field_name}"
            )
        if probe[field_name] != record[field_name]:
            raise CoverageAuditError(
                f"browser evidence row {index} probe {field_name} does not match record"
            )
    if _probe_is_html_shell(probe):
        raise CoverageAuditError(
            f"browser evidence row {index} API health probe returned HTML shell"
        )
    summary = record["network_probe_summary"]
    request_count = summary.get("business_api_request_count")
    if not isinstance(request_count, int) or request_count < 1:
        raise CoverageAuditError(
            f"browser evidence row {index} network_probe_summary missing business API request"
        )
    business_requests = probe.get("business_api_requests")
    if not isinstance(business_requests, list) or not business_requests:
        raise CoverageAuditError(
            f"browser evidence row {index} probe missing business API requests"
        )


def _probe_is_html_shell(probe: dict[str, Any]) -> bool:
    content_type = str(probe.get("health_response_content_type", "")).lower()
    body_sample = str(probe.get("health_response_body_sample", "")).strip().lower()
    if "text/html" in content_type:
        return True
    return (
        body_sample.startswith("<!doctype html")
        or body_sample.startswith("<html")
        or "<div id=\"root\"" in body_sample
    )


def _is_business_api_mock(route: dict[str, Any]) -> bool:
    return bool(route.get("is_business_api")) or route.get("classification") == "business_api"


def _planned_obligations_by_key(
    obligations: list[dict[str, Any]],
    exemptions: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    exempted = {
        exemption.get("object_id")
        for exemption in exemptions
        if exemption.get("allows_closure") is True
    }
    planned: dict[tuple[str, str], dict[str, Any]] = {}
    for obligation in obligations:
        if obligation.get("exemption_status") == "approved" and (
            obligation.get("scenario_id") in exempted
            or obligation.get("obligation_id") in exempted
            or obligation.get("test_id") in exempted
        ):
            continue
        planned[(obligation["obligation_id"], obligation["test_id"])] = obligation
    return planned


def _validate_executed_records_cover_planned(
    records: list[dict[str, Any]],
    planned_by_key: dict[tuple[str, str], dict[str, Any]],
) -> None:
    record_keys = {
        (record.get("obligation_id"), record.get("test_id"))
        for record in records
    }
    missing = [
        f"{obligation_id}:{test_id}"
        for obligation_id, test_id in planned_by_key
        if (obligation_id, test_id) not in record_keys
    ]
    if missing:
        raise CoverageAuditError(
            "planned E2E obligation missing executed evidence: "
            + ", ".join(missing)
        )
    extra = [
        f"{record.get('obligation_id')}:{record.get('test_id')}"
        for record in records
        if (record.get("obligation_id"), record.get("test_id")) not in planned_by_key
    ]
    if extra:
        raise CoverageAuditError(
            "executed browser evidence is not linked to planned E2E obligation: "
            + ", ".join(extra)
        )
    _validate_executed_actor_path_segments(records, planned_by_key)


def _validate_executed_actor_path_segments(
    records: list[dict[str, Any]],
    planned_by_key: dict[tuple[str, str], dict[str, Any]],
) -> None:
    records_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        records_by_key.setdefault(
            (record.get("obligation_id"), record.get("test_id")),
            [],
        ).append(record)
    segment_owners: dict[str, str] = {}
    duplicate_segments = []
    for key, planned in planned_by_key.items():
        matching = records_by_key.get(key, [])
        required_roles = {
            _normalize_actor_role(role)
            for role in _string_list(planned.get("required_actor_roles"))
        }
        if not required_roles:
            raise CoverageAuditError(
                f"planned obligation {key[0]}:{key[1]} missing required_actor_roles"
            )
        executed_roles = {
            _normalize_actor_role(role)
            for record in matching
            for role in _string_list(record.get("executed_actor_roles"))
        }
        missing_roles = sorted(required_roles - executed_roles)
        if missing_roles:
            raise CoverageAuditError(
                "executed browser evidence actor role does not cover planned "
                f"requirement for {key[0]}:{key[1]}: "
                + ", ".join(missing_roles)
            )
        if not any(record.get("ordinary_path_observed") is True for record in matching):
            raise CoverageAuditError(
                "executed browser evidence missing ordinary path observation for "
                f"{key[0]}:{key[1]}"
            )
        path_kind = str(planned.get("path_kind", "")).strip()
        if path_kind in INDEPENDENT_SEGMENT_PATH_KINDS:
            segments = [
                str(record.get("execution_segment_id", "")).strip()
                for record in matching
                if str(record.get("execution_segment_id", "")).strip()
            ]
            if not segments:
                raise CoverageAuditError(
                    "executed browser evidence missing execution segment for "
                    f"{key[0]}:{key[1]}"
                )
            segment = segments[0]
            owner = f"{key[0]}:{key[1]}"
            previous_owner = segment_owners.get(segment)
            if previous_owner and previous_owner != owner:
                duplicate_segments.append(f"{segment} ({previous_owner}, {owner})")
            segment_owners[segment] = owner
    if duplicate_segments:
        raise CoverageAuditError(
            "executed browser evidence reuses execution segments across UI "
            "journey obligations: "
            + ", ".join(duplicate_segments)
        )


def _has_list_values(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _has_structured_value(value: Any) -> bool:
    if _has_value(value):
        return True
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def _normalize_actor_role(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as evidence_file:
        for chunk in iter(lambda: evidence_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
