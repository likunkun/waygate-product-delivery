"""Progress maps are a projection, never an alternate workflow authority."""
import copy
import hashlib
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import write_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow


class ProgressMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"CODEX_THREAD_ID": "map-owner"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.wf = ProductDeliveryWorkflow(self.root)
        self.state = self.wf.start(feature_slug="map-example", multi_agent_mode="spawned_subagents_authorized")
        self.state_path = self.root / ".product-delivery/state.json"
        self.live = self.root / ".product-delivery/maps/index.html"
        self.assertTrue(hasattr(self.wf, "set_progress_map_mode"), "progress-map API missing")
        self.maps = importlib.import_module("product_delivery_agent.progress_map")

    def enable(self):
        return self.wf.set_progress_map_mode("on", delivery_id=self.state["delivery_id"])

    def state_files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in (self.root / ".product-delivery").rglob("*.json")
                if "progress-map" not in str(p) and "/maps/" not in str(p)}

    def plan(self):
        path = self.root / "scope.md"
        path.write_text("Reports: administrators export and receive audit evidence.\n")
        source = {"path": "scope.md", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        return {"schema_version": "v1", "delivery_id": self.state["delivery_id"], "title": "报表产品", "current_version": "v1",
                "objective": "管理员可靠导出报表", "success_criteria": ["真实数据可下载"],
                "versions": [{"id": "v1", "title": "导出"}, {"id": "v2", "title": "定时生成"}],
                "goals": [{"id": "G1", "title": "可靠导出", "sources": [source]}],
                "components": [{"id": "C1", "title": "报表服务", "description": "生成导出内容", "goal_ids": ["G1"], "sources": [source]}],
                "capabilities": [{"id": "A1", "title": "管理员导出", "description": "鉴权后生成报表", "goal_ids": ["G1"], "component_ids": ["C1"], "version_ids": ["v1"], "sources": [source]},
                                 {"id": "A2", "title": "定时生成", "goal_ids": ["G1"], "component_ids": ["C1"], "version_ids": ["v2"], "sources": [source]}],
                "edges": [], "task_bindings": [], "changes": [], "sources": [source]}

    def test_default_off_and_project_default_does_not_change_existing_delivery(self):
        before = self.state_files()
        self.assertFalse(self.maps.inspect_progress_map(self.root)["enabled"])
        self.assertFalse(self.live.exists())
        self.wf.set_progress_map_mode("on", scope="project")
        self.assertFalse(self.maps.inspect_progress_map(self.root)["enabled"])
        self.assertEqual(self.state_files(), before)
        self.wf.start(feature_slug="map-example")
        self.assertFalse(self.maps.inspect_progress_map(self.root)["enabled"])

    def test_toggle_and_export_do_not_mutate_canonical_files(self):
        before = self.state_files()
        self.enable()
        self.assertTrue(self.live.is_file())
        exported = self.wf.export_progress_map()
        self.assertTrue((self.root / exported["path"]).is_file())
        self.wf.set_progress_map_mode("off", delivery_id=self.state["delivery_id"])
        self.assertIn("自动更新已关闭", self.live.read_text())
        self.assertEqual(self.state_files(), before)
        with self.assertRaisesRegex(ValueError, "disabled|关闭"):
            self.wf.export_progress_map()

    def test_wrong_delivery_rejected_without_files_changed(self):
        before = self.state_files()
        with self.assertRaisesRegex(ValueError, "delivery"):
            self.wf.set_progress_map_mode("on", delivery_id="foreign")
        self.assertFalse(self.live.exists())
        self.assertEqual(before, self.state_files())

    def test_new_delivery_captures_project_default_and_old_missing_config_stays_off(self):
        self.wf.set_progress_map_mode("on", scope="project")
        next_state = copy.deepcopy(self.state)
        next_state["delivery_id"] = "another-delivery"
        write_state(self.root, next_state)
        self.assertTrue(self.maps.inspect_progress_map(self.root)["enabled"])
        self.wf.set_progress_map_mode("off", scope="project")
        write_state(self.root, next_state)
        self.assertTrue(self.maps.inspect_progress_map(self.root)["enabled"])
        config = self.maps.delivery_map_dir(self.root, next_state) / "config.json"
        config.unlink()
        write_state(self.root, next_state)
        self.assertFalse(self.maps.inspect_progress_map(self.root)["enabled"])

    def test_switch_to_disabled_delivery_cannot_show_old_delivery_as_current(self):
        self.enable()
        old_id = self.state["delivery_id"]
        next_state = copy.deepcopy(self.state)
        next_state["delivery_id"] = "second-delivery"
        write_state(self.root, next_state)
        self.assertIn("second-delivery", self.live.read_text())
        self.assertNotIn('"delivery_id": "' + old_id + '"', self.live.read_text())
        self.assertIn("自动更新已关闭", self.live.read_text())

    def test_render_failure_preserves_old_page_and_reports_stale_without_failing_commit(self):
        self.enable()
        old_page = self.live.read_bytes()
        changed = copy.deepcopy(self.state)
        changed["stage"] = "architecture"
        with patch("product_delivery_agent.progress_map.render_progress_map", side_effect=OSError("disk full")):
            write_state(self.root, changed)
        self.assertEqual(json.loads(self.state_path.read_text())["stage"], "architecture")
        self.assertEqual(self.live.read_bytes(), old_page)
        report = self.maps.inspect_progress_map(self.root)
        self.assertEqual(report["freshness"], "stale")
        self.assertIn("disk full", report["error"])

    def test_plan_sources_revision_conflicts_and_future_scope(self):
        self.enable()
        plan = self.plan()
        first = self.wf.record_progress_map_plan(plan, expected_revision=0)
        self.assertEqual(first["revision"], 1)
        with self.assertRaisesRegex(ValueError, "revision"):
            self.wf.record_progress_map_plan(plan, expected_revision=0)
        model = self.wf.build_progress_map()
        self.assertEqual(model["counts"]["current_capabilities"], 1)
        self.assertTrue(any(r["id"] == "A1" for r in model["remaining"]))
        self.assertFalse(any(r["id"] == "A2" for r in model["remaining"]))
        self.assertEqual(model["counts"]["verified_capabilities"], 0)
        (self.root / "scope.md").write_text("Unrecorded scope change")
        self.assertEqual(self.maps.inspect_progress_map(self.root)["freshness"], "stale")
        model = self.wf.build_progress_map()
        self.assertTrue(any(c["kind"] == "stale_evidence" for c in model["changes"]))

    def test_source_escape_and_dangling_component_are_rejected(self):
        self.enable()
        plan = self.plan()
        plan["sources"][0]["path"] = "../outside"
        with self.assertRaises(ValueError):
            self.wf.record_progress_map_plan(plan, expected_revision=0)
        plan = self.plan()
        plan["capabilities"][0]["component_ids"] = ["absent"]
        with self.assertRaisesRegex(ValueError, "component"):
            self.wf.record_progress_map_plan(plan, expected_revision=0)

    def test_cross_delivery_task_binding_and_fabricated_approval_are_rejected(self):
        self.enable()
        plan = self.plan()
        plan["task_bindings"] = [{"delivery_id": "foreign", "task_id": "TASK-001", "planned_task_hash": "a" * 64, "capability_ids": ["A1"]}]
        with self.assertRaisesRegex(ValueError, "delivery"):
            self.wf.record_progress_map_plan(plan, expected_revision=0)
        plan = self.plan()
        plan["approval"] = {"target": "product_baseline", "artifact_hash": "b" * 64}
        with self.assertRaisesRegex(ValueError, "approval|确认"):
            self.wf.record_progress_map_plan(plan, expected_revision=0)

    def test_stage_change_creates_offline_snapshot_but_noop_does_not(self):
        self.enable()
        directory = self.maps.delivery_map_dir(self.root, self.state) / "snapshots"
        initial = len(list(directory.glob("*.html")))
        write_state(self.root, self.state)
        self.assertEqual(len(list(directory.glob("*.html"))), initial)
        changed = copy.deepcopy(self.state)
        changed["stage"] = "architecture"
        write_state(self.root, changed)
        self.assertEqual(len(list(directory.glob("*.html"))), initial + 1)

    def test_task_done_requires_matching_hash_and_real_evidence_not_a_green_label(self):
        self.enable()
        task = {"task_id": "TASK-001", "title": "实现管理员导出", "description": "生成 CSV", "verification": "python verify.py", "planned_task_hash": "a" * 64}
        evidence = self.root / "execution.txt"
        evidence.write_text("Exported real CSV with authorized account")
        state = copy.deepcopy(self.state)
        state["delivery_goal"] = {"planned_tasks": [task], "completed_tasks": ["TASK-001"], "current_task_cursor": None,
            "task_completion_artifacts": {"TASK-001": {"planned_task_hash": task["planned_task_hash"], "artifact_path": "execution.txt",
                "artifact_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(), "verification_command": task["verification"],
                "verification_exit_code": 0, "verification_output": "passed"}}}
        write_state(self.root, state)
        plan = self.plan()
        plan["task_bindings"] = [{"delivery_id": state["delivery_id"], "task_id": "TASK-001", "planned_task_hash": task["planned_task_hash"], "capability_ids": ["A1"]}]
        self.wf.record_progress_map_plan(plan, expected_revision=0)
        model = self.wf.build_progress_map()
        capability = next(c for c in model["capabilities"] if c["id"] == "A1")
        self.assertEqual(capability["status"], "verified")
        self.assertFalse(capability["milestones"]["reviewed"])
        self.assertFalse(capability["milestones"]["delivered"])
        evidence.write_text("Replaced log, not verified")
        self.assertEqual(self.maps.inspect_progress_map(self.root)["freshness"], "stale")
        model = self.wf.build_progress_map()
        self.assertFalse(model["capabilities"][0]["milestones"]["verified"])
        self.assertEqual(model["counts"]["verified_capabilities"], 0)

    def test_unmapped_task_and_plan_delta_are_explained(self):
        self.enable()
        state = copy.deepcopy(self.state)
        state["delivery_goal"] = {"planned_tasks": [{"task_id": "TASK-001", "planned_task_hash": "a" * 64, "title": "导出报表", "description": "CSV", "verification": "check"}], "current_task_cursor": "TASK-001"}
        write_state(self.root, state)
        plan = self.plan()
        self.wf.record_progress_map_plan(plan, expected_revision=0)
        model = self.wf.build_progress_map()
        self.assertTrue(any(c["kind"] == "unexplained" and "TASK-001" in c["title"] for c in model["changes"]))
        plan["capabilities"][0]["title"] = "导出管理员和审计记录"
        self.wf.record_progress_map_plan(plan, expected_revision=1)
        model = self.wf.build_progress_map()
        self.assertEqual(len(model["history"]), 2)
        self.assertTrue(any(c.get("before") == "管理员导出" and c.get("after") == "导出管理员和审计记录" for c in model["changes"]))

    def test_product_definition_then_architecture_uses_active_team_stage(self):
        # An architecture TeamRun must highlight architecture even before a
        # product baseline exists; entry_stage() alone intentionally cannot.
        from product_delivery_agent.team_orchestration import atomic_json, file_hash
        self.enable()
        state = copy.deepcopy(self.state)
        path = self.root / "run.json"
        run = {"run_id": "r1", "delivery_id": state["delivery_id"], "stage": "architecture_version_planning", "status": "running", "task_id": None,
               "work_packages": {"WP-arch": {"status": "running", "agent_id": "architect", "task": {"role_ids": ["production.architecture_contract"]}}}}
        atomic_json(path, run)
        state["team_runs"] = {"r1": {"run_path": "run.json", "run_sha256": file_hash(path), "status": "running"}}
        write_state(self.root, state)
        model = self.wf.build_progress_map()
        self.assertEqual([s["id"] for s in model["stages"] if s["status"] == "current"], ["architecture_version_planning"])
        self.assertEqual(model["current_work"]["work_packages"][0]["agent_id"], "architect")

    def test_self_reported_complete_closure_is_never_shown_as_passed(self):
        self.enable()
        state = copy.deepcopy(self.state)
        state["closure_validation"] = {"status": "passed"}
        write_state(self.root, state)
        self.assertNotEqual(self.wf.build_progress_map()["closure"]["status"], "passed")

    def test_receipt_failure_leaves_last_live_html_unchanged(self):
        self.enable()
        old_page = self.live.read_bytes()
        changed = copy.deepcopy(self.state)
        changed["stage"] = "architecture"
        atomic = self.maps._atomic
        def fail_receipt(path, value, **kwargs):
            if path.name == "receipt.json":
                raise OSError("receipt write failed")
            return atomic(path, value, **kwargs)
        with patch.object(self.maps, "_atomic", side_effect=fail_receipt):
            write_state(self.root, changed)
        self.assertEqual(self.live.read_bytes(), old_page)
        self.assertEqual(self.maps.inspect_progress_map(self.root)["freshness"], "stale")

    def test_wrong_test_obligation_cannot_verify_a_capability(self):
        self.enable()
        task = {"task_id": "TASK-001", "title": "导出", "description": "导出", "verification": "check", "planned_task_hash": "a" * 64, "obligation_ids": ["O1"]}
        proof = self.root / "proof.txt"
        proof.write_text("O1 passed")
        state = copy.deepcopy(self.state)
        state["planned_e2e_obligations"] = {"obligations": [{"obligation_id": "O1", "scenario_id": "S1"}, {"obligation_id": "O2", "scenario_id": "S2"}]}
        state["delivery_goal"] = {"planned_tasks": [task], "completed_tasks": ["TASK-001"], "task_completion_artifacts": {"TASK-001": {
            "planned_task_hash": task["planned_task_hash"], "artifact_path": "proof.txt", "artifact_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            "verification_exit_code": 0, "verification_command": "check"}}}
        write_state(self.root, state)
        plan = self.plan()
        plan["capabilities"][0]["obligation_ids"] = ["O2"]
        plan["task_bindings"] = [{"delivery_id": state["delivery_id"], "task_id": "TASK-001", "planned_task_hash": task["planned_task_hash"], "capability_ids": ["A1"]}]
        self.wf.record_progress_map_plan(plan, expected_revision=0)
        capability = self.wf.build_progress_map()["capabilities"][0]
        self.assertFalse(capability["milestones"]["verified"])
        self.assertTrue(any("O2" in gap for gap in capability["gaps"]))

    def test_current_design_work_package_files_participate_in_freshness(self):
        self.enable()
        from product_delivery_agent.team_orchestration import atomic_json, file_hash
        output = self.root / "design.md"
        output.write_text("Architecture output")
        run_path = self.root / "run.json"
        run = {"run_id": "r1", "delivery_id": self.state["delivery_id"], "stage": "architecture_version_planning", "status": "running", "task_id": None,
               "work_packages": {"WP-design": {"status": "ready", "agent_id": "architect", "task": {},
                   "accepted_artifacts": [{"ref": "design.md", "sha256": file_hash(output)}]}}}
        atomic_json(run_path, run)
        state = copy.deepcopy(self.state)
        state["team_runs"] = {"r1": {"run_path": "run.json", "run_sha256": file_hash(run_path), "status": "running"}}
        write_state(self.root, state)
        self.assertEqual(self.maps.inspect_progress_map(self.root)["freshness"], "fresh")
        output.write_text("Externally changed output")
        self.assertEqual(self.maps.inspect_progress_map(self.root)["freshness"], "stale")

    def test_off_after_failed_render_freezes_only_last_published_model(self):
        from tests.test_progress_map_html import Document
        self.enable()
        original = json.loads(Document(self.live.read_text()).payload)["model"]
        changed = copy.deepcopy(self.state)
        changed["stage"] = "architecture"
        atomic = self.maps._atomic
        def fail_receipt(path, value, **kwargs):
            if path.name == "receipt.json":
                raise OSError("receipt failure")
            return atomic(path, value, **kwargs)
        with patch.object(self.maps, "_atomic", side_effect=fail_receipt):
            write_state(self.root, changed)
        self.wf.set_progress_map_mode("off", delivery_id=self.state["delivery_id"])
        frozen = json.loads(Document(self.live.read_text()).payload)["model"]
        self.assertEqual(frozen["source_revision"], original["source_revision"])
        self.assertEqual(frozen["current_work"], original["current_work"])

    def test_malformed_plan_collections_never_persist_a_broken_revision(self):
        self.enable()
        for field, value in [("changes", None), ("changes", [None]), ("changes", "bad"), ("edges", {}),
                             ("task_bindings", "bad"), ("sources", [None])]:
            with self.subTest(field=field, value=value):
                plan = self.plan()
                plan[field] = value
                with self.assertRaises(ValueError):
                    self.wf.record_progress_map_plan(plan, expected_revision=0)
        plan = self.plan()
        plan["changes"] = [{"id": "C", "kind": "unexplained", "title": "新增", "reason": "待查", "impact": "未知", "owner": "主线程", "next_action": "核实", "affected_ids": [{"id": "A1"}]}]
        with self.assertRaises(ValueError):
            self.wf.record_progress_map_plan(plan, expected_revision=0)
        self.assertEqual(self.wf.build_progress_map()["plan_revision"], 0)

    def test_old_revision_sources_remain_inspectable_when_latest_replaces_them(self):
        self.enable()
        plan = self.plan()
        self.wf.record_progress_map_plan(plan, expected_revision=0)
        old = self.root / "scope.md"
        new = self.root / "new-scope.md"
        new.write_bytes(old.read_bytes())
        old.unlink()
        for ref in plan["sources"]:
            ref["path"] = "new-scope.md"
        self.wf.record_progress_map_plan(plan, expected_revision=1)
        history = self.wf.build_progress_map()["history"]
        self.assertEqual(history[0]["sources"][0]["status"], "stale")
        self.assertEqual(history[1]["sources"][0]["status"], "current")


if __name__ == "__main__":
    unittest.main()
