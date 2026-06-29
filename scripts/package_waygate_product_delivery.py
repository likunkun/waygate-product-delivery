#!/usr/bin/env python3
"""Build the Waygate Product Delivery Codex plugin distribution."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from product_delivery_agent.plugin_packaging import build_codex_plugin_distribution


def main() -> int:
    archive_path = build_codex_plugin_distribution(REPO_ROOT)
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
