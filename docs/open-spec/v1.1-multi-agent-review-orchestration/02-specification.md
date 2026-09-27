# V1.1.0 评审专家团编排 - 02 规范

| 字段 | 值 |
| --- | --- |
| 版本 | V1.1.0 |
| 作者 | Codex / Open Spec Lead（合并规范阶段分析） |
| 日期 | 2026-09-26 |
| 状态 | CR-003 角色契约规范已细化；实现增量实施中，未发布 |
| 源基线 | V1.0.42 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | 历史 V1.1 评审编排规范草案。 | CR-001 |
| REV-20260702-01 | 2026-07-02 | Codex | 历史场景验收追溯补充。 | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex / Open Spec Lead | 按 CR-002 合并规范阶段分析并落盘角色契约、五类 profile、panel run、异常和兼容语义。 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex / Open Spec Implementation | 补充 22 字段角色卡、逐角色任务书、任务绑定、最小输入、证据分类和 CR-003 实施增量；完整 panel run/四 API 保持目标架构。 | CR-003 |
| REV-20260926-03 | 2026-09-26 | Codex / Open Spec Implementation | 固定两个复合 reviewer 席位，保留八个逻辑角色并同步席位身份、存储、测试和兼容规则。 | CR-004 |

## 变更关联与范围

- 变更请求：`CR-003`；继承 `CR-002` 目标架构
- 需求来源：`01-requirements.md` FR-001..024 / NFR-001..013
- 目标：将既有五类评审门禁组织为可恢复、可追溯的评审专家团。
- 范围内：角色目录、固定 gate profile、输入快照、成员事件、屏障、裁决、证据投影和兼容读取。
- 范围外：V1.2 生产专家、provider spawn adapter、模型路由、OS 沙箱、Dashboard、外部 controller、独立 Runtime API、Host Goal/closure 权限替换。

## 本次实施边界（CR-003）

CR-003 的实现增量为 RoleCard、task builder、result validator 和可选 role result review 投影。以下 PanelRun、事件屏障、四个公共 API、receipt/恢复和新 delivery 强制 panel policy 描述是目标架构；本轮不宣称这些部分已经实现。角色字段与逐角色任务书见 [09](09-role-cards.md)，实施状态见 [05](05-development-plan.md)。

## 规范原则

1. **Gate 仍是权威**：panel run 只能生成结构化 review 投影，`review_gates.py`、`gatekeeper.py` 和现有 workflow 继续决定门禁。
2. **成员不写权威状态**：成员只能回传结果；canonical state、delivery artifact、Goal、TASK、产品基线和 closure 由 owner workflow API 写入。
3. **同一快照盲评**：独立阶段的席位收到同一输入快照和最小 brief，不注入主线程预设结论、其他席位结果或 full-history fork。
4. **证据优先**：无发现必须提供检查范围和证据；多数票不能覆盖缺失证据、确定性门禁失败或越权写入。
5. **有限周期**：一次 run 只有独立评审、一次质疑、一次修订、一次裁决；修复后复验创建新的关联 run，禁止相同快照和相同 finding-set 无限重开。

## 需求追溯

| 规范章节 | 需求 |
| --- | --- |
| 角色与 profile | FR-001、FR-003～005、FR-018～020、NFR-007～008 |
| Panel API 与阶段 | FR-002、FR-007～011、FR-019～024、NFR-001～003、NFR-010～013 |
| 权威与兼容 | FR-006、FR-012、FR-016～017、FR-021～022、NFR-004～006、NFR-009、NFR-012 |
| 运行与恢复 | FR-008、FR-023～024、NFR-010～013 |

## 角色与 Profile 规范

### RoleCard（正式 22 字段）

所有固定角色均须满足以下字段和类型；版本字段固定为 `role_version`，不增加 `version` 别名。未知角色、缺字段、空职责或字段类型错位应在构建任务前拒绝。

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `role_id` | string | 八个固定 ID 之一，不得动态新增。 |
| `role_version` | string | 非空且参与定义 hash；结果精确匹配。 |
| `display_name` | string | 面向用户的明确角色名称。 |
| `mission` | string | 可核验的职责目标，不能是泛化“检查一下”。 |
| `when_to_invoke` | string | 明确适用 gate 和阶段。 |
| `scope` | list[string] | 允许检查的对象边界。 |
| `non_goals` | list[string] | 不承担的目标和行为。 |
| `required_inputs` | list[string] | 必需输入类型；由任务单映射为当前快照中的引用。 |
| `optional_inputs` | list[string] | 可选输入类型；不能扩大为任意外部读取。 |
| `task_steps` | list[string] | 有序检查步骤和判断依据。 |
| `must_check` | list[string] | 结果必须逐项覆盖的稳定检查 ID。 |
| `must_not_do` | list[string] | 禁止的写入、推断或证据替代行为。 |
| `required_capabilities` | list[string] | 所需只读/证据读取/结构化输出能力；不是新工具授权。 |
| `permissions` | object | 只读 brief/快照并回传结果，`canonical_write=false`。 |
| `output_schema` | object | 立场、逐项检查、证据、发现/风险/问题/阻塞的结构。 |
| `evidence_requirements` | list[string] | 对象定位、版本和可验证引用的要求。 |
| `completion_criteria` | list[string] | 必查项完成与证据完整的条件；不能填成升级条件。 |
| `escalation_conditions` | list[string] | 缺证据、违规、冲突或超限时升级 owner 的条件。 |
| `peer_challenge_contract` | object | `can_challenge`、`must_respond_to`、`cannot_adjudicate`；只在独立结果收回后适用。 |
| `runtime_policy` | object | 600 秒/阶段、一次恢复、一次修订；模型由宿主管理。 |
| `definition_hash` | string | 完整定义内容的稳定小写 SHA-256，排除 hash 自身；权限与运行策略变化不可被忽略。 |
| `template_hash` | string | 任务模板内容的稳定小写 SHA-256，排除 hash 自身。 |

22 个字段以外可保留 `quality_rubric`、`examples`、`provenance` 等说明性扩展；它们不能替代必填字段，也不能把升级条件写入完成标准或把 peer 契约降为不具对象/回应/边界的普通列表。每个角色的五类例子、具体任务书与规范一致，见 [09](09-role-cards.md)。

角色定义不选择或记录具体模型。角色契约声明能力边界，不是 OS 文件系统沙箱。

### RoleTask 与输入边界（CR-003）

`build_role_task` 生成可供宿主派发的只读任务单；该纯函数不启动 Agent、不写 canonical state。

- 绑定：`delivery_id`、`project_type`、`review_type`、`feature_slug`、`input_snapshot_hash`、`role_id`、`role_version`、`role_definition_hash`、`task_template_hash`、`task_hash`。
- 输入：每个必需类型映射到当前 delivery/project_type 的受控 `input_refs`；可选输入只从调用方允许集合取子集。缺必需类型、错误分支、空引用或错 profile 均拒绝；准备时过滤未选中的额外输入，回传证据越出任务允许集合则拒绝。
- 首轮：不含 peer 结果、challenge、coordinator 预设裁决、全量聊天历史。无关上下文不得以“可能有帮助”为由加入；角色不能在回传结果时扩大允许集合。
- 内容：使命、步骤、必查/禁止、证据要求、完成/升级、质疑回应契约、输出 schema 和运行策略来自冻结 RoleCard。
- hash：`task_hash` 覆盖身份/project_type/输入快照绑定、允许输入和完整任务内容；定义或模板改变必须使任务身份改变。调用方不能仅替换 hash 字符串后复用不同任务内容。

### RoleResult 与证据语义（CR-003）

结果是对一张任务单的回传。校验须确认角色/profile、delivery、project_type、当前 input_snapshot、角色版本、定义/template/task hash 和身份匹配；未知/重复/缺失角色、重复真实 agent ID、coordinator 冒充、模拟身份冒充真实身份和非空 `write_intents` 均拒绝。

`status` 为 `passed|blocked|needs_remediation`，`completion_status` 为 `complete|incomplete`。可接纳的完整结果必须有 `check_records`（每项含 `check_id`、`outcome`、`reason`、`evidence_refs`），对每个 `must_check` 给出检查对象、结论和证据引用，并用 `completion_evidence` 将每项 `completion_criteria` 映射到证据；只列检查 ID 或给出一个不相关总证据引用不足以证明覆盖。无发现仍需逐项证据和无变化理由。`passed` 不能携带未解决 blocking finding 或影响必需检查完成的 unresolved question。

| 分类 | 判定 | 对门禁的影响 |
| --- | --- | --- |
| `finding` | 有对象、检查、影响和证据的待处置问题；正向检查写入 check_records。 | 未被有证据地驳回时不能返回 passed，修复由原流程承担。 |
| `risk` | 有依据的潜在影响，尚不足以证明失败。 | 不自动变 blocker；说明缺失验证。 |
| `unresolved_question` | 当前允许输入不足以回答的问题。 | 未解决时不能返回 passed；不得只清空顶层问题数组以隐藏 findings 中的未知项。 |
| `blocking_finding` | 已声明的目标/权限/门禁/版本契约被证据证明违反且未解决。 | 不允许通过；引用的 finding ID 必须存在并标明阻塞原因。 |

发现必须包含稳定 ID、分类、对象/检查、证据、影响和建议；不能使用不存在的 evidence ref、重复/悬空 finding ID 或把风险改名来消除阻塞。结果是评审证据；最终 gate 仍由既有 canonical validator 决定。

### 固定 Profile

| `review_type` | 必需角色 | 前置证据 |
| --- | --- | --- |
| `scenario` | `product.intent_reviewer`、`scenario.journey_reviewer`、`negative.boundary_reviewer` | Open Spec、场景矩阵、UI 原型或 non-UI 行为契约草稿；无需当前产品确认已完成 |
| `test` | `test.strategy_reviewer`、`coverage.assertion_reviewer` | 已确认产品基线、测试策略和计划断言 |
| `test_coverage` | `coverage.traceability_reviewer`、`coverage.assertion_reviewer`、`negative.boundary_reviewer` | 已确认产品基线、planned obligations、coverage audit、TASK/TC |
| `test_implementation` | `test.implementation_reviewer`、`coverage.assertion_reviewer` | 实际测试代码、执行证据、planned obligations |
| `ui_conformance` | `ui.conformance_reviewer`、`scenario.journey_reviewer` | UI prototype contract、production conformance、browser evidence；仅 UI 项目 |

除了 `ui_conformance` 仅适用 UI，其他四种 gate 都支持 UI/non-UI；分支决定证据类型，不能把 non-UI 错误排除出 `test` 或 `test_implementation`。`coverage.assertion_reviewer` 在 `test_implementation` 强制读取 `test_source` 和 `execution_evidence`。

主线程 coordinator 不计入席位。`test` 与 `test_coverage` 继续都是必需 gate；任何 profile 不能替代其他 profile。

## Panel 数据契约（目标架构）

### ReviewSnapshot

不可变快照至少包含：

- `delivery_id`、`feature_slug`、`review_type`、项目类型；
- `review_mode` 和当前授权的 policy 引用/hash；降级模式还需既有用户接受的引用/hash；
- 当前适用 artifact refs 及其 sha256；
- `profile_id/profile_version/hash`；
- 每个角色的 `role_id/role_version/definition_hash/template_hash`；
- `review_input_hash`、`snapshot_hash`、运行策略 hash；
- 生成时间、父 run（复验时）和当前 runtime provenance。

业务工件通过当前 delivery 的 canonical 引用解析，根目录兼容 mirror 不是权威来源。Open Spec、测试源码等仓库文件也可作为输入，由 facade 以受控仓库相对路径、内容哈希及冻结副本绑定；源码证据不能因不在 artifacts 内被排除。证据定位需包含工件/文件哈希及章节、代码位置或 surface/state 等锚点；缺必需证据时不能用人工输入 passed 替代。

`snapshot_hash` 覆盖实际材料、所用角色/profile/template/policy 和当前 delivery 身份；不包括 run 状态、时间戳、usage、pending、事件修订号、最终 projection 或它自身，避免每次收集结果都使自己 stale。`review_input_hash` 用同一规范化算法从当前来源和已冻结绑定重算，不直接相信调用方回传的 hash。

安装 catalog 更新不替换 active delivery 的冻结绑定；无关角色/模板和已 closed 交付不失效。只有本次绑定的实际内容不一致才使 run stale。原 run 的快照不覆盖，使用新快照时创建新 run。

### PanelRun

状态字段至少包含：

- `run_id`、`parent_run_id`、`cycle_index`、`review_type`、`profile_hash`；
- `review_mode`、`authorization_policy_ref/hash`、降级时的 `user_acceptance_ref/hash`；
- `phase`、`status`、`revision`、`created_at`、`updated_at`；
- `snapshot_ref/hash`、角色目录和模板哈希；
- seat summaries：`seat_id`、`role_id/role_version`、`agent_id`、attempt、状态、耗时、结果引用；
- `expected_revision`、失败/阻塞原因、`pending_commit`、实际 `protection_level`；
- usage：宿主真实提供的 input/output tokens、duration、cost；缺失为 `unavailable`。

运行详情和事件保存在 delivery-scoped JSON；`multi_agent_reviews[review_type]` 只保存 gate projection：status、artifact、review ID/version、mode、agent IDs/source、current input hash 和 panel run ref。

### MemberResult 与事件

`MemberResult` 必须绑定 `run_id`、`seat_id`、`phase`、`attempt`、`role_id/role_version/hash`、`snapshot_hash` 和 evidence refs；在 `spawned_subagents` 模式还必须绑定真实 `agent_id`、`spawn_source` 和可用的宿主调用记录，并包含：

- `status`、`independent_position`；
- findings：finding ID、severity、blocking、rule/check、subject ref、evidence refs、影响与建议；不确定项需说明依据，不能把自报置信度作为通过门槛；
- `no_change_reason` 或 `unresolved_questions`；
- challenge targets、revision before/after 和实际 usage。

事件以 run 内的 `(event_id, payload_hash)` 幂等。相同 ID 与相同 hash 重复提交返回原确认，不重复推进；相同 ID 不同内容拒绝并记录冲突。先检查已接纳的重复事件，再检查新事件的 `expected_revision`；因此网络重试携带旧 revision 不会破坏幂等。批次先全量校验再提交，任一新事件冲突则整批拒绝，不留下部分成功。

成员身份显式区分 `identity_kind=spawned` 与 `identity_kind=simulated`。`role_simulation` 使用相同逻辑席位、输入和阶段契约，`agent_id`/spawn 信息为空并记录模拟执行者；不适用真实 Agent ID 唯一性校验，不伪造宿主回执。仍需当前 delivery 的既有降级 policy 和用户接受，两者引用/hash进入运行快照，缺一不可。`blocked_with_reason` 只代表阻塞报告，不是一种可获通过的执行方式；已收集的部分结果可保留排查，但不能满足完整评审。真实成员模式首轮不共享意见是任务输入约束，不宣称共享文件系统绝对隔离或同一模型误差独立。

## Panel 生命周期（目标架构）

```text
prepared
  -> independent_review
  -> cross_challenge
  -> revision
  -> adjudication
  -> validating
  -> completed
```

phase 记录进度；status 独立取 `prepared`、`running`、`passed`、`blocked`、`stale`、`needs_remediation`。成功为 `phase=completed,status=passed`；已完成但需修复为 `phase=completed,status=needs_remediation`。blocked/stale 保留中止时的 phase 和原因，不能被当作完成通过。

### 准备与独立评审

`prepare_review_panel` 校验当前 delivery、multi-agent 授权、项目分支、gate profile 和 required inputs，生成快照与 2–3 个 seat tasks；仅状态为 `prepared`，不写通过 review。

真实成员的 Agent ID 必须互异且不等于 coordinator。所有席位收到同一 `snapshot_hash` 和最小 role brief。缺失必需输入、无法完成必要读取、真实 agent ID 重复或与 coordinator 相同，run 进入 `blocked`。并发不足时允许排队或串行启动独立实例，不能合并角色或省略席位；排队不计入执行超时。

### 交叉质疑与修订

所有必需席位完成独立结果后才进入 `cross_challenge`。质疑必须引用目标席位或 finding；质疑完成后进入 `revision`，每席位最多一次修订。没有变化也要写 `no_change_reason` 和证据。任何席位未返回、使用旧快照或结果 schema 无效时，不得进入裁决。

### 裁决与投影

owner 去重 findings，保留来源及分歧，记录 accepted/rejected suggestions、unresolved questions、blocking findings 和 final adjudication。需要修复、证据不足或未解决的阻塞项不能仅改标签消除；驳回须有证据与理由，豁免只能引用当前主流程已允许且有效的记录。`finalize_review_panel` 先构建候选结果、运行角色契约/屏障/快照/gate-specific validator，再在同一提交中登记完成 run 及旧格式投影，不能先写 passed 后补证据。复用 `record_multi_agent_review` 的内部校验与登记路径时只消费一次外层授权，不递归重复进入公开 mutation。

## 四个公共接口（目标架构，CR-003 未实现）

这些是现有 `ProductDeliveryWorkflow` facade 的逻辑接口；不暴露 provider spawn API。

### `prepare_review_panel(review_type, parent_run_id=None)`

- 输入：当前 workflow/delivery context、gate 类型和可选父 run。
- 输出：`run_id`、profile、snapshot refs/hash、seat tasks、phase=`prepared`、deadline。
- 拒绝：未知 gate、缺 profile、缺输入、未授权 delivery、旧 runtime、closed delivery、动态角色或父 run 不匹配。

### `inspect_review_panel(run_id)`

- 只读返回 phase、status、revision、seat summaries、缺失席位、deadline、snapshot/hash、pending recovery 和下一动作。
- 不修复 pending、不推进 phase、不消费 Host Goal checkpoint、不写 state/artifact。
- 独立阶段不返回其他席位的结论，保持盲评。

### `record_review_panel_events(run_id, events, expected_revision)`

- 接受 `dispatch_observed`、`member_result`、`cross_challenge`、`revision`、`adjudication`、`recovery`、`timeout` 事件；usage 附于宿主返回记录。adjudication 由 coordinator 提交，成员事件必须绑定 seat/phase/attempt。
- 校验 owner、run、seat、phase、attempt、role/hash、snapshot/hash、schema、权限等级和 revision。
- 允许同一席位一次 retry 或 replacement；replacement 后从最早失效阶段重新收集，不复用旧 challenge/revision/adjudication。
- 返回新的 revision 和 phase；不自行生成正式 passed review。

### `finalize_review_panel(run_id)`

- 要求独立→质疑→修订→裁决屏障完整、所有必需角色完成、无 stale/pending/冲突。
- 运行现有 `validate_multi_agent_review` 及对应 gate-specific 校验。
- 成功才写最终 artifact 与 projection；发现未解决问题返回 `needs_remediation`，不修改整个 delivery/Host Goal。
- 修复后复验在新 run 的 `parent_run_id` 指向已结束父 run；一个自动周期最多初审+一次复验。仍失败返回主流程，有新修复证据后才允许新有界周期，不增加用户确认节点；相同失败 snapshot+finding-set 不得重开。

## 运行约束、异常与安全

| 条件 | 结果 |
| --- | --- |
| 单席位/阶段超过 600 秒 | 从宿主调用开始计时；每席位每 run 最多一次 retry 或 replacement，二选一；再次失败为 blocked；迟到旧 attempt 不接纳 |
| 宿主无真实成员或必要能力 | blocked_with_reason；不得伪造 spawned evidence |
| 实际绑定的角色、profile、template、输入 hash 不匹配 | 原 run stale；新快照建立新 run，从独立检查重新收集 |
| 成员越权写 canonical 对象或提交时快照漂移 | 拒绝接纳 run，记录 blocked reason |
| event 重放且 payload 相同 | 幂等返回，不重复推进 |
| event ID 冲突或 expected revision 过期 | 拒绝并保留当前 run |
| `role_simulation` | 继续遵守既有 degradation policy + user acceptance；不冒充真实 agent ID |
| usage 不可得 | 字段写 `unavailable`，不估算 |
| 需要修改评审对象 | 回到原工作流，修复后新快照/new parent run |

权限是三层边界：角色 contract 声明只读/回传；owner API 是唯一 canonical writer；提交前重新计算快照。可选宿主 sandbox 只记录真实 protection level，不把 JSON 当作 OS 沙箱。

handoff 后每次公开 mutation（含事件批次与恢复）遵循现有 fresh `stage_transition` 对账规则；一次 API 内部提交/投影不重复消费 checkpoint。专家团自身不操作 Goal。达到期限后请求宿主终止过期尝试、拒绝迟到结果，不承诺正在执行的宿主工具可瞬时中断或额外 token 消耗必为零。

## 兼容与失效（完整 panel 目标架构）

- 源基线 1.0.42 的旧 `multi_agent_reviews` 和 Markdown 可读，在原 delivery/runtime/规则下保留原门禁效力；对新的 1.1 交付只能作为历史背景，不能冒充其 panel 通过记录。
- 新 1.1 delivery 必须使用 panel run projection；直接向 `record_multi_agent_review` 提交旧 schema 被拒绝。
- 旧 active delivery 按原 runtime 和既有策略完成；不能删除 policy、混用新旧 runtime 或静默升级。
- 已闭合 delivery 不因安装目录、无关角色或 catalog 更新重新打开；只有当前 delivery 绑定的角色/template/input 变化使相关 run stale。
- V1.1 运行与历史 records 追加存储，不重写 closure truth、Host Goal owner 或确认语义。
- 新 delivery 的 panel policy 与 activation/runtime 身份绑定；缺 policy 不能自动当作 legacy 通过。两次正式用户确认仍为产品基线与测试覆盖计划，随后由 runtime 自动生成实现授权。
- UI 评审遵守当前视觉策略及有效用户裁决，不恢复已退役像素门槛；非 UI 采用行为契约及执行证据，不要求 UI 角色。

## 验收追溯

| FR/NFR | 规范锚点 |
| --- | --- |
| FR-001、FR-018～019 | 角色与 Profile、准备校验 |
| FR-002、FR-020～021、NFR-005、NFR-007～008、NFR-012 | ReviewSnapshot、角色 brief、hash/stale |
| FR-003～006、FR-014～017、NFR-001～006 | 固定 Profile、裁决投影、兼容与 gate 权威 |
| FR-007～011、FR-023、NFR-010～011 | 生命周期、屏障、异常、有限周期 |
| FR-022、FR-024、NFR-009、NFR-013 | 权限、owner writer、receipt 和 usage |
| FR-012、FR-013 | 历史效力、当前分支输入和新 delivery policy 的兼容边界 |

## 验收场景（规范级；尚未转为执行 TC）

| 验收锚点 | 输入/触发 | 预期结果 | 追溯 |
| --- | --- | --- | --- |
| AC-PANEL-001 | UI/non-UI 到达适用 gate | 使用对应固定 profile；test 与 test_coverage 都保留，UI 才要求 ui_conformance | FR-001、FR-003～006、FR-013、FR-016、FR-019 |
| AC-PANEL-002 | 首轮材料准备 | 当前 feature 的准确材料和方法进入 brief，不传 coordinator 预设答案或 peer 结论 | FR-002、FR-018、FR-020 |
| AC-PANEL-003 | 所有成员无发现 | 每个角色有正向覆盖及证据，无变化有理由，不制造发现 | FR-007、FR-020 |
| AC-PANEL-004 | 缺角色、重复 Agent、主线程冒充、无证据、弱断言 | 不能登记 passed，不用多数票绕过失败 | FR-008、FR-014～015、FR-017～020、FR-022 |
| AC-PANEL-005 | 未授权 simulation 或伪造真实 ID | 拒绝；只有既有降级授权可使用标明弱证据的逻辑席位 | FR-009～011 |
| AC-PANEL-006 | 同批次仍有未归席位或后续阶段提前回传 | 不跨越屏障，不提前修改评审对象 | FR-007、FR-019、FR-023 |
| AC-PANEL-007 | 超时、串行排队、替换成员、旧尝试迟到 | 排队不计时；恢复受上限约束；失效结论重收集；旧尝试不覆盖新结果 | FR-008、FR-023 |
| AC-PANEL-008 | 相同事件重传、同 ID 异内容、过期 revision | 分别幂等确认、冲突拒绝、拒绝覆盖 | FR-020、FR-023 |
| AC-PANEL-009 | 本次材料漂移、无关 catalog 更新、历史 closed | 分别 stale、冻结绑定不变、历史不重开 | FR-012、FR-021 |
| AC-PANEL-010 | 初审有问题，修复后复验仍失败 | needs_remediation；不操作 Goal；新修复证据才能重启有界周期 | FR-008、FR-023 |
| AC-PANEL-011 | 写入各步骤中断，再调用只读 inspect/原 mutation | inspect 不写；原 mutation 验证并恢复或明确 blocked；pending 不算通过 | FR-017、FR-021～023 |
| AC-PANEL-012 | 宿主缺少用量/强隔离、旧格式直写新交付 | 用量 unavailable，保护等级真实；拒绝绕过新 panel policy | FR-012、FR-022～024 |

上述 AC-PANEL 是完整目标架构的验收场景。CR-003 的 RoleCard/任务/结果增量使用新 TASK/TC 追溯，见 05/06；旧 TASK/TC 保留历史，不自动转为本修订证据。

## 信息缺口

| 等级 | 项目 | 影响 | 处理 |
| --- | --- | --- | --- |
| Blocker | 无 | 角色、profile、公共接口、阶段和兼容策略已由 CR-002 冻结。 | Proceed |
| Assumption | 宿主提供真实成员调用和事件回传；隔离能力可选。 | 方案阶段定义 host callback、protection level 和 blocked 语义，不实现 provider adapter。 | Carry forward |
| Assumption | 运行详情可放 delivery-scoped JSON，摘要留在 state。 | 方案阶段定义 artifact manifest、pending intent 和恢复检查。 | Carry forward |
| Nice-to-know | 动态 selector、精确 token 计费、跨 gate 角色复用 | 不影响 V1.1.0 规范。 | Track |

## 规范阶段门禁

**PASS（CR-002 / REV-20260926-01）**：行为、数据、接口、阶段、异常、兼容、失效和验收追溯已定义；五种 gate 不互相替代，V1.1 不越界为生产专家团、模型调度或 OS 沙箱；无 Blocker。该 PASS 仅表示规范文档完成，不表示 runtime 已实现。

## CR-003 增量验收锚点（REV-20260926-02）

| 锚点 | 场景 | 预期 | 追溯 |
| --- | --- | --- | --- |
| AC-ROLE-001 | 八卡完整/缺字段/字段类型错位 | 完整卡通过；错卡在派发前拒绝；peer 契约包含对象、回应和不可裁决边界 | FR-018、NFR-007 |
| AC-ROLE-002 | delivery/project_type/input_snapshot/role/task 任一绑定变化 | 不接受旧任务或串任务结果 | FR-020～022、NFR-005、NFR-008 |
| AC-ROLE-003 | peer/预设结论/额外输入进入首轮 | task builder 拒绝或不注入；角色不能扩大输入 | FR-020、FR-022、NFR-009～010 |
| AC-ROLE-004 | 无发现、只列检查 ID、空证据或证据与检查不对应 | 只有逐项对象/结论/证据完整时可接纳 | FR-020、NFR-001～003 |
| AC-ROLE-005 | 风险/问题/阻塞混写、悬空 blocker、passed 带未解 blocker | 拒绝无效结果，不能仅改状态获得通过 | FR-008、FR-020、FR-022 |
| AC-ROLE-006 | owner 提交可选 role result 投影 | 复用现有 review validator；未提供角色结果的兼容路径不被宣称为完整 panel run | FR-012、FR-017、FR-021～022 |

**PASS（文档）**：上述增量有字段、输入/结果约束和可执行测试锚点。运行时通过与完整 panel 的完成状态必须以主线程测试证据另行记录。


## CR-004 SeatProfile 与席位任务规范

`SeatProfile` 是实际派发单位，包含 `seat_id`、`display_name`、`role_ids` 和 `seat_task_hash`。五个 gate 的 SeatProfile 固定为两个席位；`role_ids` 的并集必须精确等于原八角色 gate profile。

`build_gate_tasks(review_type, context)` 返回两个 `review_seats` 和扁平的 `role_tasks`。每个角色任务增加 `seat_contract_version`、`seat_id`、`seat_display_name`、`seat_role_ids`、`seat_task_hash`。任务 hash 覆盖席位映射和任务内容。

MemberResult 仍以逻辑角色为粒度，必须带 `seat_id`、`seat_task_hash`；校验器允许同一席位多个结果使用相同 Agent 身份，但禁止不同席位复用身份。真实模式 `reviewer_agent_ids` 必须正好包含两个席位身份；模拟模式不保存真实身份。

旧的 `role_contract_version=1.1.0` 且缺少 `seat_contract_version` 的记录按原八角色独立席位逻辑读取；含席位契约的记录必须完整提交 `review_seats`，不允许删除席位字段后回退旧 passed 语义。
