import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.closure import ClosureGateError
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def scenario_row():
    return {
        "scenario_id": "SC-001",
        "role": "teacher",
        "user_story": "US-001",
        "journey": "J-001",
        "path_type": "main",
        "risk_level": "high",
        "blocking_level": "p0",
        "review_status": "draft",
        "negative_boundary": "student billing is absent",
        "planned_e2e_case": "TC-V008-001",
    }


def multi_agent_review(review_type):
    return {
        "review_id": f"MR-{review_type.upper()}-001",
        "review_type": review_type,
        "status": "passed",
        "reviewers": [
            "product intent reviewer",
            "ui scenario reviewer",
            "test strategy reviewer",
        ],
        "artifact_version": f"{review_type}-review-v1",
        "independent_positions": [
            "Reviewer A: no blocker",
            "Reviewer B: no blocker",
        ],
        "cross_challenges": [
            "Reviewer A challenged missing journey coverage and it was resolved",
        ],
        "revisions": ["Final review includes explicit browser E2E obligation"],
        "final_adjudication": "passed with no blocking findings",
        "conclusions": [f"{review_type} review passed"],
        "accepted_suggestions": ["add duplicate-name visible exception"],
        "rejected_suggestions": ["billing is outside this version"],
        "unresolved_questions": [],
        "blocking_findings": [],
        "traceability_reviewed": ["US", "J", "SC", "AC", "TASK", "TC"],
        "coverage_gaps": [],
        "title_overbreadth_findings": [],
        "missing_executable_assertions": [],
        "false_positive_risks": [],
        "collection_coverage": [
            {
                "collection_id": "classroom-journeys",
                "required_items": ["classroom-create"],
                "covered_items": ["classroom-create"],
                "item_level_assertions": {
                    "classroom-create": (
                        "click create classroom and assert classroom creation form"
                    ),
                },
            }
        ],
        "actual_test_code_paths": ["tests/e2e/classroom.spec.ts"],
        "execution_evidence_paths": [
            ".product-delivery/artifacts/browser-e2e-results.json",
        ],
        "reviewed_test_ids": ["TC-V008-001"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V008-001",
                "item_id": "classroom-create",
                "clicked_entry": "create classroom action",
                "expected_real_surface": "classroom creation form",
                "assertion_target": "submit button and duplicate-name error",
                "evidence_path": ".product-delivery/artifacts/browser-e2e-results.json",
            }
        ],
        "supporting_evidence_only": [],
    }


def user_confirmation(target):
    return {
        "confirmation_id": f"CONF-{target}",
        "target": target,
        "artifact_path": f".product-delivery/artifacts/{target}.md",
        "artifact_version": "v1",
        "confirmed_by": "user",
        "confirmation_source": "chat_user_reply",
        "confirmed_at": "2026-06-23T00:00:00+00:00",
        "decision": "approved",
        "user_message": "确认",
    }


def ui_review_payload():
    return {
        "prototype_path": "prototype/index.html",
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["J-001"],
        "taxonomy": {
            "roles": ["teacher"],
            "main_paths": ["teacher creates classroom"],
            "exceptions": ["duplicate classroom name"],
            "recovery": ["retry after network failure"],
            "permissions": ["teacher cannot access admin settings"],
            "long_tasks": ["bulk import progress"],
            "mobile": ["375px layout"],
            "keyboard": ["tab through primary actions"],
            "negative_scope_boundaries": ["student billing is absent"],
        },
        "limitations": ["static fixture data"],
        "browser_e2e_candidates": ["J-001"],
        "negative_scope_guard_candidates": ["student billing is absent"],
    }


def coverage_row():
    return {
        "tc_id": "TC-V008-001",
        "fr": "FR-001",
        "nfr": "NFR-001",
        "us": "US-001",
        "journey": "J-001",
        "acceptance_criteria": "AC-001",
        "task": "TASK-001",
        "test_layer": "browser_e2e",
        "evidence_type": "browser_e2e",
        "semantic_marker": "ui-browser-e2e-required",
        "coverage_status": "covered",
        "exemption_status": "none",
        "obligation_ref": "J-001",
        "critical": True,
    }


def planned_obligation():
    return {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "J-001",
        "visible_exception": "duplicate classroom name",
        "test_layer": "browser_e2e",
        "semantic_assertions": ["teacher creates classroom"],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "coverage_items": ["classroom-create"],
        "action_assertions": [
            {
                "item_id": "classroom-create",
                "action_entry": "click create classroom",
                "expected_real_surface": "classroom creation form",
                "assertion_target": "submit button and duplicate-name error",
                "semantic_depth": "real_surface",
            }
        ],
        "false_positive_guards": [
            "reject marker-only",
            "reject function-name-only",
            "reject static-panel-only",
            "reject first-button-only",
        ],
    }


def browser_evidence():
    return {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "npx playwright test tests/e2e/classroom.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["teacher creates classroom"],
        "evidence_path": ".product-delivery/artifacts/browser-e2e-results.json",
    }


def task_completion_artifact(state, task_id):
    task = next(
        task for task in state["delivery_goal"]["planned_tasks"] if task["task_id"] == task_id
    )
    return {
        "artifact_path": f".product-delivery/artifacts/{task_id}.json",
        "artifact_sha256": "a" * 64,
        "verification_command": task["verification"],
        "verification_exit_code": 0,
        "verification_output": "OK",
        "planned_task_hash": task["planned_task_hash"],
    }


def ready_workflow(project_root):
    prototype = project_root / "prototype" / "index.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>prototype</html>", encoding="utf-8")
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(feature_slug="v2.5-key-owner-ops")
    workflow.record_scenario_matrix([scenario_row()])
    workflow.record_multi_agent_review("scenario", multi_agent_review("scenario"))
    workflow.record_user_confirmation(user_confirmation("open_spec_freeze"))
    workflow.select_project_type("ui")
    workflow.confirm("product_brief")
    workflow.confirm("version_scope")
    state = workflow.record_ui_prototype_review(ui_review_payload())
    pending = state["pending_confirmations"]["ui_prototype"]
    workflow.confirm_ui_prototype(
        "确认本地 HTML 原型符合预期",
        "prototype/index.html",
        nonce=pending["nonce"],
    )
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_user_confirmation(user_confirmation("planned_e2e_obligations"))
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["student billing is absent"],
    )
    workflow.record_multi_agent_review("test_coverage", multi_agent_review("test_coverage"))
    workflow.record_multi_agent_review("test", multi_agent_review("test"))
    workflow.record_implementation_launch_authorization(
        scope="Implement classroom dashboard",
        verification_commands=["PYTHONPATH=src python3 -m unittest discover -s tests"],
        prohibited_work=["Do not mutate Waygate state"],
    )
    workflow.generate_codex_goal_handoff(
        scope="Implement classroom dashboard",
        verification_commands=["PYTHONPATH=src python3 -m unittest discover -s tests"],
        prohibited_work=["Do not mutate Waygate state"],
    )
    workflow.record_task_completion(
        "TASK-001",
        artifact=task_completion_artifact(
            workflow._state(),
            "TASK-001",
        ),
    )
    evidence_path = project_root / ".product-delivery" / "artifacts" / "browser-e2e-results.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"status":"passed"}\n', encoding="utf-8")
    workflow.record_executed_browser_evidence([browser_evidence()])
    workflow.record_multi_agent_review(
        "test_implementation",
        multi_agent_review("test_implementation"),
    )
    return workflow


def valid_closure_artifact():
    return {
        "status": "passed",
        "passed": True,
        "closure_flag": "v0.10-feature-closure-passed",
        "latest_test_case": "TC-V008-001",
        "matrix_range": "TC-V008-001..TC-V008-001",
        "e2e_covered_tc": ["TC-V008-001"],
        "covered_user_stories": ["US-001"],
        "covered_journeys": ["J-001"],
        "artifact_root": ".product-delivery/artifacts",
        "artifact_generation_command": "product-delivery formal-closure",
        "e2e_evidence_paths": [
            ".product-delivery/artifacts/browser-e2e-results.json",
        ],
        "high_risk_gate_subresults": {
            "ui-browser-e2e-required": "passed",
        },
        "negative_scope_guard_result": "passed",
        "required_commands": [
            {
                "command": "PYTHONPATH=src python3 -m unittest discover -s tests",
                "exit_code": 0,
                "output": "Ran 46 tests\nOK",
            }
        ],
        "secret_values_recorded": False,
        "controller_session_modified": False,
        "created_fake_controller_state": False,
    }


class FeatureClosureGateTests(unittest.TestCase):
    def test_records_passing_feature_closure_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_workflow(project_root)

            result = workflow.record_feature_closure(valid_closure_artifact())

            self.assertEqual(result["stage"], "feature_closure_passed")
            self.assertTrue(result["feature_closure"]["passed"])
            self.assertEqual(
                result["feature_closure"]["matrix_range"],
                "TC-V008-001..TC-V008-001",
            )
            closure_path = (
                project_root / ".product-delivery" / "artifacts" / "feature-closure.md"
            )
            self.assertTrue(closure_path.is_file())
            closure_text = closure_path.read_text("utf-8")
            self.assertIn("Artifact Metadata", closure_text)
            self.assertIn(".product-delivery/artifacts", closure_text)
            self.assertIn("browser-e2e-results.json", closure_text)

    def test_summary_only_completion_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure({"summary": "done in progress.md"})

            self.assertIn("closure artifact", str(caught.exception))

    def test_range_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["matrix_range"] = "TC-V008-001..TC-V008-002"

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("matrix_range", str(caught.exception))

    def test_missing_e2e_coverage_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["covered_journeys"] = []

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("covered_journeys", str(caught.exception))

    def test_missing_artifact_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["e2e_evidence_paths"] = []

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("e2e_evidence_paths", str(caught.exception))

    def test_missing_or_failed_high_risk_subresults_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            missing_artifact = valid_closure_artifact()
            missing_artifact["high_risk_gate_subresults"] = {}

            with self.assertRaises(ClosureGateError) as missing:
                workflow.record_feature_closure(missing_artifact)

            self.assertIn("high_risk_gate_subresults", str(missing.exception))

            failed_artifact = valid_closure_artifact()
            failed_artifact["high_risk_gate_subresults"] = {
                "ui-browser-e2e-required": "failed",
            }

            with self.assertRaises(ClosureGateError) as failed:
                workflow.record_feature_closure(failed_artifact)

            self.assertIn("ui-browser-e2e-required", str(failed.exception))

    def test_required_command_without_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["required_commands"][0]["output"] = ""

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("command output", str(caught.exception))

    def test_failed_negative_scope_guard_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["negative_scope_guard_result"] = "failed"

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("negative scope guard", str(caught.exception))

    def test_unsafe_integrity_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["controller_session_modified"] = True

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("controller_session_modified", str(caught.exception))

    def test_non_boolean_integrity_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["secret_values_recorded"] = "false"

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("secret_values_recorded", str(caught.exception))

    def test_superseded_closure_without_cr_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            artifact = valid_closure_artifact()
            artifact["superseded_by"] = "closure-v2"

            with self.assertRaises(ClosureGateError) as caught:
                workflow.record_feature_closure(artifact)

            self.assertIn("triggering CR", str(caught.exception))

    def test_superseded_closure_with_triggering_cr_remains_reviewable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_workflow(project_root)
            artifact = valid_closure_artifact()
            artifact["superseded_by"] = "closure-v2"
            artifact["triggering_cr"] = "CR-010"

            result = workflow.record_feature_closure(artifact)

            self.assertEqual(result["feature_closure"]["triggering_cr"], "CR-010")
            self.assertEqual(
                result["feature_closure"]["closure_artifact_path"],
                "artifacts/feature-closure.md",
            )
            self.assertTrue(
                (
                    project_root
                    / ".product-delivery"
                    / "artifacts"
                    / "feature-closure.md"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
