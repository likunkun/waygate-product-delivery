import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.non_ui_behavior import NON_UI_BEHAVIOR_TAXONOMY
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import confirm_product_baseline
from tests.test_feature_closure import scenario_row


def complete_contract_payload():
    return {
        "contract_name": "classroom import service",
        "entry_points": ["POST /imports", "classroom import --file roster.csv"],
        "inputs": ["roster.csv", "teacher_id"],
        "outputs": ["import_id", "accepted_count", "rejected_count"],
        "taxonomy": {
            "entry_points": ["POST /imports"],
            "inputs_outputs": ["roster.csv produces import summary"],
            "exceptions": ["invalid csv", "duplicate student"],
            "recovery": ["retry failed rows"],
            "permissions": ["teacher cannot import another tenant"],
            "long_tasks": ["import progress polling"],
            "state_transitions": ["queued -> running -> completed"],
            "boundary_conditions": ["file over max size is rejected"],
        },
        "behavior_paths": [
            "valid roster import completes",
            "invalid csv returns row errors",
        ],
        "negative_boundary_records": [
            "cross-tenant import remains unsupported",
        ],
        "limitations": ["contract does not cover SIS sync"],
    }


def scenario_review_payload():
    return {
        "review_id": "MR-SCENARIO-001",
        "review_type": "scenario",
        "status": "passed",
        "reviewers": ["agent-a", "agent-b"],
        "artifact_version": "scenario-review-v1",
        "independent_positions": ["A: no blocker", "B: no blocker"],
        "cross_challenges": ["A challenged B on behavior coverage"],
        "revisions": ["Added behavior coverage"],
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
    if not workflow.status().get("scenario_matrix_draft_ready"):
        workflow.record_scenario_matrix([scenario_row()])
    return confirm_product_baseline(
        workflow,
        scenario_review_payload(),
        "确认需求范围和非 UI 行为契约",
    )


class NonUIBehaviorContractTests(unittest.TestCase):
    def test_non_ui_project_records_behavior_contract_and_downstream_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")

            result = workflow.record_non_ui_behavior_contract(complete_contract_payload())

            self.assertEqual(result["stage"], "non_ui_behavior_contract_ready")
            contract = result["non_ui_behavior_contract"]
            self.assertEqual(contract["contract_name"], "classroom import service")
            self.assertEqual(set(contract["taxonomy"]), set(NON_UI_BEHAVIOR_TAXONOMY))
            self.assertEqual(
                result["downstream_inputs"]["behavior_evidence_candidates"],
                ["valid roster import completes", "invalid csv returns row errors"],
            )
            self.assertEqual(
                result["downstream_inputs"]["negative_boundary_candidates"],
                ["cross-tenant import remains unsupported"],
            )
            artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "non-ui-behavior-contract.md"
            )
            self.assertTrue(artifact.is_file())
            self.assertIn("valid roster import completes", artifact.read_text("utf-8"))

    def test_ui_project_cannot_enter_non_ui_behavior_contract_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")

            with self.assertRaises(WorkflowError):
                workflow.record_non_ui_behavior_contract(complete_contract_payload())

    def test_missing_taxonomy_blocks_behavior_contract_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            payload = complete_contract_payload()
            payload["taxonomy"].pop("state_transitions")

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_non_ui_behavior_contract(payload)

            self.assertIn("taxonomy:state_transitions", str(caught.exception))

    def test_missing_permissions_or_long_tasks_block_behavior_contract_recording(self):
        for taxonomy_field in ("permissions", "long_tasks"):
            with self.subTest(taxonomy_field=taxonomy_field):
                with tempfile.TemporaryDirectory() as tmp:
                    workflow = ProductDeliveryWorkflow(Path(tmp))
                    workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
                    workflow.select_project_type("non_ui")
                    payload = complete_contract_payload()
                    payload["taxonomy"].pop(taxonomy_field)

                    with self.assertRaises(WorkflowError) as caught:
                        workflow.record_non_ui_behavior_contract(payload)

                    self.assertIn(f"taxonomy:{taxonomy_field}", str(caught.exception))

    def test_audit_and_handoff_block_until_behavior_contract_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            with self.assertRaises(WorkflowError):
                workflow.prepare_audit_and_handoff_drafts()

            workflow.record_non_ui_behavior_contract(complete_contract_payload())
            confirm_scope(workflow)
            status = workflow.prepare_audit_and_handoff_drafts()

            self.assertEqual(status["stage"], "handoff_draft_ready")

    def test_limitations_are_carried_for_later_audit_handoff_and_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(complete_contract_payload())

            state = load_state(project_root)

            self.assertEqual(
                state["behavior_contract_limitations"],
                ["contract does not cover SIS sync"],
            )
            self.assertEqual(
                state["closure_inputs"]["non_ui_behavior_limitations"],
                ["contract does not cover SIS sync"],
            )
            self.assertEqual(
                state["handoff_inputs"]["non_ui_behavior_limitations"],
                ["contract does not cover SIS sync"],
            )


if __name__ == "__main__":
    unittest.main()
