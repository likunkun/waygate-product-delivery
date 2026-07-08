import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.coverage_audit import (
    CoverageAuditError,
    build_executed_browser_evidence,
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


def planned_obligation():
    return {
        "obligation_id": "OBL-001",
        "scenario_id": "SC-001",
        "test_id": "TC-V008-001",
        "user_story": "US-001",
        "journey": "Teacher creates a classroom through the real web surface",
        "visible_exception": "duplicate classroom name",
        "test_layer": "browser_e2e",
        "semantic_assertions": ["classroom is created through the browser"],
        "expected_artifact_pattern": ".product-delivery/artifacts/e2e/*.json",
        "exemption_status": "none",
        "baseline_entry_path": "teacher opens the existing classroom dashboard",
    }


def closure_artifact():
    return {
        "e2e_covered_tc": ["TC-V008-001"],
        "covered_user_stories": ["US-001"],
        "covered_journeys": [
            "Teacher creates a classroom through the real web surface",
        ],
        "e2e_evidence_paths": [".product-delivery/artifacts/e2e/tc-v008-001.json"],
    }


def write_evidence_files(project_root: Path, *, html_health: bool = False) -> None:
    evidence_path = project_root / ".product-delivery" / "artifacts" / "e2e" / "tc-v008-001.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"status":"passed"}\n', encoding="utf-8")
    probe_path = project_root / ".product-delivery" / "artifacts" / "e2e" / "tc-v008-001-probe.json"
    probe = {
        "acceptance_url": "http://127.0.0.1:15082/customer/course-production",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "classroom-api",
        "health_response_content_type": "application/json",
        "health_response_body_sample": '{"service":"classroom-api"}',
        "business_api_requests": [
            {
                "method": "GET",
                "url": "http://127.0.0.1:15082/api/course-operations/standard-courses",
                "status": 200,
                "source": "network",
            }
        ],
    }
    if html_health:
        probe["health_response_content_type"] = "text/html"
        probe["health_response_body_sample"] = "<html><div id=\"root\"></div></html>"
    probe_path.write_text(json.dumps(probe), encoding="utf-8")


def full_stack_record(**overrides):
    record = {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "npx playwright test e2e/classroom.spec.ts",
        "exit_code": 0,
        "trace_path": ".product-delivery/artifacts/e2e/trace.zip",
        "screenshot_path": ".product-delivery/artifacts/e2e/screenshot.png",
        "console_errors": [],
        "network_errors": [],
        "semantic_assertions": ["classroom is created through the browser"],
        "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
        "evidence_strength": "full_stack_browser_e2e",
        "acceptance_url": "http://127.0.0.1:15082/customer/course-production",
        "api_health_url": "http://127.0.0.1:15082/api/health",
        "api_health_identity": "classroom-api",
        "network_probe_summary": {
            "business_api_request_count": 1,
            "html_shell_health_response": False,
        },
        "mocked_routes": [],
        "probe_artifact_path": ".product-delivery/artifacts/e2e/tc-v008-001-probe.json",
    }
    record.update(overrides)
    return record


def review_payload(**overrides):
    payload = {
        "review_id": "REV-V1013-TEST-IMPLEMENTATION-001",
        "review_type": "test_implementation",
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["qa-agent", "e2e-agent"],
        "artifact_version": "test-implementation-review-v1",
        "independent_positions": ["QA found no blocker", "E2E found no blocker"],
        "cross_challenges": ["E2E challenged whether API calls were real"],
        "revisions": ["Added network probe evidence"],
        "final_adjudication": "passed with no blocking findings",
        "conclusions": ["test implementation review passed"],
        "accepted_suggestions": ["record business API probe"],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
        "actual_test_code_paths": ["apps/web/e2e/classroom.spec.ts"],
        "execution_evidence_paths": [
            ".product-delivery/artifacts/e2e/tc-v008-001.json",
        ],
        "reviewed_test_ids": ["TC-V008-001"],
        "verified_action_assertions": [
            {
                "test_id": "TC-V008-001",
                "item_id": "classroom-create",
                "clicked_entry": "create classroom button",
                "expected_real_surface": "classroom creation form",
                "assertion_target": "created classroom visible after submit",
                "evidence_path": ".product-delivery/artifacts/e2e/tc-v008-001.json",
            }
        ],
        "false_positive_risks": [],
        "supporting_evidence_only": [],
        "business_api_mock_findings": [],
    }
    payload.update(overrides)
    return payload


class FullStackBrowserEvidenceV1013Tests(unittest.TestCase):
    def test_full_stack_evidence_rejects_business_api_route_mocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_evidence_files(project_root)
            record = full_stack_record(
                mocked_routes=[
                    {
                        "mechanism": "playwright.page.route",
                        "pattern": "**/api/course-operations/standard-courses**",
                        "classification": "business_api",
                        "is_business_api": True,
                    }
                ]
            )

            with self.assertRaises(CoverageAuditError) as caught:
                build_executed_browser_evidence(
                    project_root,
                    [record],
                    planned_obligations=[planned_obligation()],
                )

            self.assertIn("business API mock", str(caught.exception))

    def test_full_stack_evidence_rejects_html_shell_health_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_evidence_files(project_root, html_health=True)

            with self.assertRaises(CoverageAuditError) as caught:
                build_executed_browser_evidence(
                    project_root,
                    [full_stack_record()],
                    planned_obligations=[planned_obligation()],
                )

            self.assertIn("HTML shell", str(caught.exception))

    def test_full_stack_evidence_records_probe_artifact_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_evidence_files(project_root)

            result = build_executed_browser_evidence(
                project_root,
                [full_stack_record()],
                planned_obligations=[planned_obligation()],
            )

            record = result["records"][0]
            self.assertEqual(record["evidence_strength"], "full_stack_browser_e2e")
            self.assertRegex(record["probe_artifact_sha256"], r"^[0-9a-f]{64}$")

    def test_pre_closure_rejects_mocked_browser_evidence_for_ui_journey(self):
        obligation = planned_obligation()
        state = {
            "feature_slug": "v1.0.13-full-stack-browser-evidence",
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
                        **full_stack_record(
                            evidence_strength="mocked_api_browser_e2e",
                            mocked_routes=[
                                {
                                    "mechanism": "playwright.page.route",
                                    "pattern": "**/api/course-operations/**",
                                    "classification": "business_api",
                                    "is_business_api": True,
                                }
                            ],
                        ),
                        "scenario_id": obligation["scenario_id"],
                        "user_story": obligation["user_story"],
                        "journey": obligation["journey"],
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

        self.assertIn("full_stack_browser_e2e", str(caught.exception))

    def test_test_implementation_review_rejects_unexempted_business_api_mocks(self):
        review = review_payload(
            business_api_mock_findings=[
                {
                    "test_id": "TC-V008-001",
                    "route": "**/api/course-operations/**",
                    "mechanism": "playwright.page.route",
                    "is_business_api": True,
                    "exemption_ref": "",
                }
            ],
        )

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("test_implementation", review)

        self.assertIn("business API mock", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
