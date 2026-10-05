"""Host-event integration tests: real files and canonical workflow gates.

Agent events and evidence documents are deterministic test fixtures; these tests
exercise the host's contract enforcement, not a live model or browser run.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state
from product_delivery_agent.production_profiles import get_production_role_card, get_stage_profile
from product_delivery_agent.team_orchestration import TeamError
from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow
from tests.conformance_fixtures import (
    activate_host_goal, bind_prototype_design_review, complete_host_goal,
    confirm_test_coverage_plan, record_bundled_ui_prototype_review,
    record_passing_task_prototype_conformance, record_passing_task_slice_evidence,
    record_ui_conformance, reconcile_host_goal,
    write_prototype_screenshot,
)
from tests.test_feature_closure import (
    browser_evidence, coverage_row, multi_agent_review, planned_obligation,
    scenario_row, task_completion_artifact, ui_review_payload,
)
from tests.test_non_ui_behavior_contract import complete_contract_payload


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def behavior_evidence(project_root):
    evidence_path = project_root / ".product-delivery" / "artifacts" / "behavior-e2e-results.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "command": "python3 scripts/roster_import.py fixtures/valid.csv",
                "stdout": "valid roster import completes; invalid csv returns row errors",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    trace_path = project_root / ".product-delivery" / "artifacts" / "behavior" / "roster-import.log"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "run=roster-import exit_code=0\n"
        "stdout=valid roster import completes\n"
        "stderr=invalid csv returns row errors\n",
        encoding="utf-8",
    )
    return {
        "test_id": "TC-V008-001",
        "obligation_id": "OBL-001",
        "command": "python3 scripts/roster_import.py fixtures/valid.csv",
        "exit_code": 0,
        "trace_path": str(trace_path.relative_to(project_root)),
        "semantic_assertions": [
            "valid roster import completes",
            "invalid csv returns row errors",
        ],
        "evidence_path": ".product-delivery/artifacts/behavior-e2e-results.json",
        "execution_segment_id": "teacher-roster-import",
        "test_title_or_step": "teacher imports a valid roster and receives row errors for invalid csv",
    }


def closure_artifact_for_state(state):
    evidence_key = "executed_browser_evidence" if state["project_type"] == "ui" else "executed_behavior_evidence"
    evidence = state[evidence_key]
    artifact = {
        "status": "passed",
        "passed": True,
        "canonical_validator": CANONICAL_VALIDATOR,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "closure_flag": "v0.11-feature-closure-passed",
        "latest_test_case": state["handoff"]["latest_test_case"],
        "matrix_range": state["handoff"]["matrix_range"],
        "e2e_covered_tc": sorted({record["test_id"] for record in evidence["records"]}),
        "covered_user_stories": sorted({record["user_story"] for record in evidence["records"]}),
        "covered_journeys": sorted({record["journey"] for record in evidence["records"]}),
        "artifact_root": ".product-delivery/artifacts",
        "artifact_generation_command": "product-delivery formal-closure",
        "e2e_evidence_paths": [record["evidence_path"] for record in evidence["records"]],
        "high_risk_gate_subresults": {
            ("ui-browser-e2e-required" if state["project_type"] == "ui" else "non-ui-behavior-evidence"): "passed"
        },
        "negative_scope_guard_result": "passed",
        "required_commands": [
            {
                "command": command,
                "exit_code": 0,
                "output": "release exercise command passed",
            }
            for command in state["handoff"].get("required_commands", [])
        ],
        "secret_values_recorded": False,
        "controller_session_modified": False,
        "created_fake_controller_state": False,
    }
    if state["project_type"] == "ui":
        from product_delivery_agent.gatekeeper import prototype_conformance_closure_binding
        artifact["prototype_conformance"] = prototype_conformance_closure_binding(state)
    return artifact


class TeamWorkflowPathsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        owner = patch.dict(os.environ, {"CODEX_THREAD_ID": "team-path-owner"})
        owner.start()
        self.addCleanup(owner.stop)
        self.workflow = ProductDeliveryWorkflow(self.root)
        self.refs = {}
        self.completed = []

    def start(self, branch="non_ui"):
        self.workflow.start(feature_slug="team-paths", multi_agent_mode="spawned_subagents_authorized",
                            production_mode_if_created="team")
        self.workflow.select_project_type(branch)

    def prepare(self, stage, *, packages=None, task_id=None, extra_refs=None):
        profile = get_stage_profile(stage, self.workflow.status()["project_type"])
        if packages is None:
            outputs = list(dict.fromkeys(kind for role in profile["required_role_ids"]
                                        for kind in get_production_role_card(role)["required_outputs"]))
            packages = [{"work_package_id": stage, "role_ids": profile["required_role_ids"],
                         "depends_on": [], "allowed_write_paths": [
                             "docs/team/" + stage + "/" + kind + ".md" for kind in outputs]}]
        keys = {key for package in packages for role in package["role_ids"]
                for key in get_production_role_card(role)["required_inputs"]}
        refs = {}
        for key in keys:
            if key not in self.refs:
                path = self.root / "fixture-inputs" / (key + ".md")
                path.parent.mkdir(exist_ok=True)
                path.write_text(f"Bound {key}: teachers create classrooms; duplicate names are rejected.\n")
                self.refs[key] = {"ref": str(path.relative_to(self.root)), "sha256": sha(path)}
            refs[key] = copy.deepcopy(self.refs[key])
        refs.update(extra_refs or {})
        self.reconcile()
        return self.workflow.prepare_team_run(stage, packages, input_refs=refs, task_id=task_id)

    def reconcile(self):
        if (self.workflow.status().get("host_goal_binding") or {}).get("status") == "active":
            reconcile_host_goal(self.workflow)

    def event(self, run, event_type, **values):
        event = {"event_id": f"{run['revision']}-{event_type}", "type": event_type, **values}
        self.reconcile()
        return self.workflow.record_team_events(run["run_id"], [event], expected_revision=run["revision"])

    def dispatch(self, run, key=None, agent=None):
        key = key or next(iter(run["work_packages"]))
        row = run["work_packages"][key]
        return self.event(run, "dispatched", work_package_id=key, attempt=row["attempt"],
                          agent_id=agent or ("producer-" + key), spawn_source="fixture.host.spawn")

    def result(self, run, key=None, content=None):
        key = key or next(iter(run["work_packages"]))
        row = run["work_packages"][key]
        task = row["task"]
        workspace = self.root / row["staging_root"]
        artifacts = []
        changes = []
        for index, kind in enumerate(task["required_outputs"]):
            paths = task["allowed_write_paths"]
            path = paths[index] if index < len(paths) else "evidence/" + kind + ".md"
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content or f"{run['stage']} {kind}: teacher creates a classroom; duplicate name is rejected.\n")
            artifacts.append({"path": path, "sha256": sha(target), "artifact_type": kind})
            if path in paths:
                base = row["baseline"][path]
                changes.append({"path": path, "operation": "modify" if base else "add",
                                "base_sha256": base, "result_sha256": sha(target), "staged_path": path})
        return {"task_hash": task["task_hash"], "input_snapshot_hash": task["input_snapshot_hash"],
                "role_ids": task["role_ids"], "status": "ready_for_integration", "artifacts": artifacts,
                "changes": changes, "check_records": [
                    {"check_id": check, "outcome": "satisfied", "reason": "Actor, successful outcome and duplicate rejection are explicitly stated.",
                     "evidence_refs": [artifacts[0]["path"]]} for check in task["must_check"]],
                "completion_evidence": {item["artifact_type"]: [item["path"]] for item in artifacts},
                "risks": [], "blockers": [], "unresolved_questions": [],
                "handoff": "Coordinator must integrate these artifacts and pass the separate canonical gates."}

    def produce(self, run, key=None, *, content=None):
        key = key or next(iter(run["work_packages"]))
        run = self.dispatch(run, key)
        row = run["work_packages"][key]
        result = self.result(run, key, content)
        run = self.event(run, "result", work_package_id=key, attempt=row["attempt"],
                         agent_id=row["agent_id"], result=result)
        self.reconcile()
        run = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        changed = {change["path"] for change in result["changes"]}
        for artifact in result["artifacts"]:
            if artifact["path"] in changed:
                self.refs[artifact["artifact_type"]] = {"ref": artifact["path"], "sha256": artifact["sha256"]}
        return run

    def finalize(self, run):
        self.reconcile()
        run = self.workflow.finalize_team_run(run["run_id"], expected_revision=run["revision"])
        self.assertEqual(run["status"], "completed")
        self.completed.append(run["stage"])
        return run

    def initial_stages(self):
        self.finalize(self.produce(self.prepare("product_definition")))
        self.finalize(self.produce(self.prepare("architecture_version_planning")))

    def surface(self, branch="non_ui"):
        self.start(branch)
        self.initial_stages()
        run = self.produce(self.prepare("open_spec_product_surface"))
        self.workflow.record_scenario_matrix([scenario_row()])
        self.workflow.confirm("product_brief")
        self.workflow.confirm("version_scope")
        if branch == "ui":
            prototype = self.root / "prototype/index.html"
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text("<html><button>Create classroom</button></html>")
            write_prototype_screenshot(self.root)
            record_bundled_ui_prototype_review(self.workflow, self.root, ui_review_payload())
        else:
            self.workflow.record_non_ui_behavior_contract(complete_contract_payload())
        return run

    def review_payload(self, gate, agents=None):
        review = multi_agent_review(gate)
        agents = agents or ["reviewer-" + gate + "-a", "reviewer-" + gate + "-b"]
        review.update(review_mode="spawned_subagents", reviewers=agents, reviewer_agent_ids=agents)
        if gate == "scenario" and self.workflow.status()["project_type"] == "ui":
            review = bind_prototype_design_review(self.workflow, review)
            ui = self.workflow.status()["ui_prototype_review"]
            review.update(ui_continuity_findings=[], baseline_inheritance_review={
                "ui_change_type": ui["ui_change_type"], "baseline_feature_slug": ui["baseline_feature_slug"],
                "baseline_entry_path": ui["baseline_user_journey"], "inherits_existing_surface": True,
                "parallel_surface_replacement": False})
        return review

    def member(self, run, gate, agent, phase):
        path = self.root / "reviews" / (gate + "-" + phase + "-" + agent + ".json")
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"agent_id": agent, "phase": phase,
                                    "position": "Actor and duplicate rejection are covered by the cited fixture artifacts."}))
        return self.event(run, "review_member", review_type=gate, agent_id=agent, phase=phase,
                          artifact={"ref": str(path.relative_to(self.root)), "sha256": sha(path)})

    def barriers(self, run, gate, agents=None):
        agents = agents or self.review_payload(gate)["reviewer_agent_ids"]
        run = self.event(run, "review_started", review_type=gate, reviewer_agent_ids=agents)
        for phase in ("independent", "challenge", "revision"):
            for agent in agents:
                run = self.member(run, gate, agent, phase)
        return run

    def record_review(self, run, gate, payload=None):
        payload = payload or self.review_payload(gate)
        run = self.barriers(run, gate, payload["reviewer_agent_ids"])
        if (self.workflow.status().get("host_goal_binding") or {}).get("status") == "active":
            reconcile_host_goal(self.workflow)
        state = self.workflow.record_multi_agent_review(gate, payload)
        self.assertEqual(state["multi_agent_reviews"][gate]["team_run_id"], run["run_id"])
        return run

    def confirm_baseline(self, run):
        run = self.record_review(run, "scenario")
        self.finalize(run)
        state = self.workflow.prepare_product_baseline_confirmation()
        pending = state["pending_confirmations"]["product_baseline"]
        self.workflow.confirm_product_baseline("确认产品基线和课堂工作流范围", pending["nonce"])

    def launch(self, branch="non_ui"):
        self.confirm_baseline(self.surface(branch))
        run = self.produce(self.prepare("test_design"))
        obligation = planned_obligation()
        coverage = coverage_row()
        if branch == "non_ui":
            obligation["test_layer"] = "api_e2e"
            coverage.update(test_layer="api_e2e", evidence_type="behavior_evidence",
                            semantic_marker="non-ui-behavior-evidence", obligation_ref="valid roster import completes")
            second = dict(coverage, tc_id="TC-V008-002", obligation_ref="invalid csv returns row errors")
        self.workflow.record_planned_e2e_obligations([obligation])
        self.workflow.record_test_coverage_audit([coverage, second] if branch == "non_ui" else [coverage],
                                               negative_guard_records=["student billing is absent", "cross-tenant import remains unsupported"])
        for gate in ("test_coverage", "test"):
            run = self.record_review(run, gate)
        self.finalize(run)
        confirm_test_coverage_plan(self.workflow)
        options = {"scope": "Implement classroom creation", "verification_commands": ["python -m unittest"],
                   "prohibited_work": ["Do not mutate canonical Waygate state"]}
        self.workflow.record_implementation_launch_authorization(**options)
        self.workflow.generate_codex_goal_handoff(**options)
        activate_host_goal(self.workflow)
        return self.workflow.status()["delivery_goal"]["current_task_cursor"]

    def test_architecture_cannot_skip_product_definition(self):
        self.start()
        with self.assertRaisesRegex(TeamError, "stage|preced|product_definition"):
            self.prepare("architecture_version_planning")

    def test_product_surface_cannot_skip_architecture(self):
        self.start()
        self.finalize(self.produce(self.prepare("product_definition")))
        with self.assertRaisesRegex(TeamError, "stage|preced|architecture"):
            self.prepare("open_spec_product_surface")

    def test_accepted_dependency_updates_downstream_task_snapshot(self):
        self.start()
        source = self.root / "docs/shared-intent.md"
        source.parent.mkdir()
        source.write_text("Original actor requirement.\n")
        initial_hash = sha(source)
        self.refs["product_intent"] = {"ref": "docs/shared-intent.md", "sha256": initial_hash}
        packages = [
            {"work_package_id": "clarify", "role_ids": ["production.product_requirements"], "depends_on": [],
             "allowed_write_paths": ["docs/shared-intent.md"]},
            {"work_package_id": "downstream", "role_ids": ["production.product_requirements"], "depends_on": ["clarify"],
             "allowed_write_paths": ["docs/downstream.md"]},
        ]
        run = self.prepare("product_definition", packages=packages)
        old_task_hash = run["work_packages"]["downstream"]["task"]["task_hash"]
        old_snapshot_hash = run["work_packages"]["downstream"]["task"]["input_snapshot_hash"]
        with self.assertRaisesRegex(TeamError, "dependenc"):
            self.dispatch(run, "downstream")
        run = self.produce(run, "clarify", content="Teachers create classrooms; students cannot.\n")
        run = self.dispatch(run, "downstream")
        row = run["work_packages"]["downstream"]
        self.assertEqual((self.root / row["staging_root"] / "docs/shared-intent.md").read_bytes(), source.read_bytes())
        self.assertEqual(row["task"]["input_refs"]["product_intent"]["sha256"], sha(source),
                         "downstream brief must bind the accepted predecessor bytes, not the original snapshot")
        self.assertNotEqual(row["task"]["task_hash"], old_task_hash)
        self.assertNotEqual(row["task"]["input_snapshot_hash"], old_snapshot_hash)
        # The rebound brief must remain usable through the second integration,
        # whose inputs now legitimately contain predecessor modifications.
        result = self.result(run, "downstream")
        run = self.event(run, "result", work_package_id="downstream", attempt=row["attempt"],
                         agent_id=row["agent_id"], result=result)
        run = self.workflow.integrate_team_run(run["run_id"], expected_revision=run["revision"])
        self.finalize(run)
        self.assertTrue((self.root / "docs/downstream.md").is_file())

    def test_review_phase_barriers_and_finalization_require_canonical_review(self):
        run = self.surface()
        payload = self.review_payload("scenario")
        agents = payload["reviewer_agent_ids"]
        with self.assertRaisesRegex(TeamError, "review"):
            self.finalize(run)
        run = self.event(run, "review_started", review_type="scenario", reviewer_agent_ids=agents)
        for phase in ("independent", "challenge", "revision"):
            run = self.member(run, "scenario", agents[0], phase)
            with self.assertRaisesRegex(TeamError, "barrier|independent"):
                self.workflow.record_multi_agent_review("scenario", payload)
            if phase != "revision":
                next_phase = "challenge" if phase == "independent" else "revision"
                with self.assertRaisesRegex(TeamError, "phase"):
                    self.member(run, "scenario", agents[0], next_phase)
            run = self.member(run, "scenario", agents[1], phase)
        state = self.workflow.record_multi_agent_review("scenario", payload)
        self.assertEqual(state["multi_agent_reviews"]["scenario"]["team_run_id"], run["run_id"])
        self.finalize(run)
        self.assertNotEqual(load_state(self.root)["confirmation_readiness"]["product_baseline"], "confirmed")

    def test_reviewers_must_be_two_distinct_nonproducer_nonowner_identities(self):
        run = self.surface()
        for agents in (["reviewer-a"], ["reviewer-a", "reviewer-a"],
                       ["producer-product_definition", "reviewer-b"], ["team-path-owner", "reviewer-b"]):
            with self.subTest(agents=agents), self.assertRaisesRegex(TeamError, "independent|identit"):
                self.event(run, "review_started", review_type="scenario", reviewer_agent_ids=agents)

    def test_omitted_review_mode_cannot_replace_frozen_reviewer_identities(self):
        run = self.surface()
        run = self.barriers(run, "scenario")
        review = self.review_payload("scenario", ["producer-open_spec_product_surface", "unfrozen-reviewer"])
        review.pop("review_mode")  # Canonical legacy review semantics default to spawned_subagents.
        with self.assertRaisesRegex(TeamError, "identit|reviewer|producer"):
            self.workflow.record_multi_agent_review("scenario", review)

    def test_review_artifact_or_producer_source_drift_prevents_canonical_pass(self):
        run = self.surface()
        run = self.barriers(run, "scenario")
        path = self.root / next(iter(run["work_packages"].values()))["result"]["changes"][0]["path"]
        path.write_text("Changed after the review snapshot was frozen.\n")
        with self.assertRaisesRegex(TeamError, "source|snapshot|changed"):
            self.workflow.record_multi_agent_review("scenario", self.review_payload("scenario"))

    def test_confirmed_baseline_blocks_earlier_stages_and_wrong_task_is_rejected(self):
        task_id = self.launch()
        for stage in ("product_definition", "architecture_version_planning", "open_spec_product_surface", "test_design"):
            with self.subTest(stage=stage), self.assertRaisesRegex(TeamError, "frozen|confirmation|stage"):
                self.prepare(stage)
        with self.assertRaisesRegex(TeamError, "TASK|task"):
            self.prepare("implementation_execution", task_id="TASK-WRONG")
        with self.assertRaisesRegex(TeamError, "TASK|completed"):
            self.prepare("delivery_preparation")
        reconcile_host_goal(self.workflow)
        with self.assertRaisesRegex(TeamError, "production run"):
            self.workflow.record_task_completion(task_id, artifact=task_completion_artifact(self.workflow.status(), task_id))

    def exercise_six_stages(self, branch):
        task_id = self.launch(branch)
        run = self.produce(self.prepare("implementation_execution", task_id=task_id))
        # Integration alone must not mark the TASK complete or erase its evidence gate.
        self.assertEqual(self.workflow.status()["delivery_goal"]["current_task_cursor"], task_id)
        with self.assertRaisesRegex(Exception, "slice|conformance|visual"):
            self.finalize(run)
        if branch == "ui":
            record_passing_task_prototype_conformance(self.workflow, self.root, task_id)
        else:
            record_passing_task_slice_evidence(self.workflow, self.root, task_id)
        self.finalize(run)
        reconcile_host_goal(self.workflow)
        self.workflow.record_task_completion(task_id, artifact=task_completion_artifact(self.workflow.status(), task_id))
        self.assertIsNone(self.workflow.status()["delivery_goal"]["current_task_cursor"])
        run = self.produce(self.prepare("delivery_preparation"))
        if branch == "ui":
            reconcile_host_goal(self.workflow)
            self.workflow.record_executed_browser_evidence([browser_evidence(self.root)])
        else:
            reconcile_host_goal(self.workflow)
            self.workflow.record_executed_behavior_evidence([behavior_evidence(self.root)])
        run = self.record_review(run, "test_implementation")
        if branch == "ui":
            # Existing fixture builds actual prototype-conformance artifacts. The
            # wrapper supplies host barriers and still calls the real recorder.
            original_record = self.workflow.record_multi_agent_review
            def through_barriers(gate, payload):
                nonlocal run
                run = self.barriers(run, gate, payload["reviewer_agent_ids"])
                reconcile_host_goal(self.workflow)
                return original_record(gate, payload)
            with patch.object(self.workflow, "record_multi_agent_review", side_effect=through_barriers):
                record_ui_conformance(self.workflow, self.root)
        self.finalize(run)
        self.assertEqual(self.completed, ["product_definition", "architecture_version_planning",
                                         "open_spec_product_surface", "test_design",
                                         "implementation_execution", "delivery_preparation"])
        state = self.workflow.status()
        self.assertNotEqual(state["closure_validation"]["status"], "passed")
        self.assertNotEqual(state["status"], "closed")
        self.assertEqual(state["host_goal_binding"]["status"], "active")
        self.reconcile()
        with self.assertRaisesRegex(Exception, "closure"):
            self.workflow.assert_goal_can_stop()

    def test_non_ui_six_stage_path_keeps_formal_closure_separate(self):
        self.exercise_six_stages("non_ui")

    def test_non_ui_team_path_reaches_formal_closure_after_behavior_evidence(self):
        self.exercise_six_stages("non_ui")
        self.reconcile()
        state = self.workflow.record_feature_closure(
            closure_artifact_for_state(self.workflow.status())
        )
        self.assertEqual(state["closure_validation"]["status"], "passed")
        complete_host_goal(self.workflow)
        closed = self.workflow.close_delivery()
        self.assertEqual(closed["status"], "closed")

    def test_ui_six_stage_path_keeps_visual_gate_and_formal_closure_separate(self):
        self.exercise_six_stages("ui")

    def test_ui_team_path_reaches_formal_closure_after_conformance_reviews(self):
        self.exercise_six_stages("ui")
        self.reconcile()
        state = self.workflow.record_feature_closure(
            closure_artifact_for_state(self.workflow.status())
        )
        self.assertEqual(state["closure_validation"]["status"], "passed")
        complete_host_goal(self.workflow)
        closed = self.workflow.close_delivery()
        self.assertEqual(closed["status"], "closed")


if __name__ == "__main__":
    unittest.main()
