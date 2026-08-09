import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    initialize_workspace,
    load_state,
    write_state,
)
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.gatekeeper import PLUGIN_VERSION
from product_delivery_agent.transition_journal import append_transition
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    goal_result,
    handed_off_workflow,
)
from tests.test_launch_package_supersession_v1018 import task_completion_artifact


COORDINATOR_THREAD_ID = "thread-v1026-coordinator"
RECOVERY_SUBAGENT_THREAD_ID = "thread-v1026-recovery-subagent"
FRESH_THREAD_ID = "thread-v1026-fresh-owner"
OWNER_CLAIM_MESSAGE = "恢复交付主线程，接管当前 Host Goal"


def classroom_v1025_state(project_root: Path) -> tuple[ProductDeliveryWorkflow, dict]:
    with patch.dict(
        os.environ,
        {"CODEX_THREAD_ID": RECOVERY_SUBAGENT_THREAD_ID},
    ):
        workflow = handed_off_workflow(project_root)
        activate_host_goal(workflow)
        state = workflow.status()
        while len(state["transition_journal"]["events"]) < 40:
            state = append_transition(
                state,
                "classroom_v146_fixture_transition",
                feature_slug=state["feature_slug"],
                runtime_version="1.0.25",
                metadata={
                    "fixture_sequence": len(state["transition_journal"]["events"])
                    + 1
                },
            )
        state["stage"] = "executed_browser_evidence_passed"
        state["next_gate"] = "feature_closure_after_implementation"
        state["classroom_recovery_fixture"] = {
            "prototype_revision": "r40",
            "artifact_sha256": "a" * 64,
            "task_ids": ["TASK-001"],
            "review_ids": ["scenario", "test_coverage", "test_implementation"],
        }
        write_state(project_root, state)
        pending = workflow.prepare_host_goal_reconciliation(
            "stage_transition",
            target_gate="feature_closure_after_implementation",
            host_turn_id="v146-r40-conformance-record-20260731",
        )
        legacy = workflow.status()

    legacy.pop("host_goal_owner", None)
    legacy["runtime_version"] = "1.0.25"
    legacy["plugin_version"] = "1.0.25"
    legacy["host_goal_binding"].pop("owner_thread_id", None)
    legacy["host_goal_binding"]["host_identifiers"] = {
        "threadId": RECOVERY_SUBAGENT_THREAD_ID
    }
    write_state(project_root, legacy)
    return workflow, pending


class HostGoalOwnerV1026Tests(unittest.TestCase):
    def test_startup_captures_current_codex_thread_as_delivery_coordinator(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = ProductDeliveryWorkflow(Path(tmp))
            state = workflow.start(
                feature_slug="v1.4.6-unit-progress-sequential-unlock",
                multi_agent_mode="spawned_subagents_authorized",
            )

            self.assertEqual(state["host_goal_owner"]["status"], "claimed")
            self.assertEqual(
                state["host_goal_owner"]["coordinator_thread_id"],
                COORDINATOR_THREAD_ID,
            )
            self.assertEqual(
                state["host_goal_owner"]["delivery_id"], state["delivery_id"]
            )
            self.assertEqual(
                state["host_goal_owner"]["feature_slug"], state["feature_slug"]
            )

    def test_same_thread_activation_binds_goal_to_coordinator(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)

            self.assertEqual(
                active["host_goal_binding"]["owner_thread_id"],
                COORDINATOR_THREAD_ID,
            )
            self.assertEqual(
                active["host_goal_binding"]["host_identifiers"]["threadId"],
                COORDINATOR_THREAD_ID,
            )

    def test_different_thread_cannot_prepare_or_record_goal_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            checkpoint = workflow.prepare_host_goal_activation()

            with patch.dict(
                os.environ,
                {"CODEX_THREAD_ID": RECOVERY_SUBAGENT_THREAD_ID},
            ):
                with self.assertRaisesRegex(WorkflowError, "coordinator thread"):
                    workflow.prepare_host_goal_activation()
                with self.assertRaisesRegex(WorkflowError, "coordinator thread"):
                    workflow.record_host_goal_observation(
                        checkpoint["checkpoint_id"],
                        {
                            "observation_source": "codex_goal_tool",
                            "tool": "get_goal",
                            "result": {"goal": None},
                        },
                    )

            self.assertEqual(
                workflow.status()["host_goal_binding"]["pending_checkpoint"][
                    "checkpoint_id"
                ],
                checkpoint["checkpoint_id"],
            )

    def test_different_thread_cannot_write_post_handoff_canonical_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            activate_host_goal(workflow)

            with patch.dict(
                os.environ,
                {"CODEX_THREAD_ID": RECOVERY_SUBAGENT_THREAD_ID},
            ):
                with self.assertRaisesRegex(WorkflowError, "coordinator thread"):
                    workflow.record_task_completion(
                        "TASK-001",
                        artifact=task_completion_artifact(
                            workflow.status(), "TASK-001"
                        ),
                    )

    def test_missing_codex_thread_id_blocks_host_goal_operations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            with patch.dict(os.environ, {"CODEX_THREAD_ID": ""}):
                with self.assertRaisesRegex(WorkflowError, "CODEX_THREAD_ID"):
                    workflow.prepare_host_goal_activation()

    def test_observed_goal_thread_must_match_coordinator(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            inspection = workflow.prepare_host_goal_activation()
            workflow.record_host_goal_observation(
                inspection["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": {"goal": None},
                },
            )
            creation = workflow.prepare_host_goal_activation()

            with self.assertRaisesRegex(WorkflowError, "threadId"):
                workflow.record_host_goal_observation(
                    creation["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "create_goal",
                        "result": goal_result(
                            creation["objective"],
                            thread_id=RECOVERY_SUBAGENT_THREAD_ID,
                        ),
                    },
                )

    def test_active_binding_requires_persisted_matching_goal_thread(self):
        for observed_thread_id in (None, RECOVERY_SUBAGENT_THREAD_ID):
            with self.subTest(
                observed_thread_id=observed_thread_id
            ), tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ,
                {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
            ):
                project_root = Path(tmp)
                workflow = handed_off_workflow(project_root)
                active = activate_host_goal(workflow)
                state = workflow.status()
                if observed_thread_id is None:
                    state["host_goal_binding"]["host_identifiers"].pop(
                        "threadId", None
                    )
                else:
                    state["host_goal_binding"]["host_identifiers"][
                        "threadId"
                    ] = observed_thread_id
                write_state(project_root, state)

                with self.assertRaisesRegex(WorkflowError, "threadId"):
                    workflow.prepare_host_goal_reconciliation(
                        "stage_transition",
                        target_gate=active["next_gate"],
                    )

    def test_pause_and_resume_require_post_handoff_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)
            objective = active["host_goal_binding"]["objective"]

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.pause()

            pause_checkpoint = workflow.prepare_host_goal_reconciliation(
                "stage_transition",
                target_gate=active["next_gate"],
            )
            workflow.record_host_goal_observation(
                pause_checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(
                        objective, thread_id=COORDINATOR_THREAD_ID
                    ),
                },
            )
            paused = workflow.pause()
            self.assertTrue(paused["paused"])

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.resume()

            resume_checkpoint = workflow.prepare_host_goal_reconciliation(
                "stage_transition",
                target_gate=paused["next_gate"],
            )
            workflow.record_host_goal_observation(
                resume_checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(
                        objective, thread_id=COORDINATOR_THREAD_ID
                    ),
                },
            )
            resumed = workflow.resume()
            self.assertFalse(resumed["paused"])

    def test_v1025_active_state_migrates_without_inferring_coordinator(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            classroom_v1025_state(project_root)

            migrated = load_state(project_root)

            self.assertEqual(
                migrated["host_goal_owner"]["status"], "legacy_unverified"
            )
            self.assertIsNone(
                migrated["host_goal_owner"].get("coordinator_thread_id")
            )
            self.assertEqual(
                migrated["host_goal_binding"]["host_identifiers"]["threadId"],
                RECOVERY_SUBAGENT_THREAD_ID,
            )
            self.assertEqual(
                migrated["classroom_recovery_fixture"]["prototype_revision"],
                "r40",
            )

    def test_active_or_blocked_goal_in_candidate_thread_rejects_owner_transfer(self):
        for status in ("active", "blocked"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp)
                classroom_v1025_state(project_root)
                with patch.dict(
                    os.environ,
                    {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
                ):
                    workflow = ProductDeliveryWorkflow(project_root)
                    before = copy.deepcopy(workflow.status())
                    with self.assertRaisesRegex(
                        WorkflowError, "recover_legacy_active_delivery"
                    ):
                        workflow.prepare_host_goal_owner_claim(
                            OWNER_CLAIM_MESSAGE
                        )

                    after = workflow.status()
                    self.assertEqual(
                        after["host_goal_binding"], before["host_goal_binding"]
                    )
                    self.assertEqual(
                        after["transition_journal"], before["transition_journal"]
                    )

    def test_legacy_owner_claim_recovery_is_rejected_before_checkpoint_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            classroom_v1025_state(project_root)
            with patch.dict(os.environ, {"CODEX_THREAD_ID": FRESH_THREAD_ID}):
                workflow = ProductDeliveryWorkflow(project_root)
                with self.assertRaisesRegex(
                    WorkflowError, "recover_legacy_active_delivery"
                ):
                    workflow.prepare_host_goal_owner_claim(OWNER_CLAIM_MESSAGE)

    def test_completed_goal_in_fresh_thread_does_not_recover_legacy_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            classroom_v1025_state(project_root)
            with patch.dict(os.environ, {"CODEX_THREAD_ID": FRESH_THREAD_ID}):
                workflow = ProductDeliveryWorkflow(project_root)
                with self.assertRaisesRegex(
                    WorkflowError, "recover_legacy_active_delivery"
                ):
                    workflow.prepare_host_goal_owner_claim(OWNER_CLAIM_MESSAGE)

    def test_foreign_runtime_thread_is_reported_as_owner_recovery(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)

            with patch.dict(
                os.environ,
                {"CODEX_THREAD_ID": RECOVERY_SUBAGENT_THREAD_ID},
            ):
                continuation = derive_continuation_status(active)

            self.assertEqual(continuation["status"], "wait_for_user")
            self.assertEqual(
                continuation["next_action"], "host_goal_owner_recovery"
            )
            self.assertIn(
                "host_goal_owner:current_thread_mismatch",
                continuation["blockers"],
            )

    def test_legacy_synthetic_recovery_gate_is_not_restored_after_transfer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            legacy = workflow.status()
            legacy.pop("host_goal_owner", None)
            legacy.pop("host_goal_binding", None)
            legacy["next_gate"] = None
            legacy["runtime_version"] = "1.0.23"
            legacy["plugin_version"] = "1.0.23"
            write_state(project_root, legacy)

            migrated = load_state(project_root)
            self.assertEqual(migrated["next_gate"], "host_goal_owner_recovery")
            with self.assertRaisesRegex(
                WorkflowError, "recover_legacy_active_delivery"
            ):
                ProductDeliveryWorkflow(project_root).prepare_host_goal_owner_claim(
                    OWNER_CLAIM_MESSAGE
                )

    def test_fresh_recovery_archives_legacy_owner_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            classroom_v1025_state(project_root)
            migrated = load_state(project_root)
            original_marker = copy.deepcopy(migrated["classroom_recovery_fixture"])

            with patch.dict(os.environ, {"CODEX_THREAD_ID": FRESH_THREAD_ID}):
                workflow = ProductDeliveryWorkflow(project_root)
                recovered = workflow.recover_legacy_active_delivery()
                self.assertNotEqual(recovered["delivery_id"], migrated["delivery_id"])
                snapshot = project_root / recovered["previous_delivery"]["state_snapshot_path"]
                self.assertEqual(
                    json.loads(snapshot.read_text(encoding="utf-8"))["classroom_recovery_fixture"],
                    original_marker,
                )

    def test_terminal_history_does_not_require_owner_migration(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID},
        ):
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            state = workflow.status()
            state["status"] = "closed"
            state["active"] = False
            state.pop("host_goal_owner", None)
            state_path = project_root / ".product-delivery" / "state.json"
            state_path.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            original_bytes = state_path.read_bytes()

            loaded = ProductDeliveryWorkflow(project_root).status()

            self.assertEqual(loaded["host_goal_owner"]["status"], "not_required")
            self.assertEqual(state_path.read_bytes(), original_bytes)
            initialized = initialize_workspace(project_root)
            self.assertEqual(
                initialized["host_goal_owner"]["status"], "not_required"
            )
            self.assertEqual(state_path.read_bytes(), original_bytes)

    def test_inspect_owner_context_reports_classroom_thread_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            classroom_v1025_state(project_root)
            with patch.dict(os.environ, {"CODEX_THREAD_ID": COORDINATOR_THREAD_ID}):
                context = ProductDeliveryWorkflow(
                    project_root
                ).inspect_host_goal_owner_context()

            self.assertEqual(context["owner_status"], "legacy_unverified")
            self.assertEqual(
                context["observed_binding_thread_id"],
                RECOVERY_SUBAGENT_THREAD_ID,
            )
            self.assertEqual(context["current_thread_id"], COORDINATOR_THREAD_ID)
            self.assertTrue(context["owner_transfer_required"])


if __name__ == "__main__":
    unittest.main()
