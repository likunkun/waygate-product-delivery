# V0.6 UI Prototype Gate - 06 Test Cases

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
| REV-20260622-02 | 2026-06-22 | Codex | Add UI scenario taxonomy and closure input checks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add explicit UI taxonomy tests and FR/NFR/TASK coverage matrix. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Tighten limitation propagation into audit, handoff, and closure inputs. | CR-001 |
| REV-20260622-05 | 2026-06-22 | Codex | Record V0.6 UI prototype gate unit tests and execution evidence. | CR-001 |
| REV-20260622-06 | 2026-06-22 | Codex | Add explicit permission and long-task taxonomy coverage. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.6 UI prototype gate plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V006-001 | Unit test | UI project branch | Run `test_non_ui_project_cannot_enter_ui_prototype_gate` and `test_ui_project_records_complete_prototype_review_and_downstream_inputs`. | `project_type=ui` can record prototype review; non-UI projects are rejected; FR-001, NFR-002, and TASK-001 are covered. |
| TC-V006-002 | Unit test | Pages, states, journeys | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs`. | Prototype review records key pages, UI states, and user journeys; FR-002, NFR-001, and TASK-001 are covered. |
| TC-V006-003 | Unit test | User confirmation gate | Run `test_audit_and_handoff_block_until_ui_prototype_review_is_confirmed`. | Audit and handoff are blocked until UI prototype review confirmation; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V006-004 | Unit test | Accepted limitations propagation | Run `test_limitations_are_carried_in_state_for_later_audit_handoff_and_closure`. | Accepted prototype limitations are copied into state for V0.8 audit, V0.9 handoff, and V0.10 closure; FR-004, NFR-003, and TASK-003 are covered. |
| TC-V006-005 | Unit test | Role and main-path taxonomy | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs` and `test_missing_taxonomy_blocks_prototype_confirmation`. | Prototype review records required roles and main paths, and missing taxonomy blocks recording; FR-005, NFR-001, and TASK-001 are covered. |
| TC-V006-006 | Unit test | Exception and recovery taxonomy | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs` and `test_missing_taxonomy_blocks_prototype_confirmation`. | Prototype review records user-visible exceptions and recovery paths; missing entries block recording; FR-005, NFR-001, and TASK-001 are covered. |
| TC-V006-007 | Unit test | Accessibility and device taxonomy | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs` and `test_missing_taxonomy_blocks_prototype_confirmation`. | Prototype review records mobile and keyboard coverage; missing entries block recording; FR-005, NFR-001, and TASK-001 are covered. |
| TC-V006-008 | Unit test | Negative scope boundaries | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs` and `test_missing_taxonomy_blocks_prototype_confirmation`. | Prototype review records negative scope boundaries; missing entries block recording; FR-005, NFR-003, and TASK-001 are covered. |
| TC-V006-009 | Unit test | Browser E2E inputs | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs`. | Confirmed prototype scenarios produce downstream browser E2E candidates; FR-006, NFR-003, and TASK-003 are covered. |
| TC-V006-010 | Unit test | Negative scope guard inputs | Run `test_ui_project_records_complete_prototype_review_and_downstream_inputs`. | Confirmed prototype boundaries produce downstream negative scope guard candidates; FR-006, NFR-003, and TASK-003 are covered. |
| TC-V006-011 | Unit test | Permission taxonomy | Run `test_missing_permissions_or_long_tasks_block_prototype_confirmation`. | Prototype review records permission scenarios and missing permission taxonomy blocks confirmation; FR-005, NFR-001, and TASK-001 are covered. |
| TC-V006-012 | Unit test | Long-task taxonomy | Run `test_missing_permissions_or_long_tasks_block_prototype_confirmation`. | Prototype review records long-task scenarios and missing long-task taxonomy blocks confirmation; FR-005, NFR-001, and TASK-001 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type | Downstream Obligation |
| --- | --- | --- | --- | --- | --- |
| FR-001 | NFR-002 | TASK-001 | TC-V006-001 | Unit test | UI-only prototype branch |
| FR-002 | NFR-001 | TASK-001 | TC-V006-002 | Unit test | User journey review input |
| FR-003 | NFR-001 | TASK-002 | TC-V006-003 | Unit test | Audit cannot start before confirmation |
| FR-004 | NFR-003 | TASK-003 | TC-V006-004 | Unit test | Limitation propagation to V0.8 audit, V0.9 handoff, and V0.10 closure |
| FR-005 | NFR-001 | TASK-001 | TC-V006-005 | Unit test | Role and main-path E2E candidates |
| FR-005 | NFR-001 | TASK-001 | TC-V006-006 | Unit test | User-visible exception and recovery E2E candidates |
| FR-005 | NFR-001 | TASK-001 | TC-V006-007 | Unit test | Mobile and keyboard review inputs |
| FR-005 | NFR-003 | TASK-001 | TC-V006-008 | Unit test | Negative scope guard candidates |
| FR-005 | NFR-001 | TASK-001 | TC-V006-011 | Unit test | Permission scenario review inputs |
| FR-005 | NFR-001 | TASK-001 | TC-V006-012 | Unit test | Long-task scenario review inputs |
| FR-006 | NFR-003 | TASK-003 | TC-V006-009 | Unit test | Browser E2E obligations for V0.8/V0.10 |
| FR-006 | NFR-003 | TASK-003 | TC-V006-010 | Unit test | Negative scope guard obligations for V0.8/V0.10 |

## Matrix Rules

- Continuous range: `TC-V006-001..TC-V006-012`.
- Required traceability anchors: `FR/NFR/TASK`.
- Prototype confirmation must generate reviewable inputs for later browser E2E, accepted-limitations handling, negative scope guard, V0.9 handoff, and V0.10 closure obligations.
- V0.6 verifies review/state behavior, not full browser automation.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_ui_prototype_gate.py`.
- Result: PASS, 6 tests.
- Current full-suite execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 69 tests ran in 0.112s.
- Evidence: `src/product_delivery_agent/ui_prototype.py`, `src/product_delivery_agent/workflow.py`, and `tests/test_ui_prototype_gate.py`.
- Future evidence: browser E2E execution and screenshot/pixel validation when a concrete UI implementation or prototype runner is in scope.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
