import json
import struct
import tempfile
import unittest
import zlib
from copy import deepcopy
from pathlib import Path

from product_delivery_agent.evidence_artifacts import sha256_file
from product_delivery_agent.implementation_baseline import (
    DEFAULT_VISUAL_POLICY,
    ImplementationBaselineError,
    build_task_prototype_conformance,
    build_implementation_baseline,
    implementation_baseline_required,
    normalize_visual_policy,
)
from product_delivery_agent.prototype_design import build_prototype_design_bundle
from product_delivery_agent.ui_prototype import build_prototype_contract
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import (
    confirm_product_baseline,
    prototype_contract,
    prototype_design_bundle_payload,
    record_bundled_ui_prototype_review,
)
from tests.test_goal_driven_closure_v104 import (
    activate_host_goal,
    multi_agent_review,
    reconcile_host_goal,
    scenario_row,
    task_completion_artifact,
    ui_review_payload,
    workflow_ready_for_handoff,
)


def _paeth(left, above, upper_left):
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _write_rgba_png(path: Path, rows, *, filter_types=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    height = len(rows)
    width = len(rows[0])
    raw_rows = [bytes(channel for pixel in row for channel in pixel) for row in rows]
    filters = list(filter_types or [0] * height)
    encoded_rows = []
    previous = bytes(width * 4)
    for raw, filter_type in zip(raw_rows, filters):
        filtered = bytearray()
        for index, value in enumerate(raw):
            left = raw[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                raise ValueError("unsupported test PNG filter")
            filtered.append((value - predictor) & 0xFF)
        encoded_rows.append(bytes([filter_type]) + bytes(filtered))
        previous = raw

    def chunk(kind, data):
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(b"".join(encoded_rows)))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class PrototypeImplementationBaselineV1028Tests(unittest.TestCase):
    def build_inputs(self, root: Path):
        raw_contract = prototype_contract()
        payload = prototype_design_bundle_payload(root, contract=raw_contract)
        canonical_contract = build_prototype_contract(root, raw_contract)
        bundle = build_prototype_design_bundle(
            root,
            payload,
            prototype_contract=canonical_contract,
        )
        return bundle, canonical_contract

    def test_builds_units_from_confirmed_bundle_runtime_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle, contract = self.build_inputs(root)

            baseline = build_implementation_baseline(
                root,
                bundle,
                contract,
            )

            self.assertEqual(baseline["status"], "ready")
            self.assertEqual(baseline["baseline_version"], "v1")
            self.assertEqual(
                baseline["product_domain_sha256"],
                bundle["product_domain_sha256"],
            )
            self.assertEqual(
                baseline["prototype_contract_sha256"],
                contract["contract_sha256"],
            )
            self.assertRegex(baseline["baseline_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(len(baseline["units"]), 1)
            unit = baseline["units"][0]
            self.assertEqual(unit["surface_id"], "primary-surface")
            self.assertEqual(unit["state_id"], "ready")
            self.assertEqual(unit["viewport_class"], "desktop")
            self.assertEqual(unit["route"], "/customer/course-production")
            self.assertEqual(unit["region_ids"], ["primary-region"])
            self.assertEqual(unit["interaction_ids"], ["primary-action"])
            self.assertEqual(
                unit["prototype_screenshot_path"],
                bundle["clean_surface"]["runtime_checks"][0][
                    "clean_screenshot_path"
                ],
            )
            self.assertEqual(unit["prototype_regions"][0]["region_id"], "primary-region")
            self.assertEqual(unit["prototype_regions"][0]["bounds"]["width"], 1280)

    def test_default_visual_policy_is_stable_and_strict(self):
        contract = prototype_contract()

        policy = normalize_visual_policy(None, contract)

        self.assertEqual(policy, DEFAULT_VISUAL_POLICY)
        self.assertEqual(policy["critical_region_max_diff_ratio"], 0.02)
        self.assertEqual(policy["full_surface_max_diff_ratio"], 0.05)
        self.assertEqual(policy["pixel_threshold"], 0.2)
        self.assertEqual(policy["geometry_tolerance_px"], 4)
        self.assertEqual(policy["geometry_tolerance_viewport_ratio"], 0.01)
        self.assertEqual(policy["dynamic_masks"], [])

    def test_visual_policy_allows_stricter_thresholds_and_known_masks(self):
        contract = prototype_contract()

        policy = normalize_visual_policy(
            {
                "critical_region_max_diff_ratio": 0.01,
                "full_surface_max_diff_ratio": 0.03,
                "pixel_threshold": 0.1,
                "geometry_tolerance_px": 2,
                "geometry_tolerance_viewport_ratio": 0.005,
                "dynamic_masks": [
                    {
                        "surface_id": "primary-surface",
                        "state_id": "ready",
                        "viewport_class": "desktop",
                        "region_ids": ["primary-region"],
                    }
                ],
            },
            contract,
        )

        self.assertEqual(policy["critical_region_max_diff_ratio"], 0.01)
        self.assertEqual(policy["dynamic_masks"][0]["region_ids"], ["primary-region"])

    def test_visual_policy_rejects_relaxed_thresholds(self):
        contract = prototype_contract()

        with self.assertRaisesRegex(
            ImplementationBaselineError,
            "cannot be relaxed",
        ):
            normalize_visual_policy(
                {"full_surface_max_diff_ratio": 0.08},
                contract,
            )


class PrototypeImplementationBaselineWorkflowV1028Tests(unittest.TestCase):
    def ready_ui_workflow(self, root: Path) -> ProductDeliveryWorkflow:
        workflow = ProductDeliveryWorkflow(root)
        workflow.start(
            feature_slug="v1.0.28-prototype-driven-implementation",
            multi_agent_mode="spawned_subagents_authorized",
        )
        workflow.record_scenario_matrix([scenario_row()])
        workflow.select_project_type("ui")
        review = ui_review_payload("docs/prototypes/v1028-prototype.html")
        record_bundled_ui_prototype_review(workflow, root, review)
        return workflow

    def test_new_ui_confirmation_writes_implementation_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.ready_ui_workflow(root)

            state = confirm_product_baseline(
                workflow,
                multi_agent_review("scenario"),
            )

            baseline = state["implementation_baseline"]
            self.assertEqual(baseline["status"], "ready")
            self.assertRegex(baseline["baseline_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                baseline["product_domain_sha256"],
                state["prototype_design_bundle"]["product_domain_sha256"],
            )
            self.assertEqual(
                baseline["artifact_path"],
                "artifacts/implementation-baseline.json",
            )
            self.assertTrue(
                (
                    root
                    / ".product-delivery/artifacts/implementation-baseline.json"
                ).is_file()
            )

    def test_visual_policy_is_frozen_into_product_confirmation_and_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.ready_ui_workflow(root)

            state = workflow.record_implementation_visual_policy(
                {
                    "full_surface_max_diff_ratio": 0.03,
                    "critical_region_max_diff_ratio": 0.01,
                }
            )
            self.assertEqual(
                state["implementation_visual_policy"][
                    "full_surface_max_diff_ratio"
                ],
                0.03,
            )
            state = confirm_product_baseline(
                workflow,
                multi_agent_review("scenario"),
            )

            self.assertEqual(
                state["implementation_baseline"]["visual_policy"][
                    "full_surface_max_diff_ratio"
                ],
                0.03,
            )
            confirmation = state["user_confirmations"]["product_baseline"]
            self.assertEqual(
                confirmation["implementation_visual_policy_sha256"],
                state["implementation_baseline"]["visual_policy_sha256"],
            )

    def test_visual_policy_cannot_change_after_product_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = self.ready_ui_workflow(root)
            confirm_product_baseline(workflow, multi_agent_review("scenario"))

            with self.assertRaisesRegex(Exception, "reopen product baseline"):
                workflow.record_implementation_visual_policy(
                    {"full_surface_max_diff_ratio": 0.03}
                )

    def test_non_ui_delivery_marks_implementation_baseline_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(tmp)
            workflow.start(
                feature_slug="v1.0.28-non-ui",
                multi_agent_mode="spawned_subagents_authorized",
            )

            state = workflow.select_project_type("non_ui")

            self.assertEqual(
                state["implementation_baseline_policy"]["status"],
                "not_applicable",
            )
            self.assertFalse(implementation_baseline_required(state))

    def test_confirmed_legacy_ui_without_policy_is_grandfathered(self):
        legacy_state = {
            "project_type": "ui",
            "ui_prototype": {"confirmed_by_user": True},
            "user_confirmations": {
                "product_baseline": {"decision": "approved"}
            },
        }

        self.assertFalse(implementation_baseline_required(legacy_state))


class PrototypeBoundTaskAndPromptV1028Tests(unittest.TestCase):
    @staticmethod
    def generic_task():
        return {
            "task_id": "TASK-001",
            "title": "Implement the confirmed UI",
            "description": "Implement the user-visible primary surface.",
            "verification": "pytest",
        }

    @classmethod
    def bound_task(cls, state):
        unit = state["implementation_baseline"]["units"][0]
        return {
            **cls.generic_task(),
            "ui_impact": "prototype_bound",
            "prototype_bindings": [
                {
                    "surface_id": unit["surface_id"],
                    "state_id": unit["state_id"],
                    "viewport_classes": [unit["viewport_class"]],
                    "region_ids": list(unit["region_ids"]),
                    "interaction_ids": list(unit["interaction_ids"]),
                }
            ],
        }

    def test_new_ui_explicit_task_without_binding_blocks_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = workflow_ready_for_handoff(Path(tmp))

            with self.assertRaisesRegex(WorkflowError, "prototype_bindings"):
                workflow.record_implementation_launch_authorization(
                    scope="Implement the confirmed UI",
                    verification_commands=["pytest"],
                    planned_tasks=[self.generic_task()],
                )

    def test_non_visual_task_requires_an_explicit_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = workflow_ready_for_handoff(Path(tmp))
            task = {
                **self.generic_task(),
                "ui_impact": "none",
                "prototype_bindings": [],
            }

            with self.assertRaisesRegex(WorkflowError, "ui_impact_reason"):
                workflow.record_implementation_launch_authorization(
                    scope="Implement supporting code",
                    verification_commands=["pytest"],
                    planned_tasks=[task],
                )

    def test_handoff_writes_baseline_bound_goal_and_current_task_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = workflow_ready_for_handoff(root)
            task = self.bound_task(workflow.status())
            workflow.record_implementation_launch_authorization(
                scope="Implement the confirmed UI",
                verification_commands=["pytest"],
                planned_tasks=[task],
            )

            state = workflow.generate_codex_goal_handoff(
                scope="Implement the confirmed UI",
                verification_commands=["pytest"],
                planned_tasks=[task],
            )

            baseline_hash = state["implementation_baseline"]["baseline_sha256"]
            self.assertIn(baseline_hash, state["codex_goal_prompt"])
            self.assertIn("不是在重新设计", state["codex_goal_prompt"])
            self.assertIn("primary-surface", state["current_task_prompt"])
            self.assertIn("primary-region", state["current_task_prompt"])
            self.assertEqual(
                state["current_task_prompt_path"],
                "artifacts/current-task-prompt.md",
            )
            self.assertTrue(
                (
                    root
                    / ".product-delivery/artifacts/current-task-prompt.md"
                ).is_file()
            )

    def test_current_task_prompt_excludes_unbound_baseline_units(self):
        from product_delivery_agent.handoff import render_current_task_prompt

        task = {
            **self.generic_task(),
            "ui_impact": "prototype_bound",
            "prototype_bindings": [
                {
                    "surface_id": "bound-surface",
                    "state_id": "ready",
                    "viewport_classes": ["desktop"],
                    "region_ids": ["bound-region"],
                    "interaction_ids": ["bound-action"],
                }
            ],
        }
        baseline = {
            "baseline_sha256": "a" * 64,
            "prototype_path": "docs/prototype.html",
            "visual_policy_sha256": "b" * 64,
            "units": [
                {
                    "surface_id": "bound-surface",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "route": "/bound",
                    "prototype_screenshot_path": "bound.png",
                    "region_ids": ["bound-region"],
                    "interaction_ids": ["bound-action"],
                },
                {
                    "surface_id": "unrelated-settings-surface",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "route": "/settings",
                    "prototype_screenshot_path": "settings.png",
                    "region_ids": ["settings-region"],
                    "interaction_ids": ["settings-action"],
                },
            ],
        }

        prompt = render_current_task_prompt(task, baseline)

        self.assertIn("bound-surface", prompt)
        self.assertNotIn("unrelated-settings-surface", prompt)

    def test_visual_policy_rejects_unknown_mask_regions(self):
        contract = prototype_contract()

        with self.assertRaisesRegex(
            ImplementationBaselineError,
            "unknown region",
        ):
            normalize_visual_policy(
                {
                    "dynamic_masks": [
                        {
                            "surface_id": "primary-surface",
                            "state_id": "ready",
                            "viewport_class": "desktop",
                            "region_ids": ["missing-region"],
                        }
                    ]
                },
                contract,
            )


class TaskPrototypeConformanceV1028Tests(unittest.TestCase):
    @staticmethod
    def _white_rows(width=10, height=5):
        return [[(255, 255, 255, 255) for _ in range(width)] for _ in range(height)]

    def build_domain_fixture(self, root: Path, *, production_filters=None):
        prototype_path = root / ".product-delivery/artifacts/prototype-reference.png"
        production_path = root / ".product-delivery/artifacts/production-current.png"
        rows = self._white_rows()
        _write_rgba_png(prototype_path, rows)
        _write_rgba_png(
            production_path,
            rows,
            filter_types=production_filters,
        )
        snapshot_path = root / ".product-delivery/artifacts/production-semantic.json"
        snapshot = {
            "schema_version": "task-production-semantic-snapshot-v1",
            "surface_id": "bound-surface",
            "state_id": "ready",
            "route": "/bound",
            "viewport": {"class": "desktop", "width": 10, "height": 5},
            "regions": [
                {
                    "region_id": "root",
                    "matched_count": 1,
                    "visible": True,
                    "role": "main",
                    "accessible_name": "Bound surface",
                    "parent_region_id": None,
                    "display_order": 1,
                    "bounding_box": {"x": 0, "y": 0, "width": 10, "height": 5},
                    "key_controls": ["submit"],
                    "interaction_state": "ready",
                },
                {
                    "region_id": "action",
                    "matched_count": 1,
                    "visible": True,
                    "role": "button",
                    "accessible_name": "Submit changes",
                    "parent_region_id": "root",
                    "display_order": 2,
                    "bounding_box": {"x": 4, "y": 2, "width": 2, "height": 2},
                    "key_controls": ["submit"],
                    "interaction_state": "ready",
                },
            ],
            "relationships": [
                {
                    "source_region_id": "root",
                    "relation": "contains",
                    "target_region_id": "action",
                    "observed": True,
                }
            ],
            "interactions": [
                {
                    "interaction_id": "submit",
                    "observed": True,
                    "relation": "updates",
                    "target_region_id": "root",
                    "result": "The bound surface is updated.",
                }
            ],
        }
        _write_json(snapshot_path, snapshot)
        unit = {
            "surface_id": "bound-surface",
            "state_id": "ready",
            "viewport_class": "desktop",
            "route": "/bound",
            "prototype_screenshot_path": str(prototype_path.relative_to(root)),
            "prototype_screenshot_sha256": sha256_file(prototype_path),
            "prototype_screenshot_width": 10,
            "prototype_screenshot_height": 5,
            "region_ids": ["root", "action"],
            "interaction_ids": ["submit"],
            "critical_regions": [
                {
                    "region_id": "root",
                    "semantic_role": "main",
                    "accessible_name_match": {"mode": "contains", "value": "Bound"},
                    "visibility": "visible",
                },
                {
                    "region_id": "action",
                    "semantic_role": "button",
                    "accessible_name_match": {"mode": "exact", "value": "Submit changes"},
                    "visibility": "visible",
                    "parent_region_id": "root",
                    "display_order": 2,
                },
            ],
            "critical_relationships": [
                {
                    "source_region_id": "root",
                    "relation": "contains",
                    "target_region_id": "action",
                }
            ],
            "critical_interactions": [
                {
                    "interaction_id": "submit",
                    "entry_region_id": "action",
                    "action": "submit changes",
                    "expected_relation": "updates",
                    "target_region_id": "root",
                }
            ],
            "prototype_regions": [
                {
                    "region_id": "root",
                    "semantic_role": "main",
                    "accessible_name": "Bound surface",
                    "visibility": "visible",
                    "display_order": 1,
                    "bounds": {"x": 0, "y": 0, "width": 10, "height": 5},
                    "controls": ["submit"],
                    "interaction_state": "ready",
                },
                {
                    "region_id": "action",
                    "semantic_role": "button",
                    "accessible_name": "Submit changes",
                    "visibility": "visible",
                    "parent_region_id": "root",
                    "display_order": 2,
                    "bounds": {"x": 4, "y": 2, "width": 2, "height": 2},
                    "controls": ["submit"],
                    "interaction_state": "ready",
                },
            ],
            "dynamic_mask_region_ids": [],
        }
        baseline = {
            "status": "ready",
            "baseline_sha256": "a" * 64,
            "visual_policy_sha256": "b" * 64,
            "visual_policy": deepcopy(DEFAULT_VISUAL_POLICY),
            "units": [unit],
        }
        task = {
            "task_id": "TASK-001",
            "title": "Implement bound action",
            "description": "Implement the action without redesigning it.",
            "verification": "pytest",
            "planned_task_hash": "c" * 64,
            "ui_impact": "prototype_bound",
            "prototype_bindings": [
                {
                    "surface_id": "bound-surface",
                    "state_id": "ready",
                    "viewport_classes": ["desktop"],
                    "region_ids": ["action"],
                    "interaction_ids": ["submit"],
                }
            ],
        }
        payload = {
            "implementation_baseline_sha256": baseline["baseline_sha256"],
            "planned_task_hash": task["planned_task_hash"],
            "environment_status": "stable",
            "records": [
                {
                    "surface_id": "bound-surface",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "production_route": "/bound",
                    "production_screenshot_path": str(production_path.relative_to(root)),
                    "semantic_snapshot_path": str(snapshot_path.relative_to(root)),
                    "computed_style_comparisons": [
                        {
                            "region_id": "action",
                            "prototype": {
                                "display": "inline-flex",
                                "font-size": "14px",
                            },
                            "production": {
                                "display": "inline-flex",
                                "font-size": "14px",
                            },
                        }
                    ],
                }
            ],
        }
        return baseline, task, payload, snapshot_path, production_path

    def test_matching_task_conformance_passes_and_decodes_all_png_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, task, payload, _, _ = self.build_domain_fixture(
                root,
                production_filters=[0, 1, 2, 3, 4],
            )

            evidence = build_task_prototype_conformance(
                root,
                payload,
                implementation_baseline=baseline,
                planned_task=task,
            )

            self.assertEqual(evidence["status"], "passed")
            self.assertEqual(evidence["failure_codes"], [])
            record = evidence["records"][0]
            self.assertEqual(record["full_surface_diff_ratio"], 0)
            self.assertEqual(record["critical_region_results"][0]["diff_ratio"], 0)
            self.assertRegex(evidence["evidence_sha256"], r"^[0-9a-f]{64}$")

    def test_contract_visual_and_evidence_failures_are_independently_reported(self):
        cases = (
            ("route_mismatch", "route_mismatch"),
            ("region_hierarchy_mismatch", "region_hierarchy_mismatch"),
            ("region_order_mismatch", "region_order_mismatch"),
            ("interaction_missing", "interaction_missing"),
            ("computed_style_mismatch", "computed_style_mismatch"),
            ("geometry_mismatch", "geometry_mismatch"),
            ("critical_region_pixel_diff", "critical_region_pixel_diff"),
            ("full_surface_pixel_diff", "full_surface_pixel_diff"),
            ("missing_evidence", "evidence_missing"),
        )
        for mutation, expected_code in cases:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                baseline, task, payload, snapshot_path, production_path = (
                    self.build_domain_fixture(root)
                )
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                action = next(
                    region for region in snapshot["regions"] if region["region_id"] == "action"
                )
                if mutation == "route_mismatch":
                    payload["records"][0]["production_route"] = "/redesigned"
                elif mutation == "region_hierarchy_mismatch":
                    action["parent_region_id"] = None
                elif mutation == "region_order_mismatch":
                    action["display_order"] = 3
                elif mutation == "interaction_missing":
                    snapshot["interactions"] = []
                elif mutation == "computed_style_mismatch":
                    payload["records"][0]["computed_style_comparisons"][0][
                        "production"
                    ]["display"] = "block"
                elif mutation == "geometry_mismatch":
                    action["bounding_box"] = {"x": 2, "y": 2, "width": 8, "height": 2}
                elif mutation == "critical_region_pixel_diff":
                    rows = self._white_rows()
                    rows[2][4] = (0, 0, 0, 255)
                    _write_rgba_png(production_path, rows)
                elif mutation == "full_surface_pixel_diff":
                    rows = self._white_rows()
                    for x in range(3):
                        rows[0][x] = (0, 0, 0, 255)
                    _write_rgba_png(production_path, rows)
                elif mutation == "missing_evidence":
                    payload["records"][0]["semantic_snapshot_path"] = (
                        ".product-delivery/artifacts/missing.json"
                    )
                if mutation in {
                    "region_hierarchy_mismatch",
                    "region_order_mismatch",
                    "interaction_missing",
                    "geometry_mismatch",
                }:
                    _write_json(snapshot_path, snapshot)

                evidence = build_task_prototype_conformance(
                    root,
                    payload,
                    implementation_baseline=baseline,
                    planned_task=task,
                )

                self.assertEqual(evidence["status"], "failed")
                self.assertIn(expected_code, evidence["failure_codes"])

    def test_unstable_capture_environment_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, task, payload, _, _ = self.build_domain_fixture(root)
            payload.update(
                {
                    "environment_status": "inconclusive",
                    "environment_reason": "browser renderer crashed during capture",
                    "records": [],
                }
            )

            evidence = build_task_prototype_conformance(
                root,
                payload,
                implementation_baseline=baseline,
                planned_task=task,
            )

            self.assertEqual(evidence["status"], "inconclusive")
            self.assertIn("environment_inconclusive", evidence["failure_codes"])

    def workflow_conformance_payload(self, root: Path, state):
        baseline = state["implementation_baseline"]
        task = state["delivery_goal"]["planned_tasks"][0]
        unit = baseline["units"][0]
        production_path = (
            root / ".product-delivery/artifacts/task-conformance/production.png"
        )
        production_path.parent.mkdir(parents=True, exist_ok=True)
        production_path.write_bytes((root / unit["prototype_screenshot_path"]).read_bytes())
        prototype_region = unit["prototype_regions"][0]
        snapshot_path = (
            root / ".product-delivery/artifacts/task-conformance/semantic.json"
        )
        _write_json(
            snapshot_path,
            {
                "schema_version": "task-production-semantic-snapshot-v1",
                "surface_id": unit["surface_id"],
                "state_id": unit["state_id"],
                "route": unit["route"],
                "viewport": {
                    "class": unit["viewport_class"],
                    "width": unit["prototype_screenshot_width"],
                    "height": unit["prototype_screenshot_height"],
                },
                "regions": [
                    {
                        "region_id": prototype_region["region_id"],
                        "matched_count": 1,
                        "visible": True,
                        "role": prototype_region["semantic_role"],
                        "accessible_name": prototype_region["accessible_name"],
                        "parent_region_id": prototype_region.get("parent_region_id"),
                        "display_order": prototype_region["display_order"],
                        "bounding_box": deepcopy(prototype_region["bounds"]),
                        "key_controls": list(prototype_region["controls"]),
                        "interaction_state": prototype_region["interaction_state"],
                    }
                ],
                "relationships": [
                    {**relationship, "observed": True}
                    for relationship in unit["critical_relationships"]
                ],
                "interactions": [
                    {
                        "interaction_id": interaction["interaction_id"],
                        "observed": True,
                        "relation": interaction["expected_relation"],
                        "target_region_id": interaction["target_region_id"],
                        "result": "The expected production state was observed.",
                    }
                    for interaction in unit["critical_interactions"]
                ],
            },
        )
        return {
            "implementation_baseline_sha256": baseline["baseline_sha256"],
            "planned_task_hash": task["planned_task_hash"],
            "environment_status": "stable",
            "records": [
                {
                    "surface_id": unit["surface_id"],
                    "state_id": unit["state_id"],
                    "viewport_class": unit["viewport_class"],
                    "production_route": unit["route"],
                    "production_screenshot_path": str(production_path.relative_to(root)),
                    "semantic_snapshot_path": str(snapshot_path.relative_to(root)),
                    "computed_style_comparisons": [
                        {
                            "region_id": region_id,
                            "prototype": {"display": "block"},
                            "production": {"display": "block"},
                        }
                        for region_id in task["prototype_bindings"][0]["region_ids"]
                    ],
                }
            ],
        }

    def test_functional_success_cannot_complete_bound_task_without_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            state = workflow.status()

            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "task prototype conformance"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(state, "TASK-001"),
                )

            reconcile_host_goal(workflow)
            current = workflow.status()
            inconclusive = workflow.record_task_prototype_conformance(
                "TASK-001",
                {
                    "implementation_baseline_sha256": current[
                        "implementation_baseline"
                    ]["baseline_sha256"],
                    "planned_task_hash": current["delivery_goal"]["planned_tasks"][
                        0
                    ]["planned_task_hash"],
                    "environment_status": "inconclusive",
                    "environment_reason": "browser renderer crashed during capture",
                    "records": [],
                },
            )
            self.assertEqual(
                inconclusive["task_prototype_conformance"]["records"]["TASK-001"][
                    "status"
                ],
                "inconclusive",
            )
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "task prototype conformance"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(
                        workflow.status(),
                        "TASK-001",
                    ),
                )

            reconcile_host_goal(workflow)
            conformance = workflow.record_task_prototype_conformance(
                "TASK-001",
                self.workflow_conformance_payload(root, workflow.status()),
            )
            self.assertEqual(
                conformance["task_prototype_conformance"]["records"]["TASK-001"][
                    "status"
                ],
                "passed",
            )

            reconcile_host_goal(workflow)
            completed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )

            self.assertEqual(
                completed["delivery_goal"]["completed_tasks"],
                ["TASK-001"],
            )
            self.assertIn("All planned TASKs are complete", completed["current_task_prompt"])
            self.assertTrue(
                any(
                    event["transition_name"]
                    == "task_prototype_conformance_recorded"
                    for event in completed["transition_journal"]["events"]
                )
            )


if __name__ == "__main__":
    unittest.main()
