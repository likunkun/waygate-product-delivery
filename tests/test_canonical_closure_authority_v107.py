import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.closure import ClosureGateError
from product_delivery_agent.finalization import run_finalize_cli
from product_delivery_agent.gatekeeper import validate_state_invariants
from product_delivery_agent.hooks import (
    build_prompt_context,
    build_resume_context,
    check_pre_compaction,
    check_stop_guardrail,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow

from tests.test_feature_closure import ready_workflow, valid_closure_artifact


def write_raw_state(project_root, state):
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def target_specific_pass_artifact():
    return {
        "feature_slug": "v2.7-team-member-usage-analytics-export",
        "status": "PASS_WITH_NOTES",
        "passed": True,
        "product_delivery_local_closure": True,
        "latest_test_case": "TC-V27-024",
        "matrix_range": "TC-V27-001..TC-V27-024",
        "required_commands": [
            {"command": "bash scripts/verify/v27-team-analytics-ui.sh", "status": "PASS"}
        ],
        "controller_state_safety": {
            "controller_session_modified": False,
            "created_fake_controller_state": False,
        },
        "supporting_validators": [
            {
                "name": "target scripts/verify/validate-closure-artifact.py",
                "status": "passed",
            }
        ],
    }


class CanonicalClosureAuthorityV107Tests(unittest.TestCase):
    def test_target_specific_validator_pass_does_not_satisfy_canonical_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(target_specific_pass_artifact())

            self.assertIn("status", str(caught.exception))
            state = load_state(Path(tmp))
            self.assertEqual(state["closure_validation"]["status"], "closure_failed")
            self.assertNotEqual(
                state["closure_validation"].get("validator"),
                "target scripts/verify/validate-closure-artifact.py",
            )

    def test_required_command_requires_exit_code_or_structured_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["required_commands"][0].pop("exit_code")

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("exit_code", str(caught.exception))

            artifact["required_commands"][0]["exit_code"] = 0
            result = workflow.record_feature_closure(artifact)

            self.assertEqual(result["closure_validation"]["status"], "passed")

    def test_finalization_writes_canonical_validator_metadata_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            ready_workflow(project_root)
            artifact = valid_closure_artifact()
            artifact["required_commands"][0]["exit_code"] = 0
            artifact_path = project_root / "formal-closure.json"
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = run_finalize_cli(
                    [
                        "--project-root",
                        str(project_root),
                        "--closure-artifact",
                        str(artifact_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            state = load_state(project_root)
            self.assertEqual(
                state["closure_validation"]["validator"],
                "product_delivery_agent.finalization",
            )
            self.assertEqual(
                state["closure_validation"]["canonical_schema_version"],
                "v0.10",
            )
            self.assertEqual(state["closure_validation"]["plugin_version"], "1.0.12")
            self.assertEqual(
                state["feature_closure"]["source_artifact_path"],
                str(artifact_path),
            )
            self.assertEqual(
                state["feature_closure"]["source_artifact_sha256"],
                state["closure_validation"]["closure_artifact_sha256"],
            )

    def test_closed_state_without_canonical_validator_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(
                project_root,
                {
                    "active": True,
                    "feature_slug": "v2.7-team-member-usage-analytics-export",
                    "project_type": "ui",
                    "status": "closed_local_product_delivery",
                    "implementation": {"current_task": "COMPLETE"},
                    "delivery_goal": {"status": "complete"},
                    "executed_browser_evidence": {"status": "passed"},
                    "feature_closure": {"status": "passed"},
                    "closure_validation": {
                        "status": "passed",
                        "validator": "target scripts/verify/validate-closure-artifact.py",
                    },
                },
            )

            state = load_state(project_root)

            self.assertEqual(state["status"], "closure_failed")
            errors = " ".join(state["closure_validation"]["errors"])
            self.assertIn("canonical_closure_validation", errors)
            for result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_pre_compaction(project_root),
                check_stop_guardrail(project_root),
            ):
                self.assertFalse(result.passed)
                self.assertIn("canonical_closure_validation", " ".join(result.missing_items))
            with self.assertRaises(Exception) as caught:
                validate_state_invariants(state)
            self.assertIn("canonical_closure_validation", str(caught.exception))

    def test_project_type_normalization_is_persisted_by_workflow_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(
                project_root,
                {
                    "active": True,
                    "feature_slug": "v1.0.7-normalize-project-type",
                    "project_type": "web_system",
                    "stage": "planning",
                },
            )

            state = ProductDeliveryWorkflow(project_root).status()
            raw = json.loads(
                (project_root / ARTIFACT_ROOT / "state.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(state["project_type"], "ui")
            self.assertEqual(raw["project_type"], "ui")
            self.assertEqual(raw["project_subtype"], "web_system")


if __name__ == "__main__":
    unittest.main()
