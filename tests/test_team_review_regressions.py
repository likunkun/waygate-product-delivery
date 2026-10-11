"""Regression coverage for production persistence and review recovery boundaries.

The composed fixture supplies deterministic host events and canonical workflow
inputs. These are integration tests with real temporary files, not live agents.
"""

from contextlib import contextmanager
import copy
import os
import shutil
from pathlib import Path
import unittest
from unittest.mock import patch

from product_delivery_agent import workflow as workflow_module
from product_delivery_agent.team_orchestration import (
    TeamError,
    assert_team_closure_ready,
)
from tests import test_team_workflow_paths as fixtures


class TeamReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        # Compose the helper instead of importing/subclassing its TestCase:
        # unittest discovery must collect only this module's new regressions.
        self.host = fixtures.TeamWorkflowPathsTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.root = self.host.root
        self.workflow = self.host.workflow

    def _submit(self, run, result):
        key = next(iter(run["work_packages"]))
        row = run["work_packages"][key]
        return self.host.event(
            run, "result", work_package_id=key, agent_id=row["agent_id"],
            attempt=row["attempt"], result=result,
        )

    def _partially_integrated(self):
        self.host.start()
        run = self.host.dispatch(self.host.prepare("product_definition"))
        result = self.host.result(run)
        self.assertGreaterEqual(len(result["changes"]), 2)
        run = self._submit(run, result)
        first, second = [self.root / c["path"] for c in result["changes"][:2]]
        replace = os.replace

        def interrupt_second_target(source, target):
            if Path(target) == second:
                raise OSError("injected interruption at the second canonical target")
            return replace(source, target)

        with patch("product_delivery_agent.team_orchestration.os.replace",
                   side_effect=interrupt_second_target):
            with self.assertRaisesRegex(OSError, "injected interruption"):
                self.workflow.integrate_team_run(
                    run["run_id"], expected_revision=run["revision"],
                )
        self.assertTrue(first.is_file())
        self.assertFalse(second.exists())
        return run, result

    def _assert_recovers(self, run, result):
        recovered = self.workflow.integrate_team_run(
            run["run_id"], expected_revision=run["revision"],
        )
        self.assertEqual(recovered["status"], "integrated")
        for change in result["changes"]:
            self.assertEqual(fixtures.sha(self.root / change["path"]),
                             change["result_sha256"])

    def test_durable_merge_recovers_after_worker_staging_is_lost(self):
        run, result = self._partially_integrated()
        row = next(iter(run["work_packages"].values()))
        shutil.rmtree(self.root / row["staging_root"])
        self._assert_recovers(run, result)

    def test_pause_preserves_result_accepted_immediately_before_lock(self):
        self.host.start()
        run = self.host.dispatch(self.host.prepare("product_definition"))
        result = self.host.result(run)
        key = next(iter(run["work_packages"]))
        real_lock = workflow_module.state_write_lock
        concurrent = []
        pending = True

        @contextmanager
        def accept_result_before_lock(root):
            nonlocal pending
            if pending:
                pending = False
                concurrent.append(self._submit(run, result))
            with real_lock(root):
                yield

        with patch.object(workflow_module, "state_write_lock",
                          side_effect=accept_result_before_lock):
            self.workflow.pause_delivery()

        current = self.workflow.inspect_team_run(run["run_id"])
        self.assertEqual(len(concurrent), 1)
        self.assertGreater(current["revision"], concurrent[0]["revision"])
        self.assertEqual(current["work_packages"][key]["status"], "ready")
        self.assertEqual(current["work_packages"][key]["result"], result)
        event_id = f"{run['revision']}-result"
        self.assertEqual(current["events"][event_id], concurrent[0]["events"][event_id])
        self.assertTrue(self.workflow.status()["paused"])
        self.workflow.resume_delivery()
        current = self.workflow.inspect_team_run(run["run_id"])
        self._assert_recovers(current, result)

    def test_resume_invalidates_review_locks_when_frozen_input_is_stale(self):
        run = self.host.barriers(self.host.surface(), "scenario")
        self.workflow.pause_delivery()
        changed = self.root / next(iter(run["input_refs"].values()))["ref"]
        changed.write_text("Updated product input while delivery was paused.\n")
        self.workflow.resume_delivery()

        self.assertEqual(self.workflow.inspect_team_run(run["run_id"])["status"], "stale")
        state = self.workflow.status()
        self.assertFalse(state.get("team_review_locks"))
        changed_mode = self.workflow.set_production_mode(
            "coordinator", delivery_id=state["delivery_id"],
        )
        self.assertEqual(changed_mode["production_policy"]["mode"], "coordinator")

    def test_two_review_rejections_allocate_one_shared_remediation_attempt(self):
        self.host.confirm_baseline(self.host.surface())
        run = self.host.produce(self.host.prepare("test_design"))
        for gate in ("test", "test_coverage"):
            run = self.host.barriers(run, gate)
        key = next(iter(run["work_packages"]))
        run = self.host.event(
            run, "review_rejected", review_type="test", reason="Cover denied actor.",
            work_package_ids=[key],
        )
        with self.assertRaisesRegex(TeamError, "review|frozen|barrier"):
            self.host.dispatch(run, key)
        run = self.host.event(
            run, "review_rejected", review_type="test_coverage",
            reason="Cover the same denied actor in the coverage plan.",
            work_package_ids=[key],
        )

        self.assertFalse(self.workflow.status().get("team_review_locks"))
        row = run["work_packages"][key]
        self.assertEqual(row["attempt"], 2)
        self.assertEqual(row["revision_count"], 1)
        self.assertNotIn("accepted_artifacts", row)
        self.assertNotIn("finished_at", row)
        self.assertNotIn("elapsed_seconds", row)
        run = self.host.dispatch(run, key)
        self.assertEqual(run["work_packages"][key]["status"], "running")

    def test_finalization_replays_with_the_original_revision(self):
        self.host.start()
        run = self.host.produce(self.host.prepare("product_definition"))
        source_revision = run["revision"]
        completed = self.workflow.finalize_team_run(
            run["run_id"], expected_revision=source_revision
        )
        replayed = self.workflow.finalize_team_run(
            run["run_id"], expected_revision=source_revision
        )
        self.assertEqual(replayed, completed)
        receipt = replayed["finalization_receipt"]
        self.assertEqual(receipt["source_revision"], source_revision)
        self.assertEqual(receipt["final_revision"], replayed["revision"])

    def test_review_submission_rejects_input_drift_after_barriers(self):
        run = self.host.barriers(self.host.surface(), "scenario")
        changed = self.root / next(iter(run["input_refs"].values()))["ref"]
        changed.write_text("Input changed after the final review member returned.\n")
        with self.assertRaisesRegex(TeamError, "stale|snapshot|input"):
            self.workflow.record_multi_agent_review(
                "scenario", self.host.review_payload("scenario")
            )

    def test_invalid_review_does_not_consume_host_goal_transition(self):
        task_id = self.host.launch("non_ui")
        run = self.host.produce(
            self.host.prepare("implementation_execution", task_id=task_id)
        )
        fixtures.record_passing_task_slice_evidence(
            self.workflow, self.root, task_id
        )
        self.host.finalize(run)
        self.host.reconcile()
        self.workflow.record_task_completion(
            task_id,
            artifact=fixtures.task_completion_artifact(
                self.workflow.status(), task_id
            ),
        )
        run = self.host.produce(self.host.prepare("delivery_preparation"))
        run = self.host.barriers(run, "test_implementation")
        self.host.reconcile()
        before = copy.deepcopy(
            self.workflow.status()["host_goal_binding"]["authorized_transition"]
        )
        invalid = self.host.review_payload("test_implementation")
        invalid["reviewer_agent_ids"] = ["wrong-reviewer-a", "wrong-reviewer-b"]
        with self.assertRaisesRegex(TeamError, "identit|reviewer"):
            self.workflow.record_multi_agent_review(
                "test_implementation", invalid
            )
        self.assertEqual(
            self.workflow.status()["host_goal_binding"]["authorized_transition"],
            before,
        )

    def test_review_members_cannot_reuse_production_sources_as_evidence(self):
        run = self.host.surface()
        agents = self.host.review_payload("scenario")["reviewer_agent_ids"]
        run = self.host.event(
            run, "review_started", review_type="scenario",
            reviewer_agent_ids=agents,
        )
        path = next(iter(run["work_packages"].values()))["result"]["changes"][0]["path"]
        with self.assertRaisesRegex(TeamError, "distinct|production"):
            self.host.event(
                run, "review_member", review_type="scenario",
                agent_id=agents[0], phase="independent",
                artifact={"ref": path, "sha256": fixtures.sha(self.root / path)},
            )

    def test_completed_integrated_output_drift_blocks_formal_team_closure(self):
        self.host.exercise_six_stages("non_ui")
        state = self.workflow.status()
        completed_run_ids = [
            run_id for run_id, summary in state["team_runs"].items()
            if summary["stage"] == "delivery_preparation"
            and summary["status"] == "completed"
        ]
        self.assertEqual(len(completed_run_ids), 1)
        completed = self.workflow.inspect_team_run(completed_run_ids[0])
        path = next(iter(completed["integration_receipts"][-1]["outputs"]))
        (self.root / path).write_text("Canonical output drifted after production completion.\n")
        with self.assertRaisesRegex(TeamError, "integrated production output changed"):
            assert_team_closure_ready(self.workflow.status(), self.root)

    def test_partial_merge_cannot_be_cancelled_before_recovery(self):
        run, result = self._partially_integrated()
        key = next(iter(run["work_packages"]))
        before = (self.root / ".product-delivery/state.json").read_bytes()
        with self.assertRaisesRegex(TeamError, "intent|integration|recover"):
            self.host.event(run, "cancel", work_package_id=key, reason="Stop this run.")
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)
        self.assertEqual(self.workflow.inspect_team_run(run["run_id"]), run)
        self._assert_recovers(run, result)

    def test_partial_merge_cannot_be_paused_before_recovery(self):
        run, result = self._partially_integrated()
        before = (self.root / ".product-delivery/state.json").read_bytes()
        with self.assertRaisesRegex(TeamError, "intent|integration|recover"):
            self.workflow.pause_delivery()
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)
        self.assertFalse(self.workflow.status().get("paused"))
        self.assertEqual(self.workflow.inspect_team_run(run["run_id"]), run)
        self._assert_recovers(run, result)

    def test_finalize_rejects_changed_integrated_output_not_listed_as_input(self):
        self.host.start()
        run = self.host.produce(self.host.prepare("product_definition"))
        row = next(iter(run["work_packages"].values()))
        path = row["result"]["changes"][0]["path"]
        self.assertNotIn(path, {ref["ref"] for ref in run["input_refs"].values()})
        (self.root / path).write_text("Owner's subsequent edit must remain untouched.\n")
        with self.assertRaisesRegex(TeamError, "output|changed|artifact|stale"):
            self.workflow.finalize_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertNotEqual(self.workflow.inspect_team_run(run["run_id"])["status"], "completed")
        self.assertEqual((self.root / path).read_text(),
                         "Owner's subsequent edit must remain untouched.\n")

    def test_worker_workspace_contains_only_its_role_bound_input_files(self):
        self.host.start()
        unrelated = self.root / "unrelated-private-notes.md"
        unrelated.write_text("Unrelated stage data outside this role's input contract.\n")
        run = self.host.prepare("product_definition", extra_refs={
            "unrelated_internal_notes": {
                "ref": unrelated.name, "sha256": fixtures.sha(unrelated),
            },
        })
        run = self.host.dispatch(run)
        row = next(iter(run["work_packages"].values()))
        self.assertNotIn("unrelated_internal_notes", row["task"]["input_refs"])
        workspace = self.root / row["staging_root"]
        self.assertFalse((workspace / unrelated.name).exists())
        for ref in row["task"]["input_refs"].values():
            self.assertEqual(fixtures.sha(workspace / ref["ref"]), ref["sha256"])

    def test_exact_event_replay_after_handoff_needs_no_new_goal_reconciliation(self):
        task_id = self.host.launch()
        run = self.host.prepare("implementation_execution", task_id=task_id)
        key = next(iter(run["work_packages"]))
        event = {
            "event_id": "implementation-spawn-response-loss", "type": "dispatched",
            "work_package_id": key, "attempt": 1, "agent_id": "implementation-worker",
            "spawn_source": "fixture.host.spawn",
        }
        event.update({field: run["work_packages"][key][field] for field in ("agent_display_name", "agent_spawn_name")})
        self.host.reconcile()
        first = self.workflow.record_team_events(
            run["run_id"], [event], expected_revision=run["revision"],
        )
        before = (self.root / ".product-delivery/state.json").read_bytes()
        second = self.workflow.record_team_events(
            run["run_id"], [event], expected_revision=run["revision"],
        )
        self.assertEqual(second, first)
        self.assertEqual((self.root / ".product-delivery/state.json").read_bytes(), before)

    def test_earlier_stage_rerun_cannot_reuse_old_downstream_completion(self):
        self.host.start()
        self.host.initial_stages()
        try:
            rerun = self.host.prepare("product_definition")
        except TeamError as error:
            # Rejecting a backward stage transition also prevents stale proofs.
            self.assertRegex(str(error), "stage|order|completed|prior|backward")
            return
        self.host.finalize(self.host.produce(
            rerun, content="Revised product scope: administrators export classrooms.\n",
        ))
        with self.assertRaisesRegex(TeamError, "stage|preced|architecture|stale"):
            self.host.prepare("open_spec_product_surface")

    def test_writable_package_cannot_complete_without_its_declared_changes(self):
        self.host.start()
        run = self.host.dispatch(self.host.prepare("product_definition"))
        result = self.host.result(run)
        result["changes"] = []
        with self.assertRaisesRegex(ValueError, "change|write|output|integrat"):
            self._submit(run, result)
        self.assertEqual(self.workflow.inspect_team_run(run["run_id"])["status"], "running")


if __name__ == "__main__":
    unittest.main()
