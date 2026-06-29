# V0.5 Hooks And Recovery Guardrails - 03 Technical Solution

| Field | Value |
| --- | --- |
| Version | V0.5 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.5 Hooks And Recovery Guardrails. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record pure hook helper module and guardrail flow. | CR-001 |


## Solution Boundary

This version package implements `V0.5 - Hooks And Recovery Guardrails` as pure local helper functions in `src/product_delivery_agent/hooks.py`.
The helpers are ready to be bound to future Codex plugin hooks, but V0.5 intentionally does not implement plugin packaging or external hook registration.

## Modules And Responsibilities

- `HookResult`: reviewable hook result with `active`, `silent`, `message`, `warnings`, `missing_items`, and `passed`.
- `build_resume_context`: session start/resume context builder for active projects.
- `build_prompt_context`: user prompt context builder for active projects.
- `check_pre_compaction`: state durability guardrail before compaction.
- `check_stop_guardrail`: missing confirmation/artifact guardrail before stop.
- Active/inactive detector: enforces silent no-op behavior outside active Product Delivery projects.

## Key Flow

1. A future hook entrypoint calls the matching V0.5 helper.
2. The helper reads local `.product-delivery/state.json`.
3. If the project is inactive or state is absent, the helper returns a silent `HookResult`.
4. If the project is active, the helper returns recovery context or guardrail findings derived from state and local artifact paths.
5. The helper does not write runtime state and does not mutate Waygate/controller state.

## Architecture Decision Records

| ADR | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Use Codex-native Agent Plugin as the product form. | Keeps the first product surface close to the target agent workflow. |
| ADR-002 | Use dormant-by-default activation. | Prevents plugin installation from interfering with normal Codex work. |
| ADR-003 | Prefer local artifacts over chat context for recovery. | Reduces compaction and resume drift. |
| ADR-004 | Use separate UI and non-UI confirmation gates. | Keeps prototype review from being forced onto non-UI work. |
| ADR-006 | Hooks are guardrails and remain silent for inactive projects. | Preserves non-interference and avoids hook-driven state ambiguity. |
| ADR-007 | Implement hooks as pure helpers before plugin packaging. | Enables TDD verification now while deferring concrete Codex hook registration to V1.0. |

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| Activation misfire | Require explicit start and inactive silence. | Return to inactive state with artifacts preserved. |
| Context loss | Use state/artifact precedence. | Resume from last confirmed artifact. |
| Branch routing error | Route by project_type and confirmation gate. | Return to project type selection. |
| Scope drift after freeze | Require return to version scope confirmation. | Unfreeze only through scope confirmation. |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Implementation-specific architecture diagrams and API contracts are deferred to later scoped versions. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Implementation details remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
