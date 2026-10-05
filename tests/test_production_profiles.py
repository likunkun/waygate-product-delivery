"""Production briefs reject incomplete scope and unsupported completion claims."""

import copy
import importlib
import importlib.util
import unittest
from unittest.mock import patch


CORE = ["product_requirements", "architecture_contract", "scenario_interaction",
        "ui_prototype", "test_design", "frontend", "backend", "test_automation",
        "integration", "delivery_evidence"]
CONDITIONAL = ["domain_research", "data_migration", "security_engineering",
               "performance_reliability", "build_deployment"]


class ProductionProfileTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("product_delivery_agent.production_profiles"),
                             "production profile contracts must be implemented")
        self.p = importlib.import_module("product_delivery_agent.production_profiles")

    def context(self):
        keys = set()
        for name in CORE + CONDITIONAL:
            card = self.p.get_production_role_card("production." + name)
            keys.update(card["required_inputs"] + card["optional_inputs"])
        return {"delivery_id": "delivery-1", "feature_slug": "imports",
                "project_type": "non_ui", "input_snapshot_hash": "a" * 64,
                "task_id": "TASK-01", "condition_flags": [],
                "input_refs": {key: {"ref": "docs/" + key + ".md", "sha256": "b" * 64}
                               for key in keys}}

    def package(self, name="requirements", roles=None, depends=None):
        return {"work_package_id": name,
                "role_ids": roles or ["production.product_requirements"],
                "depends_on": depends or [], "allowed_write_paths": ["drafts/" + name + ".md"]}

    def task(self):
        return self.p.build_stage_tasks("product_definition", self.context(), [self.package()])["tasks"][0]

    def result(self, task):
        # Each output is independent evidence; no assertion relies on implementation hashing.
        artifacts = [{"path": "staging/" + kind + ".md", "sha256": "c" * 64,
                      "artifact_type": kind} for kind in task["required_outputs"]]
        return {"task_hash": task["task_hash"], "input_snapshot_hash": task["input_snapshot_hash"],
                "role_ids": task["role_ids"], "status": "ready_for_integration",
                "artifacts": artifacts,
                "changes": [{"path": "drafts/requirements.md", "operation": "add",
                             "base_sha256": None, "result_sha256": "c" * 64,
                             "staged_path": artifacts[0]["path"]}],
                "check_records": [{"check_id": check, "outcome": "satisfied",
                                   "reason": "Acceptance mapping is present at the cited section.",
                                   "evidence_refs": [artifacts[0]["path"] + "#acceptance"]}
                                  for check in task["must_check"]],
                "completion_evidence": {row["artifact_type"]: [row["path"]] for row in artifacts},
                "risks": [], "blockers": [], "unresolved_questions": [],
                "handoff": "Coordinator: inspect staged blueprint and integrate after source hash validation."}

    def test_all_roles_produce_isolated_complete_dispatchable_cards(self):
        for name in CORE + CONDITIONAL:
            with self.subTest(role=name):
                card = self.p.get_production_role_card("production." + name)
                self.assertEqual(card["role_version"], "1.2.0")
                self.assertFalse(card["permissions"]["canonical_write"])
                self.assertEqual(card["permissions"]["write"], ["staging_artifacts", "member_result_return"])
                for field in ("mission", "task_steps", "must_check", "required_inputs", "required_outputs",
                              "quality_rubric", "evidence_requirements", "completion_criteria",
                              "escalation_conditions", "output_schema"):
                    self.assertTrue(card[field], field)
                self.assertEqual(set(card["examples"]), {"pass", "insufficient", "scope_violation",
                                                         "false_positive", "must_block"})
                self.assertEqual(card["runtime_policy"], {"timeout_seconds": 1800, "max_recovery": 1,
                                                         "max_revision_rounds": 1, "model_control": "host_managed"})
                self.assertRegex(card["definition_hash"], "^[a-f0-9]{64}$")
                self.assertRegex(card["template_hash"], "^[a-f0-9]{64}$")
                card["must_check"].clear()
                self.assertTrue(self.p.get_production_role_card("production." + name)["must_check"])
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.get_production_role_card("production.coordinator")

    def test_ui_stage_requires_prototype_and_defines_dependency(self):
        ui = self.p.get_stage_profile("open_spec_product_surface", "ui")
        non_ui = self.p.get_stage_profile("open_spec_product_surface")
        self.assertEqual(ui["max_parallel"], 2)
        self.assertIn("production.ui_prototype", ui["required_role_ids"])
        self.assertNotIn("production.ui_prototype", non_ui["required_role_ids"])
        self.assertIn("production.scenario_interaction", ui["role_dependencies"]["production.ui_prototype"])
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.get_stage_profile("close")

    def test_task_binds_scope_inputs_and_role_methods(self):
        context = self.context()
        context["input_refs"]["unrelated"] = {"ref": "private.txt", "sha256": "b" * 64}
        context["coordinator_conclusion"] = "Ship immediately"
        task = self.p.build_stage_tasks("product_definition", context, [self.package()])["tasks"][0]
        self.assertNotIn("unrelated", task["input_refs"])
        self.assertNotIn("coordinator_conclusion", task)
        self.assertEqual(task["allowed_write_paths"], ["drafts/requirements.md"])
        self.assertIn("production.product_requirements", task["role_definition_hashes"])
        self.assertIn("production.product_requirements", task["task_template_hashes"])
        for field, value in (("delivery_id", "delivery-2"), ("input_snapshot_hash", "d" * 64)):
            changed = copy.deepcopy(context)
            changed[field] = value
            self.assertNotEqual(task["task_hash"], self.p.build_stage_tasks(
                "product_definition", changed, [self.package()])["tasks"][0]["task_hash"])
        changed = self.package()
        changed["allowed_write_paths"] = ["drafts/revised.md"]
        self.assertNotEqual(task["task_hash"], self.p.build_stage_tasks(
            "product_definition", context, [changed])["tasks"][0]["task_hash"])

    def test_stage_roles_cannot_be_missing_or_smuggled(self):
        for packages in ([], [self.package(roles=["production.frontend"])],
                         [self.package(roles=["production.product_requirements", "production.domain_research"]) ]):
            with self.subTest(packages=packages), self.assertRaises(self.p.ProductionProfileError):
                self.p.build_stage_tasks("product_definition", self.context(), packages)
        context = self.context()
        context["condition_flags"] = ["domain_research"]
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.build_stage_tasks("product_definition", context, [self.package()])
        bundle = self.p.build_stage_tasks("product_definition", context, [self.package(
            roles=["production.product_requirements", "production.domain_research"])])
        self.assertIn("production.domain_research", bundle["profile"]["required_role_ids"])

    def test_required_input_and_snapshot_digest_are_enforced(self):
        context = self.context()
        context["input_refs"] = {}
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.build_stage_tasks("product_definition", context, [self.package()])
        for digest in ("bad", "A" * 64, 42, None):
            context = self.context()
            context["input_snapshot_hash"] = digest
            with self.subTest(digest=digest), self.assertRaises(self.p.ProductionProfileError):
                self.p.build_stage_tasks("product_definition", context, [self.package()])

    def test_exact_write_paths_cannot_reach_canonical_or_control_files(self):
        bad_paths = ["/tmp/file", "../secret", "src/../secret", "src//file", "src/", ".", "*",
                     "src/*.py", "C:\\temp\\file", ".git/config", "src/.git/config",
                     ".product-delivery/state.json", "canonical/acceptance.json", "TASK.md", "AGENTS.md"]
        for path in bad_paths:
            package = self.package()
            package["allowed_write_paths"] = [path]
            with self.subTest(path=path), self.assertRaises(self.p.ProductionProfileError):
                self.p.build_stage_tasks("product_definition", self.context(), [package])

    def test_package_dependencies_must_exist_and_be_acyclic(self):
        for packages in ([self.package(depends=["missing"])],
                         [self.package(depends=["requirements"])],
                         [self.package(depends=["other"]), self.package("other", depends=["requirements"])],
                         [self.package(), self.package()]):
            with self.subTest(packages=packages), self.assertRaises(self.p.ProductionProfileError):
                self.p.build_stage_tasks("product_definition", self.context(), packages)

    def test_implementation_requires_current_task_and_orders_integration(self):
        packages = [self.package("code", ["production.backend", "production.test_automation"]),
                    self.package("integrate", ["production.integration"])]
        context = self.context()
        del context["task_id"]
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.build_stage_tasks("implementation_execution", context, packages)
        context["task_id"] = "TASK-01"
        tasks = self.p.build_stage_tasks("implementation_execution", context, packages)["tasks"]
        self.assertEqual(tasks[1]["depends_on"], ["code"])
        self.assertEqual(tasks[1]["task_id"], "TASK-01")
        context["implementation_roles"] = ["production.backend"]
        narrowed = self.p.build_stage_tasks("implementation_execution", context, [
            self.package("code", ["production.backend"]), self.package("integrate", ["production.integration"])])
        self.assertEqual(set(narrowed["profile"]["required_role_ids"]),
                         {"production.backend", "production.integration"})

    def test_required_outputs_cannot_remove_role_deliverables(self):
        package = self.package()
        package["required_outputs"] = ["extra_analysis"]
        task = self.p.build_stage_tasks("product_definition", self.context(), [package])["tasks"][0]
        self.assertIn("extra_analysis", task["required_outputs"])
        self.assertIn("product_blueprint", task["required_outputs"])

    def test_complete_result_is_normalized_without_mutating_caller(self):
        task = self.task()
        result = self.result(task)
        normalized = self.p.validate_production_result(task, result)
        self.assertEqual(normalized, result)
        normalized["artifacts"].clear()
        self.assertTrue(result["artifacts"])

    def test_ready_claim_cannot_hide_incomplete_checks_or_outputs(self):
        task = self.task()
        cases = [("status", "passed"), ("check_records", []), ("artifacts", []),
                 ("completion_evidence", {}), ("blockers", ["Schema owner unavailable"]),
                 ("unresolved_questions", ["Which actor can cancel imports?"]),
                 ("task_hash", "d" * 64), ("input_snapshot_hash", "e" * 64),
                 ("role_ids", ["production.integration"]), ("handoff", "")]
        for field, value in cases:
            result = self.result(task)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)

    def test_check_evidence_cannot_be_missing_unbound_or_duplicate(self):
        task = self.task()
        for field, value in (("evidence_refs", []), ("evidence_refs", ["private.txt#anything"]),
                             ("reason", ""), ("outcome", "blocked"), ("check_id", "invented")):
            result = self.result(task)
            result["check_records"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)
        result = self.result(task)
        result["check_records"].append(copy.deepcopy(result["check_records"][0]))
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.validate_production_result(task, result)

    def test_completion_must_reference_matching_produced_artifact(self):
        task = self.task()
        for ref in ("private.txt", next(iter(task["input_refs"].values()))["ref"]):
            result = self.result(task)
            result["completion_evidence"][task["required_outputs"][0]] = [ref]
            with self.subTest(ref=ref), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)

    def test_change_manifest_requires_permitted_path_and_artifact_hash(self):
        task = self.task()
        cases = [("path", "drafts/unallocated.md"), ("path", "../requirements.md"),
                 ("staged_path", "other.md"), ("result_sha256", "d" * 64),
                 ("base_sha256", "e" * 64), ("operation", "rename")]
        for field, value in cases:
            result = self.result(task)
            result["changes"][0][field] = value
            with self.subTest(field=field), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)
        result = self.result(task)
        result["changes"].append(copy.deepcopy(result["changes"][0]))
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.validate_production_result(task, result)

    def test_delete_cannot_claim_replacement_and_modify_needs_base_hash(self):
        task = self.task()
        for operation in ("modify", "delete"):
            result = self.result(task)
            result["changes"][0]["operation"] = operation
            with self.subTest(operation=operation), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)
        result = self.result(task)
        result["changes"][0].update(operation="delete", base_sha256="b" * 64,
                                     result_sha256=None, staged_path=None)
        self.p.validate_production_result(task, result)

    def test_missing_input_is_reportable_but_requires_reason(self):
        task = self.task()
        result = self.result(task)
        result.update(status="needs_input", artifacts=[], changes=[], check_records=[],
                      completion_evidence={}, blockers=["Product owner must provide a supported actor list."])
        self.p.validate_production_result(task, result)
        result["blockers"] = []
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.validate_production_result(task, result)

    def test_rehashed_task_cannot_forge_role_checks_or_permissions(self):
        original = self.task()
        for field, value in (("must_check", []), ("required_outputs", []),
                             ("permissions", {"canonical_write": True}),
                             ("role_definition_hashes", {})):
            task = copy.deepcopy(original)
            task[field] = value
            task["task_hash"] = self.p.stable_hash({key: value for key, value in task.items()
                                                   if key != "task_hash"})
            result = self.result(original)
            result["task_hash"] = task["task_hash"]
            with self.subTest(field=field), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)

    def test_each_stage_can_dispatch_its_complete_enabled_role_set(self):
        for stage in ("product_definition", "architecture_version_planning", "open_spec_product_surface",
                      "test_design", "implementation_execution", "delivery_preparation"):
            for branch in ("ui", "non_ui"):
                profile = self.p.get_stage_profile(stage, branch)
                context = self.context()
                context.update(project_type=branch, condition_flags=list(profile["conditional_roles"]))
                roles = profile["required_role_ids"] + list(profile["conditional_roles"].values())
                with self.subTest(stage=stage, branch=branch):
                    task = self.p.build_stage_tasks(stage, context, [self.package(roles=roles)])["tasks"][0]
                    self.p.validate_production_result(task, self.result(task))

    def test_malformed_branch_never_leaks_unstructured_type_error(self):
        for branch in ([], {}, 0, None, "mobile"):
            with self.subTest(branch=branch), self.assertRaises(self.p.ProductionProfileError):
                self.p.get_stage_profile("product_definition", branch)

    def test_stale_role_definitions_cannot_create_tasks(self):
        for field, value in (("task_steps", []), ("mission", "Invent new scope"),
                             ("permissions", {"canonical_write": True})):
            card = self.p.get_production_role_card("production.product_requirements")
            card[field] = value
            context = self.context()
            with self.subTest(field=field), patch.dict(self.p._ROLE_CARDS, {card["role_id"]: card}):
                with self.assertRaises(self.p.ProductionProfileError):
                    self.p.build_stage_tasks("product_definition", context, [self.package()])

    def test_input_files_require_safe_paths_real_digest_and_matching_branch(self):
        key = self.p.get_production_role_card("production.product_requirements")["required_inputs"][0]
        for field, value in (("ref", "../secret.txt"), ("sha256", "claimed-hash"),
                             ("project_type", "ui"), ("project_type", [])):
            context = self.context()
            context["input_refs"][key][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(self.p.ProductionProfileError):
                self.p.build_stage_tasks("product_definition", context, [self.package()])

    def test_malformed_and_duplicate_result_rows_are_rejected(self):
        task = self.task()
        for field, value in (("artifacts", [None]), ("changes", [{}]), ("check_records", "done"),
                             ("completion_evidence", []), ("handoff", {}), ("risks", [42])):
            result = self.result(task)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(self.p.ProductionProfileError):
                self.p.validate_production_result(task, result)
        result = self.result(task)
        result["artifacts"].append(copy.deepcopy(result["artifacts"][0]))
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.validate_production_result(task, result)
        result = self.result(task)
        result["write_intents"] = ["close_delivery"]
        with self.assertRaises(self.p.ProductionProfileError):
            self.p.validate_production_result(task, result)


if __name__ == "__main__":
    unittest.main()
