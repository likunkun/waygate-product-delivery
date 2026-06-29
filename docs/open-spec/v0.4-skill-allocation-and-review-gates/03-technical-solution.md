# V0.4 Skill Allocation And Review Gates - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime skill gate module implementation. | CR-001 |


## Solution Boundary

This version implements the runtime solution boundary for `V0.4 - Skill Allocation And Review Gates`.
It does not implement external skill installation, dynamic discovery, plugin packaging, or hook execution.

## Modules And Responsibilities

- `src/product_delivery_agent/skill_gates.py`: stage-to-skill allocation, file-skill policy, gate validation, and result serialization.
- `ProductDeliveryWorkflow.record_skill_use`: persists passed gate results into workflow state.
- `tests/test_skill_gates.py`: verifies V0.4 runtime behavior.

## Key Flow

1. Caller asks `required_skills_for_stage(stage, file_paths=...)` for reviewable stage requirements.
2. Caller passes observed skills into `validate_skill_gate(stage, used_skills, file_paths=...)`.
3. Missing required skills produce a failed gate result.
4. `ProductDeliveryWorkflow.record_skill_use` rejects failed gates and records passed gate results into `state.json`.
5. File-specific skills are added only for matching `.pdf`, `.docx`, and `.pptx` paths.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Implement skill gates as explicit runtime policy instead of comments only. | Makes skill use reviewable and testable before plugin packaging. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| Missing required skill | Reject the skill gate before recording it. | Re-run the stage with required skill use. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | External skill installation and plugin API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
