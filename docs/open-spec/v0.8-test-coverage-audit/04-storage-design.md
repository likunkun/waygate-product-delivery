# V0.8 Test Coverage Audit - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.8 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.8 Test Coverage Audit. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record coverage audit artifact and state fields. | CR-001 |


## Storage Scope

This document records the V0.8 storage responsibilities for coverage audit artifacts, matrix rows, and closure-ready fields.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Local product delivery workspace root. |
| state.json | Record of active state, current stage, project type, confirmation points, artifact paths, coverage audit state, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |
| artifacts/test-coverage-audit.md | Runtime coverage audit record rendered from validated matrix rows. |
| test_coverage_audit | State object containing pass status, matrix range, latest test case, rows, inherited limitations, negative guard records, and obligations. |
| handoff_inputs | Coverage matrix range and latest test case for V0.9 handoff. |
| closure_inputs | Coverage matrix range and latest test case for V0.10 closure. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Coverage audit state must only be written after validation passes.
- UI audits inherit prototype limitations and negative scope guard obligations from V0.6.
- Non-UI audits inherit behavior limitations and negative boundary obligations from V0.7.
- V0.8 does not execute test commands and does not write outside `.product-delivery/`.

## Compatibility And Migration

- Future schema changes must preserve existing `.product-delivery/` artifacts.
- Plugin upgrades must not delete product delivery artifacts.
- If migration is required in a future version, it must be additive or include a clear rollback path.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Exact JSON field names and validation scripts are deferred until their implementation version. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
