#!/usr/bin/env python3
"""Compare one production unit to a prepared visual-loop plan."""

from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.ui_visual_loop import run_compare_cli

if __name__ == '__main__':
    raise SystemExit(run_compare_cli())
