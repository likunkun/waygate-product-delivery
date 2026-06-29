import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.gatekeeper import GatekeeperError
from product_delivery_agent.handoff import HandoffError
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
            ".product-delivery/artifacts/e2e/tc-v008-001.json",
        ],
        "reviewed_test_ids": ["TC-V008-001"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V008-001",
                "item_id": "classroom-create",
                "clicked_entry": "create classroom action",
                "expected_real_surface": "classroom creation form",
                "assertion_target": "submit button and duplicate-name error",
                "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
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
    return workflow


def authorize_launch(
    workflow,
    *,
    scope="Implement classroom dashboard",
    verification_commands=None,
    prohibited_work=None,
):
    workflow.record_implementation_launch_authorization(
        user_message="确认按当前交付包开始实现",
        scope=scope,
        verification_commands=(
            ["pytest"] if verification_commands is None else verification_commands
        ),
        prohibited_work=prohibited_work,
    )


class CodexGoalHandoffTests(unittest.TestCase):
    def test_generates_handoff_document_and_codex_goal_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_workflow(project_root)
            authorize_launch(
                workflow,
                scope="Implement classroom dashboard",
                verification_commands=["PYTHONPATH=src python3 -m unittest discover -s tests"],
                prohibited_work=["Do not mutate Waygate state"],
            )

            result = workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                non_goals=["No billing"],
                verification_commands=["PYTHONPATH=src python3 -m unittest discover -s tests"],
                prohibited_work=["Do not mutate Waygate state"],
            )

            self.assertEqual(result["stage"], "codex_goal_handoff_ready")
            self.assertTrue(result["freeze"]["frozen"])
            self.assertEqual(result["handoff"]["matrix_range"], "TC-V008-001..TC-V008-001")
            self.assertIn("J-001", result["codex_goal_prompt"])
            self.assertIn("Do not mutate Waygate state", result["codex_goal_prompt"])
            handoff = project_root / ARTIFACT_ROOT / "artifacts" / "handoff.md"
            goal = project_root / ARTIFACT_ROOT / "artifacts" / "codex-goal-prompt.md"
            self.assertTrue(handoff.is_file())
            self.assertTrue(goal.is_file())
            handoff_text = handoff.read_text("utf-8")
            self.assertIn("Closure Readiness", handoff_text)
            self.assertIn("Matrix Range: TC-V008-001..TC-V008-001", handoff_text)
            self.assertIn("Latest Test Case: TC-V008-001", handoff_text)
            self.assertIn("Browser E2E Obligations", handoff_text)
            self.assertIn("J-001", handoff_text)
            self.assertIn("Negative Guard Records", handoff_text)
            self.assertIn("student billing is absent", handoff_text)
            self.assertIn("Required Commands", handoff_text)
            self.assertIn("Prohibited Work", handoff_text)
            self.assertIn("CR Supersession Rules", handoff_text)

    def test_handoff_requires_passing_coverage_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement classroom dashboard",
                    verification_commands=["pytest"],
                )

            self.assertIn("test_coverage_audit", str(caught.exception))

    def test_required_commands_are_mandatory_for_closure_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            authorize_launch(
                workflow,
                scope="Implement classroom dashboard",
                verification_commands=[],
            )

            with self.assertRaises(HandoffError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement classroom dashboard",
                    verification_commands=[],
                )

            self.assertIn("verification commands", str(caught.exception))

    def test_scope_change_after_freeze_returns_to_version_scope_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_workflow(project_root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )

            state = workflow.record_post_freeze_change(
                change_type="scope_change",
                description="Add billing dashboard",
                cr_id="CR-002",
            )

            self.assertFalse(state["freeze"]["frozen"])
            self.assertEqual(state["stage"], "version_scope_confirmation")
            self.assertEqual(state["change_requests"][-1]["cr_id"], "CR-002")

    def test_acceptance_feedback_and_test_gaps_after_freeze_are_recorded_as_crs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )

            feedback_state = workflow.record_post_freeze_change(
                change_type="acceptance_feedback",
                description="Empty state copy must change",
                cr_id="CR-004",
            )
            gap_state = workflow.record_post_freeze_change(
                change_type="test_gap",
                description="Missing duplicate-name browser E2E",
                cr_id="CR-005",
            )

            self.assertTrue(feedback_state["freeze"]["frozen"])
            self.assertEqual(gap_state["change_requests"][-2]["change_type"], "acceptance_feedback")
            self.assertEqual(gap_state["change_requests"][-1]["change_type"], "test_gap")
            self.assertEqual(gap_state["change_requests"][-1]["status"], "recorded")

    def test_superseded_closure_records_link_to_triggering_cr(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_workflow(project_root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )

            state = workflow.record_superseded_closure(
                closure_id="closure-v1",
                triggering_cr="CR-003",
                reason="Acceptance feedback changed expected empty state",
            )

            self.assertEqual(state["superseded_closures"][-1]["status"], "superseded")
            self.assertEqual(
                state["superseded_closures"][-1]["triggering_cr"],
                "CR-003",
            )
            self.assertNotIn("feature_closure", state)


if __name__ == "__main__":
    unittest.main()
