# V0.9 Codex Goal Handoff - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Add closure readiness handoff semantics. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record handoff interfaces, freeze behavior, and CR outputs. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |
| FR-005 | Closure readiness inputs |
| FR-006 | CR supersession rules |
| FR-007 | Superseded closure handling |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Handoff must include coverage matrix, E2E obligations, negative scope guard obligations, required commands, and CR supersession rules.
- Handoff must preserve V0.10 closure readiness inputs rather than treating Codex Goal handoff as completion.
- Acceptance feedback, scope changes, and test gaps after freeze must be recorded as CR updates.
- Superseded closure artifacts must remain linked to the triggering CR.
- Runtime handoff generation must fail without a passing coverage audit.
- Runtime handoff generation must fail without required verification commands.
- Scope changes after freeze must clear the frozen flag and set the stage back to `version_scope_confirmation`.

## Data And Artifact Rules

- This version package implements handoff generation in `src/product_delivery_agent/handoff.py` and workflow state recording through `ProductDeliveryWorkflow.generate_codex_goal_handoff`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Handoff artifacts must carry matrix range, latest known TC range, E2E obligations, negative scope guard obligations, and required commands.
- CR supersession records must distinguish active closure expectations from superseded closure evidence.
- Handoff artifacts are written to `.product-delivery/artifacts/handoff.md` and `.product-delivery/artifacts/codex-goal-prompt.md`.
- Handoff state is stored under `handoff`, `codex_goal_prompt`, `freeze`, `change_requests`, and `superseded_closures`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.9 runtime interfaces are `build_codex_goal_handoff`, `render_handoff_document`, `render_codex_goal_prompt`, `HandoffError`, `ProductDeliveryWorkflow.generate_codex_goal_handoff`, `record_post_freeze_change`, and `record_superseded_closure`.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Missing coverage matrix, E2E obligations, negative scope guard obligations, or required commands blocks closure readiness.
- Missing CR supersession rules blocks freeze readiness when acceptance feedback, scope changes, or test gaps exist.
- Scope changes after freeze return to version scope confirmation.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
