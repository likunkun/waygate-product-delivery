# V1.2.0 团队生产编排需求

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Requirements |
| 日期 | 2026-09-29 |
| 状态 | 需求与当前实现及真实宿主演练已对齐；自动化验证与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 将批准范围拆为可测试 FR/NFR、边界和验收条件。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 对齐实际阶段、并发上限、TASK 绑定与独立授权契约。 | CR-005 |

## 用户与场景

- Host Goal owner 创建交付时显式选择 coordinator 或 team；team 记录独立 production_policy 授权，不继承 review authorization。
- Coordinator 作为 stage lead，按阶段职责和依赖准备 work packages，同时最多运行两个不冲突的包；仅实施阶段选择当前 canonical TASK。
- 生产成员读取最小快照，在 staging 副本或 patch 上产出；任务简报不包含其他成员未冻结的结果；shared_fs 不提供 OS 级文件隔离。
- owner 收集事件并整合 staging 产出，按相应阶段启动 review freeze；TeamRun 完成后仍通过原入口推进 TASK/closure。
- UI 项目验证冻结 surface/state/region/interaction；非 UI 项目验证行为契约、命令/接口和证据链。

## 功能需求

| ID | 需求与可验证结果 |
|---|---|
| FR-001 | startup 创建 production mode 时，只接受 coordinator 或 team，未知值拒绝；set_production_mode 仅允许同一版本安全边界。 |
| FR-002 | team mode 必须有独立 team authorization；review authorization 不能代替。 |
| FR-003 | TeamRun 只能按六阶段顺序运行，阶段跃迁记录 owner 事件。 |
| FR-004 | 每轮可含多个 production work packages；同时最多两个 running，第三个并发派发拒绝；依赖包须先整合。 |
| FR-005 | implementation_execution 的 ProductionTask 必须引用当前 canonical task_id；其他阶段不要求 TASK。任务以 task_hash/input_snapshot_hash 和 run.scope_hash 绑定版本化角色、输入及授权上下文，过期结果拒绝。 |
| FR-006 | 成员输入只来自 role card 允许的快照字段；禁止注入预设结论或其他成员结果。 |
| FR-007 | 成员权限只允许写 staging copy/patch 和结构化 ProductionResult，owner 校验后才整合；不能改变 canonical state/Goal/TASK/closure。shared_fs 的权限契约不是 OS 沙箱。 |
| FR-008 | 结果状态只能是 ready_for_integration、needs_input、needs_rework 或 failed。 |
| FR-009 | owner API 负责事件记录、结果整合和 canonical 写入；成员 API 不具备写权限。 |
| FR-010 | 成员每次 attempt 的 timeout 为 1800 秒；每个 work package 周期最多一次 recovery（retry）和一次 remediation（revise/评审批量修复）。 |
| FR-011 | 事件使用 expected_revision CAS 和 event_id+payload hash；完整同批重放幂等，混合新旧事件、改写 payload、stale/late 请求拒绝。 |
| FR-012 | patch 合并检查 base_sha256/result_sha256；持久化 merge intent 支持中断恢复，遇到外部变化时拒绝并保留原文件，由 owner 处理冲突。 |
| FR-013 | 对应阶段 review freeze 必须完成 independent、challenge、revision 三道 barrier，相关 review locks 全部关闭后，owner 才批量修复。 |
| FR-014 | 生产 agent 不得评审自己贡献的 artifact；冲突时分配独立 reviewer 或阻塞。 |
| FR-015 | 保持 startup input understanding、product baseline、test coverage confirmation 的现有顺序与确认语义。 |
| FR-016 | HostGoalOwner 仍是唯一目标推进者；团队成员不能完成 Goal 或 closure。 |
| FR-017 | TASK 状态、证据和 closure 只能由 owner canonical 路径推进。 |
| FR-018 | UI exercise 需真实 host 记录页面状态/交互证据；非 UI exercise 需真实 host 记录行为/接口证据。 |
| FR-019 | 对照运行必须记录质量、返工次数、耗时和可用用量；缺失用量写 unavailable。 |
| FR-020 | team run 的完成状态只在 finalize 校验通过后生成；文档阶段不得声称实现完成。 |

## 非功能需求

- NFR-001：事件写入和整合具备稳定 run_id、work_package_id、event_id、hash（实施阶段另有 task_id），审计可重放。
- NFR-002：并发冲突不会覆盖 owner 在冲突窗口内的新提交。
- NFR-003：超时/重试/补救策略有固定上限，避免无限循环。
- NFR-004：结果与 role_version、definition_hash、template_hash 精确绑定。
- NFR-005：拒绝通过明确的 Python 异常类型和说明暴露原因；owner 根据 inspect_team_run 的当前 revision 决定恢复，不承诺不存在的数字/机器错误码。
- NFR-006：stage profile 可扩展但默认六阶段不可被运行时动态插入。
- NFR-007：生产输入最小化，敏感内容按既有 host policy 处理。
- NFR-008：真实 host exercise 在 UI 和非 UI 场景均可重复。
- NFR-009：记录质量/返工/时间/用量对照，不作“多 agent 必然更好”结论。
- NFR-010：与 V1.1 review gate、HostGoalOwner、closure 向后兼容。

## 范围边界

- In scope：生产协作状态、角色合同、阶段编排、staging merge、测试与证据。
- Out of scope：评审 gate 的授权升级、动态市场、模型选择、外部发布系统。

## 信息缺口

| 等级 | 项目 | 处理 |
|---|---|---|
| Blocker | 无 | 进入规范阶段。 |
| Assumption | 宿主用量计量可能缺失 | 使用 unavailable，不估算。 |
| Nice-to-know | 并发宿主数量上限 | 本版本固定最多两个同时运行的生产包；宿主能力另行记录。 |

## 追溯

FR-001..020、NFR-001..010 → 02-specification.md；任务映射见 05-development-plan.md；验证见 06-test-cases.md。

## 实现对齐记录

REV-20260929-02：对齐 `production_profiles.py`、`team_orchestration.py` 与 `workflow.py` 的字段、阶段入口、并发上限和文件存储边界；不变更 CR-005 的批准目标。前置三阶段先形成产品面，scenario review 与产品确认后进入 test_design，测试/覆盖评审与确认后再 handoff 和当前 TASK 实施。TeamRun completed 与正式 closure 分开。完整测试及真实宿主验收状态见 06、07。
