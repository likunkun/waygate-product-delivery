import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.artifact_protocol import current_runtime_provenance
from product_delivery_agent.transition_journal import journal_integrity_errors
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    handed_off_workflow,
    goal_result,
)


OWNER_THREAD_ID = "thread-v110-orphaned-recovery"
AUTHORIZATION_MESSAGE = "授权执行可审计的 Waygate 1.1.0 orphaned blocked-binding 恢复"
PUBLISHED_1100_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.1.0",
    "package_root_sha256": "dde3c69c8dd26b0ada675e914f01d75cf062f3ff1c99a3b0e4882b4c9836f50f",
}


@patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID})
class OrphanedBlockedGoalRecoveryV110Tests(unittest.TestCase):
    def _blocked_workflow(self, project_root: Path):
        workflow = handed_off_workflow(project_root)
        active = activate_host_goal(workflow)
        state = workflow.status()
        binding = state["host_goal_binding"]
        binding.update(
            {
                "status": "blocked",
                "last_observed_status": "blocked",
                "pending_checkpoint": None,
                "human_wait": None,
                "authorized_transition": None,
                "resume_gate": "STALE-TASK",
            }
        )
        state["next_gate"] = "host_goal_resume_required"
        write_state(project_root, state)
        return workflow, active["host_goal_binding"]["objective"]

    def _request(self, project_root: Path, objective: str, *, dry_run: bool):
        state_path = project_root / ".product-delivery" / "state.json"
        return {
            "expected_state_file_sha256": hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
            "authorization_message": AUTHORIZATION_MESSAGE,
            "host_turn_id": OWNER_THREAD_ID,
            "goal_observation": {
                "observation_source": "codex_goal_tool",
                "tool": "get_goal",
                "result": goal_result(objective),
            },
            "dry_run": dry_run,
        }

    def test_dry_run_is_non_mutating_and_targets_current_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state_path = root / ".product-delivery" / "state.json"
            before = state_path.read_bytes()

            result = workflow.recover_orphaned_blocked_host_goal_current_task(
                **self._request(root, objective, dry_run=True)
            )

            self.assertEqual(result["result"], "dry_run")
            self.assertEqual(result["next_gate"], "TASK-001")
            self.assertEqual(state_path.read_bytes(), before)

    def test_recovery_is_audited_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)

            recovered = workflow.recover_orphaned_blocked_host_goal_current_task(
                **self._request(root, objective, dry_run=False)
            )
            state = load_state(root)

            self.assertEqual(recovered["result"], "recovered")
            self.assertEqual(state["host_goal_binding"]["status"], "active")
            self.assertEqual(state["next_gate"], "TASK-001")
            self.assertEqual(
                state["host_goal_binding"]["authorized_transition"]["operation"],
                "user_resume",
            )
            self.assertEqual(
                state["transition_journal"]["events"][-1]["transition_name"],
                "host_goal_orphaned_binding_recovered",
            )
            self.assertEqual(journal_integrity_errors(state), [])

            repeated = workflow.recover_orphaned_blocked_host_goal_current_task(
                **self._request(root, objective, dry_run=False)
            )
            self.assertEqual(repeated["result"], "already_recovered")

    def test_identity_hash_and_active_goal_mismatches_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            request = self._request(root, objective, dry_run=True)

            with self.assertRaisesRegex(WorkflowError, "state file hash"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **{**request, "expected_state_file_sha256": "0" * 64}
                )
            with self.assertRaisesRegex(WorkflowError, "active"):
                blocked_observation = {
                    **request["goal_observation"],
                    "result": goal_result(objective, status="blocked"),
                }
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **{**request, "goal_observation": blocked_observation}
                )
            with self.assertRaisesRegex(WorkflowError, "objective"):
                wrong_observation = {
                    **request["goal_observation"],
                    "result": goal_result("different objective"),
                }
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **{**request, "goal_observation": wrong_observation}
                )

    def test_bound_goal_identifiers_must_match_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state = workflow.status()
            state["host_goal_binding"]["host_identifiers"] = {
                "threadId": OWNER_THREAD_ID,
                "goalId": "goal-bound",
            }
            write_state(root, state)
            request = self._request(root, objective, dry_run=True)
            request["goal_observation"]["result"]["goal"]["goalId"] = "goal-other"

            with self.assertRaisesRegex(WorkflowError, "identifier"):
                workflow.recover_orphaned_blocked_host_goal_current_task(**request)

    def test_non_implementation_lifecycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state = workflow.status()
            state.update({"status": "closure_failed", "stage": "closure_failed"})
            state["delivery_lifecycle"] = {"status": "paused"}
            write_state(root, state)

            with self.assertRaisesRegex(WorkflowError, "implementation"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective, dry_run=True)
                )

    def test_persistence_failure_rolls_back_root_and_delivery_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state = workflow.status()
            root_state = root / ".product-delivery" / "state.json"
            delivery_state = (
                root
                / ".product-delivery"
                / "deliveries"
                / state["feature_slug"]
                / state["delivery_id"]
                / "state.json"
            )
            before_root = root_state.read_bytes()
            before_delivery = delivery_state.read_bytes()

            with patch(
                "product_delivery_agent.artifact_store.ensure_delivery_layout",
                side_effect=RuntimeError("simulated mirror write failure"),
            ), self.assertRaisesRegex(WorkflowError, "persistence failed"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective, dry_run=False)
                )

            self.assertEqual(root_state.read_bytes(), before_root)
            self.assertEqual(delivery_state.read_bytes(), before_delivery)

    def test_concurrent_state_change_is_not_overwritten_during_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            root_state = root / ".product-delivery" / "state.json"
            external_bytes = b"external concurrent state\n"

            def concurrent_failure(project_root, persisted):
                root_state.write_bytes(external_bytes)
                raise RuntimeError("simulated concurrent write")

            with patch(
                "product_delivery_agent.artifact_store.ensure_delivery_layout",
                side_effect=concurrent_failure,
            ), self.assertRaisesRegex(WorkflowError, "concurrent"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective, dry_run=False)
                )

            self.assertEqual(root_state.read_bytes(), external_bytes)

    def test_concurrent_change_after_mirror_write_restores_mirror_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state = workflow.status()
            root_state = root / ".product-delivery" / "state.json"
            delivery_state = (
                root
                / ".product-delivery"
                / "deliveries"
                / state["feature_slug"]
                / state["delivery_id"]
                / "state.json"
            )
            before_delivery = delivery_state.read_bytes()
            external_bytes = b"external concurrent state after mirror\n"
            from product_delivery_agent.artifact_store import (
                ensure_delivery_layout as real_ensure_delivery_layout,
            )

            def mirror_then_concurrent(project_root, persisted):
                real_ensure_delivery_layout(project_root, persisted)
                root_state.write_bytes(external_bytes)
                raise RuntimeError("simulated concurrent write after mirror")

            with patch(
                "product_delivery_agent.artifact_store.ensure_delivery_layout",
                side_effect=mirror_then_concurrent,
            ), self.assertRaisesRegex(WorkflowError, "concurrent"):
                workflow.recover_orphaned_blocked_host_goal_current_task(
                    **self._request(root, objective, dry_run=False)
                )

            self.assertEqual(root_state.read_bytes(), external_bytes)
            self.assertEqual(delivery_state.read_bytes(), before_delivery)

    def test_recovery_migrates_exact_published_v110_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, objective = self._blocked_workflow(root)
            state = workflow.status()
            state["runtime_provenance"] = dict(PUBLISHED_1100_RECEIPT)
            write_state(root, state)

            recovered = workflow.recover_orphaned_blocked_host_goal_current_task(
                **self._request(root, objective, dry_run=False)
            )
            state = load_state(root)

            self.assertEqual(recovered["result"], "recovered")
            self.assertEqual(state["runtime_provenance"], current_runtime_provenance())
            self.assertEqual(
                state["transition_journal"]["events"][-2]["transition_name"],
                "runtime_receipt_recovered",
            )
            self.assertEqual(
                state["transition_journal"]["events"][-1]["transition_name"],
                "host_goal_orphaned_binding_recovered",
            )


if __name__ == "__main__":
    unittest.main()
