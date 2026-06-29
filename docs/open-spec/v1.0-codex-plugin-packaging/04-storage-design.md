# V1.0 Codex Plugin Packaging - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V1.0 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V1.0 Codex Plugin Packaging. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record generated plugin package and marketplace artifacts. | CR-001 |


## Storage Scope

This document records the generated V1.0 repo-local plugin package and marketplace artifacts.

## Artifact And State Inventory

| Artifact | Responsibility |
| --- | --- |
| .product-delivery/ | Future local product delivery workspace root. |
| state.json | Future record of active state, current stage, project type, confirmation points, artifact paths, freeze state, and last update. |
| Templates | Future source documents for product brief, version scope, prototype review, behavior contract, test audit, and handoff. |
| Handoff artifacts | Future frozen implementation package and Codex Goal prompt. |
| plugins/product-delivery-agent/.codex-plugin/plugin.json | Packaged plugin metadata. |
| plugins/product-delivery-agent/skills/product-delivery-agent/SKILL.md | Packaged skill entry. |
| plugins/product-delivery-agent/hooks/README.md | Packaged hook behavior notes for future binding. |
| plugins/product-delivery-agent/templates/ | Packaged workflow, coverage, handoff, and closure templates. |
| plugins/product-delivery-agent/scripts/ | Packaged validation script assets and formal gate plan. |
| plugins/product-delivery-agent/policies/ | Dormant lifecycle, upgrade retention, and read-only boundary policies. |
| .agents/plugins/marketplace.json | Repo-local plugin distribution entry. |

## State Responsibility Rules

- State files are authoritative over chat context for workflow recovery.
- Confirmation points must have durable artifact paths or recorded state responsibilities.
- `start` enters active mode; `stop` exits intervention while preserving artifacts.
- UI prototype and non-UI behavior contract records are mutually exclusive by project type.
- Plugin packaging must not create or modify project `.product-delivery/` runtime state.
- Generated package policies require dormant-by-default activation and `.product-delivery/` retention.
- Generated read-only boundary policy forbids direct Waygate/controller mutation.

## Compatibility And Migration

- Future schema changes must preserve existing `.product-delivery/` artifacts.
- Plugin upgrades must not delete product delivery artifacts.
- If migration is required in a future version, it must be additive or include a clear rollback path.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Repo-local package artifacts are sufficient for V1.0 packaging validation. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Future migration scripts for live plugin upgrades remain deferred until a version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
