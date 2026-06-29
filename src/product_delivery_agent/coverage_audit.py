"""Test coverage audit validation and rendering."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


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
NON_UI_E2E_LAYERS = {"api_e2e", "service_e2e", "cli_e2e"}

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
)


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
) -> dict[str, Any]:
    """Validate implementation-prep E2E obligations without requiring evidence."""
    if not obligations:
        raise CoverageAuditError("planned E2E obligations require at least one row")
    exemption_records = list(exemptions or [])
    _validate_planned_obligations(obligations)
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
        _validate_browser_evidence_record(index, record)
        evidence_path = root / record["evidence_path"]
        if not evidence_path.is_file():
            raise CoverageAuditError(
                f"evidence_path does not exist: {record['evidence_path']}"
            )
        next_record = dict(record)
        next_record["evidence_sha256"] = _sha256(evidence_path)
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
                row["test_layer"] in NON_UI_E2E_LAYERS
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


def _validate_planned_obligations(obligations: list[dict[str, Any]]) -> None:
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
        if obligation["test_layer"] != "browser_e2e":
            raise CoverageAuditError("UI planned obligation must target browser_e2e")
        _validate_obligation_action_assertions(index, obligation)


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


def _validate_browser_evidence_record(index: int, record: dict[str, Any]) -> None:
    missing = []
    for field_name in REQUIRED_BROWSER_EVIDENCE_FIELDS:
        value = record.get(field_name)
        if field_name in {"console_errors", "network_errors"}:
            if not isinstance(value, list):
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


def _has_list_values(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


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
