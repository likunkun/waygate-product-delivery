#!/usr/bin/env python3
"""Generate optional static progress maps using the packaged runtime."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from product_delivery_agent.progress_map import run_map_cli
if __name__ == '__main__':
    raise SystemExit(run_map_cli())
