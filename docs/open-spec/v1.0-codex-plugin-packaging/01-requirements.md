# V1.0 Codex Plugin Packaging - 01 Requirements

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
| REV-20260622-02 | 2026-06-22 | Codex | Add V0.10 Feature Closure packaging requirements. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record runtime repo-local plugin packaging implementation and validation evidence. | CR-001 |


## Business Goal

Package the stable workflow as an installable Codex plugin.

## Scope

### In Scope

- Package the skill, hooks, templates, and validation scripts.
- Package V0.10 closure artifact template, coverage matrix template, negative scope guard checklist, and formal gate validation script planning item.
- Provide repo marketplace configuration.
- Keep the plugin dormant after installation.
- Enter active mode only after start.
- Exit intervention after stop.
- Preserve existing .product-delivery/ artifacts across plugin upgrades.
- Generate repo-local plugin package under `plugins/product-delivery-agent/` and marketplace config under `.agents/plugins/marketplace.json`.

### Out Of Scope

- Public plugin marketplace publication.
- Managed enterprise distribution.
- Breaking existing .product-delivery/ artifacts during upgrade.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When the plugin is packaged, it shall include the skill, hooks, templates, and validation scripts. | Package contents list these assets. |
| FR-002 | P0 | When the plugin is distributed for local use, it shall provide repo marketplace configuration. | Repo marketplace config is listed as a required output. |
| FR-003 | P0 | After installation, the plugin shall remain dormant until start. | Lifecycle requirements include install dormant and start active. |
| FR-004 | P0 | After stop, the plugin shall exit intervention. | Lifecycle requirements include stop exit. |
| FR-005 | P0 | During upgrade, the plugin shall preserve existing .product-delivery/ artifacts. | Upgrade retention is a required rule. |
| FR-006 | P0 | When V1.0 packages workflow templates, it shall include V0.10 closure artifact template. | Closure artifact template is listed as a package asset. |
| FR-007 | P0 | When V1.0 packages validation assets, it shall include coverage matrix template and negative scope guard checklist. | Matrix template and scope guard checklist are listed as package assets. |
| FR-008 | P0 | When V1.0 packages validation scripts, it shall include a formal gate validation script planning item. | Formal gate validation script is listed as a planned package asset. |
| FR-009 | P0 | When packaging is reviewed, V0.10 shall be treated as a pre-packaging capability dependency. | Package requirements reference V0.10 as an input. |

Runtime acceptance:

- `package_codex_plugin(repo_root)` creates `.codex-plugin/plugin.json`, packaged skill, hooks documentation, templates, validation script assets, lifecycle policies, upgrade retention policy, and read-only boundary policy.
- Repo-local marketplace config points to `./plugins/product-delivery-agent` with `AVAILABLE` and `ON_INSTALL` policy.
- Plugin manifest validates with `plugin-creator/scripts/validate_plugin.py`.
- Lifecycle policy remains dormant by default and scoped to the current project after `start`.
- Upgrade policy preserves `.product-delivery/` artifacts.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Install safety | Installing the plugin must not alter project behavior without explicit start. | Dormant-by-default behavior is required. |
| NFR-002 | Upgrade compatibility | Existing artifacts must survive plugin upgrades. | Artifact retention is required. |
| NFR-003 | Closure capability completeness | The packaged workflow must include closure evidence assets planned in V0.10. | V1.0 package contents include closure template, matrix template, scope guard checklist, and formal gate script planning item. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Feature Closure Packaging Requirements

- V1.0 packages V0.10 as a pre-packaging capability dependency.
- Package contents must include closure artifact template.
- Package contents must include coverage matrix template.
- Package contents must include negative scope guard checklist.
- Package contents must include formal gate validation script planning item.
- Dormant-by-default, `start`, `stop`, and artifact retention behavior remain unchanged.

## Risks And Assumptions

- Risk: scope drift from future implementation details. Mitigation: keep this version aligned to `ROADMAP.md` scope.
- Risk: branch rules become ambiguous. Mitigation: keep UI and non-UI confirmation gates mutually exclusive.
- Assumption: Codex Goal remains the first handoff target until a later version changes the roadmap.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Repo-local packaging is sufficient for V1.0; public marketplace publication remains out of scope. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Future hook binding and hosted distribution details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
