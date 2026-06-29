# V1.0 Codex Plugin Packaging - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Add V0.10 Feature Closure packaging components. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record plugin packaging helper and generated repo-local package. | CR-001 |


## Solution Boundary

This version package implements `V1.0 - Codex Plugin Packaging` as a repo-local plugin package generator.
It creates local plugin files and marketplace config, but does not publish to a public marketplace.

## Modules And Responsibilities

- `package_codex_plugin`: creates repo-local package structure.
- Plugin manifest: `.codex-plugin/plugin.json`.
- Packaged skill: `skills/product-delivery-agent/SKILL.md`.
- Packaged hooks documentation: `hooks/README.md`.
- Templates: product brief, version scope, UI prototype review, non-UI behavior contract, coverage audit, handoff, closure artifact, coverage matrix, and negative scope guard checklist.
- Validation scripts: `scripts/validate-closure-artifact.py` and formal gate validation plan.
- Policies: lifecycle, upgrade retention, and Waygate/controller read-only boundary.
- Repo marketplace config: `.agents/plugins/marketplace.json`.

## Key Flow

1. Run `package_codex_plugin(repo_root)`.
2. Generate `plugins/product-delivery-agent/` with manifest, skill, hooks docs, templates, scripts, and policies.
3. Generate `.agents/plugins/marketplace.json` pointing to `./plugins/product-delivery-agent`.
4. Validate manifest with `plugin-creator/scripts/validate_plugin.py`.
5. Keep plugin dormant after installation and activate only after `start`.
6. Preserve existing `.product-delivery/` artifacts across upgrades.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Validate with local skill before final plugin packaging. | Reduces distribution complexity while the workflow stabilizes. |
| ADR-007 | Plugin upgrades must preserve artifacts. | Protects local workflow history and audit records. |
| ADR-008 | Package V0.10 closure assets in V1.0. | Ensures formal closure is part of the installable workflow. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| Closure assets omitted | Treat V0.10 as a packaging dependency. | Return to package assembly before release. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation-specific architecture diagrams and API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
