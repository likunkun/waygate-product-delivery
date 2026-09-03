# Waygate Product Delivery Installation

## Deliverable Shape

The installable Codex plugin is:

```text
plugins/waygate-product-delivery/
```

The distributable archive is:

```text
dist/waygate-product-delivery-<version>.tar.gz
```

The runtime package inside the plugin remains `runtime/product_delivery_agent/`.
That is an internal Python import path, not the Codex plugin name.

## Build Package

From this repository root:

```bash
python3 scripts/package_waygate_product_delivery.py
```

This regenerates:

- `plugins/waygate-product-delivery/`
- `.agents/plugins/marketplace.json`
- `dist/waygate-product-delivery-<version>.tar.gz`

## Install Or Update Locally

Use the automated install script:

```bash
bash scripts/install_waygate_product_delivery.sh
```

The script runs:

1. required local skill dependency check;
2. package regeneration;
3. plugin validation;
4. Codex cachebuster update;
5. `codex plugin add waygate-product-delivery@repo-local`.

Missing required skills block installation. Missing file-specific skills for `.pdf`,
`.docx`, or `.pptx` only produce warnings because they are conditional.

Version 1.0.39 no longer requires `superpowers:using-superpowers` or
`code-simplifier`. Codex-native Skill routing handles generic selection, and code
refinement is verified through project standards, tests, review, and completion
evidence. Skill authoring uses the system `skill-creator` workflow.

V1.0.39 also packages `capture-ui-evidence.py`, a Playwright adapter template,
and `report-ui-evidence-performance.py`. The capture command writes staging
facts only; canonical workflow ingestion is still required before any gate can
pass. Do not upgrade an active delivery whose verified runtime receipt is older
than 1.0.39; complete or explicitly abandon it with its original runtime first.

## UI Evidence Capture Recipe

Use the runtime and scripts from the same installed plugin version. In the
examples below, export `WAYGATE_PLUGIN_ROOT` as the installed package root and
run Python with `PYTHONPATH="$WAYGATE_PLUGIN_ROOT/runtime"`. Do not import the
repository source runtime for an active installed-plugin delivery.

First prepare a plan. `prepare_ui_evidence_run()` writes the canonical plan
record under the current delivery and returns its delivery-relative
`artifact_path`:

```bash
PYTHONPATH="$WAYGATE_PLUGIN_ROOT/runtime" python3 - <<'PY'
import json
from pathlib import Path
from product_delivery_agent.artifact_protocol import load_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow

root = Path(".").resolve()
workflow = ProductDeliveryWorkflow(root)
plan = workflow.prepare_ui_evidence_run("closure", requested_profile="auto")
state = load_state(root)
delivery_root = root / ".product-delivery" / "deliveries" / state["feature_slug"] / state["delivery_id"]
print(json.dumps({
    "plan_id": plan["plan_id"],
    "profile": plan["resolved_profile"],
    "plan_path": str(delivery_root / plan["artifact_path"]),
}))
PY
```

Copy `templates/playwright-capture-adapter.mjs` into the project and implement
the documented `capture(context)` project module. The bundled
`templates/ui-capture-manifest.json` is a complete nested shape example, not a
literal fixture: replace every placeholder, use real PNG/JSON/trace/probe
bytes, and compute each SHA-256 through the adapter's `writeArtifact()` helper.
The API probe JSON must include a non-empty `business_api_requests` list for
formal journeys. Each unit must write a `task_semantic_snapshot` using
`task-production-semantic-snapshot-v1` and a `production_semantic_snapshot`
using `ui-semantic-surface-v1`; `semantic_snapshot` remains a compatibility ref.
Do not point the two typed fields at one JSON with a renamed schema.

Run into a fresh empty staging directory. Each `--adapter-arg` is passed as one
literal process argument; no shell interpretation occurs:

```bash
python3 "$WAYGATE_PLUGIN_ROOT/scripts/capture-ui-evidence.py" \
  --project-root . \
  --plan <plan-path> \
  --output-dir .product-delivery/staging/<fresh-run-id> \
  --adapter-executable node \
  --adapter-arg scripts/waygate-playwright-capture.mjs \
  --adapter-arg=--project-module \
  --adapter-arg scripts/waygate-project-capture.mjs
```

The CLI output must say `staging_capture_ready` and
`canonical_gate_advanced=false`. Then, after the required Host Goal
reconciliation for a canonical write, ingest that exact manifest:

```bash
PYTHONPATH="$WAYGATE_PLUGIN_ROOT/runtime" python3 - <<'PY'
from product_delivery_agent.workflow import ProductDeliveryWorkflow

workflow = ProductDeliveryWorkflow(".")
print(workflow.record_ui_evidence_run(
    plan_id="<plan-id>",
    manifest_path="<manifest-path>",
))
PY
```

Use the returned `capture_id` with
`record_task_executed_evidence(..., capture_run_ids=[capture_id])` and
`record_task_prototype_conformance(..., capture_run_ids=[capture_id])` before
completing the current TASK. After all TASKs, prefer the no-argument
`record_executed_browser_evidence()` slice-union path. Record final production
conformance from a current full capture, then use
`prepare_post_implementation_review_batch()` and
`record_post_implementation_review_batch()` so test-implementation and
UI-conformance reviews share one immutable index. Finally run the packaged
canonical closure validator. Neither staging capture, canonical ingestion, nor
the performance report can close delivery by itself.

### Standard, Strict, And Supplemental Capture

`iteration` is never ingestible and is only for local feedback. For formal
capture, `auto` selects `standard` only when impact is known and no strict risk
is present; otherwise it selects `strict`. The user may upgrade to `strict`, but
no caller may downgrade it.

In a standard plan, `units` is the affected-plus-canary fast set and
`required_units` is the complete closure set. A final closure run should capture
all `required_units` in one browser invocation on the same frozen build. If an
earlier standard run captured only `units`, prepare a current plan and make a
fresh run that covers all `required_units`; use that full capture for the final
projections. Do not blindly union partial and full captures when both contain
the same journeys. Upgrade to strict when provenance or impact is uncertain, a
strict risk tag applies, or full same-build coverage cannot be demonstrated.

### Fail-Closed Recovery

- Adapter exit, missing manifest, invalid schema/identity, unsafe path, or hash
  mismatch leaves only staging output and advances no gate. Preserve it for
  diagnosis, fix the adapter/source, and rerun in a new empty staging directory.
- If prototype, TASK binding, planned E2E, source tree, or build changed after
  prepare, discard the old plan and prepare again. Never replay or edit stale
  evidence, the capture registry, or `.product-delivery/state.json`.
- Diagnose network, authentication, and deterministic-data failures before a
  retry. Do not turn an inconclusive environment into passed evidence.
- Structural, semantic, interaction, and evidence failures cannot be waived.
  Visual-adjudicable failures follow the two-round systematic-debugging policy.
- If review inputs change, prepare a new batch. Never partially record one
  review as passed. If canonical closure fails, keep the Goal active and repair
  the reported blocker before generating a new closure artifact.

After installation, start a new Codex thread so Codex loads the updated plugin.

Version 1.0.34 writes prototype design bundle v2 for new or reopened UI prototypes. Existing v1 bundles remain readable and are not rewritten during installation; an already confirmed active delivery is revalidated under v2 only after its prototype is modified, replaced, or explicitly reopened.

## Manual Install

If you need to run the steps manually:

```bash
PYTHONPATH=src python3 scripts/check_waygate_product_delivery_dependencies.py --plugin-root plugins/waygate-product-delivery
python3 scripts/package_waygate_product_delivery.py
python3 <plugin-creator>/scripts/validate_plugin.py plugins/waygate-product-delivery
python3 <plugin-creator>/scripts/update_plugin_cachebuster.py plugins/waygate-product-delivery
codex plugin add waygate-product-delivery@repo-local
```

## Smoke Test

Run the packaged validator without source `PYTHONPATH`:

```bash
env -u PYTHONPATH PYTHONNOUSERSITE=1 \
  python3 plugins/waygate-product-delivery/scripts/validate-closure-artifact.py --help
```

For the installed cache, replace the script path with:

```text
<codex-home>/plugins/cache/repo-local/waygate-product-delivery/<installed-version>/scripts/validate-closure-artifact.py
```
