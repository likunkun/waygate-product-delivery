# V0.6 UI Prototype Gate - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.6 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.6 UI Prototype Gate. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record UI prototype review artifact and state fields. | CR-001 |


## Storage Scope

This document records the V0.6 storage responsibilities for UI prototype review artifacts and downstream obligation fields.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Local product delivery workspace root. |
| state.json | Record of active state, current stage, project type, confirmation points, artifact paths, freeze state, review inputs, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |
| artifacts/ui-prototype-review.md | Runtime UI prototype review record rendered from the review payload. |
| ui_prototype_review | State object containing prototype path, pages, states, journeys, taxonomy, limitations, and review artifact path. |
| downstream_inputs | Browser E2E and negative scope guard candidates derived from the confirmed prototype review. |
| prototype_limitations | Accepted prototype limitations for later audit, handoff, and closure. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- UI prototype review state must only be written for `project_type = ui`.
- UI prototype limitations must also be copied into `handoff_inputs` and `closure_inputs`.
- V0.6 does not create production UI files or write outside `.product-delivery/`.

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
