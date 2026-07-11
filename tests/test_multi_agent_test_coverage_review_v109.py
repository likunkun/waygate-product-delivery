import unittest

from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    build_planned_e2e_obligations,
)
from product_delivery_agent.gatekeeper import (
    GatekeeperError,
    assert_pre_closure_ready,
    derive_blockers,
)
from product_delivery_agent.review_gates import (
    ReviewGateError,
    validate_multi_agent_review,
)


WORKBENCH_ITEMS = [
    "people-maintenance",
    "templates",
    "agent-rules",
    "model-permissions",
    "key-binding",
    "sensitive-key-actions",
    "provider-capacity",
    "login-source-handling",
    "alert-ignore-rules",
    "whitelist",
    "team-config",
]


def review_payload(review_type, **overrides):
    payload = {
        "review_id": f"MR-{review_type.upper()}-001",
        "review_type": review_type,
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["qa-coverage-agent", "ui-path-agent", "e2e-agent"],
        "artifact_version": f"{review_type}-review-v1",
        "independent_positions": [
            "QA: US/J/SC/AC/TASK/TC mappings are complete",
            "UI: every collection item has a concrete action path",
            "E2E: each planned TC has executable assertions",
        ],
        "cross_challenges": [
            "UI challenged title-only TC coverage; QA added item-level checks",
        ],
        "revisions": ["Expanded workbench coverage into per-item assertions"],
        "final_adjudication": "passed with no blocking findings",
        "conclusions": [f"{review_type} review passed"],
        "accepted_suggestions": ["reject marker-only coverage"],
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
                "collection_id": "second-level-workbench-tabs",
                "required_items": WORKBENCH_ITEMS,
                "covered_items": WORKBENCH_ITEMS,
                "item_level_assertions": {
                    item: f"click {item} and assert real functional panel"
                    for item in WORKBENCH_ITEMS
                },
            }
        ],
        "role_journey_coverage": [
            {
                "test_id": "TC-V28-017",
                "required_actor_roles": ["operator"],
                "journey": (
                    "Operator opens every second-level workbench tab and reaches real "
                    "tertiary panels"
                ),
            }
        ],
        "ordinary_path_coverage": [
            {
                "test_id": "TC-V28-017",
                "ordinary_entry_path": "operator opens the existing workbench surface",
            }
        ],
        "scenario_granularity_findings": [],
        "actual_test_code_paths": [
            "internal/usagereport/web/testdata/v2_8/v28_scenario_ui_mobile_raw_playwright.py",
        ],
        "execution_evidence_paths": [
            ".product-delivery/artifacts/v2.8-verification/v28-scenario-ui-mobile-raw-e2e.json",
        ],
        "reviewed_test_ids": ["TC-V28-017", "TC-V28-018"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V28-017",
                "item_id": item,
                "clicked_entry": f"[data-workbench-tab='{item}']",
                "expected_real_surface": f"{item} functional panel",
                "assertion_target": "save button or live interaction control",
                "evidence_path": ".product-delivery/artifacts/v2.8-verification/v28-scenario-ui-mobile-raw-e2e.json",
            }
            for item in WORKBENCH_ITEMS
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


def planned_workbench_obligation(**overrides):
    payload = {
        "obligation_id": "OBL-V28-WORKBENCH",
        "scenario_id": "SCN-V28-TERTIARY-PANELS",
        "test_id": "TC-V28-017",
        "user_story": "US-V28-014",
        "journey": (
            "Operator opens every second-level workbench tab and reaches real "
            "tertiary panels"
        ),
        "visible_exception": "missing tab or static-only panel",
        "test_layer": "browser_e2e",
        "semantic_assertions": [
            "every workbench action opens a real functional panel",
        ],
        "expected_artifact_pattern": ".product-delivery/artifacts/v2.8-verification/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "operator opens the existing workbench surface",
        "required_actor_roles": ["operator"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "operator opens the existing workbench surface",
        "data_state_contract": "existing operator account with every workbench tab enabled",
        "coverage_items": WORKBENCH_ITEMS,
        "action_assertions": [
            {
                "item_id": item,
                "action_entry": f"click {item} tab",
                "expected_real_surface": f"{item} functional panel",
                "assertion_target": "save button or live interaction control",
                "semantic_depth": "real_surface",
            }
            for item in WORKBENCH_ITEMS
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


def pre_handoff_state_with_old_test_review():
    return {
        "feature_slug": "v1.0.9-test-coverage-review",
        "project_type": "ui",
        "open_spec_draft_ready": True,
        "scenario_matrix_draft_ready": True,
        "scenario_matrix": {"draft_ready": True},
        "multi_agent_reviews": {
            "scenario": {"status": "passed"},
            "test": {"status": "passed"},
        },
        "open_spec_freeze": {"approved_by_user": True},
        "user_confirmations": {
            "open_spec_freeze": {"decision": "approved"},
            "planned_e2e_obligations": {"decision": "approved"},
            "ui_prototype": {
                "artifact_hash": "a" * 64,
                "prototype_revision": "r1",
            },
        },
        "pending_confirmations": {},
        "ui_prototype": {
            "generated": True,
            "reviewed_by_agent": True,
            "confirmed_by_user": True,
            "artifact_hash": "a" * 64,
            "prototype_revision": "r1",
        },
        "planned_e2e_obligations": {
            "accepted": True,
            "accepted_by_user": True,
            "obligations": [planned_workbench_obligation()],
            "exemptions": [],
        },
        "test_coverage_audit": {"passed": True},
        "implementation_launch_authorization": {
            "status": "authorized",
            "launch_package_hash": "launch-hash",
        },
    }


def pre_closure_state_without_implementation_review():
    obligation = planned_workbench_obligation()
    return {
        "feature_slug": "v1.0.9-test-coverage-review",
        "project_type": "ui",
        "handoff": {"status": "generated"},
        "delivery_goal": {"status": "active"},
        "multi_agent_reviews": {
            "scenario": {"status": "passed"},
            "test": {"status": "passed"},
            "test_coverage": {"status": "passed"},
        },
        "test_coverage_audit": {"passed": True},
        "planned_e2e_obligations": {
            "accepted": True,
            "accepted_by_user": True,
            "obligations": [obligation],
            "exemptions": [],
        },
        "executed_browser_evidence": {
            "status": "passed",
            "records": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "test_id": obligation["test_id"],
                    "scenario_id": obligation["scenario_id"],
                    "user_story": obligation["user_story"],
                    "journey": obligation["journey"],
                    "evidence_path": ".product-delivery/artifacts/e2e.json",
                }
            ],
        },
    }


def closure_artifact():
    return {
        "e2e_covered_tc": ["TC-V28-017"],
        "covered_user_stories": ["US-V28-014"],
        "covered_journeys": [
            "Operator opens every second-level workbench tab and reaches real tertiary panels",
        ],
        "e2e_evidence_paths": [".product-delivery/artifacts/e2e.json"],
    }


class MultiAgentTestCoverageReviewV109Tests(unittest.TestCase):
    def test_test_coverage_review_type_accepts_item_level_mapping(self):
        validate_multi_agent_review(
            "test_coverage",
            review_payload("test_coverage"),
        )

    def test_missing_test_coverage_review_blocks_pre_handoff_even_if_old_test_review_passed(self):
        blockers = derive_blockers(
            pre_handoff_state_with_old_test_review(),
            launch_package_hash="launch-hash",
        )

        self.assertIn("multi_agent_test_coverage_review", blockers)

    def test_collection_coverage_requires_action_assertion_for_every_declared_item(self):
        shallow = planned_workbench_obligation(
            action_assertions=[
                {
                    "item_id": "people-maintenance",
                    "action_entry": "click people-maintenance tab",
                    "expected_real_surface": "people maintenance panel",
                    "assertion_target": "save button or live interaction control",
                    "semantic_depth": "real_surface",
                }
            ]
        )

        with self.assertRaises(CoverageAuditError) as caught:
            build_planned_e2e_obligations([shallow])

        self.assertIn("missing action assertions", str(caught.exception))
        self.assertIn("templates", str(caught.exception))

    def test_marker_only_or_first_button_only_action_assertions_are_false_positive_risks(self):
        marker_only = planned_workbench_obligation(
            coverage_items=["people-maintenance"],
            action_assertions=[
                {
                    "item_id": "people-maintenance",
                    "action_entry": "click first visible button",
                    "expected_real_surface": "static explanation panel",
                    "assertion_target": "data-v28-workbench marker exists",
                    "semantic_depth": "marker_only",
                }
            ],
        )

        with self.assertRaises(CoverageAuditError) as caught:
            build_planned_e2e_obligations([marker_only])

        self.assertIn("false-positive", str(caught.exception))

    def test_missing_test_implementation_review_blocks_closure(self):
        with self.assertRaises(GatekeeperError) as caught:
            assert_pre_closure_ready(
                pre_closure_state_without_implementation_review(),
                closure_artifact(),
            )

        self.assertIn("multi_agent_test_implementation_review", str(caught.exception))

    def test_test_implementation_review_must_reference_real_test_code_and_evidence(self):
        plan_only = review_payload(
            "test_implementation",
            actual_test_code_paths=[],
            execution_evidence_paths=[],
            verified_action_assertions=[],
        )

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("test_implementation", plan_only)

        self.assertIn("actual_test_code_paths", str(caught.exception))

    def test_valid_test_implementation_review_passes(self):
        validate_multi_agent_review(
            "test_implementation",
            review_payload("test_implementation"),
        )


if __name__ == "__main__":
    unittest.main()
