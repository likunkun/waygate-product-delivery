# V0.9 Codex Goal Handoff - 06 Test Cases

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
| REV-20260622-02 | 2026-06-22 | Codex | Add closure readiness and CR supersession checks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add NFR traceability to handoff test matrix. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Record V0.9 Codex Goal handoff unit tests and execution evidence. | CR-001 |
| REV-20260622-05 | 2026-06-22 | Codex | Add acceptance-feedback, test-gap, superseded-status, closure-readiness-field, and lifecycle coverage. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.9 Codex Goal handoff gate plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V009-001 | Unit test | Handoff document | Run `test_generates_handoff_document_and_codex_goal_prompt`. | `handoff.md` is generated; FR-001 is covered. |
| TC-V009-002 | Unit test | Codex Goal prompt | Run `test_generates_handoff_document_and_codex_goal_prompt`. | `codex-goal-prompt.md` is generated; FR-002 is covered. |
| TC-V009-003 | Unit test | Frozen handoff contents | Run `test_generates_handoff_document_and_codex_goal_prompt`. | Handoff includes scope, non-goals, confirmations, test obligations, commands, and prohibited work; FR-003 is covered. |
| TC-V009-004 | Unit test | Scope changes | Run `test_scope_change_after_freeze_returns_to_version_scope_confirmation`. | Scope changes after freeze unfreeze scope and return to version scope confirmation; FR-004 is covered. |
| TC-V009-005 | Unit test | Closure readiness | Run `test_generates_handoff_document_and_codex_goal_prompt`, `test_handoff_requires_passing_coverage_audit`, and `test_required_commands_are_mandatory_for_closure_readiness`. | Handoff includes `matrix_range`, `latest_test_case`, E2E/behavior obligations, negative guard records, required commands, prohibited work, and CR supersession rules; missing prerequisites block handoff; FR-005 is covered. |
| TC-V009-006 | Unit test | Scope-change CR | Run `test_scope_change_after_freeze_returns_to_version_scope_confirmation`. | Scope changes after freeze are recorded as CR updates and return to version scope confirmation; FR-004 and FR-006 are covered. |
| TC-V009-007 | Unit test | Acceptance-feedback CR | Run `test_acceptance_feedback_and_test_gaps_after_freeze_are_recorded_as_crs`. | Acceptance feedback after freeze is recorded as a CR update without silently changing active closure evidence; FR-006 is covered. |
| TC-V009-008 | Unit test | Test-gap CR | Run `test_acceptance_feedback_and_test_gaps_after_freeze_are_recorded_as_crs`. | Test gaps after freeze are recorded as CR updates; FR-006 is covered. |
| TC-V009-009 | Unit test | Superseded closure | Run `test_superseded_closure_records_link_to_triggering_cr`. | Superseded closure artifacts are marked `superseded`, linked to the triggering CR, and distinguished from active closure evidence; FR-007 is covered. |
| TC-V009-010 | Unit test | Lifecycle guard | Run V0.3 lifecycle tests `test_start_status_pause_resume_and_stop_preserve_state_and_artifacts` and `test_missing_confirmation_blocks_audit_and_handoff_drafts`. | Handoff workflow remains dormant until `start` and exits intervention after `stop`; NFR-001 and NFR-002 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type | Handoff Obligation |
| --- | --- | --- | --- | --- | --- |
| FR-001 | NFR-001 | TASK-001 | TC-V009-001 | Unit test | Handoff document exists |
| FR-002 | NFR-001 | TASK-002 | TC-V009-002 | Unit test | Codex Goal prompt exists |
| FR-003 | NFR-001 | TASK-003 | TC-V009-003 | Unit test | Scope, non-goals, confirmations, tests, commands, prohibitions |
| FR-004 | NFR-002 | TASK-004 | TC-V009-004, TC-V009-006 | Unit test | Scope changes return to confirmation |
| FR-005 | NFR-003 | TASK-005 | TC-V009-005 | Unit test | Coverage matrix, E2E obligations, scope guard, required commands |
| FR-006 | NFR-002 | TASK-006 | TC-V009-006, TC-V009-007, TC-V009-008 | Unit test | Acceptance feedback, scope changes, and test gaps recorded as CR |
| FR-007 | NFR-003 | TASK-007 | TC-V009-009 | Unit test | Superseded closure artifact marked superseded and linked to triggering CR |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V009-010 | Unit test | Dormant until explicit `start` |
| NFR-002 | NFR-002 | TASK-004, TASK-006 | TC-V009-006, TC-V009-010 | Unit test | Freeze change control and stop exits intervention |

## Closure Readiness Matrix

- Continuous range: `TC-V009-001..TC-V009-010`.
- Required handoff attachments: coverage matrix, `matrix_range`, `latest_test_case`, E2E/behavior obligations, negative scope guard obligations, required commands, prohibited work, and CR supersession rules.
- Required CR triggers: acceptance feedback, scope changes, and test gaps.
- Superseded closure artifacts must be marked `superseded`, remain linked to their triggering CR, and stay distinct from active closure evidence.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_codex_goal_handoff.py`.
- Result: PASS, 6 tests.
- Current full-suite execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 69 tests ran in 0.112s.
- Evidence: `src/product_delivery_agent/handoff.py`, `src/product_delivery_agent/workflow.py`, and `tests/test_codex_goal_handoff.py`.
- Future evidence: implementation command output and formal closure artifact after implementation work.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
