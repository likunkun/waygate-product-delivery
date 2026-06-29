# V0.5 Hooks And Recovery Guardrails - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.5 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.5 Hooks And Recovery Guardrails. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record hook read model over existing state and artifact paths. | CR-001 |


## Storage Scope

This document records the V0.5 hook read model over the existing V0.2 `.product-delivery/` state and artifact protocol.
V0.5 does not introduce a new storage root or a second source of truth.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Future local product delivery workspace root. |
| state.json | Future record of active state, current stage, project type, confirmation points, artifact paths, freeze state, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |
| Hook state reads | Hooks read state only when project is active and remain silent when inactive. |
| Hook artifact checks | Stop guardrails resolve required artifact files through `artifact_paths` and `.product-delivery/artifacts/`. |
| Skill records | Resume context reports existing `skill_records` without changing them. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Hook helpers must not write `state.json`; they only report state validity, recovery context, or missing evidence.
- Invalid JSON during pre-compaction is reported as a guardrail failure for active state durability.

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
