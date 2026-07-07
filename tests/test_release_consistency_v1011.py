import json
import unittest
from pathlib import Path

from product_delivery_agent.gatekeeper import PLUGIN_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.12"


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
            self.assertIn("version-1.0.12", text)
            self.assertIn(
                "dist/waygate-product-delivery-1.0.12.tar.gz",
                text,
            )

    def test_changelog_records_simplified_post_1_0_10_roadmap(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text("utf-8")
        self.assertIn("## 1.0.12", changelog)
        self.assertIn("V1.1 多 Agent 评审编排产品化", changelog)
        self.assertIn("V2.0 外部工作流集成", changelog)


if __name__ == "__main__":
    unittest.main()
