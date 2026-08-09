import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import write_state
from product_delivery_agent.gatekeeper import PLUGIN_VERSION
from product_delivery_agent.host_goal import stable_hash
from product_delivery_agent.transition_journal import append_transition
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    goal_result,
    handed_off_workflow,
)


def stale_activation_checkpoint(
    project_root: Path,
) -> tuple[ProductDeliveryWorkflow, dict, list[dict]]:
    workflow = handed_off_workflow(project_root)
    workflow.prepare_host_goal_activation()
    checkpoint = copy.deepcopy(
        workflow.status()["host_goal_binding"]["pending_checkpoint"]
    )
    state = workflow.status()
    state["classroom_recovery_fixture"] = {
        "prototype_revision": "r40",
        "artifact_sha256": "a" * 64,
        "task_ids": ["TASK-001"],
        "review_ids": ["scenario", "test_coverage", "test_implementation"],
    }
    state = append_transition(
        state,
        "executed_browser_evidence_recorded",
        feature_slug=state["feature_slug"],
        runtime_version="1.0.8",
        input_artifact_hashes={"r40": "a" * 64},
        output_artifact_hashes={"browser_evidence": "b" * 64},
        metadata={"fixture": "classroom-v1.4.6"},
        occurred_at="2099-01-01T00:00:00+00:00",
    )
    write_state(project_root, state)
    return (
        workflow,
        checkpoint,
        copy.deepcopy(state["transition_journal"]["events"]),
    )


@patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-v1024"})
class HostGoalCheckpointRecoveryV1025Tests(unittest.TestCase):
    def test_stale_activation_checkpoint_recovers_and_completes_handshake(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, old_checkpoint, original_events = stale_activation_checkpoint(
                Path(tmp)
            )
            before = workflow.status()
            original_delivery_goal = copy.deepcopy(before["delivery_goal"])
            original_marker = copy.deepcopy(before["classroom_recovery_fixture"])
            state = workflow.status()
            state["host_goal_binding"]["resume_gate"] = (
                "record_executed_evidence_and_closure"
            )
            state["next_gate"] = "feature_closure_after_implementation"
            state = append_transition(
                state,
                "prototype_production_conformance_recorded",
                feature_slug=state["feature_slug"],
                runtime_version="1.0.8",
                metadata={"fixture": "current-closure-gate"},
                occurred_at="2099-01-02T00:00:00+00:00",
            )
            write_state(Path(tmp), state)
            original_events = copy.deepcopy(
                state["transition_journal"]["events"]
            )

            with self.assertRaisesRegex(WorkflowError, "projection is stale"):
                workflow.record_host_goal_observation(
                    old_checkpoint["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": {"goal": None},
                    },
                )
            with self.assertRaisesRegex(
                WorkflowError, "recover_stale_host_goal_checkpoint"
            ):
                workflow.prepare_host_goal_activation()

            recovered = workflow.recover_stale_host_goal_checkpoint(
                old_checkpoint["checkpoint_id"]
            )
            self.assertEqual(recovered["operation"], "inspect_before_activation")
            self.assertEqual(recovered["required_tool"], "get_goal")
            self.assertNotEqual(
                recovered["checkpoint_id"], old_checkpoint["checkpoint_id"]
            )

            state = workflow.status()
            binding = state["host_goal_binding"]
            self.assertEqual(binding["status"], "activation_pending")
            self.assertEqual(binding["generation"], 1)
            self.assertEqual(
                binding["binding_nonce"],
                before["host_goal_binding"]["binding_nonce"],
            )
            self.assertEqual(binding["objective"], before["host_goal_binding"]["objective"])
            self.assertEqual(state["delivery_id"], before["delivery_id"])
            self.assertEqual(state["feature_slug"], before["feature_slug"])
            self.assertEqual(state["delivery_goal"], original_delivery_goal)
            self.assertEqual(state["classroom_recovery_fixture"], original_marker)

            archive = binding["checkpoint_history"][-1]
            self.assertEqual(
                archive["checkpoint"]["checkpoint_id"],
                old_checkpoint["checkpoint_id"],
            )
            self.assertEqual(
                archive["replacement_checkpoint_id"], recovered["checkpoint_id"]
            )
            self.assertEqual(
                archive["stored_projection_sha256"],
                old_checkpoint["projection_sha256"],
            )
            self.assertNotEqual(
                archive["stored_projection_sha256"],
                archive["current_projection_sha256"],
            )
            self.assertEqual(archive["intervening_transition_start"], 3)
            self.assertEqual(
                archive["intervening_transition_end"], len(original_events)
            )
            self.assertIn("1.0.8", archive["intervening_runtime_versions"])
            self.assertEqual(
                archive["intervening_transition_range_basis"],
                "checkpoint_last_event_hash",
            )
            self.assertIn(
                old_checkpoint["checkpoint_id"],
                binding["superseded_checkpoint_ids"],
            )

            events = state["transition_journal"]["events"]
            self.assertEqual(events[:-1], original_events)
            self.assertEqual(
                events[-1]["transition_name"], "host_goal_checkpoint_superseded"
            )
            self.assertEqual(
                events[-1]["previous_event_hash"], original_events[-1]["event_hash"]
            )
            self.assertEqual(
                events[-1]["output_artifact_hashes"]["checkpoint_archive"],
                stable_hash(archive),
            )
            pending = binding["pending_checkpoint"]
            self.assertEqual(pending["checkpoint_id"], recovered["checkpoint_id"])
            self.assertEqual(pending["transition_sequence"], len(events))
            self.assertEqual(
                pending["transition_last_event_hash"],
                state["transition_journal"]["last_event_hash"],
            )

            with self.assertRaisesRegex(WorkflowError, "superseded"):
                workflow.record_host_goal_observation(
                    old_checkpoint["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": {"goal": None},
                    },
                )

            event_count = len(events)
            idempotent = workflow.recover_stale_host_goal_checkpoint(
                old_checkpoint["checkpoint_id"]
            )
            self.assertEqual(idempotent["checkpoint_id"], recovered["checkpoint_id"])
            self.assertEqual(
                len(workflow.status()["transition_journal"]["events"]), event_count
            )

            after_missing = workflow.record_host_goal_observation(
                recovered["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": {"goal": None},
                },
            )
            self.assertEqual(
                after_missing["host_goal_binding"]["status"], "creation_ready"
            )
            creation = workflow.prepare_host_goal_activation()
            workflow.record_host_goal_observation(
                creation["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "create_goal",
                    "result": goal_result(creation["objective"]),
                },
            )
            verification = workflow.prepare_host_goal_activation()
            active = workflow.record_host_goal_observation(
                verification["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(creation["objective"]),
                },
            )
            self.assertEqual(active["host_goal_binding"]["status"], "active")
            self.assertEqual(
                active["next_gate"], "feature_closure_after_implementation"
            )

    def test_recovery_accepts_legacy_checkpoint_projection_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            state = workflow.status()
            pending = state["host_goal_binding"]["pending_checkpoint"]
            pending["transition_sequence"] = 3
            pending.pop("transition_last_event_hash", None)
            pending["projection_sha256"] = "c" * 64
            pending["issued_at"] = "2098-01-01T00:00:00+00:00"
            write_state(Path(tmp), state)

            recovered = workflow.recover_stale_host_goal_checkpoint(
                checkpoint["checkpoint_id"]
            )

            self.assertEqual(recovered["operation"], "inspect_before_activation")
            archive = workflow.status()["host_goal_binding"]["checkpoint_history"][-1]
            self.assertEqual(archive["checkpoint"]["transition_sequence"], 3)
            self.assertEqual(archive["stored_projection_sha256"], "c" * 64)
            self.assertEqual(
                archive["intervening_transition_start"],
                3,
            )
            self.assertEqual(
                archive["intervening_transition_range_basis"],
                "checkpoint_issued_at",
            )

    def test_recovery_rejects_wrong_identity_and_corrupt_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            state = workflow.status()
            state["host_goal_binding"]["pending_checkpoint"]["feature_slug"] = (
                "different-feature"
            )
            write_state(Path(tmp), state)
            with self.assertRaisesRegex(WorkflowError, "feature"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

    def test_recovery_rejects_unjournaled_projection_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            checkpoint = workflow.prepare_host_goal_activation()
            state = workflow.status()
            state["next_gate"] = "unjournaled-gate"
            write_state(project_root, state)

            with self.assertRaisesRegex(WorkflowError, "intervening transition"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

    def test_recovery_recomputes_canonical_objective_and_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            state = workflow.status()
            forged_objective = "Complete a forged delivery"
            forged_hash = stable_hash(forged_objective)
            state["host_goal_binding"]["objective"] = forged_objective
            state["host_goal_binding"]["objective_sha256"] = forged_hash
            state["host_goal_binding"]["pending_checkpoint"][
                "objective_sha256"
            ] = forged_hash
            write_state(Path(tmp), state)
            with self.assertRaisesRegex(WorkflowError, "canonical objective"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            state = workflow.status()
            state["host_goal_authorization"]["authorization_hash"] = "f" * 64
            state["host_goal_binding"]["authorization_hash"] = "f" * 64
            write_state(Path(tmp), state)
            with self.assertRaisesRegex(WorkflowError, "canonical authorization"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

    def test_idempotent_recovery_revalidates_current_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            workflow.recover_stale_host_goal_checkpoint(checkpoint["checkpoint_id"])
            state = workflow.status()
            state["host_goal_binding"]["delivery_id"] = "forged-delivery"
            write_state(Path(tmp), state)

            with self.assertRaisesRegex(WorkflowError, "delivery identity"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            workflow.recover_stale_host_goal_checkpoint(checkpoint["checkpoint_id"])
            state = workflow.status()
            state["host_goal_binding"]["pending_checkpoint"]["required_tool"] = (
                "create_goal"
            )
            write_state(Path(tmp), state)

            with self.assertRaisesRegex(
                WorkflowError, "replacement checkpoint lifecycle"
            ):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            workflow.recover_stale_host_goal_checkpoint(checkpoint["checkpoint_id"])
            state = workflow.status()
            state["host_goal_binding"]["checkpoint_history"][-1]["reason"] = (
                "mutated-archive"
            )
            write_state(Path(tmp), state)

            with self.assertRaisesRegex(WorkflowError, "archive hash"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            state = workflow.status()
            state["transition_journal"]["events"][-1]["metadata"]["tampered"] = True
            write_state(Path(tmp), state)
            with self.assertRaisesRegex(WorkflowError, "journal"):
                workflow.recover_stale_host_goal_checkpoint(
                    checkpoint["checkpoint_id"]
                )

    def test_recovery_restarts_any_pre_active_activation_lifecycle(self):
        for lifecycle_status in ("creation_ready", "verification_pending"):
            with self.subTest(lifecycle_status=lifecycle_status):
                with tempfile.TemporaryDirectory() as tmp:
                    project_root = Path(tmp)
                    workflow = handed_off_workflow(project_root)
                    inspection = workflow.prepare_host_goal_activation()
                    workflow.record_host_goal_observation(
                        inspection["checkpoint_id"],
                        {
                            "observation_source": "codex_goal_tool",
                            "tool": "get_goal",
                            "result": {"goal": None},
                        },
                    )
                    checkpoint = workflow.prepare_host_goal_activation()
                    if lifecycle_status == "verification_pending":
                        workflow.record_host_goal_observation(
                            checkpoint["checkpoint_id"],
                            {
                                "observation_source": "codex_goal_tool",
                                "tool": "create_goal",
                                "result": goal_result(checkpoint["objective"]),
                            },
                        )
                        checkpoint = workflow.prepare_host_goal_activation()
                    state = workflow.status()
                    state = append_transition(
                        state,
                        "executed_browser_evidence_recorded",
                        feature_slug=state["feature_slug"],
                        runtime_version=PLUGIN_VERSION,
                        metadata={"fixture": lifecycle_status},
                    )
                    write_state(project_root, state)

                    recovered = workflow.recover_stale_host_goal_checkpoint(
                        checkpoint["checkpoint_id"]
                    )

                    self.assertEqual(
                        workflow.status()["host_goal_binding"]["status"],
                        "activation_pending",
                    )
                    self.assertEqual(
                        recovered["operation"], "inspect_before_activation"
                    )

    def test_recovery_rejects_unknown_checkpoint_and_active_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, checkpoint, _ = stale_activation_checkpoint(Path(tmp))
            with self.assertRaisesRegex(WorkflowError, "current.*checkpoint"):
                workflow.recover_stale_host_goal_checkpoint("wrong-checkpoint")

        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            initial = workflow.prepare_host_goal_activation()
            activate_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "already been active"):
                workflow.recover_stale_host_goal_checkpoint(
                    initial["checkpoint_id"]
                )

    def test_new_checkpoint_projection_uses_real_journal_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            state = workflow.status()
            event_count = len(state["transition_journal"]["events"])
            self.assertNotEqual(event_count, len(state["transition_journal"]))

            checkpoint = workflow.prepare_host_goal_activation()
            pending = workflow.status()["host_goal_binding"]["pending_checkpoint"]

            self.assertEqual(pending["checkpoint_id"], checkpoint["checkpoint_id"])
            self.assertEqual(pending["transition_sequence"], event_count)
            self.assertEqual(
                pending["transition_last_event_hash"],
                state["transition_journal"]["last_event_hash"],
            )


if __name__ == "__main__":
    unittest.main()
