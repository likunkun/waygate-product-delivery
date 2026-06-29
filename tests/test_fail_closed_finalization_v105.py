import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.finalization import run_finalize_cli
from product_delivery_agent.gatekeeper import GatekeeperError, validate_state_invariants
from product_delivery_agent.hooks import (
    build_prompt_context,
    build_resume_context,
    check_pre_compaction,
    check_stop_guardrail,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


def write_raw_state(project_root, state):
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def poisoned_v26_state():
    return {
        "active": True,
        "feature_slug": "v2.6-gateway-concurrency-provider-priority-ui",
        "project_type": "web_system",
        "status": "closed_local_product_delivery",
        "blocking_gates": {"closure": True},
        "implementation": {"current_task": "COMPLETE"},
        "delivery_goal": None,
        "executed_browser_evidence": None,
        "closure_validation": None,
        "feature_closure": None,
        "handoff": {"required_commands": ["pytest"]},
    }


class FailClosedFinalizationV105Tests(unittest.TestCase):
    def test_load_state_fail_closes_v26_poisoned_terminal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(project_root, poisoned_v26_state())

            state = load_state(project_root)

            self.assertEqual(state["status"], "closure_failed")
            self.assertEqual(state["stage"], "closure_failed")
            self.assertEqual(state["next_gate"], "feature_closure_after_implementation")
            self.assertEqual(state["blocking_gates"]["closure"], False)
            self.assertEqual(state["closure_validation"]["status"], "closure_failed")
            errors = " ".join(state["closure_validation"]["errors"])
            self.assertIn("delivery_goal.status=complete", errors)
            self.assertEqual(state["project_type"], "ui")
            self.assertEqual(state["project_subtype"], "web_system")

    def test_invariants_reject_closure_like_state_without_required_terminal_evidence(self):
        with self.assertRaises(GatekeeperError) as caught:
            validate_state_invariants(poisoned_v26_state())

        self.assertIn("closure-like state requires", str(caught.exception))

    def test_workflow_status_and_hooks_report_poisoned_state_as_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(project_root, poisoned_v26_state())

            state = ProductDeliveryWorkflow(project_root).status()
            self.assertEqual(state["status"], "closure_failed")

            for result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_pre_compaction(project_root),
                check_stop_guardrail(project_root),
            ):
                self.assertTrue(result.active)
                self.assertFalse(result.passed)
                self.assertIn("closure_validation.status=passed", " ".join(result.missing_items))

    def test_goal_stop_guard_blocks_missing_goal_after_handoff_or_terminal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(project_root, poisoned_v26_state())
            workflow = ProductDeliveryWorkflow(project_root)

            with self.assertRaises(WorkflowError) as caught:
                workflow.assert_goal_can_stop()

            self.assertIn("active delivery goal is required", str(caught.exception))

    def test_pre_handoff_state_may_have_no_delivery_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(feature_slug="v1.0.5-pre-handoff")

            state = workflow.status()

            self.assertIsNone(state["delivery_goal"])
            self.assertNotEqual(state.get("status"), "closure_failed")

    def test_finalization_cli_fails_nonzero_for_pass_with_notes_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(project_root, poisoned_v26_state())
            artifact_path = project_root / "formal-closure.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        "status": "PASS_WITH_NOTES",
                        "passed": True,
                        "required_commands": [{"command": "pytest"}],
                    }
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = run_finalize_cli(
                    [
                        "--project-root",
                        str(project_root),
                        "--closure-artifact",
                        str(artifact_path),
                    ]
                )

            self.assertEqual(exit_code, 1)
            result_path = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "closure-validator-result.md"
            )
            self.assertTrue(result_path.is_file())
            self.assertIn("closure_failed", result_path.read_text("utf-8"))
            self.assertEqual(load_state(project_root)["status"], "closure_failed")


if __name__ == "__main__":
    unittest.main()
