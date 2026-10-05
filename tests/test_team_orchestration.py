"""Behavioral coverage for owner-controlled production and recoverable integration."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def digest(data):
    return hashlib.sha256(data).hexdigest()


class TeamOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"CODEX_THREAD_ID": "team-owner"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.workflow = ProductDeliveryWorkflow(self.root)

    def start(self, mode="team"):
        self.assertTrue(hasattr(self.workflow, "prepare_team_run"), "production facade missing")
        state = self.workflow.start(feature_slug="team-example", multi_agent_mode="spawned_subagents_authorized", production_mode_if_created=mode)
        self.workflow.select_project_type("non_ui")
        return state

    def prepare(self, packages=None):
        from product_delivery_agent.production_profiles import get_production_role_card
        (self.root / "input.md").write_text("Confirmed understanding: export reports for administrators.\n")
        refs = {key: {"ref": "input.md", "sha256": digest((self.root / "input.md").read_bytes())}
                for key in get_production_role_card("production.product_requirements")["required_inputs"]}
        return self.workflow.prepare_team_run("product_definition", packages or [{
            "work_package_id": "WP-01", "role_ids": ["production.product_requirements"],
            "depends_on": [], "allowed_write_paths": ["docs/brief.md"],
        }], input_refs=refs)

    def event(self, run, kind, **payload):
        event = {"event_id": f"E-{run['revision']}-{kind}", "type": kind, "work_package_id": "WP-01", **payload}
        return self.workflow.record_team_events(run["run_id"], [event], expected_revision=run["revision"])

    def dispatch(self, run, agent="worker-a"):
        return self.event(run, "dispatched", agent_id=agent, spawn_source="test.host", attempt=run["work_packages"]["WP-01"]["attempt"])

    def produce(self, run):
        row = run["work_packages"]["WP-01"]
        task = row["task"]
        stage = self.root / row["staging_root"]
        output = stage / "docs/brief.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("Administrators export CSV; ordinary members are denied.\n")
        ref = "docs/brief.md"
        artifacts = []
        for index, kind in enumerate(task["required_outputs"]):
            artifact_path = ref if index == 0 else "evidence/" + kind + ".md"
            dest = stage / artifact_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if index:
                dest.write_text("Export administrators only; scope traced to input.md.\n")
            artifacts.append({"path": artifact_path, "sha256": digest(dest.read_bytes()), "artifact_type": kind})
        result = {
            "task_hash": task["task_hash"], "input_snapshot_hash": task["input_snapshot_hash"],
            "role_ids": task["role_ids"], "status": "ready_for_integration",
            "artifacts": artifacts,
            "changes": [{"path": ref, "operation": "add", "base_sha256": None, "result_sha256": digest(output.read_bytes()), "staged_path": ref}],
            "check_records": [{"check_id": check, "outcome": "satisfied", "reason": "Administrator export and denied-member paths have explicit outcomes.", "evidence_refs": [artifacts[0]["path"]]} for check in task["must_check"]],
            "completion_evidence": {a["artifact_type"]: [a["path"]] for a in artifacts},
            "risks": [], "blockers": [], "unresolved_questions": [], "handoff": "Use these exact actor and scope boundaries.",
        }
        return result

    def submit(self, run, result=None):
        row = run["work_packages"]["WP-01"]
        return self.event(run, "result", agent_id=row["agent_id"], attempt=row["attempt"], result=result or self.produce(run))

    def test_team_authorization_does_not_come_from_review_authorization(self):
        self.start("coordinator")
        with self.assertRaisesRegex(ValueError, "team.*authoriz|production.*team"):
            self.prepare()

    def test_staged_production_merges_once_without_completing_delivery(self):
        self.start()
        run = self.dispatch(self.prepare())
        run = self.submit(run)
        self.assertFalse((self.root / "docs/brief.md").exists())
        run = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertIn("ordinary members are denied", (self.root / "docs/brief.md").read_text())
        run = self.workflow.finalize_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertEqual(run["status"], "completed")
        state = load_state(self.root)
        self.assertIsNone(state["delivery_goal"])
        self.assertNotEqual(state["closure_validation"]["status"], "passed")

    def test_event_replay_is_idempotent_but_conflicting_payload_rejected(self):
        self.start()
        run = self.prepare()
        event = {"event_id": "spawn-1", "type": "dispatched", "work_package_id": "WP-01", "agent_id": "worker-a", "spawn_source": "test.host", "attempt": 1}
        first = self.workflow.record_team_events(run["run_id"], [event], expected_revision=0)
        second = self.workflow.record_team_events(run["run_id"], [event], expected_revision=0)
        self.assertEqual(second["revision"], first["revision"])
        event["agent_id"] = "other-worker"
        with self.assertRaisesRegex(ValueError, "event|conflict"):
            self.workflow.record_team_events(run["run_id"], [event], expected_revision=0)

    def test_foreign_thread_cannot_submit_or_integrate(self):
        self.start()
        run = self.prepare()
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "worker-a"}):
            with self.assertRaisesRegex(Exception, "coordinator|owner"):
                self.dispatch(run)

    def test_external_target_change_is_preserved(self):
        self.start()
        run = self.submit(self.dispatch(self.prepare()))
        target = self.root / "docs/brief.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("User's concurrent edit")
        with self.assertRaisesRegex(ValueError, "conflict|baseline"):
            self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertEqual(target.read_text(), "User's concurrent edit")

    def test_input_drift_blocks_results(self):
        self.start()
        run = self.dispatch(self.prepare())
        (self.root / "input.md").write_text("Changed scope")
        with self.assertRaisesRegex(ValueError, "input|snapshot|stale"):
            self.submit(run)

    def test_mutated_staged_result_is_rejected_at_merge(self):
        self.start()
        run = self.submit(self.dispatch(self.prepare()))
        stage = self.root / run["work_packages"]["WP-01"]["staging_root"]
        (stage / "docs/brief.md").write_text("Unreviewed changes")
        with self.assertRaisesRegex(ValueError, "hash|changed|artifact"):
            self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])

    def test_pause_invalidates_active_attempt_and_resume_preserves_delivery(self):
        original = self.start()
        run = self.dispatch(self.prepare())
        late = self.produce(run)
        self.workflow.pause_delivery()
        self.workflow.resume_delivery()
        current = self.workflow.inspect_team_run(run["run_id"])
        self.assertGreater(current["work_packages"]["WP-01"]["attempt"], 1)
        with self.assertRaisesRegex(ValueError, "attempt|running"):
            self.event(current, "result", agent_id="worker-a", attempt=1, result=late)
        self.assertEqual(load_state(self.root)["delivery_id"], original["delivery_id"])

    def test_existing_mode_cannot_change_with_open_work(self):
        self.start()
        self.prepare()
        with self.assertRaisesRegex(ValueError, "boundary|unfinished|active"):
            self.workflow.set_production_mode("coordinator", delivery_id=load_state(self.root)["delivery_id"])

    def test_implementation_cannot_start_before_confirmations(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "baseline|confirmation|handoff|stage"):
            self.workflow.prepare_team_run("implementation_execution", [], input_refs={}, task_id="TASK-001")

    def test_formal_closure_requires_completed_delivery_preparation(self):
        from product_delivery_agent.gatekeeper import assert_pre_closure_ready, GatekeeperError
        self.start()
        with self.assertRaisesRegex(GatekeeperError, "production.*delivery_preparation"):
            assert_pre_closure_ready(load_state(self.root), {}, self.root)

    def test_integration_response_loss_can_replay_without_second_write(self):
        self.start()
        run = self.submit(self.dispatch(self.prepare()))
        first = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        second = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertEqual(first, second)

    def test_claimed_simulated_or_other_identity_is_not_a_real_worker_result(self):
        self.start()
        run = self.dispatch(self.prepare())
        result = self.produce(run)
        result.update(identity_kind="simulated", simulated_identity="imaginary", agent_id="someone-else")
        with self.assertRaisesRegex(ValueError, "identity|simulat"):
            self.submit(run, result)

    def test_design_stage_cannot_write_implementation_source(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "design|implementation|path"):
            self.prepare([{"work_package_id": "WP-01", "role_ids": ["production.product_requirements"],
                           "depends_on": [], "allowed_write_paths": ["src/feature.py"]}])

    def test_restart_via_start_resumes_paused_runs_as_well_as_delivery(self):
        self.start()
        run = self.dispatch(self.prepare())
        self.workflow.pause_delivery()
        self.workflow.start(feature_slug="team-example")
        current = self.workflow.inspect_team_run(run["run_id"])
        self.assertNotEqual(current["status"], "paused")

    def test_merge_interruption_replays_only_remaining_exact_changes(self):
        self.start()
        run = self.dispatch(self.prepare([{"work_package_id": "WP-01", "role_ids": ["production.product_requirements"],
                           "depends_on": [], "allowed_write_paths": ["docs/brief.md", "docs/acceptance.md"]}]))
        result = self.produce(run)
        stage = self.root / run["work_packages"]["WP-01"]["staging_root"]
        added = stage / "docs/acceptance.md"
        added.write_text("Ordinary members receive a denied result")
        result["artifacts"].append({"path": "docs/acceptance.md", "sha256": digest(added.read_bytes()), "artifact_type": "acceptance_notes"})
        result["changes"].append({"path": "docs/acceptance.md", "operation": "add", "base_sha256": None,
                                  "result_sha256": digest(added.read_bytes()), "staged_path": "docs/acceptance.md"})
        run = self.submit(run, result)
        replace = os.replace
        def interrupted(source, target):
            if Path(target) == self.root / "docs/acceptance.md":
                raise OSError("simulated power loss at second target")
            return replace(source, target)
        with patch("product_delivery_agent.team_orchestration.os.replace", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertTrue((self.root / "docs/brief.md").exists())
        self.assertFalse((self.root / "docs/acceptance.md").exists())
        recovered = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertEqual(recovered["status"], "integrated")
        self.assertIn("denied", (self.root / "docs/acceptance.md").read_text())


if __name__ == "__main__":
    unittest.main()
