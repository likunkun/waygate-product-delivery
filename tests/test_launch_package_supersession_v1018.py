import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.transition_journal import has_transition
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_canonical_launch_v106 import planned_tasks, workflow_ready_for_launch


def task_completion_artifact(state, task_id):
    task = next(
        task
        for task in state["delivery_goal"]["planned_tasks"]
        if task["task_id"] == task_id
    )
    return {
        "artifact_path": f".product-delivery/artifacts/{task_id}.json",
        "artifact_sha256": "b" * 64,
        "verification_command": task["verification"],
        "verification_exit_code": 0,
        "verification_output": "OK",
        "planned_task_hash": task["planned_task_hash"],
    }


def changed_task_queue():
    return [
        {
            "task_id": "TASK-001",
            "title": "Implement revised provider governance",
            "description": "Deliver the revised frozen provider governance slice.",
            "verification": "pytest -k task_001_revised",
        },
        {
            "task_id": "TASK-002",
            "title": "Verify revised provider governance",
            "description": "Verify the revised provider governance slice.",
            "verification": "pytest -k task_002",
        },
    ]


class LaunchPackageSupersessionV1018Tests(unittest.TestCase):
    def _stale_launch_workflow(self, project_root, replacement_tasks):
        workflow = workflow_ready_for_launch(project_root)
        workflow.generate_codex_goal_handoff(
            scope="Implement the frozen package",
            verification_commands=["pytest"],
            planned_tasks=planned_tasks(),
        )
        workflow.record_task_completion(
            "TASK-001",
            artifact=task_completion_artifact(workflow._state(), "TASK-001"),
        )
        workflow.record_implementation_launch_authorization(
            scope="Implement the revised frozen package",
            verification_commands=["pytest"],
            planned_tasks=replacement_tasks,
        )
        return workflow

    def test_recovery_supersedes_old_package_and_records_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._stale_launch_workflow(Path(tmp), changed_task_queue())
            old_goal_hash = workflow._state()["delivery_goal"]["launch_package_hash"]

            state = workflow.recover_stale_launch_package(
                scope="Implement the revised frozen package",
                verification_commands=["pytest"],
                planned_tasks=changed_task_queue(),
            )

            new_hash = state["implementation_launch_authorization"][
                "launch_package_hash"
            ]
            self.assertNotEqual(old_goal_hash, new_hash)
            self.assertEqual(state["delivery_goal"]["launch_package_hash"], new_hash)
            archived = state["superseded_implementation_packages"][-1]
            self.assertEqual(
                archived["delivery_goal"]["launch_package_hash"], old_goal_hash
            )
            self.assertIn("task_completion_artifacts", archived["delivery_goal"])
            self.assertTrue(has_transition(state, "implementation_package_superseded"))
            self.assertNotIn(
                "stale_implementation_launch_authorization",
                state.get("blocked_until", []),
            )

    def test_handoff_path_automatically_supersedes_authorized_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._stale_launch_workflow(Path(tmp), changed_task_queue())

            state = workflow.generate_codex_goal_handoff(
                scope="Implement the revised frozen package",
                verification_commands=["pytest"],
                planned_tasks=changed_task_queue(),
            )

            self.assertEqual(
                state["delivery_goal"]["launch_package_hash"],
                state["implementation_launch_authorization"]["launch_package_hash"],
            )
            self.assertTrue(has_transition(state, "implementation_package_superseded"))

    def test_changed_task_hash_does_not_reuse_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = self._stale_launch_workflow(Path(tmp), changed_task_queue())

            state = workflow.recover_stale_launch_package(
                scope="Implement the revised frozen package",
                verification_commands=["pytest"],
                planned_tasks=changed_task_queue(),
            )

            self.assertNotIn("TASK-001", state["delivery_goal"]["completed_tasks"])
            self.assertNotIn(
                "TASK-001", state["delivery_goal"].get("task_completion_artifacts", {})
            )

    def test_identical_task_hash_reuses_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            replacement = planned_tasks(extra=True)
            workflow = self._stale_launch_workflow(Path(tmp), replacement)

            state = workflow.recover_stale_launch_package(
                scope="Implement the revised frozen package",
                verification_commands=["pytest"],
                planned_tasks=replacement,
            )

            self.assertIn("TASK-001", state["delivery_goal"]["completed_tasks"])
            self.assertIn(
                "TASK-001", state["delivery_goal"]["task_completion_artifacts"]
            )
            self.assertEqual(state["delivery_goal"]["current_task_cursor"], "TASK-002")

    def test_matching_launch_package_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = workflow_ready_for_launch(Path(tmp))
            first = workflow.generate_codex_goal_handoff(
                scope="Implement the frozen package",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )

            recovered = workflow.recover_stale_launch_package(
                scope="Implement the frozen package",
                verification_commands=["pytest"],
                planned_tasks=planned_tasks(),
            )

            self.assertEqual(recovered["delivery_goal"], first["delivery_goal"])
            self.assertEqual(
                recovered.get("superseded_implementation_packages", []), []
            )

    def test_stale_review_rejects_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._stale_launch_workflow(project_root, changed_task_queue())
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state = load_state(project_root)
            state["multi_agent_reviews"]["test_coverage"]["status"] = "stale"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            with self.assertRaises(WorkflowError) as caught:
                workflow.recover_stale_launch_package(
                    scope="Implement the revised frozen package",
                    verification_commands=["pytest"],
                    planned_tasks=changed_task_queue(),
                )

            self.assertIn("stale_multi_agent_test_coverage_review", str(caught.exception))

    def test_stale_authorization_rejects_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._stale_launch_workflow(project_root, changed_task_queue())
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state = load_state(project_root)
            state["implementation_launch_authorization"]["status"] = "stale"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            with self.assertRaises(WorkflowError) as caught:
                workflow.recover_stale_launch_package(
                    scope="Implement the revised frozen package",
                    verification_commands=["pytest"],
                    planned_tasks=changed_task_queue(),
                )

            self.assertIn("implementation_launch_authorization", str(caught.exception))

    def test_stale_requirements_confirmation_rejects_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = self._stale_launch_workflow(project_root, changed_task_queue())
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state = load_state(project_root)
            state["user_confirmations"].pop("test_coverage_plan", None)
            state["planned_e2e_obligations"]["accepted_by_user"] = False
            state_path.write_text(json.dumps(state), encoding="utf-8")

            with self.assertRaises(WorkflowError) as caught:
                workflow.recover_stale_launch_package(
                    scope="Implement the revised frozen package",
                    verification_commands=["pytest"],
                    planned_tasks=changed_task_queue(),
                )

            self.assertIn("test_coverage_plan_user_confirmation", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
