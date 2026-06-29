"""User confirmation artifact validation and rendering."""

from __future__ import annotations

from typing import Any


class ConfirmationError(RuntimeError):
    """Raised when a user confirmation cannot be accepted."""


REQUIRED_CONFIRMATION_FIELDS = (
    "confirmation_id",
    "target",
    "artifact_path",
    "artifact_version",
    "confirmed_by",
    "confirmation_source",
    "confirmed_at",
    "decision",
    "user_message",
)


def validate_user_confirmation(confirmation: dict[str, Any]) -> None:
    """Validate a structured user confirmation record."""
    missing = [
        field_name
        for field_name in REQUIRED_CONFIRMATION_FIELDS
        if not _has_value(confirmation.get(field_name))
    ]
    if missing:
        raise ConfirmationError(
            "missing confirmation fields: " + ", ".join(missing)
        )
    if confirmation.get("decision") != "approved":
        raise ConfirmationError("confirmation decision must be approved")


def validate_confirmation_message(
    user_message: str,
    *,
    agent_explicitly_asked: bool = False,
) -> None:
    """Accept only explicit confirmation language."""
    normalized = user_message.strip().lower()
    if not normalized:
        raise ConfirmationError("user confirmation message is required")
    explicit_markers = ("确认", "同意", "approved", "approve", "confirmed", "yes")
    if any(marker in normalized for marker in explicit_markers):
        return
    raise ConfirmationError("explicit user confirmation is required")


def render_user_confirmation(confirmation: dict[str, Any]) -> str:
    """Render a user confirmation as a Markdown artifact."""
    return "\n".join(
        [
            "# User Confirmation",
            "",
            f"Confirmation ID: {confirmation['confirmation_id']}",
            f"Target: {confirmation['target']}",
            f"Decision: {confirmation['decision']}",
            f"Confirmed By: {confirmation['confirmed_by']}",
            f"Source: {confirmation['confirmation_source']}",
            f"Confirmed At: {confirmation['confirmed_at']}",
            f"Artifact Path: {confirmation['artifact_path']}",
            f"Artifact Version: {confirmation['artifact_version']}",
            *(
                [f"Artifact Hash: {confirmation['artifact_hash']}"]
                if confirmation.get("artifact_hash")
                else []
            ),
            *(
                [f"Prototype Revision: {confirmation['prototype_revision']}"]
                if confirmation.get("prototype_revision")
                else []
            ),
            *(
                [f"Nonce: {confirmation['nonce']}"]
                if confirmation.get("nonce")
                else []
            ),
            "",
            "## User Message",
            confirmation["user_message"],
            "",
        ]
    )


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
