"""Codex Host Goal binding and reconciliation protocol."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from product_delivery_agent.transition_journal import (
    append_transition,
    journal_integrity_errors,
)


HOST_GOAL_SCHEMA_VERSION = "v1"
HOST_GOAL_SOURCE = "codex_goal_tool"
CODEX_THREAD_ID_ENV = "CODEX_THREAD_ID"
HOST_GOAL_OWNER_CLAIM_MESSAGE = "恢复交付主线程，接管当前 Host Goal"
RECONCILIATION_OPERATIONS = {
    "turn_start",
    "stage_transition",
    "user_resume",
    "block_goal",
    "pre_complete",
    "complete_goal",
    "verify_completion",
    "stop_delivery",
}
CANONICAL_TRANSITION_OPERATIONS = {
    "stage_transition",
    "user_resume",
}
ACTIVATION_OPERATIONS = {
    "inspect_before_activation",
    "create_goal",
    "verify_activation",
}


class HostGoalError(RuntimeError):
    """Raised when Codex Host Goal evidence cannot authorize progression."""


def host_goal_required(state: dict[str, Any]) -> bool:
    """Return whether the active delivery has entered the post-handoff phase."""
    if not state.get("active"):
        return False
    if state.get("status") in {"closed", "complete", "stopped"}:
        return False
    return bool(state.get("handoff") or state.get("delivery_goal"))


def build_host_goal_authorization(
    state: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    """Bind explicit test-plan confirmation to Host Goal orchestration."""
    confirmation_hash = str(confirmation.get("artifact_hash") or "")
    if not confirmation_hash:
        raise HostGoalError("test coverage confirmation hash is required")
    material = {
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "confirmation_hash": confirmation_hash,
        "scope": "current_delivery",
        "advance_until": "canonical_closure_or_explicit_user_stop",
        "pause_for_human_decisions": True,
        "stop_on_user_request": True,
    }
    return {
        "schema_version": HOST_GOAL_SCHEMA_VERSION,
        "status": "authorized",
        **material,
        "authorization_hash": stable_hash(material),
        "authorization_source": "test_coverage_plan_user_confirmation",
        "authorized_at": _timestamp(),
    }


def current_codex_thread_id() -> str | None:
    """Return the current Codex thread identity exposed by the host."""
    value = os.environ.get(CODEX_THREAD_ID_ENV)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def initialize_host_goal_owner(state: dict[str, Any]) -> dict[str, Any]:
    """Capture the delivery coordinator thread without creating a Host Goal."""
    thread_id = current_codex_thread_id()
    return {
        "schema_version": HOST_GOAL_SCHEMA_VERSION,
        "status": "claimed" if thread_id else "thread_context_unavailable",
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "coordinator_thread_id": thread_id,
        "generation": 1 if thread_id else 0,
        "claim_source": "delivery_start" if thread_id else None,
        "claimed_at": _timestamp() if thread_id else None,
        "pending_claim": None,
    }


def inspect_host_goal_owner(state: dict[str, Any]) -> dict[str, Any]:
    """Describe current coordinator, binding owner, and transfer readiness."""
    owner = state.get("host_goal_owner") or {}
    binding = state.get("host_goal_binding") or {}
    current_thread_id = current_codex_thread_id()
    coordinator_thread_id = owner.get("coordinator_thread_id")
    observed_binding_thread_id = (binding.get("host_identifiers") or {}).get(
        "threadId"
    )
    binding_owner_thread_id = binding.get("owner_thread_id")
    owner_matches_current = bool(
        current_thread_id
        and owner.get("status") == "claimed"
        and coordinator_thread_id == current_thread_id
    )
    binding_requires_thread = _binding_requires_observed_thread(binding)
    binding_matches_current = bool(
        not host_goal_required(state)
        or (
            current_thread_id
            and binding_owner_thread_id == current_thread_id
            and (
                observed_binding_thread_id == current_thread_id
                if binding_requires_thread
                else not observed_binding_thread_id
                or observed_binding_thread_id == current_thread_id
            )
        )
    )
    return {
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "owner_status": owner.get("status"),
        "current_thread_id": current_thread_id,
        "coordinator_thread_id": coordinator_thread_id,
        "binding_owner_thread_id": binding_owner_thread_id,
        "observed_binding_thread_id": observed_binding_thread_id,
        "owner_matches_current_thread": owner_matches_current,
        "binding_matches_current_thread": binding_matches_current,
        "owner_transfer_required": not (
            owner_matches_current and binding_matches_current
        ),
        "required_user_message": HOST_GOAL_OWNER_CLAIM_MESSAGE,
    }


def assert_host_goal_owner(
    state: dict[str, Any],
    *,
    require_binding: bool = True,
) -> str:
    """Fail closed unless this runtime is the delivery coordinator thread."""
    thread_id = current_codex_thread_id()
    if not thread_id:
        raise HostGoalError(
            "CODEX_THREAD_ID is required for Codex Host Goal operations"
        )
    owner = state.get("host_goal_owner") or {}
    if owner.get("status") != "claimed":
        raise HostGoalError(
            "Host Goal coordinator thread is unverified; use the owner claim recovery API"
        )
    if owner.get("delivery_id") != state.get("delivery_id"):
        raise HostGoalError("Host Goal owner delivery identity mismatch")
    if owner.get("feature_slug") != state.get("feature_slug"):
        raise HostGoalError("Host Goal owner feature identity mismatch")
    if owner.get("coordinator_thread_id") != thread_id:
        raise HostGoalError(
            "current CODEX_THREAD_ID does not match the Host Goal coordinator thread"
        )
    if require_binding and host_goal_required(state):
        binding = state.get("host_goal_binding") or {}
        if binding.get("owner_thread_id") != thread_id:
            raise HostGoalError(
                "Host Goal binding does not belong to the coordinator thread"
            )
        observed_thread_id = (binding.get("host_identifiers") or {}).get(
            "threadId"
        )
        if _binding_requires_observed_thread(binding) and not observed_thread_id:
            raise HostGoalError(
                "active Host Goal binding requires an observed threadId"
            )
        if observed_thread_id and observed_thread_id != thread_id:
            raise HostGoalError(
                "stored Host Goal threadId does not match the coordinator thread"
            )
    return thread_id


def initialize_host_goal_binding(state: dict[str, Any]) -> dict[str, Any]:
    """Create a current-delivery Host Goal binding after canonical handoff."""
    owner_thread_id = assert_host_goal_owner(state, require_binding=False)
    authorization = state.get("host_goal_authorization") or {}
    if authorization.get("status") != "authorized":
        raise HostGoalError("Host Goal authorization is required before activation")
    goal = state.get("delivery_goal") or {}
    launch_hash = str(goal.get("launch_package_hash") or "")
    if not launch_hash:
        raise HostGoalError("launch package hash is required for Host Goal activation")

    previous = state.get("host_goal_binding") or {}
    if (
        previous.get("delivery_id") == state.get("delivery_id")
        and previous.get("launch_package_hash") == launch_hash
        and previous.get("owner_thread_id") == owner_thread_id
        and previous.get("status")
        in {
            "activation_pending",
            "creation_ready",
            "verification_pending",
            "active",
        }
    ):
        return deepcopy(previous)

    return _new_host_goal_binding(
        state,
        owner_thread_id=owner_thread_id,
        previous_binding=previous,
    )


def build_host_goal_objective(
    *,
    delivery_id: str,
    feature_slug: str,
    launch_package_hash: str,
    binding_nonce: str,
) -> str:
    """Return the stable objective sent to Codex create_goal."""
    return (
        "Complete Waygate Product Delivery for "
        f"delivery {delivery_id}, feature {feature_slug}, launch package "
        f"{launch_package_hash}, binding {binding_nonce}. Execute every planned "
        "TASK, record required evidence and reviews, and reach canonical closure. "
        "Pause without canonical delivery mutations for unresolved human decisions. "
        "Stop further delivery work after an explicit user stop."
    )


def prepare_activation_checkpoint(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare the next get/create/get action for initial activation."""
    assert_host_goal_owner(state)
    binding = deepcopy(state.get("host_goal_binding") or {})
    status = binding.get("status")
    operations = {
        "activation_pending": ("inspect_before_activation", "get_goal"),
        "creation_ready": ("create_goal", "create_goal"),
        "verification_pending": ("verify_activation", "get_goal"),
    }
    if status == "active":
        return binding, _activation_response(binding, None)
    if status in {"legacy_unverified", "reactivation_required"}:
        raise HostGoalError("Host Goal recovery authorization is required")
    if status not in operations:
        raise HostGoalError(f"Host Goal activation is unavailable from status: {status}")
    pending = binding.get("pending_checkpoint") or {}
    if pending and pending.get("projection_sha256") != goal_state_projection_hash(
        state, binding=binding
    ):
        checkpoint_id = str(pending.get("checkpoint_id") or "")
        raise HostGoalError(
            "Host Goal activation checkpoint is stale; call "
            f"recover_stale_host_goal_checkpoint('{checkpoint_id}')"
        )
    operation, required_tool = operations[status]
    binding, checkpoint = _prepare_checkpoint(
        state,
        binding,
        operation=operation,
        required_tool=required_tool,
        target_gate="host_goal_activation",
    )
    return binding, _activation_response(binding, checkpoint)


def prepare_reconciliation_checkpoint(
    state: dict[str, Any],
    *,
    operation: str,
    target_gate: str | None,
    host_turn_id: str | None = None,
    human_decision_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare a fresh get_goal checkpoint for one canonical transition."""
    assert_host_goal_owner(state)
    binding = deepcopy(state.get("host_goal_binding") or {})
    if operation not in RECONCILIATION_OPERATIONS:
        raise HostGoalError(f"unsupported Host Goal operation: {operation}")
    operation_tools = {
        "block_goal": "update_goal",
        "complete_goal": "update_goal",
        "verify_completion": "get_goal",
    }
    required_tool = operation_tools.get(operation, "get_goal")
    if operation == "verify_completion":
        if binding.get("status") != "completion_verification_pending":
            raise HostGoalError("Host Goal completion verification is not pending")
    elif operation == "user_resume":
        if binding.get("status") not in {"active", "blocked"}:
            raise HostGoalError("Host Goal cannot resume from the current status")
    elif binding.get("status") != "active":
        raise HostGoalError("active Host Goal binding is required")
    if not isinstance(target_gate, str) or not target_gate.strip():
        raise HostGoalError("target_gate is required for Host Goal reconciliation")
    if operation == "complete_goal":
        if not canonical_closure_passed(state):
            raise HostGoalError(
                "canonical closure must pass before Host Goal completion"
            )
        authorization = binding.get("authorized_transition") or {}
        if (
            authorization.get("operation") != "pre_complete"
            or authorization.get("target_gate") != target_gate
        ):
            raise HostGoalError(
                "fresh pre-completion Host Goal observation is required"
            )
        binding["authorized_transition"] = None
    if operation == "block_goal":
        human_wait = binding.get("human_wait") or {}
        if int(human_wait.get("consecutive_goal_turns") or 0) < 3:
            raise HostGoalError(
                "three consecutive Host Goal turns are required before blocking"
            )
    if operation == "turn_start" and not (
        isinstance(host_turn_id, str) and host_turn_id.strip()
    ):
        raise HostGoalError("host_turn_id is required for turn_start")
    binding, checkpoint = _prepare_checkpoint(
        state,
        binding,
        operation=operation,
        required_tool=required_tool,
        target_gate=target_gate,
        host_turn_id=host_turn_id,
        human_decision_id=human_decision_id,
    )
    return binding, {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "operation": operation,
        "required_tool": required_tool,
        "target_gate": target_gate,
        "objective": binding["objective"],
        "objective_sha256": binding["objective_sha256"],
        "host_turn_id": host_turn_id,
        "decision_id": human_decision_id,
    }


def prepare_owner_claim_checkpoint(
    state: dict[str, Any],
    user_message: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare a one-time get_goal observation before coordinator transfer."""
    if user_message.strip() != HOST_GOAL_OWNER_CLAIM_MESSAGE:
        raise HostGoalError(
            "owner claim user_message must exactly authorize Host Goal takeover"
        )
    thread_id = current_codex_thread_id()
    if not thread_id:
        raise HostGoalError(
            "CODEX_THREAD_ID is required for Host Goal owner recovery"
        )
    integrity_errors = journal_integrity_errors(state)
    if integrity_errors:
        raise HostGoalError(
            "Host Goal owner recovery requires an intact journal: "
            + ", ".join(integrity_errors)
        )
    owner = deepcopy(state.get("host_goal_owner") or {})
    if owner.get("delivery_id") not in {None, state.get("delivery_id")}:
        raise HostGoalError("Host Goal owner delivery identity mismatch")
    if owner.get("feature_slug") not in {None, state.get("feature_slug")}:
        raise HostGoalError("Host Goal owner feature identity mismatch")
    if (
        owner.get("status") == "claimed"
        and owner.get("coordinator_thread_id") == thread_id
    ):
        binding = state.get("host_goal_binding") or {}
        if not host_goal_required(state) or binding.get("owner_thread_id") == thread_id:
            raise HostGoalError("current thread already owns the Host Goal lifecycle")

    pending = owner.get("pending_claim") or {}
    if pending:
        if (
            pending.get("candidate_thread_id") == thread_id
            and pending.get("projection_sha256")
            == host_goal_owner_projection_hash(state)
        ):
            return owner, _owner_claim_response(owner, pending)
        raise HostGoalError("an unconsumed Host Goal owner claim already exists")

    transition_sequence, transition_last_event_hash = _journal_position(state)
    binding = state.get("host_goal_binding") or {}
    checkpoint = {
        "checkpoint_id": uuid.uuid4().hex,
        "operation": "inspect_before_owner_claim",
        "required_tool": "get_goal",
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "candidate_thread_id": thread_id,
        "previous_coordinator_thread_id": owner.get("coordinator_thread_id"),
        "owner_generation": int(owner.get("generation") or 0),
        "binding_generation": binding.get("generation"),
        "binding_nonce": binding.get("binding_nonce"),
        "objective_sha256": binding.get("objective_sha256"),
        "transition_sequence": transition_sequence,
        "transition_last_event_hash": transition_last_event_hash,
        "projection_sha256": host_goal_owner_projection_hash(state),
        "user_message_sha256": stable_hash(user_message.strip()),
        "issued_at": _timestamp(),
    }
    owner.setdefault("schema_version", HOST_GOAL_SCHEMA_VERSION)
    owner.setdefault("delivery_id", state.get("delivery_id"))
    owner.setdefault("feature_slug", state.get("feature_slug"))
    owner["pending_claim"] = checkpoint
    return owner, _owner_claim_response(owner, checkpoint)


def apply_owner_claim_observation(
    state: dict[str, Any],
    checkpoint_id: str,
    observation: dict[str, Any],
    *,
    runtime_version: str,
) -> dict[str, Any]:
    """Transfer Host Goal ownership after proving the new thread is replaceable."""
    next_state = deepcopy(state)
    owner = deepcopy(next_state.get("host_goal_owner") or {})
    if checkpoint_id in set(owner.get("superseded_claim_checkpoint_ids") or []):
        raise HostGoalError("Host Goal owner claim checkpoint was superseded")
    checkpoint = owner.get("pending_claim") or {}
    if checkpoint.get("checkpoint_id") != checkpoint_id:
        raise HostGoalError("current Host Goal owner claim checkpoint is required")
    thread_id = current_codex_thread_id()
    if not thread_id:
        raise HostGoalError(
            "CODEX_THREAD_ID is required for Host Goal owner recovery"
        )
    if checkpoint.get("candidate_thread_id") != thread_id:
        raise HostGoalError(
            "Host Goal owner claim belongs to a different coordinator thread"
        )
    _validate_owner_claim_identity(next_state, owner, checkpoint)
    if checkpoint.get("projection_sha256") != host_goal_owner_projection_hash(
        next_state
    ):
        raise HostGoalError("Host Goal owner claim state projection is stale")
    if observation.get("observation_source") != HOST_GOAL_SOURCE:
        raise HostGoalError("Host Goal observation_source must be codex_goal_tool")
    if observation.get("tool") != "get_goal":
        raise HostGoalError("Host Goal owner claim requires get_goal")
    result = observation.get("result")
    if not isinstance(result, dict):
        raise HostGoalError("Host Goal tool result must be an object")
    normalized = normalize_tool_result("get_goal", result)
    if normalized["status"] == "blocked":
        raise HostGoalError(
            "candidate coordinator thread has a blocked Host Goal and cannot take ownership"
        )
    if normalized["status"] == "active":
        raise HostGoalError(
            "candidate coordinator thread has an active Host Goal and cannot take ownership"
        )
    if normalized["status"] == "complete":
        _validate_observed_goal_thread(normalized, thread_id)

    original_owner = deepcopy(owner)
    original_binding = deepcopy(next_state.get("host_goal_binding") or {})
    resume_gate = _owner_transfer_resume_gate(next_state, original_owner, original_binding)
    observed_record = {
        "checkpoint_id": checkpoint_id,
        "operation": checkpoint["operation"],
        "tool": "get_goal",
        "status": normalized["status"],
        "host_identifiers": normalized.get("host_identifiers") or {},
        "result_sha256": stable_hash(result),
        "observed_at": _timestamp(),
    }

    archived_binding_exists = original_binding.get("status") not in {
        None,
        "not_required",
    }
    if archived_binding_exists:
        binding_history = list(next_state.get("host_goal_binding_history") or [])
        binding_history.append(
            {
                "binding": original_binding,
                "archived_at": _timestamp(),
                "reason": "host_goal_owner_transferred",
                "disposition": "orphaned_unreachable",
                "replacement_owner_thread_id": thread_id,
            }
        )
        next_state["host_goal_binding_history"] = binding_history
    owner_history = list(next_state.get("host_goal_owner_history") or [])
    owner_history.append(
        {
            "owner": original_owner,
            "archived_at": _timestamp(),
            "reason": "host_goal_owner_transferred",
            "claim_observation": observed_record,
        }
    )
    next_state["host_goal_owner_history"] = owner_history

    authorization = next_state.get("host_goal_authorization") or {}
    if authorization.get("status") != "authorized":
        confirmation = (next_state.get("user_confirmations") or {}).get(
            "test_coverage_plan"
        ) or {}
        authorization = build_host_goal_authorization(next_state, confirmation)
        authorization.update(
            {
                "authorization_source": "explicit_host_goal_owner_transfer",
                "recovery_message_sha256": checkpoint[
                    "user_message_sha256"
                ],
            }
        )
        next_state["host_goal_authorization"] = authorization

    new_owner = {
        "schema_version": HOST_GOAL_SCHEMA_VERSION,
        "status": "claimed",
        "delivery_id": next_state.get("delivery_id"),
        "feature_slug": next_state.get("feature_slug"),
        "coordinator_thread_id": thread_id,
        "generation": int(original_owner.get("generation") or 0) + 1,
        "claim_source": "explicit_owner_transfer",
        "claim_checkpoint_id": checkpoint_id,
        "claim_observation_sha256": stable_hash(observed_record),
        "previous_binding_disposition": "orphaned_unreachable",
        "claimed_at": _timestamp(),
        "pending_claim": None,
    }
    next_state["host_goal_owner"] = new_owner
    if host_goal_required(next_state):
        next_state["host_goal_binding"] = _new_host_goal_binding(
            next_state,
            owner_thread_id=thread_id,
            previous_binding=original_binding,
            resume_gate=resume_gate,
        )
        next_state["next_gate"] = "host_goal_activation"
    else:
        next_state["host_goal_binding"] = {"status": "not_required"}

    next_state = append_transition(
        next_state,
        "host_goal_owner_transferred",
        feature_slug=next_state.get("feature_slug"),
        runtime_version=runtime_version,
        input_artifact_hashes={
            "previous_owner": stable_hash(original_owner),
            "previous_binding": stable_hash(original_binding),
            "owner_claim_observation": stable_hash(observed_record),
        },
        output_artifact_hashes={
            "host_goal_owner": stable_hash(new_owner),
            "host_goal_binding": stable_hash(
                next_state.get("host_goal_binding") or {}
            ),
        },
        metadata={
            "previous_coordinator_thread_id": original_owner.get(
                "coordinator_thread_id"
            ),
            "previous_observed_thread_id": (
                original_binding.get("host_identifiers") or {}
            ).get("threadId"),
            "new_coordinator_thread_id": thread_id,
            "previous_binding_generation": original_binding.get("generation"),
            "new_binding_generation": (
                next_state.get("host_goal_binding") or {}
            ).get("generation"),
            "resume_gate": resume_gate,
        },
    )
    return next_state


def recover_stale_owner_claim_checkpoint(
    state: dict[str, Any],
    checkpoint_id: str,
    *,
    runtime_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Archive and replace one stale coordinator owner-claim checkpoint."""
    next_state = deepcopy(state)
    owner = deepcopy(next_state.get("host_goal_owner") or {})
    pending = owner.get("pending_claim") or {}
    superseded_ids = list(owner.get("superseded_claim_checkpoint_ids") or [])
    if checkpoint_id in superseded_ids:
        current = owner.get("pending_claim") or {}
        if (
            current.get("projection_sha256")
            != host_goal_owner_projection_hash(next_state)
        ):
            raise HostGoalError(
                "replacement Host Goal owner claim is stale; recover its checkpoint ID"
            )
        response = _owner_claim_response(owner, current)
        response.update(
            {
                "recovery_status": "already_recovered",
                "superseded_checkpoint_id": checkpoint_id,
            }
        )
        return next_state, response
    if pending.get("checkpoint_id") != checkpoint_id:
        raise HostGoalError("current Host Goal owner claim checkpoint is required")
    thread_id = current_codex_thread_id()
    if not thread_id:
        raise HostGoalError(
            "CODEX_THREAD_ID is required for Host Goal owner recovery"
        )
    if pending.get("candidate_thread_id") != thread_id:
        raise HostGoalError(
            "Host Goal owner claim belongs to a different coordinator thread"
        )
    _validate_owner_claim_identity(next_state, owner, pending)
    stored_projection = str(pending.get("projection_sha256") or "")
    current_projection = host_goal_owner_projection_hash(next_state)
    if stored_projection == current_projection:
        raise HostGoalError("Host Goal owner claim is current and cannot be recovered")
    journal = next_state.get("transition_journal") or {}
    intervening_events, transition_range_basis = _intervening_transition_events(
        pending,
        journal.get("events") or [],
    )
    if not intervening_events:
        raise HostGoalError(
            "stale Host Goal owner claim requires an intervening transition"
        )
    archive = {
        "checkpoint": deepcopy(pending),
        "reason": "stale_host_goal_owner_claim",
        "stored_projection_sha256": stored_projection,
        "current_projection_sha256": current_projection,
        "intervening_transition_start": int(intervening_events[0]["sequence"]),
        "intervening_transition_end": int(intervening_events[-1]["sequence"]),
        "intervening_transition_range_basis": transition_range_basis,
        "recovery_runtime_version": runtime_version,
        "archived_at": _timestamp(),
    }
    history = list(owner.get("claim_checkpoint_history") or [])
    history.append(archive)
    owner["claim_checkpoint_history"] = history[-100:]
    superseded_ids.append(checkpoint_id)
    owner["superseded_claim_checkpoint_ids"] = superseded_ids[-100:]
    owner["pending_claim"] = None
    next_state["host_goal_owner"] = owner
    next_state = append_transition(
        next_state,
        "host_goal_owner_claim_superseded",
        feature_slug=next_state.get("feature_slug"),
        runtime_version=runtime_version,
        input_artifact_hashes={"owner_claim_checkpoint": stable_hash(pending)},
        output_artifact_hashes={"owner_claim_archive": stable_hash(archive)},
        metadata={
            "checkpoint_id": checkpoint_id,
            "candidate_thread_id": thread_id,
            "stored_projection_sha256": stored_projection,
            "current_projection_sha256": current_projection,
        },
    )
    replacement_owner, response = prepare_owner_claim_checkpoint(
        next_state,
        HOST_GOAL_OWNER_CLAIM_MESSAGE,
    )
    next_state["host_goal_owner"] = replacement_owner
    response.update(
        {
            "recovery_status": "recovered",
            "superseded_checkpoint_id": checkpoint_id,
        }
    )
    return next_state, response


def apply_host_goal_observation(
    state: dict[str, Any],
    checkpoint_id: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Consume one checkpoint and apply an actual Codex Goal tool result."""
    next_state = deepcopy(state)
    owner_thread_id = assert_host_goal_owner(next_state)
    binding = deepcopy(next_state.get("host_goal_binding") or {})
    consumed = list(binding.get("consumed_checkpoint_ids") or [])
    if checkpoint_id in set(binding.get("superseded_checkpoint_ids") or []):
        raise HostGoalError("Host Goal checkpoint was superseded")
    if checkpoint_id in consumed:
        raise HostGoalError("Host Goal checkpoint was already consumed")
    checkpoint = binding.get("pending_checkpoint") or {}
    if checkpoint.get("checkpoint_id") != checkpoint_id:
        raise HostGoalError("current Host Goal checkpoint is required")
    if checkpoint.get("binding_generation") != binding.get("generation"):
        raise HostGoalError("Host Goal checkpoint binding generation is stale")
    if checkpoint.get("coordinator_thread_id") != owner_thread_id:
        raise HostGoalError("Host Goal checkpoint coordinator thread is stale")
    if checkpoint.get("projection_sha256") != goal_state_projection_hash(
        next_state, binding=binding
    ):
        raise HostGoalError("Host Goal checkpoint state projection is stale")
    if observation.get("observation_source") != HOST_GOAL_SOURCE:
        raise HostGoalError("Host Goal observation_source must be codex_goal_tool")
    tool = str(observation.get("tool") or "")
    if tool != checkpoint.get("required_tool"):
        raise HostGoalError(
            f"Host Goal checkpoint requires {checkpoint.get('required_tool')}"
        )
    availability_status = observation.get("availability_status")
    if availability_status is not None:
        if availability_status != "unavailable":
            raise HostGoalError(
                "Host Goal availability_status must be unavailable when present"
            )
        consumed.append(checkpoint_id)
        binding["consumed_checkpoint_ids"] = consumed[-100:]
        binding["pending_checkpoint"] = None
        record = {
            "checkpoint_id": checkpoint_id,
            "operation": str(checkpoint.get("operation") or ""),
            "tool": tool,
            "status": "unavailable",
            "error_type": str(observation.get("error_type") or "unknown"),
            "error_sha256": stable_hash(
                str(observation.get("error_message") or "")
            ),
            "observed_at": _timestamp(),
        }
        observations = list(binding.get("observations") or [])
        observations.append(record)
        binding["observations"] = observations[-200:]
        binding["last_observed_status"] = "unavailable"
        binding["last_observation_sha256"] = stable_hash(record)
        binding["last_observed_at"] = record["observed_at"]
        binding["status"] = "unavailable"
        binding["unavailable_observation"] = record
        next_state["host_goal_binding"] = binding
        next_state["next_gate"] = "use_goal_capable_codex_host"
        return next_state
    result = observation.get("result")
    if not isinstance(result, dict):
        raise HostGoalError("Host Goal tool result must be an object")
    normalized = normalize_tool_result(tool, result)
    operation = str(checkpoint.get("operation") or "")
    _validate_observed_goal_thread(normalized, owner_thread_id)
    _validate_observed_goal(binding, normalized, operation)

    consumed.append(checkpoint_id)
    binding["consumed_checkpoint_ids"] = consumed[-100:]
    binding["pending_checkpoint"] = None
    record = {
        "checkpoint_id": checkpoint_id,
        "operation": operation,
        "tool": tool,
        "status": normalized["status"],
        "objective": normalized.get("objective"),
        "host_identifiers": normalized.get("host_identifiers", {}),
        "result_sha256": stable_hash(result),
        "observed_at": _timestamp(),
    }
    observations = list(binding.get("observations") or [])
    observations.append(record)
    binding["observations"] = observations[-200:]
    binding["last_observed_status"] = normalized["status"]
    binding["last_observation_sha256"] = stable_hash(record)
    binding["last_observed_at"] = record["observed_at"]

    if operation == "inspect_before_activation":
        if normalized["status"] == "missing":
            binding["status"] = "creation_ready"
        elif normalized["status"] == "active":
            _mark_active(binding, normalized)
    elif operation == "create_goal":
        binding["status"] = "verification_pending"
        binding["host_identifiers"] = dict(
            normalized.get("host_identifiers") or {}
        )
        binding["create_observation_sha256"] = stable_hash(record)
    elif operation == "verify_activation":
        _mark_active(binding, normalized)
    elif operation == "complete_goal":
        binding["status"] = "completion_verification_pending"
        binding["completion_update_observation_sha256"] = stable_hash(record)
    elif operation == "verify_completion":
        binding["status"] = "complete"
        binding["completed_at"] = _timestamp()
        next_state["status"] = "closed"
        next_state["stage"] = "feature_closure_passed"
        next_state["next_gate"] = "plugin_packaging"
    elif operation == "turn_start":
        if normalized["status"] == "blocked":
            binding["status"] = "blocked"
            next_state["next_gate"] = "host_goal_resume_required"
        elif normalized["status"] != "active":
            binding["status"] = "reactivation_required"
            binding["reactivation_reason"] = f"observed_{normalized['status']}"
            next_state["next_gate"] = "host_goal_reactivation_authorization"
        elif checkpoint.get("human_decision_id"):
            _record_human_wait_turn(binding, checkpoint)
        else:
            _reset_human_wait_episode(binding)
    elif operation == "block_goal":
        binding["status"] = "blocked"
        binding["blocked_at"] = _timestamp()
        next_state["next_gate"] = "host_goal_resume_required"
    elif operation == "user_resume":
        if normalized["status"] == "active":
            _mark_active(binding, normalized)
            human_wait = deepcopy(binding.get("human_wait") or {})
            human_wait["status"] = "resolved"
            human_wait["resolved_at"] = _timestamp()
            fingerprint = human_wait.get("blocker_fingerprint")
            resolved = list(binding.get("resolved_decision_fingerprints") or [])
            if fingerprint and fingerprint not in resolved:
                resolved.append(fingerprint)
            binding["resolved_decision_fingerprints"] = resolved[-100:]
            binding["human_wait"] = human_wait
            resolvable_blockers = set(
                str(item)
                for item in human_wait.get("resolvable_blockers") or []
            )
            if resolvable_blockers:
                next_state["blocked_until"] = [
                    blocker
                    for blocker in next_state.get("blocked_until") or []
                    if str(blocker) not in resolvable_blockers
                ]
            next_state["next_gate"] = checkpoint.get("target_gate")
            binding["authorized_transition"] = {
                "checkpoint_id": checkpoint_id,
                "operation": operation,
                "target_gate": checkpoint.get("target_gate"),
                "observation_sha256": stable_hash(record),
                "authorized_at": _timestamp(),
            }
        elif normalized["status"] == "blocked":
            binding["status"] = "blocked"
            next_state["next_gate"] = "host_goal_resume_required"
        else:
            binding["status"] = "reactivation_required"
            binding["reactivation_reason"] = f"observed_{normalized['status']}"
            next_state["next_gate"] = "host_goal_reactivation_authorization"
    elif operation in {
        "stage_transition",
        "pre_complete",
        "stop_delivery",
    }:
        if normalized["status"] == "blocked":
            binding["status"] = "blocked"
            next_state["next_gate"] = "host_goal_resume_required"
        elif normalized["status"] != "active":
            binding["status"] = "reactivation_required"
            binding["reactivation_reason"] = f"observed_{normalized['status']}"
            next_state["next_gate"] = "host_goal_reactivation_authorization"
        else:
            binding["authorized_transition"] = {
                "checkpoint_id": checkpoint_id,
                "operation": operation,
                "target_gate": checkpoint.get("target_gate"),
                "observation_sha256": stable_hash(record),
                "authorized_at": _timestamp(),
            }

    next_state["host_goal_binding"] = binding
    if binding.get("status") == "active" and operation in {
        "inspect_before_activation",
        "verify_activation",
    }:
        next_state["next_gate"] = binding.get("resume_gate") or _delivery_goal_next_gate(
            next_state
        )
    return next_state


def recover_stale_activation_checkpoint(
    state: dict[str, Any],
    checkpoint_id: str,
    *,
    runtime_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Archive and replace one stale pre-active activation checkpoint."""
    next_state = deepcopy(state)
    assert_host_goal_owner(next_state)
    binding = deepcopy(next_state.get("host_goal_binding") or {})
    if binding.get("ever_active") or binding.get("status") == "active":
        raise HostGoalError("Host Goal binding has already been active")

    journal = next_state.get("transition_journal")
    if not isinstance(journal, dict):
        raise HostGoalError("Host Goal checkpoint recovery requires a valid journal")
    integrity_errors = journal_integrity_errors(next_state)
    if integrity_errors:
        raise HostGoalError(
            "Host Goal checkpoint recovery requires an intact journal: "
            + ", ".join(integrity_errors)
        )

    superseded_ids = list(binding.get("superseded_checkpoint_ids") or [])
    if checkpoint_id in superseded_ids:
        pending = binding.get("pending_checkpoint") or {}
        _validate_recovery_identity(next_state, binding, pending)
        return _idempotent_recovery_response(next_state, binding, checkpoint_id)

    pending = binding.get("pending_checkpoint") or {}
    if pending.get("checkpoint_id") != checkpoint_id:
        raise HostGoalError("current Host Goal checkpoint is required for recovery")
    if pending.get("operation") not in ACTIVATION_OPERATIONS:
        raise HostGoalError("only an activation lifecycle checkpoint can be recovered")
    if pending.get("target_gate") != "host_goal_activation":
        raise HostGoalError("Host Goal checkpoint target gate is not activation")

    _validate_recovery_identity(next_state, binding, pending)

    stored_projection = str(pending.get("projection_sha256") or "")
    current_projection = goal_state_projection_hash(next_state, binding=binding)
    if stored_projection == current_projection:
        raise HostGoalError("Host Goal checkpoint is current and cannot be recovered")

    current_sequence, current_last_event_hash = _journal_position(next_state)
    reported_sequence = _checkpoint_transition_sequence(pending)
    intervening_events, transition_range_basis = _intervening_transition_events(
        pending,
        journal.get("events") or [],
    )
    if not intervening_events:
        raise HostGoalError(
            "stale Host Goal checkpoint requires an intervening transition"
        )
    resume_gate = str(next_state.get("next_gate") or "")
    if not resume_gate or resume_gate == "host_goal_activation":
        resume_gate = str(
            binding.get("resume_gate") or _delivery_goal_next_gate(next_state)
        )
    if not resume_gate:
        raise HostGoalError("Host Goal recovery resume gate is unavailable")
    replacement_checkpoint_id = uuid.uuid4().hex
    archive = {
        "checkpoint": deepcopy(pending),
        "reason": "stale_activation_checkpoint",
        "stored_projection_sha256": stored_projection,
        "current_projection_sha256": current_projection,
        "checkpoint_transition_sequence": reported_sequence,
        "current_transition_sequence": current_sequence,
        "current_transition_last_event_hash": current_last_event_hash,
        "intervening_transition_start": (
            int(intervening_events[0]["sequence"]) if intervening_events else None
        ),
        "intervening_transition_end": (
            int(intervening_events[-1]["sequence"]) if intervening_events else None
        ),
        "intervening_runtime_versions": sorted(
            {
                str(event.get("runtime_version") or "")
                for event in intervening_events
                if str(event.get("runtime_version") or "")
            }
        ),
        "intervening_transition_range_basis": transition_range_basis,
        "checkpoint_runtime_version": str(
            pending.get("runtime_version")
            or next_state.get("runtime_version")
            or next_state.get("plugin_version")
            or ""
        ),
        "recovery_runtime_version": runtime_version,
        "previous_resume_gate": binding.get("resume_gate"),
        "replacement_resume_gate": resume_gate,
        "archived_at": _timestamp(),
        "replacement_checkpoint_id": replacement_checkpoint_id,
    }
    history = list(binding.get("checkpoint_history") or [])
    history.append(archive)
    binding["checkpoint_history"] = history
    superseded_ids.append(checkpoint_id)
    binding["superseded_checkpoint_ids"] = superseded_ids[-200:]
    binding["status"] = "activation_pending"
    binding["resume_gate"] = resume_gate
    binding["pending_checkpoint"] = None
    binding["authorized_transition"] = None
    next_state["host_goal_binding"] = binding
    next_state["next_gate"] = "host_goal_activation"

    next_state = append_transition(
        next_state,
        "host_goal_checkpoint_superseded",
        feature_slug=next_state.get("feature_slug"),
        runtime_version=runtime_version,
        input_artifact_hashes={"checkpoint": stable_hash(pending)},
        output_artifact_hashes={"checkpoint_archive": stable_hash(archive)},
        metadata={
            "checkpoint_id": checkpoint_id,
            "operation": pending.get("operation"),
            "stored_projection_sha256": stored_projection,
            "current_projection_sha256": current_projection,
            "checkpoint_transition_sequence": reported_sequence,
            "current_transition_sequence": current_sequence,
        },
    )
    binding, replacement = _prepare_checkpoint(
        next_state,
        binding,
        operation="inspect_before_activation",
        required_tool="get_goal",
        target_gate="host_goal_activation",
        checkpoint_id=replacement_checkpoint_id,
    )
    next_state["host_goal_binding"] = binding
    response = _activation_response(binding, replacement)
    response.update(
        {
            "recovery_status": "recovered",
            "superseded_checkpoint_id": checkpoint_id,
        }
    )
    return next_state, response


def consume_authorized_transition(
    state: dict[str, Any],
    *,
    allowed_operations: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Consume the one fresh Goal observation authorizing the current gate."""
    next_state = deepcopy(state)
    assert_host_goal_owner(next_state)
    binding = deepcopy(next_state.get("host_goal_binding") or {})
    if binding.get("status") != "active":
        raise HostGoalError("active Host Goal binding is required for post-handoff progress")
    transition = binding.get("authorized_transition") or {}
    if not transition:
        raise HostGoalError(
            "fresh Host Goal reconciliation is required for post-handoff progress"
        )
    if transition.get("target_gate") != next_state.get("next_gate"):
        raise HostGoalError("Host Goal reconciliation target gate is stale")
    permitted = allowed_operations or CANONICAL_TRANSITION_OPERATIONS
    if transition.get("operation") not in permitted:
        raise HostGoalError(
            "Host Goal reconciliation operation cannot authorize this transition"
        )
    binding["last_consumed_transition"] = {
        **transition,
        "consumed_at": _timestamp(),
    }
    binding["authorized_transition"] = None
    next_state["host_goal_binding"] = binding
    return next_state


def goal_state_projection_hash(
    state: dict[str, Any],
    *,
    binding: dict[str, Any] | None = None,
) -> str:
    """Hash only Goal-relevant canonical state, excluding display timestamps."""
    current = binding or state.get("host_goal_binding") or {}
    goal = state.get("delivery_goal") or {}
    authorization = state.get("host_goal_authorization") or {}
    owner = state.get("host_goal_owner") or {}
    transition_sequence, transition_last_event_hash = _journal_position(state)
    projection = {
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "launch_package_hash": goal.get("launch_package_hash"),
        "authorization_hash": authorization.get("authorization_hash"),
        "owner_generation": owner.get("generation"),
        "coordinator_thread_id": owner.get("coordinator_thread_id"),
        "binding_owner_thread_id": current.get("owner_thread_id"),
        "binding_observed_thread_id": (
            current.get("host_identifiers") or {}
        ).get("threadId"),
        "binding_generation": current.get("generation"),
        "binding_nonce": current.get("binding_nonce"),
        "objective_sha256": current.get("objective_sha256"),
        "binding_status": current.get("status"),
        "next_gate": state.get("next_gate"),
        "delivery_goal_status": goal.get("status"),
        "current_task_cursor": goal.get("current_task_cursor"),
        "transition_sequence": transition_sequence,
        "transition_last_event_hash": transition_last_event_hash,
        "pending_decision_id": (
            (current.get("human_wait") or {}).get("decision_id")
        ),
    }
    return stable_hash(projection)


def canonical_closure_passed(state: dict[str, Any]) -> bool:
    """Return whether Waygate's canonical closure facts are complete."""
    return bool(
        (state.get("closure_validation") or {}).get("status") == "passed"
        and (state.get("feature_closure") or {}).get("status") == "passed"
        and (state.get("delivery_goal") or {}).get("status") == "complete"
    )


def normalize_tool_result(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the Goal shape returned by create_goal/get_goal/update_goal."""
    goal = result.get("goal")
    if goal is None:
        return {"status": "missing", "objective": None, "host_identifiers": {}}
    if not isinstance(goal, dict):
        raise HostGoalError(f"{tool} result.goal must be an object or null")
    status = str(goal.get("status") or "")
    if status not in {"active", "blocked", "complete"}:
        raise HostGoalError(f"unsupported Host Goal status: {status}")
    objective = goal.get("objective")
    identifiers = {
        key: goal[key]
        for key in ("threadId", "goalId", "id")
        if isinstance(goal.get(key), str) and goal.get(key)
    }
    return {
        "status": status,
        "objective": objective,
        "host_identifiers": identifiers,
    }


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def host_goal_owner_projection_hash(state: dict[str, Any]) -> str:
    """Hash canonical facts that an owner-claim checkpoint is allowed to bind."""
    owner = state.get("host_goal_owner") or {}
    binding = state.get("host_goal_binding") or {}
    transition_sequence, transition_last_event_hash = _journal_position(state)
    return stable_hash(
        {
            "delivery_id": state.get("delivery_id"),
            "feature_slug": state.get("feature_slug"),
            "owner_status": owner.get("status"),
            "owner_generation": owner.get("generation"),
            "coordinator_thread_id": owner.get("coordinator_thread_id"),
            "binding_generation": binding.get("generation"),
            "binding_nonce": binding.get("binding_nonce"),
            "binding_status": binding.get("status"),
            "binding_owner_thread_id": binding.get("owner_thread_id"),
            "binding_observed_thread_id": (
                binding.get("host_identifiers") or {}
            ).get("threadId"),
            "binding_objective_sha256": binding.get("objective_sha256"),
            "binding_pending_checkpoint_sha256": stable_hash(
                binding.get("pending_checkpoint") or {}
            ),
            "next_gate": state.get("next_gate"),
            "transition_sequence": transition_sequence,
            "transition_last_event_hash": transition_last_event_hash,
        }
    )


def _new_host_goal_binding(
    state: dict[str, Any],
    *,
    owner_thread_id: str,
    previous_binding: dict[str, Any] | None = None,
    resume_gate: str | None = None,
) -> dict[str, Any]:
    authorization = state.get("host_goal_authorization") or {}
    if authorization.get("status") != "authorized":
        raise HostGoalError("Host Goal authorization is required before activation")
    goal = state.get("delivery_goal") or {}
    launch_hash = str(goal.get("launch_package_hash") or "")
    if not launch_hash:
        raise HostGoalError("launch package hash is required for Host Goal activation")
    previous = previous_binding or {}
    generation = int(previous.get("generation") or 0) + 1
    binding_nonce = uuid.uuid4().hex
    objective = build_host_goal_objective(
        delivery_id=str(state.get("delivery_id") or ""),
        feature_slug=str(state.get("feature_slug") or ""),
        launch_package_hash=launch_hash,
        binding_nonce=binding_nonce,
    )
    return {
        "schema_version": HOST_GOAL_SCHEMA_VERSION,
        "status": "activation_pending",
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "launch_package_hash": launch_hash,
        "authorization_hash": authorization.get("authorization_hash"),
        "owner_thread_id": owner_thread_id,
        "generation": generation,
        "binding_nonce": binding_nonce,
        "objective": objective,
        "objective_sha256": stable_hash(objective),
        "resume_gate": resume_gate or _delivery_goal_next_gate(state),
        "ever_active": False,
        "pending_checkpoint": None,
        "consumed_checkpoint_ids": [],
        "observations": [],
        "created_at": _timestamp(),
    }


def _owner_claim_response(
    owner: dict[str, Any], checkpoint: dict[str, Any]
) -> dict[str, Any]:
    return {
        "status": owner.get("status"),
        "checkpoint_id": checkpoint["checkpoint_id"],
        "operation": checkpoint["operation"],
        "required_tool": checkpoint["required_tool"],
        "candidate_thread_id": checkpoint["candidate_thread_id"],
    }


def _validate_owner_claim_identity(
    state: dict[str, Any],
    owner: dict[str, Any],
    checkpoint: dict[str, Any],
) -> None:
    identities = {
        "delivery": (checkpoint.get("delivery_id"), state.get("delivery_id")),
        "feature": (checkpoint.get("feature_slug"), state.get("feature_slug")),
        "owner generation": (
            checkpoint.get("owner_generation"),
            int(owner.get("generation") or 0),
        ),
    }
    binding = state.get("host_goal_binding") or {}
    if binding:
        identities.update(
            {
                "binding generation": (
                    checkpoint.get("binding_generation"),
                    binding.get("generation"),
                ),
                "binding nonce": (
                    checkpoint.get("binding_nonce"),
                    binding.get("binding_nonce"),
                ),
                "objective": (
                    checkpoint.get("objective_sha256"),
                    binding.get("objective_sha256"),
                ),
            }
        )
    for label, (checkpoint_value, current_value) in identities.items():
        if checkpoint_value != current_value:
            raise HostGoalError(f"Host Goal owner claim {label} identity mismatch")
    if owner.get("delivery_id") not in {None, state.get("delivery_id")}:
        raise HostGoalError("Host Goal owner delivery identity mismatch")
    if owner.get("feature_slug") not in {None, state.get("feature_slug")}:
        raise HostGoalError("Host Goal owner feature identity mismatch")
    integrity_errors = journal_integrity_errors(state)
    if integrity_errors:
        raise HostGoalError(
            "Host Goal owner recovery requires an intact journal: "
            + ", ".join(integrity_errors)
        )


def _owner_transfer_resume_gate(
    state: dict[str, Any],
    owner: dict[str, Any],
    binding: dict[str, Any],
) -> str:
    pending_target = str(
        (binding.get("pending_checkpoint") or {}).get("target_gate") or ""
    )
    candidates = (
        pending_target,
        str(binding.get("resume_gate") or ""),
        str(owner.get("resume_gate") or ""),
        str(state.get("next_gate") or ""),
        _delivery_goal_next_gate(state),
    )
    for candidate in candidates:
        if candidate and candidate not in {
            "host_goal_activation",
            "host_goal_recovery",
            "host_goal_owner_recovery",
            "host_goal_reactivation_authorization",
        }:
            return candidate
    raise HostGoalError("Host Goal owner transfer resume gate is unavailable")


def _prepare_checkpoint(
    state: dict[str, Any],
    binding: dict[str, Any],
    *,
    operation: str,
    required_tool: str,
    target_gate: str,
    host_turn_id: str | None = None,
    human_decision_id: str | None = None,
    checkpoint_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = binding.get("pending_checkpoint")
    if pending:
        if (
            pending.get("operation") == operation
            and pending.get("target_gate") == target_gate
        ):
            return binding, pending
        raise HostGoalError("an unconsumed Host Goal checkpoint already exists")
    transition_sequence, transition_last_event_hash = _journal_position(state)
    checkpoint = {
        "checkpoint_id": checkpoint_id or uuid.uuid4().hex,
        "operation": operation,
        "required_tool": required_tool,
        "target_gate": target_gate,
        "delivery_id": state.get("delivery_id"),
        "feature_slug": state.get("feature_slug"),
        "binding_generation": binding.get("generation"),
        "binding_nonce": binding.get("binding_nonce"),
        "objective_sha256": binding.get("objective_sha256"),
        "owner_generation": (state.get("host_goal_owner") or {}).get(
            "generation"
        ),
        "coordinator_thread_id": (state.get("host_goal_owner") or {}).get(
            "coordinator_thread_id"
        ),
        "transition_sequence": transition_sequence,
        "transition_last_event_hash": transition_last_event_hash,
        "projection_sha256": goal_state_projection_hash(state, binding=binding),
        "host_turn_id": host_turn_id,
        "human_decision_id": human_decision_id,
        "issued_at": _timestamp(),
    }
    binding["pending_checkpoint"] = checkpoint
    return binding, checkpoint


def _journal_position(state: dict[str, Any]) -> tuple[int, str]:
    journal = state.get("transition_journal") or {}
    if not isinstance(journal, dict):
        return 0, ""
    events = journal.get("events") or []
    if not isinstance(events, list):
        return 0, str(journal.get("last_event_hash") or "")
    return len(events), str(journal.get("last_event_hash") or "")


def _checkpoint_transition_sequence(checkpoint: dict[str, Any]) -> int:
    value = checkpoint.get("transition_sequence")
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _intervening_transition_events(
    checkpoint: dict[str, Any],
    events: list[Any],
) -> tuple[list[dict[str, Any]], str]:
    reported_sequence = _checkpoint_transition_sequence(checkpoint)
    if "transition_last_event_hash" in checkpoint:
        checkpoint_last_hash = checkpoint.get("transition_last_event_hash")
        if reported_sequence == 0:
            trustworthy_position = checkpoint_last_hash == ""
        else:
            trustworthy_position = any(
                isinstance(event, dict)
                and event.get("sequence") == reported_sequence
                and event.get("event_hash") == checkpoint_last_hash
                for event in events
            )
        if not trustworthy_position:
            raise HostGoalError(
                "Host Goal checkpoint transition identity does not match journal"
            )
        return (
            [
                event
                for event in events
                if isinstance(event, dict)
                and int(event.get("sequence") or 0) > reported_sequence
            ],
            "checkpoint_last_event_hash",
        )

    issued_at = _parse_timestamp(checkpoint.get("issued_at"))
    if issued_at is None:
        raise HostGoalError(
            "legacy Host Goal checkpoint requires a valid issued_at timestamp"
        )
    dated_events = []
    for event in events:
        if not isinstance(event, dict):
            raise HostGoalError("Host Goal checkpoint journal event is invalid")
        occurred_at = _parse_timestamp(event.get("occurred_at"))
        if occurred_at is None:
            raise HostGoalError(
                "legacy Host Goal checkpoint requires journal event timestamps"
            )
        if occurred_at == issued_at:
            raise HostGoalError(
                "legacy Host Goal checkpoint transition range is ambiguous"
            )
        if occurred_at > issued_at:
            dated_events.append(event)
    return dated_events, "checkpoint_issued_at"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _validate_recovery_identity(
    state: dict[str, Any],
    binding: dict[str, Any],
    checkpoint: dict[str, Any],
) -> None:
    authorization = state.get("host_goal_authorization") or {}
    if authorization.get("status") != "authorized":
        raise HostGoalError("current Host Goal authorization is required")
    confirmation = (state.get("user_confirmations") or {}).get(
        "test_coverage_plan"
    ) or {}
    expected_authorization = build_host_goal_authorization(state, confirmation)
    if authorization.get("authorization_hash") != expected_authorization.get(
        "authorization_hash"
    ):
        raise HostGoalError("Host Goal canonical authorization does not match state")
    identities = {
        "delivery": (checkpoint.get("delivery_id"), state.get("delivery_id")),
        "feature": (checkpoint.get("feature_slug"), state.get("feature_slug")),
        "binding generation": (
            checkpoint.get("binding_generation"),
            binding.get("generation"),
        ),
        "binding nonce": (
            checkpoint.get("binding_nonce"),
            binding.get("binding_nonce"),
        ),
        "objective": (
            checkpoint.get("objective_sha256"),
            binding.get("objective_sha256"),
        ),
        "coordinator thread": (
            checkpoint.get("coordinator_thread_id"),
            (state.get("host_goal_owner") or {}).get("coordinator_thread_id"),
        ),
    }
    for label, (checkpoint_value, current_value) in identities.items():
        if checkpoint_value != current_value:
            raise HostGoalError(f"Host Goal checkpoint {label} identity mismatch")
    if binding.get("delivery_id") != state.get("delivery_id"):
        raise HostGoalError("Host Goal binding delivery identity mismatch")
    if binding.get("feature_slug") != state.get("feature_slug"):
        raise HostGoalError("Host Goal binding feature identity mismatch")
    if binding.get("authorization_hash") != authorization.get("authorization_hash"):
        raise HostGoalError("Host Goal binding authorization identity mismatch")
    if authorization.get("delivery_id") != state.get("delivery_id"):
        raise HostGoalError("Host Goal authorization delivery identity mismatch")
    if authorization.get("feature_slug") != state.get("feature_slug"):
        raise HostGoalError("Host Goal authorization feature identity mismatch")
    goal = state.get("delivery_goal") or {}
    if binding.get("launch_package_hash") != goal.get("launch_package_hash"):
        raise HostGoalError("Host Goal binding launch package identity mismatch")
    expected_objective = build_host_goal_objective(
        delivery_id=str(state.get("delivery_id") or ""),
        feature_slug=str(state.get("feature_slug") or ""),
        launch_package_hash=str(goal.get("launch_package_hash") or ""),
        binding_nonce=str(binding.get("binding_nonce") or ""),
    )
    if binding.get("objective") != expected_objective:
        raise HostGoalError("Host Goal canonical objective does not match state")
    if stable_hash(binding.get("objective")) != binding.get("objective_sha256"):
        raise HostGoalError("Host Goal binding objective hash is invalid")


def _idempotent_recovery_response(
    state: dict[str, Any],
    binding: dict[str, Any],
    checkpoint_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    history = list(binding.get("checkpoint_history") or [])
    archive = next(
        (
            item
            for item in reversed(history)
            if (item.get("checkpoint") or {}).get("checkpoint_id") == checkpoint_id
        ),
        None,
    )
    pending = binding.get("pending_checkpoint") or {}
    if not archive or pending.get("checkpoint_id") != archive.get(
        "replacement_checkpoint_id"
    ):
        raise HostGoalError("superseded Host Goal checkpoint is no longer recoverable")
    _validate_idempotent_recovery_evidence(
        state,
        binding,
        archive,
        pending,
        checkpoint_id,
    )
    if pending.get("projection_sha256") != goal_state_projection_hash(
        state, binding=binding
    ):
        raise HostGoalError(
            "replacement Host Goal checkpoint is stale; recover its checkpoint ID"
        )
    response = _activation_response(binding, pending)
    response.update(
        {
            "recovery_status": "already_recovered",
            "superseded_checkpoint_id": checkpoint_id,
        }
    )
    return state, response


def _validate_idempotent_recovery_evidence(
    state: dict[str, Any],
    binding: dict[str, Any],
    archive: dict[str, Any],
    pending: dict[str, Any],
    superseded_checkpoint_id: str,
) -> None:
    if binding.get("status") != "activation_pending":
        raise HostGoalError(
            "Host Goal replacement checkpoint lifecycle status is invalid"
        )
    expected_lifecycle = {
        "operation": "inspect_before_activation",
        "required_tool": "get_goal",
        "target_gate": "host_goal_activation",
        "host_turn_id": None,
        "human_decision_id": None,
    }
    if any(pending.get(key) != value for key, value in expected_lifecycle.items()):
        raise HostGoalError("Host Goal replacement checkpoint lifecycle is invalid")
    transition_sequence, transition_last_event_hash = _journal_position(state)
    if (
        pending.get("transition_sequence") != transition_sequence
        or pending.get("transition_last_event_hash") != transition_last_event_hash
    ):
        raise HostGoalError(
            "Host Goal replacement checkpoint lifecycle position is invalid"
        )
    if _parse_timestamp(pending.get("issued_at")) is None:
        raise HostGoalError(
            "Host Goal replacement checkpoint lifecycle timestamp is invalid"
        )

    matching_events = [
        event
        for event in (state.get("transition_journal") or {}).get("events", [])
        if isinstance(event, dict)
        and event.get("transition_name") == "host_goal_checkpoint_superseded"
        and (event.get("metadata") or {}).get("checkpoint_id")
        == superseded_checkpoint_id
    ]
    if len(matching_events) != 1:
        raise HostGoalError(
            "Host Goal checkpoint supersession transition is not unique"
        )
    supersession_event = matching_events[0]
    if supersession_event.get("sequence") != transition_sequence:
        raise HostGoalError(
            "Host Goal replacement checkpoint lifecycle transition is invalid"
        )
    if (
        supersession_event.get("output_artifact_hashes") or {}
    ).get("checkpoint_archive") != stable_hash(archive):
        raise HostGoalError("Host Goal checkpoint archive hash does not match journal")
    if (supersession_event.get("input_artifact_hashes") or {}).get(
        "checkpoint"
    ) != stable_hash(archive.get("checkpoint") or {}):
        raise HostGoalError(
            "Host Goal superseded checkpoint hash does not match journal"
        )


def _activation_response(
    binding: dict[str, Any], checkpoint: dict[str, Any] | None
) -> dict[str, Any]:
    response = {
        "status": binding.get("status"),
        "objective": binding.get("objective"),
        "objective_sha256": binding.get("objective_sha256"),
    }
    if checkpoint:
        response.update(
            {
                "checkpoint_id": checkpoint["checkpoint_id"],
                "operation": checkpoint["operation"],
                "required_tool": checkpoint["required_tool"],
            }
        )
    return response


def _validate_observed_goal(
    binding: dict[str, Any],
    normalized: dict[str, Any],
    operation: str,
) -> None:
    status = normalized["status"]
    objective = normalized.get("objective")
    if operation == "inspect_before_activation" and status == "missing":
        return
    if status == "missing":
        if operation in {
            "create_goal",
            "verify_activation",
            "block_goal",
            "complete_goal",
            "verify_completion",
        }:
            raise HostGoalError("Host Goal is missing")
        return
    if objective != binding.get("objective"):
        raise HostGoalError("observed Host Goal objective does not match binding")
    bound_identifiers = binding.get("host_identifiers") or {}
    observed_identifiers = normalized.get("host_identifiers") or {}
    if not observed_identifiers:
        raise HostGoalError(
            "observed Host Goal requires a stable threadId, goalId, or id identifier"
        )
    if bound_identifiers and any(
        observed_identifiers.get(key) != value
        for key, value in bound_identifiers.items()
    ):
        raise HostGoalError("observed Host Goal identifier does not match binding")
    if operation in {"create_goal", "verify_activation"} and status != "active":
        raise HostGoalError("Host Goal activation must be observed active")
    if operation in {"complete_goal", "verify_completion"} and status != "complete":
        raise HostGoalError("Host Goal completion must be observed complete")
    if operation == "block_goal" and status != "blocked":
        raise HostGoalError("Host Goal blocking must be observed blocked")


def _validate_observed_goal_thread(
    normalized: dict[str, Any], expected_thread_id: str
) -> None:
    if normalized.get("status") == "missing":
        return
    observed_thread_id = (normalized.get("host_identifiers") or {}).get(
        "threadId"
    )
    if not observed_thread_id:
        raise HostGoalError(
            "observed Host Goal threadId identifier is required"
        )
    if observed_thread_id != expected_thread_id:
        raise HostGoalError(
            "observed Host Goal threadId does not match the coordinator thread"
        )


def _binding_requires_observed_thread(binding: dict[str, Any]) -> bool:
    return bool(
        binding.get("ever_active")
        or binding.get("status")
        in {
            "verification_pending",
            "active",
            "blocked",
            "completion_verification_pending",
            "complete",
            "reactivation_required",
            "stopped_by_user",
        }
    )


def _mark_active(binding: dict[str, Any], normalized: dict[str, Any]) -> None:
    binding["status"] = "active"
    binding["ever_active"] = True
    existing_identifiers = dict(binding.get("host_identifiers") or {})
    for key, value in (normalized.get("host_identifiers") or {}).items():
        existing_identifiers.setdefault(key, value)
    binding["host_identifiers"] = existing_identifiers
    binding["activated_at"] = _timestamp()


def _record_human_wait_turn(
    binding: dict[str, Any], checkpoint: dict[str, Any]
) -> None:
    human_wait = deepcopy(binding.get("human_wait") or {})
    if human_wait.get("decision_id") != checkpoint.get("human_decision_id"):
        raise HostGoalError("current human decision is required")
    if human_wait.get("status") == "resolved":
        human_wait["last_observed_at"] = _timestamp()
        binding["human_wait"] = human_wait
        return
    turn_id = checkpoint.get("host_turn_id")
    observed_turn_ids = list(human_wait.get("observed_goal_turn_ids") or [])
    if turn_id not in observed_turn_ids:
        observed_turn_ids.append(turn_id)
        human_wait["consecutive_goal_turns"] = int(
            human_wait.get("consecutive_goal_turns") or 0
        ) + 1
    human_wait["observed_goal_turn_ids"] = observed_turn_ids[-20:]
    human_wait["last_observed_at"] = _timestamp()
    binding["human_wait"] = human_wait


def _reset_human_wait_episode(binding: dict[str, Any]) -> None:
    human_wait = deepcopy(binding.get("human_wait") or {})
    if not human_wait:
        return
    human_wait["ended_at"] = _timestamp()
    human_wait["end_reason"] = "blocker_not_observed_on_goal_turn"
    history = list(binding.get("human_wait_history") or [])
    history.append(human_wait)
    binding["human_wait_history"] = history[-100:]
    binding["human_wait"] = None


def _delivery_goal_next_gate(state: dict[str, Any]) -> str:
    goal = state.get("delivery_goal") or {}
    value = goal.get("current_task_cursor") or goal.get("next_action")
    return str(value or "record_executed_evidence_and_closure")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
