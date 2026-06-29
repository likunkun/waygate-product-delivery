# V0.2 Artifact And State Protocol - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.2 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.2 Artifact And State Protocol. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add runtime helper implementation scope for artifact/state protocol. | CR-001 |


## Business Goal

Define the local state and artifact protocol the plugin will use.

## Scope

### In Scope

- Define the .product-delivery/ workspace.
- Define state.json responsibilities for stage, project type, confirmation points, and artifact paths.
- Define templates for product brief, version scope, UI prototype review, non-UI behavior contract, test coverage audit, and handoff.
- Define that state files take precedence over chat context.
- Implement a minimal local helper library for workspace initialization, state loading, and state writing.

### Out Of Scope

- Full workflow command implementation.
- Detailed public JSON schema beyond the runtime fields needed by V0.2 tests.
- Hooks implementation.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When a product delivery project is initialized, the protocol shall reserve a .product-delivery/ workspace for local artifacts. | `initialize_workspace` creates `.product-delivery/`, `state.json`, `templates/`, and `artifacts/`. |
| FR-002 | P0 | When long sessions are resumed, state files shall be treated as authoritative over chat context. | `load_state` prefers disk `state.json` over fallback state. |
| FR-003 | P0 | When project state is recorded, state.json responsibilities shall include stage, project type, confirmation points, and artifact paths. | Unit tests verify the runtime state responsibilities. |
| FR-004 | P1 | When templates are defined, each core artifact type shall have an explicit template responsibility. | Runtime template creation includes product brief, version scope, prototype review, behavior contract, test coverage audit, and handoff. |

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Recoverability | A future workflow must be recoverable from local artifacts after compaction or resume. | Unit tests verify disk state precedence and JSON persistence. |
| NFR-002 | Auditability | Every confirmation point must have a durable artifact path or state responsibility. | Unit tests verify confirmation points and artifact paths. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Risks And Assumptions

- Risk: scope drift from future workflow implementation details. Mitigation: keep V0.2 limited to artifact/state helpers.
- Risk: branch rules become ambiguous. Mitigation: keep UI and non-UI confirmation gates mutually exclusive.
- Assumption: Codex Goal remains the first handoff target until a later version changes the roadmap.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Full workflow implementation details are intentionally deferred from this requirements package. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Additional implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
