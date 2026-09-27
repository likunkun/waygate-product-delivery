import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    current_runtime_provenance,
    load_state,
    runtime_status,
    write_state,
)
from product_delivery_agent.host_goal import stable_hash
from product_delivery_agent.artifact_store import ensure_delivery_layout
from product_delivery_agent.transition_journal import append_transition
from product_delivery_agent.transition_journal import journal_integrity_errors
from product_delivery_agent.workflow import ProductDeliveryWorkflow


OWNER_THREAD_ID = "thread-v1042-owner"
FEATURE_SLUG = "v1042-blocked-binding-recovery"
BINDING_NONCE = "binding-v1042-nonce"
OBJECTIVE = (
    "Complete Waygate Product Delivery delivery v1042 and reach canonical closure."
)
AUTHORIZATION_MESSAGE = "授权执行可审计的 Waygate 1.0.42 blocked-binding 状态机修复"
PREVIOUS_RECOVERY_ID = "previous-v1037-recovery-id"
HOST_TURN_ID = "host-turn-v1042"
FIXTURE_RUNTIME_PROVENANCE = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.0.42",
    "runtime_package_sha256": "fixture-runtime-v1042",
}
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "waygate-product-delivery"
    / "scripts"
    / "recover-blocked-host-goal-current-task-v1042.py"
)


def _load_recovery_module():
    spec = importlib.util.spec_from_file_location(
        "waygate_v1042_recovery", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Waygate 1.0.42 recovery script is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID})
class BlockedHostGoalCurrentTaskRecoveryV1042Tests(unittest.TestCase):
    def setUp(self):
        self.recovery = _load_recovery_module()
        # This test exercises the historical 1.0.42 recovery contract while
        # running from a newer checkout.  Keep the fixture pinned to the
        # historical runtime instead of coupling it to the release under test.
        self.recovery.emergency.PLUGIN_VERSION = "1.0.42"
        self.recovery.emergency.current_runtime_provenance = (
            lambda: dict(FIXTURE_RUNTIME_PROVENANCE)
        )
        self.recovery.emergency.runtime_status = (
            lambda state, raw_state: (
                "verified_waygate"
                if raw_state.get("runtime_provenance") == FIXTURE_RUNTIME_PROVENANCE
                else "invalid_runtime"
            )
        )

    def _write_blocked_state(self, project_root: Path) -> dict:
        state = ProductDeliveryWorkflow(project_root).start(
            feature_slug=FEATURE_SLUG,
            multi_agent_mode="spawned_subagents_authorized",
        )
        state.update(
            {
                "active": True,
                "status": "implementation_in_progress",
                "stage": "implementation_in_progress",
                "next_gate": "host_goal_resume_required",
            }
        )
        state["host_goal_owner"] = {
            "status": "claimed",
            "delivery_id": state["delivery_id"],
            "feature_slug": state["feature_slug"],
            "coordinator_thread_id": OWNER_THREAD_ID,
        }
        state["implementation"] = {
            "current_task": "TASK-003",
            "completed_tasks": ["TASK-001", "TASK-002"],
        }
        state["delivery_goal"] = {
            "status": "implementation_in_progress",
            "current_task_cursor": "TASK-003",
            "next_action": "TASK-003",
            "launch_package_hash": "launch-package-v1042",
            "completed_tasks": ["TASK-001", "TASK-002"],
            "planned_tasks": [
                {"task_id": "TASK-001"},
                {"task_id": "TASK-002"},
                {"task_id": "TASK-003"},
                {"task_id": "TASK-004"},
            ],
        }
        state["handoff"] = {"status": "complete"}
        state["implementation_launch_authorization"] = {
            "status": "authorized",
            "feature_slug": state["feature_slug"],
            "launch_package_hash": "launch-package-v1042",
        }
        state = append_transition(
            state,
            "handoff_generated",
            feature_slug=state["feature_slug"],
            runtime_version="1.0.42",
            metadata={"fixture": True},
        )
        state = append_transition(
            state,
            "task_completed",
            feature_slug=state["feature_slug"],
            runtime_version="1.0.42",
            metadata={"fixture": True},
        )
        state["host_goal_binding"] = {
            "schema_version": "v1",
            "status": "blocked",
            "delivery_id": state["delivery_id"],
            "feature_slug": state["feature_slug"],
            "binding_nonce": BINDING_NONCE,
            "generation": 3,
            "owner_thread_id": OWNER_THREAD_ID,
            "host_identifiers": {"threadId": OWNER_THREAD_ID},
            "objective": OBJECTIVE,
            "objective_sha256": stable_hash(OBJECTIVE),
            "launch_package_hash": "launch-package-v1042",
            "authorization_hash": stable_hash({"authorization": "v1042"}),
            "human_wait": None,
            "pending_checkpoint": None,
            "authorized_transition": None,
            "resume_gate": "TASK-002",
            "emergency_recovery": {
                "schema_version": "v1",
                "recovery_id": PREVIOUS_RECOVERY_ID,
                "plugin_version": "1.0.37",
                "restored_gate": "TASK-002",
            },
        }
        state["runtime_provenance"] = dict(FIXTURE_RUNTIME_PROVENANCE)
        write_state(project_root, state)
        # The fixture deliberately bypasses protocol reclassification so it can
        # reproduce the already-authorized implementation state being recovered.
        state_path = project_root / ".product-delivery" / "state.json"
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        ensure_delivery_layout(project_root, state)
        return state

    def _request(self, state: dict, state_file_sha256: str) -> dict:
        return {
            "schema_version": "v1",
            "action": "recover_blocked_host_goal_current_task",
            "delivery_id": state["delivery_id"],
            "feature_slug": state["feature_slug"],
            "binding_nonce": BINDING_NONCE,
            "expected_objective_sha256": stable_hash(OBJECTIVE),
            "expected_state_file_sha256": state_file_sha256,
            "authorization_message": AUTHORIZATION_MESSAGE,
            "host_turn_id": HOST_TURN_ID,
            "goal_observation": {
                "observation_source": "codex_goal_tool",
                "tool": "get_goal",
                "result": {
                    "goal": {
                        "status": "active",
                        "objective": OBJECTIVE,
                        "threadId": OWNER_THREAD_ID,
                    }
                },
            },
            "dry_run": True,
        }

    def test_requires_exact_v1042_authorization_message(self):
        request = {
            "schema_version": "v1",
            "action": "recover_blocked_host_goal_current_task",
            "delivery_id": "delivery",
            "feature_slug": "feature",
            "binding_nonce": "nonce",
            "expected_objective_sha256": "objective-hash",
            "expected_state_file_sha256": "state-hash",
            "authorization_message": "恢复被阻塞的 Host Goal 并继续当前交付",
            "host_turn_id": "turn",
            "goal_observation": {
                "observation_source": "codex_goal_tool",
                "tool": "get_goal",
                "result": {"goal": None},
            },
            "dry_run": True,
        }

        with self.assertRaisesRegex(
            self.recovery.RecoveryError, "authorization_message must be"
        ):
            self.recovery.validate_request(request)

    def test_dry_run_does_not_change_state_and_targets_current_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_blocked_state(project_root)
            state_path = project_root / ".product-delivery" / "state.json"
            state_bytes = state_path.read_bytes()
            state_hash = hashlib.sha256(state_bytes).hexdigest()

            response = self.recovery.recover(
                project_root, self._request(state, state_hash)
            )

            self.assertEqual(response["result"], "dry_run")
            self.assertEqual(response["next_gate"], "TASK-003")
            self.assertEqual(response["previous_recovery_id"], PREVIOUS_RECOVERY_ID)
            self.assertEqual(
                response["validation_results"]["state_write"], "not_performed"
            )
            self.assertEqual(state_path.read_bytes(), state_bytes)

    def test_recovery_restores_binding_and_preserves_current_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_blocked_state(project_root)
            state_path = project_root / ".product-delivery" / "state.json"
            state_hash = hashlib.sha256(state_path.read_bytes()).hexdigest()
            request = self._request(state, state_hash)

            dry_run_response = self.recovery.recover(project_root, request)
            actual_response = self.recovery.recover(
                project_root, {**request, "dry_run": False}
            )

            self.assertEqual(dry_run_response["result"], "dry_run")
            self.assertEqual(actual_response["result"], "recovered")
            recovered = load_state(project_root)
            self.assertEqual(recovered["status"], "implementation_in_progress")
            self.assertEqual(recovered["next_gate"], "TASK-003")
            self.assertEqual(recovered["implementation"]["current_task"], "TASK-003")
            binding = recovered["host_goal_binding"]
            self.assertEqual(binding["status"], "active")
            self.assertEqual(binding["resume_gate"], "TASK-003")
            self.assertEqual(
                binding["emergency_recovery"]["previous_recovery_id"],
                PREVIOUS_RECOVERY_ID,
            )
            self.assertEqual(
                binding["emergency_recovery"]["plugin_version"], "1.0.42"
            )
            history = recovered["host_goal_binding_history"][-1]
            self.assertEqual(
                history["reason"],
                "blocked_host_goal_current_task_recovery_v1042",
            )
            self.assertEqual(history["recovery_id"], actual_response["recovery_id"])
            event = recovered["transition_journal"]["events"][-1]
            self.assertEqual(
                event["transition_name"], "host_goal_blocked_binding_recovered"
            )
            self.assertEqual(event["runtime_version"], "1.0.42")
            self.assertEqual(
                event["metadata"]["authorization_sha256"],
                stable_hash(AUTHORIZATION_MESSAGE),
            )
            self.assertEqual(
                event["metadata"]["previous_recovery_id"], PREVIOUS_RECOVERY_ID
            )
            self.assertEqual(event["metadata"]["restored_gate"], "TASK-003")
            self.assertEqual(event["metadata"]["owner_thread_id"], OWNER_THREAD_ID)
            self.assertEqual(event["metadata"]["host_turn_id"], HOST_TURN_ID)
            self.assertFalse(journal_integrity_errors(recovered))
            self.assertEqual(
                self.recovery.emergency.runtime_status(recovered, recovered),
                "verified_waygate",
            )


if __name__ == "__main__":
    unittest.main()
