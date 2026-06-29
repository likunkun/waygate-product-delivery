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
VALID_REVIEW_TYPES = {"scenario", "test", "test_coverage", "test_implementation"}
VALID_REVIEW_MODES = {"spawned_subagents", "role_simulation", "blocked_with_reason"}
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


def validate_multi_agent_review(review_type: str, review: dict[str, Any]) -> None:
    """Validate visible multi-agent review output."""
    if review_type not in VALID_REVIEW_TYPES:
        raise ReviewGateError(
            "review_type must be scenario, test, test_coverage, or test_implementation"
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
    if review_type == "test_coverage":
        _validate_test_coverage_review(review)
    elif review_type == "test_implementation":
        _validate_test_implementation_review(review)


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


def _test_review_evidence(review: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "traceability_reviewed",
        "coverage_gaps",
        "title_overbreadth_findings",
        "missing_executable_assertions",
        "false_positive_risks",
        "collection_coverage",
        "actual_test_code_paths",
        "execution_evidence_paths",
        "reviewed_test_ids",
        "verified_action_assertions",
        "supporting_evidence_only",
    )
    return {key: review[key] for key in keys if key in review}


def _has_values(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _validate_test_coverage_review(review: dict[str, Any]) -> None:
    missing = []
    for field_name in (
        "traceability_reviewed",
        "coverage_gaps",
        "title_overbreadth_findings",
        "missing_executable_assertions",
        "false_positive_risks",
        "collection_coverage",
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
    _validate_collection_coverage(review.get("collection_coverage"))


def _validate_test_implementation_review(review: dict[str, Any]) -> None:
    missing = []
    for field_name in (
        "actual_test_code_paths",
        "execution_evidence_paths",
        "reviewed_test_ids",
    ):
        if not _has_values(review.get(field_name)):
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
    _validate_verified_action_assertions(review.get("verified_action_assertions"))


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


def _validate_verified_action_assertions(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ReviewGateError("verified_action_assertions requires at least one row")
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
        _reject_false_positive_text(
            assertion.get("expected_real_surface", ""),
            assertion.get("assertion_target", ""),
        )


def _reject_false_positive_text(*values: str) -> None:
    haystack = " ".join(values).lower()
    if any(term in haystack for term in FALSE_POSITIVE_TERMS):
        raise ReviewGateError("false-positive test implementation assertion detected")


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    }


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
