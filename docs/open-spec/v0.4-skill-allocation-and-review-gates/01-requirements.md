# V0.4 Skill Allocation And Review Gates - 01 Requirements

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
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime skill allocation and review gate implementation. | CR-001 |


## Business Goal

Explicitly include the Waygate README recommended skills in the workflow.

## Scope

### In Scope

- Assign Waygate baseline skills to workflow stages.
- Define review gates that require relevant skills.
- Document that file-specific skills only trigger when corresponding file types are involved.
- Implement a runtime skill gate registry and workflow state recording for passed skill gates.

### Out Of Scope

- Skill installation automation.
- External skill installation and discovery automation.
- Plugin packaging.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When the workflow starts, it shall require the agent startup skill policy to be visible in the skill allocation plan. | `required_skills_for_stage("agent_startup")` includes `superpowers:using-superpowers`. |
| FR-002 | P0 | When product blueprint or scope shaping occurs, brainstorming skill use shall be assigned. | Runtime skill gates map blueprint and scope stages to `superpowers:brainstorming`. |
| FR-003 | P0 | When test coverage audit occurs, test-strategy or testing-strategy shall be assigned. | Runtime skill gate accepts either `test-strategy` or `testing-strategy`. |
| FR-004 | P0 | When UI/Web/prototype work occurs, ui-ux-pro-max shall be assigned. | Runtime skill gate maps UI prototype confirmation to `ui-ux-pro-max`. |

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Process consistency | Every stage-level skill assignment must be explicit and reviewable. | `record_skill_use` writes passed skill gate records into local state. |
| NFR-002 | Scope discipline | Document-specific skills must not be invoked unless corresponding file types are involved. | File-specific skills are required only for `.pdf`, `.docx`, and `.pptx` inputs. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Risks And Assumptions

- Risk: scope drift into external skill installation. Mitigation: V0.4 only validates and records skill use; installation remains out of scope.
- Risk: branch rules become ambiguous. Mitigation: keep UI and non-UI confirmation gates mutually exclusive.
- Assumption: Codex Goal remains the first handoff target until a later version changes the roadmap.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | External skill discovery and installation remain deferred from this requirements package. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Additional implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
