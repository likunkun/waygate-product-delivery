"""Hash-linked transition journal for critical Product Delivery events."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

GENESIS_EVENT_HASH = "0" * 64


def append_transition(
    state: dict[str, Any],
    transition_name: str,
    *,
    feature_slug: str | None,
    runtime_version: str,
    input_artifact_hashes: dict[str, str] | None = None,
    output_artifact_hashes: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Return a state copy with one canonical transition event appended."""
    next_state = dict(state)
    journal = dict(next_state.get("transition_journal") or {})
    events = [dict(event) for event in journal.get("events", [])]
    previous_hash = events[-1].get("event_hash", GENESIS_EVENT_HASH) if events else GENESIS_EVENT_HASH
    event = {
        "sequence": len(events) + 1,
        "transition_name": transition_name,
        "feature_slug": feature_slug,
        "previous_event_hash": previous_hash,
        "runtime_version": runtime_version,
        "input_artifact_hashes": dict(input_artifact_hashes or {}),
        "output_artifact_hashes": dict(output_artifact_hashes or {}),
        "metadata": dict(metadata or {}),
        "occurred_at": occurred_at or _timestamp(),
    }
    event["event_hash"] = _event_hash(event)
    events.append(event)
    next_state["transition_journal"] = {
        "schema_version": "v1",
        "events": events,
        "last_event_hash": event["event_hash"],
    }
    return next_state


def journal_integrity_errors(state: dict[str, Any]) -> list[str]:
    """Return hash-chain errors for the current transition journal."""
    journal = state.get("transition_journal")
    if not journal:
        return []
    events = journal.get("events")
    if not isinstance(events, list):
        return ["transition_journal_events"]
    errors: list[str] = []
    previous_hash = GENESIS_EVENT_HASH
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            errors.append("transition_journal_event_shape")
            continue
        if event.get("sequence") != index:
            errors.append("transition_journal_sequence")
        if event.get("previous_event_hash") != previous_hash:
            errors.append("transition_journal_previous_hash")
        expected_hash = _event_hash(event)
        if event.get("event_hash") != expected_hash:
            errors.append("transition_journal_event_hash")
        previous_hash = event.get("event_hash", "")
    if events and journal.get("last_event_hash") != previous_hash:
        errors.append("transition_journal_last_hash")
    return _dedupe(errors)


def has_transition(state: dict[str, Any], transition_name: str) -> bool:
    """Return whether a valid journal contains a transition."""
    if journal_integrity_errors(state):
        return False
    return any(
        isinstance(event, dict) and event.get("transition_name") == transition_name
        for event in state.get("transition_journal", {}).get("events", [])
    )


def transition_names(state: dict[str, Any]) -> list[str]:
    """Return transition names from a valid journal, or an empty list."""
    if journal_integrity_errors(state):
        return []
    return [
        event["transition_name"]
        for event in state.get("transition_journal", {}).get("events", [])
        if isinstance(event, dict) and "transition_name" in event
    ]


def _event_hash(event: dict[str, Any]) -> str:
    material = {key: value for key, value in event.items() if key != "event_hash"}
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
