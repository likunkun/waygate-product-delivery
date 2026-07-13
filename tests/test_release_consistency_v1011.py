import json
import unittest
from pathlib import Path

from product_delivery_agent.gatekeeper import PLUGIN_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.19"


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
            self.assertIn("version-1.0.19", text)
            self.assertIn(
                "dist/waygate-product-delivery-1.0.19.tar.gz",
                text,
            )

    def test_changelog_records_simplified_post_1_0_10_roadmap(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text("utf-8")
        self.assertIn("## 1.0.19", changelog)
        self.assertIn("execution_model_policy", changelog)
        self.assertIn("启动交付，全速模式，多 Agent 模式", changelog)
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
