# V0.6 UI Prototype Gate - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Add UI scenario taxonomy and closure input rules. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record UI prototype review interfaces and state outputs. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |
| FR-005 | UI scenario taxonomy |
| FR-006 | E2E and negative scope guard inputs |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- UI prototype review must cover roles, main paths, exceptions, recovery, permissions, long tasks, mobile, keyboard, and negative scope boundaries.
- UI prototype confirmation must identify downstream browser E2E and negative scope guard candidates.
- Runtime UI prototype review recording must be rejected unless `project_type = ui`.
- Runtime validation must require pages, states, journeys, limitations, browser E2E candidates, negative scope guard candidates, and all taxonomy entries.
- Runtime state must preserve prototype limitations for V0.8 audit, V0.9 handoff, and V0.10 closure.

## Data And Artifact Rules

- This version package implements UI prototype review validation in `src/product_delivery_agent/ui_prototype.py` and workflow state recording through `ProductDeliveryWorkflow.record_ui_prototype_review`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Prototype review records must preserve scenario taxonomy decisions and accepted limitations.
- Negative scope boundary records must remain available for V0.8 audit, V0.9 handoff, and V0.10 closure.
- The review artifact is written to `.product-delivery/artifacts/ui-prototype-review.md`.
- Prototype review state is stored under `ui_prototype_review`, `downstream_inputs`, `prototype_limitations`, `handoff_inputs`, and `closure_inputs`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.6 runtime interfaces are `validate_ui_prototype_review`, `render_ui_prototype_review`, `UI_PROTOTYPE_TAXONOMY`, and `ProductDeliveryWorkflow.record_ui_prototype_review`.
- Public browser E2E execution remains deferred to later audit and webapp verification stages.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Missing UI scenario taxonomy entries should block prototype confirmation unless explicitly exempted.
- Missing negative scope boundary notes should block closure readiness for UI projects unless explicitly exempted.
- Scope changes after freeze return to version scope confirmation.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
