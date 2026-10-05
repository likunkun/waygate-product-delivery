"""Packaged map CLI and status projection work without source checkout access."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.control import dispatch
from product_delivery_agent.plugin_packaging import package_codex_plugin


class ProgressMapControlTests(unittest.TestCase):
    def test_status_and_inspect_expose_effective_switch_without_writing_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_THREAD_ID": "map-cli"}):
            dispatch(tmp, {"schema_version": "v1", "action": "start", "feature_slug": "map", "user_request": "Export reports"})
            state_file = Path(tmp) / ".product-delivery/state.json"
            before = state_file.read_bytes()
            for action in ("status", "inspect"):
                report = dispatch(tmp, {"schema_version": "v1", "action": action})
                self.assertIn("progress_map", report)
                self.assertFalse(report["progress_map"]["enabled"])
                self.assertEqual(state_file.read_bytes(), before)

    def test_packaged_cli_toggle_and_export_in_isolated_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = package_codex_plugin(root)["plugin_root"]
            script = plugin / "scripts/waygate-map.py"
            self.assertTrue(script.exists(), "packaged map CLI missing")
            project = root / "example"
            project.mkdir()
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "map-cli"}):
                delivery = dispatch(project, {"schema_version": "v1", "action": "start", "feature_slug": "map", "user_request": "Export reports"})
            before = (project / ".product-delivery/state.json").read_bytes()
            def run(*args):
                return subprocess.run([sys.executable, "-I", str(script), "--project-root", str(project), *args],
                                      cwd=plugin, capture_output=True, text=True)
            disabled = run("export")
            self.assertEqual(disabled.returncode, 2)
            wrong = run("on", "--delivery-id", "foreign")
            self.assertEqual(wrong.returncode, 2)
            enabled = run("on", "--delivery-id", delivery["delivery_id"])
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            self.assertTrue(json.loads(enabled.stdout)["enabled"])
            exported = run("export")
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertTrue((project / json.loads(exported.stdout)["path"]).is_file())
            self.assertEqual((project / ".product-delivery/state.json").read_bytes(), before)
            default = run("default", "off")
            self.assertEqual(default.returncode, 0, default.stderr)
            self.assertTrue(json.loads(default.stdout)["enabled"])
            self.assertEqual(run("off", "--delivery-id", delivery["delivery_id"]).returncode, 0)
            self.assertFalse(json.loads(run("inspect").stdout)["enabled"])


if __name__ == "__main__":
    unittest.main()
