# V1.0.39 Storage Design

## Delivery Layout

```text
.product-delivery/deliveries/<feature>/<delivery>/
  evidence/
    capture-registry.json
    captures/<capture-id>/manifest.json
    closure-manifest.json
    performance-telemetry.jsonl
  artifacts/
    post-implementation-review-index.json
    multi-agent-test_implementation-review.md
    multi-agent-ui_conformance-review.md
```

Compatibility mirrors under `.product-delivery/artifacts/` remain hash-checked views, not authority.

## `capture-run-v1`

Top-level fields are `schema_version`, `plan_id`, `purpose`, `profile`, `closure_valid`, `source_identity`, `build_identity`, `deployment_identity`, `environment_identity`, `collector_identity`, `actor_identity`, `data_state_identity`, `units`, `journey_segments`, and `artifacts`.

Each unit binds `surface_id`, `state_id`, `viewport_class`, DPR, route/origin, capture ID, screenshot, semantic snapshot, style/geometry facts, console/network facts, and optional scan facts. Each journey segment binds obligation/test IDs, actor/session, ordinary path, trace, screenshot, API probe, business requests, and mock inventory.

## Registry Rules

- Capture ID is computed from normalized raw facts and artifact hashes.
- Byte-identical re-ingestion is idempotent; any identity collision with different content fails.
- Paths must resolve inside the allowed staging root during ingestion and inside the canonical delivery root afterward.
- Registry root hash covers ordered capture identities. V1.0.39 does not persist a separate attestation store; every reuse candidate is revalidated from its registered capture facts.
- Raw capture entries contain no authoritative `passed` field.

## State Fields

- `ui_evidence_policy`: policy version, resolved profile, reasons, risk/impact/plan hashes, closure eligibility.
- `ui_capture_registry`: registry artifact path/hash/root hash and current run IDs.
- `ui_closure_manifest`: matrix completeness, selected capture references, projection hashes and artifact hash.
- `post_implementation_review_batch`: batch/snapshot identity and two typed review hashes.
- `performance_telemetry`: report path/hash and counters; never a blocker by itself.
