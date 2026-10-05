# V1.2.0 团队生产编排变更请求

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Codex / Open Spec Lead |
| 日期 | 2026-09-29 |
| 状态 | 已批准范围；文档、生产实现与真实 UI/non-UI 宿主演练已对齐，正式 closure 演练完成 |
| 源基线 | V1.1.0 多 Agent 评审编排 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立 V1.2 生产团队编排的需求、规范、方案、任务、测试与交接文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 对齐实际阶段、并发上限、TASK 绑定与独立授权契约。 | CR-005 |

## 变更请求

- **CR ID**：CR-005
- **类型**：向后兼容的生产编排增强
- **目标版本**：1.2.0
- **授权**：用户已批准实施范围；本文件不再次请求批准。

## 背景与目标

V1.1 已有八个逻辑评审角色，实际以每个 gate 两个 reviewer seat 运行，并保留 gate 权威、独立意见、交叉质疑和复验约束；fullPanelRun 尚未实现。V1.2 增加一条与评审授权分离的生产团队路径：由主协调者担任阶段负责人，按六个生产阶段派发有限生产任务，成员只在 staging 副本或 patch 上工作，owner 合并并写入 canonical 状态。

目标是让产品定义、架构与版本计划、Open Spec 产品面、测试设计、实施执行和交付准备形成可恢复、可追溯的生产协作，同时继续保护既有启动输入理解、产品基线、测试覆盖确认、HostGoalOwner、TASK 与 canonical closure。

## 范围

**In scope**

- startup.production_mode_if_created 取值 coordinator|team；默认不改变既有 coordinator。
- set_production_mode 仅允许在同一版本的安全边界内调用；跨版本切换必须拒绝并保持原 mode。
- 与 review authorization 分离的 team authorization 与成员权限。
- 六个固定阶段：product_definition、architecture_version_planning、open_spec_product_surface、test_design、implementation_execution、delivery_preparation。
- 十个核心生产角色和五个条件角色（见 09-production-role-cards.md）。
- 每轮允许按依赖图安排多个 production work packages，同时最多两个处于 running；仅 implementation_execution 绑定当前 canonical TASK。
- ProductionRoleCard、StageProfile、ProductionTask、ProductionResult、TeamRun 契约。
- prepare_team_run、inspect_team_run、record_team_events、integrate_team_run、finalize_team_run 五个 owner API。
- 每次成员执行的 timeout_seconds=1800；每个 work package 运行周期最多一次 recovery 和一次 remediation；revision CAS、event_id 幂等及 stale/late 拒绝。
- staging copy/patch 的 pre/post hash、无覆盖合并和恢复。
- review freeze（独立评审→交叉评审→revision barrier）后由 owner 批量派发修复；生产成员不得评审自己贡献的 artifact。
- UI 和非 UI 的真实 host exercise，以及质量、返工、时间/用量对照数据；不预设收益。

**Out of scope**

- fullPanelRun 或 V1.1 review gate 的替换、合并授权。
- 动态角色市场、外部 provider/model 路由、Dashboard、OS 沙箱。
- 成员直接写 canonical state、artifact、Goal、TASK 或 closure。
- 生产团队自动宣布发布或质量收益。

## 关键验收条件

- AC-001 team authorization 与 review authorization 互不继承；未授权 team mode 被拒绝且不改状态。
- AC-002 阶段顺序和 profile 校验通过；每个运行同时最多两个 work packages 处于 running；实施阶段绑定当前 canonical TASK，前置阶段不依赖尚未形成的 TASK。
- AC-003 owner 是唯一 canonical writer；成员写 staging/patch，pre/post hash 不匹配时合并拒绝且不覆盖。
- AC-004 超时、重复事件、stale/late 结果均有明确校验结果；合法事件留存 hash，拒绝调用不推进 canonical 状态，每包周期不超过一次 recovery 和 remediation。
- AC-005 review freeze 三个屏障完整，owner 批量修复；贡献者不能评审其贡献 artifact。
- AC-006 六个阶段均能通过真实宿主 exercise（UI 与非 UI）；结果记录质量、返工、时间/用量，不能假设团队优于单人。
- AC-007 保持 startup input understanding、product baseline、test coverage confirmation、HostGoalOwner、TASK、closure 的既有语义和权限。
- AC-008 文档、实现和测试均明确未完成项；没有在实现前写 PASS/发布完成结论。

## 追溯与风险

| 风险 | 缓解 |
|---|---|
| 生产和评审授权混用 | 独立 production_policy 与 review authorization；校验 delivery/feature/owner 身份和 policy_hash。 |
| 两个 workpackage 修改同一 TASK | 当前 TASK 绑定、依赖图、写路径交集校验与 revision CAS；冲突拒绝并由 owner 处理。 |
| staging 覆盖 owner 新提交 | base_sha256/result_sha256、不可变合并意图和无 clobber 恢复；无自动三方合并。 |
| 团队协作收益被夸大 | 真实 host 对照实验，记录质量、返工、时间/用量。 |
| 条件角色误派发 | StageProfile 的固定 condition_flags→角色映射；未知标志拒绝，已启用角色必须由工作包完整覆盖。 |

## 信息缺口

- **Blocker**：无（范围与授权已明确）。
- **Assumption**：宿主负责真实成员派发、身份与执行日志；模块提供 shared_fs staging。用量不可得时记录 unavailable，不估算。
- **Nice-to-know**：各 provider 的并发上限、跨项目统计、长期角色市场；留到后续版本。

## 可追溯引用

CR-005、FR-001..FR-020、NFR-001..NFR-010、TASK-001..TASK-018、TC-001..TC-024、REV-20260929-01。

## 实现对齐记录

REV-20260929-02：对齐 `production_profiles.py`、`team_orchestration.py` 与 `workflow.py` 的字段、阶段入口、并发上限和文件存储边界；不变更 CR-005 的批准目标。前置三阶段先形成产品面，scenario review 与产品确认后进入 test_design，测试/覆盖评审与确认后再 handoff 和当前 TASK 实施。TeamRun completed 与正式 closure 分开。完整测试及真实宿主验收状态见 06、07。
