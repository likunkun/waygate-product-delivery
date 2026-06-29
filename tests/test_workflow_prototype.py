import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


def ui_review_payload():
    return {
        "prototype_path": "prototype/index.html",
        "pages": ["dashboard"],
        "states": ["empty", "loading", "error", "success"],
        "journeys": ["teacher creates classroom"],
        "taxonomy": {
            "roles": ["teacher"],
            "main_paths": ["teacher creates classroom"],
            "exceptions": ["duplicate classroom name"],
            "recovery": ["retry after network failure"],
            "permissions": ["teacher cannot access admin settings"],
            "long_tasks": ["bulk import progress"],
            "mobile": ["375px layout"],
            "keyboard": ["tab through primary actions"],
            "negative_scope_boundaries": ["student billing is absent"],
        },
        "limitations": ["static fixture data"],
        "browser_e2e_candidates": ["teacher creates classroom"],
        "negative_scope_guard_candidates": ["student billing is absent"],
    }


class WorkflowPrototypeTests(unittest.TestCase):
    def test_start_status_pause_resume_and_stop_preserve_state_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)

            started = workflow.start(feature_slug="v2.4-ops-security-alerts")
            self.assertTrue(started["active"])
            self.assertFalse(started["paused"])
            self.assertEqual(started["stage"], "product_blueprint")
            self.assertTrue(started["intervention_enabled"])
            self.assertEqual(started["feature_slug"], "v2.4-ops-security-alerts")
            self.assertIn("active_mode_startup", started["required_skill_gates"])
            self.assertEqual(
                started["required_skill_gates"]["active_mode_startup"],
                [
                    "superpowers:using-superpowers",
                    "planning-with-files",
                    "waygate-product-delivery",
                ],
            )
            self.assertIn("planning_files_ready", started["blocked_until"])
            self.assertIn("open_spec_current_feature", started["blocked_until"])
            self.assertIn("project_type_decision", started["blocked_until"])
            self.assertIn(
                "docs/open-spec/v2.4-ops-security-alerts/",
                started["required_artifacts"],
            )

            artifact = project_root / ARTIFACT_ROOT / "artifacts" / "note.md"
            artifact.write_text("preserve\n", encoding="utf-8")

            paused = workflow.pause()
            self.assertTrue(paused["active"])
            self.assertTrue(paused["paused"])
            self.assertEqual(paused["stage"], "product_blueprint")

            resumed = ProductDeliveryWorkflow(project_root).resume()
            self.assertTrue(resumed["active"])
            self.assertFalse(resumed["paused"])
            self.assertEqual(resumed["stage"], "product_blueprint")

            stopped = workflow.stop()
            self.assertFalse(stopped["active"])
            self.assertFalse(stopped["intervention_enabled"])
            self.assertEqual(artifact.read_text(encoding="utf-8"), "preserve\n")

    def test_ui_project_routes_to_prototype_confirmation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()

            status = workflow.select_project_type("ui")

            self.assertEqual(status["project_type"], "ui")
            self.assertEqual(status["stage"], "ui_prototype_confirmation")
            self.assertEqual(status["next_gate"], "ui_prototype_review")
            self.assertNotEqual(status["next_gate"], "non_ui_behavior_contract")
            self.assertIn("ui_html_prototype_confirmation", status["blocked_until"])

    def test_non_ui_project_routes_to_behavior_contract_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()

            status = workflow.select_project_type("non_ui")

            self.assertEqual(status["project_type"], "non_ui")
            self.assertEqual(status["stage"], "non_ui_behavior_contract_confirmation")
            self.assertEqual(status["next_gate"], "non_ui_behavior_contract")
            self.assertNotEqual(status["next_gate"], "ui_prototype_review")
            self.assertIn(
                "non_ui_behavior_contract_confirmation",
                status["blocked_until"],
            )

    def test_confirmation_gates_prepare_audit_and_handoff_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            prototype = project_root / "prototype" / "index.html"
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text("<html>prototype</html>", encoding="utf-8")
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")
            workflow.confirm("product_brief")
            workflow.confirm("version_scope")
            state = workflow.record_ui_prototype_review(ui_review_payload())
            pending = state["pending_confirmations"]["ui_prototype"]
            workflow.confirm_ui_prototype(
                "确认本地 HTML 原型符合预期",
                "prototype/index.html",
                nonce=pending["nonce"],
            )

            status = workflow.prepare_audit_and_handoff_drafts()

            self.assertEqual(status["stage"], "handoff_draft_ready")
            audit = project_root / ARTIFACT_ROOT / "artifacts" / "test-coverage-audit.md"
            handoff = project_root / ARTIFACT_ROOT / "artifacts" / "handoff.md"
            self.assertTrue(audit.is_file())
            self.assertTrue(handoff.is_file())
            self.assertIn("Test Coverage Audit", audit.read_text(encoding="utf-8"))
            self.assertIn("Codex Goal Handoff Draft", handoff.read_text(encoding="utf-8"))

    def test_missing_confirmation_blocks_audit_and_handoff_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()
            workflow.select_project_type("non_ui")
            workflow.confirm("product_brief")

            with self.assertRaises(WorkflowError):
                workflow.prepare_audit_and_handoff_drafts()

    def test_resume_prefers_disk_state_over_chat_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            workflow.start()
            workflow.select_project_type("ui")

            recovered = ProductDeliveryWorkflow(
                project_root,
                fallback_state={"stage": "chat_only", "project_type": "non_ui"},
            ).status()

            self.assertEqual(recovered["stage"], "ui_prototype_confirmation")
            self.assertEqual(load_state(project_root)["stage"], "ui_prototype_confirmation")


if __name__ == "__main__":
    unittest.main()
