# V1.2.0 团队生产编排发布与复盘

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Release |
| 日期 | 2026-09-29 |
| 状态 | 自动化实现验证、真实宿主验收与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按真实接口与文件存储纠正计划及验收边界。 | CR-005 |

## 发布范围与当前状态

范围为 V1.2 production contracts、15 角色、六阶段 profiles、owner APIs、独立授权、staging/revision CAS/merge recovery、兼容与真实宿主验收。V1.1 review gate 保持原权威；fullPanelRun、后台服务、数据库迁移和外部 provider/model 路由不在范围。

当前状态为发布候选验证完成：683 项全量回归、插件验证、1.2.0 分发包验证、两组早期真实生产 Agent product_definition smoke，以及完整 UI/non-UI Host Goal、浏览器/CLI 旅程、coordinator 对照和正式 closure 演练均已归档。non-UI 正式证据现使用独立 behavior evidence 契约，并验证命令输出/trace 文件存在与 hash；此文件不声明长期团队收益。

## 发布前证据

- 最新完整回归、打包一致性和既有 startup/确认/HostGoalOwner/TASK/closure 门禁验证记录。
- 06 中真实 UI/non_ui host exercise，具有真实成员身份与派发来源、当前字节/版本绑定、独立 review 和用户路径证据。
- 中断恢复、精确重放、外部编辑 no-clobber、旧 active 不迁移与安全边界切换证据。
- 质量/返工/耗时/可用用量的真实 coordinator/team 对照报告，缺用量明确 unavailable。
- 既有正式 closure 路径产生的可核验产物；TeamRun completed 不能代替。

## 安装与运行观察

按项目既有插件打包/安装流程交付，首次新建仍默认 coordinator；需要 team 时在新交付或同版本安全边界显式选择。不存在 schema migration、后台服务启动或虚构 team capability allowlist 操作。运行记录关注 active run、deadline、recovery/revision 额度、CAS/late/stale 拒绝、pending intent、评审冻结与失败原因。

指标报告需注明样本、输入规模、环境和数据缺口；缺失 token/cost 不估算。阈值若未实测不写成既定发布效果。

## 停止与恢复

遇到 canonical clobber、门禁绕过、无法验证的状态/意图或关键宿主失败，停止新派发并保留 revisions、staging、accepted artifacts、intent 和日志。宿主停止旧成员；有 pending merge intent 时先按原 intent 校验恢复，不能用切换 mode 或暂停绕过。只有无未完成 run/review 且 TASK 处于安全边界时才能调用 set_production_mode 切回 coordinator。

旧 active delivery 保持原语义。已整合 canonical 变更须通过已有可审计变更/回退路径处理，不能拿旧 staging 覆盖新编辑；本版本不提供数据库回滚脚本或无条件 feature flag 回退。

## 复盘输入（本次真实观测）

| 维度 | 当前观测 | 责任 |
|---|---|---|
| team vs coordinator 质量缺陷 | 本次 smoke 未观察到缺陷差异；样本不足 | Delivery owner |
| 返工次数/原因、dependency 等待 | 两条 team/coordinator smoke 均 0 次返工；不代表长期分布 | Stage lead |
| 总耗时/可用用量 | 已记录演练耗时；用量为 unavailable | Host operator |
| 超时/CAS/stale/merge recovery | 自动化证据与真实 host 分列 | Runtime owner |
| 用户确认/TASK/formal closure | UI/non-UI 两条 team 链路均通过并 close | HostGoalOwner |

## 信息缺口

- Blocker：无。完整真实 host 对照、正式 closure artifact 和发布演练已完成；长期收益仍不预设。
- Assumption：发布使用项目现有分发与版本管理流程，不新增部署授权或服务。
- Nice-to-know：长期协作收益、成本波动、样本量待持续观察；不提前承诺。

追溯：TASK-010/011/015..018、TC-015..021/024、FR-015..020、NFR-008..010。
