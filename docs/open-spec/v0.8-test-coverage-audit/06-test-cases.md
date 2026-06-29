# V0.8 Test Coverage Audit - 06 Test Cases

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
| REV-20260622-02 | 2026-06-22 | Codex | Add continuous TC matrix and E2E evidence checks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add closure-ready matrix fields and blocking negative coverage tests. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Add inherited limitation, matrix range, latest test case, and guard-record checks. | CR-001 |
| REV-20260622-05 | 2026-06-22 | Codex | Record V0.8 coverage audit unit tests and execution evidence. | CR-001 |


## Test Strategy

Current tests include runtime unit tests for the V0.8 coverage audit gate plus document-level traceability checks.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V008-001 | Unit test | Coverage mapping | Run `test_ui_audit_accepts_browser_e2e_and_supporting_evidence` and `test_non_ui_audit_accepts_behavior_evidence`. | Audit maps rows into a coverage matrix with obligations; FR-001 is covered. |
| TC-V008-002 | Unit test | UI browser E2E | Run `test_ui_audit_accepts_browser_e2e_and_supporting_evidence`. | UI browser E2E obligations are accepted when backed by browser E2E rows; FR-002 and FR-007 are covered. |
| TC-V008-003 | Unit test | Non-UI behavior evidence | Run `test_non_ui_audit_accepts_behavior_evidence`. | Non-UI behavior paths are accepted when backed by API/service/CLI evidence rows; FR-003 is covered. |
| TC-V008-004 | Unit test | Blocking behavior | Run `test_unexempted_critical_gap_blocks_audit`. | Critical coverage gaps block audit when not exempted; FR-004 is covered. |
| TC-V008-005 | Unit test | Continuous TC range | Run `test_non_continuous_tc_range_blocks_audit`. | Non-continuous TC ranges are rejected; FR-005 is covered. |
| TC-V008-006 | Unit test | Traceability | Run `test_missing_trace_anchor_blocks_audit`. | Missing `FR/NFR/US/J/AC/TASK` anchors are rejected; FR-006 is covered. |
| TC-V008-007 | Unit test | Supporting evidence | Run `test_ui_audit_accepts_browser_e2e_and_supporting_evidence`. | Supporting evidence can coexist with required browser E2E; FR-008 is covered. |
| TC-V008-008 | Unit test | Semantic markers | Run `test_missing_semantic_marker_blocks_high_risk_row`. | Gate checks inspect semantic marker fields; FR-009 is covered. |
| TC-V008-009 | Unit test | Non-continuous TC range | Run `test_non_continuous_tc_range_blocks_audit`. | Gate rejects skipped TC identifiers and blocks handoff under FR-005. |
| TC-V008-010 | Unit test | Missing trace anchors | Run `test_missing_trace_anchor_blocks_audit`. | Gate rejects rows without required anchors under FR-006 and NFR-001. |
| TC-V008-011 | Unit test | UI E2E missing | Run `test_ui_supporting_evidence_cannot_replace_browser_e2e`. | Gate blocks missing browser E2E for inherited UI obligations under FR-002, FR-004, FR-007, and NFR-002. |
| TC-V008-012 | Unit test | Supporting evidence misclassified | Run `test_ui_supporting_evidence_cannot_replace_browser_e2e`. | Supporting evidence cannot replace browser E2E under FR-008. |
| TC-V008-013 | Unit test | Missing semantic marker | Run `test_missing_semantic_marker_blocks_high_risk_row`. | Gate rejects shallow coverage under FR-009 and NFR-003. |
| TC-V008-014 | Unit test | Unexempted critical gap | Run `test_unexempted_critical_gap_blocks_audit`. | Gate blocks critical missing coverage under FR-004 and NFR-001. |
| TC-V008-015 | Unit test | Closure range fields | Run `test_ui_audit_accepts_browser_e2e_and_supporting_evidence`. | Audit records `matrix_range`, `latest_test_case`, and row-level status for V0.10 closure input. |
| TC-V008-016 | Unit test | Inherited limitations | Run `test_inherited_limitations_are_preserved_for_closure`. | Accepted limitations from V0.6/V0.7 are preserved for closure inputs. |
| TC-V008-017 | Unit test | Missing inherited guard records | Run `test_missing_inherited_negative_guard_record_blocks_audit`. | Gate blocks audit when inherited negative guard records are omitted. |

## Coverage Matrix

| Requirement | NFR | US/J/AC Anchors | TASK | TC | Test Layer | Evidence Type | Semantic Marker | Coverage Status | Exemption Status | Closure Fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-001 | NFR-001 | `US-*`, `J-*`, `AC-*` present | TASK-001 | TC-V008-001, TC-V008-016 | Audit matrix | Coverage mapping | `traceability-map` | Required | Required or explicit | Inherited limitations captured |
| FR-002 | NFR-002 | UI `US-*`, `J-*`, visible exception `AC-*` | TASK-002 | TC-V008-002 | Browser E2E | Browser journey evidence | `ui-browser-e2e-required` | Covered or exempted | Required or explicit | E2E obligations |
| FR-003 | NFR-002 | Non-UI `US-*`, `J-*`, behavior `AC-*` | TASK-003 | TC-V008-003 | API/service/CLI E2E | Behavior evidence | `non-ui-behavior-evidence` | Covered or exempted | Required or explicit | Behavior evidence obligations |
| FR-004 | NFR-001 | Critical `US-*`, `J-*`, `AC-*` | TASK-004 | TC-V008-004, TC-V008-014, TC-V008-016, TC-V008-017 | Gate check | Blocking decision | `critical-gap-blocks-handoff` | Covered, missing, or exempted | Required | Handoff blocking decision and inherited guards |
| FR-005 | NFR-003 | Matrix range | TASK-005 | TC-V008-005, TC-V008-009, TC-V008-015 | Gate check | ID range validation | `continuous-tc-range` | Required | Not applicable | `matrix_range`, `latest_test_case` |
| FR-006 | NFR-001, NFR-003 | `FR/NFR/US/J/AC/TASK` | TASK-006 | TC-V008-006, TC-V008-010, TC-V008-015, TC-V008-017 | Gate check | Traceability validation | `full-anchor-required` | Required | Not applicable | Full anchors and guard records |
| FR-007 | NFR-002 | UI `US-*`, `J-*`, visible exception `AC-*` | TASK-007 | TC-V008-002, TC-V008-011 | Browser E2E | Browser journey evidence | `ui-visible-path-e2e` | Covered or exempted | Required or explicit | Browser E2E list |
| FR-008 | NFR-002 | UI `US-*`, `J-*` with supporting tests | TASK-007 | TC-V008-007, TC-V008-012 | Supporting evidence | API/unit/static/doc scan | `supporting-evidence-only` | Supporting only | Not a replacement | Supporting evidence list |
| FR-009 | NFR-003 | High-risk `US-*`, `J-*`, `AC-*` | TASK-008 | TC-V008-008, TC-V008-013 | Gate check | Semantic marker validation | `semantic-marker-required` | Required | Required | High-risk marker list |

## Matrix Rules

- Continuous range: `TC-V008-001..TC-V008-017`.
- Required traceability anchors: `FR/NFR/US/J/AC/TASK`.
- Required validation fields: test layer, evidence type, semantic marker, coverage status, exemption status, `latest_test_case`, and `matrix_range`.
- Browser E2E is mandatory for active UI user stories, journeys, and user-visible exceptions unless explicitly exempted.
- API, unit, contract, static, and document checks are supporting evidence for UI journeys and cannot replace browser E2E.
- Gate checks must inspect the layer and semantic marker fields; ID or title text alone is insufficient coverage evidence.
- Any unexempted critical gap blocks handoff.
- Accepted limitations and negative scope or boundary guard records inherited from V0.6/V0.7 must be represented as audit constraints, exemptions, closure inputs, or blocking gaps.

## Execution Record

- Current execution: `PYTHONPATH=src python3 -m unittest tests/test_coverage_audit.py`.
- Result: PASS, 9 tests ran in 0.016s.
- Current full-suite execution: `PYTHONPATH=src python3 -m unittest discover -s tests`, PASS, 69 tests ran in 0.112s.
- Evidence: `src/product_delivery_agent/coverage_audit.py`, `src/product_delivery_agent/workflow.py`, and `tests/test_coverage_audit.py`.
- Future evidence: actual browser/API/service/CLI command output when implementation verification and closure are in scope.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Executable tests are deferred until implementation artifacts exist. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
