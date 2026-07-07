"""Shared Product Delivery user-confirmation policy."""

from __future__ import annotations

from typing import Any


USER_CONFIRMATION_TARGETS = frozenset(
    {
        "open_spec_freeze",
        "ui_prototype",
        "planned_e2e_obligations",
    }
)

RECORDABLE_USER_CONFIRMATION_TARGETS = frozenset(
    {
        "open_spec_freeze",
        "planned_e2e_obligations",
    }
)


def is_user_confirmation_target(target: Any) -> bool:
    return isinstance(target, str) and target in USER_CONFIRMATION_TARGETS


def is_recordable_user_confirmation_target(target: Any) -> bool:
    return isinstance(target, str) and target in RECORDABLE_USER_CONFIRMATION_TARGETS


def pending_user_confirmation_blockers(state: dict[str, Any]) -> list[str]:
    pending = state.get("pending_confirmations") or {}
    if not isinstance(pending, dict):
        return []
    return [
        f"pending_confirmation:{name}"
        for name, record in sorted(pending.items())
        if record and is_user_confirmation_target(name)
    ]


def confirmed_user_confirmation_targets(state: dict[str, Any]) -> list[str]:
    confirmations = state.get("user_confirmations") or {}
    confirmed = [
        name
        for name in sorted(USER_CONFIRMATION_TARGETS)
        if name in confirmations
    ]
    ui = state.get("ui_prototype") or {}
    if ui.get("confirmed_by_user") and "ui_prototype" not in confirmed:
        confirmed.append("ui_prototype")
    return sorted(confirmed)
