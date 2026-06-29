# V0.4 Skill Allocation And Review Gates - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime skill gate behavior and state recording. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Skill allocation is a workflow requirement: stages must name the corresponding Waygate baseline skills.
- Runtime skill gates must reject missing required skills.
- Test coverage audit must accept either `test-strategy` or `testing-strategy`.
- File-specific skills must be required only when matching `.pdf`, `.docx`, or `.pptx` files are present.
- Passed skill gate records must be written into local workflow state for review.

## Data And Artifact Rules

- This version package implements runtime skill allocation and review gate helpers on top of the V0.3 workflow prototype.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Skill records are stored in `state.json` under `skill_records`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.4 runtime interfaces are `required_skills_for_stage`, `validate_skill_gate`, and `ProductDeliveryWorkflow.record_skill_use`.
- External skill installation and discovery are deferred.

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
| Assumption | External skill discovery and installation contracts are deferred unless a later version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
