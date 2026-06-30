import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.finalization import run_finalize_cli
from product_delivery_agent.gatekeeper import GatekeeperError, derive_blockers
from product_delivery_agent.hooks import (
    build_prompt_context,
    build_resume_context,
    check_pre_compaction,
    check_stop_guardrail,
)
from product_delivery_agent.review_gates import ReviewGateError
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def write_raw_state(project_root, state):
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def poisoned_implementation_state():
    return {
        "active": True,
        "feature_slug": "v2.6.1-provider-capacity-governance-fixes",
        "project_type": "web_system",
        "status": "implementation_in_progress",
        "blocking_gates": {
            "pre_handoff": True,
            "ui_prototype_gate": True,
        },
        "implementation": {
            "current_task": "TASK-005",
            "completed_tasks": ["TASK-001", "TASK-002", "TASK-003", "TASK-004"],
        },
        "handoff": None,
        "delivery_goal": None,
        "executed_browser_evidence": None,
        "closure_validation": None,
    }


def scenario_row():
    return {
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


def review_payload(review_type, **overrides):
    payload = {
        "review_id": f"MR-{review_type.upper()}-001",
        "review_type": review_type,
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["agent-a", "agent-b"],
        "artifact_version": f"{review_type}-review-v1",
        "independent_positions": ["A: no blocker", "B: no blocker"],
        "cross_challenges": ["A challenged B on E2E journey coverage"],
        "revisions": ["Added journey coverage"],
        "final_adjudication": "passed",
        "conclusions": [f"{review_type} review passed"],
        "accepted_suggestions": ["add mobile journey"],
        "rejected_suggestions": [],
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
        "confirmed_at": "2026-06-25T00:00:00+00:00",
        "decision": "approved",
        "user_message": "确认",
    }
    payload.update(overrides)
    return payload


def ui_review_payload(prototype_path):
    return {
        "prototype_path": prototype_path,
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["J-001"],
        "taxonomy": {
            "roles": ["operator"],
            "main_paths": ["J-001"],
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


def planned_tasks(extra=False):
    tasks = [
        {
            "task_id": "TASK-001",
            "title": "Implement provider governance",
            "description": "Deliver the frozen provider governance slice.",
            "verification": "pytest -k task_001",
        }
    ]
    if extra:
        tasks.append(
            {
                "task_id": "TASK-002",
                "title": "Unexpected extra task",
                "description": "This task was not in the launch package.",
                "verification": "pytest -k task_002",
            }
        )
    return tasks


def closure_artifact():
    return {
        "status": "passed",
        "passed": True,
        "closure_flag": "v1.0.6-canonical-launch-passed",
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


def workflow_ready_for_launch(project_root):
    prototype_path = "docs/prototypes/v106-prototype.html"
    prototype = project_root / prototype_path
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>revision one</html>", encoding="utf-8")

    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(feature_slug="v1.0.6-canonical-launch")
    workflow.record_scenario_matrix([scenario_row()])
    workflow.record_multi_agent_review("scenario", review_payload("scenario"))
    workflow.record_user_confirmation(user_confirmation("open_spec_freeze"))
    workflow.select_project_type("ui")
    state = workflow.record_ui_prototype_review(ui_review_payload(prototype_path))
    pending = state["pending_confirmations"]["ui_prototype"]
    workflow.confirm_ui_prototype(
        "确认本地 HTML 原型，nonce=" + pending["nonce"],
        prototype_path,
        nonce=pending["nonce"],
    )
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_user_confirmation(user_confirmation("planned_e2e_obligations"))
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["billing remains absent"],
    )
    workflow.record_multi_agent_review("test_coverage", review_payload("test_coverage"))
    workflow.record_multi_agent_review("test", review_payload("test"))
    return workflow


class CanonicalLaunchV106Tests(unittest.TestCase):
    def test_implementation_state_without_goal_fails_closed_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_raw_state(project_root, poisoned_implementation_state())
            custom_gate = (
                project_root
                / ARTIFACT_ROOT
                / "artifacts"
                / "v2.6.1-pre-handoff-gate.json"
            )
            custom_gate.parent.mkdir(parents=True, exist_ok=True)
            custom_gate.write_text('{"status":"PASS"}\n', encoding="utf-8")

            state = load_state(project_root)

            self.assertEqual(state["status"], "implementation_blocked")
            self.assertIn(
                "implementation_without_delivery_goal",
                state["protocol_errors"],
            )
            self.assertIn(
                "implementation_without_delivery_goal",
                derive_blockers(state, project_root),
            )
            for result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_pre_compaction(project_root),
                check_stop_guardrail(project_root),
            ):
                self.assertTrue(result.active)
                self.assertFalse(result.passed)
                self.assertIn(
                    "implementation_without_delivery_goal",
                    " ".join(result.missing_items),
                )

            closure_path = project_root / "formal-closure.json"
            closure_path.write_text(json.dumps(closure_artifact()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = run_finalize_cli(
                    [
                        "--project-root",
                        str(project_root),
                        "--closure-artifact",
                        str(closure_path),
                    ]
                )
            self.assertEqual(exit_code, 1)

    def test_handoff_requires_canonical_launch_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = workflow_ready_for_launch(project_root)

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement the frozen package",
                    verification_commands=["pytest"],
                    planned_tasks=planned_tasks(),
                )

            self.assertIn("implementation_launch_authorization", str(caught.exception))

            state = workflow.record_implementation_launch_authorization(
                user_message="确认按当前交付包开始实现",
                scope="Implement the frozen package",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )
            self.assertEqual(
                state["implementation_launch_authorization"]["status"],
                "authorized",
            )

            state = workflow.generate_codex_goal_handoff(
                scope="Implement the frozen package",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )
            self.assertEqual(state["delivery_goal"]["status"], "active")
            self.assertEqual(state["status"], "implementation_goal_active")

    def test_launch_authorization_is_stale_when_task_queue_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = workflow_ready_for_launch(Path(tmp))
            workflow.record_implementation_launch_authorization(
                user_message="确认按当前交付包开始实现",
                scope="Implement the frozen package",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )

            with self.assertRaises(GatekeeperError) as caught:
                workflow.generate_codex_goal_handoff(
                    scope="Implement the frozen package",
                    verification_commands=["pytest"],
                    planned_tasks=planned_tasks(extra=True),
                )

            self.assertIn("implementation_launch_authorization", str(caught.exception))

    def test_role_simulation_review_requires_separate_user_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                feature_slug="v1.0.6-canonical-launch",
                allow_review_degradation=True,
            )
            workflow.record_scenario_matrix([scenario_row()])
            review = review_payload(
                "scenario",
                review_mode="role_simulation",
                role_simulation_user_accepted=True,
            )

            with self.assertRaises(ReviewGateError) as caught:
                workflow.record_multi_agent_review("scenario", review)

            self.assertIn("role_simulation", str(caught.exception))

            workflow.record_user_confirmation(
                user_confirmation(
                    "role_simulation_review_acceptance",
                    user_message="确认接受 role_simulation 弱证据",
                )
            )
            state = workflow.record_multi_agent_review("scenario", review)

            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["review_mode"],
                "role_simulation",
            )


if __name__ == "__main__":
    unittest.main()
