# V0.5 Hooks And Recovery Guardrails - 01 Requirements

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime hook guardrail implementation and unit-test evidence. | CR-001 |


## Business Goal

Preserve workflow continuity across compaction, resume, and long sessions.

## Scope

### In Scope

- Inject current state when an active project starts or resumes.
- Add current stage context before user prompts in active projects.
- Check that state is written before compaction.
- Check missing artifacts or confirmation records before stopping.
- Keep hooks silent for inactive projects.
- Implement pure hook result helpers that read local Product Delivery state without binding to a concrete Codex hook framework.

### Out Of Scope

- General-purpose hook framework replacement.
- Hooks that operate outside active Product Delivery projects.
- Direct mutation of Waygate state.
- Direct mutation of controller state.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When an active project starts or resumes, hooks shall provide the current state context. | Specification documents active-project state injection. |
| FR-002 | P0 | When a user prompt is submitted in an active project, hooks shall add current stage context. | Specification documents prompt-time stage context. |
| FR-003 | P0 | Before compaction, hooks shall check that state is written. | Specification documents pre-compaction state check. |
| FR-004 | P0 | Before stopping, hooks shall check missing artifacts or confirmation records. | Specification documents stop-time guardrail. |
| FR-005 | P0 | When the project is inactive, hooks shall remain silent. | Specification documents inactive silence. |

Runtime acceptance:

- `build_resume_context(project_root)` reports stage, project type, next gate, confirmations, and skill records for active projects.
- `build_prompt_context(project_root)` reports current stage and next gate for active projects.
- `check_pre_compaction(project_root)` verifies readable, valid `state.json` before compaction.
- `check_stop_guardrail(project_root)` reports missing required confirmations and artifact files before stop.
- All V0.5 hook helpers return silent results for inactive projects.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Resilience | Hooks must reduce compaction and resume context loss without becoming the source of truth. | State files remain authoritative. |
| NFR-002 | Non-interference | Inactive projects must not receive workflow intervention. | Inactive silence is a hard rule. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

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
