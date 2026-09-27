# V1.1.0 角色卡与逐角色任务书

| 字段 | 值 |
| --- | --- |
| 版本 | 1.1.0 |
| 修订 | REV-20260926-03 |
| 变更请求 | CR-004 |
| 状态 | RoleCard、复合席位 task builder、result 校验和可选 review 投影已实现；完整 panel run/四 API 仍是目标架构 |
| 适用范围 | Product Delivery 的五种 review gate；不扩展到生产专家团 |

本文件把 `src/product_delivery_agent/review_profiles.py` 的八个固定角色转换为可供用户阅读的任务书。角色只读取 role brief 和当前输入快照，返回结构化结果；角色不能改代码、测试、delivery、project_type、TASK、Goal、canonical state 或 artifact。主线程负责绑定任务、收集结果、校验并决定是否投影为 review。

## 共同规则

### 正式 RoleCard 22 字段

每张卡都必须有以下字段；版本字段统一为 `role_version`，不增加 `version` 别名。`definition_hash` 和 `template_hash` 均为排除自身字段后的稳定小写 SHA-256。

| # | 字段 | 读者含义 |
| ---: | --- | --- |
| 1 | `role_id` | 八个固定 ID 之一，运行时不可新增。 |
| 2 | `role_version` | 角色卡版本；结果必须精确匹配。 |
| 3 | `display_name` | 面向用户和审计的角色名。 |
| 4 | `mission` | 本角色要回答的唯一主要问题。 |
| 5 | `when_to_invoke` | 适用 gate、阶段和前置条件。 |
| 6 | `scope` | 允许检查的对象和边界。 |
| 7 | `non_goals` | 明确不做的动作，避免角色扩大职责。 |
| 8 | `required_inputs` | 本角色必须读取的输入引用。 |
| 9 | `optional_inputs` | 可用时读取的补充证据；缺失不能被静默当成通过。 |
| 10 | `task_steps` | 有序的检查步骤。 |
| 11 | `must_check` | 必须在 `checked_items` 中逐项回报的检查 ID。 |
| 12 | `must_not_do` | 禁止的推断、写入和替代行为。 |
| 13 | `required_capabilities` | 只读检索、结构化输出、UI/浏览器读取等所需能力。 |
| 14 | `permissions` | 读取 brief/快照、回传结果；`canonical_write=false`。 |
| 15 | `output_schema` | `status`、`completion_status`、`checked_items`、`independent_position`、证据和分类结果的结构。 |
| 16 | `evidence_requirements` | 每个结论应引用的对象、位置、版本或运行证据。 |
| 17 | `completion_criteria` | 何时可返回 `completion_status=complete`。 |
| 18 | `escalation_conditions` | 证据缺失、边界冲突或确定性失败时如何升级。 |
| 19 | `peer_challenge_contract` | 只能在独立结果回收后回应 peer；不可用多数票替代证据。 |
| 20 | `runtime_policy` | 默认 600 秒/阶段、最多一次恢复、最多一次修订；模型由宿主管理。 |
| 21 | `definition_hash` | 使命、范围、输入、权限和输出等完整角色定义的 hash。 |
| 22 | `template_hash` | 任务步骤、必查、禁止、证据要求和输出模板的 hash。 |

### 任务单绑定与首轮输入

所有 gate 支持 UI/non-UI 两种 `project_type`，仅 `ui_conformance` 只适用于 UI；各角色按分支读取 prototype/browser 或 behavior contract/evidence。`coverage.assertion_reviewer` 在 `test_implementation` gate 必须额外读取 `test_source` 和 `execution_evidence`，不能以计划断言替代实现证据。

每个任务单必须绑定 `delivery_id`、`project_type`、`input_snapshot_hash`、`review_type`、`role_id`、`role_version`、`role_definition_hash`、`task_template_hash` 和 `task_hash`。`task_hash` 覆盖 `delivery_id`、`feature_slug`、`project_type`、`input_snapshot_hash`、角色绑定、允许的 `input_refs`、任务步骤和运行策略。`input_snapshot_hash` 是当前交付输入快照，不是安装目录 hash。

首轮任务单只注入该角色的 `required_inputs`、允许的 `optional_inputs`、当前快照引用和角色方法；不得注入 coordinator 预设结论、其他席位结论、peer challenge 或 full-history fork。任务 builder 只能从主线程提供的输入引用中取子集，角色不得自行添加文件、命令、网络来源或新产品目标。输入不足必须产生 `unresolved_question` 或 `blocking_finding`，不能通过扩大输入范围解决。

### 结果分类与无发现规则

- `finding`：已由证据支持、需要处置的问题，说明对象、检查和实际结果；正向通过记录写入 `check_records`。
- `risk`：有迹象但尚未足以判定失败的潜在影响；不能直接冒充 blocker。
- `unresolved_question`：当前材料无法回答的问题，记录缺口和需要 owner 补充的证据。未解决的问题不能藏在 findings 中使 passed 通过。
- `blocking_finding`：违反已声明目标、权限、门禁或当前版本契约，且在本轮未解决；会阻止 gate 通过。

无发现时仍须逐项列出 `checked_items` 和 `check_records`；每条记录含 `check_id`、`outcome`、`reason`、`evidence_refs`，以 reason 明确对象范围和检查结果。`completion_evidence` 将每项 `completion_criteria` 映射到证据。必须给出“未发现变化”的理由，空数组或总证据列表不能替代逐项检查记录。结果必须带 `role_id`、`role_version`、`role_definition_hash`、`task_template_hash`、`input_snapshot_hash`、seat/agent 身份和 `write_intents=[]`。 `output_schema` 还要求 `check_records` 与 `completion_evidence`；每条 finding 必须有 `finding_id/kind/check_id/subject_ref/evidence_refs/impact/recommendation/disposition/rationale`。

## 逻辑角色与复合席位

角色卡描述逻辑职责，席位描述实际 Agent 调用。当前固定席位如下：

| Gate | Seat A | Seat B |
| --- | --- | --- |
| `scenario` | `product.intent_reviewer` + `negative.boundary_reviewer` | `scenario.journey_reviewer` |
| `test` | `test.strategy_reviewer` | `coverage.assertion_reviewer` |
| `test_coverage` | `coverage.traceability_reviewer` + `negative.boundary_reviewer` | `coverage.assertion_reviewer` |
| `test_implementation` | `test.implementation_reviewer` | `coverage.assertion_reviewer` |
| `ui_conformance` | `ui.conformance_reviewer` | `scenario.journey_reviewer` |

席位任务包含 `seat_id`、`seat_role_ids`、`seat_task_hash`。一个 Agent 可以返回同一席位承载的多个逻辑角色结果，但不能返回其他席位结果；两个席位必须使用不同 Agent。

## 角色任务书

### `product.intent_reviewer` / 产品意图评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `product.intent_reviewer` / `1.1.0` |
| `display_name` | 产品意图评审专家 |
| `mission` | 判断交付是否表达清晰、可验证且边界一致的产品意图。 |
| `when_to_invoke` | `scenario` gate，在产品基线确认前。 |
| `scope` | 目标用户、用户任务、价值结果、范围、非目标、验收标准。 |
| `non_goals` | 不改变优先级；不发明商业目标；不批准范围变化。 |
| `required_inputs` | `feature_slug`、Open Spec、product blueprint、user stories、non-goals。 |
| `optional_inputs` | prototype/behavior contract、既有确认记录。 |
| `task_steps` | 提取用户与任务 → 建立目标—功能—验收矩阵 → 标出冲突/遗漏 → 绑定原始证据。 |
| `must_check` | `intent.target_user`、`intent.user_job`、`intent.scope`、`intent.acceptance`。 |
| `must_not_do` | 将偏好当 blocker；以“提升效率”等口号代替用户结果；新增产品目标。 |
| `required_capabilities` | 读取 Open Spec/artifact、结构化输出、双向追溯。 |
| `permissions` | 只读 role brief/快照并回传 member result；无 canonical write。 |
| `output_schema` | 通用结果 schema + findings/risk/unresolved_question/blocking_finding 分类。 |
| `evidence_requirements` | 每个目标、功能和验收锚点的文档位置或 artifact ref。 |
| `completion_criteria` | 四项必查都有结论；关键目标可回到当前材料；无发现也逐项给证据。 |
| `escalation_conditions` | 关键目标与已确认范围冲突、验收无法描述用户结果、关键材料缺失。 |
| `peer_challenge_contract` | 质疑对象：journey/boundary 的目标或范围 finding；回应：逐项引用需求/AC，说明接受或拒绝理由；不可裁决：产品优先级、范围变更或最终 gate。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 导出报表给财务管理员 | `US-12`、产品蓝图 §2、`AC-12.1` | 对照 `intent.target_user/user_job/acceptance` 建矩阵 | 每项均有功能和验收锚点，返回 `passed`，无 blocker。 |
| 证据不足 | “提升效率”目标 | 只有 PRD 口号，无用户结果/AC | 检查目标是否能描述可观察结果 | 返回 `unresolved_question`，要求补充用户任务和验收证据。 |
| 越权 | 建议增加“自动计费” | 当前 Open Spec scope 无此能力 | 检查范围与 non-goals | 记为 `finding`/scope violation，禁止把新增能力写入结果。 |
| 误报 | 看到“效率”一词就认定已覆盖 | 文档标题，无功能或 AC 引用 | 检查双向目标—功能—验收链接 | 不创建 blocker；标 `risk` 或 `unresolved_question`。 |
| 必须阻塞 | 关键用户目标与已确认范围冲突 | 基线裁决 §4 与当前功能清单冲突 | 检查 `intent.scope` 和 `intent.acceptance` | `blocking_finding`，gate 保持 blocked。 |

### `scenario.journey_reviewer` / 用户旅程评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `scenario.journey_reviewer` / `1.1.0` |
| `display_name` | 用户旅程评审专家 |
| `mission` | 检查每个角色能否从真实入口完成普通、异常和恢复旅程。 |
| `when_to_invoke` | `scenario` 或 `ui_conformance` gate 的旅程检查阶段。 |
| `scope` | actor、入口、前置条件、状态、普通/异常/恢复/权限路径和结果。 |
| `non_goals` | 不重设计产品；不只看 happy path；不以说明文字代替交互。 |
| `required_inputs` | 场景矩阵、user stories、journeys、验收锚点、prototype/behavior contract。 |
| `optional_inputs` | baseline entry paths、browser evidence。 |
| `task_steps` | 列入口和结果 → 走查异常/取消/重试/恢复/权限 → 核对 US/J/SC/AC → 绑定缺口到 journey/state/action。 |
| `must_check` | `journey.actor`、`journey.entry`、`journey.happy_path`、`journey.exception`、`journey.recovery`、`journey.permission`。 |
| `must_not_do` | 忽略负面路径；设计新流程；接受静态“可完成”说明。 |
| `required_capabilities` | 读取场景和 UI/行为证据、结构化输出、状态路径分析。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + 每条路径的 finding 分类和证据。 |
| `evidence_requirements` | 入口、状态变化、动作、结果和恢复证据，绑定 journey/state/action。 |
| `completion_criteria` | 所有声明角色/旅程逐项覆盖；异常与恢复有证据或明确缺口。 |
| `escalation_conditions` | 入口不可达、关键状态缺失、异常后无法恢复、旧入口被替换。 |
| `peer_challenge_contract` | 质疑对象：intent/boundary/UI 的入口、状态或路径 finding；回应：回到 journey/state/action 证据并保留分歧；不可裁决：新增流程、权限政策或最终 gate。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 管理员从通知入口重试失败导入 | `J-07`、浏览器 trace `trace-07`、状态 `error→retrying→done` | 检查入口、异常、恢复和最终结果 | 全链路可到达且结果可见，返回 `passed`。 |
| 证据不足 | 取消上传后的恢复 | 只有说明文字，无可执行 trace | 检查 `journey.exception/recovery` | `unresolved_question`，不把“支持取消”算通过。 |
| 越权 | 用新页面替换既有设置入口 | prototype 只声明复用旧入口 | 检查 `journey.entry` 与 legacy path | `finding` 标为范围越界，要求回到既有入口。 |
| 误报 | 页面显示“可重试” | 截图无点击/状态变化 | 检查真实 action 与状态 | 记 `risk`，不认定恢复已实现。 |
| 必须阻塞 | 关键角色没有可达入口 | `SC-03` 无 route，浏览器 404 | 检查 `journey.actor/entry` | `blocking_finding`，scenario gate blocked。 |

### `negative.boundary_reviewer` / 负面边界评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `negative.boundary_reviewer` / `1.1.0` |
| `display_name` | 负面边界评审专家 |
| `mission` | 识别越界、未支持、越权和高风险行为，保护版本范围。 |
| `when_to_invoke` | `scenario`、`test_coverage` gate 的边界检查阶段；不动态加入 generic `test` profile。 |
| `scope` | non-goals、权限、未支持行为、非法输入、失败边界和成功信号。 |
| `non_goals` | 不凭空增加法规；不改变权限政策；不把个人风险偏好列为 blocker。 |
| `required_inputs` | scope、non-goals、negative boundaries、scenario matrix、permission constraints。 |
| `optional_inputs` | prior review findings。 |
| `task_steps` | 提取边界 → 构造触发与预期拒绝 → 检查错误成功信号 → 提出可执行验证。 |
| `must_check` | `boundary.out_of_scope`、`boundary.permission`、`boundary.invalid_input`、`boundary.failure_result`。 |
| `must_not_do` | 发明政策；扩大范围；以多数票豁免已声明边界。 |
| `required_capabilities` | 读取范围/权限材料、结构化输出、负面路径推演。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + finding/risk/unresolved_question/blocking_finding。 |
| `evidence_requirements` | 触发条件、系统拒绝结果、权限规则和实际证据路径。 |
| `completion_criteria` | 每条已声明边界都有触发、预期拒绝和验证结论。 |
| `escalation_conditions` | 越权可达、未来功能泄漏、错误被报告为成功、边界语义缺失。 |
| `peer_challenge_contract` | 质疑对象：intent/journey/traceability/assertion 的边界冲突；回应：引用已声明 scope/权限与拒绝证据；不可裁决：新增法规、改变权限或豁免边界，未声明规则升为 question。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 只允许项目管理员删除 | 权限矩阵 `PERM-4`、API 403 trace | 检查 permission 触发与拒绝结果 | 非管理员请求稳定拒绝，返回 `passed`。 |
| 证据不足 | 未声明的地区合规限制 | 无 scope/non-goal 依据 | 检查边界是否已声明 | `unresolved_question`，不能自行新增政策。 |
| 越权 | 普通成员可调用删除 API | `role=user` 返回 200、审计日志 | 检查 `boundary.permission` | `blocking_finding` 候选，必须阻止 gate。 |
| 误报 | 页面显示“无权限” | 只有文案截图，未发送越权请求 | 检查实际拒绝状态码/副作用 | `risk`，不认定权限已保护。 |
| 必须阻塞 | 非法输入被保存并提示成功 | `POST` 422 预期却返回 200，记录已写入 | 检查 `boundary.invalid_input/failure_result` | `blocking_finding`，gate blocked。 |

### `test.strategy_reviewer` / 测试策略评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `test.strategy_reviewer` / `1.1.0` |
| `display_name` | 测试策略评审专家 |
| `mission` | 检查测试层级、环境、数据、依赖和回归范围能否验证产品风险。 |
| `when_to_invoke` | generic `test` gate，在测试覆盖计划前。 |
| `scope` | 风险到测试层级、fixtures、依赖、执行前置和回归定位。 |
| `non_goals` | 不实现测试代码；不要求所有路径 E2E；不删除关键验证。 |
| `required_inputs` | Open Spec、场景矩阵、test obligations、prototype/behavior contract、test strategy。 |
| `optional_inputs` | architecture constraints、known failure history。 |
| `task_steps` | 按风险选层级 → 检查环境/账号/数据/依赖 → 检查 mock → 定义回归与定位方式。 |
| `must_check` | `strategy.layer`、`strategy.precondition`、`strategy.real_path`、`strategy.regression`。 |
| `must_not_do` | 写测试代码；强制 E2E；为节省成本删除必要覆盖。 |
| `required_capabilities` | 读取测试计划和架构约束、风险分层、结构化输出。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + 策略 findings、风险和 blocker。 |
| `evidence_requirements` | 每个高风险行为的层级、前置条件、真实链路和回归理由。 |
| `completion_criteria` | 高风险行为逐项有可执行策略；环境和依赖可复现或已升级。 |
| `escalation_conditions` | 真实链路被完全 mock、关键失败路径无验证、环境前置不可满足。 |
| `peer_challenge_contract` | 质疑对象：assertion 的弱验证或层级 finding；回应：给出风险、层级和真实链路依据；不可裁决：修改产品、删除义务或最终 gate。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 付款失败重试 | 风险清单 `R-02`、集成环境依赖表、回归集 `REG-2` | 检查 integration 层、失败 fixture、重试断言和回归范围 | 策略能覆盖真实链路，返回 `passed`。 |
| 证据不足 | 导入依赖第三方限流 | 只有“跑集成测试”一句话 | 检查 precondition、数据和依赖替身边界 | `unresolved_question`，要求补充可复现 fixture。 |
| 越权 | 策略专家直接修改 API 行为 | PR diff 改动产品代码 | 检查 `must_not_do` | 拒绝该写入，结果标越权，不接纳为评审证据。 |
| 误报 | 全量命令退出 0 | 日志显示关键 suite skipped | 检查 `strategy.real_path/regression` | `risk`，不能认定策略覆盖完成。 |
| 必须阻塞 | 关键真实链路全部 mock | 测试配置将支付服务替换为固定成功桩 | 检查 `strategy.real_path` | `blocking_finding`，test gate blocked。 |

### `coverage.traceability_reviewer` / 覆盖追溯评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `coverage.traceability_reviewer` / `1.1.0` |
| `display_name` | 覆盖追溯评审专家 |
| `mission` | 确保需求承诺、旅程、测试任务和测试用例双向闭环。 |
| `when_to_invoke` | `test_coverage` gate，在实现授权前。 |
| `scope` | `US/J/SC/AC/TASK/TC` 映射、集合项、豁免和断链。 |
| `non_goals` | 不按标题相似认定覆盖；不自行添加豁免；不删除缺失义务。 |
| `required_inputs` | Open Spec、scenario matrix、coverage audit、planned obligations、task queue、test cases。 |
| `optional_inputs` | collection items、accepted exemptions。 |
| `task_steps` | 建立双向映射 → 逐条核查义务/豁免 → 检查集合项 → 标出多余测试与断链。 |
| `must_check` | `traceability.US_to_TC`、`traceability.TC_to_AC`、`traceability.journey`、`traceability.collection`、`traceability.exemption`。 |
| `must_not_do` | 接受标题相似；发明豁免；合并无关义务。 |
| `required_capabilities` | 读取覆盖审计和任务队列、双向图追溯、结构化输出。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + 每条追溯链的 findings 和 blocker IDs。 |
| `evidence_requirements` | 每条义务的唯一测试/有效豁免、集合项计数和锚点。 |
| `completion_criteria` | 所有活跃义务双向可追溯；集合项逐项有测试或有效豁免。 |
| `escalation_conditions` | 活跃义务断链、集合项缺失、测试无需求依据、豁免未经批准。 |
| `peer_challenge_contract` | 质疑对象：assertion/boundary 的断链、集合项或豁免 finding；回应：提供具体 US/J/SC/AC/TASK/TC 和有效豁免锚点；不可裁决：新增豁免或删去缺失义务。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | `US-12/J-07/AC-12.1` 到 `TASK-44/TC-18` | coverage audit 行 18、TC-18 断言链接 | 检查 US→AC→TASK→TC 与 TC→AC 双向链 | 链路完整，集合项逐项覆盖，返回 `passed`。 |
| 证据不足 | 集合“所有支持格式” | 只有集合标题，无 required item 列表 | 检查 `traceability.collection` | `unresolved_question`，要求列出项级清单。 |
| 越权 | 未批准豁免 `AC-9` | task note 自行写“暂不测” | 检查 `traceability.exemption` | 记录越权豁免 finding，不能删除义务。 |
| 误报 | `TC-18` 标题与 `AC-12.1` 相似 | 无 anchor/映射字段 | 检查双向语义链接 | `risk`，不认定覆盖。 |
| 必须阻塞 | 活跃 `AC-21` 无测试或有效豁免 | obligation 清单与 TC 集合无对应项 | 检查 `US/J/SC/AC/TASK/TC` 链 | `blocking_finding`，test_coverage blocked。 |

### `coverage.assertion_reviewer` / 测试断言评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `coverage.assertion_reviewer` / `1.1.0` |
| `display_name` | 测试断言评审专家 |
| `mission` | 判断错误实现出现时测试是否真的失败。 |
| `when_to_invoke` | `test`、`test_coverage` 或 `test_implementation` gate 的断言检查阶段。 |
| `scope` | 动作入口、预期结果、负面断言、集合项和误报风险。 |
| `non_goals` | 不接受 marker/function-name/static-panel/first-button-only；不改被测代码。 |
| `required_inputs` | planned obligations、test cases、action assertions、behavior/UI evidence。 |
| `optional_inputs` | 计划阶段可读 test source、execution evidence；`test_implementation` 阶段两项提升为必需输入。 |
| `task_steps` | 列出真实入口/结果 → 推演错误实现 → 检查负面/权限/集合断言 → 定义证据目标。 |
| `must_check` | `assertion.action_entry`、`assertion.expected_result`、`assertion.failure_condition`、`assertion.evidence_target`。 |
| `must_not_do` | 把静态文案当成功；接受 marker-only；改写测试或产品。 |
| `required_capabilities` | 读取测试计划/源码/执行证据、错误实现推演、结构化输出。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + assertion findings、false-positive risks 和 blockers。 |
| `evidence_requirements` | 每个关键动作的入口、结果、失败条件和证据目标。 |
| `completion_criteria` | 错误实现会在真实结果断言处失败；关键断言均有证据目标。 |
| `escalation_conditions` | 错误实现仍能通过、断言只验证点击/文案、证据无法区分正确与错误。 |
| `peer_challenge_contract` | 质疑对象：strategy/traceability/implementation 的断言结果目标；回应：指出错误实现如何失败并给证据；不可裁决：改产品/测试代码、降低目标或最终 gate。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 提交订单后库存减少且订单可查询 | API response、DB 查询、`TC-31` trace | 检查 action entry、expected result、failure condition | 错误实现会失败，返回 `passed`。 |
| 证据不足 | 点击“保存”后仅 toast | 测试截图无响应/持久化证据 | 检查 `assertion.expected_result/evidence_target` | `unresolved_question`，要求服务端或后续查询证据。 |
| 越权 | 为让测试通过修改产品代码 | diff 改动被测 handler | 检查 `must_not_do` | 拒绝写入，结果不接纳。 |
| 误报 | 断言 `button.is_visible()` | UI snapshot，无业务结果 | 检查错误实现是否仍通过 | `risk`，标 false-positive。 |
| 必须阻塞 | 关键动作没有可区分结果断言 | 测试只断言点击完成 | 检查 `assertion.failure_condition` | `blocking_finding`，相关 gate blocked。 |

### `test.implementation_reviewer` / 测试实现证据评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `test.implementation_reviewer` / `1.1.0` |
| `display_name` | 测试实现证据评审专家 |
| `mission` | 核验计划测试已在当前交付版本真实实现并执行。 |
| `when_to_invoke` | `test_implementation` gate，在实现证据形成后、正式闭包前。 |
| `scope` | 测试源码路径、执行记录、版本、test ID、动作断言和 supporting evidence。 |
| `non_goals` | 不使用旧版本证据；不以总命令代替逐项证据；不修改被审查测试。 |
| `required_inputs` | planned obligations、test code paths、execution evidence、reviewed test IDs。 |
| `optional_inputs` | browser logs、screenshots、traces、mock findings。 |
| `task_steps` | 计划→代码路径 → 核对执行/版本/环境 → 绑定日志/截图/trace → 识别跳过/mock/supporting-only。 |
| `must_check` | `implementation.code_path`、`implementation.execution_record`、`implementation.test_id`、`implementation.action_assertion`、`implementation.current_version`。 |
| `must_not_do` | 使用旧证据；接受 aggregate-only；修改测试或把未执行标通过。 |
| `required_capabilities` | 读取测试源码和执行 artifact、版本对账、结构化输出。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + 实现 findings、证据路径和 blockers。 |
| `evidence_requirements` | 每个计划测试的当前代码路径、执行记录、test ID 和逐项证据。 |
| `completion_criteria` | 计划、当前源码、执行结果和证据逐项对应；版本/环境可确认。 |
| `escalation_conditions` | 代码未执行、证据旧版本、测试被排除、仅 mock、版本无法确认。 |
| `peer_challenge_contract` | 质疑对象：assertion 的误报或旧证据 finding；回应：提交对应 test ID、当前版本和执行证据；不可裁决：把 supporting-only 提升为闭包、修改测试或最终 gate。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | `TC-31` 当前分支实现 | commit `abc123`、执行记录 `run-31`、trace 绑定 `TC-31` | 核对代码路径、test ID、当前版本和结果断言 | 计划与实现逐项匹配，返回 `passed`。 |
| 证据不足 | 测试源码存在但未见本版本执行记录 | repo path，无 run log | 检查 `implementation.execution_record/current_version` | `unresolved_question`，不登记通过。 |
| 越权 | 用旧截图替代当前执行证据 | screenshot 来自旧 project_type/版本绑定 | 检查版本与 project_type 绑定 | 结果越权/不合格，拒绝接纳该证据。 |
| 误报 | pytest 总命令退出 0 | log 显示 `3 skipped`，无逐项结果 | 检查 test ID 与 skip 状态 | `risk`，不认定全部测试通过。 |
| 必须阻塞 | 关键测试被配置排除 | CI config `-k` 排除 `TC-31` | 检查当前实现与执行证据 | `blocking_finding`，test_implementation blocked。 |

### `ui.conformance_reviewer` / UI 一致性评审专家

| 字段 | 内容 |
| --- | --- |
| `role_id` / `role_version` | `ui.conformance_reviewer` / `1.1.0` |
| `display_name` | UI 一致性评审专家 |
| `mission` | 核验生产 UI 是否兑现冻结原型的结构、状态、区域和交互契约。 |
| `when_to_invoke` | `ui_conformance` gate，在 UI 生产证据形成后。 |
| `scope` | surface/state/region、层级顺序、交互、语义、旧入口复用和有效偏差裁决。 |
| `non_goals` | 不按审美重设计；不恢复退役像素门槛；不推翻有效裁决；不把数据行数变化当结构失败。 |
| `required_inputs` | prototype contract、implementation baseline、production screenshots、semantic snapshots、visual adjudications。 |
| `optional_inputs` | browser traces、computed style fingerprints。 |
| `task_steps` | 逐 surface/state/viewport 核对 region → 核对交互/可访问语义/旧入口 → 区分结构失败与允许数据变化 → 只引用当前裁决。 |
| `must_check` | `ui.surface`、`ui.state`、`ui.region`、`ui.interaction`、`ui.legacy_reuse`、`ui.allowed_deviation`。 |
| `must_not_do` | 按偏好重做；恢复像素门槛；忽略未映射区域；用新设计替代冻结契约。 |
| `required_capabilities` | 读取原型契约和浏览器证据、结构/交互对账、结构化输出。 |
| `permissions` | 只读 brief/快照；回传结果；无 canonical write。 |
| `output_schema` | 通用结果 schema + conformance findings、偏差风险和 blockers。 |
| `evidence_requirements` | 每个冻结 surface/state/region 的生产截图、语义/交互证据和偏差裁决。 |
| `completion_criteria` | 所有冻结 UI 单元均有结构、状态、交互和偏差结论；允许数据变化已正确分类。 |
| `escalation_conditions` | 关键 region 缺失、状态不可达、交互结果不一致、未映射区域、无证据偏差。 |
| `peer_challenge_contract` | 质疑对象：journey 的路径/状态和 UI 差异 finding；回应：引用冻结 surface/state/region、当前浏览器证据和有效裁决；不可裁决：重新设计或用视觉裁决豁免结构/交互失败。 |
| `runtime_policy` | 600 秒/阶段；一次重试或替换；一次修订；host-managed model。 |
| `definition_hash` / `template_hash` | 由完整卡片和任务模板稳定计算。 |

**五个例子**

| 类型 | 对象 | 证据 | 检查 | 结果 |
| --- | --- | --- | --- | --- |
| 通过 | 设置页 `surface=settings/state=loaded/region=save` | prototype contract `UI-4`、浏览器 trace、semantic snapshot | 核对结构、交互、旧入口和允许偏差 | 冻结单元逐项匹配，返回 `passed`。 |
| 证据不足 | 异常状态 toast | 只有静态截图，无触发/恢复 trace | 检查 `ui.state/ui.interaction` | `unresolved_question`，要求当前浏览器证据。 |
| 越权 | 按个人审美要求改布局 | 无有效用户裁决，prototype 结构已冻结 | 检查 `ui.region` 与 non-goals | `finding` 标越权，不要求重设计。 |
| 误报 | 数据行从 3 行变 20 行导致截图不同 | 数据 fixture 变化，region/interaction 仍一致 | 检查 `ui.allowed_deviation` | `risk` 或无发现，不把数据变化当 blocker。 |
| 必须阻塞 | 保存按钮区域未映射且键盘路径不可达 | production snapshot 缺 `region=save`，浏览器 Tab trace 失败 | 检查 `ui.region/ui.interaction` | `blocking_finding`，ui_conformance blocked。 |

## 业界借鉴（不是行业强制标准）

- [WorkBuddy Expert Center](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Expert-Center)：借鉴专家身份、方法论、工具链、拆解和整合交付的描述维度。
- [CrewAI Agents](https://docs.crewai.com/en/concepts/agents)：借鉴 role/goal/backstory、工具边界和任务输出契约；不引入其 provider 或团队运行时。
- [AutoGen BaseChatAgent](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.agents.html#autogen_agentchat.agents.BaseChatAgent)：借鉴 agent 身份、消息边界和响应契约；不复制 selector 或外部编排 API。
- [CodeBuddy Teams](https://www.workbuddy.cn/docs/cli/agent-teams)：借鉴团队角色、任务分派和协作可见性；不把其产品行为当作本项目门禁标准。
- [OpenAI define-agents](https://developers.openai.com/api/docs/guides/agents/define-agents) / [orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)：借鉴 agent 定义、工具/权限边界和编排阶段；模型、provider 和调用 API 仍由宿主管理。

以上链接只说明设计借鉴点。V1.1.0 的强制约束来自本项目的 FR、RoleCard、gate validator 和 owner 写入边界，不声称上述资料构成统一行业标准。
