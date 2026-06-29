# V0.2 Artifact And State Protocol - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.2 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.2 Artifact And State Protocol. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record implemented local storage layout and state fields. | CR-001 |


## Storage Scope

This document records the V0.2 implemented storage responsibilities and minimal runtime fields.
Detailed workflow command schemas remain deferred until the implementation version that needs them.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Implemented local product delivery workspace root. |
| .product-delivery/state.json | Implemented record of active state, current stage, project type, confirmation points, artifact paths, freeze state, and last update. |
| .product-delivery/templates/ | Implemented source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| .product-delivery/artifacts/ | Implemented durable workspace for review and confirmation artifacts. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |

## Implemented State Fields

| Field | Responsibility |
| --- | --- |
| active | Records whether a later workflow has activated product-delivery mode. |
| stage | Records the current workflow stage. |
| project_type | Records `ui`, `non_ui`, or no selected type. |
| confirmation_points | Records durable confirmation responsibilities for each core artifact. |
| artifact_paths | Records relative artifact paths for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| freeze | Records whether scope is frozen and the scope version, for later handoff behavior. |
| updated_at | Records the latest state write time. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Initialization must preserve existing state and artifacts.
- State writes must produce valid JSON on disk.

## Compatibility And Migration

- Future schema changes must preserve existing `.product-delivery/` artifacts.
- Plugin upgrades must not delete product delivery artifacts.
- If migration is required in a future version, it must be additive or include a clear rollback path.
- V0.2 initialization backfills missing protocol fields into existing state without deleting custom artifacts.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Additional JSON field names and validation scripts are deferred until their implementation version. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
