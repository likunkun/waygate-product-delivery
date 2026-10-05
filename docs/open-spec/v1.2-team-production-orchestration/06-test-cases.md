# V1.2.0 团队生产编排测试用例

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec QA |
| 日期 | 2026-09-29 |
| 状态 | 自动化验证、真实宿主验收与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按真实接口与文件存储纠正计划及验收边界。 | CR-005 |

## 验证分层与当前状态

契约/文件恢复测试验证实现约束；真实宿主测试验证实际派发、独立评审与完整用户路径。Python fixtures、身份字符串、模拟时钟或本地文件测试不能充当真实 host exercise。UI 用户可见路径还需真实浏览器旅程证据；non_ui 需真实命令/API 的可观察行为证据。

截至 2026-09-29，实施者实际运行全量 `PYTHONPATH=src python3 -m unittest discover -s tests`，683 项通过（运行约 180.638 秒）。新增 TeamRun/角色/控制/评审回归、独立 non-UI behavior evidence 校验和 UI/non-UI 六阶段确定性流程均通过。插件 manifest 校验、Skill quick validation、源码/打包 runtime 编译、`git diff --check` 和 1.2.0 分发包内容检查也通过。另有两组真实生产 Agent smoke 完成 `product_definition` 的派发、实际文件产出、owner 合并和 TeamRun 收敛；它们不等同于完整 Host Goal、浏览器旅程或正式 closure。相关实现测试位于 `tests/test_production_profiles.py`、`test_team_orchestration.py`、`test_team_control.py`、`test_team_review_regressions.py`、`test_team_mixed_review_regressions.py`、`test_team_workflow_paths.py` 和 `test_team_rework.py`。

## 用例

| TC | 场景/断言 | 映射 | 证据类型 |
|---|---|---|---|
| TC-001 | 新建 startup 接受 coordinator/team，默认 coordinator；未知 mode 拒绝；同一 V1.2 delivery 安全边界可切换，错误 delivery、旧 active、活动 run/review/已开始 TASK 拒绝。 | FR-001 | 契约/兼容回归 |
| TC-002 | review authorization 不能代替独立 production_policy；错误 policy hash、owner 或 delivery 时 prepare 拒绝。 | FR-002 | 契约/身份回归 |
| TC-003 | 六阶段及安全边界 entry_stage 正确；未知 condition flag 拒绝，启用职责必须完整覆盖，依赖无环；UI/non_ui 分支及 implementation_roles 正确。 | FR-003 | profile/阶段回归 |
| TC-004 | run 可含三个以上包但第三个同时 running 被拒绝；依赖须 integrated；只在实施绑定当前 TASK，旧 cursor 结果拒绝。 | FR-004/005 | 调度/当前 TASK 回归 |
| TC-005 | 简报只选角色 required/optional refs，workspace 只复制绑定输入与获准目标；readonly 输入被改拒绝；不把 shared_fs 当 OS 沙箱。 | FR-006 | 输入/文件回归 |
| TC-006 | 声明写控制文件、越权路径、symlink、改 TASK/Goal/closure 的成员行为不能通过 owner 整合；宿主实际权限边界另测。 | FR-007/016/017 | 路径/权限回归 + host |
| TC-007 | 四种 result status 与严格字段、全部角色 methods/examples/hash 可校验；ready 缺输出/检查/证据或带 blocker 拒绝。 | FR-008 | 15 卡/结果契约 |
| TC-008 | 相同 event_id+payload 的完整重放返回同 run；改 payload、重复 id、混合新旧事件拒绝，不重复推进 Goal。 | FR-011 | 幂等回归 |
| TC-009 | expected_revision CAS、scope/input hash 漂移和旧 attempt 拒绝；不得接纳 stale 状态或覆盖 canonical。 | FR-011/012 | CAS/新鲜度回归 |
| TC-010 | 每 attempt 1800 秒 deadline，提前 timeout 拒绝，迟到 result 拒绝；每包第二次 recovery 拒绝。 | FR-010 | 时钟/恢复回归 |
| TC-011 | 每包最多一次 remediation；needs_input 必须新快照；暂停/恢复保留上限，旧 attempt 不能复活。 | FR-010 | remediation/暂停回归 |
| TC-012 | base hash 匹配才整合；模拟部分应用中断后按 pre/post hash 恢复；第三种外部字节保留且拒绝；意图损坏不应用。 | FR-012 | 故障注入/文件回归 |
| TC-013 | 整合后才开始 independent→challenge→revision；冻结期禁止生产事件/整合；所有相关 gate 完成后 owner 汇总批量修复。 | FR-013 | 评审屏障回归 |
| TC-014 | 生产 contributor、owner、重复 reviewer 身份不能充当独立 reviewer；两席身份、阶段证据和源 hash 绑定。 | FR-014 | reviewer 身份回归 |
| TC-015 | 产品定义→架构→产品面→scenario review→产品确认→测试设计→test/coverage review→覆盖确认→handoff/实施→交付准备/复验；startup 理解不绕过。 | FR-015 | workflow 回归 + host |
| TC-016 | finalize_team_run 只完成 run；原 TASK/HostGoalOwner/formal closure 仍要求其授权与证据，成员不能自行关闭。 | FR-016/017 | 权限/闭环回归 |
| TC-017 | UI 真实 host：六阶段实际生产、独立 review 和确认；代表性页面加载/空/错/交互有浏览器 screenshot/trace/semantic evidence。 | FR-018 | 真实 release exercise |
| TC-018 | non_ui 真实 host：六阶段实际生产与 review/确认，命令/API 行为有输入、输出、日志、真实身份和版本证据。 | FR-018 | 真实 release exercise |
| TC-019 | 真实 UI/non_ui 产物/旅程证据绑定当前 run/输入/输出 hash，过期或虚构 spawn/simulated evidence 不作为验收。 | FR-018 | 回归 + 真实 release exercise |
| TC-020 | coordinator/team 对照记录质量缺陷、返工、耗时与方法，不预设收益。 | FR-019 | 真实 release exercise 对照 |
| TC-021 | 无用量时 usage/status 或报告明确 unavailable；不得由耗时推算 token/cost。 | FR-019/NFR-009 | 契约 + 真实 release exercise（unavailable） |
| TC-022 | 整合前验证 task/role/profile/input hash 与真实 staged bytes、输出范围和证据；篡改或重叠 ready patches 拒绝。 | FR-008/020 | 结果/整合回归 |
| TC-023 | finalize 缺 integrated 包、accepted artifact、所需当前 review 或实施切片证据时失败；成功不写 TASK/closure passed。 | FR-017/020 | finalize/workflow 回归 |
| TC-024 | immutable revision/state hash 引用与 journal 一致；pending intent 须恢复；精确重放及旧 coordinator delivery 兼容，不迁移旧 active。 | NFR-001/010 | 持久化/兼容回归 |

## 执行证据格式

每条执行记录包含 TC、executor、时间、版本/提交、实际命令或真实 host/agent/spawn_source、run_id（适用时）、输入/输出 hash、observed result、日志/截图/trace 引用和缺陷号。设计示例只作为 fixture，必须标为模拟。失败需写是否阻断、修复 TASK 和下一动作；未执行写 pending，不填 PASS。真实 host 的质量/返工/时间/用量只报告观测。

## 验收门禁与信息缺口

必须覆盖批准范围内的自动化回归与真实 host 用例，再由既有正式 gate 写出 closure artifact；测试通过摘要不能替代正式闭环。canonical 越权、clobber、stale 接纳或 closure 绕过阻断发布。

- Blocker：无。TC-017..021 已在真实 release exercise 中执行并归档；历史产品定义 smoke 仍单独保留，不替代本次六阶段证据。
- Assumption：UI 浏览器和 non_ui 真实执行环境可提供可核验 artifacts；不可用则明确记录阻塞，不替换为 fixture 成功。
- Nice-to-know：多次对照统计的样本量与指标分布留待实际运行数据。
