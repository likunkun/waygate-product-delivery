# V1.2.0 团队生产编排开发计划

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Implementer |
| 日期 | 2026-09-29 |
| 状态 | 生产实现、自动化验证、真实宿主演练与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按真实接口与文件存储纠正计划及验收边界。 | CR-005 |

## 任务分解

CR-006 地图增补（2026-10-06）：规范与关联契约、开关与进度投影、静态 HTML 与快照、入口与角色交接、浏览器和打包验收均已完成。独立验收清单及结果见 [11](11-progress-map.md)、[12](12-progress-map-verification.md)，不重写 CR-005 的 TASK 身份。

保留已批准的 TASK/FR/TC 标识。以下是验收清单；存在代码并不代表该 TASK 已完成，最终执行结果以 06 和独立证据为准。

| TASK | 内容 | 映射 | 依赖 | 完成定义 |
|---|---|---|---|---|
| TASK-001 | production mode、独立 production_policy 授权和同版本边界切换 | FR-001/002/015/016 | — | 未授权、错误 owner/delivery、旧 active delivery 与安全边界回归通过 |
| TASK-002 | 15 张 RoleCard、StageProfile、hash 和固定条件角色 | FR-003/006 | TASK-001 | 全部角色方法/输入/输出/五类示例与 profile 验证一致 |
| TASK-003 | ProductionTask/Result/TeamRun 契约 | FR-004/005/008 | TASK-002 | 前置无 TASK、实施绑定当前 TASK；角色和输入 hash 验证 |
| TASK-004 | prepare/inspect 与工作包依赖调度 | FR-003/004/005 | TASK-003 | 六阶段入口、完整职责覆盖、多个包/最多两个 running 验证 |
| TASK-005 | record_team_events、event_id 幂等与 revision CAS | FR-009/011 | TASK-003 | 重放、不一致 payload、混合事件、过期 revision 测试通过 |
| TASK-006 | 最小 staging copy、merge intent 与 no-clobber 整合恢复 | FR-007/012 | TASK-005 | pre/post hash、部分写中断、第三方编辑和 accepted artifact 回归通过 |
| TASK-007 | 1800 秒 attempt、每包一次 recovery/remediation | FR-010 | TASK-005 | timeout、late result、旧 attempt 与额度耗尽证据明确 |
| TASK-008 | independent/challenge/revision 三屏障、批量修复与贡献者排除 | FR-013/014 | TASK-004 | 冻结期禁止生产写入，多 gate 修复汇总及独立身份验证 |
| TASK-009 | integrate/finalize 与既有 TASK/closure 入口保护 | FR-009/017/020 | TASK-006/008 | run completed 不自动推进 TASK/Goal/closure；实施证据须由原路径校验 |
| TASK-010 | UI/non-UI 真实 host exercise | FR-018 | TASK-009 | 实际 spawn 身份、各阶段输入/产物、review 和确认有真实证据 |
| TASK-011 | 质量/返工/时间/用量与 coordinator 对照 | FR-019/NFR-009 | TASK-010 | 记录实际观测；缺用量标 unavailable |
| TASK-012 | 旧交付不迁移与新交付默认 coordinator 的兼容回归 | FR-015/016/017 | TASK-003 | 旧 active delivery 不回填/不重开，不引入 DB 或迁移脚本 |
| TASK-013 | 逐角色方法、输出、证据与五类示例核对 | FR-006/008 | TASK-002 | 09 和 getter 返回的 15 张卡一致，权限/hash 可验证 |
| TASK-014 | 文档追溯与 stage handoff 对齐 | NFR-001/006 | TASK-004..012 | 00–09 无虚构字段、门禁顺序或未执行成功声明 |
| TASK-015 | 失败注入、并发、恢复和兼容测试 | NFR-002/003/005 | TASK-005..009 | 06 的自动化用例有实际执行记录，真实 host 项另列 |
| TASK-016 | 真实 host 对照报告 | FR-018/019 | TASK-010/011 | 只报告观测；无数据则保留待验收状态 |
| TASK-017 | 既有确认/HostGoalOwner/TASK/formal closure 回归 | FR-015..017 | TASK-009/015 | run 完成与正式闭环保持分离，原证据门禁无绕过 |
| TASK-018 | 安装/恢复演练与发布复盘输入 | FR-020/NFR-010 | TASK-016/017 | 发布门禁有证据，安全边界停止新派发，保留审计与 canonical 内容 |

## 里程碑

- M1 / TASK-001..003：角色契约与独立授权。
- M2 / TASK-004..007：编排、有限恢复与持久化整合。
- M3 / TASK-008..012：独立评审、既有入口兼容与真实宿主运行。
- M4 / TASK-013..018：完整验证、对照与发布准备。

owner 依据证据更新实际 TASK 状态；成员结果不能自行改变 TASK。此文件不补写本次交付控制器状态，也不把计划表视为执行证据。

## 设计修正与当前状态

REV-20260929-02 修正首稿中“至多两个总工作包”“前置阶段绑定 canonical TASK”“product baseline 先于架构”“DB/migration”“虚构 API/receipt/error code”等描述，均属于对批准范围的契约对齐；TASK-012 改为兼容回归，未新增迁移实施范围。生产代码与自动化回归已完成；本轮 `PYTHONPATH=src python3 -m unittest discover -s tests` 共 683 项通过，插件校验和 1.2.0 分发包也已重新验证。新增 `record_executed_behavior_evidence()` 后，UI/non-UI 两条真实临时目标项目均完成六阶段、Host Goal、canonical closure 和 close；对照报告见 `10-release-exercise-report.md`。

## 信息缺口与追溯

- Blocker：无。TASK-010/016/017/018 的真实 UI/non-UI Host Goal、浏览器/CLI 旅程、对照和正式 closure 演练已完成。
- Assumption：宿主有可用真实成员派发与 UI/non-UI 验证环境；不足时记录具体阻塞和下一动作。
- Nice-to-know：对照报告记录 usage 为 `unavailable`，长期质量、返工、耗时和资源收益仍不预设。

TASK → FR/NFR → TC 见 06；最小交接见 08；角色方法见 09。
