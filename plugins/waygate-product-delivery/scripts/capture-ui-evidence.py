#!/usr/bin/env python3
"""Run one project UI evidence adapter into non-canonical staging."""

from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.ui_evidence import run_capture_cli

if __name__ == '__main__':
    raise SystemExit(run_capture_cli())
