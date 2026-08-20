import json
import math
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from product_delivery_agent import implementation_baseline
from product_delivery_agent.implementation_baseline import (
    build_task_prototype_conformance,
    validate_task_prototype_conformance,
)
from product_delivery_agent.evidence_artifacts import stable_json_hash
from product_delivery_agent.review_gates import validate_multi_agent_review
from tests.conformance_fixtures import ui_conformance_review_payload
from tests.test_goal_driven_closure_v104 import (
    activate_host_goal,
    reconcile_host_goal,
    workflow_ready_for_handoff,
)
from tests.test_prototype_implementation_closure_v1028 import (
    PrototypeBoundTaskAndPromptV1028Tests,
    TaskPrototypeConformanceV1028Tests,
)


VISUAL_DECISION_KEY = "task_visual_conformance:TASK-001"


class GeometryClassificationV1033Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = TaskPrototypeConformanceV1028Tests()

    @staticmethod
    def _mutate_action(snapshot_path: Path, box: dict) -> None:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        action = next(
            region
            for region in snapshot["regions"]
            if region["region_id"] == "action"
        )
        action["bounding_box"] = box
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _evidence_for_box(self, root: Path, box: dict):
        baseline, task, payload, snapshot_path, _ = self.fixture.build_domain_fixture(
            root
        )
        self._mutate_action(snapshot_path, box)
        return build_task_prototype_conformance(
            root,
            payload,
            implementation_baseline=baseline,
            planned_task=task,
        )

    def test_geometry_mismatch_is_an_adjudicable_visual_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = self._evidence_for_box(
                Path(tmp),
                {"x": 2, "y": 2, "width": 8, "height": 2},
            )

        self.assertEqual(evidence["conformance_version"], "v2")
        failure = next(
            item for item in evidence["failures"] if item["code"] == "geometry_mismatch"
        )
        self.assertEqual(failure["failure_class"], "visual_adjudicable")
        self.assertEqual(
            evidence["adjudication_eligibility"],
            {
                "eligible": True,
                "visual_failure_codes": ["geometry_mismatch"],
                "hard_failure_codes": [],
            },
        )
        geometry = evidence["records"][0]["geometry_results"][0]
        self.assertEqual(geometry["classification"], "mismatch")
        self.assertEqual(geometry["failure_class"], "visual_adjudicable")
        self.assertEqual(geometry["delta"]["x"], -2.0)
        self.assertEqual(geometry["delta"]["width"], 6.0)
        self.assertEqual(geometry["tolerance"]["horizontal_px"], 4.0)

    def test_small_viewport_overflow_is_an_adjudicable_visual_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = self._evidence_for_box(
                Path(tmp),
                {"x": 4, "y": 2, "width": 2, "height": 4},
            )

        failure = next(
            item for item in evidence["failures"] if item["code"] == "geometry_invalid"
        )
        self.assertEqual(failure["failure_class"], "visual_adjudicable")
        geometry = evidence["records"][0]["geometry_results"][0]
        self.assertEqual(geometry["classification"], "soft_invalid")
        self.assertEqual(geometry["viewport_overflow"]["bottom"], 1.0)
        self.assertTrue(evidence["adjudication_eligibility"]["eligible"])

    def test_zero_nonfinite_and_clearly_offscreen_geometry_are_hard_failures(self):
        cases = (
            ({"x": 4, "y": 2, "width": 0, "height": 2}, "non_positive_size"),
            ({"x": 4, "y": 2, "width": math.nan, "height": 2}, "non_finite_bounds"),
            ({"x": 20, "y": 2, "width": 2, "height": 2}, "outside_viewport_tolerance"),
        )
        for box, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                evidence = self._evidence_for_box(Path(tmp), box)

                failure = next(
                    item
                    for item in evidence["failures"]
                    if item["code"] == "geometry_invalid"
                )
                self.assertEqual(failure["failure_class"], "hard_blocking")
                self.assertEqual(failure["classification_reason"], reason)
                self.assertFalse(evidence["adjudication_eligibility"]["eligible"])
                self.assertIn(
                    "geometry_invalid",
                    evidence["adjudication_eligibility"]["hard_failure_codes"],
                )

    def test_v1_pixel_only_artifact_remains_adjudicable(self):
        classifier = getattr(
            implementation_baseline,
            "task_conformance_is_adjudicable_visual_failure",
            None,
        )
        self.assertTrue(callable(classifier))
        self.assertTrue(
            classifier(
                {
                    "conformance_version": "v1",
                    "environment_status": "stable",
                    "failure_codes": ["full_surface_pixel_diff"],
                }
            )
        )
        body = {
            "conformance_version": "v1",
            "implementation_baseline_sha256": "a" * 64,
            "task_id": "TASK-001",
            "planned_task_hash": "b" * 64,
            "environment_status": "stable",
            "environment_reason": None,
            "records": [],
            "failures": [
                {
                    "code": "full_surface_pixel_diff",
                    "message": "legacy pixel difference",
                }
            ],
            "failure_codes": ["full_surface_pixel_diff"],
            "visual_adjudication": {
                "artifact_path": "artifacts/legacy-adjudication.json",
                "artifact_sha256": "c" * 64,
                "decision_id": "visual-decision-legacy",
                "source": "prompted",
            },
        }
        legacy = {
            **body,
            "status": "accepted_by_user",
            "evidence_sha256": stable_json_hash(body),
        }
        self.assertEqual(
            validate_task_prototype_conformance(legacy)["conformance_version"],
            "v1",
        )

    def test_v2_classifier_fails_closed_when_eligibility_projection_is_tampered(self):
        classifier = implementation_baseline.task_conformance_is_adjudicable_visual_failure
        value = {
            "conformance_version": "v2",
            "environment_status": "stable",
            "failure_codes": ["route_mismatch"],
            "failures": [
                {
                    "code": "route_mismatch",
                    "failure_class": "hard_blocking",
                }
            ],
            "adjudication_eligibility": {
                "eligible": True,
                "visual_failure_codes": ["route_mismatch"],
                "hard_failure_codes": [],
            },
        }

        self.assertFalse(classifier(value))


class GeometryWorkflowV1033Tests(unittest.TestCase):
    def setUp(self):
        self.payload_factory = TaskPrototypeConformanceV1028Tests()

    @staticmethod
    def _workflow(root: Path):
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

    def _record_geometry_failure(self, workflow, root: Path, width_delta: int):
        reconcile_host_goal(workflow)
        payload = self.payload_factory.workflow_conformance_payload(
            root, workflow.status()
        )
        snapshot_path = root / payload["records"][0]["semantic_snapshot_path"]
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        box = deepcopy(snapshot["regions"][0]["bounding_box"])
        box["width"] -= width_delta
        snapshot["regions"][0]["bounding_box"] = box
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return workflow.record_task_prototype_conformance("TASK-001", payload)

    def test_geometry_uses_the_same_two_round_window_and_can_be_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)

            initial = self._record_geometry_failure(workflow, root, 20)
            first_retry = self._record_geometry_failure(workflow, root, 30)
            second_retry = self._record_geometry_failure(workflow, root, 40)

            tracker = second_retry["task_prototype_conformance"]["visual_retry"][
                "TASK-001"
            ]
            self.assertEqual(tracker["remediation_rounds_completed"], 2)
            self.assertTrue(tracker["adjudication_eligible"])
            decision = second_retry["pending_user_decisions"][VISUAL_DECISION_KEY]
            self.assertTrue(decision["presentation"]["geometry_deviations"])

            reconcile_host_goal(workflow)
            accepted = workflow.record_task_visual_conformance_adjudication(
                "TASK-001",
                decision="accept",
                user_message="我接受当前尺寸和位置差异。",
                decision_id=decision["decision_id"],
            )

            record = accepted["task_prototype_conformance"]["records"]["TASK-001"]
            self.assertEqual(record["status"], "accepted_by_user")
            deviations = accepted["task_prototype_conformance"][
                "visual_adjudications"
            ]["TASK-001"]["deviations"]
            self.assertTrue(
                any(item["deviation_type"] == "geometry" for item in deviations)
            )
            artifact = json.loads(
                (
                    root
                    / ".product-delivery"
                    / record["visual_adjudication"]["artifact_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                artifact["schema_version"],
                "task-visual-conformance-adjudication-v2",
            )
            review = ui_conformance_review_payload(accepted)
            review["accepted_visual_deviations"] = deviations
            validate_multi_agent_review(
                "ui_conformance",
                review,
                prototype_contract=accepted["prototype_contract"],
                visual_adjudications=deviations,
            )

    def test_hard_failure_does_not_advance_an_existing_visual_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self._workflow(root)
            first = self._record_geometry_failure(workflow, root, 20)
            before = first["task_prototype_conformance"]["visual_retry"]["TASK-001"]

            reconcile_host_goal(workflow)
            payload = self.payload_factory.workflow_conformance_payload(
                root, workflow.status()
            )
            payload["records"][0]["production_route"] = "/wrong-route"
            mixed = workflow.record_task_prototype_conformance("TASK-001", payload)

        after = mixed["task_prototype_conformance"]["visual_retry"]["TASK-001"]
        self.assertEqual(after["attempts"], before["attempts"])
        self.assertNotIn(VISUAL_DECISION_KEY, mixed["pending_user_decisions"])
