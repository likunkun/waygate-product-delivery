# Product Delivery Agent 流程强化方案

- 来源案例：`/home/lichangkun/code/proxy-collector`
- 观察 feature：`v2.4.1-alert-triage-whitelist`
- 日期：2026-06-22
- 状态：改进方案，已融合多 agent 评审结论；V1.0.4 增加二次原型确认和 goal-driven closure 修复

## V1.0.4 Goal-Driven Closure 修订

`proxy-collector` V1.0.3 复测修正了一个判断：第一次本地 HTML 原型生成后，agent 确实让用户确认了；真实失败是用户指出“缺少人员与模板的编辑部分”后，第二版 prototype 没有重新让用户确认，而是把后续裸 `继续` 当成确认继续实现。

同一轮复测还暴露出另一个缺口：实现阶段有 4 个 TASK，但 agent 完成 3 个 TASK 后停下，没有被 goal 机制持续拉到 TASK-004、executed browser evidence 和 formal closure。

V1.0.4 新增两条硬规则：

- prototype 每次修订后都必须重新确认。用户反馈会把当前确认状态写成 `changes_requested`；prototype 文件、截图或 review evidence 变化后，旧 confirmation 自动失效；新版 prototype 必须生成新的 pending confirmation，只有当前 artifact hash、prototype revision 和 nonce 匹配时才能通过 `confirm_ui_prototype()`。
- implementation 必须由 Product Delivery delivery goal 驱动到 closure。pre-handoff 通过后创建 active goal，goal 包含完整 planned TASK queue、current task cursor、E2E evidence 和 formal closure 完成条件；TASK 未完成或 closure validator 未通过时不能 complete goal，也不能把一次会话总结成“完成”。

V1.0.4 的 stop/final guard：

- `remaining TASK` 非空且没有用户确认等待、外部环境阻塞或连续失败阻塞时，agent 必须继续下一 TASK。
- `state.status != closed` 时禁止声明完成。
- `closure_validation.status != passed` 时 goal 必须保持 active。
- `progress.md` 和聊天总结不能替代 delivery goal status。

## V1.0.3 Gate Enforcement 修订

`proxy-collector` V2.5 复测显示：V1.0.2 已能让 agent 生成 Open Spec、本地 HTML 原型、截图、E2E 和 subagent review，但这些产物仍可能停留在聊天记录、Open Spec 摘要或普通文件中，没有成为不可跳过的 Product Delivery 状态机门禁。

V1.0.3 将强化方向从“字段和模板齐全”推进到“唯一状态机出口”：

- `pre-handoff gate`：Codex Goal handoff 生成前必须确认当前 feature Open Spec、scenario matrix、multi-agent scenario review、user-confirmed freeze、UI prototype 用户确认、planned E2E 用户确认、multi-agent test review、coverage audit 全部通过。
- `pre-closure gate`：formal closure 前必须确认 executed browser evidence 已覆盖所有未豁免 planned E2E obligations，并且 closure artifact 的 TC、user stories、journeys、evidence paths 与 executed evidence 和 coverage audit 可对账。
- `blocked_until` 只作为派生视图，不再作为事实来源；事实来源是结构化 state 字段、user confirmation artifact、multi-agent review artifact、planned/executed evidence 和 closure validator result。
- UI 项目不能再用 `confirm("ui_prototype_review")` 作为本地 HTML 原型确认；必须通过 `confirm_ui_prototype()` 生成用户确认 artifact。
- 旧 state 中 `project_type=web_system` 规范化为 `project_type=ui`、`project_subtype=web_system`；`status=closed` 但缺少 `closure_validation.status=passed` 时按 fail-closed 处理。
- `closure-validator-result.md` 必须在 closure 成功和失败时都落盘，避免再次出现 state/Open Spec 声称完成但 validator 不通过的矛盾。

V1.0.3 不改变此前结论：`proxy-collector` 的需求范围控制问题仍按用户反馈视为误报，本轮修复不以 changed-files scope audit 作为 P0。

## 结论

`proxy-collector` 试运行证明当前插件能生成 Open Spec、HTML prototype、截图证据、测试脚本和 closure artifact，但它仍然没有可靠接管交付流程。核心问题不是产物完全缺失，而是流程可以在关键确认点缺失、证据不合格或状态自称通过的情况下继续往前走。

重要修订：此前关于 `proxy-collector` 需求边界失控的判断已撤销，按用户反馈认定为误报。后续改造不再把该项作为失败根因，也不围绕该误报设计 P0 修复项。文档和模板中保留的 `scope` 只表示“版本边界与场景映射”，不是重新认定需求范围控制失败。

多 agent 评审后的核心状态机：

```text
draft Open Spec + draft scenario matrix
-> visible multi-agent scenario review
-> user-confirmed freeze
-> UI prototype user confirmation
-> planned E2E obligations + structured exemptions
-> Codex Goal handoff
-> executed browser evidence
-> formal closure validator
```

关键原则：

- Gate 1 只能是 draft ready，不能在多 agent review 前声明 freeze。
- 实现前只能冻结 planned E2E obligations 和结构化豁免，不能要求或伪造真实 browser evidence。
- 真实 browser evidence、supporting evidence、命令输出、evidence path 和 hash 必须在实现后生成，并由 closure validator 校验。
- 用户确认必须是统一 artifact，不只服务 prototype，也覆盖 Open Spec freeze、scenario matrix、planned E2E 和 handoff。
- `state.status=closed` 只能由 Product Delivery validator 通过后写入。

## 真实失败模式

### 1. Open Spec 前置接管不足

监控现象：

- 当前 feature 后续补出了 Open Spec 包。
- 但流程没有稳定表现为“先完成 Open Spec，再进入实现”。
- Open Spec、state、planning files 和实现进度一度出现不同步。

改进要求：

- 当前 feature 必须生成 `docs/open-spec/<feature>/00-change-request.md` 到 `08-stage-handoff.md`。
- 文件名必须与 runtime guard 一致：
  - `03-technical-solution.md`
  - `04-storage-design.md`
  - `05-development-plan.md`
- Open Spec 先进入 draft ready，再经过多 agent review 和用户确认后 freeze。
- 旧版本 Open Spec、聊天总结、`progress.md` 都不能替代当前 feature Open Spec。

### 2. 本地 1:1 HTML 原型修订后没有再次让用户确认

监控现象：

- 第一版原型被生成后，agent 停下来让用户确认。
- 用户提出原型缺口后，agent 修订了原型并刷新了 Playwright 证据。
- 第二版原型没有重新让用户确认，而是把后续裸 `继续` 当作确认。

改进要求：

- UI prototype gate 必须拆成三个状态：
  - `generated`
  - `reviewed_by_agent`
  - `confirmed_by_user`
- 只有 `confirmed_by_user=true` 才能进入实现。
- 用户确认必须落盘为 `user-confirmation` artifact。
- 浏览器截图、overflow 检查、静态审查只能做辅助证据，不能替代用户确认。
- 每次 prototype 修订都必须生成新的 pending confirmation。
- pending confirmation 必须绑定 artifact hash、prototype revision 和 nonce。
- 裸 `继续` 不能替代当前版本 prototype 确认。

### 3. 多 agent 讨论不可见

监控现象：

- 用户期望看到多 agent 对场景合理性、空缺、测试覆盖和 E2E 义务进行讨论。
- 试运行线程没有在实现前产出可见的多 agent 评审 artifact。

改进要求：

- 必须产出：
  - `.product-delivery/artifacts/<feature>/multi-agent-scenario-review.md`
  - `.product-delivery/artifacts/<feature>/multi-agent-test-review.md`
- 最小 reviewer 角色：
  - 产品意图 / 版本边界 reviewer
  - UI/UX 场景 reviewer
  - 测试策略 reviewer
  - 负向边界 reviewer
- artifact 必须记录 reviewer 结论、分歧点、接受建议、拒绝建议、未解决问题和 blocking findings。

### 4. 场景和空缺审查太隐式

监控现象：

- Open Spec 有 FR 和 TC，但用户旅程、异常路径、恢复路径、权限路径、移动端路径、负向边界没有在实现前以矩阵形式明显呈现。

改进要求：

- 必须产出 `scope-scenario-matrix.md`。
- 每行必须包含：
  - `scenario_id`
  - role
  - user story
  - journey
  - path type
  - risk level
  - blocking level
  - review status
  - negative boundary
  - planned E2E case
- 关键场景缺失时必须阻塞实现，除非用户通过结构化豁免 artifact 明确批准。

### 5. E2E 没有从用户旅程开始建模

监控现象：

- 后续确实生成了 E2E evidence。
- 但流程没有在实现前明确展示：每个 UI 用户旅程、用户可见异常路径是否都有 planned browser E2E 或豁免。

改进要求：

- 实现前冻结 planned E2E obligations。
- 每个 active UI 用户故事、用户旅程、用户可见异常路径必须映射到 planned browser E2E 或用户批准的结构化豁免。
- supporting evidence 不能替代 UI journey browser E2E。
- 实现后必须记录 executed browser evidence，并由 closure validator 校验。

### 6. closure 可以自称完成，但没有通过真实 validator

监控现象：

- state 变成了 `status=closed`。
- Open Spec `08-stage-handoff.md` 声称 closure 完成。
- `formal-closure.json` 存在。
- 但 Product Delivery V0.10 validator 拒绝该 artifact。

改进要求：

- `state.status=closed` 只能由 `validate_feature_closure` 通过后写入。
- validator 失败时必须写入：

```json
{
  "stage": "closure_failed",
  "closure_validation": {
    "status": "closure_failed"
  },
  "blocking_gates": {
    "closure": false
  }
}
```

## 新门禁模型

### Gate 0 - Active Mode Startup

必须具备：

- `superpowers:using-superpowers`
- `planning-with-files`
- `product-delivery-agent`
- `.product-delivery/state.json`
- 当前 feature slug
- `task_plan.md`
- `progress.md`
- `findings.md`

阻塞规则：

- startup guard 未通过时禁止实现。

### Gate 1 - Draft Open Spec And Scenario Matrix Ready

必须产出：

- 当前 feature Open Spec 00 到 08。
- `.product-delivery/artifacts/<feature>/scope-scenario-matrix.md`

阻塞规则：

- 当前 feature Open Spec 或 draft scenario matrix 缺失时禁止进入多 agent review。
- Gate 1 不能声明 freeze。

### Gate 2 - Visible Multi-Agent Scenario Review

必须产出：

- `.product-delivery/artifacts/<feature>/multi-agent-scenario-review.md`

阻塞规则：

- 有 P0/P1 blocking finding 时禁止 freeze。
- review 通过后才能请求用户确认 freeze。

### Gate 3 - User-Confirmed Freeze

必须产出：

- `.product-delivery/artifacts/<feature>/user-confirmation.md`

阻塞规则：

- 用户未确认 Open Spec 和 scenario matrix 前禁止实现。
- 确认对象必须记录 artifact path、artifact version、confirmation source、confirmed at、user message。

### Gate 4 - UI Prototype User Confirmation

仅适用于 `project_type=ui`。

必须产出：

- 本地 1:1 HTML prototype
- UI 静态评审
- 浏览器截图证据
- prototype 用户确认 artifact

阻塞规则：

- `ui_prototype.confirmed_by_user` 不是 true 时禁止实现。
- prototype 文件、截图或 review evidence 变化后，旧 confirmation 自动失效。
- 用户只说“继续”时不得通过 prototype confirmation；必须有当前 pending confirmation 的 artifact hash、revision 和 nonce 对账。

### Gate 5 - Planned E2E Obligations

必须产出：

- `.product-delivery/artifacts/<feature>/planned-e2e-obligations.md`
- 结构化豁免记录，若存在豁免。

阻塞规则：

- UI journey 没有 planned browser E2E 或结构化豁免时禁止 handoff。
- 结构化豁免必须记录对象 ID、原因、风险、替代证据、批准来源、时间戳和适用范围。

### Gate 6 - Visible Multi-Agent Test Review

必须产出：

- `.product-delivery/artifacts/<feature>/multi-agent-test-review.md`

阻塞规则：

- 测试覆盖存在关键缺口时禁止 Codex Goal handoff。

### Gate 7 - Codex Goal Handoff

必须包含：

- user-confirmed freeze
- prototype 用户确认结果
- 多 agent 评审摘要
- planned E2E obligations
- 结构化豁免
- 必须执行的验证命令
- implementation delivery goal
- planned TASK queue
- current task cursor
- stop/final guard 要求

阻塞规则：

- handoff 生成前禁止实现。
- handoff 后必须由 active delivery goal 控制实现闭环。
- planned TASK 未全部完成前禁止停在“完成”状态。

### Gate 8 - Executed Evidence

实现后必须产出：

- executed browser evidence
- supporting evidence
- required command outputs
- evidence path 和 hash

阻塞规则：

- executed browser evidence 缺失时禁止 formal closure。
- supporting evidence 不能替代 UI journey browser E2E。

### Gate 9 - Formal Closure

必须满足：

- closure artifact 通过 Product Delivery validator。
- evidence paths 存在且可读。
- required commands 有 output。
- integrity fields 为顶层 boolean false。
- `state.status=closed` 只能在 validator 通过后写入。
- `delivery_goal.status=complete` 只能在 closure validator 通过且 remaining TASK 为空后写入。

### Gate 10 - Fail-Closed Finalization

任何 closure-like 状态都不能作为事实源直接信任。

closure-like 状态包括：

- `status=closed`
- `status=closed_local_product_delivery`
- `status=complete`
- `status=completed`
- `blocking_gates.closure=true`
- `implementation.current_task=COMPLETE`
- `delivery_goal.status=complete`

必须同时满足：

- `closure_validation.status=passed`
- `feature_closure.status=passed`
- `delivery_goal.status=complete`
- UI 项目必须满足 `executed_browser_evidence.status=passed`

不满足时必须 fail closed：

- `status=closure_failed`
- `blocking_gates.closure=false`
- `next_gate=feature_closure_after_implementation`
- hooks/status/stop/pre-compaction 都必须暴露 blocker。

## 证据模型分层

### scenario_matrix

职责：描述场景、用户旅程、异常路径、风险和边界。

不得承载真实 browser evidence。

### planned_obligation

职责：实现前冻结计划测试义务。

必须包含 test id、scenario id、用户故事、旅程、用户可见异常、目标 test layer、语义断言和预期 artifact pattern。

### executed_browser_evidence

职责：实现后记录真实 browser E2E 证据。

必须包含 command、exit code、trace/screenshot、console/network 结果、semantic assertions、evidence path 和 hash。

### supporting_evidence

职责：记录 unit/API/static/doc/prototype checks。

不得替代 UI journey browser E2E。

## 运行时改造项

### P0 - 状态机和唯一写入通路

改造：

- 新增 `record_scenario_matrix`。
- 新增 `record_multi_agent_review`。
- 新增 `record_user_confirmation`。
- 新增 `confirm_ui_prototype`。
- 新增 `record_planned_e2e_obligations`。
- 新增 `record_executed_browser_evidence`。
- `record_feature_closure` 失败时写入 `closure_failed`，通过时才写入 `closed`。
- 新增 `record_ui_prototype_feedback`，用户反馈后写入 `changes_requested` 并失效旧确认。
- 新增 `create_delivery_goal` / `record_task_completion` / `derive_remaining_tasks` / `assert_goal_can_stop`。
- 新增 executable finalization path，读取 state/handoff/formal closure artifact，调用 Product Delivery validator，失败时非 0 并写 `closure-validator-result.md`。
- 所有 persisted state 读取、hooks 和 stop guard 统一执行 closure-like invariant 审计。

验收：

- 不允许手动清 `blocked_until` 替代 gate transition。
- 不允许 Open Spec closure claim 替代 validator output。
- 不允许 prototype 修订后沿用旧 confirmation。
- 不允许 TASK 未完成或 closure 未通过时 complete goal。
- 不允许 `closed_local_product_delivery`、`blocking_gates.closure=true` 或 `implementation.current_task=COMPLETE` 绕过 `closure_validation.status=passed`。

### P0 - 模板和插件规则

需要打包到插件：

- `scope-scenario-matrix.md`
- `multi-agent-scenario-review.md`
- `multi-agent-test-review.md`
- `user-confirmation.md`
- `planned-e2e-obligations.md`
- `executed-browser-evidence.md`
- `closure-validator-result.md`
- `implementation-goal.md`
- `task-queue.md`
- `stop-guard-result.md`

`SKILL.md` 必须明确：未 freeze、未确认当前 prototype revision、未冻结 planned E2E obligations、TASK 未完成、closure validator 未通过时禁止实现或声明完成。

插件还必须包含真实可执行的 `validate-closure-artifact.py`。该脚本不得是 stub，必须调用 runtime finalization 入口，并在 final summary、stop、goal complete 前作为硬检查运行。

## 成功标准

下一次 `proxy-collector` 类试运行只有满足以下条件才算合格：

- 当前 feature Open Spec 和 scenario matrix 先 draft ready，再经多 agent review 和用户确认 freeze。
- UI 项目必须明确等待用户确认本地 1:1 HTML 原型。
- prototype 修订后必须再次等待用户确认当前版本。
- 多 agent scenario review 和 test review artifact 存在并可打开。
- planned E2E obligations 覆盖 UI 用户旅程和用户可见异常路径。
- executed browser evidence 在实现后落盘并可由 validator 校验。
- implementation delivery goal 记录完整 TASK queue，且 stop guard 能阻止 3/4 TASK 时收口。
- handoff 后、implementation 中或 closure-like 状态下缺 `delivery_goal` 必须阻塞。
- `executed_browser_evidence` 必须进入 canonical state；磁盘上的 E2E JSON 不能单独替代。
- `review_mode=role_simulation` 必须标记为弱证据，并有用户接受记录。
- `project_type` 是 `ui` 或 `non_ui`。
- `state.status=closed` 只在 closure validator 通过后出现。
- `delivery_goal.status=complete` 只在 remaining TASK 为空且 closure validator 通过后出现。
- Open Spec closure claim 与 validator output 一致。

## V1.0.6 Canonical Launch And Review Enforcement

多 agent 评审后补充的修复方向：V1.0.6 不再只检查 `delivery_goal` 是否存在，而是要求实现入口必须来自 canonical Product Delivery handoff transition。

新增硬规则：

- 原型确认、review 接受、实现授权是三个不同 gate。
- 实现前必须记录 `implementation_launch_authorization`。
- 用户确认语必须是 `确认按当前交付包开始实现`。
- 授权绑定 `feature_slug`、review mode、prototype hash、planned E2E、TASK queue、required commands 和 nonce/hash。
- scope、TASK、review mode、prototype 或 planned E2E 变化后，旧实现授权自动失效。
- `role_simulation` 只有独立 `role_simulation_review_acceptance` 用户确认后才可作为弱证据。
- 自定义 `*-pre-handoff-gate.json`、task artifact、Open Spec 总结、prototype screenshot 和磁盘 E2E JSON 只能作为 supporting evidence，不能授权实现。
- 任意 `status=implementation_*`、`implementation.current_task=TASK-*` 或非空 `implementation.completed_tasks`，如果缺 canonical `handoff` 或 `delivery_goal`，必须派生 `implementation_without_delivery_goal` 并 fail closed。

验收补充：

- `load_state`、`status`、resume/prompt/pre-compaction/stop hooks、task completion、executed evidence recording 和 finalization CLI 必须对同一类 poisoned implementation state 给出一致 blocker。
- UI 项目 closure 前，磁盘上的 app E2E JSON 不够；必须通过 `record_executed_browser_evidence()` 进入 canonical `executed_browser_evidence.status=passed`。
- custom artifact 可以保留为迁移/审计材料，但不再拥有状态机授权能力。

## V1.0.7 Canonical Closure Authority

`proxy-collector` V2.7 复测显示：流程已经能做到原型二次确认、真实 spawned subagent review、精确实现授权、完整 TASK 队列、executed browser evidence 和 validator 后 local closure。但最后仍暴露出一个 closure authority 问题：目标项目把 `scripts/verify/validate-closure-artifact.py` 改成 feature-specific rules map，并让 `status=PASS_WITH_NOTES` 的自定义 `formal-closure.json` 通过。

V1.0.7 新增硬规则：

- Product Delivery closure truth 只能来自 packaged canonical finalization：`product_delivery_agent.finalization.run_finalize_cli()`。
- 目标项目 validator、Open Spec closure claim、聊天总结、`progress.md` 都只能是 supporting evidence。
- `closure_validation.status=passed` 必须同时带有：
  - `validator=product_delivery_agent.finalization`
  - `canonical_schema_version=v0.10`
  - `plugin_version=1.0.7`
  - `closure_artifact_sha256`
  - `result_artifact`
- `feature_closure` 必须记录 `source_artifact_path` 和 `source_artifact_sha256`。
- terminal / closure-like state 缺少 canonical closure metadata 时必须 fail closed。
- closure artifact 必须使用通用 V0.10 schema，拒绝 `PASS_WITH_NOTES`、`PASS`、`closed` 等目标项目自定义状态。
- `required_commands[]` 必须记录 `command`、`output`、`exit_code=0`；允许跳过时必须结构化记录 `status=skipped`、`skip_reason`、`skip_scope`、`approved_by`。
- `project_type=web_system` 这类 legacy 值在 workflow/status 写回时必须持久化为 `project_type=ui` 与 `project_subtype=web_system`。

验收补充：

- target-specific validator result 为 passed 但 canonical closure schema 无效时，Product Delivery closure 仍失败。
- closed state 缺 canonical validator identity、schema version、plugin version、artifact hash 或 result artifact 时，load/status/hooks/stop/finalization 都必须暴露 closure blocker。
- 目标项目可以保留自己的 validator 作为 `supporting_validators[]`，但不得解除 closure blocker。

## V1.0.8 Installed Runtime And Transition Authority

`proxy-collector` V2.8 复测显示：原型确认、多 agent review、实现授权、TDD、browser E2E、readonly smoke 和 redaction scan 都已明显改善；剩余失败集中在 Product Delivery 本地权威链路：

- installed plugin cache 缺少 `product_delivery_agent` runtime，导致 packaged validator 无法独立运行。
- `.product-delivery/state.json` 在实现和验证过程中滞后，缺 `delivery_goal`、`handoff`、TASK queue 和 canonical executed evidence。
- TASK evidence 被实现后批量补齐，而不是在 TASK 边界通过 runtime API 推进。
- TASK-007 可在 formal closure artifact 和 current-feature canonical validator result 缺失时自称 `passed`。
- ROADMAP / Open Spec / planning files 可先于 canonical state 写入 `Executed`、`closed`、`closure in progress` 语言。

V1.0.8 新增硬规则：

- 插件包必须包含 `runtime/product_delivery_agent/` 完整 runtime。
- `scripts/validate-closure-artifact.py` 必须从 installed plugin cache 自举 `../runtime`，不得依赖源码仓库 `PYTHONPATH`。
- `state.json` 是 projection；critical transitions 必须写入 hash-linked `transition_journal`。
- journal 覆盖 `handoff_generated`、`task_completed`、`executed_browser_evidence_recorded`、`closure_validated`、`goal_completed`。
- `record_task_completion()` 只能完成当前 `current_task_cursor`，并要求 artifact hash、planned task hash、verification command、exit code 和 output。
- hand-edited terminal state 缺 `closure_validated` / `goal_completed` transition 时必须 fail closed。
- handoff / implementation state 缺 `handoff_generated` 或 TASK state 缺 `task_completed` transition 时必须阻塞。
- `closure_validation.feature_slug` 必须匹配当前 `feature_slug`；旧 feature validator result 不能复用。
- docs-state preflight 必须拦截 human-readable docs 领先 state 的执行/闭包声明。

验收补充：

- 在无源码 `PYTHONPATH`、`PYTHONNOUSERSITE=1` 下，从插件根或 installed cache 运行 packaged validator `--help` 必须成功。
- poisoned `closed` state 即使带有看似完整的 canonical metadata，只要缺 transition journal，就必须降级为 `closure_failed`。
- 跳过当前 cursor、批量补 TASK artifact、缺 verification output、或 planned task hash 不匹配时，TASK completion 必须失败。
- E2E JSON 在磁盘上存在但未通过 `record_executed_browser_evidence()` 写入 canonical state 时，closure 仍失败。
- docs 中出现当前 feature 的 `Executed` / `closed` / `closure in progress` 语言，而 state 尚未记录 executed evidence 或 closure validation 时，必须暴露 `docs_ahead_of_*` blocker。
