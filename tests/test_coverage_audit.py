import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    build_executed_behavior_evidence,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow
from tests.conformance_fixtures import (
    confirm_product_baseline,
    prototype_contract,
    record_bundled_ui_prototype_review,
    write_prototype_screenshot,
)


def ui_review_payload(project_root=None):
    if project_root is not None:
        project_root = Path(project_root)
        write_prototype_screenshot(project_root)
        prototype = project_root / "prototype" / "index.html"
        prototype.parent.mkdir(parents=True, exist_ok=True)
        prototype.write_text("<html>coverage audit prototype</html>", encoding="utf-8")
    return {
        "prototype_contract": prototype_contract(),
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
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v0-existing-classroom",
        "baseline_surface_paths": ["prototype/index.html"],
        "baseline_user_journey": "teacher opens the existing classroom dashboard",
        "continuity_mapping": [
            "prototype keeps the existing classroom dashboard entry path",
        ],
        "prototype_delta_summary": [
            "adds classroom creation controls to the existing dashboard",
        ],
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


def behavior_record(project_root):
    evidence_path = (
        project_root / ".product-delivery" / "artifacts" / "behavior" / "tc-v008-001.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        '{"status":"passed","stdout":"valid roster import completes"}\n',
        encoding="utf-8",
    )
    trace_path = (
        project_root / ".product-delivery" / "artifacts" / "behavior" / "tc-v008-001.log"
    )
    trace_path.write_text(
        "command=python3 scripts/roster_import.py fixtures/valid.csv\n"
        "exit_code=0\n",
        encoding="utf-8",
    )
    return {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "python3 scripts/roster_import.py fixtures/valid.csv",
        "exit_code": 0,
        "semantic_assertions": ["valid roster import completes"],
        "evidence_path": str(evidence_path.relative_to(project_root)),
        "trace_path": str(trace_path.relative_to(project_root)),
        "execution_segment_id": "roster-import-cli",
        "test_title_or_step": "valid roster import completes",
    }


def behavior_planned_obligation():
    return {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "J-001",
        "visible_exception": "invalid csv",
        "test_layer": "api_e2e",
        "semantic_assertions": ["valid roster import completes"],
        "expected_artifact_pattern": ".product-delivery/artifacts/behavior/*.json",
        "exemption_status": "none",
    }


def scenario_review_payload():
    return {
        "review_id": "MR-SC-COVERAGE",
        "review_type": "scenario",
        "status": "passed",
        "reviewers": ["product reviewer", "scenario reviewer"],
        "artifact_version": "scenario-review-v1",
        "independent_positions": [
            "product reviewer found the scope complete",
            "scenario reviewer found the role paths complete",
        ],
        "cross_challenges": ["reviewed exceptions and negative scope guards"],
        "revisions": ["kept the reviewed product baseline unchanged"],
        "final_adjudication": "passed",
        "conclusions": ["product baseline is ready for confirmation"],
        "accepted_suggestions": [],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
    }


def confirm_current_product_baseline(workflow):
    return confirm_product_baseline(workflow, scenario_review_payload())


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
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)

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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())
            confirm_current_product_baseline(workflow)

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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_test_coverage_audit(
                    [coverage_row("TC-V008-001"), coverage_row("TC-V008-003")],
                    negative_guard_records=["student billing is absent"],
                )

            self.assertIn("continuous TC range", str(caught.exception))

    def test_missing_trace_anchor_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)
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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)

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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)
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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())
            confirm_current_product_baseline(workflow)

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
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            record_bundled_ui_prototype_review(
                workflow, project_root, ui_review_payload(project_root)
            )
            confirm_current_product_baseline(workflow)

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
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")
            workflow.record_non_ui_behavior_contract(behavior_contract_payload())
            confirm_current_product_baseline(workflow)
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

    def test_executed_behavior_evidence_accepts_cli_artifacts_without_browser_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            evidence = build_executed_behavior_evidence(
                project_root,
                [behavior_record(project_root)],
                planned_obligations=[behavior_planned_obligation()],
            )

            record = evidence["records"][0]
            self.assertEqual(evidence["status"], "passed")
            self.assertRegex(record["evidence_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(record["evidence_sha256"], record["evidence_path_sha256"])
            self.assertRegex(record["trace_path_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("evidence_strength", record)
            self.assertNotIn("probe_artifact_path", record)
            self.assertNotIn("acceptance_url", record)

    def test_executed_behavior_evidence_rejects_missing_trace_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            record = behavior_record(project_root)
            (project_root / record["trace_path"]).unlink()

            with self.assertRaises(CoverageAuditError) as caught:
                build_executed_behavior_evidence(
                    project_root,
                    [record],
                    planned_obligations=[behavior_planned_obligation()],
                )

            self.assertIn("trace_path does not exist", str(caught.exception))

    def test_executed_behavior_evidence_rejects_nonzero_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            record = behavior_record(project_root)
            record["exit_code"] = 1

            with self.assertRaises(CoverageAuditError) as caught:
                build_executed_behavior_evidence(
                    project_root,
                    [record],
                    planned_obligations=[behavior_planned_obligation()],
                )

            self.assertIn("exit_code must be 0", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
