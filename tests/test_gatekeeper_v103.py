import tempfile
import unittest
import json
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.coverage_audit import CoverageAuditError
from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
    assert_pre_closure_ready,
    derive_blockers,
    GatekeeperError,
    normalize_project_type,
    validate_state_invariants,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow
from tests.conformance_fixtures import (
    confirm_product_baseline,
    confirm_test_coverage_plan,
    prototype_contract,
    write_prototype_screenshot,
)


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


def review(review_type, **overrides):
    payload = {
        "review_id": f"MR-{review_type.upper()}-001",
        "review_type": review_type,
        "status": "passed",
        "reviewers": [
            "product intent reviewer",
            "ui scenario reviewer",
            "test strategy reviewer",
        ],
        "reviewer_agent_ids": ["agent-product", "agent-ui", "agent-test"],
        "reviewer_spawn_source": "codex.multi_agent_v1.spawn_agent",
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
                "collection_id": "owner-operation-paths",
                "required_items": ["teacher-owner-operation"],
                "covered_items": ["teacher-owner-operation"],
                "item_level_assertions": {
                    "teacher-owner-operation": (
                        "click teacher owner operation and assert owner operation form"
                    ),
                },
            }
        ],
        "role_journey_coverage": [
            {
                "test_id": "TC-V008-001",
                "required_actor_roles": ["teacher"],
                "journey": "J-001",
            }
        ],
        "ordinary_path_coverage": [
            {
                "test_id": "TC-V008-001",
                "ordinary_entry_path": "teacher opens the existing owner operation dashboard",
            }
        ],
        "scenario_granularity_findings": [],
        "actual_test_code_paths": ["tests/e2e/owner-operation.spec.ts"],
        "execution_evidence_paths": [
            ".product-delivery/artifacts/e2e/tc-v008-001.json",
        ],
        "reviewed_test_ids": ["TC-V008-001"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V008-001",
                "item_id": "teacher-owner-operation",
                "clicked_entry": "teacher owner operation action",
                "expected_real_surface": "owner operation form",
                "assertion_target": "save button and duplicate-name error",
                "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
            }
        ],
        "supporting_evidence_only": [],
        "business_api_mock_findings": [],
        "actor_role_findings": [],
        "evidence_distribution_findings": [],
        "annotation_only_findings": [],
        "ordinary_path_findings": [],
    }
    payload.update(overrides)
    return payload


def user_confirmation(target, **overrides):
    payload = {
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
    payload.update(overrides)
    return payload


def ui_review_payload():
    return {
        "prototype_contract": prototype_contract(),
        "prototype_path": "docs/prototypes/v2.5-prototype.html",
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
        "baseline_feature_slug": "v0-existing-owner-ops",
        "baseline_surface_paths": ["docs/prototypes/v2.5-prototype.html"],
        "baseline_user_journey": "teacher opens the existing owner operation dashboard",
        "continuity_mapping": [
            "prototype keeps the existing owner operation dashboard entry path",
        ],
        "prototype_delta_summary": [
            "adds owner operation controls to the existing dashboard",
        ],
    }


def planned_obligation(**overrides):
    payload = {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "J-001",
        "visible_exception": "duplicate classroom name",
        "test_layer": "browser_e2e",
        "semantic_assertions": [
            "teacher sees the owner operation",
            "duplicate-name error is visible",
        ],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "teacher opens the existing owner operation dashboard",
        "required_actor_roles": ["teacher"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "teacher opens the existing owner operation dashboard",
        "data_state_contract": "teacher account with owner operation access",
        "coverage_items": ["teacher-owner-operation"],
        "action_assertions": [
            {
                "item_id": "teacher-owner-operation",
                "action_entry": "click teacher owner operation",
                "expected_real_surface": "owner operation form",
                "assertion_target": "save button and duplicate-name error",
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
    payload.update(overrides)
    return payload


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
                "acceptance_url": "http://127.0.0.1:15082/customer/owner-operation",
                "api_health_url": "http://127.0.0.1:15082/api/health",
                "api_health_identity": "owner-operation-api",
                "health_response_content_type": "application/json",
                "health_response_body_sample": '{"service":"owner-operation-api"}',
                "business_api_requests": [
                    {
                        "method": "GET",
                        "url": "http://127.0.0.1:15082/api/owner-operation",
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
        "command": "npx playwright test tests/e2e/v25.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["teacher sees the owner operation"],
        "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
        "evidence_strength": "full_stack_browser_e2e",
        "acceptance_url": "http://127.0.0.1:15082/customer/owner-operation",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "owner-operation-api",
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
        "execution_segment_id": "teacher-owner-operation",
        "test_title_or_step": "teacher reaches owner operation through dashboard",
    }
    record.update(overrides)
    return record


def task_completion_artifact(state, task_id):
    task = next(
        task for task in state["delivery_goal"]["planned_tasks"] if task["task_id"] == task_id
    )
    return {
        "artifact_path": f".product-delivery/artifacts/{task_id}.json",
        "artifact_sha256": "c" * 64,
        "verification_command": task["verification"],
        "verification_exit_code": 0,
        "verification_output": "OK",
        "planned_task_hash": task["planned_task_hash"],
    }


def closure_artifact():
    return {
        "status": "passed",
        "passed": True,
        "canonical_validator": CANONICAL_VALIDATOR,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "closure_flag": "v1.0.3-gate-enforcement-passed",
        "latest_test_case": "TC-V008-001",
        "matrix_range": "TC-V008-001..TC-V008-001",
        "e2e_covered_tc": ["TC-V008-001"],
        "covered_user_stories": ["US-001"],
        "covered_journeys": ["J-001"],
        "artifact_root": ".product-delivery/artifacts",
        "artifact_generation_command": "product-delivery formal-closure",
        "e2e_evidence_paths": [".product-delivery/artifacts/e2e/tc-v008-001.json"],
        "high_risk_gate_subresults": {"ui-browser-e2e-required": "passed"},
        "negative_scope_guard_result": "passed",
        "required_commands": [{"command": "pytest", "exit_code": 0, "output": "OK"}],
        "secret_values_recorded": False,
        "controller_session_modified": False,
        "created_fake_controller_state": False,
    }


def workflow_with_open_spec_and_scenario(project_root):
    prototype = project_root / "docs" / "prototypes" / "v2.5-prototype.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>prototype</html>", encoding="utf-8")
    write_prototype_screenshot(project_root)
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(
                feature_slug="v2.5-key-owner-ops", multi_agent_mode="spawned_subagents_authorized")
    workflow.record_scenario_matrix([scenario_row()])
    workflow.select_project_type("ui")
    workflow.record_ui_prototype_review(ui_review_payload())
    confirm_product_baseline(
        workflow,
        review("scenario"),
        "确认需求范围和本地 HTML 原型",
    )
    return workflow


def ready_for_handoff(project_root):
    workflow = workflow_with_open_spec_and_scenario(project_root)
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["student billing remains absent"],
    )
    workflow.record_multi_agent_review("test_coverage", review("test_coverage"))
    workflow.record_multi_agent_review("test", review("test"))
    confirm_test_coverage_plan(workflow)
    workflow.record_implementation_launch_authorization(
        scope="Implement owner operations",
        verification_commands=["pytest"],
    )
    workflow.generate_codex_goal_handoff(
        scope="Implement owner operations",
        verification_commands=["pytest"],
    )
    return workflow


class GatekeeperV103Tests(unittest.TestCase):
    def test_planned_e2e_change_after_test_coverage_review_marks_review_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_with_open_spec_and_scenario(project_root)
            workflow.record_planned_e2e_obligations([planned_obligation()])
            workflow.record_test_coverage_audit(
                [coverage_row()],
                negative_guard_records=["student billing remains absent"],
            )
            workflow.record_multi_agent_review("test_coverage", review("test_coverage"))

            state = workflow.record_planned_e2e_obligations(
                [
                    planned_obligation(
                        test_id="TC-V008-002",
                        obligation_id="OBL-002",
                    )
                ]
            )

            self.assertEqual(
                state["multi_agent_reviews"]["test_coverage"]["status"],
                "stale",
            )
            self.assertIn(
                "stale_multi_agent_test_coverage_review",
                derive_blockers(state, project_root),
            )

    def test_scenario_matrix_change_after_scenario_review_marks_review_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                feature_slug="v2.5-key-owner-ops", multi_agent_mode="spawned_subagents_authorized")
            workflow.record_scenario_matrix([scenario_row()])
            workflow.record_multi_agent_review("scenario", review("scenario"))

            state = workflow.record_scenario_matrix(
                [scenario_row(scenario_id="SC-002", planned_e2e_case="TC-V008-002")]
            )

            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["status"],
                "stale",
            )
            self.assertIn(
                "stale_multi_agent_scenario_review",
                derive_blockers(state, project_root),
            )

    def test_passed_review_without_snapshot_hash_blocks_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_for_handoff(project_root)
            state = workflow.status()
            state["multi_agent_reviews"]["test_coverage"].pop(
                "input_snapshot_hash",
                None,
            )

            blockers = derive_blockers(state, project_root)

            self.assertIn("stale_multi_agent_test_coverage_review", blockers)

    def test_non_ui_pre_closure_requires_behavior_evidence_and_implementation_review(self):
        state = {
            "project_type": "non_ui",
            "handoff": {"handoff_artifact_path": "artifacts/handoff.md"},
            "delivery_goal": {"status": "active"},
            "test_coverage_audit": {"passed": True},
            "planned_e2e_obligations": {
                "obligations": [
                    {
                        "obligation_id": "OBL-001",
                        "test_id": "TC-V008-001",
                        "scenario_id": "SC-001",
                        "user_story": "US-001",
                        "journey": "J-001",
                        "exemption_status": "none",
                    }
                ],
                "exemptions": [],
            },
            "executed_behavior_evidence": {"status": "missing", "records": []},
            "multi_agent_reviews": {
                "test_implementation": {
                    "status": "passed",
                    "input_snapshot_hash": "not-current",
                }
            },
        }

        with self.assertRaises(GatekeeperError) as caught:
            assert_pre_closure_ready(state, {})

        self.assertIn("executed_behavior_evidence", str(caught.exception))

    def test_pre_closure_rejects_stale_test_implementation_review(self):
        state = {
            "project_type": "ui",
            "handoff": {"handoff_artifact_path": "artifacts/handoff.md"},
            "delivery_goal": {"status": "active"},
            "test_coverage_audit": {"passed": True},
            "planned_e2e_obligations": {
                "obligations": [
                    {
                        "obligation_id": "OBL-001",
                        "test_id": "TC-V008-001",
                        "scenario_id": "SC-001",
                        "user_story": "US-001",
                        "journey": "J-001",
                        "exemption_status": "none",
                    }
                ],
                "exemptions": [],
            },
            "executed_browser_evidence": {
                "status": "passed",
                "records": [
                    {
                        "obligation_id": "OBL-001",
                        "test_id": "TC-V008-001",
                        "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
                    }
                ],
            },
            "multi_agent_reviews": {
                "test_implementation": {
                    "status": "passed",
                    "input_snapshot_hash": "not-current",
                }
            },
        }
        closure_artifact = {
            "e2e_covered_tc": ["TC-V008-001"],
            "covered_user_stories": ["US-001"],
            "covered_journeys": ["J-001"],
            "e2e_evidence_paths": [
                ".product-delivery/artifacts/e2e/tc-v008-001.json"
            ],
        }

        with self.assertRaises(GatekeeperError) as caught:
            assert_pre_closure_ready(state, closure_artifact)

        self.assertIn("multi_agent_test_implementation_review", str(caught.exception))

    def test_normalizes_web_system_to_ui_subtype(self):
        self.assertEqual(
            normalize_project_type("web_system"),
            ("ui", "web_system"),
        )

    def test_state_closed_without_passed_closure_validation_is_invalid(self):
        with self.assertRaises(GatekeeperError) as caught:
            validate_state_invariants(
                {
                    "active": True,
                    "project_type": "ui",
                    "status": "closed",
                    "closure_validation": {"status": "closure_failed"},
                }
            )

        self.assertIn("closure-like state requires", str(caught.exception))
        self.assertIn("closure_validation.status=passed", str(caught.exception))

    def test_handoff_blocks_until_test_coverage_plan_confirmation_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = workflow_with_open_spec_and_scenario(Path(tmp))
            workflow.record_planned_e2e_obligations([planned_obligation()])
            workflow.record_test_coverage_audit(
                [coverage_row()],
                negative_guard_records=["student billing remains absent"],
            )
            workflow.record_multi_agent_review("test_coverage", review("test_coverage"))
            workflow.record_multi_agent_review("test", review("test"))

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement owner operations",
                    verification_commands=["pytest"],
                )

            self.assertIn("test_coverage_plan_user_confirmation", str(caught.exception))

    def test_legacy_confirm_does_not_clear_product_baseline_user_confirmation_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype = project_root / "docs" / "prototypes" / "v2.5-prototype.html"
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text("<html>prototype</html>", encoding="utf-8")
            write_prototype_screenshot(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                feature_slug="v2.5-key-owner-ops",
                multi_agent_mode="spawned_subagents_authorized",
            )
            workflow.record_scenario_matrix([scenario_row()])
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(ui_review_payload())
            state = workflow.confirm("ui_prototype_review")

            self.assertFalse(state["ui_prototype"]["confirmed_by_user"])
            self.assertNotIn("product_baseline", state["user_confirmations"])
            self.assertIn("user_confirmed_freeze", state["blocked_until"])

    def test_handoff_requires_structured_multi_agent_test_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_with_open_spec_and_scenario(project_root)
            workflow.record_planned_e2e_obligations([planned_obligation()])
            workflow.record_test_coverage_audit(
                [coverage_row()],
                negative_guard_records=["student billing remains absent"],
            )
            workflow.record_multi_agent_review("test_coverage", review("test_coverage"))

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement owner operations",
                    verification_commands=["pytest"],
                )

            self.assertIn("multi_agent_test_review", str(caught.exception))

    def test_executed_browser_evidence_must_cover_unexempted_planned_obligations(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_for_handoff(project_root)

            with self.assertRaises(CoverageAuditError) as caught:
                workflow.record_executed_browser_evidence(
                    [browser_evidence(project_root, obligation_id="OBL-OTHER")]
                )

            self.assertIn("planned E2E obligation missing executed evidence", str(caught.exception))

    def test_closure_requires_executed_evidence_matching_planned_obligations(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_for_handoff(project_root)
            workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow._state(), "TASK-001"),
            )
            evidence_path = (
                project_root / ARTIFACT_ROOT / "artifacts" / "e2e" / "tc-v008-001.json"
            )
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text('{"status":"passed"}\n', encoding="utf-8")

            with self.assertRaises(GatekeeperError) as caught:
                workflow.record_feature_closure(closure_artifact())

            self.assertIn("executed_browser_evidence", str(caught.exception))

    def test_closure_requires_delivery_goal_before_validator_can_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_for_handoff(project_root)
            workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow._state(), "TASK-001"),
            )
            workflow.record_executed_browser_evidence([browser_evidence(project_root)])
            workflow.record_multi_agent_review(
                "test_implementation",
                review("test_implementation"),
            )
            state = load_state(project_root)
            state["delivery_goal"] = None
            write_state(project_root, state)

            with self.assertRaises(GatekeeperError) as caught:
                workflow.record_feature_closure(closure_artifact())

            self.assertIn("implementation_without_delivery_goal", str(caught.exception))

    def test_invalid_closure_writes_closure_validator_result_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ready_for_handoff(project_root)
            workflow.record_executed_browser_evidence([browser_evidence(project_root)])
            workflow.record_multi_agent_review(
                "test_implementation",
                review("test_implementation"),
            )
            bad_artifact = closure_artifact()
            bad_artifact["status"] = "closed"

            with self.assertRaises(Exception):
                workflow.record_feature_closure(bad_artifact)

            state = load_state(project_root)
            self.assertEqual(state["closure_validation"]["status"], "closure_failed")
            self.assertNotEqual(state.get("status"), "closed")
            result_path = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "closure-validator-result.md"
            )
            self.assertTrue(result_path.is_file())
            self.assertIn("closure_failed", result_path.read_text("utf-8"))

    def test_project_type_web_system_is_normalized_when_existing_state_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            state = workflow.start(
                feature_slug="v2.5-key-owner-ops", multi_agent_mode="spawned_subagents_authorized")
            state["project_type"] = "web_system"
            write_state(project_root, state)

            recovered = ProductDeliveryWorkflow(project_root).status()

            self.assertEqual(recovered["project_type"], "ui")
            self.assertEqual(recovered["project_subtype"], "web_system")


if __name__ == "__main__":
    unittest.main()
