import math
import unittest

from product_delivery_agent.implementation_baseline import (
    DEFAULT_VISUAL_POLICY,
    HARD_BLOCKING,
    _assess_geometry,
)


VIEWPORT = {"width": 1024, "height": 768}


class SharedOverflowGeometryV111Tests(unittest.TestCase):
    def assess(self, prototype, production, *, visible=True):
        return _assess_geometry(
            prototype,
            production,
            VIEWPORT,
            DEFAULT_VISUAL_POLICY,
            visible=visible,
        )

    def test_matching_bottom_overflow_uses_relative_geometry(self):
        result = self.assess(
            {"x": 248, "y": 79, "width": 752, "height": 783},
            {"x": 249, "y": 79, "width": 751, "height": 783},
        )

        self.assertEqual(result["classification"], "exact")
        self.assertIsNone(result["failure_class"])
        self.assertEqual(
            result["classification_reason"], "shared_viewport_overflow_within_tolerance"
        )
        self.assertEqual(result["prototype_viewport_overflow"]["bottom"], 94.0)
        self.assertEqual(result["viewport_overflow"]["bottom"], 94.0)

    def test_matching_top_and_bottom_overflow_uses_relative_geometry(self):
        result = self.assess(
            {"x": 248, "y": -782, "width": 752, "height": 1655},
            {"x": 250, "y": -783, "width": 750, "height": 1657},
        )

        self.assertEqual(result["classification"], "exact")
        self.assertEqual(
            {key for key, value in result["prototype_viewport_overflow"].items() if value},
            {"top", "bottom"},
        )
        self.assertEqual(
            {key for key, value in result["viewport_overflow"].items() if value},
            {"top", "bottom"},
        )

    def test_production_only_large_overflow_remains_hard_invalid(self):
        result = self.assess(
            {"x": 100, "y": 100, "width": 300, "height": 300},
            {"x": 100, "y": 100, "width": 300, "height": 900},
        )

        self.assertEqual(result["classification"], "hard_invalid")
        self.assertEqual(result["failure_class"], HARD_BLOCKING)
        self.assertNotEqual(
            result["classification_reason"], "shared_viewport_overflow_within_tolerance"
        )

    def test_shared_overflow_delta_beyond_tolerance_does_not_pass(self):
        result = self.assess(
            {"x": 248, "y": 79, "width": 752, "height": 783},
            {"x": 248, "y": 79, "width": 752, "height": 900},
        )

        self.assertNotEqual(result["classification"], "exact")
        self.assertIn(
            result["classification_reason"],
            {"geometry_delta_exceeds_tolerance", "outside_viewport_tolerance"},
        )

    def test_invalid_prototype_geometry_remains_hard_blocking(self):
        cases = (
            ({"x": 0, "y": 0, "width": math.nan, "height": 10}, "prototype_bounds_invalid"),
            ({"x": 0, "y": 0, "width": 0, "height": 10}, "prototype_non_positive_size"),
            ({"x": 2000, "y": 0, "width": 10, "height": 10}, "prototype_outside_viewport"),
        )
        production = {"x": 0, "y": 0, "width": 10, "height": 10}

        for prototype, reason in cases:
            with self.subTest(reason=reason):
                result = self.assess(prototype, production)
                self.assertEqual(result["classification"], "hard_invalid")
                self.assertEqual(result["failure_class"], HARD_BLOCKING)
                self.assertEqual(result["classification_reason"], reason)


if __name__ == "__main__":
    unittest.main()
