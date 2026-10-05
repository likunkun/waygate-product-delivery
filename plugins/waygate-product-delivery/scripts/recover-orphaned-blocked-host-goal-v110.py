#!/usr/bin/env python3
"""Audited Waygate 1.1.0 orphaned blocked-binding recovery."""

import argparse
import json
from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.workflow import (
    ProductDeliveryWorkflow,
    WorkflowError,
)

parser = argparse.ArgumentParser()
parser.add_argument('--project-root', default='.')
args = parser.parse_args()
try:
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise WorkflowError('recovery request must be a JSON object')
    allowed = {
        'expected_state_file_sha256', 'authorization_message',
        'host_turn_id', 'goal_observation', 'dry_run',
    }
    extras = sorted(set(request) - allowed)
    if extras:
        raise WorkflowError(f'unknown recovery fields: {extras}')
    result = ProductDeliveryWorkflow(
        args.project_root
    ).recover_orphaned_blocked_host_goal_current_task(**request)
except (WorkflowError, json.JSONDecodeError, TypeError) as error:
    print(f'recovery rejected: {error}', file=sys.stderr)
    raise SystemExit(2)
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
