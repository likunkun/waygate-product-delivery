# Multi-Agent Scenario Review

- review_type: scenario
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- reviewer_agent_ids: []
- reviewer_spawn_source:
- role_simulation_user_accepted: false
- status: draft
- seat_contract_version: 1.1.0-seat.1
- review_seats: intent_boundary, journey_interaction
- reviewers: product intent + negative boundary, journey + interaction
- independent_positions: []
- cross_challenges: []
- revisions: []
- final_adjudication:
- baseline_inheritance_review: {}
- ui_continuity_findings: []
- prototype_design_bundle_hash:
- prototype_design_audit_hash:
- reviewed_design_dimensions: [global_shell, navigation, visual_language, information_density, component_system, responsive_behavior]
- global_visual_continuity_findings: []
- annotation_separation_findings: []
- blocking_findings: []

New reviews must carry the two seat-scoped `review_briefs` returned by `prepare_review_role_tasks`. Dispatch only the matching brief to each seat; it contains that seat's role tasks and complete frozen role cards, including quality rubrics and five examples.

For incremental existing-surface UI, `baseline_inheritance_review` must prove the scenario inherits the previous real entry path and does not replace it with a parallel page.
The review must bind the current design bundle and audit, positively cover every product-context dimension, and judge whether the inherited shell and overall composition are coherent. Empty findings alone are not positive coverage, and reviewers cannot waive a failed `prototype_design_integrity` gate.

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
