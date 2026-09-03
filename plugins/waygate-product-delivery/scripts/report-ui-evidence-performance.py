#!/usr/bin/env python3
"""Report non-authoritative Waygate UI evidence telemetry."""

from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.ui_evidence import run_performance_report_cli

if __name__ == '__main__':
    raise SystemExit(run_performance_report_cli())
