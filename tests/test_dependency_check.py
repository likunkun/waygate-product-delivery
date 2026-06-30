import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_waygate_product_delivery_dependencies.py"


def load_dependency_module():
    spec = importlib.util.spec_from_file_location("dependency_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, relative: str) -> None:
    path = root / relative / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: test\n---\n", encoding="utf-8")


class DependencyCheckTests(unittest.TestCase):
    def test_check_passes_with_required_skills_and_warns_optional_file_skills(self):
        module = load_dependency_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            agents_home = root / "agents"
            plugin_root = root / "repo" / "plugins" / "waygate-product-delivery"

            for skill in module.REQUIRED_SKILL_NAMES:
                if skill == "waygate-product-delivery":
                    write_skill(plugin_root, "skills/waygate-product-delivery")
                elif skill.startswith("superpowers:"):
                    write_skill(
                        codex_home,
                        "superpowers/skills/" + skill.split(":", 1)[1],
                    )
                else:
                    write_skill(codex_home, "skills/" + skill)

            result = module.check_dependencies(
                plugin_root=plugin_root,
                codex_home=codex_home,
                agents_home=agents_home,
            )

            self.assertFalse(result["missing_required"])
            self.assertEqual(set(result["missing_optional"]), {"pdf", "docx", "pptx"})
            self.assertTrue(result["passed"])

    def test_one_of_requirement_passes_when_one_alternative_exists(self):
        module = load_dependency_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            agents_home = root / "agents"
            plugin_root = root / "repo" / "plugins" / "waygate-product-delivery"

            write_skill(codex_home, "skills/test-strategy")

            result = module.check_requirement(
                "test-strategy|testing-strategy",
                plugin_root=plugin_root,
                codex_home=codex_home,
                agents_home=agents_home,
            )

            self.assertTrue(result["satisfied"])
            self.assertEqual(result["matched"], "test-strategy")

    def test_cli_fails_when_required_skill_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_root = root / "plugins" / "waygate-product-delivery"
            plugin_root.mkdir(parents=True)
            env = {
                **os.environ,
                "PYTHONPATH": str(REPO_ROOT / "src"),
                "CODEX_HOME": str(root / "codex"),
                "AGENTS_HOME": str(root / "agents"),
            }

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT_PATH),
                    "--plugin-root",
                    str(plugin_root),
                ],
                cwd=str(REPO_ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_required", result.stdout)
            self.assertIn("superpowers:using-superpowers", result.stdout)

    def test_install_script_runs_dependency_check_before_packaging(self):
        install_script = (REPO_ROOT / "scripts" / "install_waygate_product_delivery.sh").read_text(
            encoding="utf-8"
        )

        dependency_index = install_script.index(
            "check_waygate_product_delivery_dependencies.py"
        )
        package_index = install_script.index("package_waygate_product_delivery.py")

        self.assertLess(dependency_index, package_index)


if __name__ == "__main__":
    unittest.main()
