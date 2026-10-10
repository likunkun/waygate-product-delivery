# Multi-Agent Test Coverage Review

- review_type: test_coverage
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- reviewer_agent_ids: []
- reviewer_spawn_source:
- seat_contract_version: 1.1.0-seat.1
- review_seats: coverage_boundary, assertion_quality
- status: draft
- traceability_reviewed: [US, J, SC, AC, TASK, TC]
- coverage_gaps: []
- title_overbreadth_findings: []
- missing_executable_assertions: []
- false_positive_risks: []

- role_journey_coverage: []
- ordinary_path_coverage: []
- scenario_granularity_findings: []

New reviews must carry the two seat-scoped `review_briefs` returned by `prepare_review_role_tasks`; dispatch each seat its matching role tasks and complete role cards.

## Collection Coverage

| collection_id | required_items | covered_items | item_level_assertions |
| --- | --- | --- | --- |

This gate reviews test case coverage range before implementation. It must prove every UI journey has the required actor role, ordinary entry path, and scenario granularity before implementation starts. Scenario review, prototype review, and generic test review cannot replace it.
