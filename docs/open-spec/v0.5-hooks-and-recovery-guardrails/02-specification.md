# V0.5 Hooks And Recovery Guardrails - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Record hook helper interfaces and active/inactive behavior. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |
| FR-005 | FR-005 behavior, gate, or artifact rule |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Hooks are guardrails, not the source of truth; inactive projects must receive no workflow intervention.
- V0.5 hook helpers must be pure local guardrail/context builders. They read `.product-delivery/state.json` and artifact paths, but do not mutate Waygate or controller state.
- Resume context must include `stage`, `project_type`, optional `next_gate`, confirmation summary, and recorded skill gates when the project is active.
- Prompt context must include `current_stage`, `project_type`, and optional `next_gate` when the project is active.
- Pre-compaction checks must fail if active state is missing readable valid JSON or required durability fields.
- Stop guardrails must report missing required confirmations and missing required artifact files based on `project_type`.

## Data And Artifact Rules

- This version package implements runtime hook guardrail helpers in `src/product_delivery_agent/hooks.py`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Hook results use explicit fields: `active`, `silent`, `message`, `warnings`, `missing_items`, and `passed`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.5 runtime interfaces are `build_resume_context`, `build_prompt_context`, `check_pre_compaction`, and `check_stop_guardrail`.
- Public binding to a concrete Codex hook framework remains deferred until plugin packaging.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Scope changes after freeze return to version scope confirmation.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
