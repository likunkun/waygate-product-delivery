import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    CORE_ARTIFACTS,
    initialize_workspace,
    load_state,
    write_state,
)


class ArtifactProtocolTests(unittest.TestCase):
    def test_initialize_workspace_creates_artifact_root_state_and_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)

            state = initialize_workspace(project_root)

            workspace = project_root / ARTIFACT_ROOT
            self.assertTrue(workspace.is_dir())
            self.assertTrue((workspace / "state.json").is_file())
            self.assertTrue((workspace / "templates").is_dir())
            self.assertTrue((workspace / "artifacts").is_dir())
            self.assertEqual(state["stage"], "initialized")
            self.assertIsNone(state["project_type"])
            self.assertEqual(state["prototype_contract"]["status"], "missing")
            self.assertEqual(
                state["prototype_production_conformance"]["status"],
                "missing",
            )
            self.assertEqual(
                state["multi_agent_reviews"]["ui_conformance"]["status"],
                "missing",
            )
            self.assertEqual(
                state["multi_agent_policy"]["mode"],
                "authorization_pending",
            )
            self.assertEqual(state["pending_user_decisions"], {})

            for artifact_name, template_file in CORE_ARTIFACTS.items():
                self.assertTrue((workspace / "templates" / template_file).is_file())
                self.assertIn(artifact_name, state["confirmation_points"])
                self.assertIn(artifact_name, state["artifact_paths"])

    def test_state_records_required_responsibility_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = initialize_workspace(Path(tmp), project_type="ui")

            self.assertEqual(state["project_type"], "ui")
            self.assertIn("stage", state)
            self.assertIn("confirmation_points", state)
            self.assertIn("artifact_paths", state)
            self.assertIn("updated_at", state)
            self.assertEqual(
                set(state["confirmation_points"]),
                set(CORE_ARTIFACTS),
            )

    def test_load_state_prefers_disk_state_over_chat_context_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            initialize_workspace(project_root)
            disk_state = load_state(project_root)
            disk_state["stage"] = "version_scope_confirmed"
            write_state(project_root, disk_state)

            recovered = load_state(
                project_root,
                fallback_state={"stage": "chat_context_only", "project_type": "non_ui"},
            )

            self.assertEqual(recovered["stage"], "version_scope_confirmed")
            self.assertNotEqual(recovered["stage"], "chat_context_only")

    def test_initialize_workspace_preserves_existing_state_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            first_state = initialize_workspace(project_root, project_type="ui")
            first_state["stage"] = "product_brief_confirmed"
            write_state(project_root, first_state)
            custom_artifact = project_root / ARTIFACT_ROOT / "artifacts" / "custom.md"
            custom_artifact.write_text("keep me\n", encoding="utf-8")

            second_state = initialize_workspace(project_root, project_type="non_ui")

            self.assertEqual(second_state["stage"], "product_brief_confirmed")
            self.assertEqual(second_state["project_type"], "ui")
            self.assertEqual(custom_artifact.read_text(encoding="utf-8"), "keep me\n")

    def test_written_state_is_valid_json_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = initialize_workspace(project_root)
            state["stage"] = "test_coverage_audit"

            write_state(project_root, state)

            raw = (project_root / ARTIFACT_ROOT / "state.json").read_text(
                encoding="utf-8"
            )
            self.assertEqual(json.loads(raw)["stage"], "test_coverage_audit")

    def test_loading_legacy_state_adds_ui_conformance_protocol_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "stage": "test_coverage_audit",
                        "project_type": "ui",
                        "multi_agent_reviews": {},
                    }
                ),
                encoding="utf-8",
            )

            state = load_state(project_root)

            self.assertEqual(state["prototype_contract"]["status"], "missing")
            self.assertEqual(
                state["prototype_production_conformance"]["status"],
                "missing",
            )
            self.assertEqual(
                state["multi_agent_reviews"]["ui_conformance"]["status"],
                "missing",
            )

    def test_active_legacy_multi_agent_policy_requires_fresh_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "stage": "scenario_matrix_draft_ready",
                        "multi_agent_policy": {"mode": "spawned_subagents_required"},
                    }
                ),
                encoding="utf-8",
            )

            state = load_state(project_root)

            self.assertEqual(
                state["multi_agent_policy"]["execution_authorization"],
                "legacy_unverified",
            )
            self.assertEqual(state["next_gate"], "multi_agent_mode_selection")
            self.assertIn("multi_agent_mode", state["pending_user_decisions"])

    def test_terminal_legacy_multi_agent_policy_remains_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            original = {
                "active": False,
                "status": "closed",
                "stage": "feature_closure_passed",
                "multi_agent_policy": {"mode": "spawned_subagents_required"},
            }
            state_path.write_text(json.dumps(original), encoding="utf-8")

            state = load_state(project_root)

            self.assertEqual(
                state["multi_agent_policy"],
                {"mode": "spawned_subagents_required"},
            )
            self.assertNotIn("multi_agent_mode", state["pending_user_decisions"])

    def test_legacy_degradation_policy_reports_matching_evidence_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "multi_agent_policy": {"mode": "role_simulation_allowed"},
                    }
                ),
                encoding="utf-8",
            )

            state = load_state(project_root)

            self.assertEqual(
                state["multi_agent_policy"]["evidence_requirement"],
                "structured_role_simulation",
            )


if __name__ == "__main__":
    unittest.main()
