import unittest
import tempfile
from pathlib import Path

from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    build_planned_e2e_obligations,
)
from product_delivery_agent.review_gates import (
    ReviewGateError,
    validate_multi_agent_review,
)
from product_delivery_agent.ui_prototype import validate_ui_prototype_review
from product_delivery_agent.workflow import ProductDeliveryWorkflow
from tests.conformance_fixtures import prototype_contract, write_prototype_screenshot


def prototype_review_payload(**overrides):
    payload = {
        "prototype_contract": prototype_contract(),
        "prototype_path": "docs/prototypes/v1.4.4-confirmation.html",
        "pages": ["series detail course table"],
        "states": ["loading", "ready", "drawer-open", "error"],
        "journeys": [
            "series management -> series detail course table -> content status drawer",
        ],
        "taxonomy": {
            "roles": ["teaching operator"],
            "main_paths": [
                "open an existing standard course series and inspect course content status",
            ],
            "exceptions": ["status refresh fails"],
            "recovery": ["retry status refresh"],
            "permissions": ["teacher without series access cannot confirm"],
            "long_tasks": ["bulk status refresh"],
            "mobile": ["drawer keeps primary confirmation visible"],
            "keyboard": ["tab from course row into drawer confirmation controls"],
            "negative_scope_boundaries": ["does not introduce AI lesson generation"],
        },
        "limitations": ["static prototype data only"],
        "browser_e2e_candidates": ["confirm teachability from content status drawer"],
        "negative_scope_guard_candidates": ["AI lesson generation remains absent"],
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v1.4.3-standard-course-construction",
        "baseline_surface_paths": [
            "apps/web/src/v10Surfaces.tsx:V143StandardCourseConstructionPage",
            "apps/web/src/v12CourseOperations.tsx:V12CourseOperationsPage",
        ],
        "baseline_user_journey": (
            "系列管理 -> 系列详情课程表 -> 查看内容状态抽屉"
        ),
        "continuity_mapping": [
            "revision-004 keeps the V1.4.3 series detail course table as entry",
            "teachability confirmation is added inside the existing content status drawer",
        ],
        "prototype_delta_summary": [
            "adds confirmation controls to the existing drawer",
            "does not replace the main path with a standalone workbench",
        ],
    }
    payload.update(overrides)
    return payload


def scenario_review_payload(**overrides):
    payload = {
        "review_id": "MR-SCENARIO-V1014",
        "review_type": "scenario",
        "status": "passed",
        "reviewers": ["baseline reviewer", "scenario reviewer"],
        "artifact_version": "scenario-review-v1",
        "independent_positions": [
            "baseline reviewer traced the previous V1.4.3 entry path",
            "scenario reviewer found no missing user-visible exception",
        ],
        "cross_challenges": [
            "baseline reviewer challenged whether a new workbench replaced the drawer",
        ],
        "revisions": ["kept the prior series detail entry path"],
        "final_adjudication": "passed with no continuity blockers",
        "conclusions": ["scenario review passed"],
        "accepted_suggestions": ["add baseline entry path to E2E obligation"],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
        "baseline_inheritance_review": {
            "ui_change_type": "incremental_existing_surface",
            "baseline_feature_slug": "v1.4.3-standard-course-construction",
            "baseline_entry_path": (
                "系列管理 -> 系列详情课程表 -> 查看内容状态抽屉"
            ),
            "inherits_existing_surface": True,
            "parallel_surface_replacement": False,
        },
        "ui_continuity_findings": [],
    }
    payload.update(overrides)
    return payload


def planned_obligation(**overrides):
    payload = {
        "obligation_id": "OBL-V144-CONFIRMATION",
        "scenario_id": "SC-V144-001",
        "test_id": "TC-V144-001",
        "user_story": "US-V144-001",
        "journey": "confirm teachability from the existing content status drawer",
        "visible_exception": "course is not teachable",
        "test_layer": "browser_e2e",
        "semantic_assertions": [
            "operator enters through the existing V1.4.3 series detail course table",
            "operator confirms teachability in the content status drawer",
        ],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "coverage_items": ["teachable-confirmation"],
        "action_assertions": [
            {
                "item_id": "teachable-confirmation",
                "action_entry": "open content status drawer from series detail course table",
                "expected_real_surface": "existing V1.4.3 content status drawer",
                "assertion_target": "teachable confirmation control and persisted status",
                "semantic_depth": "user_journey",
            }
        ],
        "false_positive_guards": [
            "reject standalone workbench entry",
            "reject static-panel-only",
            "reject first-button-only",
        ],
        "baseline_entry_path": "系列管理 -> 系列详情课程表 -> 查看内容状态抽屉",
        "required_actor_roles": ["teaching operator"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "系列管理 -> 系列详情课程表 -> 查看内容状态抽屉",
        "data_state_contract": "existing V1.4.3 standard course series with course rows",
    }
    payload.update(overrides)
    return payload


class UIBaselineContinuityV1014Tests(unittest.TestCase):
    def test_incremental_existing_surface_requires_baseline_mapping(self):
        payload = prototype_review_payload(
            baseline_feature_slug="",
            continuity_mapping=[],
        )

        missing = validate_ui_prototype_review(payload)

        self.assertIn("baseline_feature_slug", missing)
        self.assertIn("continuity_mapping", missing)

    def test_parallel_workbench_prototype_fails_even_with_complete_basic_review(self):
        payload = prototype_review_payload(
            ui_change_type="incremental_existing_surface",
            baseline_user_journey="",
            continuity_mapping=[
                "prototype introduces a standalone teachability confirmation workbench",
            ],
            prototype_delta_summary=[
                "replaces the old series detail content status drawer path",
            ],
        )

        missing = validate_ui_prototype_review(payload)

        self.assertIn("baseline_user_journey", missing)
        self.assertIn("continuity_mapping:parallel_surface_replacement", missing)
        self.assertIn("prototype_delta_summary:parallel_surface_replacement", missing)

    def test_new_surface_requires_meaningful_justification_and_user_confirmation(self):
        payload = prototype_review_payload(
            ui_change_type="new_surface_in_existing_product",
            baseline_feature_slug="",
            baseline_surface_paths=[],
            baseline_user_journey="",
            continuity_mapping=[],
            prototype_delta_summary=[],
            new_surface_justification="new page",
            new_surface_user_confirmation=False,
        )

        missing = validate_ui_prototype_review(payload)

        self.assertIn("new_surface_justification", missing)
        self.assertIn("new_surface_user_confirmation", missing)

    def test_scenario_review_rejects_ui_continuity_findings(self):
        review = scenario_review_payload(
            ui_continuity_findings=[
                "prototype replaces previous content status drawer with a parallel workbench",
            ]
        )

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("scenario", review)

        self.assertIn("ui_continuity_findings", str(caught.exception))

    def test_scenario_review_requires_baseline_inheritance_for_incremental_ui(self):
        review = scenario_review_payload(baseline_inheritance_review={})

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("scenario", review)

        self.assertIn("baseline_inheritance_review", str(caught.exception))

    def test_ui_planned_e2e_requires_baseline_entry_path(self):
        obligation = planned_obligation(baseline_entry_path="")

        with self.assertRaises(CoverageAuditError) as caught:
            build_planned_e2e_obligations([obligation], project_type="ui")

        self.assertIn("baseline_entry_path", str(caught.exception))

    def test_valid_incremental_baseline_continuity_records_pass(self):
        self.assertEqual(validate_ui_prototype_review(prototype_review_payload()), [])
        validate_multi_agent_review("scenario", scenario_review_payload())

        planned = build_planned_e2e_obligations(
            [planned_obligation()],
            project_type="ui",
        )

        self.assertEqual(
            planned["obligations"][0]["baseline_entry_path"],
            "系列管理 -> 系列详情课程表 -> 查看内容状态抽屉",
        )

    def test_ui_prototype_feedback_stales_scenario_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype = project_root / "docs" / "prototypes" / "v144.html"
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text("<html>revision 003</html>", encoding="utf-8")
            write_prototype_screenshot(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(execution_mode="automatic",
                feature_slug="v1.4.4-standard-course-teachable-confirmation", multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            workflow.record_multi_agent_review("scenario", scenario_review_payload())

            state = workflow.record_ui_prototype_feedback(
                "不要另起工作台，必须沿用 V1.4.3 系列详情课程表和内容状态抽屉",
                "docs/prototypes/v144.html",
            )

            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["status"],
                "stale",
            )
            self.assertIn(
                "stale_multi_agent_scenario_review",
                state["blocked_until"],
            )


if __name__ == "__main__":
    unittest.main()
