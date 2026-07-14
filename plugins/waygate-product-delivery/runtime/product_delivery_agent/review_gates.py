"""Visible multi-agent review gate validation and rendering."""

from __future__ import annotations

import json
from typing import Any


class ReviewGateError(RuntimeError):
    """Raised when a multi-agent review cannot be accepted."""


REQUIRED_REVIEW_FIELDS = (
    "review_id",
    "review_type",
    "status",
    "reviewers",
    "artifact_version",
    "independent_positions",
    "cross_challenges",
    "revisions",
    "final_adjudication",
    "conclusions",
    "accepted_suggestions",
    "rejected_suggestions",
    "unresolved_questions",
    "blocking_findings",
)
VALID_REVIEW_TYPES = {
    "scenario",
    "test",
    "test_coverage",
    "test_implementation",
    "ui_conformance",
}
VALID_REVIEW_MODES = {"spawned_subagents", "role_simulation", "blocked_with_reason"}
UI_CONTINUITY_CHANGE_TYPES = {
    "incremental_existing_surface",
    "new_surface_in_existing_product",
    "greenfield_ui",
}
BASELINE_INHERITANCE_FIELDS = (
    "ui_change_type",
    "baseline_feature_slug",
    "baseline_entry_path",
    "inherits_existing_surface",
    "parallel_surface_replacement",
)
REQUIRED_TEST_COVERAGE_TRACE_TARGETS = {"US", "J", "SC", "AC", "TASK", "TC"}
FALSE_POSITIVE_TERMS = {
    "marker",
    "function name",
    "function-name",
    "static panel",
    "static-only",
    "first button",
    "first-button",
}


def validate_multi_agent_review(
    review_type: str,
    review: dict[str, Any],
    *,
    ui_change_type: str | None = None,
    planned_obligations: list[dict[str, Any]] | None = None,
    executed_records: list[dict[str, Any]] | None = None,
    prototype_contract: dict[str, Any] | None = None,
) -> None:
    """Validate visible multi-agent review output."""
    if review_type not in VALID_REVIEW_TYPES:
        raise ReviewGateError(
            "review_type must be scenario, test, test_coverage, test_implementation, or ui_conformance"
        )
    missing = []
    for field_name in REQUIRED_REVIEW_FIELDS:
        value = review.get(field_name)
        if field_name in {
            "reviewers",
            "independent_positions",
            "cross_challenges",
            "revisions",
            "conclusions",
        }:
            if not _has_values(value):
                missing.append(field_name)
        elif value is None:
            missing.append(field_name)
        elif isinstance(value, str) and not value.strip():
            missing.append(field_name)
    if missing:
        raise ReviewGateError("missing review fields: " + ", ".join(missing))
    if review.get("review_type") != review_type:
        raise ReviewGateError("review_type mismatch")
    review_mode = review.get("review_mode", "spawned_subagents")
    if review_mode not in VALID_REVIEW_MODES:
        raise ReviewGateError("review_mode must be spawned_subagents, role_simulation, or blocked_with_reason")
    if review_mode == "blocked_with_reason":
        raise ReviewGateError("multi-agent review is blocked: " + str(review.get("blocked_reason", "")))
    if review_mode == "role_simulation" and review.get("role_simulation_user_accepted") is not True:
        raise ReviewGateError("role_simulation review requires explicit user acceptance")
    if review.get("status") != "passed":
        raise ReviewGateError("multi-agent review must pass")
    if review.get("blocking_findings"):
        raise ReviewGateError("blocking review findings remain unresolved")
    if review_type == "scenario":
        _validate_scenario_review(review, ui_change_type=ui_change_type)
    elif review_type == "test_coverage":
        _validate_test_coverage_review(
            review,
            planned_obligations=planned_obligations,
        )
    elif review_type == "test_implementation":
        _validate_test_implementation_review(
            review,
            planned_obligations=planned_obligations,
            executed_records=executed_records,
        )
    elif review_type == "ui_conformance":
        _validate_ui_conformance_review(review, prototype_contract or {})
def _validate_ui_conformance_review(
    review: dict[str, Any],
    prototype_contract: dict[str, Any],
) -> None:
    required_list_fields = (
        "reviewed_surface_ids",
        "reviewed_state_ids",
        "reviewed_region_ids",
        "structural_findings",
        "visual_findings",
        "interaction_findings",
        "legacy_reuse_findings",
        "unmapped_regions",
    )
    missing = [
        field_name
        for field_name in required_list_fields
        if not isinstance(review.get(field_name), list)
    ]
    if missing:
        raise ReviewGateError(
            "missing UI conformance review fields: " + ", ".join(missing)
        )
    for field_name in (
        "structural_findings",
        "visual_findings",
        "interaction_findings",
        "unmapped_regions",
    ):
        _reject_unresolved_review_items(review, field_name)

    surfaces = prototype_contract.get("surfaces") or []
    required_surfaces = {surface.get("surface_id") for surface in surfaces}
    required_states = {surface.get("state_id") for surface in surfaces}
    required_regions = {
        region.get("region_id")
        for surface in surfaces
        for region in surface.get("critical_regions", [])
    }
    comparisons = (
        ("reviewed_surface_ids", required_surfaces),
        ("reviewed_state_ids", required_states),
        ("reviewed_region_ids", required_regions),
    )
    for field_name, required in comparisons:
        reviewed = _string_set(review.get(field_name))
        missing_items = sorted(required - reviewed)
        if missing_items:
            raise ReviewGateError(
                f"{field_name} missing required items: " + ", ".join(missing_items)
            )


def render_multi_agent_review(review: dict[str, Any]) -> str:
    """Render a multi-agent review as Markdown."""
    lines = [
        "# Multi-Agent Review",
        "",
        f"Review ID: {review['review_id']}",
        f"Review Type: {review['review_type']}",
        f"Status: {review['status']}",
        f"Review Mode: {review.get('review_mode', 'spawned_subagents')}",
        f"Artifact Version: {review['artifact_version']}",
        "Reviewer Agent IDs: "
        + ", ".join(review.get("reviewer_agent_ids") or []),
        f"Reviewer Spawn Source: {review.get('reviewer_spawn_source') or 'not-applicable'}",
        "",
        "## Independent Positions",
        *_bullets(review["independent_positions"]),
        "",
        "## Cross Challenges",
        *_bullets(review["cross_challenges"]),
        "",
        "## Revisions",
        *_bullets(review["revisions"]),
        "",
        "## Final Adjudication",
        review["final_adjudication"],
        "",
        "## Reviewers",
        *_bullets(review["reviewers"]),
        "",
        "## Conclusions",
        *_bullets(review["conclusions"]),
        "",
        "## Accepted Suggestions",
        *_bullets(review["accepted_suggestions"]),
        "",
        "## Rejected Suggestions",
        *_bullets(review["rejected_suggestions"]),
        "",
        "## Unresolved Questions",
        *_bullets(review["unresolved_questions"]),
        "",
    ]
    if review["review_type"] == "scenario":
        lines.extend(
            [
                "## UI Baseline Continuity",
                "",
                "```json",
                json.dumps(_scenario_review_evidence(review), indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    if review["review_type"] in {"test_coverage", "test_implementation"}:
        lines.extend(
            [
                "## Test Review Evidence",
                "",
                "```json",
                json.dumps(_test_review_evidence(review), indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _scenario_review_evidence(review: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "baseline_inheritance_review",
        "ui_continuity_findings",
    )
    return {key: review[key] for key in keys if key in review}


def _test_review_evidence(review: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "traceability_reviewed",
        "coverage_gaps",
        "title_overbreadth_findings",
        "missing_executable_assertions",
        "false_positive_risks",
        "collection_coverage",
        "role_journey_coverage",
        "ordinary_path_coverage",
        "scenario_granularity_findings",
        "actual_test_code_paths",
        "execution_evidence_paths",
        "reviewed_test_ids",
        "verified_action_assertions",
        "supporting_evidence_only",
        "business_api_mock_findings",
        "actor_role_findings",
        "evidence_distribution_findings",
        "annotation_only_findings",
        "ordinary_path_findings",
    )
    return {key: review[key] for key in keys if key in review}


def _has_values(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _validate_scenario_review(
    review: dict[str, Any],
    *,
    ui_change_type: str | None = None,
) -> None:
    continuity_fields_present = (
        "baseline_inheritance_review" in review
        or "ui_continuity_findings" in review
        or ui_change_type in UI_CONTINUITY_CHANGE_TYPES
    )
    if not continuity_fields_present:
        return

    if review.get("ui_continuity_findings"):
        raise ReviewGateError(
            "unresolved ui_continuity_findings remain: "
            + ", ".join(map(str, review.get("ui_continuity_findings") or []))
        )
    if not isinstance(review.get("ui_continuity_findings"), list):
        raise ReviewGateError("missing scenario review fields: ui_continuity_findings")

    inheritance = review.get("baseline_inheritance_review")
    if not isinstance(inheritance, dict) or not inheritance:
        raise ReviewGateError(
            "missing scenario review fields: baseline_inheritance_review"
        )
    inheritance_change_type = inheritance.get("ui_change_type") or ui_change_type
    if inheritance_change_type == "incremental_existing_surface":
        missing = [
            field_name
            for field_name in BASELINE_INHERITANCE_FIELDS
            if field_name not in inheritance
        ]
        if missing:
            raise ReviewGateError(
                "baseline_inheritance_review missing fields: "
                + ", ".join(missing)
            )
        if not _non_empty_string(inheritance.get("baseline_feature_slug")):
            raise ReviewGateError(
                "baseline_inheritance_review missing fields: baseline_feature_slug"
            )
        if not _non_empty_string(inheritance.get("baseline_entry_path")):
            raise ReviewGateError(
                "baseline_inheritance_review missing fields: baseline_entry_path"
            )
        if inheritance.get("inherits_existing_surface") is not True:
            raise ReviewGateError(
                "baseline_inheritance_review must inherit existing surface"
            )
        if inheritance.get("parallel_surface_replacement") is True:
            raise ReviewGateError(
                "baseline_inheritance_review rejects parallel surface replacement"
            )


def _validate_test_coverage_review(
    review: dict[str, Any],
    *,
    planned_obligations: list[dict[str, Any]] | None = None,
) -> None:
    missing = []
    for field_name in (
        "traceability_reviewed",
        "coverage_gaps",
        "title_overbreadth_findings",
        "missing_executable_assertions",
        "false_positive_risks",
        "collection_coverage",
        "role_journey_coverage",
        "ordinary_path_coverage",
        "scenario_granularity_findings",
    ):
        if field_name not in review:
            missing.append(field_name)
    if missing:
        raise ReviewGateError(
            "missing test coverage review fields: " + ", ".join(missing)
        )

    reviewed = set(review.get("traceability_reviewed") or [])
    missing_trace = sorted(REQUIRED_TEST_COVERAGE_TRACE_TARGETS - reviewed)
    if missing_trace:
        raise ReviewGateError(
            "test coverage review missing traceability targets: "
            + ", ".join(missing_trace)
        )
    _reject_unresolved_review_items(review, "coverage_gaps")
    _reject_unresolved_review_items(review, "title_overbreadth_findings")
    _reject_unresolved_review_items(review, "missing_executable_assertions")
    _reject_unresolved_review_items(review, "false_positive_risks")
    _reject_unresolved_review_items(review, "scenario_granularity_findings")
    _validate_collection_coverage(review.get("collection_coverage"))
    _validate_role_journey_coverage(review, planned_obligations or [])
    _validate_ordinary_path_coverage(review, planned_obligations or [])


def _validate_test_implementation_review(
    review: dict[str, Any],
    *,
    planned_obligations: list[dict[str, Any]] | None = None,
    executed_records: list[dict[str, Any]] | None = None,
) -> None:
    missing = []
    for field_name in (
        "actual_test_code_paths",
        "execution_evidence_paths",
        "reviewed_test_ids",
    ):
        if not _has_values(review.get(field_name)):
            missing.append(field_name)
    for field_name in (
        "supporting_evidence_only",
        "business_api_mock_findings",
        "actor_role_findings",
        "evidence_distribution_findings",
        "annotation_only_findings",
        "ordinary_path_findings",
    ):
        if not isinstance(review.get(field_name), list):
            missing.append(field_name)
    if not isinstance(review.get("verified_action_assertions"), list) or not review.get(
        "verified_action_assertions"
    ):
        missing.append("verified_action_assertions")
    if missing:
        raise ReviewGateError(
            "missing test implementation review fields: " + ", ".join(missing)
        )
    _reject_unresolved_review_items(review, "false_positive_risks")
    _reject_unresolved_review_items(review, "actor_role_findings")
    _reject_unresolved_review_items(review, "evidence_distribution_findings")
    _reject_unresolved_review_items(review, "annotation_only_findings")
    _reject_unresolved_review_items(review, "ordinary_path_findings")
    _reject_unexempted_business_api_mock_findings(
        review.get("business_api_mock_findings")
    )
    _validate_reviewed_test_ids(review.get("reviewed_test_ids"), planned_obligations or [])
    _validate_reviewed_test_ids(
        review.get("reviewed_test_ids"),
        _planned_like_records(executed_records or []),
    )
    _validate_verified_action_assertions(
        review.get("verified_action_assertions"),
        planned_obligations=planned_obligations or [],
    )


def _reject_unresolved_review_items(review: dict[str, Any], field_name: str) -> None:
    value = review.get(field_name)
    if value:
        raise ReviewGateError(
            f"unresolved {field_name} remain: " + ", ".join(map(str, value))
        )


def _validate_collection_coverage(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ReviewGateError("collection_coverage requires at least one collection")
    for index, collection in enumerate(value, start=1):
        if not isinstance(collection, dict):
            raise ReviewGateError(f"collection_coverage row {index} must be object")
        required = _string_set(collection.get("required_items"))
        covered = _string_set(collection.get("covered_items"))
        assertions = collection.get("item_level_assertions")
        if not required:
            raise ReviewGateError(f"collection_coverage row {index} missing required_items")
        missing_items = sorted(required - covered)
        if missing_items:
            raise ReviewGateError(
                "collection_coverage missing covered items: "
                + ", ".join(missing_items)
            )
        if not isinstance(assertions, dict):
            raise ReviewGateError(
                f"collection_coverage row {index} missing item_level_assertions"
            )
        missing_assertions = [
            item
            for item in sorted(required)
            if not isinstance(assertions.get(item), str)
            or not assertions.get(item, "").strip()
        ]
        if missing_assertions:
            raise ReviewGateError(
                "collection_coverage missing item-level assertions: "
                + ", ".join(missing_assertions)
            )


def _validate_verified_action_assertions(
    value: Any,
    *,
    planned_obligations: list[dict[str, Any]] | None = None,
) -> None:
    if not isinstance(value, list) or not value:
        raise ReviewGateError("verified_action_assertions requires at least one row")
    observed_items: set[tuple[str, str]] = set()
    for index, assertion in enumerate(value, start=1):
        if not isinstance(assertion, dict):
            raise ReviewGateError(
                f"verified_action_assertions row {index} must be object"
            )
        missing = [
            field_name
            for field_name in (
                "test_id",
                "item_id",
                "clicked_entry",
                "expected_real_surface",
                "assertion_target",
                "evidence_path",
            )
            if not isinstance(assertion.get(field_name), str)
            or not assertion.get(field_name, "").strip()
        ]
        if missing:
            raise ReviewGateError(
                f"verified_action_assertions row {index} missing fields: "
                + ", ".join(missing)
            )
        observed_items.add((assertion["test_id"], assertion["item_id"]))
        _reject_false_positive_text(
            assertion.get("expected_real_surface", ""),
            assertion.get("assertion_target", ""),
        )
    required_items = {
        (obligation["test_id"], item)
        for obligation in planned_obligations or []
        for item in _string_set(obligation.get("coverage_items"))
        if isinstance(obligation.get("test_id"), str)
    }
    missing_items = sorted(required_items - observed_items)
    if missing_items:
        raise ReviewGateError(
            "verified_action_assertions missing planned coverage items: "
            + ", ".join(f"{test_id}:{item_id}" for test_id, item_id in missing_items)
        )


def _validate_reviewed_test_ids(
    value: Any,
    planned_obligations: list[dict[str, Any]],
) -> None:
    if not planned_obligations:
        return
    reviewed = _string_set(value)
    required = {
        obligation["test_id"]
        for obligation in planned_obligations
        if isinstance(obligation.get("test_id"), str)
    }
    missing = sorted(required - reviewed)
    if missing:
        raise ReviewGateError(
            "reviewed_test_ids missing planned tests: " + ", ".join(missing)
        )


def _validate_role_journey_coverage(
    review: dict[str, Any],
    planned_obligations: list[dict[str, Any]],
) -> None:
    coverage = review.get("role_journey_coverage")
    if not isinstance(coverage, list) or not coverage:
        raise ReviewGateError("role_journey_coverage requires at least one row")
    if not planned_obligations:
        return
    by_test = {
        row.get("test_id"): row
        for row in coverage
        if isinstance(row, dict) and isinstance(row.get("test_id"), str)
    }
    missing = []
    mismatched_roles = []
    for obligation in planned_obligations:
        test_id = obligation.get("test_id")
        row = by_test.get(test_id)
        if not row:
            missing.append(str(test_id))
            continue
        required_roles = _actor_role_set(obligation.get("required_actor_roles"))
        reviewed_roles = _actor_role_set(row.get("required_actor_roles"))
        if required_roles and not required_roles <= reviewed_roles:
            mismatched_roles.append(str(test_id))
    if missing:
        raise ReviewGateError(
            "role_journey_coverage missing planned tests: " + ", ".join(missing)
        )
    if mismatched_roles:
        raise ReviewGateError(
            "role_journey_coverage missing required actor roles: "
            + ", ".join(mismatched_roles)
        )


def _validate_ordinary_path_coverage(
    review: dict[str, Any],
    planned_obligations: list[dict[str, Any]],
) -> None:
    coverage = review.get("ordinary_path_coverage")
    if not isinstance(coverage, list) or not coverage:
        raise ReviewGateError("ordinary_path_coverage requires at least one row")
    if not planned_obligations:
        return
    by_test = {
        row.get("test_id"): row
        for row in coverage
        if isinstance(row, dict) and isinstance(row.get("test_id"), str)
    }
    missing = []
    for obligation in planned_obligations:
        test_id = obligation.get("test_id")
        row = by_test.get(test_id)
        if not row:
            missing.append(str(test_id))
            continue
        expected_path = str(obligation.get("ordinary_entry_path", "")).strip()
        reviewed_path = str(row.get("ordinary_entry_path", "")).strip()
        if expected_path and reviewed_path != expected_path:
            missing.append(str(test_id))
    if missing:
        raise ReviewGateError(
            "ordinary_path_coverage missing planned paths: " + ", ".join(missing)
        )


def _planned_like_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"test_id": record["test_id"]}
        for record in records
        if isinstance(record.get("test_id"), str)
    ]


def _reject_unexempted_business_api_mock_findings(value: Any) -> None:
    if not isinstance(value, list):
        raise ReviewGateError("business_api_mock_findings must be a list")
    blockers = []
    for index, finding in enumerate(value, start=1):
        if not isinstance(finding, dict):
            raise ReviewGateError(
                f"business_api_mock_findings row {index} must be object"
            )
        if finding.get("is_business_api") is True and not _non_empty_string(
            finding.get("exemption_ref")
        ):
            blockers.append(
                str(
                    finding.get("route")
                    or finding.get("pattern")
                    or finding.get("test_id")
                    or f"row {index}"
                )
            )
    if blockers:
        raise ReviewGateError(
            "unexempted business API mock findings remain: "
            + ", ".join(blockers)
        )


def _reject_false_positive_text(*values: str) -> None:
    haystack = " ".join(values).lower()
    if any(term in haystack for term in FALSE_POSITIVE_TERMS):
        raise ReviewGateError("false-positive test implementation assertion detected")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    }


def _actor_role_set(value: Any) -> set[str]:
    return {_normalize_actor_role(item) for item in _string_set(value)}


def _normalize_actor_role(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
