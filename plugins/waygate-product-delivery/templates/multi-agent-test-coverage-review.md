# Multi-Agent Test Coverage Review

- review_type: test_coverage
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- status: draft
- traceability_reviewed: [US, J, SC, AC, TASK, TC]
- coverage_gaps: []
- title_overbreadth_findings: []
- missing_executable_assertions: []
- false_positive_risks: []

- role_journey_coverage: []
- ordinary_path_coverage: []
- scenario_granularity_findings: []

## Collection Coverage

| collection_id | required_items | covered_items | item_level_assertions |
| --- | --- | --- | --- |

This gate reviews test case coverage range before implementation. It must prove every UI journey has the required actor role, ordinary entry path, and scenario granularity before implementation starts. Scenario review, prototype review, and generic test review cannot replace it.
