import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.startup_guard import (
    detect_project_type,
    validate_current_open_spec,
    validate_planning_files,
    validate_required_delivery_gates,
)


OPEN_SPEC_FILES = [
    "00-change-request.md",
    "01-requirements.md",
    "02-specification.md",
    "03-technical-solution.md",
    "04-storage-design.md",
    "05-development-plan.md",
    "06-test-cases.md",
    "07-release-retrospective.md",
    "08-stage-handoff.md",
]


class StartupGuardTests(unittest.TestCase):
    def test_detect_project_type_identifies_web_ui_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "internal" / "usagereport" / "web" / "assets").mkdir(
                parents=True
            )
            (root / "internal" / "usagereport" / "web" / "assets" / "app.js").write_text(
                "console.log('ui')\n",
                encoding="utf-8",
            )
            (root / "internal" / "usagereport" / "web" / "assets" / "index.html").write_text(
                "<main></main>\n",
                encoding="utf-8",
            )

            self.assertEqual(detect_project_type(root), "ui")

    def test_current_open_spec_does_not_accept_old_version_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_open_spec_package(root, "v2.3-ip-key-ops")

            result = validate_current_open_spec(root, "v2.4-ops-security-alerts")

            self.assertFalse(result.passed)
            self.assertIn(
                "docs/open-spec/v2.4-ops-security-alerts/",
                result.missing_items,
            )

    def test_planning_files_must_exist_and_reference_current_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename in ("task_plan.md", "findings.md", "progress.md"):
                (root / filename).write_text("V2.3 previous work\n", encoding="utf-8")

            result = validate_planning_files(root, "v2.4-ops-security-alerts")

            self.assertFalse(result.passed)
            self.assertIn(
                "task_plan.md missing feature slug v2.4-ops-security-alerts",
                result.missing_items,
            )
            self.assertIn(
                "progress.md missing feature slug v2.4-ops-security-alerts",
                result.missing_items,
            )

    def test_ui_delivery_gates_require_planning_open_spec_and_html_prototype(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature_slug = "v2.4-ops-security-alerts"
            self._write_planning_files(root, feature_slug)
            self._write_open_spec_package(root, feature_slug)

            result = validate_required_delivery_gates(root, feature_slug, "ui")

            self.assertFalse(result.passed)
            self.assertIn(
                f"docs/prototypes/{feature_slug}-prototype.html",
                result.missing_items,
            )

    def test_ui_delivery_gates_pass_when_current_artifacts_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature_slug = "v2.4-ops-security-alerts"
            self._write_planning_files(root, feature_slug)
            self._write_open_spec_package(root, feature_slug)
            prototype = root / "docs" / "prototypes" / f"{feature_slug}-prototype.html"
            prototype.parent.mkdir(parents=True)
            prototype.write_text("<!doctype html><title>Prototype</title>\n", encoding="utf-8")

            result = validate_required_delivery_gates(root, feature_slug, "ui")

            self.assertTrue(result.passed)

    def test_open_spec_stage_files_reject_old_plan_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature_slug = "v2.4-ops-security-alerts"
            package = root / "docs" / "open-spec" / feature_slug
            package.mkdir(parents=True)
            for filename in [
                "00-change-request.md",
                "01-requirements.md",
                "02-specification.md",
                "03-solution-design.md",
                "04-implementation-plan.md",
                "06-test-cases.md",
                "07-release-retrospective.md",
                "08-stage-handoff.md",
            ]:
                (package / filename).write_text("# old name\n", encoding="utf-8")

            result = validate_current_open_spec(root, feature_slug)

            self.assertFalse(result.passed)
            self.assertIn(
                f"docs/open-spec/{feature_slug}/03-technical-solution.md",
                result.missing_items,
            )
            self.assertIn(
                f"docs/open-spec/{feature_slug}/04-storage-design.md",
                result.missing_items,
            )
            self.assertIn(
                f"docs/open-spec/{feature_slug}/05-development-plan.md",
                result.missing_items,
            )

    def test_non_ui_delivery_gates_require_behavior_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature_slug = "v2.4-api-worker"
            self._write_planning_files(root, feature_slug)
            self._write_open_spec_package(root, feature_slug)

            result = validate_required_delivery_gates(root, feature_slug, "non_ui")

            self.assertFalse(result.passed)
            self.assertIn(
                ".product-delivery/artifacts/non-ui-behavior-contract.md",
                result.missing_items,
            )

    def _write_planning_files(self, root: Path, feature_slug: str) -> None:
        for filename in ("task_plan.md", "findings.md", "progress.md"):
            (root / filename).write_text(
                f"# Product Delivery\n\nCurrent feature: {feature_slug}\n",
                encoding="utf-8",
            )

    def _write_open_spec_package(self, root: Path, feature_slug: str) -> None:
        package = root / "docs" / "open-spec" / feature_slug
        package.mkdir(parents=True)
        for filename in OPEN_SPEC_FILES:
            (package / filename).write_text(
                f"# {filename}\n\nFeature: {feature_slug}\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    unittest.main()
