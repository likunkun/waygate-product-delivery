# V0.7 Non-UI Behavior Contract Gate - 06 Test Cases

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
| REV-20260622-02 | 2026-06-22 | Codex | Add non-UI scenario taxonomy and closure input checks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add explicit non-UI taxonomy tests and FR/NFR/TASK coverage matrix. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Align taxonomy task anchors and downstream propagation checks. | CR-001 |
| REV-20260622-05 | 2026-06-22 | Codex | Record V0.7 non-UI behavior contract unit tests and execution evidence. | CR-001 |
| REV-20260622-06 | 2026-06-22 | Codex | Add explicit permission and long-task taxonomy coverage. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.7 non-UI behavior contract gate plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V007-001 | Unit test | Non-UI branch | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs` and `test_ui_project_cannot_enter_non_ui_behavior_contract_gate`. | `project_type=non_ui` can record behavior contract; UI projects are rejected; FR-001, NFR-001, NFR-002, and TASK-001 are covered. |
| TC-V007-002 | Unit test | Entry points and I/O | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs`. | Behavior contract records entry points, inputs, and outputs; FR-002, FR-004, NFR-001, and TASK-001 are covered. |
| TC-V007-003 | Unit test | Error and recovery paths | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs` and `test_missing_taxonomy_blocks_behavior_contract_recording`. | Behavior contract records exceptions and recovery paths; missing taxonomy blocks recording; FR-002, FR-004, NFR-001, and TASK-001 are covered. |
| TC-V007-004 | Unit test | State transitions | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs` and `test_missing_taxonomy_blocks_behavior_contract_recording`. | Behavior contract records state transitions and boundary conditions; missing taxonomy blocks recording; FR-002, FR-004, NFR-001, and TASK-001 are covered. |
| TC-V007-005 | Unit test | User confirmation gate | Run `test_audit_and_handoff_block_until_behavior_contract_is_confirmed`. | Audit and handoff are blocked until behavior contract confirmation; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V007-006 | Unit test | Traceable behavior paths | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs`. | Confirmed behavior records produce behavior evidence candidates; FR-005, NFR-003, and TASK-003 are covered. |
| TC-V007-007 | Unit test | Negative boundary records | Run `test_non_ui_project_records_behavior_contract_and_downstream_inputs`. | Confirmed behavior boundaries produce downstream negative boundary candidates; FR-005, NFR-003, and TASK-003 are covered. |
| TC-V007-008 | Unit test | Accepted limitations propagation | Run `test_limitations_are_carried_for_later_audit_handoff_and_closure`. | Accepted behavior limitations are copied into state for V0.8 audit, V0.9 handoff, and V0.10 closure; FR-005, NFR-003, and TASK-003 are covered. |
| TC-V007-009 | Unit test | Permission taxonomy | Run `test_missing_permissions_or_long_tasks_block_behavior_contract_recording`. | Behavior contract records permission scenarios and missing permission taxonomy blocks confirmation; FR-002, FR-004, NFR-001, and TASK-001 are covered. |
| TC-V007-010 | Unit test | Long-task taxonomy | Run `test_missing_permissions_or_long_tasks_block_behavior_contract_recording`. | Behavior contract records long-task scenarios and missing long-task taxonomy blocks confirmation; FR-002, FR-004, NFR-001, and TASK-001 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type | Downstream Obligation |
| --- | --- | --- | --- | --- | --- |
| FR-001 | NFR-001, NFR-002 | TASK-001 | TC-V007-001 | Unit test | Non-UI branch and no HTML prototype |
| FR-002 | NFR-001 | TASK-001 | TC-V007-002 | Unit test | API/service/CLI E2E candidates |
| FR-002 | NFR-001 | TASK-001 | TC-V007-003 | Unit test | Exception and recovery evidence candidates |
| FR-002 | NFR-001 | TASK-001 | TC-V007-004 | Unit test | State transition evidence candidates |
| FR-002 | NFR-001 | TASK-001 | TC-V007-009 | Unit test | Permission behavior evidence candidates |
| FR-002 | NFR-001 | TASK-001 | TC-V007-010 | Unit test | Long-task behavior evidence candidates |
| FR-003 | NFR-001 | TASK-002 | TC-V007-005 | Unit test | Audit cannot start before confirmation |
| FR-004 | NFR-001 | TASK-001 | TC-V007-002, TC-V007-003, TC-V007-004, TC-V007-009, TC-V007-010 | Unit test | Full non-UI scenario taxonomy |
| FR-005 | NFR-003 | TASK-003 | TC-V007-006 | Unit test | Behavior evidence obligations for V0.8/V0.10 |
| FR-005 | NFR-003 | TASK-003 | TC-V007-007 | Unit test | Negative boundary guard obligations for V0.8/V0.10 |
| FR-005 | NFR-003 | TASK-003 | TC-V007-008 | Unit test | Limitation propagation to handoff and closure |

## Matrix Rules

- Continuous range: `TC-V007-001..TC-V007-010`.
- Required traceability anchors: `FR/NFR/TASK`.
- Non-UI projects do not produce HTML prototypes, but they must produce traceable behavior paths, accepted-limitations handling, and negative boundary records for later V0.8 audit, V0.9 handoff, and V0.10 closure.
- V0.7 verifies behavior contract review/state behavior, not real API/service/CLI execution.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_non_ui_behavior_contract.py`.
- Result: PASS, 6 tests.
- Current full-suite execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 69 tests ran in 0.112s.
- Evidence: `src/product_delivery_agent/non_ui_behavior.py`, `src/product_delivery_agent/workflow.py`, and `tests/test_non_ui_behavior_contract.py`.
- Future evidence: API/service/CLI E2E or equivalent execution when concrete implementation exists.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
