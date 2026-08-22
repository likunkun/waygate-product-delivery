import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.plugin_packaging import (
    build_codex_plugin_distribution,
    package_codex_plugin,
)


class PluginPackagingTests(unittest.TestCase):
    def test_package_creates_valid_plugin_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)

            result = package_codex_plugin(repo_root)

            manifest_path = result["plugin_root"] / ".codex-plugin" / "plugin.json"
            manifest_text = manifest_path.read_text("utf-8")
            manifest = json.loads(manifest_text)
            self.assertEqual(manifest["name"], "waygate-product-delivery")
            self.assertEqual(manifest["version"], "1.0.34")
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertEqual(
                manifest["author"]["name"],
                "Waygate Product Delivery Maintainers",
            )
            self.assertNotIn("hooks", manifest)
            self.assertIn("interface", manifest)
            self.assertEqual(
                manifest["interface"]["displayName"],
                "Waygate Product Delivery",
            )
            self.assertEqual(
                manifest["interface"]["defaultPrompt"],
                [
                    '$waygate-product-delivery {"schema_version":"v1","action":"inspect"}',
                    '$waygate-product-delivery {"schema_version":"v1","action":"status"}',
                    '$waygate-product-delivery {"schema_version":"v1","action":"start","feature_slug":"<feature-slug>","start_mode":"resume_or_create","review_mode_if_created":"pending_selection"}',
                    '$waygate-product-delivery {"schema_version":"v1","action":"pause"}',
                    '$waygate-product-delivery start <feature-slug> multi-agent',
                    '$waygate-product-delivery status',
                    '$waygate-product-delivery pause',
                    '$waygate-product-delivery close',
                ],
            )
            self.assertIn("$waygate-product-delivery", manifest_text)

    def test_packaging_removes_legacy_plugin_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            legacy_root = repo_root / "plugins" / "product-delivery-agent"
            manifest = legacy_root / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps({"name": "product-delivery-agent"}), encoding="utf-8"
            )

            package_codex_plugin(repo_root)

            self.assertFalse(legacy_root.exists())

    def test_package_includes_runtime_assets_and_v0_11_closure_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = package_codex_plugin(Path(tmp))
            root = result["plugin_root"]

            expected_files = [
                "skills/waygate-product-delivery/SKILL.md",
                "hooks/README.md",
                "templates/product-brief.md",
                "templates/closure-artifact-template.json",
                "templates/coverage-matrix-template.json",
                "templates/negative-scope-guard-checklist.md",
                "templates/startup-checklist.md",
                "templates/required-skills-checklist.md",
                "templates/open-spec-gate.md",
                "templates/ui-prototype-gate.md",
                "templates/ui-prototype-contract.json",
                "templates/ui-prototype-design-bundle.json",
                "templates/acceptance-content-scan-report.json",
                "templates/prototype-production-conformance.md",
                "templates/scope-scenario-matrix.md",
                "templates/multi-agent-scenario-review.md",
                "templates/multi-agent-test-review.md",
                "templates/multi-agent-test-coverage-review.md",
                "templates/multi-agent-test-implementation-review.md",
                "templates/multi-agent-ui-conformance-review.md",
                "templates/user-confirmation.md",
                "templates/planned-e2e-obligations.md",
                "templates/executed-browser-evidence.md",
                "templates/closure-validator-result.md",
                "templates/implementation-goal.md",
                "templates/implementation-launch-authorization.md",
                "templates/task-queue.md",
                "templates/stop-guard-result.md",
                "scripts/validate-closure-artifact.py",
                "scripts/waygate-control.py",
                "scripts/formal-gate-validation-plan.md",
                "agents/openai.yaml",
                "runtime/product_delivery_agent/finalization.py",
                "runtime/product_delivery_agent/gatekeeper.py",
                "runtime/product_delivery_agent/continuation.py",
                "runtime/product_delivery_agent/host_goal.py",
                "runtime/product_delivery_agent/transition_journal.py",
                "runtime/product_delivery_agent/evidence_artifacts.py",
                "runtime/product_delivery_agent/implementation_baseline.py",
                "runtime/product_delivery_agent/journey_slice_tasks.py",
                "runtime/product_delivery_agent/prototype_design.py",
                "runtime/product_delivery_agent/ui_prototype.py",
                "policies/lifecycle.json",
                "policies/upgrade-retention.md",
                "policies/waygate-controller-readonly.md",
            ]
            for relative_path in expected_files:
                self.assertTrue((root / relative_path).is_file(), relative_path)
            skill_markdown = (
                root / "skills" / "waygate-product-delivery" / "SKILL.md"
            ).read_text("utf-8")
            self.assertIn(
                'description: "Codex-native product delivery workflow with shorthand commands for start, status, inspect, pause, resume, close, and abandon."',
                skill_markdown,
            )
            self.assertIn("$waygate-product-delivery", skill_markdown)
            self.assertIn("严格 JSON", skill_markdown)
            self.assertIn("禁止自然语言隐式触发", skill_markdown)
            self.assertIn("prepare_abandon", skill_markdown)
            self.assertIn("旧 `stop()` 已退役", skill_markdown)
            self.assertNotIn("说 `启动交付`", skill_markdown)
            self.assertIn("planning-with-files", skill_markdown)
            self.assertIn("open-spec", skill_markdown)
            self.assertIn("ui-ux-pro-max", skill_markdown)
            self.assertIn("webapp-testing", skill_markdown)
            self.assertIn("禁止实现", skill_markdown)
            self.assertIn("product_baseline", skill_markdown)
            self.assertIn("test_coverage_plan", skill_markdown)
            self.assertIn("pre-handoff", skill_markdown)
            self.assertIn("pre-closure", skill_markdown)
            self.assertIn("prepare_product_baseline_confirmation", skill_markdown)
            self.assertIn("confirm_product_baseline", skill_markdown)
            self.assertIn("prepare_test_coverage_confirmation", skill_markdown)
            self.assertIn("confirm_test_coverage_plan", skill_markdown)
            self.assertIn("record_prototype_production_conformance", skill_markdown)
            self.assertIn("ui_conformance", skill_markdown)
            self.assertIn(
                "recover_stale_host_goal_checkpoint", skill_markdown
            )
            self.assertIn("product-delivery-agent@1.0.8", skill_markdown)
            self.assertIn("runtime_provenance", skill_markdown)
            self.assertIn("delivery_activated", skill_markdown)
            self.assertIn("legacy_unverified", skill_markdown)
            self.assertIn("recover_legacy_active_delivery", skill_markdown)
            self.assertIn("V1.0.29", skill_markdown)
            self.assertIn("V1.0.30", skill_markdown)
            self.assertIn("implementation_baseline", skill_markdown)
            self.assertIn("prototype_bindings", skill_markdown)
            self.assertIn("record_task_prototype_conformance", skill_markdown)
            self.assertIn("不得静默降级", skill_markdown)
            self.assertIn("semantic snapshot", skill_markdown)
            self.assertIn("record_ui_prototype_design_bundle", skill_markdown)
            self.assertIn("prototype_design_integrity", skill_markdown)
            self.assertIn("clean_surface", skill_markdown)
            self.assertIn("review_annotation_set", skill_markdown)
            self.assertIn("acceptance_content_separation", skill_markdown)
            self.assertIn("高保真产品原型只能包含真实产品内容", skill_markdown)
            self.assertIn("prototype-acceptance-content-scan-v1", skill_markdown)
            self.assertIn("不得进入视觉偏差裁决", skill_markdown)
            self.assertIn("门禁验证客观事实", skill_markdown)
            self.assertIn("多 Agent 判断设计质量", skill_markdown)
            self.assertIn("不要在 TASK 未完成时停止", skill_markdown)
            self.assertIn("delivery goal", skill_markdown)
            self.assertIn("validate-closure-artifact.py", skill_markdown)
            self.assertIn("closure-like", skill_markdown)
            self.assertIn("missing goal", skill_markdown)
            self.assertIn("review_mode", skill_markdown)
            self.assertIn("Shorthand Commands", skill_markdown)
            self.assertIn("start <slug> multi-agent", skill_markdown)
            self.assertIn("start <slug> role-play", skill_markdown)
            self.assertNotIn("启动交付，允许多Agent评审", skill_markdown)
            self.assertIn("review_mode_if_created=role_simulation_allowed", skill_markdown)
            self.assertIn("multi_agent_mode_selection", skill_markdown)
            self.assertEqual(skill_markdown.count("execution_model_policy"), 1)
            self.assertNotIn("model-profiles.json", skill_markdown)
            self.assertIn("inspect_startup_request", skill_markdown)
            self.assertIn("retire_model_execution_policy", skill_markdown)
            self.assertIn("模型选择完全由用户和 Codex 宿主管理", skill_markdown)
            self.assertIn("不得重新 start 当前 delivery", skill_markdown)
            self.assertIn("current_delivery", skill_markdown)
            self.assertIn("结构化 review gate", skill_markdown)
            self.assertIn("用户面对的确认只保留两次", skill_markdown)
            self.assertIn(
                "先确认需求范围和 UI 原型或非 UI 行为契约",
                skill_markdown,
            )
            self.assertIn("产品基线确认前不得生成详细测试用例", skill_markdown)
            self.assertNotIn("确认按当前交付包开始实现", skill_markdown)
            self.assertIn("implementation_launch_authorization", skill_markdown)
            self.assertIn("custom artifact", skill_markdown)
            self.assertIn("target-specific validator", skill_markdown)
            self.assertIn("supporting evidence", skill_markdown)
            self.assertIn("product_delivery_agent.finalization", skill_markdown)
            self.assertIn("closure validator 未通过", skill_markdown)
            self.assertIn("planned E2E", skill_markdown)
            self.assertIn("multi_agent_test_coverage_review", skill_markdown)
            self.assertIn("multi_agent_test_implementation_review", skill_markdown)
            self.assertIn("item-level coverage", skill_markdown)
            self.assertIn("false-positive risk", skill_markdown)
            self.assertIn("RED test", skill_markdown)
            self.assertIn("closure validator", skill_markdown)
            self.assertIn(".product-delivery/state.json", skill_markdown)
            self.assertIn("不能替代 Product Delivery 主流程", skill_markdown)
            self.assertIn("Main Flow Continuation", skill_markdown)
            self.assertIn("continuation guard", skill_markdown)
            self.assertIn("must_continue", skill_markdown)
            self.assertIn("wait_for_user", skill_markdown)
            self.assertIn("canonical_closure_plugin_version", skill_markdown)
            self.assertIn("full_stack_browser_e2e", skill_markdown)
            self.assertIn("mocked_api_browser_e2e", skill_markdown)
            self.assertIn("business API", skill_markdown)
            self.assertIn("ui_change_type", skill_markdown)
            self.assertIn("baseline_entry_path", skill_markdown)
            self.assertIn("incremental_existing_surface", skill_markdown)
            self.assertIn("required_actor_roles", skill_markdown)
            self.assertIn("ordinary_entry_path", skill_markdown)
            self.assertIn("execution_segment_id", skill_markdown)
            self.assertIn("role-accurate Browser E2E", skill_markdown)
            self.assertIn("verified_action_assertions", skill_markdown)
            self.assertIn("recover_stale_launch_package", skill_markdown)
            self.assertIn("implementation_package_superseded", skill_markdown)
            self.assertIn("prepare_host_goal_activation", skill_markdown)
            self.assertIn("prepare_host_goal_reconciliation", skill_markdown)
            self.assertIn("record_host_goal_observation", skill_markdown)
            self.assertIn("CODEX_THREAD_ID", skill_markdown)
            self.assertIn("prepare_host_goal_owner_claim", skill_markdown)
            self.assertIn(
                "record_host_goal_owner_claim_observation", skill_markdown
            )
            self.assertIn(
                "recover_stale_host_goal_owner_claim", skill_markdown
            )
            self.assertIn("host_goal_owner_transferred", skill_markdown)
            self.assertIn("orphaned_unreachable", skill_markdown)
            self.assertIn("get_goal", skill_markdown)
            self.assertIn("create_goal", skill_markdown)
            self.assertIn("update_goal", skill_markdown)
            self.assertIn("host_turn_id", skill_markdown)
            self.assertIn("decision_id", skill_markdown)
            self.assertIn("Goal 工具不可用", skill_markdown)
            self.assertIn("不得使用 20 秒 watchdog", skill_markdown)
            required_skills = (
                root / "templates" / "required-skills-checklist.md"
            ).read_text("utf-8")
            self.assertIn("planning-with-files", required_skills)
            self.assertIn("open-spec-feature-closure", required_skills)
            scenario_template = (
                root / "templates" / "scope-scenario-matrix.md"
            ).read_text("utf-8")
            self.assertIn("Journey ID", scenario_template)
            self.assertIn("Acceptance Anchors", scenario_template)
            ui_template = (
                root / "templates" / "ui-prototype-gate.md"
            ).read_text("utf-8")
            self.assertIn("ui_change_type", ui_template)
            self.assertIn("continuity_mapping", ui_template)
            self.assertIn("product_baseline", ui_template)
            self.assertNotIn("confirm_ui_prototype", ui_template)
            startup_template = (
                root / "templates" / "startup-checklist.md"
            ).read_text("utf-8")
            self.assertIn("product_baseline", startup_template)
            self.assertIn("test_coverage_plan", startup_template)
            self.assertIn("record_ui_prototype_design_bundle", startup_template)
            self.assertIn("clean_surface", startup_template)
            self.assertIn("review_annotation_set", startup_template)
            self.assertIn("CODEX_THREAD_ID", startup_template)
            self.assertIn("prepare_host_goal_owner_claim", startup_template)
            self.assertLess(
                startup_template.index("product_baseline"),
                startup_template.index("planned E2E"),
            )
            design_bundle_template = json.loads(
                (root / "templates" / "ui-prototype-design-bundle.json").read_text(
                    "utf-8"
                )
            )
            self.assertEqual(design_bundle_template["bundle_version"], "v2")
            self.assertIn("clean_surface", design_bundle_template)
            self.assertIn(
                "browser_preflight_probe_path",
                design_bundle_template["clean_surface"],
            )
            runtime_check = design_bundle_template["clean_surface"][
                "runtime_checks"
            ][0]
            self.assertNotIn("status", runtime_check)
            self.assertNotIn("annotation_nodes_present", runtime_check)
            self.assertIn("product_context_contract", design_bundle_template)
            self.assertIn("review_annotation_set", design_bundle_template)
            self.assertIn(
                "intended_product_ui_callouts",
                design_bundle_template,
            )
            self.assertIn(
                "acceptance_content_separation",
                design_bundle_template,
            )
            evidence_ref = design_bundle_template["product_context_contract"][
                "coverage_rows"
            ][0]["evidence_refs"][0]
            self.assertEqual(
                set(evidence_ref), {"artifact_path", "artifact_sha256"}
            )
            scenario_review_template = (
                root / "templates" / "multi-agent-scenario-review.md"
            ).read_text("utf-8")
            self.assertIn("baseline_inheritance_review", scenario_review_template)
            self.assertIn("prototype_design_bundle_hash", scenario_review_template)
            self.assertIn("prototype_design_audit_hash", scenario_review_template)
            self.assertIn("reviewed_design_dimensions", scenario_review_template)
            self.assertIn("global_visual_continuity_findings", scenario_review_template)
            self.assertIn("annotation_separation_findings", scenario_review_template)
            ui_conformance_template = (
                root / "templates" / "multi-agent-ui-conformance-review.md"
            ).read_text("utf-8")
            self.assertIn("reviewed_design_dimensions", ui_conformance_template)
            self.assertIn("global_visual_continuity_findings", ui_conformance_template)
            self.assertIn("annotation_separation_findings", ui_conformance_template)
            planned_template = (
                root / "templates" / "planned-e2e-obligations.md"
            ).read_text("utf-8")
            self.assertIn("baseline_entry_path", planned_template)
            self.assertIn("required_actor_roles", planned_template)
            self.assertIn("ordinary_entry_path", planned_template)
            implementation_review_template = (
                root / "templates" / "multi-agent-test-implementation-review.md"
            ).read_text("utf-8")
            for review_template_name in (
                "multi-agent-scenario-review.md",
                "multi-agent-test-review.md",
                "multi-agent-test-coverage-review.md",
                "multi-agent-test-implementation-review.md",
                "multi-agent-ui-conformance-review.md",
            ):
                review_template = (
                    root / "templates" / review_template_name
                ).read_text("utf-8")
                self.assertIn("reviewer_agent_ids", review_template)
                self.assertIn("reviewer_spawn_source", review_template)
            self.assertIn("actor_role_findings", implementation_review_template)
            self.assertIn("annotation_only_findings", implementation_review_template)
            self.assertIn("verified_action_assertions", implementation_review_template)
            closure_template = json.loads(
                (root / "templates" / "closure-artifact-template.json").read_text(
                    "utf-8"
                )
            )
            self.assertIn("artifact_root", closure_template)
            self.assertIn("artifact_generation_command", closure_template)
            self.assertIn("e2e_evidence_paths", closure_template)
            self.assertEqual(
                closure_template["canonical_schema_version"],
                "v0.11",
            )
            self.assertEqual(
                closure_template["canonical_validator"],
                "product_delivery_agent.finalization",
            )
            self.assertEqual(closure_template["plugin_version"], "1.0.34")
            self.assertIn("prototype_conformance", closure_template)
            self.assertIn(
                "conformance_evidence_sha256",
                closure_template["prototype_conformance"],
            )
            self.assertIn("full_stack_browser_evidence", closure_template)
            self.assertTrue(
                closure_template["full_stack_browser_evidence"][
                    "role_accurate_required"
                ]
            )
            self.assertEqual(closure_template["required_commands"][0]["exit_code"], 0)
            self.assertIn("supporting_validators", closure_template)
            validator_script = (
                root / "scripts" / "validate-closure-artifact.py"
            ).read_text("utf-8")
            self.assertIn("RUNTIME_DIR", validator_script)
            self.assertIn("run_finalize_cli", validator_script)
            self.assertIn("product_delivery_agent.finalization", validator_script)
            self.assertNotIn("Import and call validate_feature_closure", validator_script)
            control_script = (root / "scripts" / "waygate-control.py").read_text("utf-8")
            self.assertIn("run_control_cli", control_script)
            self.assertIn("RUNTIME_DIR", control_script)
            hooks_readme = (root / "hooks" / "README.md").read_text("utf-8")
            self.assertIn("does not provide a timed continuation hook", hooks_readme)
            self.assertIn("Codex Host Goal", hooks_readme)
            self.assertIn("CODEX_THREAD_ID", hooks_readme)

            source_runtime = Path(__file__).resolve().parents[1] / "src" / (
                "product_delivery_agent"
            )
            packaged_runtime = root / "runtime" / "product_delivery_agent"
            source_files = sorted(path.name for path in source_runtime.glob("*.py"))
            packaged_files = sorted(path.name for path in packaged_runtime.glob("*.py"))
            self.assertEqual(packaged_files, source_files)
            for file_name in source_files:
                self.assertEqual(
                    (packaged_runtime / file_name).read_bytes(),
                    (source_runtime / file_name).read_bytes(),
                    file_name,
                )

    def test_repo_marketplace_config_points_to_local_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            package_codex_plugin(repo_root)

            marketplace = json.loads(
                (repo_root / ".agents" / "plugins" / "marketplace.json").read_text(
                    "utf-8"
                )
            )

            self.assertEqual(marketplace["name"], "repo-local")
            entry = marketplace["plugins"][0]
            self.assertEqual(entry["name"], "waygate-product-delivery")
            self.assertEqual(
                entry["source"]["path"],
                "./plugins/waygate-product-delivery",
            )
            self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
            self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")

    def test_distribution_archive_contains_installable_waygate_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            package_codex_plugin(repo_root)

            archive_path = build_codex_plugin_distribution(repo_root)

            self.assertEqual(
                archive_path.name,
                "waygate-product-delivery-1.0.34.tar.gz",
            )
            self.assertTrue(archive_path.is_file())

    def test_lifecycle_is_dormant_by_default_and_start_stop_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = package_codex_plugin(Path(tmp))
            policy = json.loads(
                (result["plugin_root"] / "policies" / "lifecycle.json").read_text(
                    "utf-8"
                )
            )

            self.assertTrue(policy["dormant_by_default"])
            self.assertTrue(policy["explicit_invocation_required"])
            self.assertEqual(policy["control_script"], "scripts/waygate-control.py")
            self.assertIn("start", policy["actions"])
            self.assertIn("abandon", policy["actions"])
            self.assertEqual(policy["retired_actions"], ["stop"])
            self.assertTrue(policy["current_project_only"])
            openai_config = (
                result["plugin_root"] / "agents" / "openai.yaml"
            ).read_text("utf-8")
            self.assertIn("allow_implicit_invocation: false", openai_config)

    def test_upgrade_policy_preserves_product_delivery_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = package_codex_plugin(Path(tmp))
            upgrade_policy = (
                result["plugin_root"] / "policies" / "upgrade-retention.md"
            ).read_text("utf-8")

            self.assertIn(".product-delivery/", upgrade_policy)
            self.assertIn("must not delete", upgrade_policy)

    def test_waygate_controller_boundary_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = package_codex_plugin(Path(tmp))
            boundary = (
                result["plugin_root"] / "policies" / "waygate-controller-readonly.md"
            ).read_text("utf-8")

            self.assertIn("read-only", boundary)
            self.assertIn("must not mutate", boundary)


if __name__ == "__main__":
    unittest.main()
