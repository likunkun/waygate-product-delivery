# V0.7 Non-UI Behavior Contract Gate - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.7 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.7 Non-UI Behavior Contract Gate. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add non-UI scenario taxonomy and closure input requirements. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record runtime non-UI behavior contract implementation and test evidence. | CR-001 |


## Business Goal

Provide a behavior confirmation gate for non-UI projects.

## Scope

### In Scope

- Apply only when project_type = non_ui.
- Define API, CLI, service, or background job entry points.
- Define input/output contracts, error paths, state transitions, and boundaries.
- Cover non-UI scenario taxonomy: entry points, inputs and outputs, exceptions, recovery, permissions, long tasks, state transitions, and boundary conditions.
- Require user confirmation before test coverage audit.
- Produce traceable behavior paths and negative boundary records for later audit, handoff, and closure.
- Implement non-UI behavior contract validation and state recording in the local workflow.

### Out Of Scope

- HTML prototype generation for non-UI projects.
- Production API implementation.
- Waygate verifier execution.
- Real API, CLI, service, or background job execution.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When project_type is non_ui, the workflow shall require behavior contract confirmation. | Non-UI branch specification contains behavior contract gate. |
| FR-002 | P0 | When behavior contract is authored, it shall define entry points, input/output contracts, error paths, state transitions, and boundaries. | Behavior contract requirements include these elements. |
| FR-003 | P0 | Before test coverage audit, the user shall confirm the behavior contract. | Gate rules block audit before behavior contract confirmation. |
| FR-004 | P0 | When non-UI scenario review occurs, it shall cover entry points, inputs and outputs, exceptions, recovery, permissions, long tasks, state transitions, and boundary conditions. | Behavior contract records include the full non-UI scenario taxonomy. |
| FR-005 | P0 | When behavior contract is confirmed, it shall produce traceable behavior paths and negative boundary records for later coverage audit, handoff, and closure. | Downstream audit inputs identify behavior evidence and boundary guard candidates. |

Runtime acceptance:

- `ProductDeliveryWorkflow.record_non_ui_behavior_contract(contract)` is available only when `project_type = non_ui`.
- Missing non-UI scenario taxonomy entries block behavior contract recording.
- UI projects cannot enter the non-UI behavior contract gate.
- Accepted behavior limitations are written into `behavior_contract_limitations`, `handoff_inputs`, and `closure_inputs`.
- Behavior evidence and negative boundary candidates are written into `downstream_inputs`.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Behavior clarity | Non-UI product intent must be reviewable without a visual prototype. | Behavior contract replaces prototype review. |
| NFR-002 | Branch isolation | Behavior contract gate must not replace UI prototype gate for UI projects. | project_type condition is explicit. |
| NFR-003 | Closure readiness | Non-UI behavior contract outputs must be traceable into later behavior evidence and negative boundary obligations. | Behavior records link paths to audit and closure inputs. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Feature Closure Inputs

- Non-UI behavior contracts must identify which behavior paths require API/service/CLI E2E or equivalent evidence later.
- Negative boundary records must identify unsupported, future-version, or out-of-scope behavior that must remain absent.
- Confirmed behavior paths and accepted limitations must be carried into V0.8 coverage audit, V0.9 handoff, and V0.10 closure.

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
