# Multi-Agent UI Conformance Review

- review_type: ui_conformance
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- reviewer_agent_ids: []
- reviewer_spawn_source:
- status: draft
- reviewed_surface_ids: []
- reviewed_state_ids: []
- reviewed_region_ids: []
- reviewed_design_dimensions: [global_shell, navigation, visual_language, information_density, component_system, responsive_behavior]
- global_visual_continuity_findings: []
- annotation_separation_findings: []
- structural_findings: []
- visual_findings: []
- interaction_findings: []
- legacy_reuse_findings: []
- unmapped_regions: []
- accepted_visual_deviations: []
- blocking_findings: []

## Review Round Discipline

同轮全部评审者必须基于同一输入快照完成独立评审、交叉质疑和修订；全部评审者返回前不得修改评审对象。汇总者必须先去重并冻结完整问题清单，再批量修复全部已接受问题，最后执行一次统一复验。评审者失败时必须重试、替换或记录 blocked_with_reason，不得提前进入修复。

Review every frozen surface, state, region, relationship, and interaction against production PNG and controlled semantic snapshot evidence. Positively cover every product-context dimension and confirm that production preserves the clean-surface and external-annotation separation; empty findings alone are not evidence of complete review.
