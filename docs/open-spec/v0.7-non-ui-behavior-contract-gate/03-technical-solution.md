# V0.7 Non-UI Behavior Contract Gate - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Record non-UI behavior contract module and workflow integration. | CR-001 |


## Solution Boundary

This version package implements `V0.7 - Non-UI Behavior Contract Gate` as a runtime workflow increment.
It validates and records non-UI behavior contract evidence, but does not execute real API, CLI, service, or background job flows.

## Modules And Responsibilities

- `ProductDeliveryWorkflow.record_non_ui_behavior_contract`: non-UI-only entrypoint for behavior contract recording.
- `NON_UI_BEHAVIOR_TAXONOMY`: required scenario taxonomy keys.
- `validate_non_ui_behavior_contract`: blocks missing entry points, inputs, outputs, taxonomy entries, behavior paths, negative boundaries, or limitations.
- `render_non_ui_behavior_contract`: renders the local Markdown behavior contract artifact.
- Contract-to-audit bridge: records behavior evidence candidates, negative boundary candidates, and limitations for V0.8, V0.9, and V0.10.

## Key Flow

1. Workflow is active and `project_type = non_ui`.
2. `record_non_ui_behavior_contract` validates entry points, inputs, outputs, taxonomy, behavior paths, negative boundaries, and limitations.
3. The contract artifact is written to `.product-delivery/artifacts/non-ui-behavior-contract.md`.
4. State records `non_ui_behavior_contract`, `downstream_inputs`, `behavior_contract_limitations`, `handoff_inputs`, and `closure_inputs`.
5. UI projects are rejected before any non-UI behavior contract evidence is recorded.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Store behavior paths and negative boundaries in state. | Keeps V0.8 audit, V0.9 handoff, and V0.10 closure traceable to non-UI behavior review. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation-specific architecture diagrams and API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
