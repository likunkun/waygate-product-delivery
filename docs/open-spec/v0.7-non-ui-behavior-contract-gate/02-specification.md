# V0.7 Non-UI Behavior Contract Gate - 02 Specification

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
| REV-20260622-02 | 2026-06-22 | Codex | Add non-UI scenario taxonomy and closure input rules. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record non-UI behavior contract interfaces and state outputs. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | Non-UI scenario taxonomy |
| FR-005 | Behavior evidence and negative boundary inputs |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Non-UI behavior contract review must cover entry points, inputs and outputs, exceptions, recovery, permissions, long tasks, state transitions, and boundary conditions.
- Non-UI confirmation must identify downstream behavior evidence and negative boundary guard candidates.
- Runtime behavior contract recording must be rejected unless `project_type = non_ui`.
- Runtime validation must require contract name, entry points, inputs, outputs, behavior paths, negative boundary records, limitations, and all taxonomy entries.
- Runtime state must preserve accepted behavior limitations for V0.8 audit, V0.9 handoff, and V0.10 closure.

## Data And Artifact Rules

- This version package implements non-UI behavior contract validation in `src/product_delivery_agent/non_ui_behavior.py` and workflow state recording through `ProductDeliveryWorkflow.record_non_ui_behavior_contract`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Behavior contract records must preserve confirmed behavior paths, limitations, and negative boundary records.
- Negative boundary records must remain available for V0.8 audit, V0.9 handoff, and V0.10 closure.
- The contract artifact is written to `.product-delivery/artifacts/non-ui-behavior-contract.md`.
- Behavior contract state is stored under `non_ui_behavior_contract`, `downstream_inputs`, `behavior_contract_limitations`, `handoff_inputs`, and `closure_inputs`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.7 runtime interfaces are `validate_non_ui_behavior_contract`, `render_non_ui_behavior_contract`, `NON_UI_BEHAVIOR_TAXONOMY`, and `ProductDeliveryWorkflow.record_non_ui_behavior_contract`.
- Real API/service/CLI execution remains deferred to later audit and implementation verification stages.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing non-UI scenario taxonomy entries should block behavior contract confirmation unless explicitly exempted.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Missing negative boundary records should block closure readiness for non-UI projects unless explicitly exempted.
- Scope changes after freeze return to version scope confirmation.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
