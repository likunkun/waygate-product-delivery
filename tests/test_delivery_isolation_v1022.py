import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


class DeliveryIsolationV1022Tests(unittest.TestCase):
    def test_start_creates_delivery_bound_review_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))

            state = workflow.start(
                feature_slug="feature-a",
                multi_agent_mode="spawned_subagents_authorized",
            )

            self.assertTrue(state["delivery_id"])
            policy = state["multi_agent_policy"]
            self.assertEqual(policy["authorization_delivery_id"], state["delivery_id"])
            self.assertEqual(policy["authorization_feature_slug"], "feature-a")
            self.assertNotIn("execution_mode", state["pending_user_decisions"])
            self.assertNotIn("execution_model_policy", state)

    def test_same_active_feature_resumes_and_different_feature_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            first = workflow.start(feature_slug="feature-a")

            inspection = workflow.inspect_startup_request(feature_slug="feature-a")
            resumed = workflow.start(feature_slug="feature-a")

            self.assertEqual(inspection["action"], "resume_current_delivery")
            self.assertTrue(inspection["review_mode_selection_required"])
            self.assertEqual(resumed["delivery_id"], first["delivery_id"])

            blocked = workflow.inspect_startup_request(feature_slug="feature-b")
            self.assertEqual(blocked["action"], "blocked_by_active_delivery")
            with self.assertRaisesRegex(WorkflowError, "active delivery"):
                workflow.start(feature_slug="feature-b")

    def test_terminal_delivery_is_archived_before_new_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ProductDeliveryWorkflow(root)
            previous = workflow.start(
                feature_slug="feature-a",
                multi_agent_mode="spawned_subagents_authorized",
            )
            previous["active"] = False
            previous["status"] = "closed"
            previous["stage"] = "feature_closure_passed"
            (root / ARTIFACT_ROOT / "state.json").write_text(
                json.dumps(previous), encoding="utf-8"
            )

            inspection = workflow.inspect_startup_request(feature_slug="feature-b")
            started = workflow.start(feature_slug="feature-b")

            self.assertEqual(inspection["action"], "new_delivery_required")
            self.assertNotEqual(started["delivery_id"], previous["delivery_id"])
            self.assertEqual(started["previous_delivery"]["feature_slug"], "feature-a")
            archived = root / started["previous_delivery"]["state_snapshot_path"]
            self.assertTrue(archived.is_file())

    def test_review_authorization_from_another_delivery_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ProductDeliveryWorkflow(root)
            state = workflow.start(
                feature_slug="feature-a",
                multi_agent_mode="spawned_subagents_authorized",
            )
            state["multi_agent_policy"]["authorization_delivery_id"] = "other"
            (root / ARTIFACT_ROOT / "state.json").write_text(
                json.dumps(state), encoding="utf-8"
            )

            with self.assertRaisesRegex(WorkflowError, "current delivery"):
                workflow.select_project_type("ui")

    def test_legacy_active_state_gets_stable_delivery_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "feature_slug": "feature-a",
                        "stage": "product_blueprint",
                        "multi_agent_policy": {
                            "mode": "spawned_subagents_required",
                            "execution_authorization": "authorized",
                            "authorization_scope": "current_delivery",
                            "authorization_source": "startup_command",
                            "authorized_review_types": ["scenario"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            first = load_state(root)
            second = load_state(root)

            self.assertTrue(first["delivery_id"].startswith("legacy-"))
            self.assertEqual(first["delivery_id"], second["delivery_id"])
            self.assertEqual(
                first["multi_agent_policy"]["authorization_delivery_id"],
                first["delivery_id"],
            )
            self.assertEqual(
                first["multi_agent_policy"]["authorization_feature_slug"],
                "feature-a",
            )


if __name__ == "__main__":
    unittest.main()
