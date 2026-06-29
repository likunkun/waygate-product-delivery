# V0.9 Codex Goal Handoff - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.9 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.9 Codex Goal Handoff. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record handoff artifacts, freeze state, and CR records. | CR-001 |


## Storage Scope

This document records the V0.9 storage responsibilities for handoff artifacts, freeze state, post-freeze CR records, and superseded closure records.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Local product delivery workspace root. |
| state.json | Record of active state, current stage, project type, confirmation points, artifact paths, freeze state, handoff state, CR records, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| artifacts/handoff.md | Runtime frozen implementation handoff package. |
| artifacts/codex-goal-prompt.md | Runtime prompt for implementation Codex. |
| handoff | State object containing scope, non-goals, confirmations, matrix range, obligations, commands, prohibited work, CR rules, and artifact paths. |
| freeze | Frozen scope marker and scope version. |
| change_requests | Post-freeze acceptance feedback, scope change, and test gap records. |
| superseded_closures | Closure artifacts replaced by later CRs. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Handoff state must only be written after V0.8 coverage audit passes.
- Scope changes after freeze must clear the frozen flag and route back to version scope confirmation.
- Superseded closure records must retain the triggering CR.
- V0.9 does not execute implementation Codex work and does not write outside `.product-delivery/`.

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
