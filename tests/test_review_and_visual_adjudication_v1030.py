import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.plugin_packaging import package_codex_plugin
from product_delivery_agent.review_gates import ReviewGateError, validate_multi_agent_review
from product_delivery_agent.workflow import WorkflowError
from tests.conformance_fixtures import (
    PROTOTYPE_DESIGN_DIMENSIONS,
    prototype_contract,
    record_passing_task_slice_evidence,
    ui_conformance_review_payload,
)
from tests.test_goal_driven_closure_v104 import (
    activate_host_goal,
    reconcile_host_goal,
    task_completion_artifact,
    workflow_ready_for_handoff,
)
from tests.test_prototype_implementation_closure_v1028 import (
    PrototypeBoundTaskAndPromptV1028Tests,
    TaskPrototypeConformanceV1028Tests,
)


VISUAL_DECISION_KEY = "task_visual_conformance:TASK-001"


def _write_solid_rgba_png(path: Path, *, width: int, height: int, color) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes(color) * width
    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
    )
    image += chunk(b"IDAT", zlib.compress(row * height))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)


class VisualConformanceAdjudicationV1030Tests(unittest.TestCase):
    def setUp(self):
        self.payload_factory = TaskPrototypeConformanceV1028Tests()

    def _workflow(self, root: Path):
        workflow = workflow_ready_for_handoff(root)
        task = PrototypeBoundTaskAndPromptV1028Tests.bound_task(workflow.status())
        workflow.record_implementation_launch_authorization(
            scope="Implement the confirmed UI",
            verification_commands=["pytest"],
            planned_tasks=[task],
        )
        workflow.generate_codex_goal_handoff(
            scope="Implement the confirmed UI",
            verification_commands=["pytest"],
            planned_tasks=[task],
        )
        activate_host_goal(workflow)
        return workflow

    def _record_pixel_failure(self, workflow, root: Path, color):
        reconcile_host_goal(workflow)
        state = workflow.status()
        payload = self.payload_factory.workflow_conformance_payload(root, state)
        unit = state["implementation_baseline"]["units"][0]
        production_path = root / payload["records"][0]["production_screenshot_path"]
        _write_solid_rgba_png(
            production_path,
            width=unit["prototype_screenshot_width"],
            height=unit["prototype_screenshot_height"],
            color=color,
        )
        return workflow.record_task_prototype_conformance("TASK-001", payload)

    def test_two_remediation_rounds_are_required_before_user_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)

            initial = self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            tracker = initial["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(tracker["remediation_rounds_completed"], 0)
            self.assertFalse(tracker["adjudication_eligible"])
            self.assertNotIn(VISUAL_DECISION_KEY, initial["pending_user_decisions"])

            first_retry = self._record_pixel_failure(workflow, root, (64, 0, 0, 255))
            tracker = first_retry["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(tracker["remediation_rounds_completed"], 1)
            self.assertFalse(tracker["adjudication_eligible"])
            self.assertNotIn(VISUAL_DECISION_KEY, first_retry["pending_user_decisions"])

            second_retry = self._record_pixel_failure(workflow, root, (0, 64, 0, 255))
            tracker = second_retry["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(tracker["remediation_rounds_completed"], 2)
            self.assertTrue(tracker["adjudication_eligible"])
            pending = second_retry["pending_user_decisions"][VISUAL_DECISION_KEY]
            self.assertEqual(pending["task_id"], "TASK-001")
            self.assertEqual(pending["status"], "pending")
            self.assertEqual(len(pending["attempt_artifact_sha256s"]), 3)
            presentation = pending["presentation"]
            self.assertTrue(presentation["prototype_screenshot_paths"])
            self.assertTrue(presentation["production_screenshot_paths"])
            self.assertTrue(presentation["pixel_diff_artifact_paths"])
            for relative_path in presentation["pixel_diff_artifact_paths"]:
                self.assertTrue((root / relative_path).is_file())

            continuation = derive_continuation_status(second_retry)
            self.assertEqual(continuation["status"], "wait_for_user")
            self.assertEqual(
                continuation["next_action"],
                "task_visual_conformance_adjudication",
            )


    def test_later_automatic_pass_supersedes_retry_and_pending_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            self._record_pixel_failure(workflow, root, (64, 0, 0, 255))
            self._record_pixel_failure(workflow, root, (0, 64, 0, 255))

            reconcile_host_goal(workflow)
            payload = self.payload_factory.workflow_conformance_payload(
                root, workflow.status()
            )
            passed = workflow.record_task_prototype_conformance("TASK-001", payload)

            record = passed["task_prototype_conformance"]["records"]["TASK-001"]
            self.assertEqual(record["status"], "passed")
            self.assertNotIn(
                "TASK-001", passed["task_prototype_conformance"]["visual_retry"]
            )
            self.assertNotIn(VISUAL_DECISION_KEY, passed["pending_user_decisions"])

    def test_duplicate_and_non_visual_failures_do_not_advance_visual_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)

            first = self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            repeated = self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            tracker = repeated["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(len(tracker["attempts"]), 1)
            self.assertEqual(tracker["remediation_rounds_completed"], 0)

            reconcile_host_goal(workflow)
            payload = self.payload_factory.workflow_conformance_payload(
                root, workflow.status()
            )
            payload["records"][0]["production_route"] = "/wrong-route"
            non_visual = workflow.record_task_prototype_conformance("TASK-001", payload)
            tracker = non_visual["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(len(tracker["attempts"]), 1)
            self.assertNotIn(VISUAL_DECISION_KEY, non_visual["pending_user_decisions"])
            self.assertEqual(
                first["task_prototype_conformance"]["records"]["TASK-001"]["status"],
                "failed",
            )

    def test_user_can_accept_pixel_difference_before_system_prompt_and_complete_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            self._record_pixel_failure(workflow, root, (0, 0, 0, 255))

            reconcile_host_goal(workflow)
            accepted = workflow.record_task_visual_conformance_adjudication(
                "TASK-001",
                decision="accept",
                user_message="我接受当前像素差异，继续交付。",
            )
            record = accepted["task_prototype_conformance"]["records"]["TASK-001"]
            self.assertEqual(record["status"], "accepted_by_user")
            adjudication = record["visual_adjudication"]
            self.assertEqual(adjudication["source"], "user_initiated")
            self.assertTrue(
                (root / ".product-delivery" / adjudication["artifact_path"]).is_file()
            )
            self.assertTrue(
                any(
                    event["transition_name"]
                    == "task_visual_conformance_adjudicated"
                    for event in accepted["transition_journal"]["events"]
                )
            )

            reconcile_host_goal(workflow)
            record_passing_task_slice_evidence(workflow, root, "TASK-001")
            reconcile_host_goal(workflow)
            completed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            self.assertEqual(completed["delivery_goal"]["completed_tasks"], ["TASK-001"])


    def test_product_baseline_change_invalidates_visual_retry_and_adjudication_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            self._record_pixel_failure(workflow, root, (64, 0, 0, 255))
            self._record_pixel_failure(workflow, root, (0, 64, 0, 255))

            reconcile_host_goal(workflow)
            changed = workflow.record_user_requested_change(
                targets=["product_baseline"],
                user_message="调整已确认的产品基线。",
            )

            self.assertNotIn(VISUAL_DECISION_KEY, changed["pending_user_decisions"])
            self.assertEqual(
                changed["task_prototype_conformance"].get("visual_retry"), {}
            )
            self.assertEqual(
                changed["task_prototype_conformance"].get("visual_adjudications"), {}
            )

    def test_non_visual_failure_cannot_be_user_adjudicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            reconcile_host_goal(workflow)
            payload = self.payload_factory.workflow_conformance_payload(
                root, workflow.status()
            )
            payload["records"][0]["production_route"] = "/wrong-route"
            workflow.record_task_prototype_conformance("TASK-001", payload)

            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "pixel-only"):
                workflow.record_task_visual_conformance_adjudication(
                    "TASK-001",
                    decision="accept",
                    user_message="accept",
                )

    def test_rejecting_prompt_resets_the_two_round_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            self._record_pixel_failure(workflow, root, (0, 0, 0, 255))
            self._record_pixel_failure(workflow, root, (64, 0, 0, 255))
            prompted = self._record_pixel_failure(workflow, root, (0, 64, 0, 255))
            decision_id = prompted["pending_user_decisions"][VISUAL_DECISION_KEY][
                "decision_id"
            ]

            reconcile_host_goal(workflow)
            rejected = workflow.record_task_visual_conformance_adjudication(
                "TASK-001",
                decision="continue_remediation",
                user_message="继续自动修复，不接受当前差异。",
                decision_id=decision_id,
            )
            tracker = rejected["task_prototype_conformance"]["visual_retry"]["TASK-001"]
            self.assertEqual(tracker["attempts"], [])
            self.assertEqual(tracker["remediation_rounds_completed"], 0)
            self.assertFalse(tracker["adjudication_eligible"])
            self.assertNotIn(VISUAL_DECISION_KEY, rejected["pending_user_decisions"])


class UiReviewAcceptedDeviationV1030Tests(unittest.TestCase):
    def _review(self):
        state = {"prototype_contract": {**prototype_contract(), "status": "ready"}}
        review = ui_conformance_review_payload(state)
        review["reviewed_design_dimensions"] = list(PROTOTYPE_DESIGN_DIMENSIONS)
        return state["prototype_contract"], review

    def test_ui_review_must_reference_every_current_visual_adjudication(self):
        contract, review = self._review()
        expected = [
            {
                "task_id": "TASK-001",
                "adjudication_artifact_sha256": "a" * 64,
                "surface_id": "primary-surface",
                "state_id": "ready",
                "viewport_class": "desktop",
                "scope": "critical_region",
                "region_id": "primary-region",
                "diff_ratio": 0.031,
                "max_diff_ratio": 0.02,
            }
        ]
        review["accepted_visual_deviations"] = expected

        validate_multi_agent_review(
            "ui_conformance",
            review,
            prototype_contract=contract,
            visual_adjudications=expected,
        )

        review["accepted_visual_deviations"] = []
        with self.assertRaisesRegex(ReviewGateError, "accepted_visual_deviations"):
            validate_multi_agent_review(
                "ui_conformance",
                review,
                prototype_contract=contract,
                visual_adjudications=expected,
            )


class ReviewRoundDisciplinePackagingV1030Tests(unittest.TestCase):
    def test_generated_execution_review_guidance_requires_batch_review_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = package_codex_plugin(Path(tmp))["plugin_root"]
            skill = (
                root / "skills" / "waygate-product-delivery" / "SKILL.md"
            ).read_text("utf-8")
            test_review = (
                root / "templates" / "multi-agent-test-implementation-review.md"
            ).read_text("utf-8")
            ui_review = (
                root / "templates" / "multi-agent-ui-conformance-review.md"
            ).read_text("utf-8")
            scenario_review = (
                root / "templates" / "multi-agent-scenario-review.md"
            ).read_text("utf-8")

            for text in (skill, test_review, ui_review):
                self.assertIn("同一输入快照", text)
                self.assertIn("全部评审者", text)
                self.assertIn("冻结完整问题清单", text)
                self.assertIn("批量修复", text)
                self.assertIn("统一复验", text)
            self.assertNotIn("冻结完整问题清单", scenario_review)
            self.assertIn("accepted_visual_deviations", ui_review)
            self.assertIn("两轮", skill)
            self.assertIn("record_task_visual_conformance_adjudication", skill)


if __name__ == "__main__":
    unittest.main()
