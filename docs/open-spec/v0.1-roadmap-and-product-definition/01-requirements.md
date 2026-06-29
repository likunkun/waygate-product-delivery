# V0.1 Roadmap And Product Definition - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.1 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.1 Roadmap And Product Definition. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add explicit main-flow and required-gate requirement. | CR-001 |


## Business Goal

Complete the product shape, capability boundary, version route, and skill allocation for the Codex-native Product Delivery Agent Plugin.

## Scope

### In Scope

- Define the product as a Codex-native Agent Plugin.
- Define an explicit project-level start/stop activation switch.
- Define UI and non-UI project branches.
- Map the main flow from product idea to Codex Goal handoff.
- Map Waygate baseline skills to workflow stages.
- Produce roadmap and version planning only, without detailed implementation design.

### Out Of Scope

- Runtime plugin implementation.
- Detailed public interface design.
- Waygate state mutation.
- Hooks or validation script implementation.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When the roadmap is reviewed, the system documentation shall identify the product as a Codex-native Agent Plugin with dormant-by-default behavior. | ROADMAP.md states Codex-native plugin shape and dormant-by-default activation. |
| FR-002 | P0 | When a project enters product delivery mode, the roadmap shall require explicit project-level start and stop semantics. | ROADMAP.md names start/stop and the active/inactive boundary. |
| FR-003 | P0 | When project type is discussed, the roadmap shall distinguish UI and non-UI branches. | ROADMAP.md states UI uses local 1:1 HTML prototype and non-UI uses behavior contract confirmation. |
| FR-004 | P1 | When Waygate skills are referenced, the roadmap shall assign baseline skills to workflow stages. | ROADMAP.md includes a stage-to-skill allocation table. |
| FR-005 | P0 | When the product delivery flow is reviewed, the roadmap shall map the main path from product idea to Codex Goal handoff through required gates. | ROADMAP.md includes product blueprint, version scope, project-type gate, test coverage audit, and Codex Goal handoff. |

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Traceability | Every roadmap statement must map to a planned version section. | Manual review against ROADMAP.md. |
| NFR-002 | Scope control | V0.1 must not include implementation design or runtime automation details. | No public interfaces, schemas, or runtime code are specified in V0.1. |

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
