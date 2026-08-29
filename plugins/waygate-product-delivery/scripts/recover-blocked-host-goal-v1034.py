#!/usr/bin/env python3
"""One-shot, fail-closed recovery for the Waygate 1.0.34 blocked Goal gap."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import stat
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _install_runtime_path() -> None:
    script_root = Path(__file__).resolve().parent.parent
    candidates = (script_root / "runtime", script_root / "src")
    for candidate in candidates:
        if (candidate / "product_delivery_agent").is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise RuntimeError("Waygate 1.0.34 runtime package could not be located")


_install_runtime_path()

from product_delivery_agent.artifact_protocol import (  # noqa: E402
    ARTIFACT_ROOT,
    current_runtime_provenance,
    lifecycle_state_hash,
    load_state,
    runtime_status,
)
from product_delivery_agent.artifact_store import ensure_delivery_layout  # noqa: E402
from product_delivery_agent.gatekeeper import (  # noqa: E402
    PLUGIN_VERSION,
    normalize_state_protocol,
)
from product_delivery_agent.host_goal import (  # noqa: E402
    HostGoalError,
    assert_host_goal_owner,
    normalize_tool_result,
    stable_hash,
)
from product_delivery_agent.transition_journal import (  # noqa: E402
    append_transition,
    journal_integrity_errors,
)


SCHEMA_VERSION = "v1"
ACTION = "recover_blocked_host_goal"
TARGET_GATE = "multi_agent_test_implementation_review"
AUTHORIZATION_MESSAGE = "恢复被阻塞的 Host Goal 并继续当前交付"
TRANSITION_NAME = "host_goal_blocked_binding_recovered"
HISTORY_REASON = "blocked_host_goal_emergency_recovery_v1034"
TARGET_DELIVERY_ID = "26a6049314fe48caa1e7d4dcdb45c171"
TARGET_FEATURE_SLUG = "v0-7-response-evidence"
TARGET_BINDING_NONCE = "e987454240574c8dbf468f815a7f1d21"
TARGET_OBJECTIVE_SHA256 = (
    "7c0cab9d70d7c4586e9220f9d0274bad7c520d67fb932e7f503433463ffcf2db"
)
TARGET_OWNER_THREAD_ID = "01a02a39-b3f6-7062-8a4b-e8a3cb399bbc"
TARGET_RUNTIME_SHA256 = "c7ee45f75750e5563e288c64b2b18f3093b6501d2fdc38470c5789ccd53f9234"
TARGET_STATE_FILE_SHA256 = "44e1447e328e660eca8054ae9e39dc0b28295069fb526df3dc6dc8ac55e4b702"
AT_FDCWD = -100
RENAME_EXCHANGE = 2
ALLOWED_FIELDS = {
    "schema_version",
    "action",
    "delivery_id",
    "feature_slug",
    "binding_nonce",
    "expected_objective_sha256",
    "authorization_message",
    "host_turn_id",
    "goal_observation",
    "dry_run",
}
OBSERVATION_FIELDS = {"observation_source", "tool", "result"}


class RecoveryError(RuntimeError):
    """A stable, user-facing emergency recovery failure."""


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


def _load_raw_state(project_root: Path) -> tuple[dict[str, Any], str]:
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    if not state_path.is_file():
        raise RecoveryError("Waygate state.json is required")
    try:
        state_bytes = state_path.read_bytes()
        raw = json.loads(state_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError(f"Waygate state.json is unreadable: {error}") from error
    if not isinstance(raw, dict):
        raise RecoveryError("Waygate state.json must contain an object")
    return raw, hashlib.sha256(state_bytes).hexdigest()


def _assert_identity(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    if not state.get("active"):
        raise RecoveryError("delivery must remain active")
    if state.get("delivery_id") != TARGET_DELIVERY_ID:
        raise RecoveryError(
            f"recovery is restricted to delivery {TARGET_DELIVERY_ID}"
        )
    if state.get("feature_slug") != TARGET_FEATURE_SLUG:
        raise RecoveryError(
            f"recovery is restricted to feature {TARGET_FEATURE_SLUG}"
        )
    if state.get("delivery_id") != request["delivery_id"]:
        raise RecoveryError("delivery_id mismatch")
    if state.get("feature_slug") != request["feature_slug"]:
        raise RecoveryError("feature_slug mismatch")

    binding = state.get("host_goal_binding") or {}
    if binding.get("delivery_id") != state.get("delivery_id"):
        raise RecoveryError("binding delivery_id mismatch")
    if binding.get("feature_slug") != state.get("feature_slug"):
        raise RecoveryError("binding feature_slug mismatch")
    if binding.get("binding_nonce") != TARGET_BINDING_NONCE:
        raise RecoveryError("binding is not the targeted 1.0.34 binding_nonce")
    if binding.get("objective_sha256") != TARGET_OBJECTIVE_SHA256:
        raise RecoveryError("binding is not the targeted 1.0.34 objective")
    if binding.get("binding_nonce") != request["binding_nonce"]:
        raise RecoveryError("binding_nonce mismatch")
    if binding.get("objective_sha256") != request["expected_objective_sha256"]:
        raise RecoveryError("expected_objective_sha256 mismatch")
    objective = _required_string(binding.get("objective"), "binding objective")
    if stable_hash(objective) != binding.get("objective_sha256"):
        raise RecoveryError("stored objective hash mismatch")
    return binding


def _assert_recovery_state(state: dict[str, Any], binding: dict[str, Any]) -> None:
    if binding.get("status") != "blocked":
        raise RecoveryError("binding status must be blocked")
    if binding.get("human_wait"):
        raise RecoveryError("human_wait must be absent")
    if binding.get("pending_checkpoint"):
        raise RecoveryError("pending checkpoint must be absent")
    if binding.get("authorized_transition"):
        raise RecoveryError("authorized transition must be absent")
    if state.get("next_gate") != "host_goal_resume_required":
        raise RecoveryError("next_gate must be host_goal_resume_required")
    if state.get("stage") != "executed_browser_evidence_passed":
        raise RecoveryError("stage must be executed_browser_evidence_passed")

    implementation = state.get("implementation") or {}
    if implementation.get("current_task") != "TASKS_COMPLETE":
        raise RecoveryError("implementation current_task must be TASKS_COMPLETE")
    delivery_goal = state.get("delivery_goal") or {}
    planned_task_ids = [
        task.get("task_id")
        for task in delivery_goal.get("planned_tasks") or []
        if isinstance(task, dict)
    ]
    completed_task_ids = implementation.get("completed_tasks") or []
    if (
        not planned_task_ids
        or completed_task_ids != planned_task_ids
        or delivery_goal.get("completed_tasks") != planned_task_ids
    ):
        raise RecoveryError("all planned TASKs must be complete")
    if delivery_goal.get("status") != "implementation_tasks_complete":
        raise RecoveryError("delivery goal must be implementation_tasks_complete")
    if (state.get("executed_browser_evidence") or {}).get("status") != "passed":
        raise RecoveryError("executed browser evidence must remain passed")
    if (state.get("prototype_production_conformance") or {}).get("status") not in {
        None,
        "missing",
    }:
        raise RecoveryError("production conformance must remain missing")

    reviews = state.get("multi_agent_reviews") or {}
    for review_type in ("test_implementation", "ui_conformance"):
        if (reviews.get(review_type) or {}).get("status") not in {None, "missing"}:
            raise RecoveryError(f"{review_type} review must remain missing")
    if (state.get("closure_validation") or {}).get("status") != "not_run":
        raise RecoveryError("closure validation must remain not_run")
    errors = journal_integrity_errors(state)
    if errors:
        raise RecoveryError(f"transition journal integrity failed: {errors}")


def _normalize_active_goal(
    state: dict[str, Any], request: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    observation = request["goal_observation"]
    try:
        normalized = normalize_tool_result("get_goal", observation["result"])
    except HostGoalError as error:
        raise RecoveryError(str(error)) from error
    if normalized.get("status") != "active":
        raise RecoveryError("Host Goal must be active")

    binding = state["host_goal_binding"]
    if normalized.get("objective") != binding.get("objective"):
        raise RecoveryError("Host Goal objective mismatch")
    if stable_hash(normalized.get("objective")) != binding.get("objective_sha256"):
        raise RecoveryError("Host Goal objective hash mismatch")

    owner_thread_id = _required_string(
        binding.get("owner_thread_id"), "binding owner_thread_id"
    )
    observed_identifiers = normalized.get("host_identifiers") or {}
    observed_thread_id = observed_identifiers.get("threadId")
    if observed_thread_id != owner_thread_id:
        raise RecoveryError("Host Goal threadId mismatch")
    for key, value in (binding.get("host_identifiers") or {}).items():
        if observed_identifiers.get(key) != value:
            raise RecoveryError(f"Host Goal {key} mismatch")
    result_sha256 = stable_hash(observation["result"])
    return normalized, result_sha256


def build_recovered_state(
    project_root: Path, request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_state, state_file_sha256 = _load_raw_state(project_root)
    state = load_state(project_root)
    if runtime_status(state, raw_state) != "verified_waygate":
        raise RecoveryError("runtime must remain verified_waygate")
    runtime_receipt = current_runtime_provenance()
    if runtime_receipt.get("package_root_sha256") != TARGET_RUNTIME_SHA256:
        raise RecoveryError("original runtime package hash mismatch")
    if state_file_sha256 != TARGET_STATE_FILE_SHA256:
        raise RecoveryError("frozen recovery state snapshot mismatch")
    if PLUGIN_VERSION != "1.0.34":
        raise RecoveryError("emergency recovery is restricted to Waygate 1.0.34")
    try:
        owner_thread_id = assert_host_goal_owner(state)
    except HostGoalError as error:
        raise RecoveryError(str(error)) from error
    if owner_thread_id != TARGET_OWNER_THREAD_ID:
        raise RecoveryError("frozen owner thread mismatch")

    binding = _assert_identity(state, request)
    _assert_recovery_state(state, binding)
    normalized_goal, observation_sha256 = _normalize_active_goal(state, request)
    state_hash_before = lifecycle_state_hash(state)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    recovery_id = stable_hash(
        {
            "delivery_id": state["delivery_id"],
            "binding_nonce": binding["binding_nonce"],
            "host_turn_id": request["host_turn_id"],
            "observation_sha256": observation_sha256,
            "state_hash_before": state_hash_before,
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
            "resume_gate": TARGET_GATE,
            "last_observed_status": "active",
            "last_observed_at": observed_at,
            "last_observation_sha256": observation_sha256,
            "emergency_recovery": {
                "schema_version": "v1",
                "recovery_id": recovery_id,
                "recovered_at": observed_at,
                "host_turn_id": request["host_turn_id"],
                "observation_sha256": observation_sha256,
                "restored_gate": TARGET_GATE,
            },
        }
    )
    observations = list(next_binding.get("observations") or [])
    observations.append(
        {
            "recovery_id": recovery_id,
            "host_turn_id": request["host_turn_id"],
            "observed_at": observed_at,
            "operation": "emergency_blocked_goal_recovery",
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
            "observation_sha256": observation_sha256,
        }
    )
    next_state["host_goal_binding_history"] = history
    next_state["host_goal_binding"] = next_binding
    next_state["next_gate"] = TARGET_GATE
    next_state = append_transition(
        next_state,
        TRANSITION_NAME,
        feature_slug=next_state.get("feature_slug"),
        runtime_version=PLUGIN_VERSION,
        metadata={
            "recovery_id": recovery_id,
            "delivery_id": next_state.get("delivery_id"),
            "binding_nonce": next_binding.get("binding_nonce"),
            "owner_thread_id": owner_thread_id,
            "host_turn_id": request["host_turn_id"],
            "observation_sha256": observation_sha256,
            "previous_status": "blocked",
            "restored_status": "active",
            "previous_gate": "host_goal_resume_required",
            "restored_gate": TARGET_GATE,
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
        "previous_binding_status": "blocked",
        "host_goal_status": "active",
        "next_gate": TARGET_GATE,
        "runtime_status": "verified_waygate",
        "runtime_provenance": deepcopy(next_state["runtime_provenance"]),
        "state_hash_before": state_hash_before,
        "state_hash_after": lifecycle_state_hash(next_state),
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


def _persistence_paths(project_root: Path, state: dict[str, Any]) -> list[Path]:
    workspace = project_root / ARTIFACT_ROOT
    delivery_root = (
        workspace
        / "deliveries"
        / str(state["feature_slug"])
        / str(state["delivery_id"])
    )
    paths = [
        workspace / "state.json",
        delivery_root / "state.json",
        delivery_root / "manifest.json",
        workspace / "current.json",
        workspace / "current",
        workspace / "state.json.recovery-candidate.tmp",
    ]
    paths.extend(
        path.with_suffix(path.suffix + ".tmp")
        for path in paths
        if path.suffix == ".json"
    )
    return paths


def _capture_persistence_snapshot(
    project_root: Path, state: dict[str, Any]
) -> dict[Path, tuple[str, bytes | str, int] | None]:
    snapshot = {}
    for path in _persistence_paths(project_root, state):
        if path.is_symlink():
            snapshot[path] = ("symlink", os.readlink(path), 0)
        elif path.is_file():
            snapshot[path] = (
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
        else:
            snapshot[path] = None
    return snapshot


def _restore_persistence_snapshot(
    snapshot: dict[Path, tuple[str, bytes | str, int] | None],
    *,
    excluded_paths: set[Path] | None = None,
) -> None:
    errors = []
    for path, saved in snapshot.items():
        if path in (excluded_paths or set()):
            continue
        try:
            if saved is None:
                if path.is_symlink() or path.is_file():
                    path.unlink()
                continue
            kind, payload, mode = saved
            if path.is_symlink() or path.is_file():
                path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)
            if kind == "symlink":
                path.symlink_to(str(payload))
            else:
                restore_path = path.with_name(path.name + ".restore.tmp")
                restore_path.write_bytes(bytes(payload))
                os.chmod(restore_path, mode)
                os.replace(restore_path, path)
        except OSError as error:
            errors.append(f"{path}: {error}")
    if errors:
        raise RecoveryError(f"state rollback failed: {errors}")


def _atomic_exchange(left: Path, right: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RecoveryError("atomic RENAME_EXCHANGE is unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        AT_FDCWD,
        os.fsencode(left),
        AT_FDCWD,
        os.fsencode(right),
        RENAME_EXCHANGE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise RecoveryError(
            f"atomic state exchange failed: {os.strerror(error_number)}"
        )


def _prepare_candidate_state(
    state_path: Path, next_state: dict[str, Any]
) -> tuple[dict[str, Any], Path, str]:
    persisted = normalize_state_protocol(dict(next_state))
    persisted["updated_at"] = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    payload = (json.dumps(persisted, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    candidate_path = state_path.with_name("state.json.recovery-candidate.tmp")
    try:
        with candidate_path.open("xb") as candidate_file:
            candidate_file.write(payload)
            candidate_file.flush()
            os.fsync(candidate_file.fileno())
    except FileExistsError as error:
        raise RecoveryError("stale recovery candidate file exists") from error
    return persisted, candidate_path, hashlib.sha256(payload).hexdigest()


def recover(project_root: Path, raw_request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(raw_request)
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    try:
        lock_file = state_path.open("rb")
    except OSError as error:
        raise RecoveryError(f"Waygate state.json cannot be locked: {error}") from error
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        next_state, response = build_recovered_state(project_root, request)
        if request["dry_run"]:
            return response
        current_sha256 = hashlib.sha256(state_path.read_bytes()).hexdigest()
        if current_sha256 != TARGET_STATE_FILE_SHA256:
            raise RecoveryError("frozen recovery state changed before commit")
        snapshot = _capture_persistence_snapshot(project_root, next_state)
        candidate_path = state_path.with_name("state.json.recovery-candidate.tmp")
        exchanged = False
        try:
            persisted, candidate_path, candidate_sha256 = _prepare_candidate_state(
                state_path, next_state
            )
            _atomic_exchange(candidate_path, state_path)
            exchanged = True
            exchanged_out_sha256 = hashlib.sha256(
                candidate_path.read_bytes()
            ).hexdigest()
            if exchanged_out_sha256 != TARGET_STATE_FILE_SHA256:
                _atomic_exchange(candidate_path, state_path)
                exchanged = False
                raise RecoveryError("frozen recovery state changed during commit")
            if hashlib.sha256(state_path.read_bytes()).hexdigest() != candidate_sha256:
                raise RecoveryError("persisted recovery candidate hash mismatch")
            ensure_delivery_layout(project_root, persisted)
            if runtime_status(persisted, persisted) != "verified_waygate":
                raise RecoveryError("persisted runtime identity is not verified_waygate")
            if journal_integrity_errors(persisted):
                raise RecoveryError(
                    "persisted transition journal failed integrity validation"
                )
            response["state_hash_after"] = lifecycle_state_hash(persisted)
            response["validation_results"]["state_write"] = "performed"
            if candidate_path.is_file() or candidate_path.is_symlink():
                candidate_path.unlink()
            exchanged = False
            return response
        except Exception as error:
            try:
                if exchanged:
                    current_state_sha256 = hashlib.sha256(
                        state_path.read_bytes()
                    ).hexdigest()
                    if current_state_sha256 == candidate_sha256:
                        _atomic_exchange(candidate_path, state_path)
                        exchanged = False
                _restore_persistence_snapshot(
                    snapshot,
                    excluded_paths={state_path},
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
        "usage: recover-blocked-host-goal-v1034.py [--project-root PATH | PATH]"
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
    except Exception as error:  # pragma: no cover - final CLI safety net
        sys.stderr.write(f"recovery runtime error: {error}\n")
        return 4
    sys.stdout.write(json.dumps(response, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
