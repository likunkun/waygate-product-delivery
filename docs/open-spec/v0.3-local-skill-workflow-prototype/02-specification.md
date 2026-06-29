# V0.3 Local Skill Workflow Prototype - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Record implemented workflow command semantics and branch routing. | CR-001 |


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
- `start` activates the workflow, clears paused state, enables intervention, and moves to `product_blueprint`.
- `pause` keeps the workflow active but disables intervention.
- `resume` keeps the workflow active and re-enables intervention from disk state.
- `stop` disables active and intervention state while preserving artifacts.
- `prepare_audit_and_handoff_drafts` blocks until product brief, version scope, and the branch-specific confirmation are complete.

## Data And Artifact Rules

- This version package implements local workflow state transitions on top of the V0.2 artifact protocol.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Draft audit and handoff artifacts are written under `.product-delivery/artifacts/`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are implemented as local workflow prototype methods.
- V0.3 runtime interface: `ProductDeliveryWorkflow` in `src/product_delivery_agent/workflow.py`.

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
| Assumption | Detailed CLI/plugin command contracts are deferred unless a later version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
