# V1.1 Multi-Agent Review Orchestration - 05 Development Plan

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft / Not Started |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Planning-only development plan. No implementation started. | CR-001 |

## Preconditions Before Implementation

Implementation is blocked until Product Delivery gates are satisfied:

- `non_ui` behavior contract is recorded and confirmed.
- Scenario matrix and `multi_agent_scenario_review` pass.
- Planned coverage obligations, test coverage audit, and `multi_agent_test_coverage_review` pass.
- Canonical `implementation_launch_authorization` is recorded with the required user phrase: `确认按当前交付包开始实现`.

All TASK statuses below are `未开始`.

## TASK Breakdown

| Task | Scope | FR Mapping | Solution Mapping | Dependencies | Status |
| --- | --- | --- | --- | --- | --- |
| TASK-001 | Add `review_orchestration.py` with review profiles, reviewer responsibilities, input snapshot builder, prompt payloads, artifact assembly, and blocked results. | FR-001, FR-002, FR-003, FR-004, FR-005, FR-013 | New Module; Key Flow; ADR-001/003/004 | Preconditions, TASK-007 RED tests | 未开始 |
| TASK-002 | Integrate V1.1 validation in `review_gates.py`: exact review type, deliberation fields, review mode semantics, split gate non-substitution, collection coverage, false-positive risks. | FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-014, FR-015 | Existing Module Changes; ADR-002 | TASK-007 | 未开始 |
| TASK-003 | Add workflow-facing orchestration helpers in `workflow.py`; route accepted artifacts through existing `record_multi_agent_review` without bypassing canonical validation. | FR-002, FR-003, FR-004, FR-005, FR-008, FR-012 | Existing Module Changes; Scenario/Test Coverage/Test Implementation Flows | TASK-001, TASK-002 | 未开始 |
| TASK-004 | Extend artifact/state metadata additively in `artifact_protocol.py`: optional input snapshots, reviewer mirrors, gate results, blocked reasons; preserve existing shape. | FR-007, FR-012, NFR-001, NFR-002, NFR-004, NFR-005 | Storage Model; State Fields; Migration And Compatibility | TASK-001, TASK-002 | 未开始 |
| TASK-005 | Harden `gatekeeper.py` blockers so split reviews, unresolved blocking findings, wrong modes, substituted review types, and summary/status/custom-only review claims fail closed, including non-UI pre-handoff/pre-closure split gates. | FR-006, FR-008, FR-010, FR-011, FR-014, FR-015, FR-016, FR-017 | Existing Module Changes; Risk And Rollback | TASK-002, TASK-004 | 未开始 |
| TASK-006 | Update packaging/docs/templates in `plugin_packaging.py` and packaged skill text for V1.1 orchestration rules, artifact templates, non-UI split gate authority, and structured artifact-only gate semantics. | FR-001..FR-017, NFR-001..NFR-006 | Plugin Packaging; Observability And Evidence; Rollback | TASK-001..TASK-005 | 未开始 |
| TASK-007 | Add RED-first tests for orchestration profiles, prompt/input snapshots, split gate substitution rejection, degradation policy, artifact/state persistence, non-UI gatekeeper blockers, summary/status-only bypass rejection, and packaging/docs. | All FR/NFR | Tests; Risk And Rollback | Preconditions for implementation | 未开始 |

## Milestones

| Milestone | Contents | Exit Criteria | Status |
| --- | --- | --- | --- |
| M1 | RED tests and orchestration contract | Tests fail for missing orchestration/profile/snapshot behavior | 未开始 |
| M2 | Core orchestration and validation | `review_orchestration.py` plus `review_gates.py` tests pass | 未开始 |
| M3 | Workflow/state/gatekeeper integration | Canonical record path and fail-closed blockers pass tests | 未开始 |
| M4 | Packaging/docs consistency | Packaged templates and skill text include V1.1 rules | 未开始 |
| M5 | Regression verification | Existing review, launch, closure, packaging tests pass | 未开始 |

## Implementation Status

No code implementation has started. No TASK is in progress. No 06/07 artifacts are generated yet.

## Blockers And Correction

| Blocker | Impact | Correction |
| --- | --- | --- |
| Behavior contract not confirmed | Non-UI branch evidence is not implementation-ready | Record and confirm current feature behavior contract |
| Scenario review missing | Freeze gate cannot pass | Complete structured `scenario` review with real spawned subagents; current `spawned_subagents_required` policy does not allow `role_simulation` degradation |
| Scenario review carry-forward blockers | Current draft must explicitly cover non-UI split gate enforcement and summary/status/custom-only artifact bypass rejection | Revise requirements, specification, plan, tests, release draft, and handoff before scenario review can pass |
| Planned coverage/test review missing | Pre-handoff cannot pass | Complete planned obligations, coverage audit, and `test_coverage` review |
| Implementation launch authorization missing | Coding cannot start | Record canonical authorization after gates pass |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | Implementation launch authorization is missing. | Coding cannot begin. | Expected Product Delivery gate; do not implement yet |
| Blocker | Behavior contract, scenario review, and planned coverage gates are missing. | Pre-handoff cannot pass. | Prepare and confirm gate artifacts before TASK execution |
| Blocker | Scenario review identified missing explicit coverage for non-UI split gates and status-only/custom artifact bypass rejection. | Scenario review cannot pass until documents and planned tests cover those risks. | Apply documentation/test revisions and rerun structured scenario review |
| Assumption | TASK-007 RED tests should be written before implementation changes. | Keeps implementation test-driven and prevents shallow orchestration. | Carry forward |
