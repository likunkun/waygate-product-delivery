#!/usr/bin/env python3
"""Refuse plugin upgrades over a verified active delivery from another version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TERMINAL = {"closed", "abandoned", "complete", "completed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--target-version", required=True)
    args = parser.parse_args(argv)
    path = Path(args.project_root) / ".product-delivery" / "state.json"
    if not path.is_file():
        return 0
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as cause:
        print(f"cannot inspect active delivery state: {cause}", file=sys.stderr)
        return 2
    if not isinstance(state, dict):
        print("cannot inspect active delivery state: state must be an object", file=sys.stderr)
        return 2
    lifecycle = (state.get("delivery_lifecycle") or {}).get("status")
    status = state.get("status")
    terminal = lifecycle in TERMINAL or status in TERMINAL
    provenance = state.get("runtime_provenance") or {}
    current_version = provenance.get("plugin_version")
    verified_waygate_receipt = (
        provenance.get("plugin_name") in {None, "waygate-product-delivery"}
        and isinstance(current_version, str)
        and bool(current_version.strip())
        and bool(provenance.get("package_root_sha256"))
    )
    if (
        state.get("active") is True
        and not terminal
        and verified_waygate_receipt
        and current_version != args.target_version
    ):
        print(
            "refusing upgrade over verified active Waygate delivery: "
            f"runtime {current_version}, target {args.target_version}; "
            "complete or explicitly abandon it with the original runtime first",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
