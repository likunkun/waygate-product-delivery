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
from product_delivery_agent.workflow import ProductDeliveryWorkflow
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
