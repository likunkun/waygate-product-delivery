# V1.0.39 Specification

## Runtime Interfaces

### `prepare_ui_evidence_run(purpose, requested_profile="auto")`

- `purpose`: `iteration` or `closure`.
- `requested_profile`: `auto` or `strict`; any request to force standard/iteration as a closure downgrade is rejected.
- Returns a content-hashed plan with required units, journeys, canaries, provenance fields, adapter protocol, `closure_valid`, and resolved profile/reasons.
- Iteration plans do not write a canonical passed gate.

### `record_ui_evidence_run(plan_id, manifest_path)`

- Accepts only a staging manifest that matches the current delivery and current plan.
- Validates all referenced files beneath the project/staging root, resolves symlinks, recomputes hashes, removes self-asserted verdict fields, and stores immutable raw facts under the current delivery.
- Appends `ui_capture_run_ingested` to the transition journal.

### Capture-backed gate APIs

The existing TASK conformance, executed Browser E2E, and production-conformance methods accept either a legacy payload or `capture_run_ids`, never both. New V1.0.39 UI deliveries require `capture_run_ids`; grandfathered paths retain legacy input.

### Review batch and reporting

- `prepare_post_implementation_review_batch()` freezes one evidence index and returns QA and UI/a11y projections.
- `record_post_implementation_review_batch(payload)` validates both existing review schemas independently and writes passed state atomically.
- `performance_report()` returns a read-only aggregate and artifact references.

## Capture Adapter Protocol

`capture-ui-evidence.py` receives `--project-root`, `--plan`, `--adapter-executable`, repeated `--adapter-arg`, and `--output-dir`. It invokes the executable directly, once, with no shell.

The adapter receives:

- `WAYGATE_CAPTURE_PLAN`
- `WAYGATE_CAPTURE_RUN_ID`
- `WAYGATE_CAPTURE_OUTPUT_DIR`

It writes `capture-manifest.json`; the CLI validates staging structure but does not advance canonical workflow state.

## Profile Resolution

- `iteration`: explicitly requested developer feedback, always `closure_valid=false`.
- `standard`: auto-selected only when impact and provenance are complete and no strict trigger exists.
- `strict`: user upgrade or automatic high-risk/unknown-impact result.

Strict triggers include auth, authorization, privacy, security, payment, destructive behavior, global shell/navigation/design tokens, responsive infrastructure, new surface/route, API/schema/migration, cross-role critical journeys, and unknown impact.

## Formal Reuse

A reusable capture identity binds capture hash, final build/deployment/environment, contract unit, baseline, visual policy, validator version, actor/data state, and execution segment. Validators recompute projections from those facts; V1.0.39 has no separate persisted attestation object and never promotes a passing conclusion across different build identities.

## Closure Compatibility

The canonical closure schema remains `v0.11`. For capture-policy UI deliveries, validation additionally requires the resolved evidence profile, registry root hash, closure manifest hash, and projection hashes. Legacy/non-UI closures retain existing requirements.
