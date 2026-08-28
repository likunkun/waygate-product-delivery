import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    load_state,
    runtime_status,
    write_state,
)
from product_delivery_agent.transition_journal import journal_integrity_errors
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    handed_off_workflow,
)


OWNER_THREAD_ID = "thread-v1034-current-task-owner"
AUTHORIZATION_MESSAGE = "恢复被阻塞的 Host Goal 并继续当前交付"
RECOVERY_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "waygate-product-delivery"
    / "scripts"
    / "recover-blocked-host-goal-current-task-v1034.py"
)


def blocked_current_task_delivery(project_root: Path) -> dict:
    with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}):
        workflow = handed_off_workflow(project_root)
        state = activate_host_goal(workflow)

    binding = copy.deepcopy(state["host_goal_binding"])
    binding.update(
        {
            "status": "blocked",
            "human_wait": None,
            "pending_checkpoint": None,
            "authorized_transition": None,
            "last_observed_status": "blocked",
        }
    )
    state["host_goal_binding"] = binding
    state["status"] = "implementation_in_progress"
    state["stage"] = "implementation_in_progress"
    state["next_gate"] = "host_goal_resume_required"
    state["implementation"] = {
        "current_task": "TASK-001",
        "completed_tasks": [],
    }
    state["delivery_goal"].update(
        {
            "status": "implementation_in_progress",
            "current_task_cursor": "TASK-001",
            "next_action": "TASK-001",
            "completed_tasks": [],
        }
    )
    return write_state(project_root, state)


def recovery_request(state: dict, *, dry_run: bool) -> dict:
    binding = state["host_goal_binding"]
    return {
        "schema_version": "v1",
        "action": "recover_blocked_host_goal_current_task",
        "delivery_id": state["delivery_id"],
        "feature_slug": state["feature_slug"],
        "binding_nonce": binding["binding_nonce"],
        "expected_objective_sha256": binding["objective_sha256"],
        "expected_state_file_sha256": "0" * 64,
        "authorization_message": AUTHORIZATION_MESSAGE,
        "host_turn_id": "goal-turn-v1034-current-task-recovery",
        "goal_observation": {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": {
                "goal": {
                    "threadId": OWNER_THREAD_ID,
                    "objective": binding["objective"],
                    "status": "active",
                }
            },
        },
        "dry_run": dry_run,
    }


def run_recovery(project_root: Path, request: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RECOVERY_SCRIPT),
            "--project-root",
            str(project_root),
        ],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env={**os.environ, "CODEX_THREAD_ID": OWNER_THREAD_ID},
        check=False,
    )


class BlockedHostGoalCurrentTaskRecoveryV1034Tests(unittest.TestCase):
    def test_dry_run_then_recovery_restores_current_task_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            before = blocked_current_task_delivery(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_file_sha256 = hashlib.sha256(state_path.read_bytes()).hexdigest()
            before_bytes = state_path.read_bytes()

            request = recovery_request(before, dry_run=True)
            request["expected_state_file_sha256"] = state_file_sha256
            dry_run = run_recovery(project_root, request)

            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            dry_response = json.loads(dry_run.stdout)
            self.assertEqual(dry_response["result"], "dry_run")
            self.assertEqual(dry_response["next_gate"], "TASK-001")
            self.assertEqual(
                dry_response["validation_results"]["state_write"], "not_performed"
            )
            self.assertEqual(state_path.read_bytes(), before_bytes)

            request = recovery_request(before, dry_run=False)
            request["expected_state_file_sha256"] = state_file_sha256
            recovered = run_recovery(project_root, request)

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            response = json.loads(recovered.stdout)
            after = load_state(project_root)
            self.assertEqual(response["result"], "recovered")
            self.assertEqual(after["host_goal_binding"]["status"], "active")
            self.assertEqual(after["next_gate"], "TASK-001")
            self.assertEqual(runtime_status(after, after), "verified_waygate")
            self.assertEqual(journal_integrity_errors(after), [])
            self.assertEqual(
                after["transition_journal"]["events"][-1]["transition_name"],
                "host_goal_blocked_binding_recovered",
            )
            self.assertEqual(after["implementation"], before["implementation"])
            self.assertEqual(after["delivery_goal"], before["delivery_goal"])

    def test_rejects_wrong_frozen_state_hash_without_state_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            before = blocked_current_task_delivery(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()
            request = recovery_request(before, dry_run=True)

            result = run_recovery(project_root, request)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("state file hash mismatch", result.stderr)
            self.assertEqual(state_path.read_bytes(), before_bytes)


if __name__ == "__main__":
    unittest.main()
