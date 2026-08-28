import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class V1034RecoveryRetirementV1035Tests(unittest.TestCase):
    def test_v1034_recovery_utilities_only_exist_in_release_history(self):
        retired_paths = (
            REPO_ROOT / "scripts" / "recover-blocked-host-goal-v1034.py",
            REPO_ROOT
            / "plugins"
            / "waygate-product-delivery"
            / "scripts"
            / "recover-blocked-host-goal-v1034.py",
            REPO_ROOT
            / "plugins"
            / "waygate-product-delivery"
            / "scripts"
            / "recover-blocked-host-goal-current-task-v1034.py",
        )
        for path in retired_paths:
            self.assertFalse(path.exists(), str(path.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    unittest.main()
