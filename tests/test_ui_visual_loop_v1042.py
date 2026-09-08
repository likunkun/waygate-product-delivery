import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from product_delivery_agent.artifact_protocol import write_state
from product_delivery_agent.implementation_baseline import DEFAULT_VISUAL_POLICY
from product_delivery_agent.ui_visual_loop import (
    VisualLoopError,
    assert_no_capture_backed_delivery,
    compare_visual_loop,
    ui_visual_loop_required,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import (
    record_passing_task_slice_evidence,
    record_passing_task_visual_loop,
)
from tests.test_goal_driven_closure_v104 import (
    activate_host_goal,
    reconcile_host_goal,
    task_completion_artifact,
    workflow_ready_for_handoff,
)
from tests.test_prototype_implementation_closure_v1028 import (
    PrototypeBoundTaskAndPromptV1028Tests,
)


def _write_png(path: Path, width: int, height: int, color=(255, 255, 255, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    pixel = bytes(color)
    row = b"\x00" + pixel * width
    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(row * height))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)


def _snapshot(path: Path, *, height: int, table_height: int, extra=None) -> None:
    payload = {
        "schema_version": "task-production-semantic-snapshot-v1",
        "surface_id": "dashboard",
        "state_id": "ready",
        "route": "/dashboard",
        "viewport": {"class": "desktop", "width": 20, "height": height},
        "regions": [
            {
                "region_id": "nav",
                "matched_count": 1,
                "visible": True,
                "role": "navigation",
                "accessible_name": "Main nav",
                "parent_region_id": None,
                "display_order": 1,
                "bounding_box": {"x": 0, "y": 0, "width": 20, "height": 4},
            },
            {
                "region_id": "table",
                "matched_count": 1,
                "visible": True,
                "role": "table",
                "accessible_name": "Rows",
                "parent_region_id": None,
                "display_order": 2,
                "bounding_box": {"x": 0, "y": 4, "width": 20, "height": table_height},
            },
        ],
    }
    if extra:
        payload["regions"].extend(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _plan_and_unit(root: Path, *, proto_color=(255, 255, 255, 255), prod_color=(0, 0, 0, 255), prod_height=24):
    proto = root / ".product-delivery/artifacts/proto.png"
    prod = root / ".product-delivery/artifacts/prod.png"
    snap = root / ".product-delivery/artifacts/snap.json"
    _write_png(proto, 20, 10, proto_color)
    _write_png(prod, 20, prod_height, prod_color)
    _snapshot(snap, height=prod_height, table_height=prod_height - 4)
    plan = {
        "plan_version": "v1",
        "plan_id": "plan-1",
        "task_id": "TASK-001",
        "planned_task_hash": "c" * 64,
        "implementation_baseline_sha256": "a" * 64,
        "surface_id": "dashboard",
        "state_id": "ready",
        "viewport_class": "desktop",
        "route": "/dashboard",
        "prototype_screenshot_path": str(proto.relative_to(root)),
        "region_ids": ["nav", "table"],
        "regions": [
            {
                "region_id": "nav",
                "content_kind": "chrome",
                "semantic_role": "navigation",
                "display_order": 1,
                "bounds": {"x": 0, "y": 0, "width": 20, "height": 4},
            },
            {
                "region_id": "table",
                "content_kind": "data",
                "semantic_role": "table",
                "display_order": 2,
                "bounds": {"x": 0, "y": 4, "width": 20, "height": 6},
            },
        ],
        "closure_valid": False,
    }
    manifest = {
        "plan_id": "plan-1",
        "production_screenshot_path": str(prod.relative_to(root)),
        "semantic_snapshot_path": str(snap.relative_to(root)),
        "production_route": "/dashboard",
    }
    return plan, manifest, snap


class VisualLoopCompareV1042Tests(unittest.TestCase):
    def test_data_growth_and_pixel_gap_do_not_fail_chrome_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tall_plan, tall_manifest, _ = _plan_and_unit(root, prod_height=40)
            evidence = compare_visual_loop(
                root, tall_plan, tall_manifest, visual_policy=DEFAULT_VISUAL_POLICY
            )
            self.assertEqual(evidence["status"], "passed")
            self.assertFalse(evidence["closure_valid"])
            self.assertTrue(
                any(item["code"] == "data_geometry_changed" for item in evidence["data_findings"])
            )
            self.assertFalse(evidence["failure_codes"])

            pixel_plan, pixel_manifest, _ = _plan_and_unit(
                root, proto_color=(255, 255, 255, 255), prod_color=(0, 0, 0, 255), prod_height=10
            )
            evidence = compare_visual_loop(
                root, pixel_plan, pixel_manifest, visual_policy=DEFAULT_VISUAL_POLICY
            )
            self.assertEqual(evidence["status"], "passed")
            self.assertTrue(
                any(
                    item["code"] == "pixel_diagnostic_above_legacy_threshold"
                    for item in evidence["data_findings"]
                )
            )

    def test_missing_chrome_and_order_and_geometry_fail_with_next_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, manifest, snap = _plan_and_unit(root)
            payload = json.loads(snap.read_text())
            payload["regions"] = [
                {
                    "region_id": "table",
                    "matched_count": 1,
                    "visible": True,
                    "role": "table",
                    "accessible_name": "Rows",
                    "display_order": 2,
                    "bounding_box": {"x": 0, "y": 4, "width": 20, "height": 20},
                }
            ]
            snap.write_text(json.dumps(payload) + "\n")
            evidence = compare_visual_loop(
                root, plan, manifest, visual_policy=DEFAULT_VISUAL_POLICY
            )
            self.assertEqual(evidence["status"], "failed")
            self.assertIn("region_missing", evidence["failure_codes"])
            self.assertEqual(evidence["next_fix"][0]["region_id"], "nav")

            payload["regions"].append(
                {
                    "region_id": "nav",
                    "matched_count": 1,
                    "visible": True,
                    "role": "navigation",
                    "accessible_name": "Main nav",
                    "display_order": 9,
                    "bounding_box": {"x": 0, "y": 20, "width": 20, "height": 4},
                }
            )
            snap.write_text(json.dumps(payload) + "\n")
            evidence = compare_visual_loop(
                root, plan, manifest, visual_policy=DEFAULT_VISUAL_POLICY
            )
            self.assertIn("region_order_mismatch", evidence["failure_codes"])
            self.assertIn("geometry_mismatch", evidence["failure_codes"])

    def test_unbound_later_task_controls_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, manifest, snap = _plan_and_unit(root, proto_color=(0, 0, 0, 255), prod_color=(0, 0, 0, 255), prod_height=10)
            payload = json.loads(snap.read_text())
            payload["regions"].append(
                {
                    "region_id": "future-filter",
                    "matched_count": 0,
                    "visible": False,
                    "role": "search",
                    "bounding_box": {"x": 0, "y": 0, "width": 1, "height": 1},
                }
            )
            snap.write_text(json.dumps(payload) + "\n")
            evidence = compare_visual_loop(
                root, plan, manifest, visual_policy=DEFAULT_VISUAL_POLICY
            )
            self.assertEqual(evidence["status"], "passed")


class VisualLoopWorkflowV1042Tests(unittest.TestCase):
    def launched(self, root: Path):
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

    def test_new_ui_sets_visual_loop_policy_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self.launched(Path(tmp))
            state = workflow.status()
            self.assertTrue(ui_visual_loop_required(state))
            self.assertIn("visual loop", state["current_task_prompt"])
            self.assertIn("next_fix[0]", state["current_task_prompt"])
            self.assertNotIn("一致性证据", state["current_task_prompt"])

    def test_loop_runs_when_host_goal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.launched(root)
            state = workflow.status()
            binding = dict(state.get("host_goal_binding") or {})
            binding["status"] = "blocked"
            binding["authorized_transition"] = None
            state["host_goal_binding"] = binding
            write_state(root, state)
            unit = state["implementation_baseline"]["units"][0]
            prepared = workflow.prepare_ui_visual_loop(
                "TASK-001",
                unit["surface_id"],
                unit["state_id"],
                unit["viewport_class"],
            )
            self.assertEqual(
                prepared["ui_visual_loop"]["plans"][
                    prepared["ui_visual_loop"]["current_plan_id"]
                ]["closure_valid"],
                False,
            )

    def test_new_ui_completes_without_conformance_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.launched(root)
            unit = workflow.status()["implementation_baseline"]["units"][0]
            with self.assertRaisesRegex(WorkflowError, "expand beyond"):
                workflow.prepare_ui_visual_loop(
                    "TASK-001",
                    unit["surface_id"],
                    unit["state_id"],
                    unit["viewport_class"],
                    region_ids=list(unit["region_ids"]) + ["future-region"],
                )
            record_passing_task_visual_loop(workflow, root, "TASK-001")
            record_passing_task_slice_evidence(workflow, root, "TASK-001")
            reconcile_host_goal(workflow)
            completed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            self.assertEqual(completed["delivery_goal"]["completed_tasks"], ["TASK-001"])
            self.assertNotIn(
                "task_prototype_conformance_sha256",
                completed["delivery_goal"]["task_completion_artifacts"]["TASK-001"],
            )
            self.assertIn(
                "task_visual_loop_sha256",
                completed["delivery_goal"]["task_completion_artifacts"]["TASK-001"],
            )
            self.assertFalse(
                any(
                    event["transition_name"] == "task_completed"
                    and event.get("metadata", {}).get("closure_valid")
                    for event in completed["transition_journal"]["events"]
                    if event["transition_name"] == "ui_visual_loop_recorded"
                )
            )

    def test_legacy_policy_still_requires_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.launched(root)
            state = workflow.status()
            state["ui_visual_loop_policy"] = {
                "policy_version": "v1",
                "status": "not_applicable",
                "introduced_in": "1.0.42",
            }
            write_state(root, state)
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "task prototype conformance"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(workflow.status(), "TASK-001"),
                )


class CaptureInstallGuardV1042Tests(unittest.TestCase):
    def test_install_rejects_capture_backed_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / ".product-delivery" / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps({"ui_capture_registry": {"root": "x"}}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(VisualLoopError):
                assert_no_capture_backed_delivery(root)
            state_path.write_text("{}\n", encoding="utf-8")
            assert_no_capture_backed_delivery(root)


if __name__ == "__main__":
    unittest.main()
