#!/usr/bin/env python3
"""Validate and record Product Delivery formal closure."""

from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

# Canonical validator identity: product_delivery_agent.finalization
from product_delivery_agent.finalization import run_finalize_cli

if __name__ == '__main__':
    raise SystemExit(run_finalize_cli())
