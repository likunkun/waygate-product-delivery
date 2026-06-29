# V0.2 Artifact And State Protocol - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | V0.2 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.2 Artifact And State Protocol. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add explicit FR/NFR/TASK to TC coverage matrix. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record V0.2 runtime unit tests and execution evidence. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.2 artifact/state protocol plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V002-001 | Unit test | Artifact root | Run `test_initialize_workspace_creates_artifact_root_state_and_templates`. | `.product-delivery/`, `state.json`, `templates/`, and `artifacts/` are created; FR-001, NFR-002, and TASK-001 are covered. |
| TC-V002-002 | Unit test | State precedence | Run `test_load_state_prefers_disk_state_over_chat_context_fallback`. | Disk `state.json` wins over fallback chat context; FR-002, NFR-001, and TASK-002 are covered. |
| TC-V002-003 | Unit test | State responsibilities | Run `test_state_records_required_responsibility_categories`. | `state.json` includes stage, project type, confirmation points, artifact paths, and update timestamp; FR-003, NFR-001, NFR-002, and TASK-002 are covered. |
| TC-V002-004 | Unit test | Artifact templates | Run `test_initialize_workspace_creates_artifact_root_state_and_templates`. | Product brief, version scope, UI prototype review, non-UI behavior contract, test audit, and handoff templates exist; FR-004, NFR-002, and TASK-003 are covered. |
| TC-V002-005 | Unit test | Recovery and retention evidence | Run `test_initialize_workspace_preserves_existing_state_and_artifacts` and `test_written_state_is_valid_json_on_disk`. | Existing state and artifacts are preserved; persisted state is valid JSON; NFR-001 and TASK-001..TASK-003 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type |
| --- | --- | --- | --- | --- |
| FR-001 | NFR-002 | TASK-001 | TC-V002-001 | Unit test |
| FR-002 | NFR-001 | TASK-002 | TC-V002-002 | Unit test |
| FR-003 | NFR-001, NFR-002 | TASK-002 | TC-V002-003 | Unit test |
| FR-004 | NFR-002 | TASK-003 | TC-V002-004 | Unit test |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V002-005 | Unit test |

## Matrix Rules

- Continuous range: `TC-V002-001..TC-V002-005`.
- Required traceability anchors: `FR/NFR/TASK`.
- V0.2 defines and implements artifact and state protocol responsibilities; executable checks are in `tests/test_artifact_protocol.py`.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_artifact_protocol.py`.
- Result: PASS, 5 tests ran in 0.010s.
- Evidence: `src/product_delivery_agent/artifact_protocol.py` and `tests/test_artifact_protocol.py`.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
