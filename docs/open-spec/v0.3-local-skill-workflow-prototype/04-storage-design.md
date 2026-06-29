# V0.3 Local Skill Workflow Prototype - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V0.3 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.3 Local Skill Workflow Prototype. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record workflow prototype state and artifact outputs. | CR-001 |


## Storage Scope

This document records V0.3 workflow prototype storage responsibilities on top of the V0.2 artifact protocol.
Detailed plugin and hook schemas remain deferred until their implementation versions.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Implemented local product delivery workspace root. |
| state.json | Implemented record of active state, paused state, intervention flag, current stage, project type, next gate, confirmation points, artifact paths, freeze state, and last update. |
| Templates | Implemented source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Draft audit artifact | Implemented draft `.product-delivery/artifacts/test-coverage-audit.md`. |
| Draft handoff artifact | Implemented draft `.product-delivery/artifacts/handoff.md`. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- `pause` keeps the workflow active but disables intervention.
- `resume` restores intervention from disk state.
- Handoff draft preparation requires product brief, version scope, and branch-specific confirmation.

## Compatibility And Migration

- Future schema changes must preserve existing `.product-delivery/` artifacts.
- Plugin upgrades must not delete product delivery artifacts.
- If migration is required in a future version, it must be additive or include a clear rollback path.
- V0.3 adds workflow state fields without deleting existing V0.2 artifacts.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Additional JSON validation scripts are deferred until their implementation version. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
