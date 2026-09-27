#!/usr/bin/env python3
"""Fail-closed recovery for a blocked current-task Goal binding in 1.0.42."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "v1"
ACTION = "recover_blocked_host_goal_current_task"
AUTHORIZATION_MESSAGE = "授权执行可审计的 Waygate 1.0.42 blocked-binding 状态机修复"
TRANSITION_NAME = "host_goal_blocked_binding_recovered"
HISTORY_REASON = "blocked_host_goal_current_task_recovery_v1042"
ALLOWED_FIELDS = {
    "schema_version",
    "action",
    "delivery_id",
    "feature_slug",
    "binding_nonce",
    "expected_objective_sha256",
    "expected_state_file_sha256",
    "authorization_message",
    "host_turn_id",
    "goal_observation",
    "dry_run",
}
OBSERVATION_FIELDS = {"observation_source", "tool", "result"}


def _load_emergency_module() -> Any:
    path = Path(__file__).with_name("recover-blocked-host-goal-v1034.py")
    spec = importlib.util.spec_from_file_location("waygate_v1034_recovery", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Waygate 1.0.34 emergency recovery module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


emergency = _load_emergency_module()


class RecoveryError(RuntimeError):
    """A stable, user-facing current-task recovery failure."""


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise RecoveryError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise RecoveryError(f"non-standard JSON constant: {value}")


def _load_strict_json(payload: str) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_strict_json_object,
        parse_constant=_reject_json_constant,
    )


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecoveryError(f"{field} is required")
    return value.strip()


def validate_request(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RecoveryError("request must be a JSON object")
    extras = sorted(set(raw) - ALLOWED_FIELDS)
    if extras:
        raise RecoveryError(f"unknown fields: {extras}")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise RecoveryError(f"schema_version must be '{SCHEMA_VERSION}'")
    if raw.get("action") != ACTION:
        raise RecoveryError(f"action must be '{ACTION}'")
    if not isinstance(raw.get("dry_run"), bool):
        raise RecoveryError("dry_run must be boolean")

    observation = raw.get("goal_observation")
    if not isinstance(observation, dict):
        raise RecoveryError("goal_observation must be an object")
    observation_extras = sorted(set(observation) - OBSERVATION_FIELDS)
    if observation_extras:
        raise RecoveryError(
            f"unknown goal_observation fields: {observation_extras}"
        )
    if observation.get("observation_source") != "codex_goal_tool":
        raise RecoveryError("goal_observation source must be codex_goal_tool")
    if observation.get("tool") != "get_goal":
        raise RecoveryError("goal_observation tool must be get_goal")
    if not isinstance(observation.get("result"), dict):
        raise RecoveryError("goal_observation result must be an object")

    request = {
        field: _required_string(raw.get(field), field)
        for field in (
            "delivery_id",
            "feature_slug",
            "binding_nonce",
            "expected_objective_sha256",
            "expected_state_file_sha256",
            "authorization_message",
            "host_turn_id",
        )
    }
    request.update(
        {
            "schema_version": SCHEMA_VERSION,
            "action": ACTION,
            "goal_observation": deepcopy(observation),
            "dry_run": raw["dry_run"],
        }
    )
    if request["authorization_message"] != AUTHORIZATION_MESSAGE:
        raise RecoveryError(
            f"authorization_message must be '{AUTHORIZATION_MESSAGE}'"
        )
    return request


def _assert_identity(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    if not state.get("active"):
        raise RecoveryError("delivery must remain active")
    if state.get("delivery_id") != request["delivery_id"]:
        raise RecoveryError("delivery_id mismatch")
    if state.get("feature_slug") != request["feature_slug"]:
        raise RecoveryError("feature_slug mismatch")

    binding = state.get("host_goal_binding") or {}
    if binding.get("delivery_id") != state.get("delivery_id"):
        raise RecoveryError("binding delivery_id mismatch")
    if binding.get("feature_slug") != state.get("feature_slug"):
        raise RecoveryError("binding feature_slug mismatch")
    if binding.get("binding_nonce") != request["binding_nonce"]:
        raise RecoveryError("binding_nonce mismatch")
    if binding.get("objective_sha256") != request["expected_objective_sha256"]:
        raise RecoveryError("expected_objective_sha256 mismatch")
    objective = _required_string(binding.get("objective"), "binding objective")
    if emergency.stable_hash(objective) != binding.get("objective_sha256"):
        raise RecoveryError("stored objective hash mismatch")
    return binding


def _current_task_gate(state: dict[str, Any]) -> str:
    if state.get("status") != "implementation_in_progress":
        raise RecoveryError("delivery status must be implementation_in_progress")
    if state.get("stage") != "implementation_in_progress":
        raise RecoveryError("delivery stage must be implementation_in_progress")
    if state.get("next_gate") != "host_goal_resume_required":
        raise RecoveryError("next_gate must be host_goal_resume_required")

    implementation = state.get("implementation") or {}
    goal = state.get("delivery_goal") or {}
    current_task = implementation.get("current_task")
    if current_task != goal.get("current_task_cursor"):
        raise RecoveryError("implementation and delivery goal TASK cursors differ")
    if current_task != goal.get("next_action"):
        raise RecoveryError("delivery goal next action is not the current TASK")
    if not isinstance(current_task, str) or not current_task.startswith("TASK-"):
        raise RecoveryError("a non-terminal current TASK is required")

    planned_tasks = goal.get("planned_tasks") or []
    planned_ids = [task.get("task_id") for task in planned_tasks if isinstance(task, dict)]
    completed_ids = implementation.get("completed_tasks") or []
    if current_task in completed_ids:
        raise RecoveryError("current TASK is already complete")
    if current_task not in planned_ids:
        raise RecoveryError("current TASK is absent from the planned queue")
    if completed_ids != planned_ids[: len(completed_ids)]:
        raise RecoveryError("completed TASKs must be a planned-TASK prefix")
    if goal.get("completed_tasks") != completed_ids:
        raise RecoveryError("delivery goal completed TASKs mismatch")
    if goal.get("status") != "implementation_in_progress":
        raise RecoveryError("delivery goal must remain implementation_in_progress")
    return current_task


def _assert_recoverable_binding(binding: dict[str, Any]) -> None:
    if binding.get("status") != "blocked":
        raise RecoveryError("binding status must be blocked")
    if binding.get("human_wait"):
        raise RecoveryError("human_wait must be absent")
    if binding.get("pending_checkpoint"):
        raise RecoveryError("pending checkpoint must be absent")
    if binding.get("authorized_transition"):
        raise RecoveryError("authorized transition must be absent")
    if not isinstance(binding.get("generation"), int) or binding["generation"] < 1:
        raise RecoveryError("binding generation must be positive")
    recovery = binding.get("emergency_recovery")
    if recovery:
        if not isinstance(recovery, dict):
            raise RecoveryError("prior emergency recovery must be an object")
        if recovery.get("schema_version") != "v1":
            raise RecoveryError("prior emergency recovery schema is unsupported")
        if not isinstance(recovery.get("recovery_id"), str) or not recovery["recovery_id"]:
            raise RecoveryError("prior emergency recovery id is required")


def _normalize_active_goal(
    state: dict[str, Any], request: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    observation = request["goal_observation"]
    try:
        normalized = emergency.normalize_tool_result(
            "get_goal", observation["result"]
        )
    except emergency.HostGoalError as error:
        raise RecoveryError(str(error)) from error
    if normalized.get("status") != "active":
        raise RecoveryError("Host Goal must be active")

    binding = state["host_goal_binding"]
    if normalized.get("objective") != binding.get("objective"):
        raise RecoveryError("Host Goal objective mismatch")
    if emergency.stable_hash(normalized.get("objective")) != binding.get(
        "objective_sha256"
    ):
        raise RecoveryError("Host Goal objective hash mismatch")

    owner_thread_id = _required_string(
        binding.get("owner_thread_id"), "binding owner_thread_id"
    )
    observed_identifiers = normalized.get("host_identifiers") or {}
    if observed_identifiers.get("threadId") != owner_thread_id:
        raise RecoveryError("Host Goal threadId mismatch")
    for key, value in (binding.get("host_identifiers") or {}).items():
        if observed_identifiers.get(key) != value:
            raise RecoveryError(f"Host Goal {key} mismatch")
    return normalized, emergency.stable_hash(observation["result"])


def build_recovered_state(
    project_root: Path, request: dict[str, Any], state_file_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_state, actual_state_file_sha256 = emergency._load_raw_state(project_root)
    if actual_state_file_sha256 != state_file_sha256:
        raise RecoveryError("state file hash mismatch")
    state = emergency.load_state(project_root)
    if emergency.runtime_status(state, raw_state) != "verified_waygate":
        raise RecoveryError("runtime must remain verified_waygate")
    if emergency.PLUGIN_VERSION != "1.0.42":
        raise RecoveryError("recovery is restricted to Waygate 1.0.42")
    if emergency.current_runtime_provenance() != state.get("runtime_provenance"):
        raise RecoveryError("current runtime provenance mismatch")
    try:
        owner_thread_id = emergency.assert_host_goal_owner(state)
    except emergency.HostGoalError as error:
        raise RecoveryError(str(error)) from error

    binding = _assert_identity(state, request)
    _assert_recoverable_binding(binding)
    target_gate = _current_task_gate(state)
    normalized_goal, observation_sha256 = _normalize_active_goal(state, request)
    if emergency.journal_integrity_errors(state):
        raise RecoveryError("transition journal integrity failed")

    state_hash_before = emergency.lifecycle_state_hash(state)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    previous_recovery = binding.get("emergency_recovery") or {}
    previous_recovery_id = previous_recovery.get("recovery_id")
    authorization_sha256 = emergency.stable_hash(request["authorization_message"])
    recovery_id = emergency.stable_hash(
        {
            "delivery_id": state["delivery_id"],
            "binding_nonce": binding["binding_nonce"],
            "plugin_version": emergency.PLUGIN_VERSION,
            "host_turn_id": request["host_turn_id"],
            "observation_sha256": observation_sha256,
            "state_hash_before": state_hash_before,
            "previous_recovery_id": previous_recovery_id,
        }
    )

    old_binding = deepcopy(binding)
    next_binding = deepcopy(binding)
    next_binding.update(
        {
            "status": "active",
            "human_wait": None,
            "pending_checkpoint": None,
            "authorized_transition": None,
            "resume_gate": target_gate,
            "last_observed_status": "active",
            "last_observed_at": observed_at,
            "last_observation_sha256": observation_sha256,
            "emergency_recovery": {
                "schema_version": "v1",
                "recovery_id": recovery_id,
                "plugin_version": emergency.PLUGIN_VERSION,
                "previous_recovery_id": previous_recovery_id,
                "recovered_at": observed_at,
                "host_turn_id": request["host_turn_id"],
                "observation_sha256": observation_sha256,
                "authorization_sha256": authorization_sha256,
                "restored_gate": target_gate,
            },
        }
    )
    observations = list(next_binding.get("observations") or [])
    observations.append(
        {
            "recovery_id": recovery_id,
            "host_turn_id": request["host_turn_id"],
            "observed_at": observed_at,
            "operation": "emergency_blocked_goal_current_task_recovery",
            "status": normalized_goal["status"],
            "objective": normalized_goal["objective"],
            "host_identifiers": normalized_goal["host_identifiers"],
            "result_sha256": observation_sha256,
            "tool": "get_goal",
        }
    )
    next_binding["observations"] = observations[-200:]

    next_state = deepcopy(state)
    history = list(next_state.get("host_goal_binding_history") or [])
    history.append(
        {
            "binding": old_binding,
            "archived_at": observed_at,
            "reason": HISTORY_REASON,
            "recovery_id": recovery_id,
            "previous_recovery_id": previous_recovery_id,
            "observation_sha256": observation_sha256,
        }
    )
    next_state["host_goal_binding_history"] = history
    next_state["host_goal_binding"] = next_binding
    next_state["next_gate"] = target_gate
    next_state = emergency.append_transition(
        next_state,
        TRANSITION_NAME,
        feature_slug=next_state.get("feature_slug"),
        runtime_version=emergency.PLUGIN_VERSION,
        metadata={
            "recovery_id": recovery_id,
            "delivery_id": next_state.get("delivery_id"),
            "binding_nonce": next_binding.get("binding_nonce"),
            "owner_thread_id": owner_thread_id,
            "host_turn_id": request["host_turn_id"],
            "plugin_version": emergency.PLUGIN_VERSION,
            "authorization_sha256": authorization_sha256,
            "observation_sha256": observation_sha256,
            "previous_recovery_id": previous_recovery_id,
            "previous_status": "blocked",
            "restored_status": "active",
            "previous_gate": "host_goal_resume_required",
            "restored_gate": target_gate,
            "state_hash_before": state_hash_before,
        },
        occurred_at=observed_at,
    )
    response = {
        "schema_version": SCHEMA_VERSION,
        "action": ACTION,
        "result": "dry_run" if request["dry_run"] else "recovered",
        "delivery_id": next_state["delivery_id"],
        "feature_slug": next_state["feature_slug"],
        "binding_nonce": next_binding["binding_nonce"],
        "recovery_id": recovery_id,
        "previous_recovery_id": previous_recovery_id,
        "previous_binding_status": "blocked",
        "host_goal_status": "active",
        "next_gate": target_gate,
        "runtime_status": "verified_waygate",
        "runtime_provenance": deepcopy(next_state["runtime_provenance"]),
        "state_hash_before": state_hash_before,
        "state_hash_after": emergency.lifecycle_state_hash(next_state),
        "journal_transition": TRANSITION_NAME,
        "validation_results": {
            "binding_recoverable": True,
            "goal_active_and_matching": True,
            "journal_integrity": "passed",
            "runtime_identity": "verified_waygate",
            "state_write": "not_performed" if request["dry_run"] else "pending",
        },
    }
    return next_state, response


def recover(project_root: Path, raw_request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(raw_request)
    state_path = project_root / emergency.ARTIFACT_ROOT / "state.json"
    try:
        lock_file = state_path.open("rb")
    except OSError as error:
        raise RecoveryError(
            f"Waygate state.json cannot be locked: {error}"
        ) from error
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        next_state, response = build_recovered_state(
            project_root, request, request["expected_state_file_sha256"]
        )
        if request["dry_run"]:
            return response
        if (
            hashlib.sha256(state_path.read_bytes()).hexdigest()
            != request["expected_state_file_sha256"]
        ):
            raise RecoveryError("frozen recovery state changed before commit")

        snapshot = emergency._capture_persistence_snapshot(project_root, next_state)
        candidate_path = state_path.with_name("state.json.recovery-candidate.tmp")
        exchanged = False
        try:
            persisted, candidate_path, candidate_sha256 = emergency._prepare_candidate_state(
                state_path, next_state
            )
            emergency._atomic_exchange(candidate_path, state_path)
            exchanged = True
            if (
                hashlib.sha256(candidate_path.read_bytes()).hexdigest()
                != request["expected_state_file_sha256"]
            ):
                emergency._atomic_exchange(candidate_path, state_path)
                exchanged = False
                raise RecoveryError("frozen recovery state changed during commit")
            if (
                hashlib.sha256(state_path.read_bytes()).hexdigest()
                != candidate_sha256
            ):
                raise RecoveryError("persisted recovery candidate hash mismatch")
            emergency.ensure_delivery_layout(project_root, persisted)
            if emergency.runtime_status(persisted, persisted) != "verified_waygate":
                raise RecoveryError(
                    "persisted runtime identity is not verified_waygate"
                )
            if emergency.journal_integrity_errors(persisted):
                raise RecoveryError(
                    "persisted transition journal failed integrity validation"
                )
            response["state_hash_after"] = emergency.lifecycle_state_hash(persisted)
            response["validation_results"]["state_write"] = "performed"
            if candidate_path.is_file() or candidate_path.is_symlink():
                candidate_path.unlink()
            exchanged = False
            return response
        except Exception as error:
            try:
                if exchanged:
                    emergency._atomic_exchange(candidate_path, state_path)
                    exchanged = False
                emergency._restore_persistence_snapshot(
                    snapshot, excluded_paths={state_path}
                )
            except RecoveryError as rollback_error:
                raise RecoveryError(
                    f"recovery failed and {rollback_error}"
                ) from error
            raise


def _resolve_project_root(argv: list[str]) -> Path:
    if not argv:
        return Path.cwd()
    if argv[0] == "--project-root" and len(argv) == 2:
        return Path(argv[1])
    if len(argv) == 1:
        return Path(argv[0])
    raise RecoveryError(
        "usage: recover-blocked-host-goal-current-task-v1042.py "
        "[--project-root PATH | PATH]"
    )


def main(argv: list[str] | None = None) -> int:
    try:
        project_root = _resolve_project_root(
            list(sys.argv[1:] if argv is None else argv)
        )
        raw_request = _load_strict_json(sys.stdin.read())
        response = recover(project_root, raw_request)
    except json.JSONDecodeError as error:
        sys.stderr.write(f"invalid JSON: {error}\n")
        return 2
    except RecoveryError as error:
        sys.stderr.write(f"recovery blocked: {error}\n")
        return 3
    except Exception as error:  # pragma: no cover - CLI safety net
        sys.stderr.write(f"recovery runtime error: {error}\n")
        return 4
    sys.stdout.write(json.dumps(response, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
