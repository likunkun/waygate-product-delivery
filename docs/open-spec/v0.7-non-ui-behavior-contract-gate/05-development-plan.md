# V0.7 Non-UI Behavior Contract Gate - 05 Development Plan

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
| REV-20260622-02 | 2026-06-22 | Codex | Record completed non-UI behavior contract implementation and tests. | CR-001 |


## Implementation Posture

This package now includes the runtime non-UI behavior contract gate implementation for `V0.7`.
The implementation lives in `src/product_delivery_agent/non_ui_behavior.py` and `ProductDeliveryWorkflow.record_non_ui_behavior_contract`, and is verified by `tests/test_non_ui_behavior_contract.py`.

## Task Plan

| Task | Description | Mapped FR | Status | Delivery Type |
| --- | --- | --- | --- | --- |
| TASK-001 | Implement behavior contract artifact and review record. | FR-001, FR-002, FR-004 | Complete | non-UI gate |
| TASK-002 | Implement behavior confirmation gate before test audit. | FR-003 | Complete | non-UI gate |
| TASK-003 | Implement behavior contract propagation into audit, handoff, and closure inputs. | FR-005 | Complete | non-UI gate |

## Dependencies

- Depends on the approved roadmap in `ROADMAP.md`.
- Depends on previous version packages for inherited policy and scope continuity.
- Depends on V0.2 artifact/state protocol.
- Depends on V0.3 workflow project type routing and confirmation gates.
- Depends on V0.5 hook/state recovery behavior for continuity.
- Must remain mutually exclusive with V0.6 UI prototype gate.
- Does not depend on direct Waygate state mutation.

## Milestones

- M1: Complete Open Spec documentation for this version. Complete.
- M2: Implement non-UI behavior contract validation and state recording. Complete.
- M3: Verify V0.7 unit tests pass. Complete.
- M4: Carry approved decisions into the next version package.

## Blockers And Deviations

- Blockers: none.
- Deviations: the active thread goal upgraded this version from documentation-only planning to runtime implementation. Real API/service/CLI execution remains out of scope.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation subtasks will be refined when this version enters actual build work. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
