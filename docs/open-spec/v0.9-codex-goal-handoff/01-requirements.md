# V0.9 Codex Goal Handoff - 01 Requirements

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
| REV-20260622-02 | 2026-06-22 | Codex | Add closure readiness and CR supersession requirements. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record runtime Codex Goal handoff implementation and test evidence. | CR-001 |


## Business Goal

Generate a frozen version package that can be handed to implementation Codex.

## Scope

### In Scope

- Generate the handoff document.
- Generate a Codex Goal prompt.
- Include scope, non-goals, confirmation results, test obligations, verification commands, and prohibited work.
- Include coverage matrix, E2E obligations, negative scope guard obligations, required commands, and CR supersession rules.
- Preserve closure readiness inputs for V0.10.
- Require scope changes after freeze to return to version scope confirmation.
- Implement handoff generation, Codex Goal prompt generation, freeze state, post-freeze CR recording, and superseded closure recording.

### Out Of Scope

- Executing implementation Codex work.
- Waygate intake automation.
- Changing scope after freeze without re-confirmation.
- Treating Codex Goal handoff as final completion.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When handoff is requested, the workflow shall generate a handoff document. | Handoff document is listed as a required output. |
| FR-002 | P0 | When handoff is requested, the workflow shall generate a Codex Goal prompt. | Codex Goal prompt is listed as a required output. |
| FR-003 | P0 | When the version is frozen, handoff shall include scope, non-goals, confirmation results, test obligations, verification commands, and prohibited work. | Handoff content requirements list these fields. |
| FR-004 | P0 | When scope changes after freeze, the workflow shall return to version scope confirmation. | Freeze change rule is documented. |
| FR-005 | P0 | When handoff is generated, it shall include coverage matrix, E2E obligations, negative scope guard obligations, and required commands. | Handoff content requirements include closure readiness inputs. |
| FR-006 | P0 | When acceptance feedback, scope changes, or test gaps appear after freeze, they shall be recorded as CR updates. | CR supersession and return-to-scope rules are documented. |
| FR-007 | P0 | When a prior closure is replaced, handoff records shall require the old closure to be marked superseded and linked to the triggering CR. | Superseded closure handling is documented. |

Runtime acceptance:

- `ProductDeliveryWorkflow.generate_codex_goal_handoff(...)` writes `handoff.md` and `codex-goal-prompt.md`.
- Handoff generation requires a passing V0.8 coverage audit and at least one verification command.
- Generated handoff carries `matrix_range`, `latest_test_case`, E2E/behavior obligations, negative guard records, required commands, prohibited work, and CR supersession rules.
- `record_post_freeze_change(..., change_type="scope_change")` unfreezes scope and returns the workflow to version scope confirmation.
- `record_superseded_closure(...)` marks old closure artifacts as superseded and links them to the triggering CR.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Handoff completeness | Implementation Codex must receive enough context to avoid product-intent drift. | Handoff includes scope, non-goals, confirmations, tests, commands, and prohibitions. |
| NFR-002 | Change control | Frozen scope cannot change silently. | Scope change returns to confirmation. |
| NFR-003 | Closure readiness | Handoff must carry enough evidence obligations for V0.10 formal closure. | Handoff includes matrix, E2E, scope guard, command, and CR supersession inputs. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Closure Readiness Requirements

- Handoff must carry the V0.8 coverage matrix, including TC range and traceability anchors.
- Handoff must carry E2E obligations and exemptions.
- Handoff must carry negative scope guard obligations from V0.6 or V0.7.
- Handoff must list required verification commands expected before V0.10 closure.
- Handoff must define CR supersession rules for acceptance feedback, scope changes, test gaps, and superseded closure artifacts.

## Risks And Assumptions

- Risk: scope drift from future implementation details. Mitigation: keep this version aligned to `ROADMAP.md` scope.
- Risk: branch rules become ambiguous. Mitigation: keep UI and non-UI confirmation gates mutually exclusive.
- Assumption: Codex Goal remains the first handoff target until a later version changes the roadmap.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Future implementation details are intentionally deferred from this requirements package. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
