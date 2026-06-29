# V0.3 Local Skill Workflow Prototype - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime workflow prototype module implementation. | CR-001 |


## Solution Boundary

This version implements the runtime solution boundary for `V0.3 - Local Skill Workflow Prototype`.
It does not implement installable plugin packaging, hooks, browser prototype generation, formal closure, or direct Waygate integration.

## Modules And Responsibilities

- `src/product_delivery_agent/workflow.py`: local workflow command facade.
- `ProductDeliveryWorkflow`: implements `start`, `status`, `pause`, `resume`, `stop`, project type selection, confirmation recording, and audit/handoff draft preparation.
- `WorkflowError`: reports invalid transitions or missing confirmations.
- V0.2 artifact protocol: persists state and artifacts.
- `tests/test_workflow_prototype.py`: verifies V0.3 workflow behavior.

## Key Flow

1. Caller creates `ProductDeliveryWorkflow(project_root)`.
2. Caller runs `start`; workflow initializes `.product-delivery/`, enters active mode, and moves to product blueprint.
3. Caller selects project type; UI routes to `ui_prototype_confirmation`, non-UI routes to `non_ui_behavior_contract_confirmation`.
4. Caller records confirmations through `confirm`.
5. Caller runs `prepare_audit_and_handoff_drafts`; missing confirmations block the transition.
6. When gates pass, the workflow writes draft test coverage audit and Codex Goal handoff artifacts.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Validate with local skill before final plugin packaging. | Reduces distribution complexity while the workflow stabilizes. |
| ADR-006 | Reuse the V0.2 artifact protocol for all workflow state. | Prevents duplicate state handling and keeps recovery behavior consistent. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| Premature handoff draft | Check required confirmations before writing audit and handoff drafts. | Keep state at the current confirmation stage. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Plugin packaging architecture and CLI contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
