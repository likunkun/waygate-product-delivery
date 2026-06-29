# V0.7 Non-UI Behavior Contract Gate - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.7 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.7 Non-UI Behavior Contract Gate. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record non-UI behavior contract artifact and state fields. | CR-001 |


## Storage Scope

This document records the V0.7 storage responsibilities for non-UI behavior contract artifacts and downstream obligation fields.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Local product delivery workspace root. |
| state.json | Record of active state, current stage, project type, confirmation points, artifact paths, freeze state, behavior contract inputs, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |
| artifacts/non-ui-behavior-contract.md | Runtime non-UI behavior contract record rendered from the contract payload. |
| non_ui_behavior_contract | State object containing contract name, entry points, inputs, outputs, taxonomy, behavior paths, negative boundary records, limitations, and artifact path. |
| downstream_inputs | Behavior evidence and negative boundary candidates derived from the confirmed contract. |
| behavior_contract_limitations | Accepted behavior limitations for later audit, handoff, and closure. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Non-UI behavior contract state must only be written for `project_type = non_ui`.
- Behavior limitations must also be copied into `handoff_inputs` and `closure_inputs`.
- V0.7 does not create HTML prototype files and does not write outside `.product-delivery/`.

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
