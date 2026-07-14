import tempfile
import unittest
import json
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.confirmation import ConfirmationError
from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
    GatekeeperError,
    prototype_conformance_closure_binding,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import (
    confirm_product_baseline,
    confirm_test_coverage_plan,
    prototype_contract,
    record_ui_conformance,
    write_prototype_screenshot,
)


def scenario_row(**overrides):
    row = {
        "scenario_id": "SC-001",
        "role": "operator",
        "user_story": "US-001",
        "journey": "J-001",
        "path_type": "main",
        "risk_level": "high",
        "blocking_level": "p0",
        "review_status": "draft",
        "negative_boundary": "billing remains absent",
        "planned_e2e_case": "TC-V008-001",
    }
    row.update(overrides)
    return row


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
        "accepted_suggestions": ["add visible exception coverage"],
        "rejected_suggestions": ["billing remains outside this version"],
        "unresolved_questions": [],
        "blocking_findings": [],
        "traceability_reviewed": ["US", "J", "SC", "AC", "TASK", "TC"],
        "coverage_gaps": [],
        "title_overbreadth_findings": [],
        "missing_executable_assertions": [],
        "false_positive_risks": [],
        "collection_coverage": [
            {
                "collection_id": "owner-edit-paths",
                "required_items": ["owner-edit"],
                "covered_items": ["owner-edit"],
                "item_level_assertions": {
                    "owner-edit": "click owner edit action and assert owner edit form",
                },
            }
        ],
        "role_journey_coverage": [
            {
                "test_id": "TC-V008-001",
                "required_actor_roles": ["operator"],
                "journey": "J-001",
            }
        ],
        "ordinary_path_coverage": [
            {
                "test_id": "TC-V008-001",
                "ordinary_entry_path": "operator opens the existing owner edit surface",
            }
        ],
        "scenario_granularity_findings": [],
        "actual_test_code_paths": ["tests/e2e/owner.spec.ts"],
        "execution_evidence_paths": [
            ".product-delivery/artifacts/e2e/tc-v008-001.json",
        ],
        "reviewed_test_ids": ["TC-V008-001"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V008-001",
                "item_id": "owner-edit",
                "clicked_entry": "owner edit action",
                "expected_real_surface": "owner edit form",
                "assertion_target": "save button and duplicate owner error",
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


def ui_scenario_review():
    review = multi_agent_review("scenario")
    review.update(
        {
            "baseline_inheritance_review": {
                "ui_change_type": "incremental_existing_surface",
                "baseline_feature_slug": "v0-existing-owner-edit",
                "baseline_entry_path": "operator opens the existing owner edit surface",
                "inherits_existing_surface": True,
                "parallel_surface_replacement": False,
            },
            "ui_continuity_findings": [],
        }
    )
    return review


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


def ui_review_payload(prototype_path):
    return {
        "prototype_contract": prototype_contract(),
        "prototype_path": prototype_path,
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["J-001"],
        "taxonomy": {
            "roles": ["operator"],
            "main_paths": ["operator edits ownership"],
            "exceptions": ["duplicate owner name"],
            "recovery": ["retry after network failure"],
            "permissions": ["readonly operator cannot edit"],
            "long_tasks": ["bulk owner sync progress"],
            "mobile": ["375px layout"],
            "keyboard": ["tab through owner actions"],
            "negative_scope_boundaries": ["billing remains absent"],
        },
        "limitations": ["static fixture data"],
        "browser_e2e_candidates": ["J-001"],
        "negative_scope_guard_candidates": ["billing remains absent"],
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v0-existing-owner-ops",
        "baseline_surface_paths": [prototype_path],
        "baseline_user_journey": "operator opens the existing owner edit surface",
        "continuity_mapping": [
            "prototype keeps the existing owner edit entry path",
        ],
        "prototype_delta_summary": [
            "adds owner edit controls to the existing surface",
        ],
    }


def planned_obligation():
    return {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "J-001",
        "visible_exception": "duplicate owner name",
        "test_layer": "browser_e2e",
        "semantic_assertions": ["operator edits ownership"],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "operator opens the existing owner edit surface",
        "required_actor_roles": ["operator"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "operator opens the existing owner edit surface",
        "data_state_contract": "operator account with editable owner data",
        "coverage_items": ["owner-edit"],
        "action_assertions": [
            {
                "item_id": "owner-edit",
                "action_entry": "click owner edit action",
                "expected_real_surface": "owner edit form",
                "assertion_target": "save button and duplicate owner error",
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


def planned_tasks():
    return [
        {
            "task_id": f"TASK-{index:03d}",
            "title": f"Implement task {index}",
            "description": f"Deliver implementation slice {index}",
            "verification": f"pytest -k task_{index}",
        }
        for index in range(1, 5)
    ]


def write_prototype(project_root, relative_path, content):
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    write_prototype_screenshot(project_root)


def browser_evidence(project_root):
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
                "acceptance_url": "http://127.0.0.1:15082/customer/owners",
                "api_health_url": "http://127.0.0.1:15082/api/health",
                "api_health_identity": "owner-api",
                "health_response_content_type": "application/json",
                "health_response_body_sample": '{"service":"owner-api"}',
                "business_api_requests": [
                    {
                        "method": "GET",
                        "url": "http://127.0.0.1:15082/api/owners",
                        "status": 200,
                        "source": "network",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "npx playwright test tests/e2e/owner.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["operator edits ownership"],
        "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
        "evidence_strength": "full_stack_browser_e2e",
        "acceptance_url": "http://127.0.0.1:15082/customer/owners",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "owner-api",
        "network_probe_summary": {
            "business_api_request_count": 1,
            "html_shell_health_response": False,
        },
        "mocked_routes": [],
        "probe_artifact_path": ".product-delivery/artifacts/e2e/tc-v008-001-probe.json",
        "executed_actor_roles": ["operator"],
        "primary_actor_role": "operator",
        "actor_identity_evidence": {"role": "operator", "user_id": "operator-1"},
        "ordinary_path_observed": True,
        "execution_segment_id": "operator-owner-edit",
        "test_title_or_step": "operator edits owner from existing surface",
    }


def task_completion_artifact(state, task_id):
    task = next(
        task for task in state["delivery_goal"]["planned_tasks"] if task["task_id"] == task_id
    )
    return {
        "artifact_path": f".product-delivery/artifacts/{task_id}.json",
        "artifact_sha256": "b" * 64,
        "verification_command": task["verification"],
        "verification_exit_code": 0,
        "verification_output": "OK",
        "planned_task_hash": task["planned_task_hash"],
    }


def closure_artifact(state=None):
    artifact = {
        "status": "passed",
        "passed": True,
        "canonical_validator": CANONICAL_VALIDATOR,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "closure_flag": "v1.0.4-goal-driven-closure-passed",
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
    if state is not None:
        artifact["prototype_conformance"] = prototype_conformance_closure_binding(
            state
        )
    return artifact


def workflow_ready_for_handoff(project_root):
    prototype_path = "docs/prototypes/v104-prototype.html"
    write_prototype(project_root, prototype_path, "<html>revision one</html>")
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(
                feature_slug="v1.0.4-goal-driven-closure", multi_agent_mode="spawned_subagents_authorized")
    workflow.record_scenario_matrix([scenario_row()])
    workflow.select_project_type("ui")
    workflow.record_ui_prototype_review(ui_review_payload(prototype_path))
    confirm_product_baseline(
        workflow,
        multi_agent_review("scenario"),
        "确认需求范围和当前本地 HTML 原型",
    )
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["billing remains absent"],
    )
    workflow.record_multi_agent_review("test_coverage", multi_agent_review("test_coverage"))
    workflow.record_multi_agent_review("test", multi_agent_review("test"))
    confirm_test_coverage_plan(workflow)
    return workflow


def authorize_launch(workflow):
    workflow.record_implementation_launch_authorization(
        scope="Implement the frozen delivery scope",
        verification_commands=["pytest"],
        planned_tasks=planned_tasks(),
    )


class GoalDrivenClosureV104Tests(unittest.TestCase):
    def test_revised_prototype_invalidates_prior_confirmation_and_requires_new_nonce(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype_path = "docs/prototypes/v104-prototype.html"
            write_prototype(project_root, prototype_path, "<html>revision one</html>")
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                feature_slug="v1.0.4-goal-driven-closure", multi_agent_mode="spawned_subagents_authorized")
            workflow.record_scenario_matrix([scenario_row()])
            workflow.select_project_type("ui")

            workflow.record_ui_prototype_review(
                ui_review_payload(prototype_path)
            )
            workflow.record_multi_agent_review("scenario", ui_scenario_review())
            state = workflow.prepare_product_baseline_confirmation()
            first_pending = state["pending_confirmations"]["product_baseline"]
            first_hash = first_pending["artifact_hash"]
            state = workflow.confirm_product_baseline(
                "确认当前本地 HTML 原型，nonce=" + first_pending["nonce"],
                first_pending["nonce"],
            )
            self.assertTrue(state["ui_prototype"]["confirmed_by_user"])

            state = workflow.record_ui_prototype_feedback(
                "缺少人员与模板的编辑部分",
                prototype_path,
            )
            self.assertEqual(state["ui_prototype"]["confirmation_status"], "changes_requested")
            self.assertFalse(state["ui_prototype"]["confirmed_by_user"])

            write_prototype(project_root, prototype_path, "<html>revision two</html>")
            state = workflow.record_ui_prototype_review(
                ui_review_payload(prototype_path)
            )
            self.assertNotIn("product_baseline", state["pending_confirmations"])
            workflow.record_multi_agent_review("scenario", ui_scenario_review())
            state = workflow.prepare_product_baseline_confirmation()
            second_pending = state["pending_confirmations"]["product_baseline"]

            self.assertNotEqual(second_pending["artifact_hash"], first_hash)
            self.assertNotEqual(second_pending["nonce"], first_pending["nonce"])
            self.assertFalse(state["ui_prototype"]["confirmed_by_user"])
            self.assertEqual(
                state["ui_prototype"]["prototype_revision"],
                second_pending["prototype_revision"],
            )

    def test_bare_continue_cannot_confirm_revised_prototype_without_pending_nonce(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype_path = "docs/prototypes/v104-prototype.html"
            write_prototype(project_root, prototype_path, "<html>revision one</html>")
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(
                feature_slug="v1.0.4-goal-driven-closure", multi_agent_mode="spawned_subagents_authorized")
            workflow.record_scenario_matrix([scenario_row()])
            workflow.select_project_type("ui")
            workflow.record_ui_prototype_review(
                ui_review_payload(prototype_path)
            )
            workflow.record_multi_agent_review("scenario", ui_scenario_review())
            state = workflow.prepare_product_baseline_confirmation()
            pending = state["pending_confirmations"]["product_baseline"]

            with self.assertRaises(ConfirmationError):
                workflow.confirm_product_baseline(
                    "继续",
                    pending["nonce"],
                    agent_explicitly_asked=True,
                )
            with self.assertRaises(ConfirmationError):
                workflow.confirm_product_baseline(
                    "确认本地 HTML 原型",
                    "wrong-nonce",
                )

            state = workflow.confirm_product_baseline(
                "确认本地 HTML 原型，nonce=" + pending["nonce"],
                pending["nonce"],
            )

            self.assertTrue(state["ui_prototype"]["confirmed_by_user"])

    def test_handoff_creates_active_delivery_goal_and_task_queue_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            authorize_launch(workflow)

            state = workflow.generate_codex_goal_handoff(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )

            goal = state["delivery_goal"]
            self.assertEqual(goal["status"], "active")
            self.assertEqual(goal["current_task_cursor"], "TASK-001")
            self.assertEqual(len(goal["planned_tasks"]), 4)
            self.assertEqual(goal["completed_tasks"], [])
            self.assertTrue(goal["closure_required"])
            self.assertIn("不要在 TASK 未完成时停止", state["codex_goal_prompt"])
            self.assertIn("closure validator 未通过", state["codex_goal_prompt"])
            self.assertTrue(
                (
                    project_root
                    / ARTIFACT_ROOT
                    / "artifacts"
                    / "implementation-goal.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    project_root
                    / ARTIFACT_ROOT
                    / "artifacts"
                    / "task-queue.md"
                ).is_file()
            )

    def test_stop_guard_blocks_when_only_three_of_four_tasks_are_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )
            for task_id in ("TASK-001", "TASK-002", "TASK-003"):
                workflow.record_task_completion(
                    task_id,
                    artifact=task_completion_artifact(workflow._state(), task_id),
                )

            with self.assertRaises(WorkflowError) as caught:
                workflow.assert_goal_can_stop()

            self.assertIn("remaining TASK", str(caught.exception))
            self.assertIn("TASK-004", str(caught.exception))

    def test_closure_failure_keeps_goal_active_and_closure_pass_completes_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )
            for task in planned_tasks():
                workflow.record_task_completion(
                    task["task_id"],
                    artifact=task_completion_artifact(workflow._state(), task["task_id"]),
                )

            with self.assertRaises(WorkflowError) as caught:
                workflow.assert_goal_can_stop()
            self.assertIn("closure", str(caught.exception))

            with self.assertRaises(Exception):
                workflow.record_feature_closure({"status": "closed"})
            failed = load_state(project_root)
            self.assertEqual(failed["delivery_goal"]["status"], "active")
            self.assertEqual(
                failed["delivery_goal"]["next_action"],
                "fix_closure_evidence",
            )

            workflow.record_executed_browser_evidence([browser_evidence(project_root)])
            workflow.record_multi_agent_review(
                "test_implementation",
                multi_agent_review("test_implementation"),
            )
            record_ui_conformance(workflow, project_root)
            state = workflow.record_feature_closure(
                closure_artifact(workflow.status())
            )
            allowed = workflow.assert_goal_can_stop()

            self.assertEqual(state["delivery_goal"]["status"], "complete")
            self.assertEqual(allowed["stop_guard"]["status"], "allowed")
            self.assertEqual(state["closure_validation"]["status"], "passed")

    def test_executed_browser_evidence_change_stales_implementation_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement the frozen delivery scope",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )
            workflow.record_executed_browser_evidence([browser_evidence(project_root)])
            workflow.record_multi_agent_review(
                "test_implementation",
                multi_agent_review("test_implementation"),
            )

            updated_evidence = browser_evidence(project_root)
            updated_evidence["semantic_assertions"] = ["updated semantic assertion"]
            state = workflow.record_executed_browser_evidence([updated_evidence])

            self.assertEqual(
                state["multi_agent_reviews"]["test_implementation"]["status"],
                "stale",
            )
            self.assertIn(
                "stale_multi_agent_test_implementation_review",
                state["blocked_until"],
            )

    def test_revised_unconfirmed_prototype_blocks_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_handoff(project_root)
            prototype_path = "docs/prototypes/v104-prototype.html"
            workflow.record_ui_prototype_feedback(
                "缺少人员与模板的编辑部分",
                prototype_path,
            )
            write_prototype(project_root, prototype_path, "<html>revision two</html>")
            workflow.record_ui_prototype_review(ui_review_payload(prototype_path))

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement the frozen delivery scope",
                    verification_commands=["pytest"],
                    planned_tasks=planned_tasks(),
                )

            self.assertIn("ui_prototype_user_confirmation", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
