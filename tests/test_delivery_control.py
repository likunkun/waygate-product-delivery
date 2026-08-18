"""Tests for parameterized delivery lifecycle control."""

import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.control import (
    ControlError,
    EXIT_CONFIRMATION_MISSING,
    EXIT_GATE_BLOCKED,
    EXIT_IDENTITY_CONFLICT,
    EXIT_OK,
    EXIT_PARAM_ERROR,
    dispatch,
    run_control_cli,
    validate_request,
)
from product_delivery_agent.gatekeeper import stable_state_hash
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError

from tests.test_feature_closure import ready_workflow, valid_closure_artifact


class RequestValidationTests(unittest.TestCase):
    def test_valid_start_request_passes(self):
        req = validate_request({
            "schema_version": "v1",
            "action": "start",
            "feature_slug": "v0-5-5",
            "start_mode": "resume_or_create",
            "review_mode_if_created": "spawned_subagents_authorized",
        })
        self.assertEqual(req["action"], "start")
        self.assertEqual(req["feature_slug"], "v0-5-5")

    def test_unknown_field_rejected(self):
        with self.assertRaises(ControlError):
            validate_request({
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "f",
                "bogus_field": "x",
            })

    def test_missing_feature_slug_for_start_rejected(self):
        with self.assertRaises(ControlError):
            validate_request({"schema_version": "v1", "action": "start"})

    def test_invalid_action_rejected(self):
        with self.assertRaises(ControlError):
            validate_request({"schema_version": "v1", "action": "destroy"})

    def test_wrong_schema_version_rejected(self):
        with self.assertRaises(ControlError):
            validate_request({"schema_version": "v2", "action": "inspect"})

    def test_natural_language_text_is_not_json(self):
        """Plain text input should fail at JSON parse, not dispatch."""
        # run_control_cli reads from stdin; we test that non-JSON fails
        import sys, io
        old_stdin = sys.stdin
        old_argv = sys.argv
        sys.stdin = io.StringIO("启动交付")
        sys.argv = ["waygate-control.py", "/tmp"]
        try:
            rc = run_control_cli()
            self.assertEqual(rc, EXIT_PARAM_ERROR)
        finally:
            sys.stdin = old_stdin
            sys.argv = old_argv

    def test_abandon_requires_confirmation_token(self):
        with self.assertRaises(ControlError) as cm:
            validate_request({
                "schema_version": "v1",
                "action": "abandon",
                "delivery_id": "x",
            })
        self.assertEqual(cm.exception.exit_code, EXIT_CONFIRMATION_MISSING)

    def test_resume_only_requires_delivery_id(self):
        with self.assertRaises(ControlError):
            validate_request({
                "schema_version": "v1",
                "action": "resume",
            })


class ControlDispatchTests(unittest.TestCase):
    def test_inspect_on_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "inspect",
            })
            self.assertEqual(result["action"], "inspect")
            self.assertEqual(result["result"], "reported")
            self.assertFalse((Path(tmp) / ".product-delivery").exists())

    def test_status_on_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "status",
            })
            self.assertEqual(result["action"], "status")
            self.assertFalse((Path(tmp) / ".product-delivery").exists())

    def test_start_creates_new_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            self.assertEqual(result["result"], "created")
            self.assertTrue(result["created_new_delivery"])
            self.assertEqual(result["feature_slug"], "v0-5-5")
            current = Path(tmp) / ".product-delivery" / "current.json"
            self.assertTrue(current.is_file())
            delivery_state = Path(tmp) / result["current_root"] / "state.json"
            self.assertTrue(delivery_state.is_file())

    def test_start_resume_or_create_resumes_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            # First start
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            # Second start should resume
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "resume_or_create",
            })
            self.assertEqual(result["result"], "resumed")
            self.assertFalse(result["created_new_delivery"])

    def test_resume_only_fails_without_existing_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ControlError) as cm:
                dispatch(tmp, {
                    "schema_version": "v1",
                    "action": "start",
                    "feature_slug": "v0-5-5",
                    "start_mode": "resume_only",
                })
            self.assertEqual(cm.exception.exit_code, EXIT_IDENTITY_CONFLICT)

    def test_create_only_fails_with_existing_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            with self.assertRaises(ControlError) as cm:
                dispatch(tmp, {
                    "schema_version": "v1",
                    "action": "start",
                    "feature_slug": "v0-5-5",
                    "start_mode": "create_only",
                    "review_mode_if_created": "spawned_subagents_authorized",
                })
            self.assertEqual(cm.exception.exit_code, EXIT_IDENTITY_CONFLICT)

    def test_different_active_feature_blocks_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "feature-a",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            with self.assertRaises(ControlError) as cm:
                dispatch(tmp, {
                    "schema_version": "v1",
                    "action": "start",
                    "feature_slug": "feature-b",
                    "start_mode": "create_only",
                    "review_mode_if_created": "spawned_subagents_authorized",
                })
            self.assertEqual(cm.exception.exit_code, EXIT_IDENTITY_CONFLICT)

    def test_dry_run_does_not_write_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            # Dry run pause should not modify state
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "pause",
                "dry_run": True,
            })
            self.assertEqual(result["result"], "dry_run")
            state = ProductDeliveryWorkflow(tmp).status()
            # Should still be active (not paused)
            self.assertTrue(state.get("active"))
            self.assertFalse(state.get("paused"))

    def test_pause_and_resume_preserve_delivery_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            original_id = created["delivery_id"]

            paused = dispatch(tmp, {"schema_version": "v1", "action": "pause"})
            self.assertEqual(paused["delivery_id"], original_id)

            resumed = dispatch(tmp, {
                "schema_version": "v1",
                "action": "resume",
                "delivery_id": original_id,
            })
            self.assertEqual(resumed["delivery_id"], original_id)
            self.assertEqual(resumed["result"], "resumed")

    def test_start_after_pause_resumes_same_delivery_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            dispatch(tmp, {"schema_version": "v1", "action": "pause"})
            resumed = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "resume_or_create",
            })
            self.assertEqual(resumed["delivery_id"], created["delivery_id"])
            self.assertEqual(resumed["result"], "resumed")
            self.assertFalse(ProductDeliveryWorkflow(tmp).status()["paused"])

    def test_abandon_requires_two_phase_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            # Direct abandon without token fails
            with self.assertRaises(ControlError):
                dispatch(tmp, {
                    "schema_version": "v1",
                    "action": "abandon",
                    "delivery_id": "x",
                    "confirmation_token": "invalid",
                })

    def test_abandon_with_valid_token_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            delivery_id = created["delivery_id"]

            # Prepare abandon
            prep = dispatch(tmp, {
                "schema_version": "v1",
                "action": "prepare_abandon",
                "delivery_id": delivery_id,
                "reason": "test abandon",
            })
            token = prep["confirmation_token"]

            # Abandon
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "abandon",
                "delivery_id": delivery_id,
                "confirmation_token": token,
            })
            self.assertEqual(result["result"], "abandoned")

    def test_abandon_token_is_invalidated_by_state_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            prepared = dispatch(tmp, {
                "schema_version": "v1",
                "action": "prepare_abandon",
                "delivery_id": created["delivery_id"],
                "reason": "state-bound token test",
            })
            ProductDeliveryWorkflow(tmp).select_project_type("non_ui")
            with self.assertRaises(ControlError) as caught:
                dispatch(tmp, {
                    "schema_version": "v1",
                    "action": "abandon",
                    "delivery_id": created["delivery_id"],
                    "confirmation_token": prepared["confirmation_token"],
                })
            self.assertEqual(caught.exception.exit_code, EXIT_CONFIRMATION_MISSING)

    def test_close_succeeds_after_canonical_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            closed_ready = workflow.record_feature_closure(
                valid_closure_artifact(workflow.status())
            )
            result = dispatch(root, {
                "schema_version": "v1",
                "action": "close",
                "delivery_id": closed_ready["delivery_id"],
            })
            self.assertEqual(result["result"], "closed")
            state = ProductDeliveryWorkflow(root).status()
            self.assertFalse(state["active"])
            self.assertEqual(state["delivery_lifecycle"]["status"], "closed")

    def test_close_fails_without_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            with self.assertRaises(ControlError) as cm:
                dispatch(tmp, {"schema_version": "v1", "action": "close"})
            self.assertEqual(cm.exception.exit_code, EXIT_GATE_BLOCKED)

    def test_abandoned_delivery_allows_new_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            delivery_id = created["delivery_id"]

            prep = dispatch(tmp, {
                "schema_version": "v1",
                "action": "prepare_abandon",
                "delivery_id": delivery_id,
                "reason": "starting over",
            })
            dispatch(tmp, {
                "schema_version": "v1",
                "action": "abandon",
                "delivery_id": delivery_id,
                "confirmation_token": prep["confirmation_token"],
            })

            # New delivery should be created
            result = dispatch(tmp, {
                "schema_version": "v1",
                "action": "start",
                "feature_slug": "v0-5-5",
                "start_mode": "create_only",
                "review_mode_if_created": "spawned_subagents_authorized",
            })
            self.assertEqual(result["result"], "created")
            self.assertNotEqual(result["delivery_id"], delivery_id)


if __name__ == "__main__":
    unittest.main()
