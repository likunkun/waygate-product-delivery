import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import write_prototype_screenshot
from tests.test_feature_closure import (
    coverage_row,
    multi_agent_review,
    planned_obligation,
    scenario_row,
    ui_review_payload,
)
from tests.test_non_ui_behavior_contract import complete_contract_payload


def scenario_review():
    review = multi_agent_review("scenario")
    review.update(
        {
            "baseline_inheritance_review": {
                "ui_change_type": "incremental_existing_surface",
                "baseline_feature_slug": "v0-existing-classroom",
                "baseline_entry_path": (
                    "teacher opens the existing classroom dashboard"
                ),
                "inherits_existing_surface": True,
                "parallel_surface_replacement": False,
            },
            "ui_continuity_findings": [],
        }
    )
    return review


def non_ui_scenario_review():
    return multi_agent_review("scenario")


def write_ui_draft(project_root: Path) -> None:
    prototype = project_root / "prototype" / "index.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>draft surface</html>", encoding="utf-8")
    write_prototype_screenshot(project_root)


def start_ui_workflow(project_root: Path) -> ProductDeliveryWorkflow:
    write_ui_draft(project_root)
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(
        
        feature_slug="v1.0.21-layered-confirmation",
        multi_agent_mode="spawned_subagents_authorized",
    )
    workflow.select_project_type("ui")
    workflow.record_scenario_matrix([scenario_row()])
    workflow.record_ui_prototype_review(ui_review_payload())
    return workflow


def confirm_product_baseline(workflow: ProductDeliveryWorkflow) -> dict:
    workflow.record_multi_agent_review("scenario", scenario_review())
    state = workflow.prepare_product_baseline_confirmation()
    pending = state["pending_confirmations"]["product_baseline"]
    return workflow.confirm_product_baseline(
        "确认需求范围和最终原型",
        pending["nonce"],
    )


def record_test_plan(workflow: ProductDeliveryWorkflow) -> dict:
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["student billing is absent"],
    )
    workflow.record_multi_agent_review(
        "test_coverage", multi_agent_review("test_coverage")
    )
    workflow.record_multi_agent_review("test", multi_agent_review("test"))
    return workflow.prepare_test_coverage_confirmation()


def obligation_with(**overrides):
    obligation = planned_obligation()
    obligation.update(overrides)
    return obligation


class LayeredConfirmationV1021Tests(unittest.TestCase):
    def test_ui_draft_does_not_request_user_confirmation_before_scenario_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = start_ui_workflow(Path(tmp)).status()

            self.assertNotIn("product_baseline", state["pending_confirmations"])
            self.assertNotIn("ui_prototype", state["pending_confirmations"])
            self.assertEqual(state["next_gate"], "multi_agent_scenario_review")

    def test_product_baseline_confirmation_binds_scope_and_ui_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))

            with self.assertRaises(WorkflowError):
                workflow.prepare_product_baseline_confirmation()

            state = confirm_product_baseline(workflow)

            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertTrue(state["ui_prototype"]["confirmed_by_user"])
            self.assertIn("product_baseline", state["user_confirmations"])
            self.assertNotIn("planned_e2e_obligations", state["user_confirmations"])
            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["status"], "passed"
            )
            self.assertEqual(state["next_gate"], "planned_e2e_obligations")

    def test_test_planning_is_blocked_until_product_baseline_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            workflow.record_multi_agent_review("scenario", scenario_review())

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_planned_e2e_obligations([planned_obligation()])

            self.assertIn("product baseline confirmation", str(caught.exception))

    def test_test_coverage_confirmation_only_accepts_test_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            confirm_product_baseline(workflow)
            state = record_test_plan(workflow)
            pending = state["pending_confirmations"]["test_coverage_plan"]

            state = workflow.confirm_test_coverage_plan(
                "确认 planned E2E 和测试覆盖计划",
                pending["nonce"],
            )

            self.assertTrue(state["planned_e2e_obligations"]["accepted_by_user"])
            self.assertIn("test_coverage_plan", state["user_confirmations"])
            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertTrue(state["ui_prototype"]["confirmed_by_user"])
            self.assertEqual(state["next_gate"], "implementation_launch_authorization")

    def test_confirmed_product_baseline_rejects_internal_surface_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = start_ui_workflow(project_root)
            confirm_product_baseline(workflow)
            prototype = project_root / "prototype" / "index.html"
            prototype.write_text("<html>internal rewrite</html>", encoding="utf-8")

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_ui_prototype_review(ui_review_payload())

            self.assertIn("user change authorization", str(caught.exception))

    def test_user_feedback_allows_product_revision_and_invalidates_test_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = start_ui_workflow(project_root)
            confirm_product_baseline(workflow)
            record_test_plan(workflow)
            prototype = project_root / "prototype" / "index.html"
            workflow.record_ui_prototype_feedback(
                "原型需要调整课程入口",
                "prototype/index.html",
            )
            prototype.write_text("<html>user requested revision</html>", encoding="utf-8")

            state = workflow.record_ui_prototype_review(ui_review_payload())

            self.assertNotIn("product_baseline", state["user_confirmations"])
            self.assertNotIn("test_coverage_plan", state["user_confirmations"])
            self.assertNotIn("product_baseline", state["pending_confirmations"])
            self.assertEqual(state["next_gate"], "multi_agent_scenario_review")

    def test_non_ui_product_baseline_requires_hash_bound_user_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                
                feature_slug="v1.0.21-non-ui-confirmation",
                multi_agent_mode="spawned_subagents_authorized",
            )
            workflow.select_project_type("non_ui")
            workflow.record_scenario_matrix([scenario_row()])
            workflow.record_non_ui_behavior_contract(complete_contract_payload())
            workflow.record_multi_agent_review("scenario", non_ui_scenario_review())

            state = workflow.prepare_product_baseline_confirmation()
            pending = state["pending_confirmations"]["product_baseline"]
            state = workflow.confirm_product_baseline(
                "确认需求范围和非 UI 行为契约",
                pending["nonce"],
            )

            self.assertIn("product_baseline", state["user_confirmations"])
            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertTrue(
                state["non_ui_behavior_contract"]["confirmed_by_user"]
            )

    def test_legacy_separate_user_confirmation_is_rejected_for_modern_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            workflow.record_multi_agent_review("scenario", scenario_review())

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_user_confirmation(
                    {
                        "confirmation_id": "CONF-open_spec_freeze",
                        "target": "open_spec_freeze",
                        "artifact_path": ".product-delivery/artifacts/open-spec.md",
                        "artifact_version": "v1",
                        "confirmed_by": "user",
                        "confirmation_source": "chat_user_reply",
                        "confirmed_at": "2026-07-14T00:00:00+00:00",
                        "decision": "approved",
                        "user_message": "确认",
                    }
                )

            self.assertIn("confirm_product_baseline", str(caught.exception))

    def test_internal_test_split_preserves_user_test_coverage_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            confirm_product_baseline(workflow)
            state = record_test_plan(workflow)
            pending = state["pending_confirmations"]["test_coverage_plan"]
            workflow.confirm_test_coverage_plan(
                "确认 planned E2E 和测试覆盖计划",
                pending["nonce"],
            )

            state = workflow.record_planned_e2e_obligations(
                [
                    obligation_with(
                        test_id="TC-V008-001A",
                        semantic_assertions=[
                            "teacher creates classroom",
                            "duplicate name error is visible",
                            "form remains keyboard reachable",
                        ],
                    ),
                    obligation_with(
                        obligation_id="OBL-002",
                        test_id="TC-V008-001B",
                        semantic_assertions=[
                            "teacher creates classroom",
                            "duplicate name error is visible",
                        ],
                    ),
                ]
            )

            self.assertIn("product_baseline", state["user_confirmations"])
            self.assertIn("test_coverage_plan", state["user_confirmations"])
            self.assertTrue(state["planned_e2e_obligations"]["accepted_by_user"])
            self.assertNotIn(
                "test_coverage_plan_user_confirmation", state["blocked_until"]
            )
            self.assertNotIn(
                "planned_e2e_user_confirmation", state["blocked_until"]
            )
            self.assertEqual(
                state["multi_agent_reviews"]["test_coverage"]["status"],
                "stale",
            )

    def test_actor_or_path_coverage_change_invalidates_only_test_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            confirm_product_baseline(workflow)
            state = record_test_plan(workflow)
            pending = state["pending_confirmations"]["test_coverage_plan"]
            workflow.confirm_test_coverage_plan(
                "确认 planned E2E 和测试覆盖计划",
                pending["nonce"],
            )

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_planned_e2e_obligations(
                    [obligation_with(required_actor_roles=["admin"])]
                )

            self.assertIn("user change authorization", str(caught.exception))
            workflow.record_user_requested_change(
                targets=["test_coverage_plan"],
                user_message="把主路径验收角色改为管理员",
            )
            state = workflow.record_planned_e2e_obligations(
                [obligation_with(required_actor_roles=["admin"])]
            )

            self.assertIn("product_baseline", state["user_confirmations"])
            self.assertNotIn("test_coverage_plan", state["user_confirmations"])
            self.assertTrue(state["open_spec_freeze"]["approved_by_user"])
            self.assertIn(
                "test_coverage_plan_user_confirmation", state["blocked_until"]
            )
            self.assertNotIn(
                "product_baseline_user_confirmation", state["blocked_until"]
            )

    def test_post_freeze_change_requires_explicit_user_change_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = start_ui_workflow(Path(tmp))
            confirm_product_baseline(workflow)
            state = record_test_plan(workflow)
            pending = state["pending_confirmations"]["test_coverage_plan"]
            workflow.confirm_test_coverage_plan(
                "确认 planned E2E 和测试覆盖计划",
                pending["nonce"],
            )

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_post_freeze_change(
                    change_type="test_gap",
                    description="add a new permission-denial coverage obligation",
                    cr_id="CR-TEST-001",
                )

            self.assertIn("user change authorization", str(caught.exception))
            workflow.record_user_requested_change(
                targets=["test_coverage_plan"],
                user_message="增加权限拒绝路径的覆盖要求",
            )
            state = workflow.record_post_freeze_change(
                change_type="test_gap",
                description="add a new permission-denial coverage obligation",
                cr_id="CR-TEST-001",
            )

            self.assertIn("product_baseline", state["user_confirmations"])
            self.assertNotIn("test_coverage_plan", state["user_confirmations"])
            self.assertEqual(state["next_gate"], "planned_e2e_obligations")

    def test_legacy_active_ui_pending_confirmation_returns_to_product_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workspace = project_root / ARTIFACT_ROOT
            workspace.mkdir(parents=True)
            legacy = {
                "active": True,
                "status": "active",
                "stage": "ui_prototype_confirmation",
                "next_gate": "ui_prototype_user_confirmation",
                "feature_slug": "v1.0.20-active-feature",
                "project_type": "ui",
                "pending_confirmations": {
                    "ui_prototype": {
                        "nonce": "legacy-ui-nonce",
                        "artifact_hash": "a" * 64,
                    }
                },
                "ui_prototype": {
                    "generated": True,
                    "reviewed_by_agent": True,
                    "confirmed_by_user": False,
                },
                "multi_agent_reviews": {
                    "scenario": {"status": "missing", "artifact": None}
                },
                "multi_agent_policy": {
                    "mode": "spawned_subagents_authorized",
                    "execution_authorization": "authorized",
                    "authorization_scope": "current_delivery",
                    "authorization_source": "explicit_start_phrase",
                    "authorized_review_types": ["scenario"],
                },
                "execution_model_policy": {
                    "mode": "automatic",
                    "authorization_status": "authorized",
                    "execution_verification_status": "verified_stage_agent",
                },
            }
            (workspace / "state.json").write_text(
                json.dumps(legacy), encoding="utf-8"
            )

            state = load_state(project_root)

            self.assertNotIn("ui_prototype", state["pending_confirmations"])
            self.assertEqual(state["next_gate"], "multi_agent_scenario_review")
            self.assertEqual(
                state["confirmation_readiness"]["product_baseline"],
                "blocked_on_scenario_review",
            )
            self.assertEqual(
                state["legacy_pending_confirmations"][-1]["target"],
                "ui_prototype",
            )

    def test_terminal_history_keeps_legacy_confirmation_record_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workspace = project_root / ARTIFACT_ROOT
            workspace.mkdir(parents=True)
            legacy = {
                "active": False,
                "status": "closed",
                "project_type": "ui",
                "pending_confirmations": {
                    "ui_prototype": {"nonce": "historical-nonce"}
                },
            }
            (workspace / "state.json").write_text(
                json.dumps(legacy), encoding="utf-8"
            )

            state = load_state(project_root)

            self.assertEqual(
                state["pending_confirmations"]["ui_prototype"]["nonce"],
                "historical-nonce",
            )
            self.assertNotIn("legacy_pending_confirmations", state)


if __name__ == "__main__":
    unittest.main()
