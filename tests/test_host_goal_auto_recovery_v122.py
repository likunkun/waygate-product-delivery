import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.host_goal import (
    HostGoalError, apply_host_goal_observation, auto_recreate_host_goal_binding,
)
from product_delivery_agent.hooks import check_stop_guardrail
from product_delivery_agent.control import dispatch
from product_delivery_agent.transition_journal import journal_integrity_errors
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_host_goal_continuation_v1024 import (
    handed_off_workflow, activate_host_goal, goal_result,
)


def observation(result=None, error=None):
    value = {"observation_source": "codex_goal_tool", "tool": "get_goal"}
    if error:
        value.update(availability_status="unavailable", error_type=error,
                     error_message="gateway disconnected")
    else:
        value["result"] = result
    return value


class HostGoalAutoRecoveryV122Tests(unittest.TestCase):
    def setUp(self):
        env_patch = patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-v122"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workflow = handed_off_workflow(self.root)
        self.active = activate_host_goal(self.workflow)
        self.objective = self.active["host_goal_binding"]["objective"]
        self.clock = patch("time.time", return_value=1000.0).start()
        self.addCleanup(patch.stopall)

    def interrupt(self, value=None):
        checkpoint = self.workflow.prepare_host_goal_reconciliation(
            "stage_transition", target_gate=self.active["next_gate"])
        value = value or observation(error="connection_error")
        return checkpoint, value, self.workflow.record_host_goal_observation(
            checkpoint["checkpoint_id"], value)

    def due(self):
        state = load_state(self.root)
        self.clock.return_value = state["host_goal_binding"]["auto_recovery"]["retry_at_epoch"]
        return self.workflow.prepare_host_goal_auto_recovery()

    def test_wait_and_duplicate_callback_are_byte_stable(self):
        checkpoint, value, recovered = self.interrupt()
        path = self.root / ".product-delivery/state.json"
        before = path.read_bytes()
        self.assertEqual(recovered["recovery_action"], "recreate_host_goal")
        self.assertEqual(recovered["recovery_attempt"], 1)
        for _ in range(2):
            response = self.workflow.prepare_host_goal_auto_recovery()
            self.assertEqual(response["operation"], "wait_for_retry")
            self.workflow.record_host_goal_observation(checkpoint["checkpoint_id"], value)
            self.assertEqual(path.read_bytes(), before)
        self.assertFalse(journal_integrity_errors(load_state(self.root)))
        with self.assertRaisesRegex(WorkflowError, "replay"):
            self.workflow.record_host_goal_observation(
                checkpoint["checkpoint_id"], observation(error="timeout"))
        self.assertEqual(path.read_bytes(), before)

    def test_concurrent_same_callback_allocates_one_attempt(self):
        checkpoint = self.workflow.prepare_host_goal_reconciliation(
            "stage_transition", target_gate=self.active["next_gate"])
        value = observation(error="connection_error")
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: ProductDeliveryWorkflow(self.root)
                .record_host_goal_observation(checkpoint["checkpoint_id"], value), range(2)))
        self.assertEqual([r["recovery_attempt"] for r in results], [1, 1])
        state = load_state(self.root)
        self.assertEqual(len(state["host_goal_binding_history"]), 1)
        self.assertEqual(sum(e["transition_name"] == "host_goal_auto_recreated"
                             for e in state["transition_journal"]["events"]), 1)

    def test_existing_active_goal_is_reattached_after_gateway_error(self):
        self.interrupt()
        checkpoint = self.due()
        state = self.workflow.record_host_goal_auto_recovery(
            checkpoint["checkpoint_id"], observation(goal_result(self.objective)),
            attempt_id=checkpoint["recovery_attempt_id"])
        self.assertEqual(state["host_goal_binding"]["status"], "active")
        self.assertEqual(state["host_goal_binding"]["objective"], self.objective)
        self.assertEqual(state["next_gate"], self.active["next_gate"])
        self.assertEqual(state["host_goal_binding"]["auto_recovery"]["status"], "resolved")

    def test_complete_old_goal_allows_new_get_create_get(self):
        self.interrupt(observation(goal_result(self.objective, "complete")))
        checkpoint = self.due()
        self.workflow.record_host_goal_auto_recovery(
            checkpoint["checkpoint_id"], observation(goal_result(self.objective, "complete")),
            attempt_id=checkpoint["recovery_attempt_id"])
        creation = self.workflow.prepare_host_goal_activation()
        self.assertEqual(creation["required_tool"], "create_goal")
        self.assertNotEqual(creation["objective"], self.objective)
        self.workflow.record_host_goal_observation(creation["checkpoint_id"], {
            "observation_source": "codex_goal_tool", "tool": "create_goal",
            "result": goal_result(creation["objective"])})
        verification = self.workflow.prepare_host_goal_activation()
        state = self.workflow.record_host_goal_observation(verification["checkpoint_id"],
            observation(goal_result(creation["objective"])))
        self.assertEqual(state["host_goal_binding"]["status"], "active")

    def test_unexpected_blocked_with_transport_reason_retries_existing_goal(self):
        value = observation(goal_result(self.objective, "blocked"))
        value["error_type"] = "connection_error"
        _, _, state = self.interrupt(value)
        self.assertEqual(state["recovery_action"], "resume_host_goal")
        checkpoint = self.due()
        state = self.workflow.record_host_goal_auto_recovery(
            checkpoint["checkpoint_id"], observation(goal_result(self.objective, "blocked")),
            attempt_id=checkpoint["recovery_attempt_id"])
        self.assertEqual(state["recovery_attempt"], 2)
        self.assertEqual(state["recovery_action"], "resume_host_goal")
        self.assertNotEqual(state["host_goal_binding"]["status"], "creation_ready")

    def test_unknown_blocked_and_explicit_business_wait_stay_manual(self):
        for explicit_wait in (False, True):
            with self.subTest(explicit_wait=explicit_wait):
                write_state(self.root, copy.deepcopy(self.active))
                state = load_state(self.root)
                if explicit_wait:
                    state["blocked_until"] = ["external_dependency"]
                    write_state(self.root, state)
                value = observation(goal_result(self.objective, "blocked"))
                if explicit_wait:
                    value["error_type"] = "connection_error"
                _, _, blocked = self.interrupt(value)
                self.assertEqual(blocked["host_goal_binding"]["status"], "blocked")
                self.assertNotIn("auto_recovery", blocked["host_goal_binding"])

    def test_permanent_tool_absence_does_not_retry(self):
        _, _, state = self.interrupt(observation(error="tool_not_exposed"))
        self.assertEqual(state["host_goal_binding"]["status"], "unavailable")
        self.assertNotIn("auto_recovery", state["host_goal_binding"])

    def test_three_delayed_attempts_exhaust_without_fourth_attempt(self):
        self.interrupt()
        for attempt, delay in ((1, 5), (2, 15), (3, 30)):
            recovery = load_state(self.root)["host_goal_binding"]["auto_recovery"]
            self.assertEqual((recovery["attempt"], recovery["retry_after_seconds"]), (attempt, delay))
            checkpoint = self.due()
            state = self.workflow.record_host_goal_auto_recovery(
                checkpoint["checkpoint_id"], observation(error="connection_error"),
                attempt_id=checkpoint["recovery_attempt_id"])
        self.assertEqual(state["host_goal_binding"]["status"], "auto_recovery_exhausted")
        self.assertEqual(state["recovery_attempt"], 3)
        self.assertEqual(state["recovery_action"], "manual_recovery_required")
        self.assertEqual(len(state["host_goal_binding_history"]), 3)

    def test_wrong_attempt_and_foreign_goal_are_rejected_without_mutation(self):
        self.interrupt()
        checkpoint = self.due()
        before = (self.root / ".product-delivery/state.json").read_bytes()
        for attempt_id, result in (("wrong", {"goal": None}),
                                   (checkpoint["recovery_attempt_id"], goal_result("foreign")),
                                   (checkpoint["recovery_attempt_id"], goal_result(self.objective, thread_id="foreign"))):
            with self.subTest(attempt_id=attempt_id, result=result):
                with self.assertRaises(WorkflowError):
                    self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
                        observation(result), attempt_id=attempt_id)
                self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_identity_changes_reject_automatic_recovery(self):
        checkpoint = self.workflow.prepare_host_goal_reconciliation(
            "stage_transition", target_gate=self.active["next_gate"])
        base = load_state(self.root)
        for field, target in (("delivery_id", "state"), ("feature_slug", "state"),
                              ("launch_package_hash", "delivery_goal"),
                              ("owner_thread_id", "host_goal_binding")):
            state = copy.deepcopy(base)
            (state if target == "state" else state[target])[field] = "changed"
            with self.subTest(field=field), self.assertRaises(HostGoalError):
                apply_host_goal_observation(state, checkpoint["checkpoint_id"],
                                           observation(error="connection_error"))

    def test_stopped_paused_and_canonical_closure_never_recreate(self):
        for mode in ("abandoned", "paused", "closed", "canonical_closure"):
            state = copy.deepcopy(self.active)
            if mode == "paused":
                state["paused"] = True
            elif mode == "canonical_closure":
                state["feature_closure"] = {"status": "passed"}
                state["closure_validation"] = {"status": "passed"}
                state["delivery_goal"]["status"] = "complete"
            else:
                state["status"] = mode
                state["active"] = False
            with self.subTest(mode=mode):
                result, response = auto_recreate_host_goal_binding(state, "unavailable")
                self.assertEqual(result, state)
                self.assertEqual(response["recovery_action"], "not_allowed")

    def test_wait_contract_reaches_stop_hook(self):
        self.interrupt()
        result = check_stop_guardrail(self.root)
        self.assertTrue(result.passed)
        self.assertEqual(result.retry_contract["retry_after_seconds"], 5)
        self.assertEqual(result.retry_contract["scheduler_required"], "host")

    def test_resolved_recovery_retains_budget_against_churn(self):
        self.interrupt()
        checkpoint = self.due()
        self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
            observation(goal_result(self.objective)), attempt_id=checkpoint["recovery_attempt_id"])
        _, _, state = self.interrupt()
        self.assertEqual(state["recovery_attempt"], 2)

    def test_interrupted_gate_and_task_evidence_are_preserved(self):
        state = load_state(self.root)
        state["next_gate"] = "multi_agent_test_review"
        write_state(self.root, state)
        _, _, recovering = self.interrupt()
        self.assertEqual(recovering["host_goal_binding"]["resume_gate"], "multi_agent_test_review")
        for key in ("delivery_id", "feature_slug", "delivery_goal", "implementation", "user_confirmations", "host_goal_owner"):
            self.assertEqual(recovering.get(key), state.get(key))
        self.assertNotEqual(recovering["host_goal_binding"]["objective"], self.objective)
        self.assertEqual(recovering["host_goal_binding"]["generation"], state["host_goal_binding"]["generation"] + 1)

    def test_callback_before_retry_time_is_rejected(self):
        self.interrupt()
        self.clock.return_value = 1005
        checkpoint = self.workflow.prepare_host_goal_auto_recovery()
        self.clock.return_value = 1004
        before = (self.root / ".product-delivery/state.json").read_bytes()
        with self.assertRaisesRegex(WorkflowError, "before retry_at"):
            self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
                observation({"goal": None}), attempt_id=checkpoint["recovery_attempt_id"])
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_canonical_reentry_reuses_same_checkpoint(self):
        self.interrupt()
        checkpoint = self.due()
        before = (self.root / ".product-delivery/state.json").read_bytes()
        response = ProductDeliveryWorkflow(self.root).prepare_host_goal_auto_recovery()
        self.assertEqual(response["checkpoint_id"], checkpoint["checkpoint_id"])
        self.assertEqual(response["recovery_attempt_id"], checkpoint["recovery_attempt_id"])
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_status_exposes_retry_contract(self):
        self.interrupt()
        response = dispatch(self.root, {"schema_version": "v1", "action": "status"})
        self.assertEqual(response["host_goal_recovery"]["recovery_attempt"], 1)
        self.assertEqual(response["host_goal_recovery"]["retry_after_seconds"], 5)

    def test_actual_user_abandon_cancels_pending_retry(self):
        self.interrupt()
        prepared = dispatch(self.root, {"schema_version": "v1", "action": "prepare_abandon",
            "delivery_id": self.active["delivery_id"], "reason": "停止交付"})
        dispatch(self.root, {"schema_version": "v1", "action": "abandon",
            "delivery_id": self.active["delivery_id"], "confirmation_token": prepared["confirmation_token"]})
        self.clock.return_value = 2000
        before = (self.root / ".product-delivery/state.json").read_bytes()
        with self.assertRaisesRegex(WorkflowError, "not active"):
            self.workflow.prepare_host_goal_auto_recovery()
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_paused_retry_is_user_wait_and_cannot_activate(self):
        self.interrupt()
        self.workflow.pause_delivery()
        state = load_state(self.root)
        self.assertEqual(derive_continuation_status(state)["status"], "wait_for_user")
        self.clock.return_value = 2000
        with self.assertRaisesRegex(WorkflowError, "paused"):
            self.workflow.prepare_host_goal_auto_recovery()

    def test_changed_launch_and_tampered_journal_cannot_issue_retry_action(self):
        self.interrupt()
        base = load_state(self.root)
        for mode in ("launch", "journal"):
            state = copy.deepcopy(base)
            if mode == "launch":
                state["delivery_goal"]["launch_package_hash"] = "changed"
            else:
                state["transition_journal"]["events"][-1]["event_hash"] = "0" * 64
            write_state(self.root, state)
            before = (self.root / ".product-delivery/state.json").read_bytes()
            with self.subTest(mode=mode), self.assertRaises(WorkflowError):
                self.workflow.prepare_host_goal_auto_recovery()
            self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_transport_block_during_activation_verification_allocates_next_attempt(self):
        self.interrupt()
        checkpoint = self.due()
        self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
            observation({"goal": None}), attempt_id=checkpoint["recovery_attempt_id"])
        creation = self.workflow.prepare_host_goal_activation()
        self.workflow.record_host_goal_observation(creation["checkpoint_id"], {
            "observation_source": "codex_goal_tool", "tool": "create_goal",
            "result": goal_result(creation["objective"])})
        verification = self.workflow.prepare_host_goal_activation()
        value = observation(goal_result(creation["objective"], "blocked"))
        value["error_type"] = "connection_error"
        recovered = self.workflow.record_host_goal_observation(verification["checkpoint_id"], value)
        self.assertEqual(recovered["recovery_attempt"], 2)
        self.assertEqual(recovered["recovery_action"], "resume_host_goal")

    def test_new_business_block_reason_overrides_inherited_transport_reason(self):
        value = observation(goal_result(self.objective, "blocked"))
        value["error_type"] = "connection_error"
        self.interrupt(value)
        checkpoint = self.due()
        value = observation(goal_result(self.objective, "blocked"))
        value["result"]["goal"]["blockedReason"] = "manual_confirmation"
        recovered = self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"], value,
            attempt_id=checkpoint["recovery_attempt_id"])
        self.assertEqual(recovered["host_goal_binding"]["status"], "blocked")
        self.assertEqual(derive_continuation_status(recovered)["status"], "wait_for_user")

    def test_new_external_block_or_closure_prevents_recovery_action(self):
        self.interrupt()
        base = load_state(self.root)
        for mode in ("external", "closure"):
            state = copy.deepcopy(base)
            if mode == "external":
                state["blocked_until"].append("external_dependency")
            else:
                state["feature_closure"] = {"status": "passed"}
                state["closure_validation"] = {"status": "passed"}
                state["delivery_goal"]["status"] = "complete"
            write_state(self.root, state)
            self.clock.return_value = 2000
            before = (self.root / ".product-delivery/state.json").read_bytes()
            with self.subTest(mode=mode), self.assertRaises(WorkflowError):
                self.workflow.prepare_host_goal_auto_recovery()
            self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_non_transport_tool_error_does_not_allocate_recovery(self):
        _, _, state = self.interrupt(observation(error="invalid_request"))
        self.assertEqual(state["host_goal_binding"]["status"], "unavailable")
        self.assertNotIn("auto_recovery", state["host_goal_binding"])

    def test_archived_goal_tampering_cannot_reattach_a_foreign_goal(self):
        self.interrupt()
        state = load_state(self.root)
        state["host_goal_binding"]["recovery_goal"]["objective"] = "foreign"
        write_state(self.root, state)
        with self.assertRaisesRegex(WorkflowError, "recovery Goal"):
            self.workflow.prepare_host_goal_auto_recovery()

    def test_canonical_external_and_failure_markers_disallow_recovery(self):
        for blocker in ("database_unavailable", "port_conflict", "repeated_failure", "failed_three_times"):
            state = copy.deepcopy(self.active)
            state["blocked_until"] = [blocker]
            with self.subTest(blocker=blocker):
                result, response = auto_recreate_host_goal_binding(state, "unavailable")
                self.assertEqual(response["recovery_action"], "not_allowed")
                self.assertEqual(result, state)

    def test_explicit_authorization_after_exhaustion_reattaches_surviving_goal(self):
        self.interrupt()
        for _ in range(3):
            checkpoint = self.due()
            self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
                observation(error="connection_error"), attempt_id=checkpoint["recovery_attempt_id"])
        authorized = self.workflow.authorize_host_goal_reactivation("恢复 Goal，继续交付")
        self.assertEqual(authorized["host_goal_binding"]["resume_gate"], self.active["next_gate"])
        checkpoint = self.workflow.prepare_host_goal_activation()
        recovered = self.workflow.record_host_goal_observation(checkpoint["checkpoint_id"],
            observation(goal_result(self.objective)))
        self.assertEqual(recovered["host_goal_binding"]["status"], "active")
        self.assertEqual(recovered["host_goal_binding"]["auto_recovery"]["attempt"], 0)
        self.assertEqual(recovered["next_gate"], self.active["next_gate"])

    def test_launch_change_after_resolved_recovery_cannot_authorize_old_goal(self):
        self.interrupt()
        checkpoint = self.due()
        self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
            observation(goal_result(self.objective)), attempt_id=checkpoint["recovery_attempt_id"])
        state = load_state(self.root)
        state["delivery_goal"]["launch_package_hash"] = "changed"
        write_state(self.root, state)
        with self.assertRaisesRegex(WorkflowError, "launch package"):
            self.workflow.prepare_host_goal_reconciliation("stage_transition", target_gate=state["next_gate"])

    def test_manual_authorization_callback_revalidates_archived_goal(self):
        self.interrupt()
        for _ in range(3):
            checkpoint = self.due()
            self.workflow.record_host_goal_auto_recovery(checkpoint["checkpoint_id"],
                observation(error="connection_error"), attempt_id=checkpoint["recovery_attempt_id"])
        self.workflow.authorize_host_goal_reactivation("恢复 Goal，继续交付")
        checkpoint = self.workflow.prepare_host_goal_activation()
        state = load_state(self.root)
        state["host_goal_binding"]["recovery_goal"]["objective"] = "foreign-objective"
        write_state(self.root, state)
        before = (self.root / ".product-delivery/state.json").read_bytes()
        with self.assertRaisesRegex(WorkflowError, "recovery Goal"):
            self.workflow.record_host_goal_observation(checkpoint["checkpoint_id"],
                observation(goal_result("foreign-objective")))
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
