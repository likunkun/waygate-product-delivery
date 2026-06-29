# V0.3 Local Skill Workflow Prototype - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.3 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.3 Local Skill Workflow Prototype. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime workflow prototype implementation scope. | CR-001 |


## Business Goal

Validate the product delivery workflow with a repo or local skill before packaging a plugin.

## Scope

### In Scope

- Support start, status, pause, resume, and stop.
- Guide the user through product blueprint, version scope, and project type selection.
- Route UI projects into prototype confirmation.
- Route non-UI projects into behavior contract confirmation.
- Generate a test coverage audit and Codex Goal handoff draft.
- Implement a local Python workflow prototype using the V0.2 artifact/state protocol.

### Out Of Scope

- Installable Codex plugin packaging.
- Final hooks implementation.
- Direct Waygate integration.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When a user invokes start, the local skill workflow shall enter product delivery mode for the current project. | `ProductDeliveryWorkflow.start` activates only the current project state. |
| FR-002 | P0 | When a user invokes status, pause, resume, or stop, the workflow shall preserve and report lifecycle state. | Unit tests verify lifecycle state transitions and artifact retention. |
| FR-003 | P0 | When project type is selected as UI, the workflow shall route to prototype confirmation. | `select_project_type("ui")` sets `next_gate=ui_prototype_review`. |
| FR-004 | P0 | When project type is selected as non-UI, the workflow shall route to behavior contract confirmation. | `select_project_type("non_ui")` sets `next_gate=non_ui_behavior_contract`. |
| FR-005 | P1 | When confirmation gates pass, the workflow shall prepare test coverage audit and Codex Goal handoff draft. | `prepare_audit_and_handoff_drafts` writes draft audit and handoff artifacts after required confirmations. |

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Continuity | The local skill prototype must not depend on chat-only memory for current stage. | Unit tests verify disk state wins over fallback chat-context state. |
| NFR-002 | Non-interference | Stop must exit intervention while preserving artifacts. | Unit tests verify `stop` disables intervention and preserves artifact files. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Risks And Assumptions

- Risk: scope drift from later plugin implementation details. Mitigation: keep V0.3 limited to the local workflow prototype.
- Risk: branch rules become ambiguous. Mitigation: keep UI and non-UI confirmation gates mutually exclusive.
- Assumption: Codex Goal remains the first handoff target until a later version changes the roadmap.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Plugin packaging and hooks implementation details are intentionally deferred from this requirements package. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Additional implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
