# V1.1 Multi-Agent Review Orchestration - 00 Change Request

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial requirements-stage change request for reusable multi-agent review orchestration. | CR-001 |

## Change Request

| Field | Value |
| --- | --- |
| CR ID | CR-001 |
| Change Type | Planned capability version |
| Priority | P0 |
| Source | `ROADMAP.md`, `CHANGELOG.md`, current Product Delivery review gate behavior |
| Target Version | V1.1 |

## Background And Objective

V1.1 upgrades the current template-and-rule based multi-agent review process into a reusable review orchestration mechanism.

The current baseline already validates visible review artifacts, review modes, and split review gates. V1.1 must productize that behavior so future Product Delivery runs can consistently generate feature-specific review prompts, preserve independent reviewer positions, force cross-review challenge, record adjudication, and fail closed on unresolved blocking findings.

## In Scope

- Productize multi-agent review orchestration for Product Delivery review gates.
- Keep fixed reviewer responsibilities for product intent, scenario and journey completeness, test coverage, test implementation, and negative boundaries.
- Generate feature-specific review prompts from current Open Spec, scenario matrix, branch evidence, planned obligations, and executed evidence when applicable.
- Treat `spawned_subagents` as the default strong-evidence path.
- Keep `role_simulation` as degraded evidence that can satisfy a gate only when the workflow policy explicitly allows degradation and the user separately accepts it; for this current `spawned_subagents_required` delivery run, `role_simulation` cannot satisfy any gate.
- Keep scenario review, test coverage review, and test implementation review as separate non-interchangeable gates.
- Persist structured review artifacts containing independent positions, cross challenges, revisions, final adjudication, and blocking findings.
- Preserve compatibility with existing Product Delivery state and artifact expectations.

## Out Of Scope

- Dashboard or visual management UI.
- External workflow/controller/system integration.
- Independent Runtime API versioning as a standalone V1.1 deliverable.
- Replacing Product Delivery closure authority with external evidence.
- Merging scenario review, test coverage review, and test implementation review into one generic review.
- Treating chat summaries, Open Spec summaries, or session logs as replacements for structured review artifacts.

## Impact Analysis

| Area | Impact |
| --- | --- |
| Product workflow | Multi-agent review becomes an explicit reusable orchestration capability instead of scattered templates and prose rules. |
| Artifacts | Review artifacts must preserve structured deliberation records and blocking findings. |
| State protocol | Existing review status, review mode, artifact path, and gate status semantics must remain compatible. |
| Gates | Split scenario, test coverage, and test implementation gates remain non-interchangeable. |
| User confirmation | `role_simulation` requires both a degradation-allowing workflow policy and explicit user acceptance before it can satisfy a review gate; user acceptance alone is insufficient under `spawned_subagents_required`. |
| Waygate / external systems | No direct integration or external state mutation in V1.1. |

## Acceptance And Rollback

- Acceptance: V1.1 requirements define testable FR/NFR, explicit scope boundaries, preserved Product Delivery review rules, and structured artifact expectations.
- Rollback: reject the V1.1 package and continue using the V1.0.11 baseline rules and templates.
- Product Delivery artifacts created before V1.1 must remain readable and must not be silently reclassified as stronger evidence.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents requirements-stage completion. | Proceed |
| Assumption | For non-UI Product Delivery branches, prompt inputs use behavior contract and behavior evidence instead of UI prototype evidence. | Keeps V1.1 branch-neutral without adding UI scope. | Record for specification |
| Assumption | V1.1 productizes orchestration behavior without creating a separately versioned Runtime API. | Prevents scope drift into out-of-scope API versioning. | Record for specification |
| Nice-to-know | Exact runtime entrypoint names are deferred. | Does not block requirements. | Resolve in specification or solution stage |
