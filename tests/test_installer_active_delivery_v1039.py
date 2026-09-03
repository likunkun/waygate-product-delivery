import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_active_delivery_upgrade.py"


class InstallerActiveDeliveryV1039Tests(unittest.TestCase):
    def _run(self, root: Path):
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--project-root",
                str(root),
                "--target-version",
                "1.0.39",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rejects_verified_active_older_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / ".product-delivery" / "state.json"
            state.parent.mkdir()
            state.write_text(
                json.dumps(
                    {
                        "active": True,
                        "delivery_lifecycle": {"status": "active"},
                        "runtime_provenance": {
                            "plugin_name": "waygate-product-delivery",
                            "plugin_version": "1.0.38",
                            "package_root_sha256": "old",
                        },
                    }
                )
            )
            result = self._run(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("1.0.38", result.stderr)

    def test_allows_terminal_missing_legacy_and_target_runtime(self):
        cases = [
            {},
            {"active": True},
            {
                "active": True,
                "delivery_lifecycle": {"status": "closed"},
                "runtime_provenance": {"plugin_version": "1.0.38"},
            },
            {
                "active": True,
                "delivery_lifecycle": {"status": "active"},
                "runtime_provenance": {"plugin_version": "1.0.39"},
            },
        ]
        for payload in cases:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if payload:
                    state = root / ".product-delivery" / "state.json"
                    state.parent.mkdir()
                    state.write_text(json.dumps(payload))
                self.assertEqual(self._run(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
