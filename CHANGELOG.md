# Changelog

## 1.0.19

- Fixes active v1.0.18 state migration so an authorized execution policy clears only the stale `execution_mode` pending decision at the next stage boundary.
- Adds startup-time `automatic` and `full_speed` execution model modes alongside the independent multi-Agent review authorization.
- Adds the explicit startup prompts `启动交付，自动模式，多 Agent 模式` and `启动交付，全速模式，多 Agent 模式`.
- Adds customizable user, project, and per-delivery model profiles with deterministic precedence, validation, and frozen profile hashes in `execution_model_policy`.
- Uses stage-specific automatic profiles with escalation after repeated failures or high-risk blockers; full-speed mode applies one uniform model profile to the main thread and every subagent.
- Requires `fork_context=false` for bounded stage agents and keeps canonical state ownership in the main coordinator.
- Adds next-stage execution mode switching and explicit main-thread model observation for full-speed mode.

## 1.0.18

- Adds canonical `recover_stale_launch_package()` recovery when a fresh launch authorization no longer matches the active delivery goal.
- Archives the previous handoff, delivery goal, implementation state, prompt, and task completion binding before replacement.
- Records a hash-linked `implementation_package_superseded` transition instead of hand-editing state or deleting the stale blocker.
- Reuses task completion evidence only when the task ID and `planned_task_hash` are unchanged; revised tasks return to the active queue.

## 1.0.17

- Defines `启动交付，多 Agent 模式` as explicit spawned-subagent execution authorization for the current delivery.
- Makes plain `启动交付` enter `authorization_pending` and wait for immediate review-mode selection before later gates can proceed.
- Splits multi-agent policy into evidence, execution authorization, scope, source, and authorized review types; authorization expires on stop or a new delivery.
- Migrates active legacy spawned-subagent policy without authorization metadata to `legacy_unverified` while preserving terminal closure history.

## 1.0.16

- Adds a frozen `prototype_contract` that binds canonical prototype HTML, PNG screenshots, surfaces, states, regions, relationships, and interactions to user confirmation.
- Adds `record_prototype_production_conformance()` with runtime validation for safe PNG evidence, controlled semantic snapshots, full-stack execution segments, and complete surface mapping.
- Adds the independent `ui_conformance` multi-agent review gate and requires exact coverage of all frozen surfaces, states, and regions.
- Upgrades canonical closure to `v0.11`, binding prototype, contract, production conformance, review hashes, and covered surface/region IDs while preserving v0.10/v1.0.15 terminal closures as read-only history.

## 1.0.15

- Adds the role-accurate scenario evidence gate for UI journey closure.
- Requires UI planned E2E obligations to bind `required_actor_roles`, `path_kind`, `ordinary_entry_path`, and `data_state_contract`.
- Requires executed browser evidence to bind actor identity, ordinary-path observation, independent `execution_segment_id`, and `test_title_or_step`.
- Blocks admin-only or annotation-only Browser E2E from closing Teacher primary journeys, and requires reviews to verify every planned test ID and action assertion.

## 1.0.14

- Adds the UI baseline continuity gate with `ui_change_type` classification.
- Requires incremental existing-surface prototypes to bind `baseline_feature_slug`, `baseline_surface_paths`, `baseline_user_journey`, `continuity_mapping`, and `prototype_delta_summary`.
- Requires UI planned E2E obligations to include `baseline_entry_path`, so browser journeys enter through the previous real product surface instead of a parallel prototype page.
- Makes prototype feedback and existing prototype revisions stale prior scenario/test review, planned E2E confirmation, and launch authorization.

## 1.0.13

- Adds the `full_stack_browser_e2e` evidence strength gate for UI journey closure.
- Rejects mocked business API browser tests as closure evidence unless a structured exemption explicitly allows closure.
- Requires executed browser evidence to bind acceptance URL, API health identity, network probe artifacts, business API request summaries, and mocked route classification.

## 1.0.12

- Limits Product Delivery user confirmation gates to scope freeze, UI prototype, and planned test coverage.
- Converts implementation launch authorization into canonical runtime evidence that auto-refreshes before handoff.
- Keeps the main flow moving through review, handoff, implementation, evidence, and closure unless a real blocker remains.

## 1.0.11

- Release consistency patch for the post-`1.0.10` line.
- Aligns the project roadmap around a compact future path:
  - `V1.0.x` remains a patch line for gate leaks, packaging failures, validator failures, and version drift.
  - `V1.1 多 Agent 评审编排产品化` becomes the next meaningful capability version.
  - `V1.1.x` absorbs orchestration support work instead of creating artificial Runtime API, schema, or dashboard versions.
  - `V2.0 外部工作流集成` remains deferred until local Product Delivery closure authority is stable.
- Keeps runtime behavior unchanged; the release focuses on version metadata, generated package alignment, and planning clarity.

## 1.0.10

- Current baseline before this cleanup.
- Provides the Waygate Product Delivery package under `plugins/waygate-product-delivery/`.
- Keeps canonical closure validation, transition journal requirements, and split multi-agent test coverage / test implementation gates.
