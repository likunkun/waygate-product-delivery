import hashlib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_SCRIPTS = {
    "scripts/recover-blocked-host-goal-v1034.py": (
        "4710d810f99f2caf7ade148516b45954b483b9ee77b03573d0587b9808af8426"
    ),
    "plugins/waygate-product-delivery/scripts/recover-blocked-host-goal-v1034.py": (
        "4710d810f99f2caf7ade148516b45954b483b9ee77b03573d0587b9808af8426"
    ),
    "plugins/waygate-product-delivery/scripts/"
    "recover-blocked-host-goal-current-task-v1034.py": (
        "9c8fa25448376050d623f60a49333f137bf7d272f07127593fdc7187900a339d"
    ),
}


class FrozenV1034RecoveryV1037Tests(unittest.TestCase):
    def test_v1034_recovery_sources_are_byte_for_byte_frozen(self):
        for relative_path, expected_sha256 in FROZEN_SCRIPTS.items():
            with self.subTest(relative_path=relative_path):
                payload = (REPO_ROOT / relative_path).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected_sha256)

    def test_v1034_recoveries_still_reject_non_1034_runtime(self):
        for relative_path in FROZEN_SCRIPTS:
            source = (REPO_ROOT / relative_path).read_text("utf-8")
            if relative_path.endswith("recover-blocked-host-goal-v1034.py"):
                self.assertIn('PLUGIN_VERSION != "1.0.34"', source)
                self.assertIn("restricted to Waygate 1.0.34", source)
            else:
                self.assertIn("_load_emergency_module", source)
                self.assertIn('with_name("recover-blocked-host-goal-v1034.py")', source)


if __name__ == "__main__":
    unittest.main()
