# V0.5 Hooks And Recovery Guardrails - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | V0.5 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.5 Hooks And Recovery Guardrails. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add explicit FR/NFR/TASK to TC coverage matrix. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record V0.5 hook guardrail unit tests and execution evidence. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Add missing-state, durability-field, branch-specific stop guardrail, and NFR-002 coverage. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for V0.5 hook context builders and guardrails plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V005-001 | Unit test | Active resume context | Run `test_resume_context_summarizes_active_state_from_disk`. | Active resume context includes stage, project type, next gate, confirmations, and skill records; FR-001, NFR-001, and TASK-001 are covered. |
| TC-V005-002 | Unit test | Prompt-time stage context | Run `test_prompt_context_adds_current_stage_for_active_project`. | Prompt context reports current stage and next gate; FR-002, NFR-001, and TASK-001 are covered. |
| TC-V005-003 | Unit test | Pre-compaction state check | Run `test_pre_compaction_requires_valid_written_state_for_active_project`. | Valid active state passes and invalid JSON fails before compaction; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V005-004 | Unit test | Missing or incomplete state | Run `test_pre_compaction_reports_missing_and_incomplete_state`. | Missing `state.json` and missing required durability fields fail pre-compaction; FR-003, NFR-001, and TASK-002 are covered. |
| TC-V005-005 | Unit test | UI stop guardrail | Run `test_stop_guardrail_reports_missing_project_artifacts_and_confirmations`. | Missing UI branch confirmations and artifact files are reported; FR-004, NFR-001, and TASK-002 are covered. |
| TC-V005-006 | Unit test | Non-UI stop guardrail | Run `test_stop_guardrail_uses_non_ui_branch_requirements`. | Missing non-UI branch confirmations and artifact files are reported; FR-004, NFR-001, and TASK-002 are covered. |
| TC-V005-007 | Unit test | Inactive silence | Run `test_inactive_projects_are_silent_for_all_hooks`. | Resume, prompt, pre-compaction, and stop helpers remain silent for inactive projects; FR-005, NFR-002, and TASK-003 are covered. |
| TC-V005-008 | Document check | State authority | Verify the hooks plan states hooks reduce context loss but do not replace state files as the source of truth. | NFR-001 and TASK-001..TASK-003 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type |
| --- | --- | --- | --- | --- |
| FR-001 | NFR-001 | TASK-001 | TC-V005-001 | Unit test |
| FR-002 | NFR-001 | TASK-001 | TC-V005-002 | Unit test |
| FR-003 | NFR-001 | TASK-002 | TC-V005-003, TC-V005-004 | Unit test |
| FR-004 | NFR-001 | TASK-002 | TC-V005-005, TC-V005-006 | Unit test |
| FR-005 | NFR-002 | TASK-003 | TC-V005-007 | Unit test |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V005-008 | Document check |
| NFR-002 | NFR-002 | TASK-003 | TC-V005-007 | Unit test |

## Matrix Rules

- Continuous range: `TC-V005-001..TC-V005-008`.
- Required traceability anchors: `FR/NFR/TASK`.
- Hooks are guardrails and context injectors; state files remain authoritative.
- V0.5 verifies pure helper behavior and does not verify concrete Codex plugin hook registration.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_hooks_recovery.py`.
- Result: PASS, 7 tests.
- Current full-suite execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 69 tests ran in 0.112s.
- Evidence: `src/product_delivery_agent/hooks.py` and `tests/test_hooks_recovery.py`.
- Future evidence: plugin-level hook registration and lifecycle verification when V1.0 packaging exists.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
