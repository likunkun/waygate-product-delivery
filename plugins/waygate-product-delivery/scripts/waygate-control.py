#!/usr/bin/env python3
"""Strict JSON lifecycle control for Waygate Product Delivery."""

from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.control import run_control_cli

if __name__ == '__main__':
    raise SystemExit(run_control_cli())
