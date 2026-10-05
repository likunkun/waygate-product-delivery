"""Map-enabled end-to-end canonical workflow paths (controlled host fixtures)."""
import unittest

from tests import test_team_workflow_paths as paths
from product_delivery_agent.progress_map import inspect_progress_map
from tests import test_review_role_contract_integration as role_fixtures


class ProgressMapWorkflowTests(unittest.TestCase):
    def test_coordinator_confirmed_gates_show_known_progress_and_unknown_architecture(self):
        fixture = paths.TeamWorkflowPathsTests()
        fixture.setUp()
        try:
            state = fixture.workflow.start(feature_slug="coordinator-map", multi_agent_mode="spawned_subagents_authorized")
            state["open_spec_draft_ready"] = True
            state["confirmation_readiness"] = {"product_baseline": "confirmed", "test_coverage_plan": "confirmed"}
            state["multi_agent_reviews"] = {"scenario": {"status": "passed"}}
            state["stage"] = "test_design"
            from product_delivery_agent.artifact_protocol import write_state
            write_state(fixture.root, state)
            fixture.workflow.set_progress_map_mode("on", delivery_id=state["delivery_id"])
            statuses = {row["id"]: row["status"] for row in fixture.workflow.build_progress_map()["stages"]}
            self.assertEqual(statuses["product_definition"], "completed")
            self.assertEqual(statuses["open_spec_product_surface"], "completed")
            self.assertEqual(statuses["test_design"], "completed")
            self.assertEqual(statuses["architecture_version_planning"], "unknown")
        finally:
            fixture.doCleanups()

    def test_changed_role_review_input_is_stale_in_map_without_state_write(self):
        fixture = role_fixtures.ReviewRoleContractIntegrationTests()
        fixture.setUp()
        try:
            state = fixture.workflow.record_multi_agent_review("scenario", fixture.review())
            fixture.workflow.set_progress_map_mode("on", delivery_id=state["delivery_id"])
            before = (fixture.root / ".product-delivery/state.json").read_bytes()
            source = next(iter(fixture.refs.values()))
            (fixture.root / source["ref"]).write_text("Changed after review")
            model = fixture.workflow.build_progress_map()
            self.assertEqual(next(r["status"] for r in model["reviews"] if r["gate"] == "scenario"), "stale")
            self.assertEqual(inspect_progress_map(fixture.root)["freshness"], "stale")
            self.assertEqual((fixture.root / ".product-delivery/state.json").read_bytes(), before)
        finally:
            fixture.doCleanups()

    def test_ui_and_non_ui_team_closure_refresh_without_owning_authority(self):
        for branch in ("ui", "non_ui"):
            with self.subTest(branch=branch):
                fixture = paths.TeamWorkflowPathsTests()
                fixture.setUp()
                try:
                    fixture.workflow.set_progress_map_mode("on", scope="project")
                    if branch == "ui":
                        fixture.test_ui_team_path_reaches_formal_closure_after_conformance_reviews()
                    else:
                        fixture.test_non_ui_team_path_reaches_formal_closure_after_behavior_evidence()
                    report = inspect_progress_map(fixture.root)
                    self.assertTrue(report["enabled"])
                    self.assertIsNone(report["error"])
                    self.assertEqual(report["freshness"], "fresh")
                    model = fixture.workflow.build_progress_map()
                    self.assertEqual(model["closure"]["status"], "passed")
                    self.assertEqual([s["status"] for s in model["stages"]], ["completed"] * 6)
                    self.assertTrue((fixture.root / report["path"]).exists())
                finally:
                    fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
