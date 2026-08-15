import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.implementation_baseline import (
    DEFAULT_VISUAL_POLICY,
    ImplementationBaselineError,
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
    multi_agent_review,
    scenario_row,
    ui_review_payload,
    workflow_ready_for_handoff,
)


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


if __name__ == "__main__":
    unittest.main()
