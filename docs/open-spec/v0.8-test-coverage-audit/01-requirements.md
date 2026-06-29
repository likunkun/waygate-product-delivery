# V0.8 Test Coverage Audit - 01 Requirements

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
| REV-20260622-02 | 2026-06-22 | Codex | Add closure-ready coverage matrix and E2E evidence rules. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record runtime coverage audit implementation and test evidence. | CR-001 |


## Business Goal

Confirm test obligations before implementation handoff.

## Scope

### In Scope

- Map user stories, journeys, failure paths, acceptance criteria, and planned tests.
- Require continuous `TC-*` numbering and traceability to `FR/NFR/US/J/AC/TASK`.
- For UI projects, check browser E2E coverage or explicit exemptions.
- Treat API, unit, static, contract, and document checks as supporting evidence for UI journeys, not browser E2E replacements.
- For non-UI projects, check API, service, or CLI E2E coverage or explicit exemptions.
- Require gate checks to inspect test layer fields and semantic markers, not only IDs or titles.
- Block handoff when critical coverage is missing and not exempted.
- Implement runtime coverage audit validation and state recording for UI and non-UI project branches.

### Out Of Scope

- Executing tests.
- Generating implementation code.
- Accepting handoff with unreviewed critical gaps.
- Running browser/API/service/CLI commands; V0.8 validates obligations and evidence classification.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When test coverage audit runs, it shall map user stories, journeys, failure paths, acceptance criteria, and planned tests. | Audit document includes a coverage matrix. |
| FR-002 | P0 | When project_type is ui, the audit shall check browser E2E coverage or explicit exemptions for critical journeys. | UI audit requirements distinguish browser E2E. |
| FR-003 | P0 | When project_type is non_ui, the audit shall check API, service, or CLI E2E coverage or explicit exemptions. | Non-UI audit requirements distinguish API/service/CLI E2E. |
| FR-004 | P0 | When critical coverage is missing and not exempted, handoff shall be blocked. | Audit gate rules block handoff on unexempted critical gaps. |
| FR-005 | P0 | When coverage matrix is created, TC identifiers shall be continuous and shall not skip numbers. | Matrix includes a continuous `TC-*` range. |
| FR-006 | P0 | When coverage matrix is created, it shall trace planned tests to `FR/NFR/US/J/AC/TASK`. | Matrix columns or equivalent records include those anchors. |
| FR-007 | P0 | When UI user stories, user journeys, or user-visible exceptions are active, each shall map to browser E2E evidence or an explicit exemption. | UI audit blocks on missing browser E2E for active obligations. |
| FR-008 | P0 | When non-browser tests are present for UI journeys, they shall be classified as supporting evidence and not as browser E2E replacements. | Audit distinguishes supporting evidence from required E2E. |
| FR-009 | P0 | When gate checks evaluate coverage, they shall inspect test layer fields and semantic markers rather than relying only on IDs or titles. | Gate rules require layer and semantic marker validation. |

Runtime acceptance:

- `ProductDeliveryWorkflow.record_test_coverage_audit(rows, negative_guard_records=...)` validates closure-ready coverage rows.
- UI projects require browser E2E rows for inherited UI obligations or explicit exemptions.
- Non-UI projects require API/service/CLI behavior evidence rows for inherited behavior obligations or explicit exemptions.
- Continuous `TC-V008-*` ranges, trace anchors, semantic markers, critical gap status, and inherited negative guard records are enforced.
- `matrix_range`, `latest_test_case`, inherited limitations, and obligation lists are written into state for V0.9 handoff and V0.10 closure.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Auditability | Coverage decisions and exemptions must be visible in artifacts. | Audit record includes covered/missing/exempted status. |
| NFR-002 | Evidence readiness | Handoff must carry enough verification obligations for implementation Codex. | Audit feeds handoff verification requirements. |
| NFR-003 | Closure readiness | Coverage matrix must be usable by V0.10 formal closure. | Matrix carries TC range, E2E coverage, exemptions, and semantic marker obligations. |

## Branch And Gate Requirements

- UI projects use local 1:1 HTML prototype confirmation only when `project_type = ui`.
- Non-UI projects use behavior contract confirmation only when `project_type = non_ui`.
- All projects must still pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Plugin behavior remains dormant until explicit project-level `start` and exits intervention after `stop`.

## Coverage Matrix Rules

- TC identifiers must be continuous and version-scoped.
- Matrix entries must trace to `FR/NFR/US/J/AC/TASK`.
- UI user stories, user journeys, and user-visible exception paths require browser E2E or explicit exemption.
- API, unit, contract, static, and document checks are supporting evidence for UI journeys.
- Gate checks must inspect test layer fields and semantic markers, not just test IDs or titles.
- Negative scope guard obligations from V0.6 and V0.7 must remain visible for V0.9 handoff and V0.10 closure.

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
