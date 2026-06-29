# V0.8 Test Coverage Audit - 03 Technical Solution

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
| REV-20260622-02 | 2026-06-22 | Codex | Add matrix validator and semantic marker concepts. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Record coverage audit module and workflow integration. | CR-001 |


## Solution Boundary

This version package implements `V0.8 - Test Coverage Audit` as a runtime workflow increment.
It validates coverage obligations and evidence classification, but does not execute browser, API, service, or CLI tests.

## Modules And Responsibilities

- `ProductDeliveryWorkflow.record_test_coverage_audit`: workflow entrypoint for coverage audit recording.
- `build_coverage_audit`: validates matrix rows, project-specific obligations, inherited guards, and closure-ready fields.
- `render_coverage_audit`: renders the local Markdown audit artifact.
- `CoverageAuditError`: blocks audit completion on coverage gate failures.
- TC continuity checker for `TC-V008-*`.
- Traceability checker for `FR/NFR/US/J/AC/TASK`.
- Test layer and semantic marker checker.
- Supporting evidence classifier and handoff blocker.

## Key Flow

1. Read project type and downstream obligations from V0.6 or V0.7 state.
2. Validate a continuous `TC-V008-*` range and trace each row to `FR/NFR/US/J/AC/TASK`.
3. Classify every TC by layer, evidence type, coverage status, exemption status, and semantic marker.
4. For UI projects, require browser E2E for inherited UI obligations unless explicitly exempted.
5. For non-UI projects, require API/service/CLI behavior evidence for inherited non-UI obligations unless explicitly exempted.
6. Check inherited negative guard records from V0.6 or V0.7.
7. Write audit state and artifact only when all gate checks pass.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-005 | Require continuous TC range. | Allows V0.10 closure to record `latest_test_case` and `matrix_range`. |
| ADR-006 | Treat browser E2E as mandatory for active UI journeys unless exempted. | Prevents API/static evidence from masking broken user-visible paths. |
| ADR-007 | Require semantic markers for high-risk paths. | Prevents tests from only mentioning IDs or titles without covering behavior. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |
| Title-only coverage | Require layer fields and semantic markers. | Reopen coverage audit. |
| Shallow UI evidence | Classify API/unit/static as supporting evidence. | Require browser E2E or exemption. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation-specific architecture diagrams and API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
