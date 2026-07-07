# V1.1 Multi-Agent Review Orchestration - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft / Not Run |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial testing-stage test case design. Implementation has not started. | CR-001 |
| REV-20260702-01 | 2026-07-02 | Codex | Added per-TC trace/evidence matrix and aligned non-UI planned evidence layers before test coverage re-review. | CR-001 |

## Change Linkage

- Change Request: CR-001
- Feature: `v1.1-multi-agent-review-orchestration`
- Requirements Source: `01-requirements.md`
- Specification Source: `02-specification.md`
- Development Plan Source: `05-development-plan.md`
- Test Strategy: Python `unittest` runtime behavior tests first; packaging/validator smoke for release verification; no browser E2E because this is not a UI project.
- Execution Status: Not Run - implementation not started

## Coverage Summary

| Coverage Area | Test Cases |
| --- | --- |
| FR-001..FR-017 | TC-001..TC-026 |
| TASK-001 | TC-001, TC-002, TC-003, TC-012, TC-016 |
| TASK-002 | TC-004..TC-013, TC-017..TC-019, TC-022 |
| TASK-003 | TC-003, TC-008, TC-010, TC-014, TC-020 |
| TASK-004 | TC-010, TC-013, TC-014, TC-015 |
| TASK-005 | TC-004, TC-006, TC-007, TC-009, TC-011, TC-012, TC-018, TC-019, TC-022, TC-023, TC-024, TC-026 |
| TASK-006 | TC-021, TC-022, TC-024, TC-025, TC-026 |
| TASK-007 | TC-001..TC-026 |

## Scenario Journey Acceptance Trace

Each `AC-V11-*` anchor is defined by the Expected Result of its mapped `TC-*` row. A coverage review must reject an acceptance anchor that is listed in this table but has no mapped executable expected result.

| Scenario | User Story | Journey Anchor | Acceptance Anchors | Planned Tests |
| --- | --- | --- | --- | --- |
| SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-001, AC-V11-002, AC-V11-003, AC-V11-004, AC-V11-013, AC-V11-014, AC-V11-024 | TC-001, TC-002, TC-003, TC-004, TC-013, TC-014, TC-024 |
| SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-005, AC-V11-006, AC-V11-007, AC-V11-017, AC-V11-018, AC-V11-023, AC-V11-024 | TC-005, TC-006, TC-007, TC-017, TC-018, TC-023, TC-024 |
| SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-008, AC-V11-009, AC-V11-019, AC-V11-023, AC-V11-024 | TC-008, TC-009, TC-019, TC-023, TC-024 |
| SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-010, AC-V11-011, AC-V11-012 | TC-010, TC-011, TC-012 |
| SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-015, AC-V11-021, AC-V11-022, AC-V11-025 | TC-015, TC-021, TC-022, TC-025 |
| SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-020, AC-V11-021, AC-V11-022, AC-V11-026 | TC-020, TC-021, TC-022, TC-026 |
| SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-023, AC-V11-024 | TC-023, TC-024 |
| SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-011, AC-V11-012, AC-V11-016, AC-V11-024, AC-V11-025, AC-V11-026 | TC-011, TC-012, TC-016, TC-024, TC-025, TC-026 |

## Per-TC Trace And Planned Evidence Matrix

This matrix is the pre-implementation coverage contract for `test_coverage` review. `Acceptance Role=Acceptance` means the TC contributes directly to scenario/journey acceptance. `Acceptance Role=Supporting` means the TC supports compatibility, packaging, static contract, or release-boundary confidence and must not be counted as the only proof for a scenario journey.

| TC | SC | US | Journey | AC | TASK | Planned Evidence Layer | Acceptance Role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-001 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-001 | TASK-001, TASK-007 | unit | Supporting |
| TC-002 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-002 | TASK-001, TASK-007 | unit | Acceptance |
| TC-003 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-003 | TASK-001, TASK-003, TASK-007 | runtime_integration | Acceptance |
| TC-004 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-004 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-005 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-005 | TASK-002, TASK-007 | unit | Acceptance |
| TC-006 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-006 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-007 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-007 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-008 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-008 | TASK-002, TASK-003, TASK-007 | unit | Acceptance |
| TC-009 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-009 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-010 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-010 | TASK-002, TASK-003, TASK-004, TASK-007 | runtime_integration | Acceptance |
| TC-011 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-011 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-012 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-012 | TASK-001, TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-013 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-013 | TASK-002, TASK-004, TASK-007 | unit | Supporting |
| TC-014 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-014 | TASK-003, TASK-004, TASK-007 | runtime_integration | Supporting |
| TC-015 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-015 | TASK-004, TASK-007 | unit | Acceptance |
| TC-016 | SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-016 | TASK-001, TASK-007 | unit | Acceptance |
| TC-017 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-017 | TASK-002, TASK-007 | unit | Acceptance |
| TC-018 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-018 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-019 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-019 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-020 | SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-020 | TASK-003, TASK-007 | runtime_integration | Acceptance |
| TC-021 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-021 | TASK-006, TASK-007 | packaging_smoke | Acceptance |
| TC-022 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-022 | TASK-002, TASK-005, TASK-006, TASK-007 | runtime_integration | Acceptance |
| TC-023 | SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-023 | TASK-005, TASK-007 | gatekeeper | Acceptance |
| TC-024 | SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-024 | TASK-005, TASK-006, TASK-007 | gatekeeper | Acceptance |
| TC-025 | SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-025 | TASK-006, TASK-007 | static_contract | Acceptance |
| TC-026 | SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-026 | TASK-005, TASK-006, TASK-007 | release_gate | Acceptance |

## Test Cases

| TC ID | Type | Level | FR | TASK | Core Assertion |
| --- | --- | --- | --- | --- | --- |
| TC-001 | Positive | Unit | FR-001 | TASK-001, TASK-007 | Review profile lookup identifies the exact review type and required reviewer responsibility set for each gate. |
| TC-002 | Positive | Unit | FR-002, FR-013 | TASK-001, TASK-007 | Non-UI review input snapshot includes current feature slug, Open Spec artifacts, scenario matrix, behavior contract, obligations, and stage evidence instead of static prompt text only. |
| TC-003 | Positive | Runtime integration | FR-003, FR-007 | TASK-001, TASK-003, TASK-007 | A valid `scenario` review artifact records product intent, journeys, negative boundaries, deliberation sections, and can advance the scenario gate. |
| TC-004 | Negative | Unit / Runtime integration | FR-003, FR-008 | TASK-002, TASK-005, TASK-007 | A `scenario` review with unresolved `blocking_findings` fails closed and cannot satisfy freeze. |
| TC-005 | Positive | Unit | FR-004 | TASK-002, TASK-007 | A valid `test_coverage` review accepts complete `US/J/SC/AC/TASK/TC` traceability with no coverage gaps or missing assertions. |
| TC-006 | Negative | Unit / Runtime integration | FR-004, FR-008 | TASK-002, TASK-005, TASK-007 | A `test_coverage` review missing required trace targets, coverage items, or executable assertions blocks handoff. |
| TC-007 | Negative / Regression | Unit | FR-006 | TASK-002, TASK-005, TASK-007 | `scenario`, `test_coverage`, `test_implementation`, and legacy `test` reviews are rejected when used to satisfy the wrong split gate. |
| TC-008 | Positive | Unit | FR-005 | TASK-002, TASK-003, TASK-007 | A valid `test_implementation` review requires actual test code paths, execution evidence paths, reviewed test IDs, and verified action assertions. |
| TC-009 | Negative | Unit / Runtime integration | FR-005, FR-008 | TASK-002, TASK-005, TASK-007 | A `test_implementation` review without executable assertion evidence fails closure readiness. |
| TC-010 | Compatibility | Unit / Runtime integration | FR-009, FR-012 | TASK-002, TASK-003, TASK-004, TASK-007 | Legacy records with missing `review_mode` are interpreted as `spawned_subagents`, while newly accepted V1.1 artifacts persist `review_mode` explicitly without changing existing artifact path/status semantics. |
| TC-011 | Negative / Compatibility | Unit / Runtime integration | FR-010 | TASK-002, TASK-005, TASK-007 | `role_simulation` reviews are rejected unless workflow policy allows degradation and explicit user acceptance is recorded; under `spawned_subagents_required`, user acceptance alone and role-simulation fallback cannot satisfy the gate. |
| TC-012 | Negative | Unit | FR-011 | TASK-001, TASK-002, TASK-005, TASK-007 | `blocked_with_reason`, including spawned-subagent-unavailable results, always records the visible reason and fails closed. |
| TC-013 | Negative | Unit | FR-007 | TASK-002, TASK-004, TASK-007 | Review artifact validation rejects missing or empty deliberation sections required for accepted artifacts. |
| TC-014 | Positive | Runtime integration | FR-012 | TASK-003, TASK-004, TASK-007 | Accepted V1.1 review records preserve artifact path, review ID, artifact version, review mode, and passed/missing state fields. |
| TC-015 | Compatibility / Regression | Unit | FR-012 | TASK-004, TASK-007 | Existing V1.0.10/V1.0.11 review state remains readable and only fails for documented V1.1 gate reasons. |
| TC-016 | Positive / Compatibility | Unit | FR-013 | TASK-001, TASK-007 | Branch evidence selection uses behavior contract evidence for `non_ui` and UI prototype/browser obligations for `ui` without mixing them. |
| TC-017 | Positive | Unit | FR-014 | TASK-002, TASK-007 | Collection coverage passes only when every declared item has covered items and item-level assertions. |
| TC-018 | Negative | Unit | FR-014 | TASK-002, TASK-005, TASK-007 | Collection coverage fails when any declared item lacks item-level coverage or assertion evidence. |
| TC-019 | Negative / Regression | Unit | FR-015 | TASK-002, TASK-005, TASK-007 | Marker-only, function-name-only, static-panel-only, and first-button-only assertions are classified as unresolved false-positive risks and fail the review. |
| TC-020 | Regression | Runtime integration | FR-002, FR-003, FR-004, FR-005, FR-008, FR-012 | TASK-003, TASK-007 | Workflow helpers route accepted artifacts through canonical `record_multi_agent_review` validation and cannot bypass fail-closed review validation. |
| TC-021 | Packaging | Packaging smoke | FR-001..FR-017 | TASK-006, TASK-007 | Packaged plugin runtime, skill text, and templates include V1.1 split gate rules, review modes, review templates, and artifact contract wording. |
| TC-022 | Compatibility / Packaging / Regression | Runtime integration / Packaging smoke | FR-006, FR-012 | TASK-002, TASK-005, TASK-006, TASK-007 | Legacy generic `test` review remains interpretable where already required but does not satisfy V1.1 `test_coverage` or `test_implementation` gates. |
| TC-023 | Negative / Runtime integration | Gatekeeper | FR-016 | TASK-005, TASK-007 | Non-UI pre-handoff blocks without authoritative `test_coverage`, and non-UI pre-closure blocks without authoritative `test_implementation` after implementation evidence exists. |
| TC-024 | Negative / Regression | Runtime integration / Gatekeeper | FR-017, NFR-006 | TASK-005, TASK-006, TASK-007 | Chat/session/status-only/Open Spec/custom artifact claims, including deceptive records with the right `review_type` but missing canonical fields, cannot satisfy `scenario`, `test_coverage`, or `test_implementation` gates. |
| TC-025 | Documentation / Packaging | Static contract | FR-016, FR-017, NFR-006 | TASK-006, TASK-007 | Generated package/runtime/skill/template outputs use non-UI behavior/planned evidence terminology, do not mislabel required non-UI coverage as browser-only `Planned E2E`, and do not introduce dashboard UI, external workflow/controller integration, or standalone Runtime API versioning behavior. |
| TC-026 | Negative / Release gate | Runtime integration / Packaging smoke | FR-008, FR-017, NFR-006 | TASK-005, TASK-006, TASK-007 | Release and Product Delivery closure derivation remain not eligible when TASKs are not complete, tests are not run, formal closure evidence is absent, only status/custom summary claims exist, or out-of-scope dashboard/external/API-versioning claims appear. |

## Detailed Case Design

| TC ID | Preconditions | Steps | Expected Result |
| --- | --- | --- | --- |
| TC-001 | Runtime exposes V1.1 review profiles. | Request profiles for `scenario`, `test_coverage`, and `test_implementation`. | Each profile returns exact review type, gate purpose, and required responsibilities matching the specification. |
| TC-002 | Non-UI feature state has Open Spec, scenario matrix, behavior contract, obligations, and optional executed evidence. | Build review input snapshot for each review type. | Snapshot references current feature artifacts and non-UI evidence anchors; generic prompt-only payload is rejected or incomplete. |
| TC-003 | Valid `scenario` review payload has required deliberation and no blockers. | Validate and record the review through workflow. | State records `multi_agent_reviews.scenario.status=passed`; next gate is freeze confirmation. |
| TC-004 | `scenario` review payload has non-empty `blocking_findings`. | Validate or record the review. | Review raises gate error; freeze remains blocked. |
| TC-005 | Valid `test_coverage` payload has `US/J/SC/AC/TASK/TC`, empty gaps, and collection coverage. | Validate `test_coverage`. | Validation passes. |
| TC-006 | `test_coverage` payload omits one trace target or includes missing executable assertions. | Validate or derive pre-handoff blockers. | Review fails and handoff blocker remains. |
| TC-007 | Valid artifact body is supplied under the wrong required gate. | Validate substituted review types, including legacy `test` for split gates. | Validation rejects every substitution. |
| TC-008 | `test_implementation` payload includes real code paths, evidence paths, reviewed IDs, and action assertions. | Validate `test_implementation`. | Validation passes. |
| TC-009 | `test_implementation` payload omits code paths, evidence paths, or verified assertions. | Validate and check pre-closure readiness. | Validation fails; closure blocker remains. |
| TC-010 | Existing legacy review record omits `review_mode`; a new V1.1 review is recorded. | Load compatible state, then record a new accepted review. | Legacy mode is interpreted as `spawned_subagents`; new review state persists explicit `review_mode` and expected review state semantics. |
| TC-011 | Review mode is `role_simulation`; current policy is `spawned_subagents_required`. | Validate without acceptance, then with user acceptance but default policy, then with explicit degradation policy and acceptance. | First two paths fail; user acceptance alone cannot override `spawned_subagents_required`; only accepted degradation under allowed policy passes outside this current run. |
| TC-012 | Review mode is `blocked_with_reason`, including spawned-subagent-unavailable output. | Validate review. | Validation fails closed and exposes blocked reason; no role-simulation fallback is accepted under `spawned_subagents_required`. |
| TC-013 | Review omits `independent_positions`, `cross_challenges`, `revisions`, `final_adjudication`, or `blocking_findings`. | Validate review. | Validation fails with missing-field error. |
| TC-014 | Workflow records an accepted V1.1 review. | Inspect state fields after recording. | State preserves artifact path, review ID, artifact version, review mode, and status. |
| TC-015 | Fixture uses V1.0.10/V1.0.11 review state shape. | Load/normalize state and validate documented gates. | Existing fields remain interpretable; failures are only documented gate failures. |
| TC-016 | Project type varies between `non_ui` and `ui`. | Build prompt/input snapshot for both project types. | `non_ui` uses behavior contract/evidence; `ui` uses UI prototype/browser obligations. |
| TC-017 | Collection coverage declares all required items and assertions. | Validate coverage review. | Validation passes. |
| TC-018 | Collection coverage declares an item missing from `covered_items` or `item_level_assertions`. | Validate coverage review. | Validation fails and names the missing item. |
| TC-019 | Assertions contain marker-only, function-name-only, static-panel-only, or first-button-only evidence. | Validate coverage or implementation review. | Validation classifies unresolved false-positive risk and fails. |
| TC-020 | Workflow helper receives valid and invalid review artifacts. | Record through helper and compare with direct canonical validation behavior. | Helper cannot bypass canonical validation; invalid payloads fail identically. |
| TC-021 | Packaging function builds plugin distribution. | Inspect generated runtime assets, skill text, and templates. | Package contains V1.1 orchestration wording, split review templates, and review mode/fail-closed rules. |
| TC-022 | Legacy generic `test` review exists in state. | Check compatibility loading plus split gate validation. | Legacy state is readable; split V1.1 gates still require authoritative review types. |
| TC-023 | Non-UI state has behavior contract and scenario matrix, but one split review gate is missing or substituted. | Derive pre-handoff blockers before `test_coverage`, then derive pre-closure blockers after implementation evidence without `test_implementation`. | Pre-handoff names missing `test_coverage`; pre-closure names missing `test_implementation`; legacy `test` and wrong split reviews do not clear either blocker. |
| TC-024 | State or custom artifact claims a review is `passed` without a matching structured artifact and validated gate-specific fields. | Attempt to satisfy `scenario`, `test_coverage`, and `test_implementation` with chat/session/status/Open Spec/progress/custom-only evidence, then with a deceptive record using the right `review_type` but missing deliberation or gate-specific fields. | Every gate remains blocked and reports that supporting evidence or incomplete canonical-looking records cannot replace the validated structured review artifact. |
| TC-025 | Package generation renders non-UI instructions, templates, planned obligation wording, and runtime assets. | Inspect generated runtime/package/skill/template outputs for `non_ui`, behavior evidence, split review gates, browser-only wording, dashboard behavior, external workflow/controller integration behavior, and standalone Runtime API versioning behavior. | Non-UI text references planned behavior evidence or planned obligations; browser E2E wording is only branch-specific UI compatibility text; dashboard UI behavior, external workflow/controller integration behavior, and standalone Runtime API versioning behavior are absent or explicitly out of scope. |
| TC-026 | State, Open Spec, package output, or closure derivation claims release/closure readiness while TASKs are incomplete, TC execution records are `Not Run`, closure validation is missing, or out-of-scope dashboard/external/API-versioning claims appear. | Run release-readiness/closure gate derivation against the incomplete state and inspect generated package/release text and closure blocker output. | Release remains Draft / Not Released; Product Delivery closure remains Not Eligible; status/custom-only closure claims and out-of-scope dashboard/external/API-versioning claims are rejected by gate derivation. |

## Execution Records

| TC ID | Executor | Execution Date | Result | Defect |
| --- | --- | --- | --- | --- |
| TC-001 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-002 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-003 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-004 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-005 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-006 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-007 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-008 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-009 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-010 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-011 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-012 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-013 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-014 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-015 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-016 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-017 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-018 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-019 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-020 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-021 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-022 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-023 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-024 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-025 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-026 | N/A | N/A | Not Run - implementation not started | N/A |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None for test-case design. | Testing-stage case design can proceed. | PASS |
| Assumption | Runtime implementation names may shift during TASK-001..TASK-006. | Test filenames and helper names may need minor alignment after RED-first implementation starts. | Carry forward |
| Constraint | Implementation has not started. | No test execution or pass/fail evidence is available. | All execution records remain Not Run |
