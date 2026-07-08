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
            self.assertEqual(manifest["version"], "1.0.14")
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
                    "启动交付",
                    "启动交付，允许降级评审",
                    "查看状态",
                    "验证闭包",
                    "停止交付",
                ],
            )
            self.assertIn("启动交付", manifest_text)

    def test_package_includes_runtime_assets_and_v0_10_closure_assets(self):
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
                "templates/scope-scenario-matrix.md",
                "templates/multi-agent-scenario-review.md",
                "templates/multi-agent-test-review.md",
                "templates/multi-agent-test-coverage-review.md",
                "templates/multi-agent-test-implementation-review.md",
                "templates/user-confirmation.md",
                "templates/planned-e2e-obligations.md",
                "templates/executed-browser-evidence.md",
                "templates/closure-validator-result.md",
                "templates/implementation-goal.md",
                "templates/implementation-launch-authorization.md",
                "templates/task-queue.md",
                "templates/stop-guard-result.md",
                "scripts/validate-closure-artifact.py",
                "scripts/formal-gate-validation-plan.md",
                "runtime/product_delivery_agent/finalization.py",
                "runtime/product_delivery_agent/gatekeeper.py",
                "runtime/product_delivery_agent/continuation.py",
                "runtime/product_delivery_agent/transition_journal.py",
                "policies/lifecycle.json",
                "policies/upgrade-retention.md",
                "policies/waygate-controller-readonly.md",
            ]
            for relative_path in expected_files:
                self.assertTrue((root / relative_path).is_file(), relative_path)
            skill_markdown = (
                root / "skills" / "waygate-product-delivery" / "SKILL.md"
            ).read_text("utf-8")
            self.assertIn("启动交付", skill_markdown)
            self.assertIn("停止交付", skill_markdown)
            self.assertIn("`start` / `stop`", skill_markdown)
            self.assertIn("planning-with-files", skill_markdown)
            self.assertIn("open-spec", skill_markdown)
            self.assertIn("ui-ux-pro-max", skill_markdown)
            self.assertIn("webapp-testing", skill_markdown)
            self.assertIn("禁止实现", skill_markdown)
            self.assertIn("未确认 prototype", skill_markdown)
            self.assertIn("未显式确认本地 1:1 HTML prototype", skill_markdown)
            self.assertIn("pre-handoff", skill_markdown)
            self.assertIn("pre-closure", skill_markdown)
            self.assertIn("confirm_ui_prototype", skill_markdown)
            self.assertIn("prototype 每次修订后都必须重新确认", skill_markdown)
            self.assertIn("不要在 TASK 未完成时停止", skill_markdown)
            self.assertIn("delivery goal", skill_markdown)
            self.assertIn("validate-closure-artifact.py", skill_markdown)
            self.assertIn("closure-like", skill_markdown)
            self.assertIn("missing goal", skill_markdown)
            self.assertIn("review_mode", skill_markdown)
            self.assertNotIn("启动交付，允许多Agent评审", skill_markdown)
            self.assertIn("启动交付，允许降级评审", skill_markdown)
            self.assertIn("用户面对的确认只保留两次", skill_markdown)
            self.assertIn(
                "combined requirements freeze + planned E2E coverage 确认",
                skill_markdown,
            )
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
            scenario_review_template = (
                root / "templates" / "multi-agent-scenario-review.md"
            ).read_text("utf-8")
            self.assertIn("baseline_inheritance_review", scenario_review_template)
            planned_template = (
                root / "templates" / "planned-e2e-obligations.md"
            ).read_text("utf-8")
            self.assertIn("baseline_entry_path", planned_template)
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
                "v0.10",
            )
            self.assertEqual(
                closure_template["canonical_validator"],
                "product_delivery_agent.finalization",
            )
            self.assertEqual(closure_template["plugin_version"], "1.0.14")
            self.assertIn("full_stack_browser_evidence", closure_template)
            self.assertEqual(closure_template["required_commands"][0]["exit_code"], 0)
            self.assertIn("supporting_validators", closure_template)
            validator_script = (
                root / "scripts" / "validate-closure-artifact.py"
            ).read_text("utf-8")
            self.assertIn("RUNTIME_DIR", validator_script)
            self.assertIn("run_finalize_cli", validator_script)
            self.assertIn("product_delivery_agent.finalization", validator_script)
            self.assertNotIn("Import and call validate_feature_closure", validator_script)

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
                "waygate-product-delivery-1.0.14.tar.gz",
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
            self.assertEqual(policy["activation_command"], "start")
            self.assertEqual(policy["deactivation_command"], "stop")
            self.assertTrue(policy["current_project_only"])

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
