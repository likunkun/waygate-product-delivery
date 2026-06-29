# V0.2 Artifact And State Protocol - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime module implementation for artifact/state protocol. | CR-001 |


## Solution Boundary

This version implements the runtime solution boundary for `V0.2 - Artifact And State Protocol`.
It does not implement lifecycle commands, hooks, UI prototypes, behavior contracts, handoff generation, closure gates, or plugin packaging.

## Modules And Responsibilities

- `src/product_delivery_agent/artifact_protocol.py`: workspace initialization, disk state loading, atomic state writing, template creation, and state precedence policy.
- `.product-delivery/` workspace: local project artifact root created by `initialize_workspace`.
- `state.json` responsibility model: stage, project type, confirmation points, artifact paths, freeze state, active flag, and update timestamp.
- Artifact template set: product brief, version scope, UI prototype review, non-UI behavior contract, test coverage audit, and handoff.
- `tests/test_artifact_protocol.py`: unit tests for V0.2 behavior.

## Key Flow

1. A caller invokes `initialize_workspace(project_root, project_type=None)`.
2. The helper creates `.product-delivery/`, `templates/`, `artifacts/`, and `state.json` when missing.
3. The helper preserves existing state and artifacts on repeated initialization.
4. Recovery calls use `load_state(project_root, fallback_state=...)`; disk state wins over fallback state.
5. State updates use `write_state(project_root, state)` to write valid JSON atomically.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Implement V0.2 as a small Python helper library. | Gives V0.3 workflow commands a tested state foundation without packaging the plugin yet. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| State write interruption | Write state through a temporary file and replace it atomically. | Re-run initialization; existing artifacts are preserved. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Workflow command diagrams and plugin API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
