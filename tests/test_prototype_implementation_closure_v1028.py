import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.implementation_baseline import (
    DEFAULT_VISUAL_POLICY,
    ImplementationBaselineError,
    build_implementation_baseline,
    normalize_visual_policy,
)
from product_delivery_agent.prototype_design import build_prototype_design_bundle
from product_delivery_agent.ui_prototype import build_prototype_contract
from tests.conformance_fixtures import (
    prototype_contract,
    prototype_design_bundle_payload,
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
