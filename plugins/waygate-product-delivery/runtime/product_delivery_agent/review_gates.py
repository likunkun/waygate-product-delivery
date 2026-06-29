"""Visible multi-agent review gate validation and rendering."""

from __future__ import annotations

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
VALID_REVIEW_MODES = {"spawned_subagents", "role_simulation", "blocked_with_reason"}


def validate_multi_agent_review(review_type: str, review: dict[str, Any]) -> None:
    """Validate visible multi-agent review output."""
    if review_type not in {"scenario", "test"}:
        raise ReviewGateError("review_type must be scenario or test")
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


def render_multi_agent_review(review: dict[str, Any]) -> str:
    """Render a multi-agent review as Markdown."""
    return "\n".join(
        [
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
    )


def _has_values(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
