#!/usr/bin/env python3
"""One-shot audited CR006 shared-overflow runtime receipt recovery."""

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
except json.JSONDecodeError as error:
    print(f'recovery rejected: invalid JSON: {error}', file=sys.stderr)
    raise SystemExit(2)
try:
    result = ProductDeliveryWorkflow(
        args.project_root
    ).recover_shared_overflow_runtime_receipt(request)
except WorkflowError as error:
    print(f'recovery rejected: {error}', file=sys.stderr)
    raise SystemExit(2)
if request.get('dry_run'):
    output = result
else:
    output = {
        'result': 'runtime_receipt_recovered',
        'delivery_id': result.get('delivery_id'),
        'feature_slug': result.get('feature_slug'),
        'runtime_provenance': result.get('runtime_provenance'),
        'journal_last_hash': (
            result.get('transition_journal') or {}
        ).get('last_event_hash'),
    }
print(json.dumps(output, ensure_ascii=False, sort_keys=True))
