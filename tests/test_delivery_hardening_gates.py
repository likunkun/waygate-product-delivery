import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.confirmation import ConfirmationError
from product_delivery_agent.coverage_audit import CoverageAuditError
from product_delivery_agent.review_gates import ReviewGateError
from product_delivery_agent.scenario_matrix import ScenarioMatrixError
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


def scenario_row(**overrides):
    row = {
        "scenario_id": "SC-001",
        "role": "teacher",
        "user_story": "US-001",
        "journey": "J-001",
        "path_type": "main",
        "risk_level": "high",
        "blocking_level": "p0",
        "review_status": "draft",
        "negative_boundary": "student billing remains absent",
        "planned_e2e_case": "TC-V008-001",
    }
    row.update(overrides)
    return row


def scenario_review(**overrides):
    review = {
        "review_id": "MR-SC-001",
        "review_type": "scenario",
        "status": "passed",
        "reviewers": [
            "product intent reviewer",
            "ui scenario reviewer",
            "negative boundary reviewer",
        ],
        "artifact_version": "scenario-matrix-v1",
        "independent_positions": [
            "product intent reviewer: no blocker",
            "ui scenario reviewer: no blocker",
        ],
        "cross_challenges": [
            "negative boundary reviewer challenged billing leakage and it remained out of scope",
        ],
        "revisions": ["duplicate-name error path added"],
        "final_adjudication": "passed with no blocking findings",
        "conclusions": ["draft matrix is ready for user freeze"],
        "accepted_suggestions": ["add duplicate-name error path"],
        "rejected_suggestions": ["billing scenario rejected as out of version boundary"],
        "unresolved_questions": [],
        "blocking_findings": [],
    }
    review.update(overrides)
    return review


def user_confirmation(target, **overrides):
    confirmation = {
        "confirmation_id": f"CONF-{target}",
        "target": target,
        "artifact_path": f".product-delivery/artifacts/{target}.md",
        "artifact_version": "v1",
        "confirmed_by": "user",
        "confirmation_source": "chat_user_reply",
        "confirmed_at": "2026-06-22T14:00:00+00:00",
        "decision": "approved",
        "user_message": "确认",
    }
    confirmation.update(overrides)
    return confirmation


def planned_obligation(**overrides):
    obligation = {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "J-001",
        "visible_exception": "duplicate classroom name",
        "test_layer": "browser_e2e",
        "semantic_assertions": [
            "teacher can create classroom",
            "duplicate name error is visible",
        ],
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
    obligation.update(overrides)
    return obligation


def ui_review_payload(prototype_path):
    return {
        "prototype_path": prototype_path,
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["J-001"],
        "taxonomy": {
            "roles": ["teacher"],
            "main_paths": ["J-001"],
            "exceptions": ["duplicate classroom name"],
            "recovery": ["retry after network failure"],
            "permissions": ["teacher cannot access admin settings"],
            "long_tasks": ["bulk import progress"],
            "mobile": ["375px layout"],
            "keyboard": ["tab through primary actions"],
            "negative_scope_boundaries": ["student billing remains absent"],
        },
        "limitations": ["static fixture data"],
        "browser_e2e_candidates": ["J-001"],
        "negative_scope_guard_candidates": ["student billing remains absent"],
    }


def structured_exemption(**overrides):
    exemption = {
        "exemption_id": "EX-001",
        "object_id": "SC-002",
        "exemption_type": "user_approved",
        "reason": "mobile keyboard path is not relevant to this CLI-only admin flow",
        "risk_impact": "low",
        "alternative_evidence": "manual accessibility review",
        "approved_by": "user",
        "approval_source": "chat_user_reply",
        "approved_at": "2026-06-22T14:30:00+00:00",
        "valid_scope": "v2.4.1-alert-triage-whitelist",
        "allows_closure": True,
    }
    exemption.update(overrides)
    return exemption


def browser_evidence(project_root, **overrides):
    evidence_path = (
        project_root / ARTIFACT_ROOT / "artifacts" / "e2e" / "tc-v008-001.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"status":"passed"}\n', encoding="utf-8")
    record = {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "npx playwright test tests/e2e/alert-triage.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["teacher can create classroom"],
        "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
        "evidence_sha256": "",
    }
    record.update(overrides)
    return record


class DeliveryHardeningGateTests(unittest.TestCase):
    def test_scenario_matrix_draft_ready_is_not_user_confirmed_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(feature_slug="v2.4.1-alert-triage-whitelist")

            state = workflow.record_scenario_matrix([scenario_row()])

            self.assertTrue(state["scenario_matrix"]["draft_ready"])
            self.assertFalse(state["open_spec_freeze"]["approved_by_user"])
            self.assertIn("multi_agent_scenario_review", state["blocked_until"])
            self.assertIn("user_confirmed_freeze", state["blocked_until"])
            artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "scope-scenario-matrix.md"
            )
            self.assertTrue(artifact.is_file())

    def test_missing_scenario_review_blocks_user_confirmed_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(feature_slug="v2.4.1-alert-triage-whitelist")
            workflow.record_scenario_matrix([scenario_row()])

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_user_confirmation(user_confirmation("open_spec_freeze"))

            self.assertIn("multi-agent scenario review", str(caught.exception))

    def test_multi_agent_review_then_user_confirmation_freezes_open_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(feature_slug="v2.4.1-alert-triage-whitelist")
            workflow.record_scenario_matrix([scenario_row()])
            workflow.record_multi_agent_review("scenario", scenario_review())

            state = workflow.record_user_confirmation(
                user_confirmation("open_spec_freeze")
            )

            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertNotIn("user_confirmed_freeze", state["blocked_until"])
            confirmation_artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "user-confirmations"
                / "open_spec_freeze.md"
            )
            self.assertTrue(confirmation_artifact.is_file())

    def test_scenario_matrix_requires_traceable_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            bad_row = scenario_row(journey="")

            with self.assertRaises(ScenarioMatrixError) as caught:
                workflow.record_scenario_matrix([bad_row])

            self.assertIn("journey", str(caught.exception))

    def test_blocking_multi_agent_finding_rejects_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.record_scenario_matrix([scenario_row()])

            with self.assertRaises(ReviewGateError):
                workflow.record_multi_agent_review(
                    "scenario",
                    scenario_review(blocking_findings=["missing error path"]),
                )

    def test_confirm_ui_prototype_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype_path = "docs/prototypes/v2.4.1-alert-triage-whitelist-prototype.html"
            prototype = project_root / prototype_path
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text("<html>prototype</html>", encoding="utf-8")
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")
            state = workflow.record_ui_prototype_review(
                ui_review_payload(prototype_path)
            )
            pending = state["pending_confirmations"]["ui_prototype"]

            with self.assertRaises(ConfirmationError):
                workflow.confirm_ui_prototype(
                    "继续",
                    prototype_path,
                    agent_explicitly_asked=True,
                )
            with self.assertRaises(ConfirmationError):
                workflow.confirm_ui_prototype(
                    "确认本地 HTML 原型符合预期",
                    prototype_path,
                    nonce="wrong-nonce",
                )

            state = workflow.confirm_ui_prototype(
                "确认本地 HTML 原型符合预期，nonce=" + pending["nonce"],
                prototype_path,
                nonce=pending["nonce"],
            )

            self.assertTrue(state["ui_prototype"]["confirmed_by_user"])
            self.assertEqual(
                state["ui_prototype"]["confirmation_source"],
                "chat_user_reply",
            )

    def test_planned_e2e_obligations_allow_empty_executed_evidence_before_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()

            state = workflow.record_planned_e2e_obligations(
                [planned_obligation()],
                exemptions=[],
            )

            self.assertTrue(state["planned_e2e_obligations"]["accepted"])
            self.assertEqual(state["executed_browser_evidence"]["status"], "missing")
            self.assertIn("executed_browser_evidence", state["blocked_until"])

    def test_structured_exemption_requires_approval_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            exemption = structured_exemption(approved_at="")

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_planned_e2e_obligations(
                    [planned_obligation(exemption_status="approved")],
                    exemptions=[exemption],
                )

            self.assertIn("approved_at", str(caught.exception))

    def test_executed_browser_evidence_requires_existing_path_and_semantic_assertions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.record_planned_e2e_obligations([planned_obligation()])
            record = browser_evidence(project_root, semantic_assertions=[])

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_executed_browser_evidence([record])

            self.assertIn("semantic_assertions", str(caught.exception))

    def test_valid_executed_browser_evidence_records_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.record_planned_e2e_obligations([planned_obligation()])

            state = workflow.record_executed_browser_evidence(
                [browser_evidence(project_root)]
            )

            evidence = state["executed_browser_evidence"]["records"][0]
            self.assertEqual(state["executed_browser_evidence"]["status"], "passed")
            self.assertTrue(evidence["evidence_sha256"])

    def test_invalid_closure_writes_closure_failed_state_without_closed_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.generate_codex_goal_handoff = lambda **kwargs: None

            with self.assertRaises(Exception):
                workflow.record_feature_closure({"status": "closed"})

            state = load_state(project_root)
            self.assertEqual(state["closure_validation"]["status"], "closure_failed")
            self.assertEqual(state["stage"], "closure_failed")
            self.assertNotEqual(state.get("status"), "closed")
            self.assertFalse(state["blocking_gates"]["closure"])


if __name__ == "__main__":
    unittest.main()
