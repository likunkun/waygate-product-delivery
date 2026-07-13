import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.ui_prototype import UI_PROTOTYPE_TAXONOMY
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import prototype_contract, write_prototype_screenshot


def complete_review_payload():
    return {
        "prototype_contract": prototype_contract(),
        "prototype_path": "prototype/index.html",
        "pages": ["dashboard", "settings"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["create classroom", "review classroom"],
        "taxonomy": {
            "roles": ["teacher", "admin"],
            "main_paths": ["teacher creates classroom"],
            "exceptions": ["duplicate classroom name"],
            "recovery": ["retry after network failure"],
            "permissions": ["teacher cannot access admin settings"],
            "long_tasks": ["bulk import progress"],
            "mobile": ["375px layout"],
            "keyboard": ["tab through primary actions"],
            "negative_scope_boundaries": ["student billing is absent"],
        },
        "limitations": ["prototype uses static fixture data"],
        "browser_e2e_candidates": [
            "teacher creates classroom",
            "duplicate classroom name",
        ],
        "negative_scope_guard_candidates": ["student billing is absent"],
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v0-existing-classroom",
        "baseline_surface_paths": ["prototype/index.html"],
        "baseline_user_journey": "teacher opens the existing classroom dashboard",
        "continuity_mapping": [
            "prototype keeps the existing classroom dashboard entry path",
        ],
        "prototype_delta_summary": [
            "adds the requested classroom controls to the existing dashboard",
        ],
    }


def scenario_review_payload():
    return {
        "review_id": "MR-SCENARIO-001",
        "review_type": "scenario",
        "status": "passed",
        "reviewers": ["agent-a", "agent-b"],
        "artifact_version": "scenario-review-v1",
        "independent_positions": ["A: no blocker", "B: no blocker"],
        "cross_challenges": ["A challenged B on journey coverage"],
        "revisions": ["Added journey coverage"],
        "final_adjudication": "passed",
        "conclusions": ["scenario review passed"],
        "accepted_suggestions": [],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
    }


def user_confirmation(target):
    return {
        "confirmation_id": f"CONF-{target}",
        "target": target,
        "artifact_path": f".product-delivery/artifacts/{target}.md",
        "artifact_version": "v1",
        "confirmed_by": "user",
        "confirmation_source": "chat_user_reply",
        "confirmed_at": "2026-07-05T00:00:00+00:00",
        "decision": "approved",
        "user_message": "确认",
    }


def confirm_scope(workflow):
    workflow.record_multi_agent_review("scenario", scenario_review_payload())
    workflow.record_user_confirmation(user_confirmation("open_spec_freeze"))


class UIPrototypeGateTests(unittest.TestCase):
    @staticmethod
    def _write_prototype(project_root):
        prototype = project_root / "prototype" / "index.html"
        prototype.parent.mkdir(parents=True, exist_ok=True)
        prototype.write_text("<html>prototype</html>", encoding="utf-8")
        write_prototype_screenshot(project_root)

    def test_ui_project_records_complete_prototype_review_and_downstream_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_prototype(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")

            result = workflow.record_ui_prototype_review(complete_review_payload())

            self.assertEqual(result["stage"], "ui_prototype_review_ready")
            review = result["ui_prototype_review"]
            self.assertEqual(review["prototype_path"], "prototype/index.html")
            self.assertEqual(set(review["taxonomy"]), set(UI_PROTOTYPE_TAXONOMY))
            self.assertEqual(
                result["downstream_inputs"]["browser_e2e_candidates"],
                ["teacher creates classroom", "duplicate classroom name"],
            )
            self.assertEqual(
                result["downstream_inputs"]["negative_scope_guard_candidates"],
                ["student billing is absent"],
            )
            artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "ui-prototype-review.md"
            )
            self.assertTrue(artifact.is_file())
            self.assertIn("teacher creates classroom", artifact.read_text("utf-8"))

    def test_non_ui_project_cannot_enter_ui_prototype_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")

            with self.assertRaises(WorkflowError):
                workflow.record_ui_prototype_review(complete_review_payload())

    def test_missing_taxonomy_blocks_prototype_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            payload = complete_review_payload()
            payload["taxonomy"].pop("keyboard")

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_ui_prototype_review(payload)

            self.assertIn("taxonomy:keyboard", str(caught.exception))

    def test_missing_permissions_or_long_tasks_block_prototype_confirmation(self):
        for taxonomy_field in ("permissions", "long_tasks"):
            with self.subTest(taxonomy_field=taxonomy_field):
                with tempfile.TemporaryDirectory() as tmp:
                    workflow = ProductDeliveryWorkflow(Path(tmp))
                    workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
                    workflow.select_project_type("ui")
                    payload = complete_review_payload()
                    payload["taxonomy"].pop(taxonomy_field)

                    with self.assertRaises(WorkflowError) as caught:
                        workflow.record_ui_prototype_review(payload)

                    self.assertIn(f"taxonomy:{taxonomy_field}", str(caught.exception))

    def test_audit_and_handoff_block_until_ui_prototype_review_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_prototype(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            confirm_scope(workflow)

            with self.assertRaises(WorkflowError):
                workflow.prepare_audit_and_handoff_drafts()

            state = workflow.record_ui_prototype_review(complete_review_payload())
            pending = state["pending_confirmations"]["ui_prototype"]
            workflow.confirm_ui_prototype(
                "确认本地 HTML 原型符合预期",
                "prototype/index.html",
                nonce=pending["nonce"],
            )
            status = workflow.prepare_audit_and_handoff_drafts()

            self.assertEqual(status["stage"], "handoff_draft_ready")

    def test_limitations_are_carried_in_state_for_later_audit_handoff_and_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_prototype(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(complete_review_payload())

            state = load_state(project_root)

            self.assertEqual(
                state["prototype_limitations"],
                ["prototype uses static fixture data"],
            )
            self.assertEqual(
                state["closure_inputs"]["ui_prototype_limitations"],
                ["prototype uses static fixture data"],
            )
            self.assertEqual(
                state["handoff_inputs"]["ui_prototype_limitations"],
                ["prototype uses static fixture data"],
            )


if __name__ == "__main__":
    unittest.main()
