# V0.6 UI Prototype Gate - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Record UI prototype gate module and workflow integration. | CR-001 |


## Solution Boundary

This version package implements `V0.6 - UI Prototype Gate` as a runtime workflow increment.
It validates and records UI prototype review evidence, but does not implement production UI, browser automation, or concrete plugin packaging.

## Modules And Responsibilities

- `ProductDeliveryWorkflow.record_ui_prototype_review`: UI-only entrypoint for prototype review recording.
- `UI_PROTOTYPE_TAXONOMY`: required scenario taxonomy keys.
- `validate_ui_prototype_review`: blocks missing pages, states, journeys, taxonomy entries, limitations, browser E2E candidates, or negative scope candidates.
- `render_ui_prototype_review`: renders the local Markdown review artifact.
- Prototype limitation handoff bridge: records limitations into state for V0.8, V0.9, and V0.10.

## Key Flow

1. Workflow is active and `project_type = ui`.
2. `record_ui_prototype_review` validates pages, states, journeys, taxonomy, limitations, E2E candidates, and negative scope candidates.
3. The review artifact is written to `.product-delivery/artifacts/ui-prototype-review.md`.
4. State records `ui_prototype_review`, `downstream_inputs`, `prototype_limitations`, `handoff_inputs`, and `closure_inputs`.
5. Non-UI projects are rejected before any UI prototype evidence is recorded.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Store UI prototype limitations and downstream obligations in state. | Keeps V0.8 audit, V0.9 handoff, and V0.10 closure traceable to prototype review. |

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
