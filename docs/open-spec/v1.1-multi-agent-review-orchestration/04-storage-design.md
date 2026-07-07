# V1.1 Multi-Agent Review Orchestration - 04 Storage Design

| Field | Value |
| --- | --- |
| Version | V1.1 |
| Author | Codex |
| Date | 2026-07-01 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial storage design for V1.1 multi-agent review orchestration. | CR-001 |

## Change Linkage

- Change Request: CR-001
- Technical Solution: `03-technical-solution.md`
- Storage type: local filesystem JSON and Markdown artifacts
- Database: N/A

## Storage Model

V1.1 does not introduce a database. It extends the existing `.product-delivery/` file-backed protocol.

| Storage Object | Path | Purpose |
| --- | --- | --- |
| Canonical state | `.product-delivery/state.json` | Machine-readable current Product Delivery state. |
| Review artifact | `.product-delivery/artifacts/multi-agent-<review_type>-review.md` | Human-readable structured review artifact. |
| Optional input snapshot artifact | `.product-delivery/artifacts/multi-agent-<review_type>-input.json` or embedded Markdown JSON block | Reproducible prompt/input context for review decisions. |
| Open Spec docs | `docs/open-spec/v1.1-multi-agent-review-orchestration/` | Versioned specification and planning source. |

## State Fields

Existing state location remains `multi_agent_reviews`.

| Field | Type | Constraint | Notes |
| --- | --- | --- | --- |
| `multi_agent_reviews.<type>.status` | string | `missing`, `passed`, or blocked status | Existing status semantics preserved. |
| `multi_agent_reviews.<type>.artifact` | string or null | Relative artifact path | Existing artifact path semantics preserved. |
| `multi_agent_reviews.<type>.review_id` | string | Required when passed | Existing accepted-review field. |
| `multi_agent_reviews.<type>.artifact_version` | string | Required when passed | Existing accepted-review field. |
| `multi_agent_reviews.<type>.review_mode` | string | `spawned_subagents`, `role_simulation`, `blocked_with_reason` | Missing mode is interpreted as `spawned_subagents` only for legacy compatibility reads; new V1.1 accepted artifacts must persist it explicitly. |
| `multi_agent_reviews.<type>.reviewers` | list[string] | Optional summary mirror | Full reviewer details live in artifact. |
| `multi_agent_reviews.<type>.inputs_snapshot` | object or string | Optional | May point to artifact path or store compact snapshot. |
| `multi_agent_reviews.<type>.gate_results` | object | Optional | Captures pass/fail checks for audit. |
| `multi_agent_reviews.<type>.blocked_reason` | string | Required when blocked | Must not satisfy gate. |

Valid `<type>` values:

- `scenario`
- `test`
- `test_coverage`
- `test_implementation`

## Review Artifact Fields

Accepted review artifacts must preserve these fields:

- `review_id`
- `review_type`
- `status`
- `review_mode`
- `reviewers`
- `artifact_version`
- `input_snapshot`
- `independent_positions`
- `cross_challenges`
- `revisions`
- `final_adjudication`
- `conclusions`
- `accepted_suggestions`
- `rejected_suggestions`
- `unresolved_questions`
- `blocking_findings`

Additional test coverage fields:

- `traceability_reviewed`
- `coverage_gaps`
- `title_overbreadth_findings`
- `missing_executable_assertions`
- `false_positive_risks`
- `collection_coverage`

Additional test implementation fields:

- `actual_test_code_paths`
- `execution_evidence_paths`
- `reviewed_test_ids`
- `verified_action_assertions`
- `supporting_evidence_only`

## Migration And Compatibility

Migration is additive.

Steps:

1. Preserve existing `multi_agent_reviews` keys and values.
2. When loading legacy state, keep missing `review_mode` compatible with `spawned_subagents`; newly accepted V1.1 artifacts must write `review_mode`.
3. Add optional V1.1 metadata only when orchestration runs.
4. Do not rewrite old artifacts unless a new review is executed.
5. Keep existing validation errors explicit and documented.

Backward compatibility:

- Existing V1.0.11 review records remain readable.
- Missing optional V1.1 fields do not corrupt state.
- A legacy generic `test` record remains visible but cannot satisfy `test_coverage` or `test_implementation`.

## Rollback

Rollback is file-level and non-destructive:

1. Stop using V1.1 orchestration helpers.
2. Leave V1.1 artifacts as supporting evidence only.
3. Continue using V1.0.11 `validate_multi_agent_review` and workflow gate behavior.
4. Do not mark closure complete from V1.1 artifacts unless the canonical validator passes.

## Integrity Rules

- State writes must continue through `write_state`.
- Review acceptance must continue through `record_multi_agent_review`.
- Hand-editing `.product-delivery/state.json` does not replace canonical transition methods.
- `blocked_with_reason` records must remain blocked and must not be reclassified as passed.
- `role_simulation` records must carry explicit user acceptance evidence and a degradation-allowing workflow policy; under `spawned_subagents_required`, they remain blocked evidence.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No storage blocker remains. | Proceed |
| Assumption | Markdown plus JSON state is sufficient for V1.1 auditability. | No database needed. | Validate through tests |
| Nice-to-know | Whether input snapshots are embedded in Markdown or written as sibling JSON files. | Implementation detail; either shape is acceptable if tests can verify reproducibility. | Decide during implementation |
