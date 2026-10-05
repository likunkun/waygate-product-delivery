"""Production failure budgets and review-driven repair preserve frozen scope."""
import copy
import unittest

from tests import test_team_workflow_paths as fixture
from product_delivery_agent.team_orchestration import TeamError
from product_delivery_agent.artifact_protocol import write_state


class TeamReworkTests(unittest.TestCase):
    def setUp(self):
        self.host = fixture.TeamWorkflowPathsTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.workflow = self.host.workflow

    def test_two_running_workers_block_a_third_but_allow_queued_work(self):
        self.host.start()
        packages = [{"work_package_id": f"work-{i}", "role_ids": ["production.product_requirements"],
                     "depends_on": [], "allowed_write_paths": [f"docs/brief-{i}.md"]} for i in range(3)]
        run = self.host.prepare("product_definition", packages=packages)
        run = self.host.dispatch(run, "work-0")
        run = self.host.dispatch(run, "work-1")
        with self.assertRaisesRegex(TeamError, "two"):
            self.host.dispatch(run, "work-2")

    def test_stale_implementation_authorization_cannot_dispatch_production(self):
        task_id = self.host.launch("non_ui")
        state = self.workflow.status()
        state["implementation_launch_authorization"]["status"] = "stale"
        write_state(self.host.root, state)
        with self.assertRaisesRegex(Exception, "implementation.*authorization|implementation.*integrity"):
            self.host.prepare("implementation_execution", task_id=task_id)

    def test_cancel_does_not_reset_identical_failed_work_budget(self):
        self.host.start()
        run = self.host.dispatch(self.host.prepare("product_definition"))
        key = next(iter(run["work_packages"]))
        run = self.host.event(run, "failed", work_package_id=key, agent_id="producer-" + key, attempt=1, reason="Tool unavailable")
        run = self.host.event(run, "retry", work_package_id=key, reason="Retry host tool")
        run = self.host.dispatch(run, key)
        run = self.host.event(run, "failed", work_package_id=key, agent_id="producer-" + key, attempt=2, reason="Same tool unavailable")
        with self.assertRaisesRegex(TeamError, "limit"):
            self.host.event(run, "retry", work_package_id=key, reason="Again")
        run = self.host.event(run, "cancel", work_package_id=key, reason="Need new repair input")
        with self.assertRaisesRegex(TeamError, "identical|material|failed"):
            self.host.prepare("product_definition")

    def test_post_implementation_review_can_reopen_task_without_new_confirmation(self):
        task_id = self.host.launch("non_ui")
        run = self.host.produce(self.host.prepare("implementation_execution", task_id=task_id))
        fixture.record_passing_task_slice_evidence(self.workflow, self.host.root, task_id)
        self.host.finalize(run)
        self.host.reconcile()
        self.workflow.record_task_completion(task_id, artifact=fixture.task_completion_artifact(self.workflow.status(), task_id))
        before = copy.deepcopy(self.workflow.status()["user_confirmations"])
        run = self.host.produce(self.host.prepare("delivery_preparation"))
        run = self.host.barriers(run, "test_implementation")
        run = self.host.event(run, "review_rejected", review_type="test_implementation",
                              work_package_ids=["delivery_preparation"], affected_task_ids=[task_id],
                              reason="The test omits the denied-role assertion already in the frozen scope")
        state = self.workflow.status()
        self.assertEqual(state["delivery_goal"]["current_task_cursor"], task_id)
        self.assertEqual(state["user_confirmations"], before)
        self.assertNotIn(task_id, state["delivery_goal"]["completed_tasks"])
        self.assertEqual(run["status"], "stale")
        repair = self.host.prepare("implementation_execution", task_id=task_id)
        self.assertEqual(repair["task_id"], task_id)
        repair = self.host.produce(repair, content="Teacher creation succeeds; denied-role assertion executes and rejects student creation.\n")
        with self.assertRaisesRegex(Exception, "slice|evidence"):
            self.host.finalize(repair)
        fixture.record_passing_task_slice_evidence(self.workflow, self.host.root, task_id)
        self.host.finalize(repair)
        self.host.reconcile()
        self.workflow.record_task_completion(task_id, artifact=fixture.task_completion_artifact(self.workflow.status(), task_id))
        self.assertIn(task_id, self.workflow.status()["delivery_goal"]["completed_tasks"])
        self.assertEqual(self.workflow.status()["user_confirmations"], before)

    def test_repair_input_allows_new_bounded_cycle_after_failure(self):
        self.host.start()
        run = self.host.dispatch(self.host.prepare("product_definition"))
        key = next(iter(run["work_packages"]))
        run = self.host.event(run, "failed", work_package_id=key, agent_id="producer-" + key, attempt=1, reason="Missing constraint")
        self.host.event(run, "cancel", work_package_id=key, reason="New evidence is required")
        source = self.host.root / self.host.refs["product_intent"]["ref"]
        source.write_text("Teachers create unique classrooms; clarified duplicate-name handling rejects unchanged records.\n")
        self.host.refs["product_intent"]["sha256"] = fixture.sha(source)
        new_run = self.host.prepare("product_definition")
        self.assertNotEqual(new_run["run_id"], run["run_id"])


if __name__ == "__main__":
    unittest.main()
