# V1.0.39 Technical Solution

## Components

1. `ui_evidence.py`: schema validation, plan/profile resolution, capture identity, immutable registry, projections, closure manifest, telemetry, and review-batch snapshot helpers.
2. Existing `coverage_audit.py`, `implementation_baseline.py`, `review_gates.py`, `gatekeeper.py`, and `workflow.py`: consume capture-backed inputs while retaining their independent checks.
3. `capture-ui-evidence.py`: dependency-free adapter launcher and staging validator; canonical ingestion remains in the runtime.

## Data Flow

1. Derive impact/risk from current state, contract, obligations, changed UI facts, and optional verified dependency facts.
2. Resolve profile and emit a deterministic capture plan.
3. Invoke the target adapter once to capture screenshot, semantic/style/geometry, console/network, API, actor, trace, and scan facts.
4. Ingest the manifest into immutable content-addressed storage.
5. Materialize independent gate projections and feed existing validators.
6. Aggregate current TASK slices into final evidence and create a complete closure manifest.
7. Run the two post-implementation reviews against one frozen index and validate closure normally.

## Trust Boundaries

- The adapter is untrusted input.
- Registry ingestion recomputes identities and never trusts adapter verdicts.
- Projection builders do not bypass existing validators.
- Review status does not replace deterministic conformance.
- Closure reloads canonical artifacts and verifies their hashes.

## Performance Design

- Cache decoded PNGs by artifact SHA for one process/run.
- Compute full-surface and region pixel counts in a shared traversal.
- Do not persist passing heatmaps unless explicitly requested.
- Reuse one capture across projections only when the complete identity matches.
- Generate compact reviewer indexes before spawning reviewers.

## Compatibility

- Additive state fields and transition events.
- No control action or closure schema version change.
- New deliveries opt into policy v1; old active deliveries require their original runtime and are not migrated.
