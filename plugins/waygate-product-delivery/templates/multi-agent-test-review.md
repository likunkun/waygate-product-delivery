# Multi-Agent Test Review

- review_type: test
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- reviewer_agent_ids: []
- reviewer_spawn_source:
- role_simulation_user_accepted: false
- status: draft
- seat_contract_version: 1.1.0-seat.1
- review_seats: test_strategy, assertion_quality
- reviewers: test strategy, assertion quality
- independent_positions: []
- cross_challenges: []
- revisions: []
- final_adjudication:
- blocking_findings: []

New reviews must carry the two seat-scoped `review_briefs` returned by `prepare_review_role_tasks`; dispatch each seat its matching role tasks and complete role cards.

## 专家身份与结论

- dispatch_briefs: preserve the canonical seat-scoped naming sidecar
- 评审席位：<seat_display_name>
- 专家：<agent_display_name>
- 语义任务名：<agent_spawn_name>
- 真实 Agent ID：<host-returned agent_id>
- 派发来源：<reviewer_spawn_source>
- 逻辑角色：<role_ids shared by this seat>
- 职责：<mission>
- 结论：<status/stance>
