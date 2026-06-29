# V0.9 Codex Goal Handoff - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Add closure readiness handoff components. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record Codex Goal handoff module and workflow integration. | CR-001 |


## Solution Boundary

This version package implements `V0.9 - Codex Goal Handoff` as a runtime workflow increment.
It generates local handoff artifacts and freeze/change-control state, but does not execute implementation Codex work.

## Modules And Responsibilities

- `ProductDeliveryWorkflow.generate_codex_goal_handoff`: workflow entrypoint for handoff generation.
- `build_codex_goal_handoff`: validates prerequisites and assembles closure-ready handoff data.
- `render_handoff_document`: renders local handoff Markdown.
- `render_codex_goal_prompt`: renders the prompt for implementation Codex.
- `record_post_freeze_change`: records CR updates and returns scope changes to confirmation.
- `record_superseded_closure`: marks replaced closure artifacts as superseded.
- Freeze state, coverage matrix attachment, E2E/behavior obligation attachment, negative guard attachment, required commands list, and CR supersession records.

## Key Flow

1. Read active workflow state and passing V0.8 coverage audit.
2. Validate scope and required verification commands.
3. Assemble scope, non-goals, confirmations, prohibited work, coverage matrix, E2E/behavior obligations, negative guards, required commands, and CR supersession rules.
4. Write `handoff.md` and `codex-goal-prompt.md`.
5. Freeze scope and set next gate to V0.10 formal closure after implementation.
6. If acceptance feedback, scope changes, or test gaps appear, record a CR update; scope changes return to version scope confirmation.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Carry closure readiness through handoff. | Ensures implementation Codex receives evidence obligations needed by V0.10. |
| ADR-006 | Treat acceptance feedback, scope changes, and test gaps as CR updates. | Prevents silent drift after freeze. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| Closure readiness omitted | Require matrix, E2E, scope guard, command, and CR records in handoff. | Return to V0.9 handoff assembly. |
| Superseded closure ambiguity | Link superseded closure artifacts to triggering CR. | Reissue handoff with explicit supersession record. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation-specific architecture diagrams and API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
