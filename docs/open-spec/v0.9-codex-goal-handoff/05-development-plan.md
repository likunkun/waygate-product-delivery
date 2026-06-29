# V0.9 Codex Goal Handoff - 05 Development Plan

| Field | Value |
| --- | --- |
| Version | V0.9 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.9 Codex Goal Handoff. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add closure readiness handoff tasks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record completed Codex Goal handoff implementation and tests. | CR-001 |


## Implementation Posture

This package now includes the runtime Codex Goal handoff implementation for `V0.9`.
The implementation lives in `src/product_delivery_agent/handoff.py` and `ProductDeliveryWorkflow.generate_codex_goal_handoff`, and is verified by `tests/test_codex_goal_handoff.py`.

## Task Plan

| Task | Description | Mapped FR | Status | Delivery Type |
| --- | --- | --- | --- | --- |
| TASK-001 | Implement handoff document contents. | FR-001 | Complete | handoff |
| TASK-002 | Implement Codex Goal prompt contents. | FR-002 | Complete | handoff |
| TASK-003 | Implement frozen scope, non-goals, confirmations, tests, commands, and prohibited work. | FR-003 | Complete | handoff |
| TASK-004 | Implement freeze and scope-change return behavior. | FR-004 | Complete | handoff |
| TASK-005 | Implement closure readiness attachment for coverage matrix, E2E obligations, negative scope guard obligations, and required commands. | FR-005 | Complete | handoff |
| TASK-006 | Implement CR supersession handling for acceptance feedback, scope changes, and test gaps. | FR-006 | Complete | handoff |
| TASK-007 | Implement superseded closure artifact linkage. | FR-007 | Complete | handoff |

## Dependencies

- Depends on the approved roadmap in `ROADMAP.md`.
- Depends on previous version packages for inherited policy and scope continuity.
- Depends on V0.8 coverage matrix and E2E obligation outputs.
- Feeds V0.10 formal closure gate.
- Depends on V0.2 artifact/state protocol and V0.3 workflow state.
- Does not depend on direct Waygate state mutation.

## Milestones

- M1: Complete Open Spec documentation for this version. Complete.
- M2: Implement handoff generation, freeze state, and post-freeze CR records. Complete.
- M3: Verify V0.9 unit tests pass. Complete.
- M4: Carry approved decisions into the next version package.

## Blockers And Deviations

- Blockers: none.
- Deviations: the active thread goal upgraded this version from documentation-only planning to runtime implementation. Executing implementation Codex work remains out of scope.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation subtasks will be refined when this version enters actual build work. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
