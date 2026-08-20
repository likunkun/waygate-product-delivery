import json
import unittest
from pathlib import Path

from product_delivery_agent.gatekeeper import PLUGIN_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.33"


class ReleaseConsistencyV1011Tests(unittest.TestCase):
    def test_runtime_manifest_and_generated_template_versions_match(self):
        self.assertEqual(PLUGIN_VERSION, EXPECTED_VERSION)

        manifest = json.loads(
            (
                REPO_ROOT
                / "plugins"
                / "waygate-product-delivery"
                / ".codex-plugin"
                / "plugin.json"
            ).read_text("utf-8")
        )
        self.assertTrue(manifest["version"].startswith(EXPECTED_VERSION))

        closure_template = json.loads(
            (
                REPO_ROOT
                / "plugins"
                / "waygate-product-delivery"
                / "templates"
                / "closure-artifact-template.json"
            ).read_text("utf-8")
        )
        self.assertEqual(closure_template["plugin_version"], EXPECTED_VERSION)

    def test_readmes_reference_current_release_artifacts(self):
        for relative_path in ("README.md", "README.zh-CN.md"):
            text = (REPO_ROOT / relative_path).read_text("utf-8")
            self.assertIn(f"version-{EXPECTED_VERSION}", text)
            self.assertIn(
                f"dist/waygate-product-delivery-{EXPECTED_VERSION}.tar.gz",
                text,
            )

    def test_changelog_records_simplified_post_1_0_10_roadmap(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text("utf-8")
        self.assertIn(f"## {EXPECTED_VERSION}", changelog)
        self.assertIn("implementation_baseline", changelog)
        self.assertIn("prototype_bindings", changelog)
        self.assertIn("record_task_prototype_conformance", changelog)
        self.assertIn("runtime_provenance", changelog)
        self.assertIn("recover_legacy_active_delivery", changelog)
        self.assertIn("legacy_unverified", changelog)
        self.assertIn("recover_stale_host_goal_checkpoint", changelog)
        self.assertIn("host_goal_checkpoint_superseded", changelog)
        self.assertIn("host_goal_owner_transferred", changelog)
        self.assertIn("host_goal_owner_claim_superseded", changelog)
        self.assertIn("CODEX_THREAD_ID", changelog)
        self.assertIn("host_goal_binding", changelog)
        self.assertIn("prepare_host_goal_reconciliation", changelog)
        self.assertIn("create_goal", changelog)
        self.assertIn("get_goal", changelog)
        self.assertIn("update_goal", changelog)
        self.assertIn("prototype_design_integrity", changelog)
        self.assertIn("record_ui_prototype_design_bundle", changelog)
        self.assertIn("product_domain_hash", changelog)
        self.assertIn("review_domain_hash", changelog)
        self.assertIn("clean_surface", changelog)
        self.assertIn("review_annotation_set", changelog)
        self.assertIn("门禁验证客观事实", changelog)
        self.assertIn("多 Agent 判断设计质量", changelog)
        self.assertIn("retire_model_execution_policy", changelog)
        self.assertIn("模型选择完全由用户和 Codex 宿主管理", changelog)
        self.assertIn("product_baseline", changelog)
        self.assertIn("test_coverage_plan", changelog)
        self.assertNotIn("启动交付，全速模式，多 Agent 模式", changelog)
        self.assertIn("recover_stale_launch_package", changelog)
        self.assertIn("implementation_package_superseded", changelog)
        self.assertIn("启动交付，多 Agent 模式", changelog)
        self.assertIn("authorization_pending", changelog)
        self.assertIn("prototype_contract", changelog)
        self.assertIn("prototype_production_conformance", changelog)
        self.assertIn("ui_conformance", changelog)
        self.assertIn("required_actor_roles", changelog)
        self.assertIn("ordinary_entry_path", changelog)
        self.assertIn("ui_change_type", changelog)
        self.assertIn("baseline_entry_path", changelog)
        self.assertIn("V1.1 多 Agent 评审编排产品化", changelog)
        self.assertIn("V2.0 外部工作流集成", changelog)


if __name__ == "__main__":
    unittest.main()
