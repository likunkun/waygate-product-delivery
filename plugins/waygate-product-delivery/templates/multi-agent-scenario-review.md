# Multi-Agent Scenario Review

- review_type: scenario
- review_mode: spawned_subagents | role_simulation | blocked_with_reason
- reviewer_agent_ids: []
- reviewer_spawn_source:
- role_simulation_user_accepted: false
- status: draft
- reviewers: product intent, UI/UX scenario, negative boundary
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

For incremental existing-surface UI, `baseline_inheritance_review` must prove the scenario inherits the previous real entry path and does not replace it with a parallel page.
The review must bind the current design bundle and audit, positively cover every product-context dimension, and judge whether the inherited shell and overall composition are coherent. Empty findings alone are not positive coverage, and reviewers cannot waive a failed `prototype_design_integrity` gate.
