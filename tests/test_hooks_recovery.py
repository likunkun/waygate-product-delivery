import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT
from product_delivery_agent.hooks import (
    build_prompt_context,
    build_resume_context,
    check_pre_compaction,
    check_stop_guardrail,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow


class HooksRecoveryTests(unittest.TestCase):
    def test_resume_context_summarizes_active_state_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")
            workflow.record_skill_use(
                "ui_prototype_confirmation",
                ["ui-ux-pro-max"],
            )

            result = build_resume_context(project_root)

            self.assertTrue(result.active)
            self.assertFalse(result.silent)
            self.assertIn("stage=ui_prototype_confirmation", result.message)
            self.assertIn("project_type=ui", result.message)
            self.assertIn("next_gate=ui_prototype_review", result.message)
            self.assertIn("ui_prototype_confirmation", result.message)

    def test_prompt_context_adds_current_stage_for_active_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("non_ui")

            result = build_prompt_context(project_root)

            self.assertTrue(result.active)
            self.assertIn(
                "current_stage=non_ui_behavior_contract_confirmation",
                result.message,
            )
            self.assertIn("next_gate=non_ui_behavior_contract", result.message)

    def test_pre_compaction_requires_valid_written_state_for_active_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            ProductDeliveryWorkflow(project_root).start()

            ok_result = check_pre_compaction(project_root)
            self.assertTrue(ok_result.passed)
            self.assertEqual(ok_result.missing_items, [])

            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.write_text("{invalid json", encoding="utf-8")

            failed_result = check_pre_compaction(project_root)
            self.assertFalse(failed_result.passed)
            self.assertIn("state.json valid JSON", failed_result.missing_items)

    def test_pre_compaction_reports_missing_and_incomplete_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()

            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.unlink()
            missing_result = check_pre_compaction(project_root)
            self.assertFalse(missing_result.passed)
            self.assertIn("state.json", missing_result.missing_items)

            workflow.start()
            state_path.write_text(
                state_path.read_text("utf-8").replace('"updated_at":', '"missing_updated_at":'),
                encoding="utf-8",
            )
            incomplete_result = check_pre_compaction(project_root)
            self.assertFalse(incomplete_result.passed)
            self.assertIn("state.updated_at", incomplete_result.missing_items)

    def test_stop_guardrail_reports_missing_project_artifacts_and_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")
            workflow.confirm("product_brief")

            result = check_stop_guardrail(project_root)

            self.assertTrue(result.active)
            self.assertFalse(result.passed)
            self.assertIn("confirmation:version_scope", result.missing_items)
            self.assertIn("confirmation:ui_prototype_review", result.missing_items)
            self.assertIn("artifact:version_scope", result.missing_items)
            self.assertIn("artifact:ui_prototype_review", result.missing_items)

    def test_stop_guardrail_uses_non_ui_branch_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.confirm("product_brief")

            result = check_stop_guardrail(project_root)

            self.assertFalse(result.passed)
            self.assertIn("confirmation:version_scope", result.missing_items)
            self.assertIn("confirmation:non_ui_behavior_contract", result.missing_items)
            self.assertIn("artifact:version_scope", result.missing_items)
            self.assertIn("artifact:non_ui_behavior_contract", result.missing_items)

    def test_inactive_projects_are_silent_for_all_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.stop()

            for hook_result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_pre_compaction(project_root),
                check_stop_guardrail(project_root),
            ):
                self.assertFalse(hook_result.active)
                self.assertTrue(hook_result.silent)
                self.assertEqual(hook_result.message, "")
                self.assertEqual(hook_result.warnings, [])


if __name__ == "__main__":
    unittest.main()
