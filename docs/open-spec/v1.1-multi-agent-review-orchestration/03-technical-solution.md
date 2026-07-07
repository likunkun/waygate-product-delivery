# V1.1 Multi-Agent Review Orchestration - 03 Technical Solution

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial technical solution for V1.1 multi-agent review orchestration. | CR-001 |

## Change Linkage

- Change Request: CR-001
- Requirements: `01-requirements.md`
- Specification: `02-specification.md`
- Confirmed project type: `non_ui`
- Scope boundary: local Product Delivery multi-agent review orchestration only

## FR Mapping

| FR | Solution Coverage |
| --- | --- |
| FR-001 | `review_orchestration.py` defines review gate profiles and reviewer responsibilities. |
| FR-002 | Input snapshot builder composes feature-specific prompt inputs from current state and artifacts. |
| FR-003 | Scenario gate profile requires product intent, scenario/journey completeness, and negative boundaries. |
| FR-004 | Test coverage profile requires `US/J/SC/AC/TASK/TC` traceability and planned coverage evidence. |
| FR-005 | Test implementation profile requires actual test code, execution evidence, reviewed test IDs, and action assertions. |
| FR-006 | Gate profile validation keeps `scenario`, `test_coverage`, and `test_implementation` non-interchangeable. |
| FR-007 | Existing `review_gates.py` validation/rendering remains authoritative for artifact structure. |
| FR-008 | Gate validation and orchestration return blocked results when blocking findings remain. |
| FR-009 | Default policy remains `spawned_subagents_required`; missing review mode is treated as `spawned_subagents` only for legacy compatibility reads, while new V1.1 accepted artifacts must record `review_mode` explicitly. |
| FR-010 | `role_simulation` remains gated by both user acceptance and an explicit degradation-allowing workflow policy; current `spawned_subagents_required` runs reject it. |
| FR-011 | `blocked_with_reason` remains fail-closed. |
| FR-012 | Existing state fields and artifact paths remain compatible. |
| FR-013 | Input snapshot builder selects non-UI behavior contract/evidence for this feature and preserves UI compatibility wording. |
| FR-014 | Existing coverage validation continues to require collection item-level assertions. |
| FR-015 | Existing false-positive risk checks remain blocking. |
| FR-016 | `gatekeeper.py` and workflow pre-handoff/pre-closure checks enforce non-UI split review requirements for `test_coverage` and `test_implementation`. |
| FR-017 | Review validation and derived blockers treat chat summaries, session status, progress text, Open Spec summaries, and custom artifacts as supporting evidence only. |

## Architecture And Modules

### New Module: `src/product_delivery_agent/review_orchestration.py`

Responsibilities:

- Define fixed review gate profiles for `scenario`, `test_coverage`, and `test_implementation`.
- Define reviewer responsibility sets for product intent, scenario/journey completeness, test coverage, test implementation, and negative boundaries.
- Build feature-specific review input snapshots from current Product Delivery state and known artifact paths.
- Render review prompts or prompt payloads that can be passed to real spawned subagents.
- Assemble review artifacts from independent positions, cross challenges, revisions, final adjudication, and blocking findings.
- Return explicit blocked results when required input evidence is unavailable.

Non-responsibilities:

- Do not spawn provider-specific agents directly.
- Do not create a dashboard.
- Do not replace `validate_multi_agent_review`.
- Do not perform closure validation.

### Existing Module Changes

| Module | Change |
| --- | --- |
| `review_gates.py` | Keep validation/rendering as the artifact authority; add any missing V1.1 fields only if required by tests. |
| `workflow.py` | Add orchestration-facing helpers that build input snapshots and record review artifacts through existing `record_multi_agent_review`. |
| `artifact_protocol.py` | Expand default `multi_agent_reviews` entries with optional V1.1 metadata while preserving existing shape. |
| `gatekeeper.py` | Ensure derived blockers treat split review gates, unresolved blocking findings, and status-only/custom-only review claims as non-authoritative. |
| `plugin_packaging.py` | Emit V1.1 rules and templates in packaged skill/docs. |
| `tests/` | Add RED tests for prompt input generation, reviewer role coverage, non-interchangeable gates, degradation policy, and artifact persistence. |

## Key Flow

### Scenario Review Orchestration

1. Load current state and verify `feature_slug` and project type exist.
2. Build input snapshot from current Open Spec documents, scenario matrix, non-UI behavior contract, and negative boundary records.
3. Generate reviewer prompts using fixed responsibilities:
   - product intent reviewer;
   - scenario/journey reviewer;
   - negative boundary reviewer.
4. Prefer real spawned subagents and record `review_mode=spawned_subagents`.
5. Collect independent positions before sharing peer critique.
6. Collect cross challenges.
7. Collect revisions.
8. Record final adjudication.
9. Validate artifact through `validate_multi_agent_review("scenario", review)`.
10. Persist artifact through `record_multi_agent_review("scenario", review)`.

### Test Coverage Review Orchestration

1. Build input snapshot from Open Spec, scenario matrix, planned obligations, coverage audit, non-UI behavior evidence obligations, and TASK/TC references.
2. Generate reviewer prompts for traceability, coverage gaps, collection item-level coverage, and false-positive risks.
3. Require `traceability_reviewed` to include `US`, `J`, `SC`, `AC`, `TASK`, and `TC`.
4. Require collection coverage with required items, covered items, and item-level assertions.
5. Fail closed if coverage gaps, title overbreadth, missing executable assertions, or false-positive risks remain.
6. Persist only after `validate_multi_agent_review("test_coverage", review)` passes.

### Test Implementation Review Orchestration

1. Build input snapshot from executed evidence, actual test code paths, reviewed test IDs, verified action assertions, and closure inputs.
2. Generate reviewer prompts for implementation evidence completeness and false-positive checks.
3. Require actual test code paths and execution evidence paths.
4. Require verified action assertions tied to evidence.
5. Fail closed on marker-only, function-name-only, static-panel-only, first-button-only, or supporting-evidence-only claims.
6. Persist only after `validate_multi_agent_review("test_implementation", review)` passes.

## ADR Summary

| ADR | Decision | Alternatives | Rationale |
| --- | --- | --- | --- |
| ADR-001 | Add a small `review_orchestration.py` module. | Put all logic into `workflow.py`; create standalone Runtime API. | Keeps orchestration reusable without bloating workflow or creating out-of-scope API versioning. |
| ADR-002 | Keep `review_gates.py` as validation authority. | Duplicate validation in orchestration. | Avoids drift and preserves existing V1.0.11 behavior. |
| ADR-003 | Persist input snapshots in review metadata/artifacts. | Rely on chat logs or regenerated prompts. | Makes review decisions reproducible and audit-friendly. |
| ADR-004 | Fail closed when spawned subagents are unavailable unless a future workflow policy explicitly allows degradation and the user separately accepts it. | Auto-fallback to role simulation. | Preserves evidence strength and Product Delivery rules; this current run remains `spawned_subagents_required`. |
| ADR-005 | No database. Use existing `.product-delivery/state.json` and artifacts. | Add SQLite or external storage. | Current workflow is file-backed; database would be unjustified scope expansion. |

## Observability And Evidence

- Every orchestration attempt should preserve:
  - review type;
  - review mode;
  - input snapshot;
  - reviewer role coverage;
  - artifact path;
  - gate result;
  - blocked reason when applicable.
- Accepted review artifacts remain Markdown under `.product-delivery/artifacts/`.
- State records keep machine-readable status under `multi_agent_reviews`.
- Tests must prove structured artifact output is enough to reproduce acceptance decisions without chat history.

## Risk And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Subagents unavailable or fail to return structured output. | Return `blocked_with_reason`; allow `role_simulation` only when a workflow policy explicitly allows degradation and user acceptance is recorded. | Keep feature blocked under `spawned_subagents_required`; do not mutate closure state. |
| Role simulation accidentally treated as strong evidence. | Keep policy checks in `workflow.py` and review mode validation in `review_gates.py`. | Revert orchestration module and retain existing review validation. |
| Artifact missing deliberation sections but accepted. | Add RED tests for missing input snapshots, responsibilities, and required deliberation fields. | Use existing `validate_multi_agent_review` fail-closed behavior. |
| Three split gates become merged. | Add tests that substitution fails for every pair of review types. | Revert to V1.0.11 gate checks. |
| Non-UI pre-handoff or pre-closure passes with only a status/custom artifact. | Add negative tests for summary-only, status-only, and custom-only review claims in gatekeeper and workflow paths. | Keep Product Delivery blocked until canonical review artifact validates. |
| Scope drifts into dashboard or external integration. | Keep plugin package text and Open Spec out-of-scope sections explicit. | Remove unapproved files and keep local orchestration only. |

## Implementation Boundary

V1.1 may add runtime helpers and structured artifacts as implementation support. It must not expose a standalone Runtime API version, build dashboard UI, or integrate with Waygate/controller as an external workflow.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No solution blocker remains. | Proceed |
| Assumption | The current harness can provide spawned subagents during actual review orchestration. | If unavailable at runtime, orchestration must return `blocked_with_reason` unless a future run explicitly enables degradation policy and the user accepts it. | Carry forward |
| Assumption | Existing Markdown artifacts remain sufficient for audit evidence. | No database or binary artifact store is needed. | Confirm in tests |
| Nice-to-know | Exact prompt phrasing may evolve during implementation. | Does not affect architecture. | Refine in implementation |
