# Open Spec Packages

This directory contains versioned Open Spec packages for the Product Delivery Agent Plugin roadmap.

| Version | Package | Goal |
| --- | --- | --- |
| V0.1 | [Roadmap And Product Definition](./v0.1-roadmap-and-product-definition/01-requirements.md) | Complete the product shape, capability boundary, version route, and skill allocation for the Codex-native Product Delivery Agent Plugin. |
| V0.2 | [Artifact And State Protocol](./v0.2-artifact-and-state-protocol/01-requirements.md) | Define the local state and artifact protocol the plugin will use. |
| V0.3 | [Local Skill Workflow Prototype](./v0.3-local-skill-workflow-prototype/01-requirements.md) | Validate the product delivery workflow with a repo or local skill before packaging a plugin. |
| V0.4 | [Skill Allocation And Review Gates](./v0.4-skill-allocation-and-review-gates/01-requirements.md) | Explicitly include the Waygate README recommended skills in the workflow. |
| V0.5 | [Hooks And Recovery Guardrails](./v0.5-hooks-and-recovery-guardrails/01-requirements.md) | Preserve workflow continuity across compaction, resume, and long sessions. |
| V0.6 | [UI Prototype Gate](./v0.6-ui-prototype-gate/01-requirements.md) | Provide local 1:1 HTML prototype confirmation for UI projects. |
| V0.7 | [Non-UI Behavior Contract Gate](./v0.7-non-ui-behavior-contract-gate/01-requirements.md) | Provide a behavior confirmation gate for non-UI projects. |
| V0.8 | [Test Coverage Audit](./v0.8-test-coverage-audit/01-requirements.md) | Confirm test obligations before implementation handoff. |
| V0.9 | [Codex Goal Handoff](./v0.9-codex-goal-handoff/01-requirements.md) | Generate a frozen version package that can be handed to implementation Codex. |
| V0.10 | [Feature Closure Gate](./v0.10-feature-closure-gate/01-requirements.md) | Require formal closure gate and a version-specific closure artifact after implementation. |
| V1.0 | [Codex Plugin Packaging](./v1.0-codex-plugin-packaging/01-requirements.md) | Package the stable workflow as an installable Codex plugin. |
| V1.1 / 1.1.0 | [Review Expert Panel Orchestration](./v1.1-multi-agent-review-orchestration/01-requirements.md) | CR-004：复合席位整合已实现，保留8个逻辑角色并固定每gate两个reviewer席位；[八角色任务书](./v1.1-multi-agent-review-orchestration/09-role-cards.md)。完整PanelRun仍待实施，未发布。 |
| V1.2 / 1.2.0 | [Stage-Based Expert Production Orchestration（路线图）](../../ROADMAP.md#v12---stage-based-expert-production-orchestration) | 后续按阶段引入生产专家；尚无独立 Open Spec 包。 |

## V1.1 当前修订边界

`CR-002 / REV-20260926-01` 基于当前 1.0.42 源码更新 00–04 与 08。CR-003 / REV-20260926-02 已补角色卡/任务契约增量的 TASK、TC 和实现证据；05/06/07仍保留CR-001历史，旧TASK/TC/PASS不作为新范围证明。完整PanelRun和四个编排API仍是目标架构；源码和打包版本保持1.0.42。

## Rules

- V1 supports both UI and non-UI projects.
- Only UI projects use the local 1:1 HTML prototype gate.
- Non-UI projects use behavior contract confirmation.
- All projects pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Codex Goal handoff does not replace formal closure after implementation.
- Chat summaries and `progress.md` are summaries only; they do not replace the version-specific closure artifact.
- Plugin behavior is dormant until explicit project-level `start`; `pause`/`resume` preserve the delivery, `close` follows validated closure, and `abandon` ends it through the existing two-step protocol. `stop` is retired.
