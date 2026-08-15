import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    load_state,
    write_state,
)
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
)
from product_delivery_agent.transition_journal import append_transition
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import record_passing_task_prototype_conformance
from tests.test_codex_goal_handoff import authorize_launch, ready_workflow
from tests.test_launch_package_supersession_v1018 import task_completion_artifact


def handed_off_workflow(project_root: Path) -> ProductDeliveryWorkflow:
    workflow = ready_workflow(project_root)
    authorize_launch(workflow)
    workflow.generate_codex_goal_handoff(
        scope="Implement classroom dashboard",
        verification_commands=["pytest"],
    )
    return workflow


def goal_result(
    objective: str,
    status: str = "active",
    *,
    thread_id: str | None = None,
) -> dict:
    resolved_thread_id = thread_id or os.environ.get(
        "CODEX_THREAD_ID", "thread-v1024"
    )
    return {
        "goal": {
            "threadId": resolved_thread_id,
            "objective": objective,
            "status": status,
        }
    }


def activate_host_goal(workflow: ProductDeliveryWorkflow) -> dict:
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
    objective = creation["objective"]
    workflow.record_host_goal_observation(
        creation["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "create_goal",
            "result": goal_result(objective),
        },
    )
    verification = workflow.prepare_host_goal_activation()
    return workflow.record_host_goal_observation(
        verification["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": goal_result(objective),
        },
    )


@patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-v1024"})
class HostGoalContinuationV1024Tests(unittest.TestCase):
    def test_test_coverage_confirmation_authorizes_host_goal_until_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ready_workflow(Path(tmp)).status()

            authorization = state["host_goal_authorization"]
            self.assertEqual(authorization["status"], "authorized")
            self.assertEqual(authorization["scope"], "current_delivery")
            self.assertTrue(authorization["pause_for_human_decisions"])
            self.assertTrue(authorization["stop_on_user_request"])
            self.assertEqual(
                authorization["confirmation_hash"],
                state["user_confirmations"]["test_coverage_plan"]["artifact_hash"],
            )

    def test_handoff_prepares_distinct_host_goal_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            state = workflow.status()

            self.assertEqual(
                state["delivery_goal"]["goal_kind"], "internal_delivery_plan"
            )
            binding = state["host_goal_binding"]
            self.assertEqual(binding["status"], "activation_pending")
            self.assertEqual(binding["delivery_id"], state["delivery_id"])
            self.assertEqual(binding["feature_slug"], state["feature_slug"])
            self.assertEqual(
                binding["launch_package_hash"],
                state["delivery_goal"]["launch_package_hash"],
            )
            self.assertIn(state["delivery_id"], binding["objective"])
            self.assertIn("canonical closure", binding["objective"])
            self.assertIn("explicit user stop", binding["objective"])
            self.assertEqual(state["next_gate"], "host_goal_activation")

    def test_initial_activation_requires_get_create_get_handshake(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))

            first = workflow.prepare_host_goal_activation()
            self.assertEqual(first["required_tool"], "get_goal")
            self.assertEqual(first["operation"], "inspect_before_activation")
            after_missing = workflow.record_host_goal_observation(
                first["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": {"goal": None},
                },
            )
            self.assertEqual(
                after_missing["host_goal_binding"]["status"], "creation_ready"
            )

            second = workflow.prepare_host_goal_activation()
            self.assertEqual(second["required_tool"], "create_goal")
            objective = second["objective"]
            after_create = workflow.record_host_goal_observation(
                second["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "create_goal",
                    "result": goal_result(objective),
                },
            )
            self.assertEqual(
                after_create["host_goal_binding"]["status"], "verification_pending"
            )

            third = workflow.prepare_host_goal_activation()
            self.assertEqual(third["required_tool"], "get_goal")
            self.assertEqual(third["operation"], "verify_activation")
            active = workflow.record_host_goal_observation(
                third["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )

            self.assertEqual(active["host_goal_binding"]["status"], "active")
            self.assertEqual(
                active["host_goal_binding"]["last_observed_status"], "active"
            )
            self.assertEqual(active["next_gate"], "TASK-001")

    def test_goal_checkpoint_is_single_use_and_rejects_wrong_objective(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            checkpoint = workflow.prepare_host_goal_activation()

            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": {"goal": None},
                },
            )
            with self.assertRaisesRegex(WorkflowError, "checkpoint.*consumed"):
                workflow.record_host_goal_observation(
                    checkpoint["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": {"goal": None},
                    },
                )

            creation = workflow.prepare_host_goal_activation()
            with self.assertRaisesRegex(WorkflowError, "objective"):
                workflow.record_host_goal_observation(
                    creation["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "create_goal",
                        "result": goal_result("Complete a different delivery"),
                    },
                )

    def test_host_goal_identifier_must_remain_stable_after_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
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
            workflow.record_host_goal_observation(
                creation["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "create_goal",
                    "result": goal_result(creation["objective"]),
                },
            )
            verification = workflow.prepare_host_goal_activation()

            with self.assertRaisesRegex(WorkflowError, "threadId"):
                workflow.record_host_goal_observation(
                    verification["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(
                            creation["objective"], thread_id="thread-foreign"
                        ),
                    },
                )

    def test_host_goal_activation_requires_a_stable_host_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
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

            with self.assertRaisesRegex(WorkflowError, "identifier"):
                workflow.record_host_goal_observation(
                    creation["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "create_goal",
                        "result": {
                            "goal": {
                                "objective": creation["objective"],
                                "status": "active",
                            }
                        },
                    },
                )

    def test_goal_tool_unavailable_is_recorded_and_blocks_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            checkpoint = workflow.prepare_host_goal_activation()

            unavailable = workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "availability_status": "unavailable",
                    "error_type": "tool_not_exposed",
                    "error_message": "Goal tools are not available in this host",
                },
            )

            self.assertEqual(
                unavailable["host_goal_binding"]["status"], "unavailable"
            )
            self.assertEqual(
                unavailable["next_gate"], "use_goal_capable_codex_host"
            )
            continuation = derive_continuation_status(unavailable)
            self.assertEqual(continuation["status"], "blocked")
            self.assertIn(
                "autonomous_continuation_unavailable", continuation["blockers"]
            )
            with self.assertRaisesRegex(WorkflowError, "unavailable"):
                workflow.prepare_host_goal_activation()

            recovered = workflow.authorize_host_goal_reactivation(
                "恢复交付并授权 Goal 重新激活"
            )
            self.assertEqual(
                recovered["host_goal_binding"]["status"], "activation_pending"
            )
            self.assertEqual(
                recovered["host_goal_binding_history"][-1]["binding"]["status"],
                "unavailable",
            )

    def test_post_handoff_progress_requires_fresh_goal_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)

            with self.assertRaisesRegex(WorkflowError, "Host Goal"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(
                        workflow.status(), "TASK-001"
                    ),
                )

            active = activate_host_goal(workflow)
            record_passing_task_prototype_conformance(
                workflow, project_root, "TASK-001"
            )
            checkpoint = workflow.prepare_host_goal_reconciliation(
                "stage_transition",
                target_gate=active["next_gate"],
            )
            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(
                        active["host_goal_binding"]["objective"]
                    ),
                },
            )

            result = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            self.assertEqual(result["delivery_goal"]["completed_tasks"], ["TASK-001"])

    def test_all_post_handoff_canonical_writes_require_reconciliation(self):
        operations = {
            "select_project_type": lambda workflow: workflow.select_project_type(
                "ui"
            ),
            "legacy_confirm": lambda workflow: workflow.confirm(
                "ui_prototype_review"
            ),
            "record_skill_use": lambda workflow: workflow.record_skill_use(
                "product_design",
                ["product-delivery-agent"],
            ),
            "prepare_audit_and_handoff_drafts": lambda workflow: (
                workflow.prepare_audit_and_handoff_drafts()
            ),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                with tempfile.TemporaryDirectory() as tmp:
                    workflow = handed_off_workflow(Path(tmp))
                    activate_host_goal(workflow)

                    with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                        operation(workflow)

    def test_replaying_current_handoff_requires_reconciliation_and_keeps_goal_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.generate_codex_goal_handoff(
                    scope="Implement classroom dashboard",
                    verification_commands=["pytest"],
                )

            checkpoint = workflow.prepare_host_goal_reconciliation(
                "stage_transition",
                target_gate=active["next_gate"],
            )
            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(active["host_goal_binding"]["objective"]),
                },
            )
            replayed = workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )

            self.assertEqual(replayed["host_goal_binding"]["status"], "active")
            self.assertEqual(
                replayed["next_gate"],
                replayed["delivery_goal"]["current_task_cursor"],
            )
            self.assertNotEqual(replayed["next_gate"], "host_goal_activation")

    def test_turn_start_and_unknown_operations_cannot_authorize_stage_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)
            turn = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id="goal-turn-stage-1",
            )
            workflow.record_host_goal_observation(
                turn["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(active["host_goal_binding"]["objective"]),
                },
            )

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(
                        workflow.status(), "TASK-001"
                    ),
                )
            with self.assertRaisesRegex(WorkflowError, "unsupported"):
                workflow.prepare_host_goal_reconciliation(
                    "arbitrary_operation",
                    target_gate=active["next_gate"],
                )

    def test_post_handoff_user_change_requires_goal_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            activate_host_goal(workflow)

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.record_user_requested_change(
                    targets=["test_coverage_plan"],
                    user_message="调整测试覆盖范围",
                )

            checkpoint = workflow.prepare_host_goal_reconciliation(
                "stage_transition",
                target_gate=workflow.status()["next_gate"],
            )
            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(
                        workflow.status()["host_goal_binding"]["objective"]
                    ),
                },
            )
            changed = workflow.record_user_requested_change(
                targets=["test_coverage_plan"],
                user_message="调整测试覆盖范围",
            )
            self.assertEqual(
                changed["user_change_requests"][-1]["status"], "authorized"
            )

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.record_post_freeze_change(
                    change_type="test_gap",
                    description="补充角色拒绝场景",
                    cr_id="CR-HOST-GOAL-001",
                )

    def test_v1023_active_handoff_requires_fresh_waygate_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            current = workflow.status()
            legacy = copy.deepcopy(current)
            legacy.pop("host_goal_binding", None)
            legacy.pop("host_goal_authorization", None)
            legacy.pop("host_goal_owner", None)
            legacy["runtime_version"] = "1.0.23"
            legacy["plugin_version"] = "1.0.23"
            legacy["next_gate"] = "TASK-001"
            legacy_marker = {"screenshots": ["artifacts/ui.png"]}
            legacy["classroom_evidence_marker"] = legacy_marker
            workspace = project_root / ARTIFACT_ROOT
            (workspace / "state.json").write_text(
                json.dumps(legacy, indent=2, sort_keys=True), encoding="utf-8"
            )

            migrated = load_state(project_root)

            self.assertEqual(
                migrated["host_goal_binding"]["status"], "legacy_unverified"
            )
            self.assertEqual(migrated["delivery_id"], current["delivery_id"])
            self.assertEqual(migrated["delivery_goal"], current["delivery_goal"])
            self.assertEqual(
                migrated["classroom_evidence_marker"], legacy_marker
            )
            self.assertEqual(
                migrated["next_gate"], "host_goal_owner_recovery"
            )

            legacy_workflow = ProductDeliveryWorkflow(project_root)
            self.assertEqual(
                legacy_workflow.status()["runtime_status"], "legacy_unverified"
            )
            with self.assertRaisesRegex(WorkflowError, "recover_legacy_active_delivery"):
                legacy_workflow.prepare_host_goal_owner_claim(
                    "恢复交付主线程，接管当前 Host Goal"
                )
            recovered = legacy_workflow.recover_legacy_active_delivery()
            self.assertNotEqual(recovered["delivery_id"], current["delivery_id"])
            snapshot = project_root / recovered["previous_delivery"]["state_snapshot_path"]
            self.assertEqual(
                json.loads(snapshot.read_text(encoding="utf-8"))["classroom_evidence_marker"],
                legacy_marker,
            )

    def test_missing_or_prematurely_complete_goal_requires_new_authorization(self):
        for observed_status, observed_result in (
            ("missing", {"goal": None}),
            ("complete", None),
        ):
            with self.subTest(observed_status=observed_status):
                with tempfile.TemporaryDirectory() as tmp:
                    workflow = handed_off_workflow(Path(tmp))
                    active = activate_host_goal(workflow)
                    objective = active["host_goal_binding"]["objective"]
                    checkpoint = workflow.prepare_host_goal_reconciliation(
                        "stage_transition",
                        target_gate=active["next_gate"],
                    )
                    result = observed_result or goal_result(
                        objective, status="complete"
                    )

                    stale = workflow.record_host_goal_observation(
                        checkpoint["checkpoint_id"],
                        {
                            "observation_source": "codex_goal_tool",
                            "tool": "get_goal",
                            "result": result,
                        },
                    )

                    self.assertEqual(
                        stale["host_goal_binding"]["status"],
                        "reactivation_required",
                    )
                    self.assertEqual(
                        stale["next_gate"], "host_goal_reactivation_authorization"
                    )
                    with self.assertRaisesRegex(
                        WorkflowError, "recovery authorization"
                    ):
                        workflow.prepare_host_goal_activation()

                    recovered = workflow.authorize_host_goal_reactivation(
                        "恢复交付并授权 Goal 重新激活"
                    )
                    self.assertEqual(
                        recovered["host_goal_binding"]["status"],
                        "activation_pending",
                    )
                    self.assertNotEqual(
                        recovered["host_goal_binding"]["binding_nonce"],
                        active["host_goal_binding"]["binding_nonce"],
                    )

    def test_explicit_user_stop_requires_fresh_goal_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)

            with self.assertRaisesRegex(WorkflowError, "explicit user stop"):
                workflow.stop()

            checkpoint = workflow.prepare_host_goal_reconciliation(
                "stop_delivery",
                target_gate=active["next_gate"],
            )
            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(active["host_goal_binding"]["objective"]),
                },
            )

            stopped = workflow.stop(user_message="停止交付")

            self.assertFalse(stopped["active"])
            self.assertEqual(stopped["status"], "stopped")
            self.assertEqual(
                stopped["host_goal_binding"]["status"], "stopped_by_user"
            )
            self.assertEqual(stopped["next_gate"], "stopped")
            with self.assertRaisesRegex(WorkflowError, "not active"):
                ProductDeliveryWorkflow(Path(tmp)).recover_host_goal_binding(
                    "继续交付并启用 Goal 自动推进"
                )

    def test_explicit_user_stop_can_terminate_an_unavailable_goal_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            checkpoint = workflow.prepare_host_goal_activation()
            workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "availability_status": "unavailable",
                    "error_type": "tool_not_exposed",
                    "error_message": "Goal tools are unavailable",
                },
            )

            stopped = workflow.stop(user_message="停止交付")

            self.assertFalse(stopped["active"])
            self.assertEqual(stopped["status"], "stopped")
            self.assertEqual(
                stopped["host_goal_binding"]["status"], "stopped_by_user"
            )
            self.assertEqual(
                stopped["host_goal_binding"]["stop_reconciliation_status"],
                "binding_unavailable",
            )

    def test_internal_closure_waits_for_verified_host_goal_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            active = activate_host_goal(workflow)
            objective = active["host_goal_binding"]["objective"]
            state = workflow.status()
            state["delivery_goal"]["status"] = "complete"
            state["delivery_goal"]["completed_tasks"] = ["TASK-001"]
            state["delivery_goal"]["current_task_cursor"] = None
            state["delivery_goal"]["next_action"] = "goal_complete"
            state["project_type"] = "non_ui"
            state["implementation"] = {
                "current_task": "COMPLETE",
                "completed_tasks": ["TASK-001"],
            }
            closure_hash = "c" * 64
            state["feature_closure"] = {
                "status": "passed",
                "source_artifact_path": "inline:test-host-goal-completion",
                "source_artifact_sha256": closure_hash,
            }
            state["closure_validation"] = {
                "status": "passed",
                "errors": [],
                "validator": CANONICAL_VALIDATOR,
                "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
                "plugin_version": PLUGIN_VERSION,
                "feature_slug": state["feature_slug"],
                "closure_artifact_sha256": closure_hash,
                "result_artifact": (
                    ".product-delivery/artifacts/closure-validator-result.md"
                ),
            }
            state = append_transition(
                state,
                "task_completed",
                feature_slug=state["feature_slug"],
                runtime_version=PLUGIN_VERSION,
                input_artifact_hashes={"planned_task": "a" * 64},
                output_artifact_hashes={"task": "b" * 64},
                metadata={"task_id": "TASK-001"},
            )
            state = append_transition(
                state,
                "closure_validated",
                feature_slug=state["feature_slug"],
                runtime_version=PLUGIN_VERSION,
                input_artifact_hashes={"closure": closure_hash},
                output_artifact_hashes={"result": closure_hash},
                metadata={"validator": CANONICAL_VALIDATOR},
            )
            state = append_transition(
                state,
                "goal_completed",
                feature_slug=state["feature_slug"],
                runtime_version=PLUGIN_VERSION,
                input_artifact_hashes={"closure": closure_hash},
                output_artifact_hashes={},
                metadata={"delivery_goal_status": "complete"},
            )
            state["status"] = "closure_passed_host_goal_completion_pending"
            state["stage"] = "feature_closure_passed"
            state["next_gate"] = "complete_host_goal"
            write_state(project_root, state)

            continuation = derive_continuation_status(workflow.status())
            self.assertEqual(continuation["status"], "must_continue")
            self.assertEqual(continuation["next_action"], "complete_host_goal")

            pre_complete = workflow.prepare_host_goal_reconciliation(
                "pre_complete", target_gate="complete_host_goal"
            )
            workflow.record_host_goal_observation(
                pre_complete["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )
            completion = workflow.prepare_host_goal_reconciliation(
                "complete_goal", target_gate="complete_host_goal"
            )
            after_update = workflow.record_host_goal_observation(
                completion["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "update_goal",
                    "result": goal_result(objective, status="complete"),
                },
            )
            self.assertEqual(
                after_update["host_goal_binding"]["status"],
                "completion_verification_pending",
            )
            verification = workflow.prepare_host_goal_reconciliation(
                "verify_completion", target_gate="complete_host_goal"
            )
            complete = workflow.record_host_goal_observation(
                verification["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective, status="complete"),
                },
            )

            self.assertEqual(complete["host_goal_binding"]["status"], "complete")
            self.assertEqual(complete["status"], "closed")
            self.assertEqual(
                derive_continuation_status(complete)["status"], "complete"
            )

    def test_host_goal_completion_is_rejected_before_canonical_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = handed_off_workflow(Path(tmp))
            active = activate_host_goal(workflow)

            with self.assertRaisesRegex(WorkflowError, "canonical closure"):
                workflow.prepare_host_goal_reconciliation(
                    "complete_goal", target_gate=active["next_gate"]
                )

    def test_human_wait_prompts_once_and_blocks_only_after_three_goal_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            active = activate_host_goal(workflow)
            record_passing_task_prototype_conformance(
                workflow, project_root, "TASK-001"
            )
            objective = active["host_goal_binding"]["objective"]
            state = workflow.status()
            state["blocked_until"] = ["requirements_clarification"]
            write_state(project_root, state)

            decision_id = None
            for index in range(1, 4):
                request = workflow.prepare_host_goal_reconciliation(
                    "turn_start",
                    target_gate=active["next_gate"],
                    host_turn_id=f"goal-turn-{index}",
                )
                if decision_id is None:
                    decision_id = request["decision_id"]
                self.assertEqual(request["decision_id"], decision_id)
                self.assertEqual(request["continuation_status"], "wait_for_user")
                self.assertEqual(request["should_prompt"], index == 1)
                waited = workflow.record_host_goal_observation(
                    request["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective),
                    },
                )
                self.assertEqual(
                    waited["host_goal_binding"]["human_wait"][
                        "consecutive_goal_turns"
                    ],
                    index,
                )
                self.assertIsNone(
                    waited["host_goal_binding"].get("authorized_transition")
                )

            with self.assertRaisesRegex(WorkflowError, "fresh Host Goal"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(
                        workflow.status(), "TASK-001"
                    ),
                )

            block = workflow.prepare_host_goal_reconciliation(
                "block_goal",
                target_gate=active["next_gate"],
                host_turn_id="goal-turn-3",
            )
            with self.assertRaisesRegex(WorkflowError, "missing"):
                workflow.record_host_goal_observation(
                    block["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "update_goal",
                        "result": {"goal": None},
                    },
                )
            blocked = workflow.record_host_goal_observation(
                block["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "update_goal",
                    "result": goal_result(objective, status="blocked"),
                },
            )
            self.assertEqual(blocked["host_goal_binding"]["status"], "blocked")
            self.assertEqual(blocked["next_gate"], "host_goal_resume_required")
            blocked_continuation = derive_continuation_status(blocked)
            self.assertEqual(blocked_continuation["status"], "wait_for_user")
            self.assertEqual(
                blocked_continuation["next_action"], "host_goal_resume_required"
            )

            resume = workflow.prepare_host_goal_reconciliation(
                "user_resume",
                target_gate=active["next_gate"],
                host_turn_id="goal-turn-4",
                decision_id=decision_id,
                user_message="补充说明：按教师普通入口继续",
            )
            resumed = workflow.record_host_goal_observation(
                resume["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )
            self.assertEqual(resumed["host_goal_binding"]["status"], "active")
            self.assertEqual(
                resumed["host_goal_binding"]["human_wait"]["status"],
                "resolved",
            )
            self.assertEqual(
                resumed["host_goal_binding"]["authorized_transition"][
                    "target_gate"
                ],
                active["next_gate"],
            )
            self.assertNotIn("requirements_clarification", resumed["blocked_until"])

            completed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            self.assertNotEqual(
                derive_continuation_status(completed)["status"],
                "wait_for_user",
            )

    def test_block_goal_rejects_resolved_or_changed_blocker_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            active = activate_host_goal(workflow)
            objective = active["host_goal_binding"]["objective"]
            state = workflow.status()
            state["blocked_until"] = ["requirements_clarification"]
            write_state(project_root, state)

            for index in range(1, 4):
                request = workflow.prepare_host_goal_reconciliation(
                    "turn_start",
                    target_gate=active["next_gate"],
                    host_turn_id=f"stale-block-turn-{index}",
                )
                workflow.record_host_goal_observation(
                    request["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective),
                    },
                )

            state = workflow.status()
            state["blocked_until"] = []
            write_state(project_root, state)

            with self.assertRaisesRegex(WorkflowError, "current blocker"):
                workflow.prepare_host_goal_reconciliation(
                    "block_goal",
                    target_gate=active["next_gate"],
                    host_turn_id="stale-block-turn-3",
                )

    def test_duplicate_host_turn_id_does_not_advance_block_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            active = activate_host_goal(workflow)
            objective = active["host_goal_binding"]["objective"]
            state = workflow.status()
            state["blocked_until"] = ["requirements_clarification"]
            write_state(project_root, state)

            for _ in range(2):
                request = workflow.prepare_host_goal_reconciliation(
                    "turn_start",
                    target_gate=active["next_gate"],
                    host_turn_id="same-goal-turn",
                )
                result = workflow.record_host_goal_observation(
                    request["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective),
                    },
                )

            self.assertEqual(
                result["host_goal_binding"]["human_wait"][
                    "consecutive_goal_turns"
                ],
                1,
            )
            with self.assertRaisesRegex(WorkflowError, "three consecutive"):
                workflow.prepare_host_goal_reconciliation(
                    "block_goal",
                    target_gate=active["next_gate"],
                    host_turn_id="same-goal-turn",
                )

    def test_clear_goal_turn_resets_consecutive_human_blocker_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handed_off_workflow(project_root)
            active = activate_host_goal(workflow)
            objective = active["host_goal_binding"]["objective"]
            state = workflow.status()
            state["blocked_until"] = ["requirements_clarification"]
            write_state(project_root, state)

            for index in range(1, 4):
                request = workflow.prepare_host_goal_reconciliation(
                    "turn_start",
                    target_gate=active["next_gate"],
                    host_turn_id=f"blocked-turn-{index}",
                )
                workflow.record_host_goal_observation(
                    request["checkpoint_id"],
                    {
                        "observation_source": "codex_goal_tool",
                        "tool": "get_goal",
                        "result": goal_result(objective),
                    },
                )

            state = workflow.status()
            state["blocked_until"] = []
            write_state(project_root, state)
            clear_turn = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id="clear-turn",
            )
            workflow.record_host_goal_observation(
                clear_turn["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )

            state = workflow.status()
            state["blocked_until"] = ["requirements_clarification"]
            write_state(project_root, state)
            restored = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id="restored-block-turn-1",
            )
            observed = workflow.record_host_goal_observation(
                restored["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )

            self.assertEqual(
                observed["host_goal_binding"]["human_wait"][
                    "consecutive_goal_turns"
                ],
                1,
            )
            with self.assertRaisesRegex(WorkflowError, "three consecutive"):
                workflow.prepare_host_goal_reconciliation(
                    "block_goal",
                    target_gate=active["next_gate"],
                    host_turn_id="restored-block-turn-1",
                )


if __name__ == "__main__":
    unittest.main()
