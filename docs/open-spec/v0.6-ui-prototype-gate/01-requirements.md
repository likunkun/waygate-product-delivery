# V0.6 UI Prototype Gate - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.6 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.6 UI Prototype Gate. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add UI scenario taxonomy and closure input requirements. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record runtime UI prototype gate implementation and test evidence. | CR-001 |


## Business Goal

Provide local 1:1 HTML prototype confirmation for UI projects.

## Scope

### In Scope

- Apply only when project_type = ui.
- Generate or guide creation of a local HTML prototype.
- Cover key pages, states, and user journeys.
- Cover UI scenario taxonomy: roles, main paths, exceptions, recovery, permissions, long tasks, mobile, keyboard, and negative scope boundaries.
- Require user confirmation before test coverage audit.
- Carry prototype limitations into handoff.
- Produce downstream browser E2E and negative scope guard inputs.
- Implement UI-only prototype review validation and state recording in the local workflow.

### Out Of Scope

- Prototype gate for non-UI projects.
- Production UI implementation.
- Backend integration for prototype data.
- Browser automation for the prototype itself; browser E2E obligations are emitted for later audit and closure.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When project_type is ui, the workflow shall require a local 1:1 HTML prototype gate. | UI branch specification contains prototype gate. |
| FR-002 | P0 | When prototype review occurs, it shall cover key pages, states, and user journeys. | Prototype review requirements name pages, states, and journeys. |
| FR-003 | P0 | Before test coverage audit, the user shall confirm the UI prototype or request revision. | Gate rules block audit before prototype confirmation. |
| FR-004 | P1 | When handoff is generated, prototype limitations shall be carried forward. | Handoff includes prototype limitations. |
| FR-005 | P0 | When UI scenario review occurs, it shall cover roles, main paths, exceptions, recovery, permissions, long tasks, mobile, keyboard, and negative scope boundaries. | Prototype review records include the full UI scenario taxonomy. |
| FR-006 | P0 | When prototype review is confirmed, it shall produce inputs for browser E2E obligations and negative scope guard checks. | Downstream audit inputs identify E2E and scope guard candidates. |

Runtime acceptance:

- `ProductDeliveryWorkflow.record_ui_prototype_review(review)` is available only when `project_type = ui`.
- Missing UI scenario taxonomy entries block prototype review recording.
- Non-UI projects cannot enter the UI prototype gate.
- Prototype limitations are written into `prototype_limitations`, `handoff_inputs`, and `closure_inputs`.
- Browser E2E and negative scope guard candidates are written into `downstream_inputs`.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Fidelity | Prototype review must be sufficient to expose missing UI scenarios before implementation. | Review covers pages, states, journeys, and limitations. |
| NFR-002 | Branch isolation | Prototype gate must not run for non-UI projects. | project_type condition is explicit. |
| NFR-003 | Closure readiness | Prototype outputs must be traceable into later E2E and negative scope guard obligations. | Prototype review records link scenarios to audit inputs. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Feature Closure Inputs

- UI prototype review records must identify which user-visible paths require browser E2E evidence later.
- Negative scope boundary notes must identify future-version or out-of-scope capabilities that must remain absent.
- Prototype limitations must be carried into V0.8 coverage audit, V0.9 handoff, and V0.10 closure.

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
