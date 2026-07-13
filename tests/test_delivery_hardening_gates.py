import tempfile
import unittest
import json
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.confirmation import ConfirmationError
from product_delivery_agent.coverage_audit import CoverageAuditError
from product_delivery_agent.review_gates import ReviewGateError
from product_delivery_agent.scenario_matrix import ScenarioMatrixError
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import prototype_contract, write_prototype_screenshot


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
        "acceptance_criteria": "AC-001",
        "task": "TASK-001",
        "visible_exception": "duplicate classroom name",
        "test_layer": "browser_e2e",
        "semantic_assertions": [
            "teacher can create classroom",
            "duplicate name error is visible",
        ],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "teacher opens the existing classroom dashboard",
        "required_actor_roles": ["teacher"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "teacher opens the existing classroom dashboard",
        "data_state_contract": "teacher account with permission to create classrooms",
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


def coverage_row(**overrides):
    row = {
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
    row.update(overrides)
    return row


def ui_review_payload(prototype_path):
    return {
        "prototype_contract": prototype_contract(),
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
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v0-existing-classroom",
        "baseline_surface_paths": [prototype_path],
        "baseline_user_journey": "teacher opens the existing classroom dashboard",
        "continuity_mapping": [
            "prototype keeps the existing classroom dashboard entry path",
        ],
        "prototype_delta_summary": [
            "adds classroom creation controls to the existing dashboard",
        ],
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
    probe_path = (
        project_root / ARTIFACT_ROOT / "artifacts" / "e2e" / "tc-v008-001-probe.json"
    )
    probe_path.write_text(
        json.dumps(
            {
                "acceptance_url": "http://127.0.0.1:15082/customer/classrooms",
                "api_health_url": "http://127.0.0.1:15082/api/health",
                "api_health_identity": "classroom-api",
                "health_response_content_type": "application/json",
                "health_response_body_sample": '{"service":"classroom-api"}',
                "business_api_requests": [
                    {
                        "method": "GET",
                        "url": "http://127.0.0.1:15082/api/classrooms",
                        "status": 200,
                        "source": "network",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
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
        "evidence_strength": "full_stack_browser_e2e",
        "acceptance_url": "http://127.0.0.1:15082/customer/classrooms",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "classroom-api",
        "network_probe_summary": {
            "business_api_request_count": 1,
            "html_shell_health_response": False,
        },
        "mocked_routes": [],
        "probe_artifact_path": ".product-delivery/artifacts/e2e/tc-v008-001-probe.json",
        "executed_actor_roles": ["teacher"],
        "primary_actor_role": "teacher",
        "actor_identity_evidence": {"role": "teacher", "user_id": "teacher-1"},
        "ordinary_path_observed": True,
        "execution_segment_id": "teacher-create-classroom",
        "test_title_or_step": "teacher creates classroom from dashboard",
    }
    record.update(overrides)
    return record


class DeliveryHardeningGateTests(unittest.TestCase):
    def _confirmed_ui_workflow_with_planned_e2e(self, project_root: Path):
        prototype_path = "docs/prototypes/v2.4.1-alert-triage-whitelist-prototype.html"
        prototype = project_root / prototype_path
        prototype.parent.mkdir(parents=True, exist_ok=True)
        prototype.write_text("<html>prototype</html>", encoding="utf-8")
        write_prototype_screenshot(project_root)
        workflow = ProductDeliveryWorkflow(project_root)
        workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")
        workflow.record_scenario_matrix([scenario_row()])
        workflow.record_multi_agent_review("scenario", scenario_review())
        workflow.select_project_type("ui")
        state = workflow.record_ui_prototype_review(ui_review_payload(prototype_path))
        pending = state["pending_confirmations"]["ui_prototype"]
        workflow.confirm_ui_prototype(
            "确认本地 HTML 原型符合预期，nonce=" + pending["nonce"],
            prototype_path,
            nonce=pending["nonce"],
        )
        workflow.record_planned_e2e_obligations([planned_obligation()])
        return workflow

    def _record_coverage_and_test_reviews(self, workflow: ProductDeliveryWorkflow):
        workflow.record_test_coverage_audit(
            [coverage_row()],
            negative_guard_records=["student billing remains absent"],
        )
        workflow.record_multi_agent_review("test_coverage", scenario_review(
            review_id="MR-COVERAGE-001",
            review_type="test_coverage",
            artifact_version="coverage-review-v1",
            traceability_reviewed=["US", "J", "SC", "AC", "TASK", "TC"],
            coverage_gaps=[],
            title_overbreadth_findings=[],
            missing_executable_assertions=[],
            false_positive_risks=[],
            collection_coverage=[
                {
                    "collection_id": "classroom-create",
                    "required_items": ["classroom-create"],
                    "covered_items": ["classroom-create"],
                    "item_level_assertions": {
                        "classroom-create": "click create classroom and assert duplicate-name error",
                    },
                }
            ],
            role_journey_coverage=[
                {
                    "test_id": "TC-V008-001",
                    "required_actor_roles": ["teacher"],
                    "journey": "J-001",
                }
            ],
            ordinary_path_coverage=[
                {
                    "test_id": "TC-V008-001",
                    "ordinary_entry_path": "teacher opens the existing classroom dashboard",
                }
            ],
            scenario_granularity_findings=[],
        ))
        workflow.record_multi_agent_review("test", scenario_review(
            review_id="MR-TEST-001",
            review_type="test",
            artifact_version="test-review-v1",
        ))

    def test_combined_requirements_and_e2e_confirmation_clears_both_user_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._confirmed_ui_workflow_with_planned_e2e(project_root)
            self._record_coverage_and_test_reviews(workflow)

            state = workflow.confirm_requirements_and_e2e_plan(
                "确认需求冻结和 planned E2E 覆盖计划",
            )

            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertTrue(state["planned_e2e_obligations"]["accepted_by_user"])
            self.assertNotIn("user_confirmed_freeze", state["blocked_until"])
            self.assertNotIn("planned_e2e_user_confirmation", state["blocked_until"])
            open_spec_confirmation = state["user_confirmations"]["open_spec_freeze"]
            planned_confirmation = state["user_confirmations"]["planned_e2e_obligations"]
            self.assertEqual(
                open_spec_confirmation["confirmation_artifact_path"],
                planned_confirmation["confirmation_artifact_path"],
            )
            self.assertEqual(
                open_spec_confirmation["snapshot_hash"],
                planned_confirmation["snapshot_hash"],
            )
            self.assertTrue(
                (
                    project_root
                    / ARTIFACT_ROOT
                    / open_spec_confirmation["confirmation_artifact_path"]
                ).is_file()
            )

    def test_scenario_review_routes_to_surface_gate_not_standalone_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")
            workflow.record_scenario_matrix([scenario_row()])

            state = workflow.record_multi_agent_review("scenario", scenario_review())

            self.assertEqual(state["next_gate"], "ui_or_non_ui_confirmation")
            self.assertIn("user_confirmed_freeze", state["blocked_until"])

    def test_reconfirming_requirements_e2e_plan_preserves_prior_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._confirmed_ui_workflow_with_planned_e2e(project_root)
            self._record_coverage_and_test_reviews(workflow)
            first = workflow.confirm_requirements_and_e2e_plan(
                "确认需求冻结和 planned E2E 覆盖计划",
            )
            first_record = first["user_confirmations"]["open_spec_freeze"]
            first_path = (
                project_root
                / ARTIFACT_ROOT
                / first_record["confirmation_artifact_path"]
            )

            workflow.record_planned_e2e_obligations(
                [
                    planned_obligation(
                        obligation_id="OBL-002",
                        visible_exception="updated duplicate classroom name",
                    )
                ]
            )
            self._record_coverage_and_test_reviews(workflow)
            second = workflow.confirm_requirements_and_e2e_plan(
                "确认修订后的需求冻结和 planned E2E 覆盖计划",
            )
            second_record = second["user_confirmations"]["open_spec_freeze"]
            second_path = (
                project_root
                / ARTIFACT_ROOT
                / second_record["confirmation_artifact_path"]
            )

            self.assertTrue(first_path.is_file())
            self.assertTrue(second_path.is_file())
            self.assertNotEqual(first_path, second_path)
            stale_targets = second["stale_user_confirmations"][-1]["targets"]
            self.assertEqual(
                sorted(stale_targets),
                ["open_spec_freeze", "planned_e2e_obligations"],
            )

    def test_coverage_audit_change_stales_reviews_confirmation_and_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._confirmed_ui_workflow_with_planned_e2e(project_root)
            self._record_coverage_and_test_reviews(workflow)
            workflow.confirm_requirements_and_e2e_plan(
                "确认需求冻结和 planned E2E 覆盖计划",
            )

            state = workflow.record_test_coverage_audit(
                [
                    coverage_row(
                        semantic_marker="ui-browser-e2e-updated",
                    )
                ],
                negative_guard_records=["student billing remains absent"],
            )

            self.assertEqual(
                state["multi_agent_reviews"]["test_coverage"]["status"],
                "stale",
            )
            self.assertEqual(state["multi_agent_reviews"]["test"]["status"], "stale")
            self.assertIn("stale_multi_agent_test_coverage_review", state["blocked_until"])
            self.assertIn("stale_multi_agent_test_review", state["blocked_until"])
            self.assertIn("user_confirmed_freeze", state["blocked_until"])
            self.assertIn("planned_e2e_user_confirmation", state["blocked_until"])
            self.assertNotIn("open_spec_freeze", state["user_confirmations"])
            self.assertNotIn("planned_e2e_obligations", state["user_confirmations"])

    def test_scenario_matrix_draft_ready_is_not_user_confirmed_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")

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

    def test_scenario_matrix_renders_journey_and_acceptance_anchors_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")

            workflow.record_scenario_matrix(
                [
                    scenario_row(
                        journey_id="J-001",
                        acceptance_anchors="AC-001, AC-002",
                        planned_e2e_case="TC-001, TC-002",
                    )
                ]
            )

            artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "scope-scenario-matrix.md"
            )
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("Journey ID", text)
            self.assertIn("Acceptance Anchors", text)
            self.assertIn("J-001", text)
            self.assertIn("AC-001, AC-002", text)

    def test_missing_scenario_review_blocks_user_confirmed_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")
            workflow.record_scenario_matrix([scenario_row()])

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_user_confirmation(user_confirmation("open_spec_freeze"))

            self.assertIn("multi-agent scenario review", str(caught.exception))

    def test_multi_agent_review_then_user_confirmation_freezes_open_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                feature_slug="v2.4.1-alert-triage-whitelist", multi_agent_mode="spawned_subagents_authorized")
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
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            bad_row = scenario_row(journey="")

            with self.assertRaises(ScenarioMatrixError) as caught:
                workflow.record_scenario_matrix([bad_row])

            self.assertIn("journey", str(caught.exception))

    def test_blocking_multi_agent_finding_rejects_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
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
            write_prototype_screenshot(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
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
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")

            state = workflow.record_planned_e2e_obligations(
                [planned_obligation()],
                exemptions=[],
            )

            self.assertTrue(state["planned_e2e_obligations"]["accepted"])
            self.assertEqual(state["executed_browser_evidence"]["status"], "missing")
            self.assertIn("executed_browser_evidence", state["blocked_until"])

    def test_non_ui_planned_obligations_accept_behavior_evidence_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")

            state = workflow.record_planned_e2e_obligations(
                [
                    planned_obligation(
                        test_layer="unit",
                        expected_artifact_pattern="tests/test_non_ui_behavior.py",
                    )
                ],
                exemptions=[],
            )

            self.assertTrue(state["planned_e2e_obligations"]["accepted"])
            self.assertEqual(
                state["planned_e2e_obligations"]["obligations"][0]["test_layer"],
                "unit",
            )
            self.assertNotIn("executed_browser_evidence", state["blocked_until"])
            self.assertIn("executed_behavior_evidence", state["blocked_until"])
            self.assertEqual(
                state["executed_behavior_evidence"]["status"],
                "missing",
            )

            artifact = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "planned-e2e-obligations.md"
            )
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("AC-001", text)
            self.assertIn("TASK-001", text)
            self.assertIn("click create classroom", text)
            self.assertIn("reject marker-only", text)

    def test_non_ui_planned_obligations_reject_browser_e2e_mislabeling(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("non_ui")

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_planned_e2e_obligations([planned_obligation()])

            self.assertIn("non-UI planned obligation", str(caught.exception))

    def test_structured_exemption_requires_approval_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
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
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
            workflow.record_planned_e2e_obligations([planned_obligation()])
            record = browser_evidence(project_root, semantic_assertions=[])

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_executed_browser_evidence([record])

            self.assertIn("semantic_assertions", str(caught.exception))

    def test_valid_executed_browser_evidence_records_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
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
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")
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
