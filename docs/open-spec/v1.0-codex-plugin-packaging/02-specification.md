# V1.0 Codex Plugin Packaging - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Add V0.10 Feature Closure packaging semantics. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record plugin package interfaces and generated assets. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |
| FR-005 | FR-005 behavior, gate, or artifact rule |
| FR-006 | Closure artifact template packaging |
| FR-007 | Coverage matrix template and negative scope guard checklist packaging |
| FR-008 | Formal gate validation script planning item |
| FR-009 | V0.10 pre-packaging dependency |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Plugin installation must not activate a project; start activates and stop exits intervention.
- V1.0 packaging must include V0.10 Feature Closure assets as planned package contents.
- Closure assets must remain inactive until explicit project-level `start`.
- Runtime packaging must create a valid `.codex-plugin/plugin.json` without unsupported manifest fields.
- Runtime packaging must create repo-local marketplace configuration with explicit install/auth policy.

## Data And Artifact Rules

- This version package implements repo-local plugin package generation in `src/product_delivery_agent/plugin_packaging.py`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Packaged templates must include closure artifact template, coverage matrix template, and negative scope guard checklist.
- Packaged validation planning must include formal gate validation script responsibilities.
- Generated package artifacts live under `plugins/product-delivery-agent/`.
- Generated marketplace config lives at `.agents/plugins/marketplace.json`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V1.0 runtime interface is `package_codex_plugin(repo_root)`.
- Generated plugin package remains repo-local and is not published to a public marketplace.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Scope changes after freeze return to version scope confirmation.
- Missing V0.10 closure assets should block V1.0 packaging readiness.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
