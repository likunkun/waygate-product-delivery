import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import load_state
from product_delivery_agent.skill_gates import (
    SkillGateError,
    required_skills_for_stage,
    validate_skill_gate,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow


class SkillGateTests(unittest.TestCase):
    def test_stage_allocations_include_waygate_baseline_skills(self):
        self.assertEqual(
            required_skills_for_stage("active_mode_startup"),
            [
                "superpowers:using-superpowers",
                "planning-with-files",
                "waygate-product-delivery",
            ],
        )
        self.assertIn(
            "superpowers:using-superpowers",
            required_skills_for_stage("agent_startup"),
        )
        self.assertIn(
            "superpowers:brainstorming",
            required_skills_for_stage("product_blueprint"),
        )
        self.assertIn(
            "superpowers:brainstorming",
            required_skills_for_stage("version_scope"),
        )
        self.assertIn(
            "ui-ux-pro-max",
            required_skills_for_stage("ui_prototype_confirmation"),
        )

    def test_test_coverage_audit_accepts_either_test_strategy_skill(self):
        first = validate_skill_gate("test_coverage_audit", ["test-strategy"])
        second = validate_skill_gate("test_coverage_audit", ["testing-strategy"])

        self.assertTrue(first.passed)
        self.assertTrue(second.passed)

    def test_missing_required_stage_skill_fails_gate(self):
        result = validate_skill_gate("product_blueprint", [])

        self.assertFalse(result.passed)
        self.assertIn("superpowers:brainstorming", result.missing_skills)

    def test_file_specific_skills_are_conditional_on_file_types(self):
        result = validate_skill_gate(
            "product_blueprint",
            ["superpowers:brainstorming", "pdf", "docx", "pptx"],
            file_paths=["brief.md", "source.pdf", "contract.docx", "deck.pptx"],
        )
        markdown_only = validate_skill_gate(
            "product_blueprint",
            ["superpowers:brainstorming"],
            file_paths=["brief.md"],
        )

        self.assertTrue(result.passed)
        self.assertIn("pdf", result.required_skills)
        self.assertIn("docx", result.required_skills)
        self.assertIn("pptx", result.required_skills)
        self.assertTrue(markdown_only.passed)
        self.assertNotIn("pdf", markdown_only.required_skills)
        self.assertNotIn("docx", markdown_only.required_skills)
        self.assertNotIn("pptx", markdown_only.required_skills)

    def test_active_mode_startup_requires_planning_with_files(self):
        result = validate_skill_gate(
            "active_mode_startup",
            ["superpowers:using-superpowers", "waygate-product-delivery"],
        )

        self.assertFalse(result.passed)
        self.assertIn("planning-with-files", result.missing_skills)

    def test_open_spec_planning_requires_open_spec_skill(self):
        result = validate_skill_gate("open_spec_planning", [])

        self.assertFalse(result.passed)
        self.assertIn("open-spec", result.missing_skills)

    def test_feature_closure_requires_closure_and_verification_skills(self):
        result = validate_skill_gate(
            "feature_closure",
            ["superpowers:verification-before-completion"],
        )

        self.assertFalse(result.passed)
        self.assertIn("open-spec-feature-closure", result.missing_skills)

    def test_workflow_records_reviewable_skill_gate_result_in_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start(multi_agent_mode="spawned_subagents_authorized")

            status = workflow.record_skill_use(
                "product_blueprint",
                ["superpowers:brainstorming"],
            )

            self.assertTrue(status["skill_records"]["product_blueprint"]["passed"])
            state = load_state(project_root)
            self.assertEqual(
                state["skill_records"]["product_blueprint"]["used_skills"],
                ["superpowers:brainstorming"],
            )

    def test_workflow_blocks_failed_skill_gate_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(multi_agent_mode="spawned_subagents_authorized")

            with self.assertRaises(SkillGateError):
                workflow.record_skill_use("ui_prototype_confirmation", [])


if __name__ == "__main__":
    unittest.main()
