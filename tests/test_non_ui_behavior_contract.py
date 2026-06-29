import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.non_ui_behavior import NON_UI_BEHAVIOR_TAXONOMY
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


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


class NonUIBehaviorContractTests(unittest.TestCase):
    def test_non_ui_project_records_behavior_contract_and_downstream_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
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
            workflow.start()
            workflow.select_project_type("ui")

            with self.assertRaises(WorkflowError):
                workflow.record_non_ui_behavior_contract(complete_contract_payload())

    def test_missing_taxonomy_blocks_behavior_contract_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
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
                    workflow.start()
                    workflow.select_project_type("non_ui")
                    payload = complete_contract_payload()
                    payload["taxonomy"].pop(taxonomy_field)

                    with self.assertRaises(WorkflowError) as caught:
                        workflow.record_non_ui_behavior_contract(payload)

                    self.assertIn(f"taxonomy:{taxonomy_field}", str(caught.exception))

    def test_audit_and_handoff_block_until_behavior_contract_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.confirm("product_brief")
            workflow.confirm("version_scope")

            with self.assertRaises(WorkflowError):
                workflow.prepare_audit_and_handoff_drafts()

            workflow.record_non_ui_behavior_contract(complete_contract_payload())
            workflow.confirm("non_ui_behavior_contract")
            status = workflow.prepare_audit_and_handoff_drafts()

            self.assertEqual(status["stage"], "handoff_draft_ready")

    def test_limitations_are_carried_for_later_audit_handoff_and_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
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
