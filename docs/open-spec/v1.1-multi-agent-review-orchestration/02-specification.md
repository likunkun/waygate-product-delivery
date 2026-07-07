# V1.1 Multi-Agent Review Orchestration - 02 Specification

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial specification for V1.1 multi-agent review orchestration. | CR-001 |
| REV-20260702-01 | 2026-07-02 | Codex | Expanded scenario acceptance trace so every TC-001..TC-026 has AC continuity before test coverage review. | CR-001 |

## Change Linkage

- Change Request: CR-001
- Requirements Source: `01-requirements.md`
- Confirmed Project Type: `non_ui`
- Scope Boundary: Product Delivery multi-agent review orchestration only
- Out Of Scope: Dashboard, external integration, independent Runtime API versioning

## FR Traceability

| FR | Specification Sections |
| --- | --- |
| FR-001 | Review Gate Identification; Reviewer Responsibilities |
| FR-002 | Prompt/Input Contract |
| FR-003 | Scenario Review Behavior |
| FR-004 | Test Coverage Review Behavior |
| FR-005 | Test Implementation Review Behavior |
| FR-006 | Non-Interchangeable Gate Rules |
| FR-007 | Review Artifact/Data Contract |
| FR-008 | Exception And Fail-Closed Semantics |
| FR-009 | Review Mode Semantics |
| FR-010 | Review Mode Semantics; User Acceptance |
| FR-011 | Exception And Fail-Closed Semantics |
| FR-012 | Compatibility Strategy |
| FR-013 | Branch Evidence Contract |
| FR-014 | Collection Coverage Rules |
| FR-015 | False-Positive Risk Rules |
| FR-016 | Non-UI Fail-Closed Gate Rules |
| FR-017 | Structured Artifact Authority |

## Review Gate Identification

The orchestration must identify the required review gate before accepting a review artifact.

Valid review types:

- `scenario`
- `test`
- `test_coverage`
- `test_implementation`

Authoritative split gates:

- `scenario` gates Open Spec freeze.
- `test_coverage` gates implementation handoff / authorization.
- `test_implementation` gates formal closure when implementation evidence is required.
- Legacy generic `test` may remain compatible where already required, but must not satisfy `scenario`, `test_coverage`, or `test_implementation`.

## Reviewer Responsibilities

Each review artifact must record reviewer coverage for the gate purpose.

Scenario review must cover:

- Product intent
- Scenario and journey completeness
- Negative boundaries

Test coverage review must cover:

- `US/J/SC/AC/TASK/TC` traceability
- Planned coverage gaps
- Missing executable assertions
- Collection item coverage
- False-positive risks

Test implementation review must cover:

- Actual test code paths
- Execution evidence paths
- Reviewed test IDs
- Verified action assertions
- False-positive implementation risks

## Prompt/Input Contract

Review orchestration must build feature-specific inputs. Static generic prompts are insufficient.

Common required inputs:

- Current feature slug
- Current Open Spec artifacts
- Scenario matrix
- Review type
- Required reviewer responsibilities
- Current gate purpose
- Existing Product Delivery state relevant to the gate

Non-UI branch inputs:

- Non-UI behavior contract
- Behavior evidence obligations
- Negative boundary records
- Accepted limitations
- Planned behavior or E2E obligations
- Executed evidence when reviewing implementation

UI-only inputs are out of scope for this package except compatibility wording. For UI projects, equivalent branch evidence is UI prototype evidence and browser E2E obligations.

## Scenario Journey And Acceptance Anchors

Scenario review and test coverage review must preserve stable `SC`, `US`, `J`, `AC`, `TASK`, and `TC` trace anchors. Natural-language journey text is not enough by itself.

Acceptance anchors are defined by the expected results of their mapped test cases. A test coverage review must fail if an `AC-V11-*` anchor is listed without a mapped `TC-*` expected result that can pass or fail.

| Scenario | User Story | Journey Anchor | Acceptance Anchors | Planned Test Anchors |
| --- | --- | --- | --- | --- |
| SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-001, AC-V11-002, AC-V11-003, AC-V11-004, AC-V11-013, AC-V11-014, AC-V11-024 | TC-001, TC-002, TC-003, TC-004, TC-013, TC-014, TC-024 |
| SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-005, AC-V11-006, AC-V11-007, AC-V11-017, AC-V11-018, AC-V11-023, AC-V11-024 | TC-005, TC-006, TC-007, TC-017, TC-018, TC-023, TC-024 |
| SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-008, AC-V11-009, AC-V11-019, AC-V11-023, AC-V11-024 | TC-008, TC-009, TC-019, TC-023, TC-024 |
| SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-010, AC-V11-011, AC-V11-012 | TC-010, TC-011, TC-012 |
| SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-015, AC-V11-021, AC-V11-022, AC-V11-025 | TC-015, TC-021, TC-022, TC-025 |
| SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-020, AC-V11-021, AC-V11-022, AC-V11-026 | TC-020, TC-021, TC-022, TC-026 |
| SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-023, AC-V11-024 | TC-023, TC-024 |
| SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-011, AC-V11-012, AC-V11-016, AC-V11-024, AC-V11-025, AC-V11-026 | TC-011, TC-012, TC-016, TC-024, TC-025, TC-026 |

## Behavior Specification

### Scenario Review Behavior

Before user-confirmed freeze, orchestration must require a `scenario` review artifact.

The review passes only when:

- Review type is exactly `scenario`.
- Required deliberation sections are present.
- Product intent, journeys, and negative boundaries are reviewed.
- `blocking_findings` is empty.
- Review mode is acceptable under Review Mode Semantics.

### Test Coverage Review Behavior

Before implementation handoff / authorization, orchestration must require a `test_coverage` review artifact.

The review passes only when:

- Review type is exactly `test_coverage`.
- `traceability_reviewed` includes `US`, `J`, `SC`, `AC`, `TASK`, and `TC`.
- `coverage_gaps` is empty.
- `title_overbreadth_findings` is empty.
- `missing_executable_assertions` is empty.
- `false_positive_risks` is empty.
- Collection coverage has required items, covered items, and item-level assertions.

For non-UI projects, coverage must use behavior evidence obligations rather than UI prototype obligations.

### Test Implementation Review Behavior

Before formal closure, orchestration must require `test_implementation` when implementation evidence is required.

The review passes only when:

- Review type is exactly `test_implementation`.
- `actual_test_code_paths` is non-empty.
- `execution_evidence_paths` is non-empty.
- `reviewed_test_ids` is non-empty.
- `verified_action_assertions` is non-empty.
- Each verified action assertion binds test ID, item ID, clicked/action entry, expected real surface or behavior, assertion target, and evidence path.
- `false_positive_risks` is empty.

## Structured Artifact Authority

The canonical structured multi-agent review artifact is the only artifact that can satisfy a multi-agent review gate.

Authoritative evidence requires:

- A state entry under `state["multi_agent_reviews"][review_type]`.
- A matching artifact path for the same `review_type`.
- Required deliberation fields from the Review Artifact/Data Contract.
- Valid review mode under Review Mode Semantics.
- Empty `blocking_findings` for accepted reviews.
- Gate-specific fields for `scenario`, `test_coverage`, or `test_implementation`.

The following are supporting evidence only and cannot satisfy a review gate by themselves:

- Chat summaries.
- Session logs.
- Open Spec summaries.
- `progress.md` or `task_plan.md` status text.
- Custom `*-pre-handoff-gate.json` or equivalent one-off artifacts.
- Status-only records that claim `passed`, `ready`, `closed`, or equivalent without the structured review artifact.

If supporting evidence conflicts with canonical structured review state or artifact validation, the gate fails closed.

## Non-UI Fail-Closed Gate Rules

For `project_type=non_ui`, Product Delivery must keep split review gates authoritative:

- Pre-freeze requires a passing `scenario` review.
- Pre-handoff requires a passing `test_coverage` review before implementation authorization.
- Pre-closure requires a passing `test_implementation` review after implementation/test evidence exists and before formal closure.

Non-UI behavior contract evidence is required branch evidence, but it does not replace split review artifacts.

The gatekeeper must block when:

- `test_coverage` is missing before handoff.
- `test_coverage` is replaced by legacy generic `test`, `scenario`, `test_implementation`, custom artifact, or prose summary.
- `test_implementation` is missing before closure after implementation evidence exists.
- `test_implementation` is replaced by legacy generic `test`, `scenario`, `test_coverage`, custom artifact, or prose summary.
- Any review artifact has unresolved blocking findings or invalid review mode.

## Non-Interchangeable Gate Rules

- `scenario` cannot satisfy `test_coverage` or `test_implementation`.
- `test_coverage` cannot satisfy `scenario` or `test_implementation`.
- `test_implementation` cannot satisfy `scenario` or `test_coverage`.
- Generic `test` cannot replace split `test_coverage` or `test_implementation`.

## Review Artifact/Data Contract

Required common fields:

- `review_id`
- `review_type`
- `status`
- `review_mode`
- `reviewers`
- `artifact_version`
- `independent_positions`
- `cross_challenges`
- `revisions`
- `final_adjudication`
- `conclusions`
- `accepted_suggestions`
- `rejected_suggestions`
- `unresolved_questions`
- `blocking_findings`

Required persisted state semantics:

- Artifact path remains `.product-delivery/artifacts/multi-agent-<review_type>-review.md`.
- State remains under `state["multi_agent_reviews"][review_type]`.
- Accepted state records preserve `status`, `artifact`, `review_id`, `artifact_version`, and `review_mode`.

Additional `test_coverage` fields:

- `traceability_reviewed`
- `coverage_gaps`
- `title_overbreadth_findings`
- `missing_executable_assertions`
- `false_positive_risks`
- `collection_coverage`

Additional `test_implementation` fields:

- `actual_test_code_paths`
- `execution_evidence_paths`
- `reviewed_test_ids`
- `verified_action_assertions`
- `false_positive_risks`
- `supporting_evidence_only`

## Review Mode Semantics

Valid modes:

- `spawned_subagents`
- `role_simulation`
- `blocked_with_reason`

Rules:

- Missing `review_mode` defaults to `spawned_subagents` only when reading legacy records for compatibility.
- New V1.1 accepted review artifacts must explicitly record `review_mode`.
- `spawned_subagents` is strong evidence and the default policy.
- `role_simulation` is degraded evidence.
- `role_simulation` requires explicit user acceptance and a workflow policy that allows degradation.
- `blocked_with_reason` always fails closed and must include a visible reason.
- Unknown review modes are invalid.

## Exception And Fail-Closed Semantics

The gate must fail closed when:

- Required fields are missing or empty.
- `review_type` does not match the required gate.
- `status` is not `passed`.
- `blocking_findings` is non-empty.
- `review_mode` is unknown.
- `role_simulation` lacks explicit user acceptance or a workflow policy that allows degradation.
- `blocked_with_reason` is used.
- Required traceability targets are missing.
- Collection items lack item-level coverage or assertions.
- Actual test paths or execution evidence paths are missing.
- False-positive risks remain unresolved.

False-positive risk terms include marker-only, function-name-only, static-panel-only, and first-button-only assertions.

## Compatibility Strategy

V1.1 must preserve existing Product Delivery state and artifact semantics.

Compatibility rules:

- Existing review IDs, artifact versions, artifact paths, statuses, and review modes remain readable.
- Legacy generic `test` review remains interpretable where existing gates require it.
- Legacy `test` review does not satisfy V1.1 split gates.
- Missing `review_mode` is interpreted as `spawned_subagents` for backward-compatible read semantics.
- Missing `review_mode` is not valid for newly accepted V1.1 structured review artifacts.
- Existing records may fail only for documented gate reasons, not because of silent schema reinterpretation.

## Acceptance Mapping

| Requirement | Acceptance Mapping |
| --- | --- |
| FR-001 | Each gate validates exact review type and responsibility set. |
| FR-002 | Review input references current feature artifacts and branch evidence. |
| FR-003 | Scenario review blocks freeze while blockers remain. |
| FR-004 | Test coverage review blocks handoff when traceability or coverage is missing. |
| FR-005 | Test implementation review blocks closure without real code/evidence assertions. |
| FR-006 | Gate validation rejects substituted review types. |
| FR-007 | Artifact validation rejects missing deliberation sections. |
| FR-008 | Non-empty blocking findings fail closed. |
| FR-009 | Missing mode defaults to `spawned_subagents` only for legacy compatibility reads; new V1.1 accepted artifacts explicitly record `review_mode`. |
| FR-010 | `role_simulation` requires explicit accepted degradation and a workflow policy that allows degradation; it fails under `spawned_subagents_required`. |
| FR-011 | `blocked_with_reason` always fails. |
| FR-012 | Existing review state fields remain interpretable. |
| FR-013 | Non-UI uses behavior contract/evidence; UI uses prototype/browser evidence. |
| FR-014 | Collection coverage requires item-level assertions. |
| FR-015 | False-positive assertion patterns remain blocking risks. |
| FR-016 | Non-UI pre-handoff and pre-closure gates block until authoritative split review artifacts pass. |
| FR-017 | Summary-only, status-only, and custom-only claims are supporting evidence and cannot satisfy structured review gates. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No specification blocker remains. | Proceed |
| Assumption | Exact runtime entrypoint names are deferred. | Solution stage must bind orchestration to concrete methods without creating standalone API versioning. | Carry forward |
| Assumption | This feature package is `project_type=non_ui`. | Specification emphasizes behavior contract and behavior evidence inputs. | Confirmed |
| Nice-to-know | Long-term fate of legacy generic `test` review. | Does not block V1.1 because compatibility is preserved while split gates remain authoritative. | Track |
