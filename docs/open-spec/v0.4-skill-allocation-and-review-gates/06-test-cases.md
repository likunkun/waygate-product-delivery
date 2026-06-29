# V0.4 Skill Allocation And Review Gates - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | V0.4 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.4 Skill Allocation And Review Gates. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add explicit FR/NFR/TASK to TC coverage matrix. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record V0.4 skill gate unit tests and execution evidence. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.4 skill gate policy plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V004-001 | Unit test | Startup skill | Run `test_stage_allocations_include_waygate_baseline_skills`. | Startup requires `superpowers:using-superpowers`; FR-001, NFR-001, and TASK-001 are covered. |
| TC-V004-002 | Unit test | Brainstorming skill | Run `test_stage_allocations_include_waygate_baseline_skills`. | Blueprint and scope shaping require `superpowers:brainstorming`; FR-002, NFR-001, and TASK-001 are covered. |
| TC-V004-003 | Unit test | Test strategy skill | Run `test_test_coverage_audit_accepts_either_test_strategy_skill` and `test_missing_required_stage_skill_fails_gate`. | Test coverage audit accepts `test-strategy` or `testing-strategy`; missing required skills fail; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V004-004 | Unit test | UI skill | Run `test_stage_allocations_include_waygate_baseline_skills`. | UI prototype confirmation requires `ui-ux-pro-max`; FR-004, NFR-001, and TASK-002 are covered. |
| TC-V004-005 | Unit test | Conditional file skills | Run `test_file_specific_skills_are_conditional_on_file_types`. | `pdf`, `docx`, and `pptx` are required only for matching file extensions; NFR-002 and TASK-003 are covered. |
| TC-V004-006 | Unit test | Gate visibility | Run `test_workflow_records_reviewable_skill_gate_result_in_state` and `test_workflow_blocks_failed_skill_gate_record`. | Passed skill gates are recorded in state; failed gates are blocked; NFR-001 and TASK-001..TASK-003 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type |
| --- | --- | --- | --- | --- |
| FR-001 | NFR-001 | TASK-001 | TC-V004-001 | Unit test |
| FR-002 | NFR-001 | TASK-001 | TC-V004-002 | Unit test |
| FR-003 | NFR-001 | TASK-002 | TC-V004-003 | Unit test |
| FR-004 | NFR-001 | TASK-002 | TC-V004-004 | Unit test |
| NFR-002 | NFR-002 | TASK-003 | TC-V004-005 | Unit test |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V004-006 | Unit test |

## Matrix Rules

- Continuous range: `TC-V004-001..TC-V004-006`.
- Required traceability anchors: `FR/NFR/TASK`.
- V0.4 verifies explicit skill allocation, conditional file-skill gating, and reviewable workflow state recording; it does not install or discover external skills.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_skill_gates.py`.
- Result: PASS, 6 tests ran in 0.006s.
- Combined V0.2-V0.4 execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 17 tests ran in 0.019s.
- Evidence: `src/product_delivery_agent/skill_gates.py`, `src/product_delivery_agent/workflow.py`, and `tests/test_skill_gates.py`.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
