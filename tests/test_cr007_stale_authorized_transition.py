import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import write_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    handed_off_workflow,
    goal_result,
)


OWNER = "thread-cr007-stale-transition"
AUTH = (
    "授权发起 CR007：修复 Waygate blocked observation 遗留 stale "
    "authorized_transition，并按修复版 runtime 的受支持迁移入口恢复当前 delivery。"
)
CR006_FIXED_RUNTIME_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.1.0",
    "package_root_sha256": (
        "1102adcf787c5ae42d52e1daa718692e29a4acf5e94ca3d8ed7651aa87e278b0"
    ),
}


@patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER})
class CR007StaleAuthorizedTransitionTests(unittest.TestCase):
    def _blocked(self, root: Path):
        workflow = handed_off_workflow(root)
        active = activate_host_goal(workflow)
        state = workflow.status()
        task = state["delivery_goal"]["current_task_cursor"]
        binding = state["host_goal_binding"]
        binding.update({
            "status": "blocked",
            "last_observed_status": "blocked",
            "pending_checkpoint": None,
            "human_wait": None,
            "authorized_transition": {
                "checkpoint_id": "stale-before-block",
                "operation": "stage_transition",
                "target_gate": task,
                "observation_sha256": "a" * 64,
                "authorized_at": "2026-11-04T00:00:00+00:00",
            },
            "resume_gate": task,
        })
        state["next_gate"] = "host_goal_resume_required"
        write_state(root, state)
        return workflow, active["host_goal_binding"]["objective"], task

    def _request(self, root: Path, objective: str):
        state_path = root / ".product-delivery/state.json"
        return {
            "expected_state_file_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
            "authorization_message": AUTH,
            "host_turn_id": OWNER,
            "goal_observation": {
                "observation_source": "codex_goal_tool",
                "tool": "get_goal",
                "result": goal_result(objective),
            },
            "dry_run": True,
        }

    def test_blocked_observation_clears_prior_stage_authorization(self):
        for operation in (
            "turn_start",
            "stage_transition",
            "pre_complete",
            "stop_delivery",
        ):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workflow = handed_off_workflow(root)
                active = activate_host_goal(workflow)
                objective = active["host_goal_binding"]["objective"]
                gate = active["next_gate"]
                first = workflow.prepare_host_goal_reconciliation(
                    "stage_transition", target_gate=gate, host_turn_id="turn-active"
                )
                authorized = workflow.record_host_goal_observation(
                    first["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective),
                    },
                )
                self.assertIsNotNone(
                    authorized["host_goal_binding"]["authorized_transition"]
                )
                second = workflow.prepare_host_goal_reconciliation(
                    operation, target_gate=gate, host_turn_id="turn-blocked"
                )
                blocked = workflow.record_host_goal_observation(
                    second["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective, status="blocked"),
                    },
                )
                self.assertEqual(
                    blocked["host_goal_binding"]["status"], "blocked"
                )
                self.assertIsNone(
                    blocked["host_goal_binding"]["authorized_transition"]
                )

    def test_recovery_accepts_only_current_task_stage_authorization_stale_before_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, task = self._blocked(root)
            before = (root / ".product-delivery/state.json").read_bytes()
            result = workflow.recover_orphaned_blocked_host_goal_current_task(
                **self._request(root, objective)
            )
            self.assertEqual(result["result"], "dry_run")
            self.assertEqual(result["next_gate"], task)
            self.assertEqual((root / ".product-delivery/state.json").read_bytes(), before)

            request = self._request(root, objective)
            request["dry_run"] = False
            stale = workflow.status()["host_goal_binding"]["authorized_transition"]
            expected_stale_hash = hashlib.sha256(
                json.dumps(
                    stale,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
            ).hexdigest()
            workflow.recover_orphaned_blocked_host_goal_current_task(**request)
            recovered = workflow.status()
            recovery = recovered["host_goal_binding"][
                "orphaned_blocked_recovery"
            ]
            self.assertEqual(
                recovery["stale_authorized_transition_sha256"],
                expected_stale_hash,
            )
            archived = recovered["host_goal_binding_history"][-1]
            self.assertEqual(
                archived["stale_authorized_transition_sha256"],
                expected_stale_hash,
            )
            event = recovered["transition_journal"]["events"][-1]
            self.assertEqual(
                event["input_artifact_hashes"]["stale_authorized_transition"],
                expected_stale_hash,
            )
            self.assertEqual(
                recovered["host_goal_binding"]["authorized_transition"][
                    "operation"
                ],
                "user_resume",
            )

    def test_recovery_rejects_foreign_or_non_stage_stale_authorization(self):
        for field, value in (
            ("target_gate", "TASK-999"),
            ("operation", "pre_complete"),
            ("operation", "stop_delivery"),
            ("operation", "complete_goal"),
            ("operation", "unknown"),
            ("authorized_at", "not-a-timestamp"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workflow, objective, _task = self._blocked(root)
                state = workflow.status()
                state["host_goal_binding"]["authorized_transition"][field] = value
                write_state(root, state)
                with self.assertRaisesRegex(WorkflowError, "authorized transition"):
                    workflow.recover_orphaned_blocked_host_goal_current_task(
                        **self._request(root, objective)
                    )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, _task = self._blocked(root)
            state = workflow.status()
            state["host_goal_binding"]["last_observed_status"] = "active"
            write_state(root, state)
            with self.assertRaisesRegex(WorkflowError, "authorized transition"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective)
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, _task = self._blocked(root)
            state = workflow.status()
            state["host_goal_binding"]["authorized_transition"]["unexpected"] = True
            write_state(root, state)
            with self.assertRaisesRegex(WorkflowError, "authorized transition"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective)
                )

    def test_recovery_migrates_exact_cr006_fixed_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, task = self._blocked(root)
            state = workflow.status()
            state["runtime_provenance"] = dict(CR006_FIXED_RUNTIME_RECEIPT)
            write_state(root, state)
            request = self._request(root, objective)
            request["dry_run"] = False

            result = workflow.recover_orphaned_blocked_host_goal_current_task(
                **request
            )
            recovered = workflow.status()

            self.assertEqual(result["result"], "recovered")
            self.assertEqual(result["next_gate"], task)
            self.assertNotEqual(
                recovered["runtime_provenance"], CR006_FIXED_RUNTIME_RECEIPT
            )
            self.assertEqual(
                recovered["transition_journal"]["events"][-2]["transition_name"],
                "runtime_receipt_recovered",
            )

    def test_legacy_generic_authorization_cannot_recover_stale_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, _task = self._blocked(root)
            request = self._request(root, objective)
            request["authorization_message"] = (
                "授权执行可审计的 Waygate 1.1.0 orphaned blocked-binding 恢复"
            )
            with self.assertRaisesRegex(WorkflowError, "exact CR007"):
                workflow.recover_orphaned_blocked_host_goal_current_task(**request)

    def test_generic_recovery_cannot_migrate_cr006_fixed_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective, _task = self._blocked(root)
            state = workflow.status()
            state["runtime_provenance"] = dict(CR006_FIXED_RUNTIME_RECEIPT)
            state["host_goal_binding"]["authorized_transition"] = None
            write_state(root, state)
            request = self._request(root, objective)
            request["authorization_message"] = (
                "授权执行可审计的 Waygate 1.1.0 orphaned blocked-binding 恢复"
            )
            with self.assertRaisesRegex(WorkflowError, "generic.*provenance"):
                workflow.recover_orphaned_blocked_host_goal_current_task(**request)


if __name__ == "__main__":
    unittest.main()
