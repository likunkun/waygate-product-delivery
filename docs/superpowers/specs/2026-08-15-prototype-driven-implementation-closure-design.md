# V1.0.28 Prototype-Driven Implementation Closure Design

## Problem

The confirmed UI prototype is protected before implementation and checked again at final closure, but the implementation handoff does not carry the prototype baseline into individual tasks. The current generated queue reduces coverage rows to generic TASK IDs, and task completion validates only a command result. Production conformance intentionally verifies semantic mapping without requiring pixel comparison. A functionally passing implementation can therefore replace the confirmed information architecture, journey, or visual system before the final review notices.

## Decision

V1.0.28 adds a lightweight closed loop using the evidence already produced by the prototype bundle and Playwright workflow. New UI deliveries freeze an `implementation_baseline`, bind every visible UI task to concrete prototype units, generate a focused prompt for the current task, and require task-level conformance before completion. Existing full-stack browser evidence, production conformance, and independent UI review remain the final authority.

The prototype is an authoritative product sample, not production source code. Implementations may use the repository's existing framework and architecture, but they may not silently redesign visible structure or behavior.

## Architecture

### Implementation baseline

After `product_baseline` confirmation, the runtime rebuilds the current canonical design bundle and contract and writes `artifacts/implementation-baseline.json`. The baseline contains:

- the confirmed product-domain, bundle, contract, prototype HTML, screenshot-set, and design-system identities;
- one immutable unit for every required `surface_id + state_id + viewport`;
- the unit route, critical regions, relationships, interactions, reference screenshot, and prototype semantic bounds;
- a frozen visual policy and policy hash;
- a stable baseline hash used by launch authorization, prompts, task evidence, and closure state.

The default visual policy is:

- critical-region maximum diff ratio: `0.02`;
- full-surface maximum diff ratio: `0.05`;
- normalized per-channel pixel threshold: `0.2`;
- geometry tolerance: the larger of `4` CSS px or `1%` of the viewport dimension;
- no dynamic masks.

Projects may make thresholds stricter and declare region-based dynamic masks before product-baseline confirmation. The policy participates in the product surface hash. It cannot be relaxed after confirmation without reopening the product baseline.

### Task contract and prompts

Normalized tasks add:

- `ui_impact`: `prototype_bound` or `none`;
- `ui_impact_reason`: required when the impact is `none`;
- `prototype_bindings`: surface/state identities, required viewports, regions, and interactions.

Explicit task queues for new UI deliveries must provide these fields. Coverage-derived queues inherit the critical baseline units automatically because their source rows do not currently carry surface IDs. Non-UI and grandfathered UI queues keep their current schema behavior.

The Goal prompt contains stable authority and change-control rules plus the baseline identity. `current-task-prompt.md` contains only the current task's bound units, artifact paths, hashes, required invariants, and verification command. It is regenerated at handoff and after every task completion.

### Task conformance

`record_task_prototype_conformance(task_id, payload)` validates the current task against the frozen baseline and writes one canonical JSON artifact. For each bound unit it:

- checks the production route and controlled semantic snapshot against required regions, hierarchy, order, accessible identity, relationships, and interactions;
- checks production screenshot identity and dimensions;
- compares prototype and production PNG pixels using the frozen full-surface and critical-region thresholds;
- compares prototype semantic bounds with production bounding boxes using the frozen geometry tolerance;
- requires computed-style comparison records for critical regions and rejects any mismatch;
- binds all results to the baseline hash and planned-task hash.

An unstable capture environment records `inconclusive`; missing or mismatching evidence records `failed`. Neither status authorizes task completion. Automated failures cannot be overridden by an internal reviewer. A deliberate product difference requires a change request and a reopened baseline.

### Staleness and compatibility

The implementation-baseline hash is included in the launch package. Product-domain or visual-policy changes stale the baseline, task conformance, launch authorization, and downstream implementation evidence. Annotation-only review-domain changes do not.

New UI deliveries started and classified under V1.0.28 require the policy. Existing UI deliveries without V1.0.28 policy metadata remain grandfathered while their confirmed product baseline stays current. Recording a changed product-domain bundle after reopening a grandfathered baseline upgrades that delivery to the new policy. Non-UI deliveries are unaffected.

## Acceptance

- A new UI handoff cannot authorize an explicit visible task without valid prototype bindings.
- Goal and current-task prompts identify the exact frozen baseline and prohibit redesign.
- A functionally passing implementation with a wrong route, hierarchy, interaction, geometry, style, or screenshot cannot complete its UI task.
- Corrected production evidence can pass without changing the baseline or adding a user confirmation.
- Final production conformance and UI review remain mandatory.
- Legacy confirmed UI deliveries and all non-UI deliveries preserve their existing behavior.
- Packaged source/runtime parity and all existing tests pass at plugin version `1.0.28` with closure schema `v0.11`.
