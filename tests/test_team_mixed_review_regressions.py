"""Regression coverage for mixed review completion and remediation freshness."""

import unittest

from product_delivery_agent.team_orchestration import TeamError
from tests import test_team_workflow_paths as fixtures


class TeamMixedReviewRegressionTests(unittest.TestCase):
    """Compose the integration fixture without importing its TestCase class."""

    def setUp(self):
        self.host = fixtures.TeamWorkflowPathsTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.workflow = self.host.workflow

    def test_mixed_review_pass_and_reject_releases_one_shared_remediation_attempt(self):
        self.host.confirm_baseline(self.host.surface())
        run = self.host.produce(self.host.prepare("test_design"))
        run = self.host.barriers(run, "test")
        run = self.host.barriers(run, "test_coverage")
        key = next(iter(run["work_packages"]))

        run = self.host.event(
            run,
            "review_rejected",
            review_type="test",
            reason="Cover the denied actor in the test plan.",
            work_package_ids=[key],
        )
        self.assertEqual(run["work_packages"][key]["status"], "integrated")
        self.assertEqual(run["work_packages"][key]["attempt"], 1)
        self.assertIn("test_coverage", self.workflow.status()["team_review_locks"])

        self.workflow.record_multi_agent_review(
            "test_coverage", self.host.review_payload("test_coverage")
        )
        current = self.workflow.inspect_team_run(run["run_id"])
        row = current["work_packages"][key]
        self.assertEqual(current["status"], "running")
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempt"], 2)
        self.assertEqual(row["revision_count"], 1)
        self.assertEqual(current.get("remediation_targets"), [])
        self.assertFalse(self.workflow.status().get("team_review_locks"))

        dispatched = self.host.dispatch(current, key)
        self.assertEqual(dispatched["work_packages"][key]["status"], "running")

    def test_prior_passed_gate_is_stale_after_remediation_until_re_reviewed(self):
        self.host.confirm_baseline(self.host.surface())
        run = self.host.produce(self.host.prepare("test_design"))
        run = self.host.record_review(run, "test")

        run = self.host.barriers(run, "test_coverage")
        key = next(iter(run["work_packages"]))
        run = self.host.event(
            run,
            "review_rejected",
            review_type="test_coverage",
            reason="Cover the denied actor in the coverage plan.",
            work_package_ids=[key],
        )
        run = self.host.produce(
            run,
            content="Revised test design adds the denied-actor recovery scenario.\n",
        )
        run = self.host.record_review(run, "test_coverage")

        with self.assertRaisesRegex(TeamError, "review|stale|changed|snapshot"):
            self.workflow.finalize_team_run(
                run["run_id"], expected_revision=run["revision"]
            )

        run = self.host.record_review(run, "test")
        completed = self.workflow.finalize_team_run(
            run["run_id"], expected_revision=run["revision"]
        )
        self.assertEqual(completed["status"], "completed")


if __name__ == "__main__":
    unittest.main()
