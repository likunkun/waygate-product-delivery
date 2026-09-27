# V1.1.0 评审专家团编排 - 01 需求

| 字段 | 值 |
| --- | --- |
| 版本 | V1.1.0 |
| 作者 | Codex / Open Spec Requirements Agent |
| 日期 | 2026-09-26 |
| 状态 | CR-003 角色契约需求已细化；实现增量实施中，未发布 |
| 源基线 | V1.0.42 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | 历史 V1.1 评审编排需求草案。 | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex / Open Spec Requirements Agent | 补充八角色契约、五种固定组合、owner 权威、预算/复验、当前差距和可测 NFR。 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex / Open Spec Implementation | 补充 22 字段角色卡、逐角色任务书、任务绑定、最小输入、证据分类和 CR-003 实施增量；完整 panel run/四 API 保持目标架构。 | CR-003 |

## 变更关联

- 变更请求：`CR-003`；继承 `CR-002` 的目标架构
- 历史来源：`CR-001`、`ROADMAP.md` V1.1
- 源基线：V1.0.42
- 目标版本：V1.1.0
- 当前阶段：角色卡、task builder、result 校验和可选 review 投影的实施增量；完整 panel run/四 API 仍为目标架构
- 后续版本边界：V1.2 才讨论分阶段生产专家团

## 业务目标

把 Product Delivery 现有的多 Agent 评审从模板、字符串角色和口头纪律升级为可复用的 Review Expert Panel Orchestration：每个席位有版本化角色契约，每个 gate 使用固定角色组合，每个结论都能回到当前输入快照和证据，并由主线程保留唯一的权威写入和 gate 决策权。

本版本解决的是“已有产出如何被多个专家稳定评审”，不是“多个生产专家如何共同完成产品、架构、测试或代码”。

## 业界参考与当前差距

参考资料：

- [WorkBuddy Expert Center](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Expert-Center)：专家身份、方法论、工具链，以及团长拆解、并行执行和整合交付。
- [CrewAI Agents](https://docs.crewai.com/en/concepts/agents) 与 [Crews](https://docs.crewai.com/en/concepts/crews)：`role`、`goal`、`backstory`、工具、委派、迭代、重试和管理者。
- [AutoGen BaseChatAgent](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.agents.html#autogen_agentchat.agents.BaseChatAgent)：借鉴身份、消息和响应契约。
- [CodeBuddy Teams](https://www.workbuddy.cn/docs/cli/agent-teams)：借鉴角色分派、协作任务和可见结果，不引入外部团队运行时。
- [OpenAI define-agents](https://developers.openai.com/api/docs/guides/agents/define-agents) / [orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)：借鉴 agent 定义、工具边界与编排阶段，宿主继续管理模型与 provider。

这些资料是可参考的设计启发，不是统一行业标准。本版本只采用与当前 Product Delivery 评审相符的最小契约。

源基线已经具备：

- `review_gates.py` 对结构化 review 的状态、模式、独立意见、交叉质疑、修订、裁决和阻塞发现进行校验。
- `workflow.py` 对 `scenario`、`test`、`test_coverage`、`test_implementation`、`ui_conformance` 进行 gate 流转，并能记录 2–3 个真实 reviewer agent ID。
- `gatekeeper.py` 用输入 hash 检查评审是否因当前交付输入变化而过期。

与业界可复用专家角色模型的差距是：

- reviewer 仍主要是字符串，没有稳定的 `role_id`、版本、使命、非目标和方法契约。
- gate 能校验 reviewer 数量，但不能校验角色是否覆盖了该 gate 的必需职责。
- 当前输入 hash 没有绑定角色定义、模板/brief 版本和角色级结果。
- 成员写入权威状态主要靠流程约定，缺少 owner 独占 canonical API 和提交前快照漂移校验的明确规则。
- 没有统一的 600 秒席位预算、一次重试或替换、初审加一次复验的运行约束。
- token/cost 可能由宿主提供，也可能完全不可得，缺少 `unavailable` 语义。

## 范围

### 范围内

- 五种评审 gate：`scenario`、`test`、`test_coverage`、`test_implementation`、`ui_conformance`。
- 八个固定评审角色及其角色契约、角色版本、方法、输入、输出和运行边界。
- 五种固定角色组合；V1.1.0 不支持动态增加角色或专家市场。
- 当前 Open Spec、场景矩阵、UI 原型/行为契约、计划义务和执行证据组成的输入快照。
- 每席位每阶段默认 600 秒、一次重试或替换、初审加一次复验。
- 独立评审、交叉质疑、owner 初审裁决、主线程写入和复验。
- 现有 review artifact/state 兼容与结构化证据权威性。

### 范围外

- V1.2 分阶段生产专家团，以及产品、架构、测试、实现生产角色的实际产出。
- 动态专家市场、用户自定义角色市场、自动发现角色和动态 selector。
- Dashboard、外部 controller、外部工作流、provider adapter、独立 Runtime API。
- 模型选择、模型路由、模型名称记录或恢复 1.0.22 已退役的模型编排。
- 成员直接改代码、测试、权威 state、canonical artifact、TASK、Goal 或 closure。
- 完整 OS 沙箱；角色权限契约不能宣称拦截任意 shell 或文件系统写入。
- 本轮完整 panel run/四 API 的完成声明、发布和“质量一定提升”的结论。

## 完整 panel 用户与系统流程（目标架构）

1. 交付进入一个必需的 review gate；系统读取对应固定 gate profile。
2. owner 根据角色必需输入构建当前输入快照和 role brief，并绑定角色版本、模板/brief hash 和输入 hash。
3. 为固定 profile 创建 2–3 个评审席位；所有席位基于同一快照独立评审，不能提前读取其他席位结论。
4. 全体独立结果回传后，执行一次交叉质疑和一次成员结论修订；每阶段全员返回后，owner 才能冻结完整问题清单并裁决。
5. 主线程保存运行记录，最终 gate 校验通过后才能登记通过的 review artifact/state；成员不能写入权威状态。
6. 原工作流完成允许的修复后，主线程建立新快照和关联 run，一次自动周期最多初审加一次复验；每次提交前重新计算该轮快照，拒绝轮内漂移。超过周期上限返回 `needs_remediation`，不直接修改 delivery/Host Goal；有新修复证据后可开启下一有界周期，相同失败材料不能无限重开。
7. 所有必需角色完成、证据完整、无未解决 blocking finding 时 gate 才能通过；角色缺失、能力不足、超时、预算不足、快照漂移或越权结果均阻塞。

## 固定角色目录

角色目录是 V1.1.0 的固定产品配置，不是开放市场。正式 RoleCard 使用 22 字段：`role_id`、`role_version`、`display_name`、`mission`、`when_to_invoke`、`scope`、`non_goals`、`required_inputs`、`optional_inputs`、`task_steps`、`must_check`、`must_not_do`、`required_capabilities`、`permissions`、`output_schema`、`evidence_requirements`、`completion_criteria`、`escalation_conditions`、`peer_challenge_contract`、`runtime_policy`、`definition_hash`、`template_hash`。不得新增含义重复的 `version` 别名。

[09 角色卡与逐角色任务书](09-role-cards.md) 是上述字段的面向用户说明：八个角色逐个说明使命、启用时机、步骤、必查/禁止、输入/证据、完成/升级和质疑回应边界；每个角色都有通过、证据不足、越权、误报、必须阻塞五个例子。通过例子必须包含检查对象、证据、检查动作和结果。

| role_id | 使命 | 方法/检查重点 | 必需输入 | 最小输出 |
| --- | --- | --- | --- | --- |
| `product.intent_reviewer` | 判断交付是否仍表达清晰、可验证的产品意图和边界。 | 检查目标用户、价值、范围、非目标、成功标准与当前基线的一致性；标出意图冲突。 | feature slug、Open Spec、产品蓝图与待确认产品表面、用户故事、非目标；已有历史确认仅作约束，不要求当前基线已确认。 | 独立立场、意图 findings、证据引用、blocking findings、建议裁决。 |
| `scenario.journey_reviewer` | 检查角色、入口、主路径、异常、恢复和旅程连续性。 | 按角色和入口遍历场景；检查普通/异常/恢复/权限路径及 `US/J/SC/AC` 锚点。 | 场景矩阵、用户故事、journey、验收锚点、UI 原型或行为契约。 | 旅程覆盖结果、缺口、证据引用、blocking findings。 |
| `negative.boundary_reviewer` | 识别未声明、越界、未支持或高风险行为。 | 对照范围、非目标、权限和负面边界检查越界功能、错误路径和误导性成功信号。 | 当前阶段的产品草稿或已确认基线、负面边界、场景矩阵、权限约束；首轮不注入同轮 peer 结论。 | 边界 findings、风险等级、证据引用、升级条件。 |
| `test.strategy_reviewer` | 检查 generic `test` gate 的测试策略是否可执行且与目标匹配。 | 检查测试层级、主路径/边界路径、断言质量、执行前置条件和回归范围。 | Open Spec、场景矩阵、测试义务、行为契约/原型证据、测试策略。 | 策略结论、缺口、断言要求、证据引用、blocking findings。 |
| `coverage.traceability_reviewer` | 检查测试义务从需求到测试的完整追溯。 | 验证 `US/J/SC/AC/TASK/TC` 映射、每条义务覆盖和缺失链路。 | Open Spec、场景矩阵、测试覆盖审计、planned obligations、TASK/TC 清单。 | 追溯集合、覆盖缺口、证据引用、blocking findings。 |
| `coverage.assertion_reviewer` | 检查测试是否有真实、可执行、粒度正确的断言。 | 检查集合项、动作入口、结果目标、负面断言和 false-positive 风险。 | 计划阶段读取 planned obligations、TC、集合项、断言定义、行为/原型证据；实现阶段另需实际测试源码和执行证据。 | 断言审查、集合项映射、false-positive findings、证据引用。 |
| `test.implementation_reviewer` | 检查实际测试实现和执行证据是否兑现了计划义务。 | 检查实际代码路径、执行记录、测试 ID、动作断言、证据分布和误报风险。 | 实际测试代码路径、执行证据、planned obligations、reviewed test IDs。 | 实现结论、验证动作断言、证据路径、blocking findings。 |
| `ui.conformance_reviewer` | 检查生产 UI 是否符合已确认的 surface/state/region 和交互契约。 | 检查结构、视觉、交互、旧入口复用、未映射区域和已授权视觉偏差。 | UI prototype contract、surface/state/region、生产浏览器证据、视觉裁决。 | conformance findings、覆盖 ID、证据引用、blocking findings。 |

角色输出都必须是结构化结果；至少包含 `status`、`independent_position`、`findings`、`evidence_refs`、`blocking_findings` 和 `role_id/role_version`。角色不能以自由文本摘要替代这些字段。结果分别记录 `finding`、`risk`、`unresolved_question` 和 `blocking_finding`。无发现/无变化仍需逐项回报 `must_check` 对应的对象、结论和证据，不制造争议，不以多数票忽略证据或确定性门禁失败。角色方法必须与可检验样例绑定，不要求编造专家履历。

真实子 Agent 模式中，席位的 agent ID 必须互异且不等于 coordinator，首轮不使用 full-history fork 注入主线程预设结论。显式降级模式仍覆盖相同逻辑职责，但不编造不同真实 agent ID；报告标明弱证据。进度通过对话、现有 status 和可读报告展示，不新增管理界面。

## 固定 Gate 与角色组合

| Gate | 固定角色组合 | Gate 目的与时点 |
| --- | --- | --- |
| `scenario` | `product.intent_reviewer` + `scenario.journey_reviewer` + `negative.boundary_reviewer` | 用户确认冻结前检查产品意图、旅程和负面边界。 |
| `test` | `test.strategy_reviewer` + `coverage.assertion_reviewer` | 保留既有 generic test gate；检查总体测试策略和可执行断言。 |
| `test_coverage` | `coverage.traceability_reviewer` + `coverage.assertion_reviewer` + `negative.boundary_reviewer` | 实现授权/交接前检查追溯、覆盖和边界。 |
| `test_implementation` | `test.implementation_reviewer` + `coverage.assertion_reviewer` | 实现证据出现后、正式闭包前检查真实测试实现和断言。 |
| `ui_conformance` | `ui.conformance_reviewer` + `scenario.journey_reviewer` | UI 生产证据出现后检查 surface/state/region、交互和旅程连续性。 |

每个组合默认创建 2–3 个席位。主流程已有的负面范围检查继续执行，不因某个 profile 未列出 `negative.boundary_reviewer` 而删除。V1.1.0 不支持运行中动态加角色、删角色或替换 gate profile。

## 功能需求

| ID | 优先级 | 需求 | 可验证验收标准 |
| --- | --- | --- | --- |
| FR-001 | P0 | 当 Product Delivery 到达评审 gate 时，系统必须识别五种 gate 之一及其固定角色组合。 | `scenario`、`test`、`test_coverage`、`test_implementation`、`ui_conformance` 均返回确定的 gate profile；未知 gate 被拒绝。 |
| FR-002 | P0 | 准备评审时，系统必须根据当前 Open Spec、场景矩阵、分支证据、计划义务和阶段执行证据构建输入。 | 输入快照包含当前 feature 和适用证据引用；只有静态通用 prompt 的 payload 不能进入评审。 |
| FR-003 | P0 | `scenario` gate 必须在用户确认冻结前覆盖产品意图、场景/旅程完整性和负面边界。 | 缺任一必需职责、证据或存在未解决 blocking finding 时，冻结 gate 保持阻塞。 |
| FR-004 | P0 | `test_coverage` gate 必须在实现授权前检查 `US/J/SC/AC/TASK/TC` 追溯和计划覆盖。 | 任一追溯目标、覆盖项、集合项或可执行断言缺失时，handoff/authorization 保持阻塞。 |
| FR-005 | P0 | `test_implementation` gate 必须在正式闭包前检查实际测试代码路径、执行证据、测试 ID 和动作断言。 | 无真实代码/证据路径或动作断言不完整时，closure 保持阻塞。 |
| FR-006 | P0 | 五种 gate 必须保持独立；既有 `test` 与 `test_coverage` 均为必需，generic `test` 不能替代 split gate。 | 用任一其他 gate、摘要或旧 generic artifact 替代必需 gate 时，canonical validator 拒绝通过。 |
| FR-007 | P0 | 接受的 review 必须包含独立立场、交叉质疑、修订、初审最终裁决和 blocking findings。 | 缺少任一必需结构、角色结果或证据引用时拒绝接受；初审后最多允许一次复验。 |
| FR-008 | P0 | 未解决 blocking findings、能力缺失、预算不足、超时或证据不足时，gate 必须 fail closed。 | 所有对应负面测试均保持 blocked/failed，不得产生 `passed`。 |
| FR-009 | P0 | 未显式指定时，真实 `spawned_subagents` 是默认强证据模式。 | 新建 review 必须显式记录 `review_mode=spawned_subagents`，除非使用另一种已授权模式。 |
| FR-010 | P0 | `role_simulation` 只能在既有 degradation policy 和明确用户接受证据同时存在时满足 gate，接受证据可引用当前 delivery 启动授权。 | 缺任一条件，或当前 `spawned_subagents_required` 运行使用 simulation 时，review 被拒绝；有效授权不重复询问。 |
| FR-011 | P0 | `blocked_with_reason` 必须保存可读原因且不能满足 gate。 | 任何 blocked record 都不能被转换成 passed，也不能触发后续授权。 |
| FR-012 | P1 | V1.1.0 必须保持源基线 V1.0.42 的 artifact path、review ID、artifact version、review mode 和状态语义可读。 | 历史记录可读取；新字段缺失只能触发文档化兼容路径，不得静默提升证据强度。 |
| FR-013 | P1 | UI 与 non-UI 分支必须使用对应证据：UI 使用 prototype/browser evidence，non-UI 使用 behavior contract/behavior evidence。 | 生成的输入快照能显示正确分支证据；错误分支证据被拒绝或标为 blocked。 |
| FR-014 | P1 | 存在集合型覆盖时，`test_coverage` 必须逐项检查 required item、covered item 和 item-level assertion。 | 任一声明项没有覆盖或逐项断言时，review 不得通过。 |
| FR-015 | P1 | marker-only、function-name-only、static-panel-only、first-button-only 等实现证据必须被识别为 false-positive risk。 | 未解决 false-positive risk 时，`test_implementation` 不得通过。 |
| FR-016 | P0 | non-UI 项目在 pre-handoff 必须有权威 `test_coverage`，在存在实现证据后 pre-closure 必须有权威 `test_implementation`。 | 缺失、替代、过期或 blocked 的 split review 继续产生相应 blocker。 |
| FR-017 | P0 | chat summary、session status、Open Spec summary、progress/task 文本或 custom artifact 不能替代 canonical structured review。 | 只有 canonical state + matching artifact + gate-specific validation 能满足五种 gate。 |
| FR-018 | P0 | 系统必须提供八个固定角色的 22 字段版本化 RoleCard，并在任务构建/spawn 前验证职责、输入、步骤、必查/禁止、证据、完成、升级和质疑回应边界。 | 八个角色均有可读任务书及五类具体例子；未知 role、缺字段或字段类型错位在任务构建前拒绝；通过样例明确对象、证据、检查和结果。 |
| FR-019 | P0 | 系统必须将五种 gate 映射到固定角色组合，并验证每个必需角色有且仅有一个有效席位结果。 | 缺失、重复、未知、越权角色或不符合 profile 的结果均被拒绝；V1.1.0 不支持动态加角色，失败尝试只保留历史。 |
| FR-020 | P0 | 每个角色基于同一当前快照和角色允许的最小输入生成任务单，绑定 delivery/project_type/input_snapshot/角色版本与 hash/任务 hash；角色不能扩大输入。 | 首轮不含 peer 结果、预设结论或 full-history；结果精确匹配任务绑定、逐项必查和证据；finding/risk/question/blocker 分开，无发现仍逐项有证据；静态 prompt、空证据、串任务结果不能通过。 |
| FR-021 | P0 | 接受的 review 必须保存角色目录版本/hash、模板或 brief hash、输入快照 hash 和角色级运行 receipt。 | 任一绑定角色、模板或当前输入变化时，仅当前 delivery 的 review 变为 stale；安装目录更新不重开历史闭合 delivery。 |
| FR-022 | P0 | 成员只能读取 brief/输入并回传结果；主线程独占 canonical API 写入权威 state/artifact，并在提交前重算快照。 | 成员直接写权威对象、提交时快照漂移或越权证据均被拒绝；不得宣称 JSON 契约是 OS 沙箱。 |
| FR-023 | P1 | 每个席位每阶段默认最多 600 秒；每席位每 run 失败恢复最多一次（重试或替换二选一）；每自动周期初审后最多一次复验；角色继承宿主模型且不记录模型。 | 超时、能力不足、预算不足或结果不完整不能伪造 passed；周期超限返回主流程 needs_remediation，有新修复证据才可再开周期，同失败快照不得无限重开。 |
| FR-024 | P1 | 系统必须保存角色级运行 receipt，包括状态、尝试次数、耗时、证据路径和用量字段。 | token/cost 有实测值则记录数值；宿主没有数据时记录 `unavailable`；禁止估算或编造。 |

## 非功能需求

| ID | 类别 | 需求 | 可测度量 |
| --- | --- | --- | --- |
| NFR-001 | 审计性 | Review 决策必须能由结构化 artifact 重建，不依赖聊天历史。 | 100% accepted review 含 mode、角色、快照、独立立场、质疑、裁决和 blocking findings。 |
| NFR-002 | 证据强度 | 强证据、降级证据和阻塞证据必须可区分。 | 100% review 含显式 `review_mode`；simulation 必须有 policy + user acceptance。 |
| NFR-003 | Gate 安全 | 缺证据、错 gate、未解决 blocker、快照漂移或能力不足时必须 fail closed。 | 负面场景拒绝率 100%；不得生成虚假的 passed 状态。 |
| NFR-004 | 兼容性 | V1.1.0 不得破坏源基线 V1.0.42 的既有读取和状态语义。 | 历史 artifact/state 读取成功率 100%；旧记录不会被静默重分类为强证据。 |
| NFR-005 | 追溯性 | 每个 accepted finding 必须连接到当前 feature、角色、agent/seat、版本和证据。 | accepted finding 的必填追溯字段完整率 100%。 |
| NFR-006 | 权威性 | 只有 canonical state、matching artifact 和 gate-specific validator 能决定 gate。 | session/status/custom-only 记录单独通过率为 0。 |
| NFR-007 | 角色契约完整性 | 角色目录和 gate profile 必须在运行前完成校验。 | 八个角色和五个 profile 的完整性校验通过率 100%；缺字段/未知 ID 的 spawn 数为 0。 |
| NFR-008 | 可重放性 | 同一角色版本、模板/brief hash 和输入快照必须能重建本次 review 的输入边界。 | 100% accepted run 能由保存的绑定信息恢复 required inputs、gate profile 和角色结果边界。 |
| NFR-009 | 最小权限与 owner 写入 | 成员结果只能回传主线程，权威写入由 owner canonical API 完成。 | 外来成员通过 canonical API 获准写入次数为 0；越权证据和快照漂移全部拒绝。该指标不承诺拦截任意 shell 写入。 |
| NFR-010 | 运行隔离 | 同一评审轮次的席位必须基于相同输入快照且不能提前共享结论。 | 100% accepted run 的席位快照 hash 相同；检测到席位间提前共享或快照不一致时阻塞。 |
| NFR-011 | 预算与恢复 | 角色运行必须受 600 秒/席位/阶段、一次重试或替换和一次复验约束。 | 超时/超额/重复恢复场景 100% fail closed。 |
| NFR-012 | 失效范围 | 角色、模板或输入变化只使当前 delivery 的相关绑定 review stale；安装更新不替换已冻结绑定。 | 安装目录更新或无关角色变更时已冻结 active/历史 closed 状态变化次数为 0；本次实际绑定内容不一致时正确变 stale。 |
| NFR-013 | 可观测性 | accepted/blocked run 都要有完整 receipt；用量不可得必须显式表示。 | 100% run 含 status、attempts、elapsed、证据路径和 token/cost 数值或 `unavailable`。 |

## Product Delivery 规则保持

- 五种 gate 都是独立职责；`test` 与 `test_coverage` 均必需，generic `test` 不能替代 `test_coverage` 或 `test_implementation`。
- `scenario` 在用户确认冻结前、`test_coverage` 在实现授权前、`test_implementation` 在实现证据存在且正式闭包前生效；`ui_conformance` 按 UI 生产证据流程生效。
- `spawned_subagents` 是默认强证据；`role_simulation` 是降级证据；`blocked_with_reason` 永远不能通过。
- 既有 multi-agent 授权沿用，不因角色编排重复询问用户；角色只校验本次 delivery 的授权范围。
- 成员不得写权威 state/artifact；主线程通过 canonical API 接纳结果并重算快照。
- 角色默认继承宿主模型；V1.1.0 不记录模型、不做模型路由、不恢复 1.0.22 已退役的编排。
- token/cost 有宿主数据时记录实测值；无数据记录 `unavailable`，不得编造。
- 角色、模板、输入的 stale 只作用于当前 delivery 绑定的 review；历史已闭合 delivery 保持可读且不重开。
- 旧 V1.1 文档的 PASS 是历史状态，不等于 CR-002 需求或实现验收通过。
- 两次用户确认仍为 product_baseline 与 test_coverage_plan，之后由 runtime 自动生成实现授权；内部评审变更不自动增加确认节点。必需门禁不能因风险分级而省略。
- 旧 active delivery 在原 runtime/策略下完成，新交付启用 V1.1 契约；旧记录可读但不能直接作为新专家团通过记录。安装更新不替换冻结角色，不删除 policy 回退旧模式。
- UI 专家采用当前视觉策略和有效用户裁决，不重新引入已退役的全页面像素门槛。

## 成功验收场景

- 五种 gate 均能返回确定且不可动态修改的角色组合。
- 八个角色均有完整使命、方法、输入、输出和边界契约。
- 同一快照下的 2–3 个席位能独立完成初审、交叉质疑和裁决；缺席角色、无证据或错 profile 时阻塞。
- 主线程能在一次修订后重新计算快照并完成最多一次复验；漂移结果不被接纳。
- 成员直接写权威对象、超过 600 秒、超过一次重试/替换、能力不足或预算不足时均不能产生 PASS。
- token/cost 不可用时文档和 receipt 显示 `unavailable`，无估算值。
- 历史 V1.0.42 artifact 可读，安装包更新不会重开已闭合 delivery。

效果评估使用同一批历史材料，对比当前多 Agent 评审与新版角色契约评审；固定相近席位数和预算，记录有效缺陷、漏检、误报、返工、耗时及宿主实际用量。报告长度和专家数量不作为收益指标，本轮不宣称已获得质量提升。

## 风险与假设

### 风险

- 同一模型的多席位可能共享偏差；独立提示和交叉质疑只能降低风险，不能保证质量提升。
- 宿主可能没有 OS 级沙箱；通过 owner 写入、只读 brief 和快照漂移校验控制系统可接纳的结果。
- 多席位、重试和复验会增加耗时与 token 成本；固定席位和 600 秒预算限制上界。
- 角色契约可能过度拟合已知检查项；V1.1.0 保留 `unresolved_questions` 和升级条件，不开放动态市场。

### 假设

- 宿主可发起真实 subagent 并回传结构化结果；宿主能力不足时系统阻塞，不伪造角色完成。
- 宿主可选地提供执行隔离；V1.1.0 不把它当作必备，也不把 JSON 声明当作 OS 沙箱。
- 现有 Product Delivery 用户确认、multi-agent 授权、closure authority 和确定性 gate 继续有效。
- 角色方法和 prompt 具体措辞由规范/方案阶段细化；需求只冻结可观察契约和边界。

## 信息缺口

| 等级 | 项目 | 影响 | 处理 |
| --- | --- | --- | --- |
| Blocker | 无 | 目标、范围、角色目录、五种组合、默认预算和权威边界已足够完成需求阶段。 | Proceed |
| Assumption | 真实 spawn、可选隔离和用量记录由宿主提供。 | 规范/方案需定义 provider 不可用、无用量和隔离等级的可观察语义。 | Carry forward |
| Assumption | 模型选择由宿主继承，canonical state/artifact 不记录模型。 | 避免恢复旧模型编排和引入未批准的模型路由。 | Carry forward |
| Assumption | 每席位每阶段 600 秒、一次重试或替换、一次复验是 V1.1.0 默认上限。 | 后续只能通过版本化策略变更，不由成员自行放宽。 | Carry forward |
| Nice-to-know | 实际有效发现率、返工率、延迟、精确 token/cost 计费、动态 selector、跨 gate 复用。 | 不阻塞当前需求；待实施/复盘阶段用相同材料测量。 | Track |

## 需求阶段门禁

**PASS（CR-002 / REV-20260926-01）**：FR-001..024 与 NFR-001..013 均有唯一 ID、可测试验收标准和范围边界；五种 gate、八个固定角色、owner 权威、预算/恢复、失效范围和 `unavailable` 用量语义已冻结；无 Blocker。该 PASS 仅表示需求文档阶段完成，不代表实现、测试、发布或闭包通过。

## CR-003 需求增量验收（REV-20260926-02）

本次仅实施 FR-018～022 的 RoleCard、任务构建、结果校验及可选 review 投影部分；FR-023 的运行策略是声明契约，实际计时/恢复执行和 FR-024 的 panel receipt 仍由目标架构实施阶段完成。本次不凭卡片中的 `runtime_policy` 宣称已能强制执行宿主超时，也不凭可选投影宣称已完成完整 panel lifecycle。

**PASS（文档）**：角色任务书、22 字段、任务绑定和结果语义已形成可验证需求；代码与测试状态由 [05](05-development-plan.md) 和主线程验证记录判定，不能由该文档 PASS 代替。

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

### CR-004 功能需求补充

| 需求 | 验收重点 |
| --- | --- |
| FR-025 复合席位 | 五种 gate 固定为两个席位，逻辑角色完整且不重复覆盖。 |
| FR-026 席位身份 | `reviewer_agent_ids` 等于两个席位身份；同席角色共享身份，跨席位身份不能重复。 |
| FR-027 席位绑定 | 席位、角色、任务 hash、输入快照和项目分支必须绑定，篡改或漂移拒绝。 |
| FR-028 兼容迁移 | 无席位版本的历史角色契约继续可读；新席位契约不能降级成 legacy passed payload。 |
