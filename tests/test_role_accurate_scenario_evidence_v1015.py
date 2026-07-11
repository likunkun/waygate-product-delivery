import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    build_executed_browser_evidence,
    build_planned_e2e_obligations,
)
from product_delivery_agent.gatekeeper import (
    GatekeeperError,
    assert_pre_closure_ready,
    review_input_hash,
)
from product_delivery_agent.review_gates import (
    ReviewGateError,
    validate_multi_agent_review,
)


def planned_obligation(**overrides):
    payload = {
        "obligation_id": "OBL-V144-TEACHER-HAPPY",
        "scenario_id": "SC-V144-TEACHER-HAPPY",
        "test_id": "TC-V144-008",
        "user_story": "US-V144-003",
        "journey": "Teacher marks an assembled course row teachable through the series detail drawer",
        "visible_exception": "blocked row cannot be confirmed",
        "test_layer": "browser_e2e",
        "semantic_assertions": ["teacher submit and readback are visible in browser"],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "/customer/course-production/standard-courses -> series detail",
        "required_actor_roles": ["teacher"],
        "path_kind": "primary_happy_path",
        "ordinary_entry_path": "/customer/course-production/standard-courses -> series detail -> content drawer",
        "data_state_contract": "existing assembled standard-course row owned by the teacher",
        "coverage_items": ["submit-teachable", "refresh-readback"],
        "action_assertions": [
            {
                "item_id": "submit-teachable",
                "action_entry": "teacher clicks mark teachable",
                "expected_real_surface": "content status drawer",
                "assertion_target": "teachable state is saved and visible",
                "semantic_depth": "user_journey",
            },
            {
                "item_id": "refresh-readback",
                "action_entry": "teacher refreshes and reopens the series",
                "expected_real_surface": "series detail course table",
                "assertion_target": "teachable status is still visible",
                "semantic_depth": "user_journey",
            },
        ],
        "false_positive_guards": [
            "reject admin-only closure for teacher story",
            "reject annotation-only coverage",
        ],
    }
    payload.update(overrides)
    return payload


def old_planned_obligation_without_role_fields():
    payload = planned_obligation()
    for key in (
        "required_actor_roles",
        "path_kind",
        "ordinary_entry_path",
        "data_state_contract",
    ):
        payload.pop(key)
    return payload


def write_evidence_files(project_root: Path) -> None:
    evidence_path = project_root / ".product-delivery" / "artifacts" / "e2e" / "teacher.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"status":"passed"}\n', encoding="utf-8")
    probe_path = project_root / ".product-delivery" / "artifacts" / "e2e" / "teacher-probe.json"
    probe_path.write_text(
        json.dumps(
            {
                "acceptance_url": "http://127.0.0.1:15082/customer/course-production",
                "api_health_url": "http://127.0.0.1:15082/api/health",
                "api_health_identity": "classroom-api",
                "health_response_content_type": "application/json",
                "health_response_body_sample": '{"service":"classroom-api"}',
                "business_api_requests": [
                    {
                        "method": "POST",
                        "url": "http://127.0.0.1:15082/api/course-operations/standard-courses/sc-1/courses/m-1/teachable-confirmation",
                        "status": 200,
                        "source": "network",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def browser_record(**overrides):
    payload = {
        "test_id": "TC-V144-008",
        "obligation_id": "OBL-V144-TEACHER-HAPPY",
        "command": "npx playwright test apps/web/e2e/v144.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["teacher submit and readback are visible in browser"],
        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
        "evidence_strength": "full_stack_browser_e2e",
        "acceptance_url": "http://127.0.0.1:15082/customer/course-production",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "classroom-api",
        "network_probe_summary": {"business_api_request_count": 1},
        "mocked_routes": [],
        "probe_artifact_path": ".product-delivery/artifacts/e2e/teacher-probe.json",
        "executed_actor_roles": ["teacher"],
        "primary_actor_role": "teacher",
        "actor_identity_evidence": {"role": "teacher", "user_id": "teacher-1"},
        "ordinary_path_observed": True,
        "execution_segment_id": "teacher-submit-teachable",
        "test_title_or_step": "teacher submits teachable from content drawer",
    }
    payload.update(overrides)
    return payload


def closure_artifact():
    return {
        "e2e_covered_tc": ["TC-V144-008"],
        "covered_user_stories": ["US-V144-003"],
        "covered_journeys": [
            "Teacher marks an assembled course row teachable through the series detail drawer",
        ],
        "e2e_evidence_paths": [".product-delivery/artifacts/e2e/teacher.json"],
    }


def review_payload(**overrides):
    payload = {
        "review_id": "REV-V1015-TEST-IMPLEMENTATION",
        "review_type": "test_implementation",
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["role-reviewer", "evidence-reviewer"],
        "artifact_version": "role-accurate-v1",
        "independent_positions": ["role journey evidence is complete"],
        "cross_challenges": ["challenged admin-only closure"],
        "revisions": ["added teacher browser evidence"],
        "final_adjudication": "passed",
        "conclusions": ["test implementation passed"],
        "accepted_suggestions": ["keep role-accurate evidence"],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
        "actual_test_code_paths": ["apps/web/e2e/v144.spec.ts"],
        "execution_evidence_paths": [".product-delivery/artifacts/e2e/teacher.json"],
        "reviewed_test_ids": ["TC-V144-008"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V144-008",
                "item_id": "submit-teachable",
                "clicked_entry": "teacher clicks mark teachable",
                "expected_real_surface": "content status drawer",
                "assertion_target": "teachable state is saved and visible",
                "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
            }
        ],
        "false_positive_risks": [],
        "supporting_evidence_only": [],
        "business_api_mock_findings": [],
        "actor_role_findings": [],
        "evidence_distribution_findings": [],
        "annotation_only_findings": [],
        "ordinary_path_findings": [],
    }
    payload.update(overrides)
    return payload


class RoleAccurateScenarioEvidenceV1015Tests(unittest.TestCase):
    def test_ui_planned_obligation_requires_role_path_and_data_contract(self):
        with self.assertRaises(CoverageAuditError) as caught:
            build_planned_e2e_obligations([old_planned_obligation_without_role_fields()])

        self.assertIn("required_actor_roles", str(caught.exception))
        self.assertIn("ordinary_entry_path", str(caught.exception))

    def test_teacher_planned_obligation_rejects_admin_only_executed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_evidence_files(project_root)

            with self.assertRaises(CoverageAuditError) as caught:
                build_executed_browser_evidence(
                    project_root,
                    [
                        browser_record(
                            executed_actor_roles=["admin"],
                            primary_actor_role="admin",
                            actor_identity_evidence={"role": "admin", "user_id": "admin-1"},
                        )
                    ],
                    planned_obligations=[planned_obligation()],
                )

            self.assertIn("actor role", str(caught.exception))
            self.assertIn("teacher", str(caught.exception))

    def test_pre_closure_rejects_old_browser_evidence_without_actor_path_segment(self):
        obligation = planned_obligation()
        state = {
            "feature_slug": "v1.0.15-role-accurate-scenario-evidence",
            "project_type": "ui",
            "handoff": {"status": "generated"},
            "delivery_goal": {"status": "active"},
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
                        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
                        "evidence_strength": "full_stack_browser_e2e",
                    }
                ],
            },
            "multi_agent_reviews": {},
        }
        state["multi_agent_reviews"]["test_implementation"] = {
            "status": "passed",
            "input_snapshot_hash": review_input_hash(state, "test_implementation"),
        }

        with self.assertRaises(GatekeeperError) as caught:
            assert_pre_closure_ready(state, closure_artifact())

        self.assertIn("actor", str(caught.exception))

    def test_test_implementation_review_must_verify_every_planned_action_item(self):
        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review(
                "test_implementation",
                review_payload(),
                planned_obligations=[planned_obligation()],
                executed_records=[browser_record()],
            )

        self.assertIn("verified_action_assertions", str(caught.exception))
        self.assertIn("refresh-readback", str(caught.exception))

    def test_role_journey_review_normalizes_actor_role_case(self):
        validate_multi_agent_review(
            "test_coverage",
            {
                "review_id": "REV-V1015-COVERAGE",
                "review_type": "test_coverage",
                "status": "passed",
                "review_mode": "spawned_subagents",
                "reviewers": ["coverage-reviewer", "role-reviewer"],
                "artifact_version": "role-coverage-v1",
                "independent_positions": ["all TC role journeys are reviewed"],
                "cross_challenges": ["role reviewer challenged Teacher casing"],
                "revisions": ["normalized role naming"],
                "final_adjudication": "passed",
                "conclusions": ["test coverage passed"],
                "accepted_suggestions": ["keep role-accurate coverage"],
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
                        "collection_id": "teacher-path",
                        "required_items": ["submit-teachable", "refresh-readback"],
                        "covered_items": ["submit-teachable", "refresh-readback"],
                        "item_level_assertions": {
                            "submit-teachable": "submit and assert saved teachable state",
                            "refresh-readback": "refresh and assert teachable readback",
                        },
                    }
                ],
                "role_journey_coverage": [
                    {
                        "test_id": "TC-V144-008",
                        "required_actor_roles": ["teacher"],
                        "journey": "Teacher marks teachable",
                    }
                ],
                "ordinary_path_coverage": [
                    {
                        "test_id": "TC-V144-008",
                        "ordinary_entry_path": planned_obligation()["ordinary_entry_path"],
                    }
                ],
                "scenario_granularity_findings": [],
            },
            planned_obligations=[
                planned_obligation(required_actor_roles=["Teacher"]),
            ],
        )

    def test_role_accurate_teacher_admin_and_denial_segments_pass(self):
        admin = planned_obligation(
            obligation_id="OBL-V144-ADMIN-SUMMARY",
            scenario_id="SC-V144-ADMIN-SUMMARY",
            test_id="TC-V144-011",
            user_story="US-V144-005",
            journey="Admin reviews confirmation summary",
            required_actor_roles=["admin"],
            path_kind="primary_happy_path",
            coverage_items=["admin-summary"],
            action_assertions=[
                {
                    "item_id": "admin-summary",
                    "action_entry": "admin opens summary",
                    "expected_real_surface": "series detail summary",
                    "assertion_target": "summary counts and updated time are visible",
                    "semantic_depth": "user_journey",
                }
            ],
        )
        denial = planned_obligation(
            obligation_id="OBL-V144-STUDENT-DENIAL",
            scenario_id="SC-V144-STUDENT-DENIAL",
            test_id="TC-V144-016",
            user_story="US-V144-008",
            journey="Student direct access receives denial",
            required_actor_roles=["student"],
            path_kind="permission_denial",
            coverage_items=["student-denied"],
            action_assertions=[
                {
                    "item_id": "student-denied",
                    "action_entry": "student opens direct confirmation URL",
                    "expected_real_surface": "business denial view",
                    "assertion_target": "form and teacher-only content are absent",
                    "semantic_depth": "user_journey",
                }
            ],
        )
        planned = [planned_obligation(), admin, denial]
        records = [
            browser_record(),
            browser_record(
                obligation_id=admin["obligation_id"],
                test_id=admin["test_id"],
                executed_actor_roles=["admin"],
                primary_actor_role="admin",
                actor_identity_evidence={"role": "admin", "user_id": "admin-1"},
                execution_segment_id="admin-summary",
                test_title_or_step="admin reviews confirmation summary",
            ),
            browser_record(
                obligation_id=denial["obligation_id"],
                test_id=denial["test_id"],
                executed_actor_roles=["student"],
                primary_actor_role="student",
                actor_identity_evidence={"role": "student", "user_id": "student-1"},
                execution_segment_id="student-denial",
                test_title_or_step="student direct URL is denied",
            ),
        ]

        build_planned_e2e_obligations(planned)
        validate_multi_agent_review(
            "test_implementation",
            review_payload(
                reviewed_test_ids=["TC-V144-008", "TC-V144-011", "TC-V144-016"],
                verified_action_assertions=[
                    {
                        "test_id": "TC-V144-008",
                        "item_id": "submit-teachable",
                        "clicked_entry": "teacher clicks mark teachable",
                        "expected_real_surface": "content status drawer",
                        "assertion_target": "teachable state is saved and visible",
                        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
                    },
                    {
                        "test_id": "TC-V144-008",
                        "item_id": "refresh-readback",
                        "clicked_entry": "teacher refreshes and reopens the series",
                        "expected_real_surface": "series detail course table",
                        "assertion_target": "teachable status is still visible",
                        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
                    },
                    {
                        "test_id": "TC-V144-011",
                        "item_id": "admin-summary",
                        "clicked_entry": "admin opens summary",
                        "expected_real_surface": "series detail summary",
                        "assertion_target": "summary counts and updated time are visible",
                        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
                    },
                    {
                        "test_id": "TC-V144-016",
                        "item_id": "student-denied",
                        "clicked_entry": "student opens direct confirmation URL",
                        "expected_real_surface": "business denial view",
                        "assertion_target": "form and teacher-only content are absent",
                        "evidence_path": ".product-delivery/artifacts/e2e/teacher.json",
                    },
                ],
            ),
            planned_obligations=planned,
            executed_records=records,
        )


if __name__ == "__main__":
    unittest.main()
