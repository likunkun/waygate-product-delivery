# V1.1.0 评审专家团编排 - 00 变更请求

| 字段 | 值 |
| --- | --- |
| 版本 | V1.1.0 |
| 作者 | Codex / Open Spec Lead |
| 日期 | 2026-09-26 |
| 状态 | CR-003 角色契约实施中；完整 panel run 仍为目标架构 |
| 源基线 | V1.0.42 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | 历史 V1.1 评审编排需求草案。 | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex / Open Spec Lead | 按已批准设计补充版本化角色契约、五种固定 gate 组合、owner 权威、预算与可追溯要求。 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex / Open Spec Implementation | 补充 22 字段角色卡、逐角色任务书、任务绑定、最小输入、证据分类和 CR-003 实施增量；完整 panel run/四 API 保持目标架构。 | CR-003 |

## 变更请求

| 字段 | 值 |
| --- | --- |
| CR ID | CR-003 |
| 变更类型 | 已批准的兼容增强 / 需求基线修订 |
| 优先级 | P0 |
| 来源 | `ROADMAP.md` V1.1、源基线 V1.0.42、历史 CR-001/CR-002、用户批准的角色卡与专家任务契约增强 |
| 目标版本 | V1.1.0 |

## 背景与目标

当前 Product Delivery 已有评审门禁、分离的 `scenario`、`test`、`test_coverage`、`test_implementation` 和 `ui_conformance` 状态，以及独立意见、交叉质疑、修订、裁决和阻塞发现等字段。但 reviewer 仍主要表现为字符串、模板和运行时约定，缺少可以复用、版本化、追踪和验证的专家角色契约。

V1.1.0 将这套评审能力产品化为本地 Review Expert Panel Orchestration：固定八个评审角色，按五种 gate 组成专家团，基于当前交付快照生成角色 brief，收集独立评审、交叉质疑、结论修订和裁决；需修复时由原流程处理，再用新快照复验。主线程通过 canonical API 写入权威状态与 artifact。V1.1.0 只增强评审线，不把生产专家团提前纳入本版本。

业界资料只用于抽取角色契约维度，不代表存在统一行业标准：

- [WorkBuddy Expert Center](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Expert-Center)：专家身份、方法论、工具链，以及团长拆解、并行执行、整合交付。
- [CrewAI Agents and Crews](https://docs.crewai.com/en/concepts/agents) / [Crews](https://docs.crewai.com/en/concepts/crews)：`role`、`goal`、`backstory`、工具、委派、迭代、重试和管理者。
- [AutoGen BaseChatAgent](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.agents.html#autogen_agentchat.agents.BaseChatAgent)：借鉴身份、消息和响应契约。
- [CodeBuddy Teams](https://www.workbuddy.cn/docs/cli/agent-teams)：借鉴角色分派、协作任务和可见结果，不引入外部团队运行时。
- [OpenAI define-agents](https://developers.openai.com/api/docs/guides/agents/define-agents) / [orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)：借鉴 agent 定义、工具边界与编排阶段，宿主继续管理模型与 provider。

这些资料提供可参考的角色定义维度；V1.1.0 只采纳适合当前 Product Delivery 评审的最小契约，不复制其 provider、模型路由或通用团队运行时。

## 当前差距

源基线已具备评审校验和 gate 状态流转，但仍存在以下产品差距：

- 角色没有稳定的 `role_id`、版本、使命、非目标、方法和输出契约。
- gate 只约束 reviewer 数量和字符串名称，不能验证某个角色是否覆盖了自己的职责。
- 当前输入 hash 能发现交付材料变化，但没有绑定角色定义、模板/brief 版本和角色级结果。
- 成员权限主要依靠流程纪律；没有明确主线程独占 canonical 写入和提交前快照漂移检查。
- 缺少角色级超时、一次重试或替换、初审与一次复验的统一运行约束。
- token/cost 不是所有宿主都提供，现有流程没有明确 `unavailable` 语义。

## CR-003 实施增量边界（REV-20260926-02）

本次把角色契约补充为可审阅、可绑定、可校验的逐角色任务书，详见 [09 角色卡](09-role-cards.md)：

- RoleCard：八个固定角色各自提供 22 个正式字段；`role_version` 是唯一版本字段；完整定义和任务模板分别绑定内容 hash。
- task builder：任务单绑定 delivery、project_type、input_snapshot、review type、角色版本/hash 和 task hash；首轮仅注入角色允许的最小输入，不带预设结论或 peer 结果，角色不能扩大输入。
- result validator：结果必须回到对应角色/profile、任务和当前快照；区分 finding、risk、unresolved_question、blocking_finding；无发现仍逐项给出检查对象和证据。
- 可选 review 投影：通过校验的角色结果由 owner 投影为现有结构化 review；成员结果不能直接写入权威 state/artifact。

完整 panel lifecycle、交叉质疑屏障、恢复流程和四个公开 API 仍是目标架构，不属于本次实现增量完成声明。现有代码的字段错位或校验缺陷必须按规范修复，不能倒推成规范行为。历史 CR-001 和 CR-002 设计结论保留追溯，不自动转为 CR-003 实施证据。

## V1.1 目标架构范围内（CR-002 保留）

以下为完整版本目标；CR-003 当前实现限于上节所列增量。

- 本地 Product Delivery 的五种评审 gate：`scenario`、`test`、`test_coverage`、`test_implementation`、`ui_conformance`。
- 八个固定评审角色的契约、使命、方法、输入、输出、权限声明和运行约束。
- 五种固定角色组合，不支持 V1.1.0 动态增删角色或角色市场。
- 基于当前 Open Spec、场景矩阵、UI 原型或非 UI 行为契约、测试义务和执行证据的输入快照与角色 brief。
- 2–3 个评审席位的独立评审、交叉质疑、初审裁决和一次复验。
- 由 owner 主线程接收角色结果、重算快照、写入 canonical state/artifact，并记录可恢复 receipt。
- 保留现有强证据、降级证据、阻塞证据语义和五种 gate 的独立性。

## 范围外

- V1.2 分阶段生产专家团：产品、架构、测试、实现等生产角色的实际产出编排。
- 动态专家市场、用户自定义角色市场和自动发现角色。
- Dashboard、可视化管理 UI、外部 controller、外部工作流系统或 provider adapter。
- 独立 Runtime API 版本化和 OpenCode 外部多 Agent 编排。
- 模型选择、模型路由、恢复 1.0.22 已退役的模型编排；角色默认继承宿主模型，canonical 文档不记录模型。
- 成员直接修改代码、测试、权威 state、canonical artifact、TASK、Goal 或 closure。
- 完整 panel run、交叉质疑/修订屏障、恢复编排和四个公开 API 的本轮完成声明。
- 发布和质量收益结论。
- 完整 OS 沙箱能力；权限契约不是任意 shell 或文件系统写入拦截器。

## 完整 panel 用户可见流程（目标架构）

1. 交付进入一个必需的评审 gate；系统根据 gate profile 选择固定角色组合。
2. owner 读取当前交付输入，生成包含角色契约版本和输入快照 hash 的 role brief。
3. 2–3 个席位基于同一快照独立评审；评审期间不得读取其他席位的结论。
4. 全体独立结果回传后，主线程安排一次交叉质疑和一次成员结论修订；每阶段全员返回后才进入下一阶段。
5. owner 去重并冻结问题清单、记录裁决。只有最终 gate 校验通过才登记正式通过的 review；需修复时只记录运行结论，成员不写权威状态。
6. 原工作流完成允许的修复后建立新快照和关联 run，一次自动周期最多初审加一次复验；每次提交前重算该轮快照，拒绝轮内漂移。
7. 无未解决阻塞发现且所有必需角色完成时 gate 才能通过；能力缺失、超时、预算不足、快照漂移或证据不足均阻塞。

## 影响分析

| 领域 | 影响 |
| --- | --- |
| 产品流程 | 从模板/岗位名称升级为固定角色契约和固定 gate profile；评审仍是质量线，不替代生产线。 |
| 状态与 artifact | 在现有 `multi_agent_reviews` 和 Markdown artifact 上增加角色、版本、快照和 receipt 元数据，保持旧字段可读。 |
| 权威性 | 主线程独占 canonical API；成员结果只有在角色、证据和快照校验通过后才能被接纳。 |
| 运行约束 | 每席位每阶段默认 600 秒；每席位最多一次重试或替换；初审后最多一次复验。 |
| 兼容性 | 现有 test 与 test_coverage 均保持必需；generic `test` 不能替代 `test_coverage` 或 `test_implementation`。历史交付不会因安装目录变化重新打开。 |
| 宿主依赖 | 真实 spawn、可选隔离和用量数据由宿主提供；模型默认继承宿主且不写入 V1.1 canonical 文档。 |

## 验收与回滚

- V1.1 目标架构验收条件：CR-002 对应的 FR/NFR 全部可测试；八个角色契约和五种 profile 完整；五种 gate、owner 权威、快照漂移、失败语义、兼容规则和范围边界均有明确验收标准。
- CR-003 验收条件：八张角色卡各有完整任务书和五类具体例子；22 字段、任务绑定、首轮输入约束、逐项证据和失败分类均能被实现及定向测试验证。实施 TASK 见 [05](05-development-plan.md)；文档 PASS 不代表代码、完整 panel、发布或闭包 PASS。
- 回滚：停止派发新的专家团并保留全部证据；原 1.0.42 active delivery 在原 runtime/策略下完成，已启用 V1.1 契约的交付不能切回旧 runtime 混写或删除策略绕过校验。恢复方案见 [03 技术方案](03-technical-solution.md) 与 [04 存储设计](04-storage-design.md)，失败评审不能因停用入口变成通过。
- 历史 V1.1 文档中已有的 PASS 仅作历史记录，不等于 CR-002 已验收。

## 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 同一宿主模型产生相关偏差 | 使用独立席位、固定职责和交叉质疑；不宣称多 Agent 必然提升质量。 |
| 成员越权写入或输入漂移 | 主线程独占 canonical API；提交前重算快照；违规结果拒绝接纳。 |
| spawn 能力、预算或宿主返回结构不足 | 记录 `blocked_with_reason`；能力不足不能伪造 PASS。 |
| 评审成本和延迟上升 | 固定 2–3 席位、600 秒/席位/阶段、一次重试或替换、一次复验。 |
| 角色契约过度僵化 | 初版固定核心目录，允许在后续版本按证据扩展；V1.1.0 不开放动态角色市场。 |
| 安装包更新误使历史结果失效 | stale 只绑定当前 delivery 的角色/模板/输入 hash；历史已闭交付保持可读且不重开。 |
| token/cost 不可获得 | 记录实测值；无宿主用量数据时写 `unavailable`，不得估算。 |

## 信息缺口

| 等级 | 项目 | 影响 | 处理 |
| --- | --- | --- | --- |
| Blocker | 无 | 已批准范围、角色目录、固定组合、默认预算和权威边界足以完成需求阶段。 | Proceed |
| Assumption | 宿主能够发起真实子 Agent 并回传结构化结果；可选隔离能力由宿主决定。 | 规范阶段需定义无能力时的 blocked 语义；不把契约声明当作 OS 沙箱。 | Carry forward |
| Assumption | 角色默认继承宿主模型，V1.1 canonical 文档不记录模型选择。 | 避免恢复已退役模型编排。 | Carry forward |
| Assumption | 现有 multi-agent 授权和用户确认继续沿用，不重复询问。 | 角色编排只校验已有授权范围。 | Carry forward |
| Nice-to-know | 精确 token/cost 计费单位、动态 selector、质量收益和跨 gate 角色复用统计。 | 不影响需求与架构边界。 | 后续实施与复盘阶段测量 |

## CR-004 复合席位整合（REV-20260926-03）

CR-004 保留八个逻辑 `role_id`，把实际派发单位改为两个固定 reviewer 席位。席位可以承载多个逻辑角色，但每个逻辑角色仍返回独立的 `role_result`，因此不会丢失职责、检查项或证据追溯。

| Gate | 席位 A | 席位 B | 逻辑角色覆盖 |
| --- | --- | --- | --- |
| `scenario` | 产品意图与边界 | 用户旅程与交互 | `product.intent_reviewer` + `negative.boundary_reviewer`; `scenario.journey_reviewer` |
| `test` | 测试策略 | 测试断言与假通过 | `test.strategy_reviewer`; `coverage.assertion_reviewer` |
| `test_coverage` | 覆盖追溯与边界 | 测试断言与假通过 | `coverage.traceability_reviewer` + `negative.boundary_reviewer`; `coverage.assertion_reviewer` |
| `test_implementation` | 测试实现证据 | 测试断言与假通过 | `test.implementation_reviewer`; `coverage.assertion_reviewer` |
| `ui_conformance` | UI 一致性 | 用户旅程与交互 | `ui.conformance_reviewer`; `scenario.journey_reviewer` |

席位身份是实际 reviewer Agent 身份：同一席位内的逻辑角色共享身份，不同席位身份必须不同；`reviewer_agent_ids` 记录席位身份，因此新契约每轮为两个身份。协调者不计席位。旧的无 `seat_contract_version` 记录继续按八角色独立席位兼容读取。

任务准备返回 `seat_contract_version`、`review_seats`、`role_tasks` 和输入快照。每个 `role_task` 绑定 `seat_id`、`seat_role_ids`、`seat_task_hash`；席位定义、角色映射或席位任务内容改变会使当前 active review stale。

本次实现边界仍止于角色任务准备、结果校验、现有 review projection 和失效检查，不等价于完整 PanelRun、阶段事件屏障或自动调度服务。
