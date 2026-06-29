# V0.8 Test Coverage Audit - 05 Development Plan

| Field | Value |
| --- | --- |
| Version | V0.8 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.8 Test Coverage Audit. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add closure-ready matrix tasks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record completed coverage audit implementation and tests. | CR-001 |


## Implementation Posture

This package now includes the runtime test coverage audit implementation for `V0.8`.
The implementation lives in `src/product_delivery_agent/coverage_audit.py` and `ProductDeliveryWorkflow.record_test_coverage_audit`, and is verified by `tests/test_coverage_audit.py`.

## Task Plan

| Task | Description | Mapped FR | Status | Delivery Type |
| --- | --- | --- | --- | --- |
| TASK-001 | Implement coverage matrix and status categories. | FR-001 | Complete | audit |
| TASK-002 | Implement UI and non-UI E2E coverage rules. | FR-002 | Complete | audit |
| TASK-003 | Implement non-UI API/service/CLI E2E or equivalent behavior evidence rules. | FR-003 | Complete | audit |
| TASK-004 | Implement blocking and exemption behavior before handoff. | FR-004 | Complete | audit |
| TASK-005 | Implement continuous TC range validation. | FR-005 | Complete | audit |
| TASK-006 | Implement `FR/NFR/US/J/AC/TASK` traceability validation. | FR-006 | Complete | audit |
| TASK-007 | Implement browser E2E requirement for active UI stories, journeys, and user-visible exceptions. | FR-007, FR-008 | Complete | audit |
| TASK-008 | Implement test layer and semantic marker validation. | FR-009 | Complete | audit |

## Dependencies

- Depends on the approved roadmap in `ROADMAP.md`.
- Depends on previous version packages for inherited policy and scope continuity.
- Depends on V0.6 and V0.7 scenario outputs for E2E and negative boundary obligations.
- Depends on V0.2 artifact/state protocol and V0.3 workflow state.
- Does not depend on direct Waygate state mutation.

## Milestones

- M1: Complete Open Spec documentation for this version. Complete.
- M2: Implement coverage audit validation and state recording. Complete.
- M3: Verify V0.8 unit tests pass. Complete.
- M4: Carry approved decisions into the next version package.

## Blockers And Deviations

- Blockers: none.
- Deviations: the active thread goal upgraded this version from documentation-only planning to runtime implementation. Actual browser/API/service/CLI test command execution remains out of scope.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation subtasks will be refined when this version enters actual build work. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
