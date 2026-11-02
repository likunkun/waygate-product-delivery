import copy
import hashlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.artifact_store import ensure_delivery_layout
from product_delivery_agent.host_goal import stable_hash
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


OWNER_THREAD_ID = "thread-cr006-owner"
FEATURE_SLUG = "v2.1-classroom-quiz-ai-analysis"
AUTHORIZATION = (
    "授权发起 CR006：修复 Waygate shared-overflow comparator，"
    "并按修复版 runtime 的受支持迁移入口恢复当前 delivery"
)
SOURCE_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.1.0",
    "package_root_sha256": "8" * 64,
}
TARGET_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.1.0",
    "package_root_sha256": "9" * 64,
}


@patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID})
class SharedOverflowRuntimeRecoveryV111Tests(unittest.TestCase):
    def _recover(self, workflow: ProductDeliveryWorkflow, request: dict):
        self.assertTrue(
            hasattr(workflow, "recover_shared_overflow_runtime_receipt"),
            "supported shared-overflow runtime recovery entry is missing",
        )
        return workflow.recover_shared_overflow_runtime_receipt(request)

    def _write_source_state(self, project_root: Path) -> dict:
        state = ProductDeliveryWorkflow(project_root).start(
            feature_slug=FEATURE_SLUG,
            multi_agent_mode="spawned_subagents_authorized",
        )
        objective = "Complete the pinned CR006 delivery"
        binding_nonce = "binding-cr006"
        state["runtime_provenance"] = dict(SOURCE_RECEIPT)
        state["stage"] = "implementation_in_progress"
        state["next_gate"] = "TASK-036"
        state["host_goal_binding"] = {
            "delivery_id": state["delivery_id"],
            "feature_slug": FEATURE_SLUG,
            "binding_nonce": binding_nonce,
            "objective": objective,
            "objective_sha256": stable_hash(objective),
            "owner_thread_id": OWNER_THREAD_ID,
            "host_identifiers": {"threadId": OWNER_THREAD_ID},
            "status": "active",
            "resume_gate": "TASK-036",
            "human_wait": None,
            "pending_checkpoint": None,
            "authorized_transition": None,
        }
        completed = [f"TASK-{index:03d}" for index in range(1, 36)]
        planned = [
            {"task_id": f"TASK-{index:03d}"} for index in range(1, 45)
        ]
        state["delivery_goal"] = {
            "status": "implementation_in_progress",
            "current_task_cursor": "TASK-036",
            "completed_tasks": completed,
            "planned_tasks": planned,
            "launch_package_hash": "c" * 64,
        }
        state["implementation"] = {
            "current_task": "TASK-036",
            "completed_tasks": completed,
            "visual_failures": [{"task_id": "TASK-036", "status": "failed"}],
        }
        write_state(project_root, state)
        persisted = load_state(project_root)
        persisted["stage"] = "implementation_in_progress"
        persisted["next_gate"] = "TASK-036"
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        state_path.write_text(
            json.dumps(persisted, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        ensure_delivery_layout(project_root, persisted)
        return load_state(project_root)

    @contextmanager
    def _pin_fixture(self, project_root: Path):
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        journal = state["transition_journal"]
        binding = state["host_goal_binding"]
        with patch.multiple(
            "product_delivery_agent.workflow",
            SHARED_OVERFLOW_RECOVERY_TARGET_DELIVERY_ID=state["delivery_id"],
            SHARED_OVERFLOW_RECOVERY_TARGET_FEATURE_SLUG=state["feature_slug"],
            SHARED_OVERFLOW_RECOVERY_TARGET_OWNER_THREAD_ID=OWNER_THREAD_ID,
            SHARED_OVERFLOW_RECOVERY_TARGET_BINDING_NONCE=binding["binding_nonce"],
            SHARED_OVERFLOW_RECOVERY_TARGET_OBJECTIVE_SHA256=binding[
                "objective_sha256"
            ],
            SHARED_OVERFLOW_RECOVERY_TARGET_STATE_SHA256=hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
            SHARED_OVERFLOW_RECOVERY_TARGET_JOURNAL_EVENT_COUNT=len(
                journal["events"]
            ),
            SHARED_OVERFLOW_RECOVERY_TARGET_JOURNAL_LAST_HASH=journal[
                "last_event_hash"
            ],
            SHARED_OVERFLOW_RECOVERY_SOURCE_RECEIPT=SOURCE_RECEIPT,
            create=True,
        ), patch(
            "product_delivery_agent.workflow.current_runtime_provenance",
            return_value=TARGET_RECEIPT,
        ), patch(
            "product_delivery_agent.artifact_protocol.current_runtime_provenance",
            return_value=TARGET_RECEIPT,
        ):
            yield state

    @staticmethod
    def _request(project_root: Path, state: dict, *, dry_run: bool) -> dict:
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        journal = state["transition_journal"]
        binding = state["host_goal_binding"]
        return {
            "schema_version": "v1",
            "action": "recover_shared_overflow_runtime_receipt",
            "authorization_message": AUTHORIZATION,
            "delivery_id": state["delivery_id"],
            "feature_slug": state["feature_slug"],
            "owner_thread_id": OWNER_THREAD_ID,
            "binding_nonce": binding["binding_nonce"],
            "expected_objective_sha256": binding["objective_sha256"],
            "expected_state_sha256": hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
            "expected_journal_event_count": len(journal["events"]),
            "expected_journal_last_hash": journal["last_event_hash"],
            "dry_run": dry_run,
        }

    def test_dry_run_is_read_only_and_formal_recovery_preserves_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            before = self._write_source_state(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()
            protected = copy.deepcopy(before)
            for key in ("runtime_provenance", "transition_journal", "updated_at"):
                protected.pop(key, None)

            with self._pin_fixture(project_root):
                dry_request = self._request(project_root, before, dry_run=True)
                dry_result = self._recover(
                    ProductDeliveryWorkflow(project_root), dry_request
                )
                self.assertEqual(dry_result["result"], "dry_run_passed")
                self.assertEqual(state_path.read_bytes(), before_bytes)

                formal_request = {**dry_request, "dry_run": False}
                recovered = self._recover(
                    ProductDeliveryWorkflow(project_root), formal_request
                )

            self.assertEqual(recovered["runtime_provenance"], TARGET_RECEIPT)
            self.assertEqual(
                recovered["transition_journal"]["events"][:-1],
                before["transition_journal"]["events"],
            )
            event = recovered["transition_journal"]["events"][-1]
            self.assertEqual(event["transition_name"], "runtime_receipt_recovered")
            self.assertEqual(
                event["metadata"]["recovery_scope"],
                "shared_overflow_comparator_v111",
            )
            actual_protected = copy.deepcopy(recovered)
            for key in ("runtime_provenance", "transition_journal", "updated_at"):
                actual_protected.pop(key, None)
            self.assertEqual(actual_protected, protected)

    def test_rejects_non_exact_authorization_unknown_receipt_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_source_state(project_root)
            request = self._request(project_root, state, dry_run=True)
            workflow = ProductDeliveryWorkflow(project_root)

            with self._pin_fixture(project_root):
                with self.assertRaisesRegex(WorkflowError, "exact explicit user authorization"):
                    self._recover(
                        workflow,
                        {**request, "authorization_message": "继续"}
                    )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            mutated = self._write_source_state(project_root)
            mutated["runtime_provenance"] = {
                **SOURCE_RECEIPT,
                "package_root_sha256": "f" * 64,
            }
            write_state(project_root, mutated)
            mutated = load_state(project_root)
            request = self._request(project_root, mutated, dry_run=True)
            workflow = ProductDeliveryWorkflow(project_root)
            with self._pin_fixture(project_root):
                with self.assertRaisesRegex(WorkflowError, "source runtime receipt"):
                    self._recover(workflow, request)

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_source_state(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            with self._pin_fixture(project_root):
                formal = self._request(project_root, state, dry_run=False)
                self._recover(workflow, formal)
                with self.assertRaisesRegex(
                    WorkflowError, "state snapshot|invalid_runtime"
                ):
                    self._recover(workflow, formal)

    def test_rejects_stale_snapshot_binding_and_foreign_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_source_state(project_root)
            request = self._request(project_root, state, dry_run=True)
            workflow = ProductDeliveryWorkflow(project_root)

            with self._pin_fixture(project_root):
                with self.assertRaisesRegex(WorkflowError, "state snapshot"):
                    self._recover(
                        workflow,
                        {**request, "expected_state_sha256": "0" * 64}
                    )
                with self.assertRaisesRegex(WorkflowError, "binding_nonce"):
                    self._recover(
                        workflow,
                        {**request, "binding_nonce": "foreign"}
                    )
                with patch.dict(os.environ, {"CODEX_THREAD_ID": "foreign-thread"}):
                    with self.assertRaisesRegex(WorkflowError, "coordinator thread"):
                        self._recover(workflow, request)


if __name__ == "__main__":
    unittest.main()
