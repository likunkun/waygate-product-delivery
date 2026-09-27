# V1.1 Multi-Agent Review Orchestration - 05 Development Plan

| Field | Value |
| --- | --- |
| Version | 1.1.0（CR-004 复合席位实施增量；完整 panel 仍为目标架构） |
| Author | Codex |
| Date | 2026-09-26 |
| Status | CR-004 复合席位实现与验证完成；未发布 |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Planning-only development plan. No implementation started. | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex | 保留实施计划历史正文，标记待按 CR-002 同步 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex / Open Spec Implementation | 补充 22 字段角色卡、逐角色任务书、任务绑定、最小输入、证据分类和 CR-004 复合席位增量；完整 panel run/四 API 保持目标架构。 | CR-003 |
| REV-20260926-03 | 2026-09-26 | Codex / Open Spec Implementation | 复合席位、席位身份、兼容和测试交接。 | CR-004 |

## 当前状态与续接边界（CR-003 / REV-20260926-02）

用户已批准并要求实现角色卡/专家任务契约增强；本阶段按现有授权继续实施，不新增人工开工确认。当前交付只覆盖 RoleCard、task builder、result validator 和可选 role result review 投影。完整 PanelRun、四 API、事件屏障、自动派发/恢复、receipt 和 canonical snapshot 提交仍是 CR-002 目标架构，不在本次完成声明中。

以下 `TASK-ROLE-101～106` 为 CR-003 新增实施任务，不复用历史 `TASK-001～007`。表内完成度指已验证的 DoD 验收比例，不代表代码编写比例。完成度以可复核成果为准：文档任务完成不代表代码任务或产品测试已通过；主线程据实际验证更新代码与测试状态。

## CR-003 任务分解（历史实现增量）

| TASK | 实施范围 | FR / NFR 映射 | 方案/规范锚点 | 依赖 | 状态 / 完成度 | DoD 与证据 |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-ROLE-101 | 八角色 22 字段与逐角色任务书、每角五类具体例子、业界借鉴说明 | FR-018、FR-020；NFR-007～008 | 02 RoleCard；03 review_profiles；09 全文 | 已批准 CR-003 | 已完成 / 100%（文档） | 00～03 与 09 一致；8 角色、40 例、通过例对象/证据/检查/结果齐全；字段与任务边界静态校验。 |
| TASK-ROLE-102 | RoleCard 命名字段构造、类型/语义校验、定义/template hash | FR-018、FR-019、FR-021；NFR-007 | 02 RoleCard；03 CR-003 路线 1 | TASK-ROLE-101 | 已完成 / 100%（定向与全量验证） | 八卡能返回完整契约；缺字段/错位类型拒绝；完成标准、升级条件、peer 契约分离；定向测试通过。 |
| TASK-ROLE-103 | 构建 delivery/project_type/input_snapshot/role/task hash 绑定的最小任务单 | FR-002、FR-019～022；NFR-005、NFR-008～010 | 02 RoleTask；03 路线 2 | TASK-ROLE-102 | 已完成 / 100%（定向与全量验证） | 必需输入齐全；UI/non-UI 正确；首轮无 peer/预设结论；不扩大输入；绑定变化测试通过。 |
| TASK-ROLE-104 | 结构化角色结果校验、逐 check/completion 证据、分类和越权拒绝 | FR-008、FR-019～022；NFR-001～003、NFR-009 | 02 RoleResult；03 路线 3 | TASK-ROLE-102～103 | 已完成 / 100%（定向与全量验证） | 检查/完成标准逐项有证据；空/错证据、悬空 blocker、passed 带 blocker、身份冒充和写意图均拒绝；定向测试通过。 |
| TASK-ROLE-105 | 可选角色结果接入既有 review 投影和兼容校验 | FR-012、FR-017、FR-019、FR-021～022；NFR-004、NFR-006 | 02 AC-ROLE-006；03 路线 4 | TASK-ROLE-104 | 已完成 / 100%（定向与全量验证） | 提供角色结果时按五个 profile 校验；owner 路径复用原 gate validator；旧 review 可读且不伪称完整 panel。 |
| TASK-ROLE-106 | 定向回归、文档/实现一致性审查、实施与测试交接 | FR-018～022；NFR-001～010 | 02 AC-ROLE-001～006；03 路线 5 | TASK-ROLE-101～105 | 已完成 / 100%（定向与全量验证） | 06 使用新 TC 映射；缺字段/绑定/泄漏/证据/身份/兼容负面路径通过；主线程记录实际命令与结果。 |

## CR-003 里程碑

| 里程碑 | 内容 | 可验收结果 | 状态 |
| --- | --- | --- | --- |
| M-ROLE-1 | 可读且无歧义的角色契约 | 八角色任务书、22 字段、五类例子和当前实现范围一致 | 已完成（文档） |
| M-ROLE-2 | 任务和结果最小可信边界 | 定向测试验证输入最小化、任务绑定、逐项证据和拒绝语义 | 已完成 |
| M-ROLE-3 | 可选投影与兼容验证 | 原 review gate 仍为权威；受影响回归通过；没有完整 panel 完成声明 | 已完成 |
| M-ROLE-4 | 阶段交接 | 06/08 记录新 TASK/TC、实际验证和剩余目标架构 | 已完成 |

## 实施进展、偏差与纠偏

| 项目 | 当前事实 / 偏差 | 责任与纠偏 | 退出条件 |
| --- | --- | --- | --- |
| 文档基线 | CR-002 曾止于设计，旧 05 不含当前增量 TASK | 文档 Agent 完成 CR-003 新 TASK 和 09 任务书；保留 CR-001 历史 | TASK-ROLE-101 完成 |
| 字段语义 | 初始 RoleCard 构造参数有错位风险，不能将现有缺陷写成规范 | 实现 Agent 改为明确字段构造/校验，分离 completion/escalation/peer | TASK-ROLE-102 定向测试通过 |
| 结果可信度 | 单一总证据引用与 checked ID 列表不足以证明逐项完成 | 实现 Agent 添加 check_records、completion_evidence 和绑定校验 | TASK-ROLE-104 负面测试通过 |
| 阶段边界 | 本次未实现完整 panel/四 API，不能以角色配置推断自动编排能力 | 主线程在 06/08/最终交接保留后续架构清单 | TASK-ROLE-106 完成 |

## 本轮信息缺口

| 等级 | 项目 | 处理 |
| --- | --- | --- |
| Blocker | 无已知外部输入阻塞；角色增强代码与测试已完成 | TASK-ROLE-102～106 已通过定向52项及全量582项验证；不重复询问批准。 |
| Assumption | 现有 review 投影保持可选；完整 panel 的强制 activation policy 待后续实现 | 本次不升级历史 delivery，不新增确认节点。 |
| Nice-to-know | 完整 panel 的计时、恢复、receipt、用量和质量收益 | 继续保留 CR-002 目标架构，不作本次验收承诺。 |

## 当前阶段门禁

**PASS（CR-003 角色增强）**：TASK-ROLE-101～106 已完成；定向52项、全量582项通过，源码/打包一致性、编译、插件结构与文档链接检查通过。证据见 [验证记录](evaluation/verification.json) 与06/08。此结论不包含CR-002完整PanelRun、正式发布或canonical closure。

---

## CR-004 复合席位实施增量（REV-20260926-03）

| TASK | 实施范围 | FR 映射 | 状态 |
| --- | --- | --- | --- |
| TASK-SEAT-201 | 固定五 gate、两个席位和八角色覆盖映射 | FR-025 | 已完成 |
| TASK-SEAT-202 | 席位任务 hash、同席共享身份、跨席唯一身份校验 | FR-026～027 | 已完成 |
| TASK-SEAT-203 | workflow/gatekeeper/state/artifact 席位摘要与 stale | FR-027～028 | 已完成 |
| TASK-SEAT-204 | 复合席位测试、兼容测试、打包和全量回归 | FR-025～028 | 待最终验证 |

本增量不实现完整 PanelRun、事件屏障、自动调度或 V1.2 生产专家。

## CR-001 历史草案（仅供追溯，不作为执行指令）

## Preconditions Before Implementation

Implementation is blocked until Product Delivery gates are satisfied:

- `non_ui` behavior contract is recorded and confirmed.
- Scenario matrix and `multi_agent_scenario_review` pass.
- Planned coverage obligations, test coverage audit, and `multi_agent_test_coverage_review` pass.
- Canonical `implementation_launch_authorization` is recorded with the required user phrase: `确认按当前交付包开始实现`.

All TASK statuses below are `未开始`.

## TASK Breakdown

| Task | Scope | FR Mapping | Solution Mapping | Dependencies | Status |
| --- | --- | --- | --- | --- | --- |
| TASK-001 | Add `review_orchestration.py` with review profiles, reviewer responsibilities, input snapshot builder, prompt payloads, artifact assembly, and blocked results. | FR-001, FR-002, FR-003, FR-004, FR-005, FR-013 | New Module; Key Flow; ADR-001/003/004 | Preconditions, TASK-007 RED tests | 未开始 |
| TASK-002 | Integrate V1.1 validation in `review_gates.py`: exact review type, deliberation fields, review mode semantics, split gate non-substitution, collection coverage, false-positive risks. | FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-014, FR-015 | Existing Module Changes; ADR-002 | TASK-007 | 未开始 |
| TASK-003 | Add workflow-facing orchestration helpers in `workflow.py`; route accepted artifacts through existing `record_multi_agent_review` without bypassing canonical validation. | FR-002, FR-003, FR-004, FR-005, FR-008, FR-012 | Existing Module Changes; Scenario/Test Coverage/Test Implementation Flows | TASK-001, TASK-002 | 未开始 |
| TASK-004 | Extend artifact/state metadata additively in `artifact_protocol.py`: optional input snapshots, reviewer mirrors, gate results, blocked reasons; preserve existing shape. | FR-007, FR-012, NFR-001, NFR-002, NFR-004, NFR-005 | Storage Model; State Fields; Migration And Compatibility | TASK-001, TASK-002 | 未开始 |
| TASK-005 | Harden `gatekeeper.py` blockers so split reviews, unresolved blocking findings, wrong modes, substituted review types, and summary/status/custom-only review claims fail closed, including non-UI pre-handoff/pre-closure split gates. | FR-006, FR-008, FR-010, FR-011, FR-014, FR-015, FR-016, FR-017 | Existing Module Changes; Risk And Rollback | TASK-002, TASK-004 | 未开始 |
| TASK-006 | Update packaging/docs/templates in `plugin_packaging.py` and packaged skill text for V1.1 orchestration rules, artifact templates, non-UI split gate authority, and structured artifact-only gate semantics. | FR-001..FR-017, NFR-001..NFR-006 | Plugin Packaging; Observability And Evidence; Rollback | TASK-001..TASK-005 | 未开始 |
| TASK-007 | Add RED-first tests for orchestration profiles, prompt/input snapshots, split gate substitution rejection, degradation policy, artifact/state persistence, non-UI gatekeeper blockers, summary/status-only bypass rejection, and packaging/docs. | All FR/NFR | Tests; Risk And Rollback | Preconditions for implementation | 未开始 |

## Milestones

| Milestone | Contents | Exit Criteria | Status |
| --- | --- | --- | --- |
| M1 | RED tests and orchestration contract | Tests fail for missing orchestration/profile/snapshot behavior | 未开始 |
| M2 | Core orchestration and validation | `review_orchestration.py` plus `review_gates.py` tests pass | 未开始 |
| M3 | Workflow/state/gatekeeper integration | Canonical record path and fail-closed blockers pass tests | 未开始 |
| M4 | Packaging/docs consistency | Packaged templates and skill text include V1.1 rules | 未开始 |
| M5 | Regression verification | Existing review, launch, closure, packaging tests pass | 未开始 |

## Implementation Status

No code implementation has started. No TASK is in progress. No 06/07 artifacts are generated yet.

## Blockers And Correction

| Blocker | Impact | Correction |
| --- | --- | --- |
| Behavior contract not confirmed | Non-UI branch evidence is not implementation-ready | Record and confirm current feature behavior contract |
| Scenario review missing | Freeze gate cannot pass | Complete structured `scenario` review with real spawned subagents; current `spawned_subagents_required` policy does not allow `role_simulation` degradation |
| Scenario review carry-forward blockers | Current draft must explicitly cover non-UI split gate enforcement and summary/status/custom-only artifact bypass rejection | Revise requirements, specification, plan, tests, release draft, and handoff before scenario review can pass |
| Planned coverage/test review missing | Pre-handoff cannot pass | Complete planned obligations, coverage audit, and `test_coverage` review |
| Implementation launch authorization missing | Coding cannot start | Record canonical authorization after gates pass |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | Implementation launch authorization is missing. | Coding cannot begin. | Expected Product Delivery gate; do not implement yet |
| Blocker | Behavior contract, scenario review, and planned coverage gates are missing. | Pre-handoff cannot pass. | Prepare and confirm gate artifacts before TASK execution |
| Blocker | Scenario review identified missing explicit coverage for non-UI split gates and status-only/custom artifact bypass rejection. | Scenario review cannot pass until documents and planned tests cover those risks. | Apply documentation/test revisions and rerun structured scenario review |
| Assumption | TASK-007 RED tests should be written before implementation changes. | Keeps implementation test-driven and prevents shallow orchestration. | Carry forward |
