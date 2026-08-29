#!/usr/bin/env python3
"""One-shot audited Waygate 1.0.36 to 1.0.37 receipt recovery."""

import argparse
import json
from pathlib import Path
import sys

RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'
sys.path.insert(0, str(RUNTIME_DIR))

from product_delivery_agent.workflow import (
    ProductDeliveryWorkflow,
    RUNTIME_RECEIPT_RECOVERY_MESSAGE,
    WorkflowError,
)

parser = argparse.ArgumentParser()
parser.add_argument('--project-root', default='.')
parser.add_argument('--authorization', required=True)
args = parser.parse_args()
try:
    state = ProductDeliveryWorkflow(args.project_root).recover_runtime_receipt(
        args.authorization
    )
except WorkflowError as error:
    print(f'recovery rejected: {error}', file=sys.stderr)
    raise SystemExit(2)
print(json.dumps({
    'result': 'runtime_receipt_recovered',
    'delivery_id': state.get('delivery_id'),
    'feature_slug': state.get('feature_slug'),
    'runtime_provenance': state.get('runtime_provenance'),
    'required_authorization': RUNTIME_RECEIPT_RECOVERY_MESSAGE,
}, ensure_ascii=False, sort_keys=True))
