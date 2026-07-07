import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.delivery_goal import DeliveryGoalError, record_task_completion
from product_delivery_agent.finalization import run_finalize_cli
from product_delivery_agent.gatekeeper import derive_blockers, render_closure_validator_result
from product_delivery_agent.plugin_packaging import package_codex_plugin
from product_delivery_agent.transition_journal import transition_names

from tests.test_feature_closure import ready_workflow, valid_closure_artifact
from tests.test_goal_driven_closure_v104 import workflow_ready_for_handoff


def write_raw_state(project_root, state):
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


class TransitionAuthorityV108Tests(unittest.TestCase):
    def test_packaged_validator_bootstraps_runtime_without_source_pythonpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = package_codex_plugin(Path(tmp))
            plugin_root = result["plugin_root"]

            self.assertTrue(
                (plugin_root / "runtime" / "product_delivery_agent" / "finalization.py").is_file()
            )

            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            env["PYTHONNOUSERSITE"] = "1"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(plugin_root / "scripts" / "validate-closure-artifact.py"),
                    "--help",
                ],
                cwd="/tmp",
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("--closure-artifact", completed.stdout)

    def test_hand_edited_closed_state_without_closure_transition_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            artifact = project_root / "formal-closure.json"
            artifact.write_text(json.dumps(valid_closure_artifact()), encoding="utf-8")
            write_raw_state(
                project_root,
                {
                    "active": True,
                    "feature_slug": "v2.8-scenario-ui-mobile-raw-unlock",
                    "project_type": "ui",
                    "status": "closed",
                    "implementation": {"current_task": "COMPLETE"},
                    "delivery_goal": {"status": "complete"},
                    "executed_browser_evidence": {"status": "passed"},
                    "feature_closure": {
                        "status": "passed",
                        "source_artifact_path": str(artifact),
                        "source_artifact_sha256": "not-a-real-hash",
                    },
                    "closure_validation": {
                        "status": "passed",
                        "validator": "product_delivery_agent.finalization",
                        "canonical_schema_version": "v0.10",
                        "plugin_version": "1.0.11",
                        "closure_artifact_sha256": "not-a-real-hash",
                        "result_artifact": "artifacts/closure-validator-result.md",
                    },
                },
            )

            state = load_state(project_root)

            self.assertEqual(state["status"], "closure_failed")
            self.assertIn(
                "canonical_closure_transition",
                " ".join(state["closure_validation"]["errors"]),
            )
            self.assertIn(
                "canonical_closure_transition",
                derive_blockers(state, project_root),
            )

    def test_docs_claims_cannot_lead_canonical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(
                project_root,
                {
                    "active": True,
                    "feature_slug": "v2.8-scenario-ui-mobile-raw-unlock",
                    "project_type": "ui",
                    "open_spec_draft_ready": True,
                    "scenario_matrix_draft_ready": True,
                    "scenario_matrix": {"draft_ready": True},
                    "multi_agent_reviews": {
                        "scenario": {"status": "passed"},
                        "test": {"status": "passed"},
                    },
                    "open_spec_freeze": {"approved_by_user": True},
                    "user_confirmations": {
                        "open_spec_freeze": {},
                        "ui_prototype": {},
                        "planned_e2e_obligations": {},
                    },
                    "ui_prototype": {
                        "generated": True,
                        "reviewed_by_agent": True,
                        "confirmed_by_user": True,
                    },
                    "planned_e2e_obligations": {
                        "accepted": True,
                        "accepted_by_user": True,
                        "obligations": [{"obligation_id": "OBL-001"}],
                    },
                    "test_coverage_audit": {"passed": True},
                    "implementation_launch_authorization": {"status": "authorized"},
                    "executed_browser_evidence": {"status": "not_started"},
                    "closure_validation": {"status": "not_run"},
                },
            )
            (project_root / "progress.md").write_text(
                "v2.8-scenario-ui-mobile-raw-unlock status=Executed and closed\n",
                encoding="utf-8",
            )

            blockers = derive_blockers(load_state(project_root), project_root)

            self.assertIn("docs_ahead_of_executed_evidence", blockers)
            self.assertIn("docs_ahead_of_closure_validation", blockers)

    def test_closure_validation_feature_slug_must_match_current_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            artifact = project_root / "formal-closure.json"
            artifact.write_text(json.dumps(valid_closure_artifact()), encoding="utf-8")
            write_raw_state(
                project_root,
                {
                    "active": True,
                    "feature_slug": "v2.8-current",
                    "project_type": "ui",
                    "status": "closed",
                    "implementation": {"current_task": "COMPLETE"},
                    "delivery_goal": {"status": "complete"},
                    "executed_browser_evidence": {"status": "passed"},
                    "feature_closure": {
                        "status": "passed",
                        "source_artifact_path": str(artifact),
                        "source_artifact_sha256": "not-a-real-hash",
                    },
                    "closure_validation": {
                        "status": "passed",
                        "validator": "product_delivery_agent.finalization",
                        "canonical_schema_version": "v0.10",
                        "plugin_version": "1.0.11",
                        "feature_slug": "v2.7-old",
                        "closure_artifact_sha256": "not-a-real-hash",
                        "result_artifact": "artifacts/closure-validator-result.md",
                    },
                },
            )

            state = load_state(project_root)

            self.assertEqual(state["status"], "closure_failed")
            self.assertIn(
                "current_feature_closure_validation",
                " ".join(state["closure_validation"]["errors"]),
            )

    def test_task_completion_must_follow_current_cursor_and_include_verification(self):
        state = {
            "feature_slug": "v1.0.8-transition-authority",
            "delivery_goal": {
                "status": "active",
                "current_task_cursor": "TASK-001",
                "planned_tasks": [
                    {
                        "task_id": "TASK-001",
                        "title": "First",
                        "description": "first task",
                        "verification": "pytest -k first",
                        "planned_task_hash": "hash-001",
                    },
                    {
                        "task_id": "TASK-002",
                        "title": "Second",
                        "description": "second task",
                        "verification": "pytest -k second",
                        "planned_task_hash": "hash-002",
                    },
                ],
                "completed_tasks": [],
                "task_completion_artifacts": {},
            },
        }
        valid_artifact = {
            "artifact_path": ".product-delivery/artifacts/task-001.json",
            "artifact_sha256": "a" * 64,
            "verification_command": "pytest -k first",
            "verification_exit_code": 0,
            "verification_output": "OK",
            "planned_task_hash": "hash-001",
        }

        with self.assertRaises(DeliveryGoalError) as caught:
            record_task_completion(state, "TASK-002", valid_artifact, completed_at="ignored")
        self.assertIn("current task cursor", str(caught.exception))

        missing_verification = dict(valid_artifact)
        missing_verification.pop("verification_output")
        with self.assertRaises(DeliveryGoalError) as caught:
            record_task_completion(state, "TASK-001", missing_verification, completed_at="ignored")
        self.assertIn("verification_output", str(caught.exception))

    def test_handoff_task_completion_evidence_and_closure_write_transition_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            workflow.record_implementation_launch_authorization(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=[
                    {
                        "task_id": "TASK-001",
                        "title": "Implement task 1",
                        "description": "Deliver implementation slice 1",
                        "verification": "pytest -k task_1",
                    }
                ],
            )
            workflow.generate_codex_goal_handoff(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=[
                    {
                        "task_id": "TASK-001",
                        "title": "Implement task 1",
                        "description": "Deliver implementation slice 1",
                        "verification": "pytest -k task_1",
                    }
                ],
            )
            state = load_state(project_root)
            self.assertEqual(
                state["transition_journal"]["events"][-1]["transition_name"],
                "handoff_generated",
            )

            workflow.record_task_completion(
                "TASK-001",
                artifact={
                    "artifact_path": ".product-delivery/artifacts/task-001.json",
                    "artifact_sha256": "b" * 64,
                    "verification_command": "pytest -k task_1",
                    "verification_exit_code": 0,
                    "verification_output": "OK",
                    "planned_task_hash": state["delivery_goal"]["planned_tasks"][0][
                        "planned_task_hash"
                    ],
                },
            )
            state = load_state(project_root)
            self.assertEqual(
                state["transition_journal"]["events"][-1]["transition_name"],
                "task_completed",
            )

    def test_stale_closure_validator_result_does_not_satisfy_current_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            ready_workflow(project_root)
            result_path = (
                project_root / ARTIFACT_ROOT / "artifacts" / "closure-validator-result.md"
            )
            result_path.write_text(
                render_closure_validator_result(
                    "passed",
                    [],
                    feature_slug="v2.7-old-feature",
                ),
                encoding="utf-8",
            )
            artifact = valid_closure_artifact()
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
            self.assertIn("closure_validated", transition_names(state))
            self.assertIn("goal_completed", transition_names(state))
            self.assertEqual(state["closure_validation"]["feature_slug"], "v2.5-key-owner-ops")


if __name__ == "__main__":
    unittest.main()
