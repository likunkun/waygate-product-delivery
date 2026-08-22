# Changelog

## 1.0.34

- Adds prototype design bundle v2 with `acceptance_content_separation` and a review-only `prototype-acceptance-content-scan-v1` report.
- Enforces that high-fidelity prototypes contain only real product content across static/rendered DOM, semantic snapshots, attributes, resources, and review modes.
- Treats acceptance, review, test, evidence, mock/fixture, and developer-only content as a hard `prototype_design_integrity` failure that cannot enter visual adjudication.
- Allows ambiguous real product copy only through `product_content_mappings` to lifecycle-bound `intended_product_ui_callouts`; invisible test selectors remain allowed.
- Keeps v1 bundles readable and existing confirmed deliveries unchanged until their prototype is modified, replaced, or reopened.
- Keeps scan evidence and mappings outside `product_domain_hash`, preserves closure schema `v0.11`, and updates runtime/package provenance to `1.0.34`.

## 1.0.33

- Classifies pixel failures, geometry mismatches, and small visible viewport-boundary overflows as `visual_adjudicable`, while keeping missing, non-finite, zero-sized, invisible, and clearly offscreen geometry `hard_blocking`.
- Uses one two-round remediation window for pixel and controlled geometry deviations, supports early user acceptance, and preserves stable decisions plus reset-on-rejection behavior.
- Writes task conformance and visual-adjudication v2 evidence with geometry bounds, deltas, tolerances, overflow, failure classification, and accepted `deviation_type`, while retaining read compatibility for v1 pixel-only artifacts.
- Requires final `ui_conformance.accepted_visual_deviations` to reference accepted pixel and geometry rows without changing the frozen prototype or reopening the product baseline.
- Keeps canonical closure schema `v0.11` and updates runtime provenance, generated plugin assets, and release packaging to `1.0.33`.

## 1.0.32

- Adds shorthand command layer to SKILL.md so users can type `$waygate-product-delivery start <slug> multi-agent` instead of the full JSON object. Codex expands shorthand to strict v1 JSON before passing to `scripts/waygate-control.py`; control.py remains unchanged.
- Supports `start`, `start <slug> multi-agent`, `start <slug> role-play`, `status`, `inspect`, `pause`, `resume`, `close`, and `abandon` shorthand commands.
- `resume` shorthand reads `.product-delivery/state.json` to resolve the current `delivery_id` automatically.
- `abandon` shorthand auto-chains `prepare_abandon` and `abandon` into a single user-facing command.
- Unsupported shorthand parameters fail closed; `stop` remains retired.
- Updates `defaultPrompt` in plugin.json to include shorthand examples.
- Updates README.md and README.zh-CN.md to document shorthand commands with usage examples.

## 1.0.31

- Stores authoritative delivery evidence under `.product-delivery/deliveries/<feature_slug>/<delivery_id>/` with a hashed manifest, a machine-readable `current.json` pointer, and a best-effort `current` symlink.
- Preserves completed, abandoned, and superseded delivery evidence while keeping `.product-delivery/artifacts/` as a hash-checked compatibility view rather than gate authority.
- Adds strict JSON lifecycle control through `scripts/waygate-control.py`; implicit natural-language activation is disabled with `agents/openai.yaml`.
- Separates resumable `pause`/`resume` from two-phase `prepare_abandon`/`abandon`, retires string-matched `stop()`, and preserves the same `delivery_id` across interruptions and resumes.
- Adds fail-closed artifact owner, manifest, canonical hash, and compatibility-mirror validation plus lossless legacy-layout migration.

## 1.0.30

- Requires execution-stage `test_implementation` and `ui_conformance` reviewers to finish one shared-snapshot discovery round before the coordinator freezes findings, batch-remediates them, and runs one unified re-review.
- Keeps the 2% critical-region and 5% full-surface pixel targets, but performs two distinct systematic remediation rounds before proactively requesting a user decision.
- Adds canonical `record_task_visual_conformance_adjudication()` evidence for explicit pixel-only acceptance; structural, semantic, geometry, interaction, unstable-environment, and missing-evidence failures remain non-overridable.
- Persists visual retry attempts, stable pending decisions, pixel-diff PNGs, adjudication artifacts, and hash-linked transition evidence while invalidating them on baseline, task, policy, or implementation changes.
- Requires final `ui_conformance.accepted_visual_deviations` to match every current user-adjudicated deviation and keeps closure schema `v0.11`.

## 1.0.29

- Derives the authoritative TASK queue from planned E2E obligations by user journey instead of extracting coverage-matrix TASK numbers.
- Splits overloaded journeys when action assertions, coverage items, surfaces, or primary happy paths exceed the slice thresholds, and rejects collection obligations larger than three items.
- Binds each TASK to its own obligation set and prototype surfaces; the first journey absorbs the minimum shell, and independent scaffold TASKs are forbidden.
- Lets agents refine titles, descriptions, verification text, and narrower bindings only. Merging TASKs, moving E2E, or expanding bindings fails closed.
- Rewrites coverage `task` columns, includes `task_queue_hash` in test-coverage review and user confirmation, and requires `record_task_executed_evidence()` plus prototype conformance before a TASK can complete.
- Accepts final `record_executed_browser_evidence()` only as the union of recorded slice evidence plus optional regression.
- Grandfathers active deliveries that already confirmed `test_coverage_plan` until that plan is reopened, and keeps canonical closure schema `v0.11` unchanged.

## 1.0.28

- Derives a read-only `implementation_baseline` from the confirmed prototype design bundle and contract, including exact surface, state, viewport, region, interaction, screenshot, and visual-policy identities.
- Requires every user-visible UI TASK to declare `ui_impact` and exact `prototype_bindings`; non-UI TASKs must explicitly record why they do not affect visible UI.
- Adds focused Goal and current-task prompts that treat the confirmed prototype as authoritative and prohibit silent redesign or degradation.
- Adds `record_task_prototype_conformance()` with fail-closed route, structure, semantic, interaction, geometry, computed-style, and pixel evidence before a UI TASK can complete.
- Binds launch authorization and completion reuse to the implementation baseline, task, and conformance hashes; product, mask, threshold, or task-binding changes stale downstream evidence while annotation-only changes do not.
- Keeps active confirmed UI deliveries grandfathered until their prototype is reopened, and keeps canonical closure schema `v0.11` unchanged.

## 1.0.27

- Adds a `runtime_provenance` receipt to every newly activated delivery: external Waygate plugin name, release version, package-root digest, nonempty delivery ID, owner metadata, and a hash-linked `delivery_activated` journal event.
- Makes `status()` expose `verified_waygate`, `legacy_unverified`, or `invalid_runtime`; active state lacking a complete current receipt cannot progress through any delivery gate.
- Adds `recover_legacy_active_delivery()` as the only recovery path for an unverifiable or foreign runtime state. It archives the exact legacy state before creating a new Waygate delivery, so no legacy confirmation, review, or implementation authorization can be reused.
- Replaces legacy `product-delivery-agent@repo-local` during installation after checking config, Codex cache, and installed-plugin registry, then asserts that the enabled product-delivery selection is only `waygate-product-delivery@repo-local`.
- Bumps the package release to invalidate prior runtime provenance and refreshes generated plugin artifacts.

## 1.0.26

- Captures the top-level delivery coordinator from `CODEX_THREAD_ID` and binds Host Goal checkpoints, observations, and canonical post-handoff writes to that owner.
- Requires the observed Codex Goal `threadId`, the stored coordinator, the binding owner, and the current runtime thread to match; missing or foreign thread identity now fails closed.
- Adds `inspect_host_goal_owner_context()`, `prepare_host_goal_owner_claim()`, and `record_host_goal_owner_claim_observation()` for explicit recovery in a fresh user-visible top-level thread.
- Adds `recover_stale_host_goal_owner_claim()` and the hash-linked `host_goal_owner_claim_superseded` transition so a legal intervening transition cannot permanently wedge an owner transfer checkpoint.
- Migrates nonterminal pre-v1.0.26 states to `host_goal_owner.status=legacy_unverified` without inferring that an old binding thread was the delivery coordinator.
- Archives an old binding and its pending checkpoint as `orphaned_unreachable`, appends `host_goal_owner_transferred`, and creates a fresh generation, nonce, and exact objective only after the candidate thread reports a missing or completed Goal.
- Rejects owner transfer when the candidate thread already has an active or blocked Goal, and explicitly prohibits spawned review subagents from owning or recovering the delivery Host Goal.
- Makes `status()` read-only for existing state, requires reconciliation for post-handoff pause/resume, and treats blocked Goals as explicit user-resume gates.
- Keeps canonical closure schema `v0.11` unchanged.

## 1.0.25

- Adds `recover_stale_host_goal_checkpoint()` for a pre-active Host Goal activation checkpoint invalidated by later legal state transitions.
- Archives the complete superseded checkpoint, stored/current projections, intervening transition range, and runtime versions without resetting the delivery or rewriting prior journal events.
- Records a hash-linked `host_goal_checkpoint_superseded` transition, preserves binding generation, nonce, authorization, and objective, then restarts the exact `get_goal` -> `create_goal` -> `get_goal` handshake.
- Fixes Host Goal projection binding to use the real transition event sequence and `last_event_hash` instead of the transition-journal object's fixed key count.
- Rejects replay, identity mismatch, damaged journals, and recovery after the binding was ever active while keeping legacy v1.0.24 checkpoint metadata recoverable.
- Explicitly prohibits mixing the legacy `product-delivery-agent@1.0.8` runtime into an active Waygate delivery.
- Keeps canonical closure schema `v0.11` unchanged.

## 1.0.24

- Separates the internal `delivery_goal` task plan from a verified Codex `host_goal_binding` tied to the current delivery, launch package, authorization, and objective hash.
- Adds `prepare_host_goal_activation()`, `prepare_host_goal_reconciliation()`, `record_host_goal_observation()`, `recover_host_goal_binding()`, and `authorize_host_goal_reactivation()`.
- Requires the initial `get_goal` -> `create_goal` -> `get_goal` handshake and fresh one-time reconciliation checkpoints before post-handoff canonical transitions.
- Rejects Goal observations that lack a stable host `threadId`, `goalId`, or `id`, and enforces identifier continuity after creation.
- Covers legacy and draft-producing post-handoff write paths with the same reconciliation gate; replaying the current handoff no longer resets an active Goal binding.
- Records Goal-tool unavailability as a fail-closed blocker, and requires explicit reauthorization after a once-active Goal becomes missing or prematurely complete.
- Gives human decisions stable `decision_id`, prompt hash, and blocker identity; repeated automatic turns do not repeat the prompt or mutate delivery evidence.
- Resolves explicit clarification blockers only after an observed active Goal and resets consecutive wait evidence whenever an intervening Goal turn no longer observes the blocker.
- Allows `update_goal(status=blocked)` only after three distinct Goal turns observe the same unresolved decision, and allows `update_goal(status=complete)` only after canonical closure passes.
- Requires verified Goal completion before the formal final summary, while keeping canonical closure schema `v0.11` unchanged.
- Explicitly rejects a 20-second watchdog or synthetic `继续`; automatic continuation may only be claimed after a real Codex Host Goal auto-reentry smoke passes.

## 1.0.23

- Adds the internal `prototype_design_integrity` gate and public `record_ui_prototype_design_bundle()` API before multi-Agent product/scenario review.
- Separates the user-facing `clean_surface` from the external `review_annotation_set`, and rejects product prototypes that load review overlays, scripts, assets, or annotation modes.
- Requires fixed-schema semantic snapshots, browser-preflight probe artifacts, screenshot/snapshot/region hash binding, and structured hashed evidence for every product-context dimension; caller-reported pass flags are not trusted.
- Requires positive product-context coverage for global shell, navigation, visual language, information density, component system, and responsive behavior across required states and viewports.
- Splits bundle identity into `product_domain_hash`, `review_domain_hash`, and the complete relation `bundle_hash`; annotation-only changes stale internal review without invalidating either user confirmation.
- Clarifies the responsibility boundary: 门禁验证客观事实，多 Agent 判断设计质量；review cannot override a failed deterministic gate or use empty findings as positive coverage.
- Presents only clean product prototypes and screenshots during `product_baseline`, while keeping exactly two user confirmations: `product_baseline` and `test_coverage_plan`.
- Grandfathers active v1.0.22 deliveries with an already confirmed product baseline until the prototype changes or the baseline is reopened; unconfirmed UI deliveries fail closed until the bundle is recorded.
- Keeps canonical closure schema `v0.11` unchanged.

## 1.0.22

- Removes plugin-managed automatic/full-speed model selection, model profiles, and model identity gates; 模型选择完全由用户和 Codex 宿主管理。
- Keeps model-related legacy APIs for one release as explicit retirement errors instead of silently ignoring unsupported parameters.
- Adds idempotent `retire_model_execution_policy()` recovery for active v1.0.19-v1.0.21 deliveries without restarting the delivery or editing state by hand.
- Preserves delivery isolation and layered `product_baseline` / `test_coverage_plan` confirmations while removing obsolete model and legacy confirmation blockers.
- Requires spawned multi-Agent review artifacts to record 2-3 unique `reviewer_agent_ids` and a real `reviewer_spawn_source`; model names are not review evidence.
- Scopes docs-ahead checks to the current feature section and records new events with current timestamps rather than reusing stale state timestamps.
- Keeps canonical closure schema `v0.11` unchanged.

## 1.0.21

- Replaces the early prototype plus combined freeze flow with two layered formal confirmations: `product_baseline` and `test_coverage_plan`.
- Requires Open Spec, scenario matrix, UI prototype or non-UI behavior contract, and product/scenario review before the first confirmation; detailed test design is blocked until that baseline is confirmed.
- Adds `prepare_product_baseline_confirmation()`, `confirm_product_baseline()`, `prepare_test_coverage_confirmation()`, and `confirm_test_coverage_plan()` with hash-bound nonces.
- Preserves product confirmation during internal test hardening and requires `record_user_requested_change()` before revising confirmed product or coverage semantics.
- Migrates active legacy prototype pending confirmations back to product/scenario review while keeping terminal delivery history read-only.
- Keeps canonical closure schema `v0.11` unchanged.

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
