# V1.0.39 Requirements

## Functional Requirements

- FR-039-001: Define an immutable, content-addressed `capture-run-v1` raw evidence protocol.
- FR-039-002: Bind capture identity to source, build, deployment, environment, actor, data, UI unit, execution segment, collector, validator, and artifact identities.
- FR-039-003: Execute a project-provided browser adapter without shell interpretation and ingest its staging manifest only through canonical workflow APIs.
- FR-039-004: Derive prototype preflight, acceptance scan, TASK conformance, Browser E2E, and production-conformance projections independently from raw capture facts.
- FR-039-005: Support `iteration`, auto-selected `standard`, and user-upgraded `strict`; iteration evidence must never authorize closure.
- FR-039-006: Force strict for high-risk or unknown-impact UI changes and reject downgrade requests.
- FR-039-007: Disable cross-build passing-result reuse; same-build reuse requires complete matching provenance.
- FR-039-008: Aggregate recorded TASK slice evidence into final Browser E2E and production-conformance inputs without resubmitting equivalent payloads.
- FR-039-009: Reuse deterministic PNG decode/comparison work within one identity and generate passing diff heatmaps only on demand.
- FR-039-010: Prepare one frozen post-implementation evidence index and atomically record separate test-implementation and UI-conformance reviews.
- FR-039-011: Record non-authoritative performance telemetry for gates, capture, retry, reuse, validation, and review input.
- FR-039-012: Harden console/network, actor identity, business-request count, origin separation, capture binding, and stale replay checks.
- FR-039-013: Package capture/report CLIs and an adapter template without adding a runtime Playwright dependency.

## Non-Functional Requirements

- NFR-039-001: Raw facts, deterministic decisions, reviewer judgments, and closure authority remain separate trust layers.
- NFR-039-002: Missing, unknown, stale, conflicting, or path-escaping evidence fails closed.
- NFR-039-003: Registry ingestion is append-only and idempotent only for byte-identical content.
- NFR-039-004: Existing lifecycle, Host Goal, confirmation, non-UI, and closure interfaces remain compatible.
- NFR-039-005: Telemetry must not contain secrets and must never relax or block a delivery gate by itself.
- NFR-039-006: Same-build reuse target is at least 85% and duplicate capture target is below 10%, reported as measured values rather than assumed claims.

## User Stories And Journeys

- US-039-001 / J-039-001: As a delivery coordinator, I run one browser adapter and obtain reusable evidence for multiple gates.
- US-039-002 / J-039-002: As a developer, I request quick iteration feedback without accidentally creating closure evidence.
- US-039-003 / J-039-003: As a release owner, I receive an automatically classified standard or strict capture plan and may only increase rigor.
- US-039-004 / J-039-004: As a reviewer, I inspect a deduplicated frozen evidence index while producing separate QA and UI conclusions.
- US-039-005 / J-039-005: As an auditor, I can replay independent validators from immutable raw captures and reject stale or forged provenance.

## Acceptance Criteria

- AC-039-001: One adapter invocation can materialize every supported projection for the same capture run.
- AC-039-002: Iteration artifacts are marked noncanonical and rejected by formal gate and closure APIs.
- AC-039-003: Unknown risk, missing provenance, or shared/high-risk UI impact resolves to strict.
- AC-039-004: Same-build identical ingestion is idempotent; conflicting reuse of a capture ID is rejected.
- AC-039-005: Formal evidence rejects non-empty console/network errors without structured exemption, weak actor identity, mismatched business-request counts, origin confusion, and cross-segment artifact reuse.
- AC-039-006: Final evidence is generated from registered TASK slices and current same-execution capture facts, then independently revalidated; no separate persisted attestation authority exists in V1.0.39.
- AC-039-007: Post-implementation review batch preserves two typed review artifacts and records neither as passed when either payload fails.
- AC-039-008: Packaged and installed capture/report/closure CLIs run without source `PYTHONPATH`.
