# V1.0 Codex Plugin Packaging - 00 Change Request

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
| REV-20260622-02 | 2026-06-22 | Codex | Record repo-local plugin package implementation and validation evidence. | CR-001 |


## Change Request

| Field | Value |
| --- | --- |
| CR ID | CR-001 |
| Change Type | Planned roadmap version |
| Priority | P0 for roadmap continuity |
| Source | Product Delivery Agent Plugin roadmap |
| Target Version | V1.0 |

## Background And Objective

Package the stable workflow as an installable Codex plugin.

## Roadmap Alignment

This change request corresponds to `V1.0 - Codex Plugin Packaging` in `ROADMAP.md`.

## In Scope

- Package the skill, hooks, templates, and validation scripts.
- Package V0.10 closure artifact template, coverage matrix template, negative scope guard checklist, and formal gate validation assets.
- Provide repo marketplace configuration.
- Keep the plugin dormant after installation.
- Enter active mode only after start.
- Exit intervention after stop.
- Preserve existing .product-delivery/ artifacts across plugin upgrades.
- Generate repo-local package files under `plugins/product-delivery-agent/`.
- Generate repo-local marketplace config under `.agents/plugins/marketplace.json`.

## Out Of Scope

- Public plugin marketplace publication.
- Managed enterprise distribution.
- Breaking existing .product-delivery/ artifacts during upgrade.

## Impact Analysis

| Area | Impact |
| --- | --- |
| Documents | Updates Open Spec package for V1.0 with implementation evidence. |
| Artifacts | Generates repo-local plugin package files and marketplace config. |
| State protocol | Impacted only when this version explicitly scopes state responsibilities. |
| Skills | Impacted when this version scopes skill allocation or skill-driven workflow behavior. |
| Waygate | No direct Waygate state mutation. |

## Acceptance And Rollback

- Acceptance: the version package contains `00` through `08` Open Spec documents with traceable `CR`, `FR`, `TASK`, `TC`, and `REV` references; `package_codex_plugin(repo_root)` generates the plugin package and marketplace config; unit tests and plugin manifest validation pass.
- Rollback: remove the generated `plugins/product-delivery-agent/` package and `.agents/plugins/marketplace.json` entry, then revert this version package directory if the implemented scope is rejected.
- Waygate state is not modified by this change request.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Repo-local packaging is sufficient for V1.0; public marketplace publication remains out of scope. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Future hook binding and marketplace publishing details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
