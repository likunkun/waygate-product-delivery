import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.coverage_audit import CoverageAuditError
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def ui_review_payload():
    return {
        "prototype_path": "prototype/index.html",
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["teacher creates classroom"],
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
        "browser_e2e_candidates": ["teacher creates classroom"],
        "negative_scope_guard_candidates": ["student billing is absent"],
    }


def behavior_contract_payload():
    return {
        "contract_name": "classroom import service",
        "entry_points": ["POST /imports"],
        "inputs": ["roster.csv"],
        "outputs": ["import_id"],
        "taxonomy": {
            "entry_points": ["POST /imports"],
            "inputs_outputs": ["roster.csv produces import summary"],
            "exceptions": ["invalid csv"],
            "recovery": ["retry failed rows"],
            "permissions": ["tenant isolation"],
            "long_tasks": ["import progress polling"],
            "state_transitions": ["queued -> completed"],
            "boundary_conditions": ["file over max size is rejected"],
        },
        "behavior_paths": ["valid roster import completes"],
        "negative_boundary_records": ["cross-tenant import remains unsupported"],
        "limitations": ["no SIS sync"],
    }


def coverage_row(tc_id, *, layer="browser_e2e", evidence="browser_e2e", marker="ui-browser-e2e-required", obligation="teacher creates classroom", status="covered", exempt="none", critical=True):
    return {
        "tc_id": tc_id,
        "fr": "FR-001",
        "nfr": "NFR-001",
        "us": "US-001",
        "journey": "J-001",
        "acceptance_criteria": "AC-001",
        "task": "TASK-001",
        "test_layer": layer,
        "evidence_type": evidence,
        "semantic_marker": marker,
        "coverage_status": status,
        "exemption_status": exempt,
        "obligation_ref": obligation,
        "critical": critical,
    }


class CoverageAuditTests(unittest.TestCase):
    def test_ui_audit_accepts_browser_e2e_and_supporting_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())

            result = workflow.record_test_coverage_audit(
                [
                    coverage_row("TC-V008-001"),
                    coverage_row(
                        "TC-V008-002",
                        layer="unit",
                        evidence="supporting",
                        marker="supporting-evidence-only",
                        obligation="validation helper edge cases",
                        critical=False,
                    ),
                ],
                negative_guard_records=["student billing is absent"],
            )

            self.assertTrue(result["test_coverage_audit"]["passed"])
            self.assertEqual(result["test_coverage_audit"]["matrix_range"], "TC-V008-001..TC-V008-002")
            self.assertEqual(result["test_coverage_audit"]["latest_test_case"], "TC-V008-002")
            artifact = project_root / ARTIFACT_ROOT / "artifacts" / "test-coverage-audit.md"
            self.assertIn("TC-V008-001..TC-V008-002", artifact.read_text("utf-8"))

    def test_non_ui_audit_accepts_behavior_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())

            result = workflow.record_test_coverage_audit(
                [
                    coverage_row(
                        "TC-V008-001",
                        layer="api_e2e",
                        evidence="behavior_evidence",
                        marker="non-ui-behavior-evidence",
                        obligation="valid roster import completes",
                    )
                ],
                negative_guard_records=["cross-tenant import remains unsupported"],
            )

            self.assertTrue(result["test_coverage_audit"]["passed"])
            self.assertEqual(
                result["test_coverage_audit"]["behavior_evidence_obligations"],
                ["valid roster import completes"],
            )

    def test_non_continuous_tc_range_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [coverage_row("TC-V008-001"), coverage_row("TC-V008-003")],
                    negative_guard_records=["student billing is absent"],
                )

            self.assertIn("continuous TC range", str(caught.exception))

    def test_missing_trace_anchor_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())
            row = coverage_row("TC-V008-001")
            row["acceptance_criteria"] = ""

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [row],
                    negative_guard_records=["student billing is absent"],
                )

            self.assertIn("trace anchor", str(caught.exception))

    def test_ui_supporting_evidence_cannot_replace_browser_e2e(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [
                        coverage_row(
                            "TC-V008-001",
                            layer="api_e2e",
                            evidence="supporting",
                            marker="supporting-evidence-only",
                            obligation="teacher creates classroom",
                        )
                    ],
                    negative_guard_records=["student billing is absent"],
                )

            self.assertIn("browser E2E", str(caught.exception))

    def test_missing_semantic_marker_blocks_high_risk_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())
            row = coverage_row("TC-V008-001")
            row["semantic_marker"] = ""

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [row],
                    negative_guard_records=["student billing is absent"],
                )

            self.assertIn("semantic marker", str(caught.exception))

    def test_unexempted_critical_gap_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [
                        coverage_row(
                            "TC-V008-001",
                            layer="api_e2e",
                            evidence="behavior_evidence",
                            marker="non-ui-behavior-evidence",
                            obligation="valid roster import completes",
                            status="missing",
                        )
                    ],
                    negative_guard_records=["cross-tenant import remains unsupported"],
                )

            self.assertIn("critical coverage gap", str(caught.exception))

    def test_missing_inherited_negative_guard_record_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [coverage_row("TC-V008-001")],
                    negative_guard_records=[],
                )

            self.assertIn("negative guard", str(caught.exception))

    def test_inherited_limitations_are_preserved_for_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())
            workflow.record_test_coverage_audit(
                [
                    coverage_row(
                        "TC-V008-001",
                        layer="api_e2e",
                        evidence="behavior_evidence",
                        marker="non-ui-behavior-evidence",
                        obligation="valid roster import completes",
                    )
                ],
                negative_guard_records=["cross-tenant import remains unsupported"],
            )

            state = load_state(project_root)

            self.assertEqual(
                state["test_coverage_audit"]["inherited_limitations"],
                ["no SIS sync"],
            )
            self.assertEqual(
                state["closure_inputs"]["coverage_matrix_range"],
                "TC-V008-001..TC-V008-001",
            )


if __name__ == "__main__":
    unittest.main()
