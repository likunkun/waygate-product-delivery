# V0.3 Local Skill Workflow Prototype - 06 Test Cases

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
| REV-20260622-02 | 2026-06-22 | Codex | Add explicit FR/NFR/TASK to TC coverage matrix. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record V0.3 workflow prototype unit tests and execution evidence. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.3 local workflow prototype plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V003-001 | Unit test | Start activation | Run `test_start_status_pause_resume_and_stop_preserve_state_and_artifacts`. | `start` activates product delivery mode for the project; FR-001, NFR-001, and TASK-001 are covered. |
| TC-V003-002 | Unit test | Lifecycle commands | Run `test_start_status_pause_resume_and_stop_preserve_state_and_artifacts`. | `status`, `pause`, `resume`, and `stop` preserve state; `stop` exits intervention while artifacts remain; FR-002, NFR-001, NFR-002, and TASK-001 are covered. |
| TC-V003-003 | Unit test | UI routing | Run `test_ui_project_routes_to_prototype_confirmation_only`. | `project_type=ui` routes to `ui_prototype_review` and not the non-UI gate; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V003-004 | Unit test | Non-UI routing | Run `test_non_ui_project_routes_to_behavior_contract_only`. | `project_type=non_ui` routes to `non_ui_behavior_contract` and not the UI gate; FR-004, NFR-001, and TASK-002 are covered. |
| TC-V003-005 | Unit test | Audit and handoff drafts | Run `test_confirmation_gates_prepare_audit_and_handoff_drafts` and `test_missing_confirmation_blocks_audit_and_handoff_drafts`. | Confirmed gates create draft audit and handoff artifacts; missing confirmations block the transition; FR-005 and TASK-003 are covered. |
| TC-V003-006 | Unit test | Continuity and non-interference | Run `test_resume_prefers_disk_state_over_chat_context` plus lifecycle stop assertions. | Disk state wins over fallback chat context; `stop` disables intervention and preserves artifacts; NFR-001, NFR-002, and TASK-001 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type |
| --- | --- | --- | --- | --- |
| FR-001 | NFR-001 | TASK-001 | TC-V003-001 | Unit test |
| FR-002 | NFR-001, NFR-002 | TASK-001 | TC-V003-002 | Unit test |
| FR-003 | NFR-001 | TASK-002 | TC-V003-003 | Unit test |
| FR-004 | NFR-001 | TASK-002 | TC-V003-004 | Unit test |
| FR-005 | NFR-001 | TASK-003 | TC-V003-005 | Unit test |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V003-006 | Unit test |
| NFR-002 | NFR-002 | TASK-001 | TC-V003-002, TC-V003-006 | Unit test |

## Matrix Rules

- Continuous range: `TC-V003-001..TC-V003-006`.
- Required traceability anchors: `FR/NFR/TASK`.
- V0.3 implements local workflow prototype verification in `tests/test_workflow_prototype.py`.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_workflow_prototype.py`.
- Result: PASS, 6 tests ran in 0.016s.
- Combined V0.2+V0.3 execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 11 tests ran in 0.021s.
- Evidence: `src/product_delivery_agent/workflow.py` and `tests/test_workflow_prototype.py`.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
