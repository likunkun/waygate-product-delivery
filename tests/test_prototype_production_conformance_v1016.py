import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from product_delivery_agent import coverage_audit, ui_prototype
from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.gatekeeper import (
    GatekeeperError,
    assert_pre_closure_ready,
)
from product_delivery_agent.review_gates import (
    ReviewGateError,
    validate_multi_agent_review,
)
from product_delivery_agent.workflow import (
    ConfirmationError,
    ProductDeliveryWorkflow,
)
from tests.test_feature_closure import ready_workflow, valid_closure_artifact


def write_png(path: Path, width: int = 1280, height: int = 720) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + (b"\xff\xff\xff\xff" * width)
    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(row * height))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)


def prototype_contract() -> dict:
    return {
        "contract_version": "v1",
        "prototype_screenshot_paths": [
            ".product-delivery/artifacts/prototype/series-desktop.png"
        ],
        "surfaces": [
            {
                "surface_id": "series-management",
                "route": "/customer/course-production/standard-courses",
                "state_id": "series-detail-ready",
                "required_viewports": ["desktop"],
                "critical_regions": [
                    {
                        "region_id": "series-list",
                        "semantic_role": "navigation",
                        "accessible_name_match": {
                            "mode": "exact",
                            "value": "系列",
                        },
                        "visibility": "visible",
                    },
                    {
                        "region_id": "series-course-table",
                        "semantic_role": "region",
                        "accessible_name_match": {
                            "mode": "contains",
                            "value": "课程表",
                        },
                        "visibility": "visible",
                    },
                ],
                "critical_relationships": [
                    {
                        "source_region_id": "series-list",
                        "relation": "precedes",
                        "target_region_id": "series-course-table",
                    }
                ],
                "critical_interactions": [
                    {
                        "interaction_id": "open-series",
                        "entry_region_id": "series-list",
                        "action": "select series",
                        "expected_relation": "updates",
                        "target_region_id": "series-course-table",
                    }
                ],
            }
        ],
    }


def semantic_snapshot() -> dict:
    return {
        "schema_version": "ui-semantic-surface-v1",
        "acceptance_url": "http://127.0.0.1:15082/customer/course-production/standard-courses",
        "execution_segment_id": "series-detail-ready-desktop",
        "viewport": {"class": "desktop", "width": 1280, "height": 720},
        "regions": [
            {
                "region_id": "series-list",
                "matched_count": 1,
                "visible": True,
                "role": "navigation",
                "accessible_name": "系列",
                "parent_region_id": None,
                "display_order": 1,
                "bounding_box": {"x": 0, "y": 0, "width": 300, "height": 720},
                "key_controls": ["select series"],
                "interaction_state": "ready",
            },
            {
                "region_id": "series-course-table",
                "matched_count": 1,
                "visible": True,
                "role": "region",
                "accessible_name": "系列详情课程表",
                "parent_region_id": None,
                "display_order": 2,
                "bounding_box": {"x": 300, "y": 0, "width": 980, "height": 720},
                "key_controls": ["view content status"],
                "interaction_state": "updated",
            },
        ],
        "relationships": [
            {
                "source_region_id": "series-list",
                "relation": "precedes",
                "target_region_id": "series-course-table",
                "observed": True,
            }
        ],
        "interactions": [
            {
                "interaction_id": "open-series",
                "observed": True,
                "result": "series-course-table updated",
            }
        ],
    }


def browser_evidence() -> dict:
    return {
        "status": "passed",
        "records": [
            {
                "test_id": "TC-V143C-031",
                "obligation_id": "OBL-V143C-031",
                "evidence_strength": "full_stack_browser_e2e",
                "acceptance_url": "http://127.0.0.1:15082/customer/course-production/standard-courses",
                "execution_segment_id": "series-detail-ready-desktop",
            }
        ],
    }


def production_payload() -> dict:
    return {
        "prototype_revision": "prototype-revision-009",
        "prototype_contract_hash": "placeholder",
        "records": [
            {
                "surface_id": "series-management",
                "state_id": "series-detail-ready",
                "viewport_class": "desktop",
                "acceptance_url": "http://127.0.0.1:15082/customer/course-production/standard-courses",
                "execution_segment_id": "series-detail-ready-desktop",
                "production_route": "/customer/course-production/standard-courses",
                "production_screenshot_path": ".product-delivery/artifacts/conformance/series-production.png",
                "semantic_snapshot_path": ".product-delivery/artifacts/conformance/series-semantic.json",
                "region_results": [
                    {"region_id": "series-list", "observed": True},
                    {"region_id": "series-course-table", "observed": True},
                ],
                "relationship_results": [
                    {
                        "source_region_id": "series-list",
                        "relation": "precedes",
                        "target_region_id": "series-course-table",
                        "observed": True,
                    }
                ],
                "interaction_results": [
                    {"interaction_id": "open-series", "observed": True}
                ],
                "production_component_refs": [
                    {
                        "path": "apps/web/src/v10Surfaces.tsx",
                        "kind": "legacy_surface_adapter",
                        "note": "shared surface preserves the confirmed region contract",
                    }
                ],
            }
        ],
    }


def prototype_review_payload() -> dict:
    return {
        "prototype_path": "docs/prototypes/v143.html",
        "pages": ["series management"],
        "states": ["series detail ready"],
        "journeys": ["series list -> series course table"],
        "taxonomy": {
            "roles": ["teacher"],
            "main_paths": ["teacher opens a series"],
            "exceptions": ["series is unavailable"],
            "recovery": ["retry series readback"],
            "permissions": ["student cannot open series management"],
            "long_tasks": ["series content refresh"],
            "mobile": ["series detail remains reachable"],
            "keyboard": ["series list is keyboard selectable"],
            "negative_scope_boundaries": ["no student learning action"],
        },
        "limitations": ["static prototype data"],
        "browser_e2e_candidates": ["teacher opens series detail"],
        "negative_scope_guard_candidates": ["student learning remains absent"],
        "ui_change_type": "incremental_existing_surface",
        "baseline_feature_slug": "v1.4.2-standard-unit-content",
        "baseline_surface_paths": ["/customer/course-production"],
        "baseline_user_journey": "course operations -> series management",
        "continuity_mapping": ["keeps the existing course operations entry"],
        "prototype_delta_summary": ["adds series management on the existing path"],
        "prototype_contract": prototype_contract(),
    }


class PrototypeProductionConformanceV1016Tests(unittest.TestCase):
    def prepare_project(self, root: Path) -> None:
        prototype = root / "docs/prototypes/v143.html"
        prototype.parent.mkdir(parents=True, exist_ok=True)
        prototype.write_text("<html><body>series prototype</body></html>", encoding="utf-8")
        write_png(root / ".product-delivery/artifacts/prototype/series-desktop.png")
        write_png(root / ".product-delivery/artifacts/conformance/series-production.png")
        snapshot = root / ".product-delivery/artifacts/conformance/series-semantic.json"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(json.dumps(semantic_snapshot()), encoding="utf-8")
        component = root / "apps/web/src/v10Surfaces.tsx"
        component.parent.mkdir(parents=True, exist_ok=True)
        component.write_text("export const Surface = true;\n", encoding="utf-8")

    def test_contract_rejects_duplicate_region_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = prototype_contract()
            contract["surfaces"][0]["critical_regions"].append(
                dict(contract["surfaces"][0]["critical_regions"][0])
            )

            with self.assertRaises(Exception) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("duplicate region_id", str(caught.exception))

    def test_contract_rejects_unknown_parent_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = prototype_contract()
            contract["surfaces"][0]["critical_regions"][1][
                "parent_region_id"
            ] = "missing-region"

            with self.assertRaises(ui_prototype.UIPrototypeError) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("parent region", str(caught.exception))

    def test_contract_rejects_region_hierarchy_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = prototype_contract()
            regions = contract["surfaces"][0]["critical_regions"]
            regions[0]["parent_region_id"] = regions[1]["region_id"]
            regions[1]["parent_region_id"] = regions[0]["region_id"]

            with self.assertRaises(ui_prototype.UIPrototypeError) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("hierarchy cycle", str(caught.exception))

    def test_contract_rejects_display_order_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = prototype_contract()
            regions = contract["surfaces"][0]["critical_regions"]
            regions[0]["display_order"] = 1
            regions[1]["display_order"] = 1

            with self.assertRaises(ui_prototype.UIPrototypeError) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("display_order", str(caught.exception))

    def test_contract_hashes_real_prototype_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)

            result = ui_prototype.build_prototype_contract(root, prototype_contract())

            self.assertEqual(result["status"], "ready")
            self.assertRegex(result["contract_sha256"], r"^[0-9a-f]{64}$")
            screenshot = result["prototype_screenshots"][0]
            self.assertEqual(screenshot["format"], "png")
            self.assertEqual(screenshot["width"], 1280)
            self.assertEqual(screenshot["height"], 720)

    def test_contract_rejects_png_extension_with_invalid_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            fake_path = root / ".product-delivery/artifacts/prototype/fake.png"
            fake_path.write_bytes(b"not a png")
            contract = prototype_contract()
            contract["prototype_screenshot_paths"] = [
                ".product-delivery/artifacts/prototype/fake.png"
            ]

            with self.assertRaises(ui_prototype.UIPrototypeError) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("valid PNG", str(caught.exception))

    def test_contract_rejects_screenshot_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            outside = root / "outside.png"
            write_png(outside)
            link = root / ".product-delivery/artifacts/prototype/escape.png"
            link.symlink_to(outside)
            contract = prototype_contract()
            contract["prototype_screenshot_paths"] = [
                ".product-delivery/artifacts/prototype/escape.png"
            ]

            with self.assertRaises(ui_prototype.UIPrototypeError) as caught:
                ui_prototype.build_prototype_contract(root, contract)

            self.assertIn("under .product-delivery/artifacts", str(caught.exception))

    def test_production_conformance_rejects_text_as_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = ui_prototype.build_prototype_contract(root, prototype_contract())
            fake = root / ".product-delivery/artifacts/conformance/not-a-screenshot.txt"
            fake.write_text("playwright titles", encoding="utf-8")
            payload = production_payload()
            payload["prototype_contract_hash"] = contract["contract_sha256"]
            payload["records"][0]["production_screenshot_path"] = str(fake.relative_to(root))

            with self.assertRaises(Exception) as caught:
                coverage_audit.build_prototype_production_conformance(
                    root,
                    payload,
                    canonical_prototype={
                        "prototype_revision": "prototype-revision-009",
                        "artifact_hash": "prototype-sha",
                    },
                    prototype_contract=contract,
                    executed_browser_evidence=browser_evidence(),
                )

            self.assertIn("PNG", str(caught.exception))

    def test_production_conformance_rejects_split_brain_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = ui_prototype.build_prototype_contract(root, prototype_contract())
            payload = production_payload()
            payload["prototype_contract_hash"] = contract["contract_sha256"]

            with self.assertRaises(Exception) as caught:
                coverage_audit.build_prototype_production_conformance(
                    root,
                    payload,
                    canonical_prototype={
                        "prototype_revision": "prototype-revision-007",
                        "artifact_hash": "prototype-sha",
                    },
                    prototype_contract=contract,
                    executed_browser_evidence=browser_evidence(),
                )

            self.assertIn("canonical prototype revision", str(caught.exception))

    def test_production_conformance_rejects_route_provenance_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = ui_prototype.build_prototype_contract(root, prototype_contract())
            payload = production_payload()
            payload["prototype_contract_hash"] = contract["contract_sha256"]
            payload["records"][0]["production_route"] = "/parallel-workbench"

            with self.assertRaises(Exception) as caught:
                coverage_audit.build_prototype_production_conformance(
                    root,
                    payload,
                    canonical_prototype={
                        "prototype_revision": "prototype-revision-009",
                        "artifact_hash": "prototype-sha",
                    },
                    prototype_contract=contract,
                    executed_browser_evidence=browser_evidence(),
                )

            self.assertIn("production route", str(caught.exception))

    def test_complete_semantic_mapping_passes_without_pixel_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = ui_prototype.build_prototype_contract(root, prototype_contract())
            payload = production_payload()
            payload["prototype_contract_hash"] = contract["contract_sha256"]

            result = coverage_audit.build_prototype_production_conformance(
                root,
                payload,
                canonical_prototype={
                    "prototype_revision": "prototype-revision-009",
                    "artifact_hash": "prototype-sha",
                },
                prototype_contract=contract,
                executed_browser_evidence=browser_evidence(),
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["covered_region_ids"], [
                "series-course-table",
                "series-list",
            ])

    def test_ui_conformance_review_must_cover_every_contract_region(self):
        review = {
            "review_id": "REV-V1016-UI-CONFORMANCE",
            "review_type": "ui_conformance",
            "status": "passed",
            "review_mode": "spawned_subagents",
            "reviewers": ["prototype reviewer", "production reviewer"],
            "artifact_version": "ui-conformance-v1",
            "independent_positions": ["prototype and production were compared"],
            "cross_challenges": ["challenged the legacy surface delegation"],
            "revisions": ["added the missing course table review"],
            "final_adjudication": "passed",
            "conclusions": ["UI conformance passed"],
            "accepted_suggestions": [],
            "rejected_suggestions": [],
            "unresolved_questions": [],
            "blocking_findings": [],
            "reviewed_surface_ids": ["series-management"],
            "reviewed_state_ids": ["series-detail-ready"],
            "reviewed_region_ids": ["series-list"],
            "structural_findings": [],
            "visual_findings": [],
            "interaction_findings": [],
            "legacy_reuse_findings": [],
            "unmapped_regions": [],
        }

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review(
                "ui_conformance",
                review,
                prototype_contract={
                    "surfaces": prototype_contract()["surfaces"],
                },
            )

        self.assertIn("reviewed_region_ids", str(caught.exception))

    def test_workflow_freezes_contract_and_screenshot_set_in_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            workflow = ProductDeliveryWorkflow(root)
            workflow.start(feature_slug="v1.0.16-prototype-conformance", multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")

            state = workflow.record_ui_prototype_review(prototype_review_payload())

            self.assertEqual(state["prototype_contract"]["status"], "ready")
            pending = state["pending_confirmations"]["ui_prototype"]
            self.assertEqual(
                pending["prototype_contract_hash"],
                state["prototype_contract"]["contract_sha256"],
            )
            self.assertEqual(
                pending["prototype_screenshot_set_hash"],
                state["prototype_contract"]["prototype_screenshot_set_sha256"],
            )

    def test_confirmation_rejects_changed_prototype_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            workflow = ProductDeliveryWorkflow(root)
            workflow.start(feature_slug="v1.0.16-prototype-conformance", multi_agent_mode="spawned_subagents_authorized")
            workflow.select_project_type("ui")
            state = workflow.record_ui_prototype_review(prototype_review_payload())
            pending = state["pending_confirmations"]["ui_prototype"]
            write_png(
                root / ".product-delivery/artifacts/prototype/series-desktop.png",
                width=1024,
                height=768,
            )

            with self.assertRaises(ConfirmationError) as caught:
                workflow.confirm_ui_prototype(
                    "确认当前原型和一致性合同",
                    "docs/prototypes/v143.html",
                    agent_explicitly_asked=True,
                    nonce=pending["nonce"],
                )

            self.assertIn("screenshot", str(caught.exception))

    def test_workflow_records_production_conformance_and_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            contract = ui_prototype.build_prototype_contract(root, prototype_contract())
            workflow = ProductDeliveryWorkflow(root)
            workflow.start(feature_slug="v1.0.16-prototype-conformance", multi_agent_mode="spawned_subagents_authorized")
            state = load_state(root)
            state.update(
                {
                    "project_type": "ui",
                    "ui_prototype": {
                        "confirmed_by_user": True,
                        "prototype_revision": "prototype-revision-009",
                        "artifact_hash": "prototype-sha",
                    },
                    "prototype_contract": contract,
                    "implementation": {
                        "current_task": "COMPLETE",
                        "completed_tasks": ["TASK-1"],
                    },
                    "executed_browser_evidence": browser_evidence(),
                }
            )
            write_state(root, state)
            payload = production_payload()
            payload["prototype_contract_hash"] = contract["contract_sha256"]

            result = workflow.record_prototype_production_conformance(payload)

            self.assertEqual(
                result["prototype_production_conformance"]["status"], "passed"
            )
            self.assertTrue(
                (root / ".product-delivery/artifacts/prototype-production-conformance.md").is_file()
            )
            transitions = result.get("transition_journal", {}).get("events", [])
            self.assertTrue(
                any(
                    event.get("transition_name")
                    == "prototype_production_conformance_recorded"
                    for event in transitions
                )
            )

    def test_prototype_feedback_stales_production_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_project(root)
            workflow = ProductDeliveryWorkflow(root)
            workflow.start(feature_slug="v1.0.16-prototype-conformance", multi_agent_mode="spawned_subagents_authorized")
            state = load_state(root)
            state.update(
                {
                    "project_type": "ui",
                    "ui_prototype": {
                        "confirmed_by_user": True,
                        "reviewed_by_agent": True,
                    },
                    "prototype_production_conformance": {
                        "status": "passed",
                        "evidence_sha256": "evidence-sha",
                    },
                }
            )
            write_state(root, state)

            result = workflow.record_ui_prototype_feedback(
                "课程表必须保留在系列详情主路径",
                "docs/prototypes/v143.html",
            )

            self.assertEqual(
                result["prototype_production_conformance"]["status"], "stale"
            )

    def test_ui_pre_closure_requires_production_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.status()
            state["prototype_production_conformance"] = {
                "status": "missing",
                "records": [],
            }
            write_state(root, state)

            with self.assertRaises(GatekeeperError) as caught:
                assert_pre_closure_ready(
                    workflow.status(),
                    valid_closure_artifact(),
                    root,
                )

            self.assertIn("prototype_production_conformance", str(caught.exception))

    def test_ui_pre_closure_requires_current_ui_conformance_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.status()
            state["multi_agent_reviews"]["ui_conformance"] = {
                "status": "missing",
                "artifact": None,
            }
            write_state(root, state)

            with self.assertRaises(GatekeeperError) as caught:
                assert_pre_closure_ready(
                    workflow.status(),
                    valid_closure_artifact(),
                    root,
                )

            self.assertIn("multi_agent_ui_conformance_review", str(caught.exception))

    def test_ui_pre_closure_revalidates_recorded_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.status()
            screenshot_path = state["prototype_production_conformance"]["records"][0][
                "production_screenshot_path"
            ]
            write_png(root / screenshot_path, width=1024, height=768)

            with self.assertRaises(GatekeeperError) as caught:
                assert_pre_closure_ready(
                    workflow.status(),
                    valid_closure_artifact(),
                    root,
                )

            self.assertIn("production screenshot", str(caught.exception))

    def test_ui_pre_closure_revalidates_semantic_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.status()
            snapshot_path = state["prototype_production_conformance"]["records"][0][
                "semantic_snapshot_path"
            ]
            snapshot = json.loads((root / snapshot_path).read_text(encoding="utf-8"))
            snapshot["regions"][0]["visible"] = False
            (root / snapshot_path).write_text(json.dumps(snapshot), encoding="utf-8")

            with self.assertRaises(GatekeeperError) as caught:
                assert_pre_closure_ready(
                    workflow.status(),
                    valid_closure_artifact(),
                    root,
                )

            self.assertIn("semantic snapshot", str(caught.exception))

    def test_ui_closure_must_bind_canonical_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)

            with self.assertRaises(GatekeeperError) as caught:
                assert_pre_closure_ready(
                    workflow.status(),
                    valid_closure_artifact(),
                    root,
                )

            self.assertIn("prototype_conformance", str(caught.exception))

    def test_ui_conformance_review_routes_to_closure_when_test_review_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))

            self.assertEqual(
                workflow.status()["next_gate"],
                "feature_closure_after_implementation",
            )

    def test_legacy_terminal_closure_remains_read_only_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.record_feature_closure(
                valid_closure_artifact(workflow.status())
            )
            state["closure_validation"]["canonical_schema_version"] = "v0.10"
            state["closure_validation"]["plugin_version"] = "1.0.15"
            state_path = root / ARTIFACT_ROOT / "state.json"
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            loaded = load_state(root)

            self.assertEqual(loaded["status"], "closed")
            self.assertEqual(
                loaded["closure_validation"]["canonical_schema_version"],
                "v0.10",
            )

    def test_reopened_legacy_closure_requires_v011(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.record_feature_closure(
                valid_closure_artifact(workflow.status())
            )
            state["status"] = "scope_revision"
            state["closure_validation"]["canonical_schema_version"] = "v0.10"
            state["closure_validation"]["plugin_version"] = "1.0.15"
            state_path = root / ARTIFACT_ROOT / "state.json"
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            loaded = load_state(root)

            self.assertEqual(loaded["status"], "closure_failed")
            self.assertIn(
                "canonical_closure_schema_version",
                loaded["closure_validation"]["errors"],
            )

    def test_v011_terminal_state_missing_conformance_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            state = workflow.record_feature_closure(
                valid_closure_artifact(workflow.status())
            )
            state.pop("prototype_production_conformance")
            state_path = root / ARTIFACT_ROOT / "state.json"
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            loaded = load_state(root)

            self.assertEqual(loaded["status"], "closure_failed")
            self.assertIn(
                "prototype_production_conformance.status=passed",
                loaded["closure_validation"]["errors"],
            )


if __name__ == "__main__":
    unittest.main()
