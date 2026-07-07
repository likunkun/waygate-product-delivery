# V1.1 Multi-Agent Review Orchestration - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial requirements for reusable multi-agent review orchestration. | CR-001 |

## Business Goal

Make multi-agent review a reusable Product Delivery orchestration mechanism, replacing loose templates and prose-only rules while preserving existing closure trust.

## Scope

### In Scope

- Reusable orchestration for Product Delivery review gates.
- Review types: scenario review, test coverage review, test implementation review, and compatibility with existing generic test review where already required.
- Fixed reviewer responsibility coverage: product intent, scenario and journey completeness, test coverage, test implementation, and negative boundaries.
- Feature-specific prompt inputs from current Open Spec, scenario matrix, UI prototype or non-UI behavior contract evidence, planned E2E or behavior obligations, and executed evidence when applicable.
- Structured review artifacts with independent positions, cross challenges, revisions, final adjudication, conclusions, unresolved questions, and blocking findings.
- Review mode policy: `spawned_subagents` default strong evidence, `role_simulation` only when workflow policy explicitly allows degradation and user acceptance is separately recorded, `blocked_with_reason` fail-closed. This current delivery run is `spawned_subagents_required`, so `role_simulation` cannot satisfy any current gate.
- Non-interchangeable gates for scenario review, test coverage review, and test implementation review.

### Out Of Scope

- Dashboard.
- External system integration.
- Independent Runtime API versioning.
- UI prototype generation or redesign.
- Replacing user confirmations, implementation launch authorization, Codex Goal handoff, or closure validation.
- Treating legacy generic `test` review as a replacement for `test_coverage` or `test_implementation`.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When a Product Delivery run reaches a multi-agent review gate, the system shall identify the required review type and required reviewer responsibilities for that gate. | Each review gate records a review type and reviewer responsibility set covering the gate purpose. |
| FR-002 | P0 | When orchestration prepares a review, it shall build feature-specific review inputs from the current Open Spec, scenario matrix, branch evidence, planned obligations, and stage-appropriate executed evidence. | Generated review input references the current feature artifacts and does not rely on generic static prompt text alone. |
| FR-003 | P0 | When a scenario review runs, it shall review product intent, scenario and journey completeness, and negative boundaries before user-confirmed freeze. | Scenario review artifact records those responsibilities and blocks freeze when blocking findings remain. |
| FR-004 | P0 | When a test coverage review runs, it shall review planned coverage before implementation authorization and shall inspect `US/J/SC/AC/TASK/TC` traceability. | Test coverage review artifact records reviewed trace targets and blocks handoff when required trace targets or coverage items are missing. |
| FR-005 | P0 | When a test implementation review runs, it shall review actual test code paths, execution evidence paths, reviewed test IDs, and verified action assertions before formal closure when that gate is required. | Test implementation review artifact records real test/evidence paths and blocks closure when executable assertion evidence is missing. |
| FR-006 | P0 | When scenario review, test coverage review, or test implementation review is required, no other review type shall satisfy that gate. | Gate validation rejects substitution between scenario, test coverage, and test implementation reviews. |
| FR-007 | P0 | When a review artifact is accepted, it shall contain independent positions, cross challenges, revisions, final adjudication, and blocking findings. | Artifact validation fails if any required deliberation section is absent or empty where evidence is required. |
| FR-008 | P0 | When blocking findings remain unresolved, the review gate shall fail closed. | Any non-empty blocking findings prevent the gate from passing. |
| FR-009 | P0 | When review mode is not specified, the system shall treat `spawned_subagents` as the default strong-evidence mode. | Accepted review records include `review_mode=spawned_subagents` unless another valid mode is explicitly recorded. |
| FR-010 | P0 | When `role_simulation` is used, the system shall require both a workflow policy that allows degradation and explicit user acceptance before the review can satisfy a gate. | A `role_simulation` review is rejected when user acceptance is missing or the workflow policy remains `spawned_subagents_required`. |
| FR-011 | P0 | When review mode is `blocked_with_reason`, the system shall record the reason and prevent the review from passing. | `blocked_with_reason` always yields a blocking result with a visible reason. |
| FR-012 | P1 | When V1.1 writes or reads review state, it shall preserve existing artifact path, review ID, artifact version, review mode, and passed/missing status semantics. | Existing V1.0.10/V1.0.11 review records remain interpretable. |
| FR-013 | P1 | When branch evidence differs by project type, orchestration shall use UI prototype evidence for UI projects and non-UI behavior contract evidence for non-UI projects. | Prompt inputs show the branch-appropriate evidence source. |
| FR-014 | P1 | When collection-style coverage exists, test coverage review shall require item-level coverage and action assertions for each declared item. | Review fails when declared collection items lack covered items or item-level assertions. |
| FR-015 | P1 | When test implementation evidence uses marker-only, function-name-only, static-panel-only, or first-button-only assertions, the review shall classify them as false-positive risks. | Review fails while unresolved false-positive risks remain. |
| FR-016 | P0 | For `non_ui` projects, pre-handoff validation shall require an authoritative `test_coverage` review and pre-closure validation shall require an authoritative `test_implementation` review when implementation evidence exists. | Non-UI pre-handoff and pre-closure gates remain blocked when the split review artifact for that specific gate is missing, substituted, or blocked. |
| FR-017 | P0 | When a chat summary, session status, Open Spec summary, progress record, or custom artifact claims review completion, the system shall reject it unless it is backed by the canonical structured multi-agent review artifact for the required review type. | Status-only, summary-only, and custom artifact-only evidence cannot satisfy `scenario`, `test_coverage`, or `test_implementation` gates. |

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Auditability | Review decisions must be reproducible from structured artifacts without relying on chat history. | Each accepted review artifact contains review mode, reviewers, deliberation sections, adjudication, and blocking findings. |
| NFR-002 | Evidence strength | Strong and degraded review evidence must be distinguishable. | Every review record contains `review_mode`; `role_simulation` requires explicit user acceptance and a degradation-allowing workflow policy. |
| NFR-003 | Gate safety | Review gates must fail closed when required evidence is missing, substituted, or blocked. | Validation rejects missing fields, wrong review type, unresolved blockers, and blocked review mode. |
| NFR-004 | Compatibility | V1.1 must preserve existing Product Delivery artifact/state semantics. | Existing review records using current review fields remain valid or fail only for documented gate reasons. |
| NFR-005 | Traceability | Review artifacts must connect decisions to current feature evidence. | Review input/output references current feature slug and relevant Open Spec, scenario matrix, obligation, or executed evidence anchors. |
| NFR-006 | Evidence integrity | Canonical gate authority must remain machine-checkable and must not depend on prose-only status claims. | Handoff, closure, and gatekeeper checks ignore session-only or custom-only review claims unless canonical structured review state and artifact validation pass. |

## Product Delivery Rule Preservation

- Default strong evidence is real `spawned_subagents`.
- `role_simulation` is degraded evidence and is allowed only after explicit user acceptance plus a workflow policy that allows degradation; under the current `spawned_subagents_required` policy it must fail closed.
- `blocked_with_reason` cannot satisfy a review gate.
- Scenario review, test coverage review, and test implementation review are separate gates and cannot replace each other.
- Generic `test` review compatibility does not remove the requirement for split `test_coverage` and `test_implementation` gates where required.
- Session logs, quick summaries, Open Spec summaries, and custom artifacts are supporting context only; they do not replace structured multi-agent review artifacts.
- For non-UI projects, behavior-contract evidence does not weaken split review requirements: `test_coverage` still gates pre-handoff, and `test_implementation` still gates pre-closure after implementation evidence exists.
- A status field that says `passed`, `closed`, `ready`, or equivalent is not authoritative unless the matching structured review artifact validates for the required review type.

## Risks And Assumptions

- Risk: orchestration scope drifts into dashboard or external controller work. Mitigation: keep V1.1 limited to local Product Delivery orchestration and artifacts.
- Risk: `role_simulation` is accidentally treated as strong evidence. Mitigation: require explicit review mode, user acceptance, and a degradation-allowing workflow policy; current `spawned_subagents_required` runs reject it.
- Risk: generic test review hides coverage or implementation gaps. Mitigation: keep split review gates non-interchangeable.
- Assumption: non-UI branch evidence is represented by behavior contracts and behavior evidence obligations.
- Assumption: exact runtime entrypoint names are deferred to later stages.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents requirements-stage completion. | Proceed |
| Assumption | Runtime entrypoint names and schema shape are not requirements-stage decisions. | Specification must define observable contracts without creating an out-of-scope API version. | Carry forward |
| Nice-to-know | Whether generic `test` review remains long-term after V1.1. | Does not block V1.1 because compatibility can be preserved while split gates remain authoritative. | Track |
| Nice-to-know | Existing custom artifacts may remain useful as supporting evidence. | They must not satisfy Product Delivery review gates by themselves. | Track |
