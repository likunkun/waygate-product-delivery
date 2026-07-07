# Non-UI Behavior Contract

Status: Draft

Contract: V1.1 Multi-Agent Review Orchestration Behavior Contract

## Entry Points
- build review orchestration profile for scenario review
- build review orchestration profile for test coverage review
- build review orchestration profile for test implementation review
- record accepted review through ProductDeliveryWorkflow.record_multi_agent_review
- derive pre-handoff and pre-closure blockers from Product Delivery state
- generate packaged skill and template text for V1.1 review orchestration

## Inputs
- feature_slug v1.1-multi-agent-review-orchestration
- current Open Spec package 00 through 08
- scope scenario matrix rows
- non-UI behavior contract artifact
- planned behavior obligations and coverage audit records
- executed test evidence and closure inputs when reviewing implementation
- review mode policy and user confirmation records
- canonical structured multi-agent review artifacts

## Outputs
- feature-specific review input snapshot
- reviewer role prompt payloads
- structured multi-agent review artifact
- Product Delivery state multi_agent_reviews entry
- blocked_with_reason result when evidence is unavailable or blockers remain
- packaged V1.1 skill/template review rules

## Scenario Taxonomy

### Entry Points
- review profile lookup
- input snapshot construction
- review artifact assembly
- workflow state recording
- gate blocker derivation
- plugin packaging generation

### Inputs Outputs
- Open Spec, scenario matrix, behavior contract, obligations, evidence, review mode input
- prompt payloads, review artifacts, state entries, blockers, package text output

### Exceptions
- missing current feature evidence
- unavailable spawned subagents
- wrong review type for gate
- unresolved blocking findings
- role_simulation under spawned_subagents_required policy
- role_simulation without both policy allowance and explicit user acceptance
- blocked_with_reason review result
- status-only or custom-only review completion claim

### Recovery
- fail closed without mutating closure status
- retry real spawned subagents when transport or capacity fails
- request user acceptance only after degradation policy is explicitly enabled
- keep role_simulation blocked under spawned_subagents_required policy
- re-run validation after fixing missing fields or blockers

### Permissions
- do not start implementation before Product Delivery gates pass
- do not accept role_simulation under spawned_subagents_required policy
- do not replace structured artifacts with chat summaries, session logs, status-only claims, Open Spec summaries, progress records, or custom gate artifacts

### Long Tasks
- multi-round subagent deliberation may exceed a single response window
- full regression and packaging verification runs after implementation

### State Transitions
- scenario matrix draft ready to scenario review passed
- scenario review passed to user confirmed freeze
- planned obligations ready to test coverage review passed
- implementation evidence ready to test implementation review passed
- review blocked to blocked_with_reason without closure mutation

### Boundary Conditions
- legacy generic test review remains readable but cannot satisfy split gates
- missing review_mode defaults to spawned_subagents for legacy compatibility only
- new V1.1 accepted artifacts must record review_mode explicitly
- existing V1.0.11 artifacts remain supporting evidence unless revalidated
- status-only, Open Spec/progress summaries, and custom gate artifacts remain supporting evidence only
- no dashboard, external integration, or standalone Runtime API versioning

## Behavior Evidence Candidates
- BP-V11-001 scenario review orchestration builds role prompts and records deliberation
- BP-V11-002 test coverage review checks traceability and item-level planned assertions
- BP-V11-003 test implementation review checks real test code and execution evidence
- BP-V11-004 role_simulation is rejected under spawned_subagents_required and requires policy allowance plus explicit user acceptance otherwise
- BP-V11-005 blocked_with_reason fails closed and preserves visible reason
- BP-V11-006 legacy state remains readable without satisfying new split gates
- BP-V11-007 package output carries V1.1 orchestration rules
- BP-V11-008 status-only, Open Spec/progress summary, and custom-only review claims cannot satisfy review gates
- BP-V11-009 non-UI pre-handoff requires test_coverage and pre-closure requires test_implementation
- BP-V11-010 release and Product Delivery closure remain not eligible before implementation, executed tests, and formal closure evidence exist

## Negative Boundary Records
- NB-V11-001 do not merge scenario, test coverage, and test implementation gates
- NB-V11-002 do not treat role_simulation as strong evidence
- NB-V11-003 do not allow chat summaries, session logs, status-only claims, Open Spec summaries, progress records, or custom gate artifacts to replace review artifacts
- NB-V11-004 do not introduce dashboard or external workflow integration in V1.1
- NB-V11-005 do not create standalone Runtime API versioning for V1.1
- NB-V11-006 do not mark release or closure passed before implementation and tests run
- NB-V11-007 do not accept role_simulation under spawned_subagents_required policy

## Accepted Limitations
- implementation has not started
- tests have not run
- release remains Draft / Not Released
- current delivery policy is spawned_subagents_required and does not allow role_simulation degradation
- real spawned subagents are available in this session but orchestration must still fail closed if unavailable in future sessions unless policy explicitly allows degradation
