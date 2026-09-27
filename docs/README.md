# Documentation Registry

This directory stores formal documentation for the Waygate Product Delivery project. Planning files in the project root record process state; formal docs in `docs/` record durable product, architecture, workflow, and operations decisions.

## Directories

| Directory | Purpose |
| --- | --- |
| `docs/product/` | Product positioning, target users, value proposition, and methodology rationale. |
| `docs/architecture/` | System boundaries, integration model, and future module design. |
| `docs/workflow/` | Product-to-delivery process, phase contracts, gates, and handoff rules. |
| `docs/operations/` | Future setup, runbook, and tool operation notes. |
| `docs/open-spec/` | Versioned Open Spec packages for the Waygate Product Delivery plugin roadmap. |

## Current Documents

| Document | Purpose |
| --- | --- |
| `CHANGELOG.md` | Release ledger and compact post-1.0 version direction. |
| `docs/product/product-delivery-workflow-agent.md` | Product value, target users, non-goals, and success criteria. |
| `docs/workflow/product-to-delivery-methodology.md` | Full methodology from product blueprint to final evidence. |
| `docs/architecture/system-boundaries.md` | Boundary between this project, Waygate, Claude workflow, Codex goal, and Open Spec. |
| `docs/operations/README.md` | Placeholder for future operational documentation. |
| `docs/operations/sample-product-delivery-monitoring.md` | Read-only monitoring report for a sample Product Delivery trial run. |
| `docs/operations/product-delivery-agent-hardening-plan.md` | Improvement plan derived from monitored Product Delivery failures. |
| `docs/operations/waygate-product-delivery-installation.md` | Build, package, install, and smoke-test instructions for the `waygate-product-delivery` Codex plugin. |
| [Open Spec packages](open-spec/README.md) | V0.1–V1.1 文档包与 V1.2 路线图；文档状态与运行时发布状态分开记录。 |
| [V1.1 评审专家团产品需求](open-spec/v1.1-multi-agent-review-orchestration/01-requirements.md) | CR-002：角色职责、专家组合、用户流程与验收；设计目标版本 1.1.0。 |
| [V1.1 技术与存储架构](open-spec/v1.1-multi-agent-review-orchestration/03-technical-solution.md) | 本地专家团编排、owner 权威、证据投影与中断恢复设计；尚未实施。 |

角色设定入口：[V1.1 八角色任务书与40个质量例子](open-spec/v1.1-multi-agent-review-orchestration/09-role-cards.md)。
