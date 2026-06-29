# V0.8 Test Coverage Audit - 02 Specification

| Field | Value |
| --- | --- |
| Version | V0.8 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.8 Test Coverage Audit. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add closure-ready coverage matrix semantics. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record coverage audit interfaces and state outputs. | CR-001 |


## Traceability

| Requirement | Specification Area |
| --- | --- |
| FR-001 | FR-001 behavior, gate, or artifact rule |
| FR-002 | FR-002 behavior, gate, or artifact rule |
| FR-003 | FR-003 behavior, gate, or artifact rule |
| FR-004 | FR-004 behavior, gate, or artifact rule |
| FR-005 | Continuous TC numbering |
| FR-006 | `FR/NFR/US/J/AC/TASK` traceability |
| FR-007 | Browser E2E obligation for UI paths |
| FR-008 | Supporting evidence classification |
| FR-009 | Test layer and semantic marker validation |

## Behavior Rules

- The workflow must not enter active product delivery mode unless the user explicitly starts it for the project.
- State and artifact records are preferred over chat memory whenever continuation or recovery is required.
- UI and non-UI branch gates are mutually exclusive and selected by project type.
- Handoff may not bypass required confirmation gates and test coverage audit obligations.
- Coverage matrix records must use continuous TC identifiers.
- Coverage matrix records must trace planned tests to `FR/NFR/US/J/AC/TASK`.
- UI user stories, user journeys, and user-visible exception paths must map to browser E2E evidence or explicit exemption.
- API, unit, contract, static, and document checks may support UI journeys but must not replace required browser E2E evidence.
- Coverage gate checks must inspect test layer fields and semantic markers.
- Runtime coverage audit must reject non-continuous TC ranges, missing trace anchors, missing semantic markers on critical rows, unexempted critical gaps, and missing inherited negative guards.
- Runtime coverage audit must preserve inherited UI prototype or non-UI behavior limitations.

## Data And Artifact Rules

- This version package implements coverage audit validation in `src/product_delivery_agent/coverage_audit.py` and workflow state recording through `ProductDeliveryWorkflow.record_test_coverage_audit`.
- Artifacts must remain reviewable Markdown or local files before any implementation handoff.
- Confirmation records must be durable enough for compaction and resume recovery in later automation.
- Coverage matrix artifacts must include TC range, traceability anchors, test layer, evidence type, semantic marker, and exemption status.
- Matrix outputs must be reusable by V0.9 handoff and V0.10 formal closure.
- The audit artifact is written to `.product-delivery/artifacts/test-coverage-audit.md`.
- Audit state is stored under `test_coverage_audit`, `handoff_inputs`, and `closure_inputs`.

## Interface And Command Semantics

- `start` means explicit project-level activation.
- `stop` means exit workflow intervention while preserving reviewable artifacts.
- `status`, `pause`, and `resume` are planned local workflow commands starting in V0.3.
- V0.8 runtime interfaces are `build_coverage_audit`, `render_coverage_audit`, `CoverageAuditError`, and `ProductDeliveryWorkflow.record_test_coverage_audit`.
- Actual test command execution remains deferred to implementation verification and closure stages.

## Exception And Compatibility Rules

- Missing required confirmation blocks downstream transition.
- Missing critical coverage without exemption blocks Codex Goal handoff.
- Missing continuous TC range blocks closure readiness.
- Missing `FR/NFR/US/J/AC/TASK` traceability blocks handoff readiness.
- Missing browser E2E for active UI user stories, journeys, or visible exceptions blocks handoff unless explicitly exempted.
- Supporting evidence mislabeled as browser E2E blocks handoff readiness.
- Scope changes after freeze return to version scope confirmation.
- Existing `.product-delivery/` artifacts must not be silently discarded by future plugin upgrades.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Detailed field schemas and command contracts are deferred unless this version explicitly scopes them. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
