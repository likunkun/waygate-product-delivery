---
name: waygate-product-delivery
description: "Codex-native product delivery workflow with shorthand commands for start, status, inspect, pause, resume, close, and abandon."
---

# Product Delivery Agent

默认休眠，并且禁止自然语言隐式触发生命周期写操作。生命周期控制必须显式调用 `$waygate-product-delivery`，并提供一个严格 JSON 对象。Skill 必须将 JSON 原样交给 `scripts/waygate-control.py` 校验；非 JSON、未知字段、缺失字段或额外操作描述一律拒绝。支持 `inspect`、`status`、`start`、`confirm_input_enrichment`、`pause`、`resume`、`prepare_abandon`、`abandon`、`close` 和 `set_production_mode`。`review_mode_if_created=pending_selection` 会进入 `multi_agent_mode_selection`。旧 `stop()` 已退役，不得根据聊天中出现的关键词执行状态变更。

示例：`$waygate-product-delivery {"schema_version":"v1","action":"start","feature_slug":"v0-5-5-flow-preview","user_request":"增加逐页建课能力","start_mode":"resume_or_create","review_mode_if_created":"spawned_subagents_authorized"}`。

## Shorthand Commands

V1.0.32 起，`$waygate-product-delivery` 支持简写命令。Codex 必须在内部将简写展开为严格 JSON 后再传给 `scripts/waygate-control.py`；control.py 只接受 v1 严格 JSON，团队参数也必须通过其校验。

**识别规则：**
- 如果 `$waygate-product-delivery` 后面跟 `{...}`（合法 JSON 对象），则原样传给 control.py（现有行为不变）。
- 如果后面跟非 JSON 文本，则按以下 shorthand 表展开为完整 JSON，再传给 control.py 校验和执行。
- 展开过程对用户透明：Codex 内部完成翻译，只展示 control.py 的返回结果。

**Shorthand 命令表：**

| Shorthand | 展开后 JSON |
|---|---|
| `start <slug>` | 恢复已有 delivery 时展开为原有 JSON；新建 delivery 时必须改用带 `user_request` 的严格 JSON。 |
| `start <slug> "<request>"` | 同上，并加入 `"user_request":"<request>"`。 |
| `start <slug> multi-agent "<request>"` | 同上，`review_mode_if_created` 为 `"spawned_subagents_authorized"`，并加入 `user_request`。 |
| `start <slug> role-play "<request>"` | 同上，`review_mode_if_created` 为 `"role_simulation_allowed"`，并加入 `user_request`。 |
| `start <slug> team "<request>"` | start JSON 增加 `production_mode_if_created=team`；评审模式仍为 `pending_selection`。 |
| `start <slug> team multi-agent "<request>"` | 同时设置 `production_mode_if_created=team` 和 `review_mode_if_created=spawned_subagents_authorized`。 |
| `start <slug> team role-play "<request>"` | 生产仍使用真实成员；仅评审显式降级为 `role_simulation_allowed`。 |
| `status` | `{"schema_version":"v1","action":"status"}` |
| `inspect` | `{"schema_version":"v1","action":"inspect"}` |
| `inspect <slug>` | `{"schema_version":"v1","action":"inspect","feature_slug":"<slug>"}` |
| `pause` | `{"schema_version":"v1","action":"pause"}` |
| `resume` | `{"schema_version":"v1","action":"resume","delivery_id":"<current>"}` — Codex 必须先读 `.product-delivery/state.json` 取当前 `delivery_id` |
| `close` | `{"schema_version":"v1","action":"close"}` |
| `abandon` | 两步自动串联：先展开为 `prepare_abandon`（reason 默认为 `user_requested`），拿到 `confirmation_token` 后自动展开为 `abandon` |

**硬约束：**
- 展开后 JSON 与手写等价，仍通过 `validate_request()` 校验。
- 不支持的 shorthand 参数直接拒绝，不做猜测。
- `stop` 已退役，shorthand 也不支持。
- 不支持的关键词（如 `help`、`list`、`config`）直接拒绝并提示可用命令。
- `<slug>` 必须是合法的 feature slug（字母、数字、连字符、点、下划线）。

## Input Enrichment Gate

新建 delivery 必须先完成一次输入理解往返，恢复已有 delivery 不重复触发：

1. 将用户原始需求原样放入 `start.user_request` 并调用 `start`。
2. 如果返回 `result=input_enrichment_required`，只展示理解完善草案，至少包含目标、用户/场景、范围、约束、假设、开放问题和成功标准。
3. 在用户下一次回复前，不调用 Open Spec、评审、原型、测试或实现相关动作，也不修改代码。
4. 用户可以直接确认，也可以在同一条回复中提出修改；将修改合并为最终增强提示词后，只调用一次 `confirm_input_enrichment`。
5. `confirm_input_enrichment` 必须提交 `delivery_id`、`raw_request_sha256`、`enhanced_prompt` 和结构化 `understanding`。确认后才恢复原来的下一门。
6. 用户没有回复时停在 `input_enrichment_confirmation`，不得按默认理解继续执行。

## Active Mode Hard Rules

启动后必须创建或恢复 `.product-delivery/state.json`，并把它作为当前项目的权威状态。聊天总结、旧版本文档和 `progress.md` 都不能替代 gate evidence。

每次新交付必须生成独立 `delivery_id`，并将 `multi_agent_policy` 同时绑定当前 `delivery_id` 与 `feature_slug`。收到启动请求时，先调用只读 `inspect_startup_request(feature_slug=...)`；已关闭旧 feature 启动新 feature 时必须归档旧 state、创建新 delivery 并重新选择评审模式，未终态的其他 feature 不得被静默覆盖。

模型选择完全由用户和 Codex 宿主管理。Product Delivery 不选择、不记录、不验证、也不声称当前线程或 subagent 使用了任何特定模型。

恢复 v1.0.19–v1.0.21 的 active state 时，如果存在旧 `execution_model_policy`，必须调用公共 `retire_model_execution_policy()` 归档旧 policy、清理模型 blocker 并保留当前 delivery、feature、原型、review 和确认；不得重新 start 当前 delivery，也不得手改 state。旧模型 API 只保留一版明确退役错误。

active mode 下必须先使用这些 baseline skills：`planning-with-files`、`waygate-product-delivery`。`planning-with-files` 必须执行 session catchup，并读取或创建 `task_plan.md`、`findings.md`、`progress.md`。

## Blocking Gates

产品设计顺序必须是 Open Spec、场景矩阵、UI 原型或非 UI 行为契约草稿，再进行产品/场景评审。评审通过后调用 `prepare_product_baseline_confirmation()` 和 `confirm_product_baseline()`，先确认需求范围和 UI 原型或非 UI 行为契约。产品基线确认前不得生成详细测试用例、planned E2E 或 coverage audit。基线确认后才生成测试覆盖计划，完成 test/test_coverage review 后调用 `prepare_test_coverage_confirmation()` 和 `confirm_test_coverage_plan()`。两次正式确认完成前禁止实现。

禁止实现，直到以下门禁全部满足：

1. 当前 feature slug 已写入 `.product-delivery/state.json`。
2. 当前 feature 已使用 `open-spec` 生成 `docs/open-spec/<feature-slug>/`，包含 `00-change-request.md` 到 `08-stage-handoff.md`。
3. 项目类型已经确认。UI 项目必须进入本地 1:1 HTML 原型 gate；非 UI 项目必须进入 behavior contract gate。
4. UI 原型生成后必须先调用 `record_ui_prototype_design_bundle()` 通过内部 `prototype_design_integrity` 门禁，再使用 `ui-ux-pro-max` 和 `webapp-testing` 完成产品/场景评审；两者通过后才能准备 `product_baseline` 确认。
5. 产品基线确认后才使用 `test-strategy` 或 `testing-strategy` 生成测试覆盖计划。
6. closure 必须使用 `open-spec-feature-closure` 和 `superpowers:verification-before-completion`。

禁止实现的条件：未完成 `product_baseline` 和 `test_coverage_plan` 两次确认、未冻结 planned E2E obligations、或 closure validator 未通过。实现前只能冻结 planned E2E，真实 browser evidence 必须在实现后落盘并校验。

V1.0.3 强制两道状态机出口：pre-handoff gate 和 pre-closure gate。pre-handoff 通过前禁止开始实现；pre-closure 和 closure validator 通过前禁止声明完成。

UI 原型是 `product_baseline` 的一部分。原型、prototype contract 或截图集合只有在产品/场景评审通过后，才通过 `prepare_product_baseline_confirmation()` 生成当前 nonce；用户使用 `confirm_product_baseline()` 一次确认需求范围和最终原型。截图、Playwright evidence 和 static review 只能作为辅助证据，不能替代该确认；裸 `继续` 不能替代当前 nonce。只有用户明确提出需求或原型修改，才允许调用 `record_user_requested_change()` 重开基线；内部评审不得自行改原型或制造重复确认。

V1.0.14 起，UI prototype review 必须声明 `ui_change_type`。默认增量 UI 是 `incremental_existing_surface`，必须记录上一版 feature、baseline surface paths、baseline user journey、continuity mapping 和 prototype delta summary。增量 UI 不得用独立工作台或平行新页面替代上一版真实主路径。`new_surface_in_existing_product` 和 `greenfield_ui` 必须记录有意义的 `new_surface_justification`，并随 `product_baseline` 一起确认，不增加第三次确认。用户明确要求修改 prototype 后，旧 product baseline、test coverage plan、相关 review 和实现授权必须 stale；重新 review 前不得进入实现。

V1.0.23 起，UI 原型生成后、multi-Agent 产品/场景评审前必须调用 `record_ui_prototype_design_bundle()`。bundle 的 `clean_surface` 绑定产品 HTML、prototype contract、纯净 PNG、semantic snapshot，以及全部关键 state/viewport 的 browser preflight。semantic snapshot 和 browser preflight 必须是固定 schema 的 JSON artifact，probe 必须绑定 snapshot、截图与 region identity 的 runtime hash；调用方自报的 `status=passed` 或 annotation flags 不能作为通过依据。`product_context_contract` 的每个 coverage row 必须引用结构化 `artifact_path`/`artifact_sha256` 设计证据，并正向覆盖 `global_shell`、`navigation`、`visual_language`、`information_density`、`component_system` 和 `responsive_behavior`。可选 `review_annotation_set` 必须是独立评审页，通过外部 region anchor 引用纯净原型；产品原型不得加载标注资源、注入 overlay、暴露标注查询模式或把评审编号混入产品页面。真实产品引导只能作为 `intended_product_ui_callouts`，并绑定需求、场景、触发条件、生命周期和 contract region。

`prototype_design_integrity` 门禁验证客观事实，多 Agent 判断设计质量。门禁负责路径、hash、状态/viewport 覆盖、全局上下文六维覆盖和标注分离，失败时评审不得覆盖；评审负责判断基线是否有代表性、局部设计是否与全局产品协调、例外是否合理。scenario 和 `ui_conformance` review 必须绑定当前 bundle/audit hash，记录完整 `reviewed_design_dimensions`、`global_visual_continuity_findings` 和 `annotation_separation_findings`；空 findings 不能替代正向覆盖证据。

`product_domain_hash` 只绑定用户实际确认的纯净产品原型、contract、截图和全局上下文；`review_domain_hash` 只绑定内部设计审计和标注；`bundle_hash` 绑定两域关系。只有产品域变化才使 `product_baseline`、`test_coverage_plan` 和下游授权 stale。仅标注变化只重开绑定旧标注 revision 的内部 scenario review，不增加用户确认。`prepare_product_baseline_confirmation()` 只能展示 `clean_surface` 和纯净截图，不得展示 review-only artifact。已确认的 v1.0.22 active delivery 在未修改原型或重开基线时保持 grandfathered；尚未确认的 UI delivery 必须先补齐 bundle。用户仍只确认 `product_baseline` 与 `test_coverage_plan` 两次，closure schema 保持 `v0.11`。

多 agent scenario/test review 必须落成结构化 artifact，包含 independent positions、cross challenges、revisions、final adjudication 和 blocking findings。session log、Open Spec 摘要、quick review 不能替代这些 artifact。

planned E2E、executed browser evidence、coverage audit 和 closure artifact 必须按 `scenario_id`、`obligation_id`、`test_id`、user story、journey 对账；UI planned E2E obligation 必须记录 `baseline_entry_path`，测试必须从上一版真实入口进入；supporting evidence 不能替代 UI journey browser E2E。V1.0.13 起，UI journey closure 只接受 `full_stack_browser_e2e`。`mocked_api_browser_e2e` 和 `static_or_prototype_browser_check` 只能作为 supporting evidence，除非有结构化豁免允许 closure。executed browser evidence 必须记录 acceptance URL、API health identity、network probe artifact、business API request summary 和 `mocked_routes`；未豁免 business API mock 必须阻塞 closure。

V1.0.15 起，UI journey closure 还必须是 role-accurate、ordinary-path、independently verifiable evidence。UI planned E2E obligation 必须记录 `required_actor_roles`、`path_kind`、`ordinary_entry_path` 和 `data_state_contract`。executed browser evidence 必须记录 `executed_actor_roles`、`primary_actor_role`、`actor_identity_evidence`、`ordinary_path_observed`、`execution_segment_id` 和 `test_title_or_step`。Teacher 主路径不能由 admin browser E2E 关闭；主路径、可见异常和权限拒绝必须有可定位、可失败的独立 execution segment。API/Go/Vitest 等 supporting evidence 可以证明后端行为，但不能替代 role-accurate Browser E2E。

V1.0.16 起，prototype confirmation 必须冻结 canonical `prototype_contract`、prototype HTML hash 和 prototype PNG screenshot set hash。实现与 full-stack Browser E2E 完成后，必须调用 `record_prototype_production_conformance`，为每个冻结 surface/state/viewport 记录 production PNG、controlled semantic snapshot、region/relationship/interaction observation 和 execution segment 绑定，并声明 production route/component provenance。`.txt`、HTML、JSON、伪 PNG、路径逃逸或被修改的证据必须 fail closed。formal closure 前还必须有独立 `ui_conformance` multi-agent review，完整覆盖所有冻结 region；`test_implementation` 不能替代它。closure schema `v0.11` 必须绑定 prototype、contract、production conformance 和 UI conformance review hashes。

用户面对的确认只保留两次：第一次 `product_baseline`，确认需求范围和 UI 原型或非 UI 行为契约；第二次 `test_coverage_plan`，确认 planned E2E 和测试覆盖计划。需求或原型变化会同时使两次确认 stale；仅测试覆盖语义变化只使第二次确认 stale；测试 ID 拆分、内部断言增强和测试实现修复不得使产品基线 stale。legacy `confirm_ui_prototype()`、独立 Open Spec/E2E confirmation 和 combined confirmation 只用于迁移兼容，现代 delivery 不再编排这些入口。`handoff`、coverage/review 接受、`implementation_launch_authorization`、closure 等都是内部 evidence/gate；满足条件后必须自动推进，不得要求额外用户确认。

V1.0.9 起，测试审查拆成两个不可互相替代的 gate。实现授权前必须通过 `multi_agent_test_coverage_review`，评审对象是测试用例覆盖范围，必须检查 `US/J/SC/AC/TASK/TC` 映射，并把集合型场景展开到 item-level coverage。例如二级工作台 tab、三级详情入口、人员维护、模板、Agent 规则、绑定、供应商、白名单、告警忽略等，必须看到每一项的 action assertion。实现和 E2E 运行后、formal closure 前必须通过 `multi_agent_test_implementation_review`，评审对象是真实测试代码、Playwright/browser 脚本、执行日志、截图和 trace。`marker exists`、函数名存在、静态说明面板、只点第一个按钮，都必须标记为 false-positive risk。如果发现 Playwright、MSW、service worker、fetch/XHR patch 或 fixture server mock 了当前 journey 依赖的 business API，却仍声称覆盖 UI journey，必须作为 blocking finding，并记录在 `business_api_mock_findings`。V1.0.15 起，`multi_agent_test_coverage_review` 必须记录 `role_journey_coverage`、`ordinary_path_coverage` 和 `scenario_granularity_findings`；`multi_agent_test_implementation_review` 必须记录 `actor_role_findings`、`evidence_distribution_findings`、`annotation_only_findings` 和 `ordinary_path_findings`。`reviewed_test_ids` 必须覆盖 planned test IDs，`verified_action_assertions` 必须覆盖每个 planned coverage item，不能只抽样代表项或只靠 annotation 关闭场景。如果发现 coverage gap，必须先补 RED test 让当前浅实现失败，再继续修 UI 或 E2E。

## Main Flow Continuation

active mode 下每次准备 final summary、普通 stop guard 或交付总结前，必须先运行 Product Delivery continuation guard，并以 `.product-delivery/state.json` 推导 `must_continue`、`wait_for_user`、`blocked`、`complete`。当结果是 `must_continue` 时，说明主流程已有 next gate 或 remaining TASK，如果没有 pending user confirmation、需求澄清、外部环境阻塞或连续失败阻塞，就必须继续推进下一 gate，不要用聊天总结结束当前交付主流程。

`wait_for_user` 只允许用于真实用户输入点：当前 `product_baseline` 确认、`test_coverage_plan` 确认、评审模式选择、必要需求澄清、用户主动暂停或停止。`blocked` 必须说明 blocker；如果 blocker 是 `canonical_closure_plugin_version`，下一步是使用当前 installed packaged `product_delivery_agent.finalization` 重新生成 canonical closure，或在启动新 feature 前显式清理/迁移旧状态。`complete` 只有在 canonical closure、feature closure 和 delivery goal 都满足当前插件规则时才成立。

## Verified Codex Host Goal Continuation

V1.0.24 起，内部 `delivery_goal` 只表示 TASK 计划，不得冒充 Codex Host Goal。第二次 `test_coverage_plan` 确认同时授权当前 delivery 创建和推进真实 Host Goal，runtime 使用独立 `host_goal_binding` 绑定 `delivery_id`、`feature_slug`、launch package、objective hash、binding generation 和宿主返回的稳定标识。

### V1.0.34 Emergency Blocked-Goal Recovery

仅 delivery `26a6049314fe48caa1e7d4dcdb45c171` 可使用 `scripts/recover-blocked-host-goal-v1034.py` 解除 1.0.34 blocked-binding 死锁。不得手改 `.product-delivery/state.json`，不得将该恢复器用于其他 delivery，也不得借此登记正式评审或 closure。

必须回到冻结的 owner thread，先由用户恢复 Host Goal，再通过宿主 `get_goal` 取得 fresh、精确匹配且 `status=active` 的 observation。将严格 v1 JSON 通过 stdin 交给恢复器；先以 `dry_run=true` 执行并确认 state 字节未变化，再使用完全相同的 observation 以 `dry_run=false` 执行一次。恢复器会锁定冻结 state 文件 SHA-256、owner thread 和原始 `c7ee45f…f9234` runtime receipt，并验证 delivery、feature、binding nonce、objective hash、Goal identifiers、journal、stage、完整 TASK、browser evidence、review/closure 状态，以及不存在 `human_wait`、pending checkpoint 或 authorized transition。

正式恢复只归档原 binding、记录 observation、追加 hash-linked `host_goal_blocked_binding_recovered` event，并把 binding 恢复为 `active`、`next_gate` 恢复为 `multi_agent_test_implementation_review`。任何 identity、状态或 runtime package hash 不匹配都必须 fail closed；重复执行必须拒绝。恢复后只运行 `status`、`inspect` 和 continuation guard 验证 `must_continue`，本次紧急恢复不得继续后续 review 或 closure。

对于仍在 `implementation_in_progress` 的其他 1.0.34 delivery，如果 binding 为 `blocked` 且不存在 `human_wait`、pending checkpoint 或 authorized transition，可使用 `scripts/recover-blocked-host-goal-current-task-v1034.py`。它按请求锁定当前 delivery、feature、binding nonce、objective hash、state 文件 SHA-256、owner thread 和当前 runtime receipt，只接受 fresh、精确匹配且 `status=active` 的 `get_goal` observation，并只把 `next_gate` 恢复为当前未完成 TASK。必须先 `dry_run=true` 且 state 字节不变，再用同一 observation `dry_run=false` 一次；恢复后不得借此登记证据或完成 gate，只允许先验证 `status` / `inspect` / continuation guard。

### V1.0.37 Runtime Receipt Recovery

仅当现有 active、nonterminal delivery 的 `runtime_provenance` 精确等于受支持的 1.0.36 receipt，并且 journal 包含完整的 `1.0.34 delivery_activated -> 1.0.36 runtime_receipt_recovered` 链时，才允许原位迁移到 1.0.37。必须回到 `host_goal_owner` 记录的原 coordinator thread，并保持 `CODEX_THREAD_ID`、binding owner、delivery、feature 和 current-delivery multi-Agent policy 一致；不得从 spawned subagent 执行。

用户必须原样授权 `用户确认恢复 1.0.36 runtime receipt 到 1.0.37`。然后在原 owner thread 调用 `recover_runtime_receipt()`，或执行 `scripts/recover-runtime-receipt-v1036-to-v1037.py --project-root <project-root> --authorization '用户确认恢复 1.0.36 runtime receipt 到 1.0.37'`。恢复器在语义上只替换 runtime receipt 并追加一条 hash-linked `runtime_receipt_recovered` event；原子写入会正常刷新协议 `updated_at` 和 canonical delivery-layout mirrors，但 delivery、Host Goal、TASK、确认、评审和证据必须保持不变。未知 receipt、journal 篡改、缺少 1.0.34->1.0.36 链、外来线程、终态 delivery 或重复迁移必须 fail closed。此入口是严格的一次性兼容例外，不得作为通用升级器，也不得改用 `recover_legacy_active_delivery()`、v1034 blocked-Goal 恢复器、Waygate `resume` 或 Host Goal Resume 代替。

### V1.1.0 Orphaned Blocked-Binding Recovery

当 active implementation delivery 的 Host Goal binding 为 `blocked`，且 `human_wait`、pending checkpoint 与 authorized transition 都为空时，使用 `scripts/recover-orphaned-blocked-host-goal-v110.py --project-root <repo>`。恢复请求通过 stdin 提供严格 JSON，必须包含冻结 state SHA-256、精确授权语、owner host turn、fresh `get_goal=active` observation 与 `dry_run`。必须先 dry-run 并确认 state 字节不变，再用相同 observation 正式恢复。入口只恢复当前 TASK，校验 runtime provenance、objective、threadId 与 journal，追加 `host_goal_orphaned_binding_recovered`，并签发一次性 `user_resume` transition；不得用于 human decision、终态 delivery 或任意 gate 跳转。

handoff 后必须按顺序执行：先调用 `prepare_host_goal_activation()`，再调用宿主 `get_goal`；确认不存在 Goal 后才调用 `create_goal`；创建后再次调用 `get_goal`。每次结果都必须通过 `record_host_goal_observation(checkpoint_id, observation)` 落盘。其他未完成 Goal、objective 不匹配、stale observation 都必须 fail closed。非恢复 checkpoint 重放必须拒绝；恢复回调只有输入、attempt ID 和 delivery identity 完全相同时才允许无写入幂等返回。Goal 工具不可用时记录 unavailable observation；瞬时故障按下述恢复契约处理，工具未暴露或权限不足时阻塞。

### V1.2.2 Host Goal 自动恢复

`missing`、提前 `complete` 和瞬时 unavailable 不再要求每次人工授权。runtime 归档旧 binding、保留 delivery/feature/launch package/owner/当前 gate 与 TASK 证据，签发新的 generation、nonce 和 objective，并写入 hash-linked `host_goal_auto_recreated`。最多三个恢复 attempt，退避依次 5、15、30 秒；初始故障不是恢复 attempt。每个 attempt 包含稳定 `attempt_id`、原因、retry_at 与诊断历史，第三次恢复失败后记录 `host_goal_auto_recovery_exhausted` 并等待人工授权。成功后保留本交付已消耗的自动恢复预算，防止频繁成功/断线绕过上限。

故障 observation response、status/inspect 与 Stop guard 暴露 `recovery_action`、`recovery_attempt`、`recovery_attempt_id`、`retry_after_seconds`、`retry_at`。主线程调用 `prepare_host_goal_auto_recovery()`；若 `operation=wait_for_retry`，由支持该契约的宿主按 `retry_at` 调度同一 owner thread，等待期间不得写 canonical state、调用 Goal 工具或忙轮询。到期取得 checkpoint 后执行指定 Goal 工具，并调用 `record_host_goal_auto_recovery(checkpoint_id, observation, attempt_id=recovery_attempt_id)`。prepare 和 record 在 workspace lock 中重新加载 state；checkpoint projection、identity 与 journal 必须匹配，重复回调不得重复创建 Goal 或重复追加 transition。

网关错误按实际 error_type 记录，例如 `connection_error`、`gateway_restart`、`timeout`、`transport_error`、`service_unavailable`、`rate_limit`、`thread_unavailable`、`host_goal_lost`。恢复探测先 get_goal；旧 Goal 仍 active 时只重绑精确 archived objective/thread/identifier，不能创建重复 Goal；missing 或绑定的旧 Goal 已 complete 才能进入 create/get 验证。observed blocked 只有明确瞬时 error_type 或 Goal blockedReason 才进入 `resume_host_goal` 契约；宿主使用其原生恢复能力后再次 get_goal 验证。Goal 仍 blocked 时只能有限重试，不能伪造 active、覆盖未完成 Goal 或为换 Goal 提前标记 complete。未知原因 blocked、human_wait、真实外部阻塞和显式 update_goal(blocked) 保留人工语义。

插件没有计时器或内部 sleep。当前 Paseo CLI 的 schedule 是 cron 周期调度，不能证明 5/15/30 秒同线程唤醒已经接通；若宿主没有延迟重试或 Goal Resume 能力，须明确说明 scheduler_required=host，并保留恢复契约，不能宣称无人值守自动恢复已生效。用户 pause/stop/abandon、终态交付或 canonical closure 后禁止自动重建。1.2.2 只用于新线程和新 runtime，不原位迁移 1.2.1 活跃交付；安装时备份并保留旧缓存。

每个 post-handoff turn 开始，以及 TASK/stage、review、closure、final、stop 和 Goal 状态更新前，调用 `prepare_host_goal_reconciliation(operation, target_gate, host_turn_id=...)`，再使用 `get_goal` 或该 checkpoint 指定的 `update_goal`，最后调用 `record_host_goal_observation()`。同一 stage 内低层文件写入不需要重复查询，但任何 canonical gate 写入都必须消费一条新鲜、目标 gate 匹配的一次性 observation。

`wait_for_user` 必须生成并复用稳定 `decision_id`、prompt hash 和 blocker fingerprint；同一问题只展示一次，自动 Goal turn 不得重复提问，也不得修改产品、测试、证据或 closure。用户回复必须匹配当前 `decision_id`，并通过 `user_resume` 再次观察 Host Goal active 后才能继续。只有三个不同 `host_turn_id` 连续观察到相同 blocker，才允许调用 `update_goal(status=blocked)`。

canonical closure 通过前禁止 `update_goal(status=complete)`；closure 后先 `pre_complete` 对账，再调用 `update_goal(status=complete)`，最后用 `get_goal` 验证 complete，之后才允许正式 final。Goal 曾经 active 后若 missing 或提前 complete，1.2.2 按自动恢复契约处理；预算耗尽后调用 `authorize_host_goal_reactivation()` 取得新的用户授权。`action=abandon` 需要 `stop_delivery` 对账，停止后 binding 标记为 `stopped_by_user`，不得自动恢复。

V1.0.25 起，Goal 尚未 ever active 且 activation checkpoint 因后续合法 transition 过期时，必须调用 `recover_stale_host_goal_checkpoint(checkpoint_id)`。runtime 会验证 delivery、feature、authorization、generation、nonce、objective 和 journal hash chain，归档旧 checkpoint，追加 `host_goal_checkpoint_superseded` transition，并以相同 binding identity 重新签发 `inspect_before_activation` checkpoint。不得手改 state、重新 start delivery 或重放旧 checkpoint。

V1.0.26 起，每个 delivery 在启动时把宿主 `CODEX_THREAD_ID` 冻结为 `host_goal_owner` 的 coordinator thread。Host Goal activation、observation、reconciliation、post-handoff canonical write 和 completion 必须同时匹配当前 `CODEX_THREAD_ID`、owner thread、binding owner 和宿主 Goal 的 `threadId`；缺失或不匹配全部 fail closed。spawned review subagent 只能产出结构化评审，不得激活、恢复、接管或完成 Host Goal。

v1.0.25 及更早的非终态 state 缺少 owner metadata 时迁移为 `legacy_unverified`，不得从旧 binding 推断 coordinator。必须在没有 active/blocked Goal 的新用户可见顶层线程中使用固定授权语 `恢复交付主线程，接管当前 Host Goal`，依次调用 `prepare_host_goal_owner_claim()`、宿主 `get_goal`、`record_host_goal_owner_claim_observation()`。只有 `get_goal` 返回 missing 或 complete 才允许 transfer；旧 binding 和未消费 checkpoint 完整归档为 `orphaned_unreachable`，journal 追加 `host_goal_owner_transferred`，然后使用新 generation、nonce 和精确 objective 重新执行 `get_goal -> create_goal -> get_goal`。active/blocked foreign Goal 禁止覆盖。owner-claim checkpoint 若因合法 transition 过期，必须调用 `recover_stale_host_goal_owner_claim(checkpoint_id)` 归档旧 claim、追加 `host_goal_owner_claim_superseded` 并签发新 claim；不得手删 `pending_claim`。

active Waygate delivery 只能使用当前安装的 `waygate-product-delivery` runtime。禁止调用旧 `product-delivery-agent@1.0.8` runtime 写入同一 delivery；旧 runtime 产生的历史 evidence 可以保留，但后续 canonical transition 必须由当前 Waygate runtime 完成。

V1.0.27 起，`start()` 必须写入当前 Waygate 的 `runtime_provenance`（插件名、版本和 runtime package hash）、非空 delivery ID、owner metadata，以及 hash-linked `delivery_activated` journal event。`status()` 只能将 active state 报告为 `verified_waygate`、`legacy_unverified` 或 `invalid_runtime`。缺少或不匹配 receipt、policy、owner 或 journal 的 active state 不得推进任何门禁。必须调用 `recover_legacy_active_delivery()` 归档原始 state 后创建新 delivery；不得手改 state，也不得复用旧 confirmation、review 或 implementation authorization。

V1.0.28 起，已确认 UI 的 `implementation_baseline` 是实现阶段的权威产品基线，不是重新设计提示。它必须只读绑定 prototype design bundle、prototype contract、产品 HTML、设计系统、纯净截图、surface/state/viewport、region、interaction 及其 hash。用户可见 TASK 必须声明 `ui_impact` 并通过 `prototype_bindings` 绑定当前任务涉及的精确原型切片；非 UI TASK 必须声明 `ui_impact=none` 及理由。handoff 和当前 TASK 提示只注入当前绑定切片，明确要求保持 route、区域层级、控件顺序、关键状态和交互结果一致；允许调整内部代码架构，禁止自行增删、移动、合并或重设计可见 UI。无法按原型实现时必须停止 TASK 并发起 CR，不得静默降级。

V1.0.42 起，新 UI delivery 用 `prepare_ui_visual_loop()` / `record_ui_visual_loop()` 做开发态壳层对照：一次只比当前 TASK 的一个绑定单元，对照参考图并只修 `next_fix[0]`。TASK 完成条件是绑定单元 visual loop 通过加上本 TASK 测试；原型与生产的像素差只作诊断，2%/5% 不再作为 TASK 或 closure 门禁。数据区允许行数、数值和高度变化。循环不消耗 Host Goal，也不能关闭 obligation。1.0.38 及更早、未启用 visual loop policy 的 UI delivery 仍走 `record_task_prototype_conformance()`。

每个未升级的 UI TASK 完成前必须调用 `record_task_prototype_conformance()`，记录生产截图、semantic snapshot、结构与交互观察、geometry、computed-style fingerprint 和像素差异。route、region 存在性、父子层级、显示顺序、可访问角色/名称、必要控件及绑定 interaction 零容忍；关键区域像素差异默认不超过 2%，全页面不超过 5%，单像素阈值为 0.2；geometry 偏差默认不超过 4 CSS px 或 viewport 的 1%，取较大值。证据缺失是 `failed`，渲染环境不稳定是 `inconclusive`，两者都阻止 TASK 完成。检查失败必须修复生产实现，不得修改冻结原型、mask 或阈值。确需改变可见设计时必须走 CR 并重开产品基线。

产品域、视觉阈值、mask 或 TASK binding 变化必须让相关 TASK、conformance evidence 和实现授权 stale；仅 `review_annotation_set` 变化不影响 implementation baseline。新 UI delivery 强制执行上述规则；已确认 product baseline 的 active UI delivery 保持 grandfathered，除非原型被重开，重开后必须升级到 V1.0.28 门禁。最终 closure 仍需 full-stack Browser E2E、全量 production conformance 和独立 `ui_conformance` review。

V1.0.29 起，权威 TASK 队列由 runtime 从 planned E2E obligations 按 Journey 派生。默认一个 Journey 一个 TASK；超过 action/item/surface/happy-path 阈值必须再拆。不允许独立脚手架 TASK。第一个 Journey TASK 只吸收最小壳，后续 Journey 复用。UI obligation 必须声明 `surface_ids`；TASK bindings 只等于其 obligation 并集。Agent 只能细化标题、描述、验证说明和更窄绑定，不能合并、删除或转移 E2E。派生后回写 coverage `task` 列，并把 `task_queue_hash` 纳入 test_coverage 评审和确认。当前 TASK 必须先通过本切片 `record_task_executed_evidence()` 和原型一致性才能完成。全部切片通过后，UI 交付的 `record_executed_browser_evidence()` 和 non-UI 交付的 `record_executed_behavior_evidence()` 只接受切片证据并集加回归；non-UI 行为证据绑定真实 `evidence_path` 和 `trace_path` 文件 hash，不使用 browser-only probe 或 strength 字段。新 delivery 强制生效；已确认 `test_coverage_plan` 的活跃 delivery 保持 grandfathered，直到测试覆盖被重开。

V1.0.30 起，执行期 `test_implementation` 和 `ui_conformance` multi-agent review 必须实行批次屏障：同轮 2–3 个评审者基于同一输入快照独立完成 positions、cross challenges 和 revisions，全部评审者返回前不得修改评审对象；汇总者先去重并冻结完整问题清单，再批量修复本轮全部已接受问题，完成后只做一次统一复验。评审者失败必须重试、替换或记录 `blocked_with_reason`，不得收到一个问题就修改并重启评审。UI TASK 像素比较仍以关键区域 2% 和完整页面 5% 为自动通过目标。首次纯像素失败后必须使用 `superpowers:systematic-debugging` 连续完成两轮真实修复复验；相同证据、inconclusive 环境或非像素失败不计数。两轮仍失败才创建稳定用户 decision 并主动询问；用户也可提前主动裁决。只有像素差异可调用 `record_task_visual_conformance_adjudication()`，结构、语义、geometry、交互和证据失败不得豁免。接受的差异必须在最终 `ui_conformance.accepted_visual_deviations` 中逐项引用。

V1.0.33 起，视觉裁决使用统一失败分类器，不再把可裁决视觉差异限定为 pixel-only。像素阈值失败、`geometry_mismatch`，以及元素仍可见且视口溢出不超过 4 CSS px 或 viewport 1%（取较大值）的受控 `geometry_invalid`，统一标记为 `visual_adjudicable` 并共用两轮修复计数。缺失、非数值、NaN、零尺寸、不可见或明显离屏的 geometry，以及结构、语义、交互和证据错误，必须标记为 `hard_blocking`，不得裁决。相同证据或 inconclusive 环境不计轮次；两轮后只生成一个稳定 decision，用户可提前主动接受，拒绝后开启新的两轮周期。接受记录必须逐项保存 pixel/geometry deviation，并由最终 `ui_conformance.accepted_visual_deviations` 引用；裁决不得修改冻结原型或重开产品基线。

V1.0.34 起，高保真产品原型只能包含真实产品内容。新建或重开的 UI 原型必须使用 bundle v2，提交 `acceptance_content_separation`，并绑定 review-only 的 `prototype-acceptance-content-scan-v1` 报告。门禁同时扫描静态 DOM、渲染 DOM、semantic snapshot、属性、资源和可激活 review mode；验收标准、测试步骤/预期结果、AC/TC/SC 编号、评审意见、证据路径、mock/fixture/test-only 和开发说明都必须移出 clean surface。不可见 `data-testid` 与稳定 ID 可以保留。可能属于真实产品的文案必须通过 `product_content_mappings` 绑定到具备真实角色、需求、场景、触发和生命周期的 `intended_product_ui_callouts`。污染属于 `prototype_design_integrity` 硬错误，不得进入视觉偏差裁决。历史 v1 bundle 与已确认 active delivery 不自动重开；原型修改、替换或主动重开后必须升级 v2。scan report、mapping 和验收说明只进入 review/integrity domain，不进入 `product_domain_hash`。

不得使用 20 秒 watchdog、定时发送 `继续`、网络异常后盲目重试或把 hook 输出伪装成用户输入。插件 hook 只能读取状态并提供 guardrail；真正的跨 turn 续跑必须由 Codex Host Goal 调度。只有真实宿主 smoke 证明无需用户发送 `继续` 也会进入下一 turn，才可以宣称自动续跑。

## Goal-Driven Closure

pre-handoff 通过后必须创建 Product Delivery implementation delivery goal，目标覆盖完整 planned TASK queue、executed E2E evidence 和 formal closure。不要在 TASK 未完成时停止；每次准备停止或总结前必须检查 remaining TASK。如果还有 TASK 且没有用户确认、外部环境阻塞或连续失败阻塞，就继续执行下一 TASK。closure validator 未通过时不要 complete goal，closure 失败时 goal 保持 active，下一步必须修复 closure evidence。`progress.md` 和聊天总结不能替代 delivery goal status。

final summary、stop、goal complete 前必须运行 `validate-closure-artifact.py --project-root <repo> --closure-artifact <path>`。该脚本必须非 0 fail closed，并写入 `.product-delivery/artifacts/closure-validator-result.md`。V1.0.8 起，只有调用 installed packaged `product_delivery_agent.finalization` 并写入 `closure_validation.validator=product_delivery_agent.finalization`、`canonical_schema_version=v0.11`、`plugin_version=1.2.3`、`closure_artifact_sha256`、`transition_journal` closure event 的结果才是 Product Delivery closure truth。target-specific validator、repo-local `scripts/verify/validate-closure-artifact.py`、Open Spec closure claim、聊天总结和 `progress.md` 只能作为 supporting evidence，不能解除 closure blocker。任何 closure-like 状态，包括 `closed_local_product_delivery`、`blocking_gates.closure=true`、`implementation.current_task=COMPLETE` 或 `delivery_goal.status=complete`，都必须同时满足 `closure_validation.status=passed`、`feature_closure.status=passed`、`delivery_goal.status=complete`；UI 项目还必须满足 `executed_browser_evidence.status=passed`。missing goal 在 handoff 后、implementation 中或 closure-like 状态下必须阻塞。

V1.0.8 起，critical transitions 必须写入 hash-linked `transition_journal`。handoff、TASK completion、executed browser evidence、closure validation、goal complete 都必须来自 canonical runtime API；手写 `.product-delivery/state.json`、批量补 TASK JSON、旧 feature closure result 或 docs 领先状态必须 fail closed。

multi-agent review 必须记录 `review_mode`。`spawned_subagents` 是强证据；该模式还必须记录 2–3 个唯一的 `reviewer_agent_ids` 和真实 `reviewer_spawn_source`；模型名称不是 review evidence。它只在 `execution_authorization` 对 `authorization_scope=current_delivery` 有效时可接受。授权只覆盖 scenario、test、test_coverage、test_implementation、ui_conformance 结构化 review gate，不授权普通实现、文件读取或串行修复自动并行。`role_simulation` 是弱证据，只有新建 delivery 时显式设置 `review_mode_if_created=role_simulation_allowed` 才允许；`blocked_with_reason` 不能通过 handoff。

进入实现前必须记录 canonical `implementation_launch_authorization`，但它是 runtime 自动授权 artifact，不是用户确认 gate。授权必须绑定当前 `feature_slug`、review mode、prototype hash、planned E2E、TASK queue、required commands 和 nonce/hash。scope、TASK、review mode、prototype 或 planned E2E 改变后必须自动刷新授权并继续 handoff。

custom artifact 可以作为 supporting evidence，但不能授权实现。自定义 `*-pre-handoff-gate.json`、Open Spec 总结、task artifact、prototype screenshot 或磁盘 E2E JSON 都不能替代 canonical handoff、delivery goal、implementation launch authorization、executed browser evidence 或 closure validation。

V1.0.18 起，如果当前 authorized launch package 与旧 `delivery_goal` 的 `launch_package_hash` 不一致，必须调用 canonical `recover_stale_launch_package()`；runtime 会归档旧 implementation package、写入 `implementation_package_superseded` transition，并仅按完全一致的 `planned_task_hash` 复用 TASK completion。禁止手改 state 或只删除 stale blocker。

其他技能只能辅助，不能替代 Product Delivery 主流程。项目 `AGENTS.md`、Waygate/controller 规则仍要遵守，但不得绕过 Product Delivery 的 Open Spec、UI/非 UI gate、测试覆盖和 closure evidence。

## Current Feature Evidence

检查 Open Spec 或原型时必须按当前 feature slug 匹配。旧版本 `docs/open-spec/`、旧 prototype、聊天总结、`progress.md` 都不能替代当前 feature gate evidence。

## V1.2.3 专家 Agent 可识别命名

生产者和评审者必须使用 runtime 生成的稳定身份：`agent_display_name` 是“角色｜职责｜业务版本”，`agent_spawn_name` 是 Paseo/Codex 可接受的 `lower_snake_case` 语义任务名。名称来自 `role_id`、席位和当前 `feature_slug`，模型不得临时自造；`role_id`、task/seat/role definition hash 和真实 `agent_id` 继续保留。宿主支持时可对真实 thread/Agent ID 调用 `thread/name/set` 或等价 title API；不支持时必须显示语义任务名并标记 semantic fallback，不能声称中文标题已被宿主设置。

派发前把“可读专家名 → 语义任务名 → 席位/工作包 → 待派发”展示给用户。创建子 Agent 时使用对应 `agent_spawn_name`，首条消息必须以 `【agent_display_name】` 开头，并包含角色使命、必查项、允许写入、禁止事项和完整绑定任务/brief。宿主返回后立即记录真实 `agent_id`、`spawn_source`、显示名和语义名；状态、地图、TeamRun/Review 报告同时展示可读名和真实 ID。历史身份保留原值并标记为历史，不覆盖旧结果。

## V1.2.1 评审专家派发与展示

这套规则适用于 coordinator/team 两种生产模式，以及 scenario、test、test_coverage、test_implementation、ui_conformance 五类评审。八个逻辑角色由每门两个固定席位承担，同席的每个角色分别返回结构化结果。

1. 主线程调用 `prepare_review_role_tasks(review_type, input_refs)`，取得冻结的 `role_context`、`review_seats`、`role_tasks`、按席分组的 `review_briefs` 和命名侧车 `dispatch_briefs`。每个 brief 包含 `seat_id/display_name/role_ids/seat_task_hash/role_tasks/role_cards`；卡内含 mission、task_steps、must_check、quality_rubric 和五类 examples。输入不足或绑定失效时先解决准备错误。
2. 根据 seat_id 选择对应 `dispatch_briefs`：`spawn_agent(task_name=dispatch_brief.agent_spawn_name, message=dispatch_brief.dispatch_message, fork_turns=none)` 或宿主等价调用。完整派发消息以身份头开始，原样包含该席完整 review brief 和只读评审指令。以任务书的 input_refs、must_check、permissions 和当前 gate 为证据与权限边界，角色卡的质量标准和案例用于判断方法。其他席任务、peer 结果和主线程预设结论不进入首轮消息；同席多个逻辑角色共享同一 Agent，逐角色返回结果。
3. 派发前展示“席位名称 → 各专家名称/role_id → 可读 Agent 名称 → 语义 task_name → 使命 → 必查项 → 待派发”；宿主返回真实 Agent ID 后，将该 ID 与席位、角色和“已派发”状态一起展示。技术 task_name 不能代替专家职责。显示已派发必须有实际宿主返回，显式 role_simulation 则显示模拟身份与弱证据。
4. 收齐同轮结果后，按角色展示真实 Agent ID 或模拟身份、独立立场、逐项检查、证据引用、发现、阻断项和未解决问题；再汇总处理结论。无发现仍返回完整 check_records/completion_evidence。准备、派发、完成检查和通过门禁是不同状态，只有 canonical validator 接纳后才显示评审通过。
5. 提交原始 `role_context/review_seats/role_tasks/role_results`、`review_briefs` 和 `dispatch_briefs` 给现有 `record_multi_agent_review`，填写真实 `reviewer_agent_ids/reviewer_spawn_source`，不要重写角色卡、输入或哈希。结果继续遵循每张任务书原有 output_schema；无需新增声称“人设已生效”的字段。runtime 校验身份和内容绑定，实际提示投递及独立性由宿主执行，不以 JSON 证明模型内部行为。

历史评审可以没有 review_briefs，原任务、席位哈希与既有角色目录版本保持不变。旧 active delivery 使用启动时的原缓存 runtime；1.2.1 不能热替换其 runtime receipt。team 模式还遵守下述评审批次屏障和生产者不能评审自己的规则。

生产派发名包含 run/工作包/attempt 的稳定后缀；新 attempt 重新读取行中的名字和消息，禁止沿用旧 staging_root 或旧真实 ID。评审派发名包含 gate/快照绑定的席位哈希后缀，避免不同 gate 或新输入快照覆盖旧子 Agent；同一快照的挑战/修订阶段复用该席真实 Agent。展示名保持“角色｜职责｜业务版本”，不把后缀当作专家职责。

## V1.2 Team Production

只有当前 delivery 的 `production_policy.mode=team` 才允许派发生产专家；`multi-agent` 本身只授权评审。新 start 可设 `production_mode_if_created=team`，默认 coordinator。恢复始终沿用原策略。显式切换使用严格 JSON `{"schema_version":"v1","action":"set_production_mode","delivery_id":"<current>","mode":"team"}`，仅同版安全阶段边界可用；旧 active delivery 不迁移。

使用当前插件 runtime 的 ProductDeliveryWorkflow；主线程独占全部下述 API 和 Host Goal。成员不得调用这些 API。复用既有 input enrichment、product_baseline、test_coverage_plan 确认，不新增团队审批。

### 生产步骤

1. 从 `production_profiles.get_stage_profile(stage, project_type)` 和 `get_production_role_card(role_id)` 获取角色方法；完整目录在 `templates/production-role-catalog.json`。六阶段依次为 product_definition、architecture_version_planning、open_spec_product_surface、test_design、implementation_execution、delivery_preparation。产品基线确认在产品表面 scenario review 后；详细测试设计在该确认后。实现期只能绑定当前权威 TASK。
2. 主线程准备输入引用 `{logical_input:{ref,sha256}}` 和工作包 `{work_package_id,role_ids,depends_on,allowed_write_paths}`。路径必须逐文件明确；需要的新文件也必须列出。调用 `prepare_team_run(stage, work_packages, input_refs=..., task_id=..., condition_flags=...)`，返回行中的 `agent_display_name/agent_spawn_name/dispatch_message` 是唯一命名来源；创建子 Agent 时使用 `agent_spawn_name`，并把完整 `dispatch_message` 作为首条消息（先等待 coordinator 提供真实 `staging_root`）。可用 implementation_roles 裁剪 frontend/backend/test_automation；integration 仍必需。条件角色不能突破当前阶段权限。
3. 读取 run.work_packages 内任务，只把该任务、角色方法、输入及分配目录交给真实子 Agent。使用 `task_name=row.agent_spawn_name`、`message=row.dispatch_message` 和 `fork_turns=none`。宿主创建 Agent 后，用实际返回身份记录 `dispatched` 事件：event_id/type/work_package_id/agent_id/spawn_source/attempt；新命名工作包必须同时提交行内 agent_display_name/agent_spawn_name 以校验，历史无命名行保持旧事件兼容。事件返回后发送该行重新生成的完整 dispatch_message，其中真实 staging_root 是唯一工作目录，成员此时才允许写入。不得注入评审预设结论。一次至多两个 running 成员，依赖必须已整合，同文件任务串行。
4. 成员编辑任务副本并返回 ProductionResult：task_hash/input_snapshot_hash/role_ids/status/artifacts/changes/check_records/completion_evidence/risks/blockers/unresolved_questions/handoff。artifacts 的 path 相对 staging_root；changes 包含 path、operation、base_sha256、result_sha256、staged_path。不得编造哈希，读取真实字节计算。结果为 ready_for_integration、needs_input、needs_rework 或 failed，绝不能把提交称作评审通过。
5. 主线程使用 `record_team_events(run_id, events, expected_revision=...)` 登记 result，事件带真实 agent_id 和 attempt。调用 `integrate_team_run(run_id, expected_revision=...)` 合并已接受结果。下游 dispatch 绑定已整合的依赖字节及新 task_hash。结果工件被保存到 owner 管理的 accepted 目录，验证实际文件与当前版本。
6. 主线程通过既有 API 登记场景、原型、测试计划、TASK 执行证据等；运行真实集成验证。`finalize_team_run` 只检查阶段出口，不替代产品确认、TASK completion、Host Goal 或 closure。

non-UI 交付完成真实 CLI/API/service 旅程后，必须调用 `ProductDeliveryWorkflow.record_executed_behavior_evidence(records)` 写入 `executed_behavior_evidence`；该入口绑定 planned obligations、命令退出码、`evidence_path` 与 `trace_path` 的真实文件 hash，以及后续 `test_implementation` review。行为证据不得使用 browser-only 的 screenshot、acceptance_url、browser evidence_strength、network probe、mocked_routes 或 probe_artifact_path 字段。只写 TASK slice evidence 不能解除 non-UI closure blocker。

### 独立评审步骤

团队在既有五类 gate 使用 V1.1 评审契约和上述完整 review_briefs 派发规则。生产者和主线程不能担任独立 reviewer。材料整合及确定性检查完成后，只读准备 brief 并创建两个真实 reviewer；登记 `review_started`（review_type、两个实际 reviewer_agent_ids）后再开始输入读取。冻结期间禁止整合生产补丁或重写 canonical 生产工件。

每位 reviewer 每阶段返回后，登记 `review_member`：review_type、agent_id、phase（independent/challenge/revision）以及 artifact `{ref,sha256}`。同阶段全员返回后才能进入下一阶段。原始意见须保存为真实工件；不得用无证据的完成标记补屏障。

所有屏障完成后，将完整 V1.1 structured review 交给 `record_multi_agent_review`，通过后解除该 gate 的锁。需要修复时，用 `review_rejected` 记录 reason 和 work_package_ids，等待所有评审批次结清后再派发修复。修复使用新 attempt，新的输入或范围变化走既有变更流程。产品范围、测试义务及确定性门禁不能被多数意见豁免。

### 失败与恢复

每工作包默认1800秒。failed/timeout 必须有原因，timeout 由实际 deadline 判定；retry 最多一次，revise 最多一次；暂停后旧 attempt 结果拒绝。新输入需要重建快照，不能扩大当前任务权限。取消 run 前必须先由宿主停止成员并通过 failed 事件收束运行身份。不得无限重开相同失败输入。

status/inspect 查看进度；inspect_team_run 为只读。合并回执丢失时使用原 run_id/revision 重试，不能手改 state、删除 intent 或还原整份状态。未完成 merge intent 必须先恢复，不能通过取消、暂停或换模式丢弃。外部修改造成冲突时保留现有字节并报告。暂停时宿主需终止或中断实际成员；runtime 使旧结果失效，但不声称可以瞬时终止宿主进程。

角色与目录限制是契约及接纳检查，保护等级为 shared_fs，不是 OS 沙箱。用量由宿主实际提供；未提供时为 unavailable。新生产模式不改变既有模型选择、不复活已退役的模型编排接口，不宣称完整 PanelRun 已实现。

## V1.2 可开关的产品交付地图

地图默认关闭，适用 team/coordinator 和 UI/non-UI。地图只生成静态 HTML，使用用户已有 HTTP 服务；禁止为地图启动 HTTP 服务、端口或后台进程。

以下简写交给 `scripts/waygate-map.py --project-root <repo>`（不是 lifecycle control JSON）：

| 简写 | 脚本参数与行为 |
| --- | --- |
| `map` | 无子命令；显示状态，开启时重新生成 HTML。 |
| `map on` / `map off` | 先只读 inspect 获取当前 delivery ID，再传 `on/off --delivery-id <id>`；竞态切换必须拒绝，不能猜测新 ID。 |
| `map default on` / `map default off` | `default on/off`；只影响以后创建的交付，当前交付保持原值。 |
| `map export` | `export`；开启时生成独立离线快照，关闭时提示先开启。 |

开关存储独立于 canonical state。恢复沿用该交付选择，不能重新应用项目默认值；旧 delivery 无配置保持关闭。开启不改变 Goal、TASK、评审或确认。关闭冻结已有页面并停止刷新，历史快照保留。

实时入口 `.product-delivery/maps/index.html` 每 1 分钟刷新，保留选择、筛选、滚动位置。`status/inspect` 的 `progress_map` 显示有效值、来源、生成时间、新鲜度和错误。只提供路径或用户配置的静态服务 URL，不编造服务地址。HTML 不依赖 CDN。快照断网可展开节点和查看变化，外部日志/trace 不会自动嵌入。

### 地图开启时的角色交接

主线程检查 `progress_map.enabled`。产品专家补充目标、成功标准、能力和版本边界；架构专家补充组件、接口与依赖；测试设计专家把已有 scenario/obligation 与 runtime TASK 关联；生产专家解释实现细化；评审问题和已批准变更必须引用真实依据。专家只交付关联建议，主线程通过 `record_progress_map_plan(plan, expected_revision=...)` 登记，不能由成员改写地图开关或权威进度。

完整 v1 计划字段：`schema_version/delivery_id/title/objective/success_criteria/current_version/versions/goals/components/capabilities/edges/task_bindings/changes/sources`。节点有稳定 id/title；组件有 goal_ids；能力有 goal_ids/component_ids/version_ids，可绑定 scenario_ids/obligation_ids；接口有 from/to/kind(dependency|interface)/label。来源必须为 `{path,sha256}`，从真实字节计算。TASK 关联为 `{delivery_id,task_id,planned_task_hash,capability_ids}`，只接受当前交付和现有任务哈希。不得按文件名或关键词推断目标已实现。

变更 kind 为 planned/implementation_detail/review_gap/approved_change/unexplained，包含 id/title/reason/impact/owner/next_action/sources，可用 affected_ids 精确关联差异。批准引用 `approval={target,artifact_hash}` 必须匹配现有当前确认，不能将成员自报 approved 当作批准。记录计划修订可使用 Python facade 或 `record - --expected-revision N` 从 stdin 读取 JSON。

地图是解释层，不是审批入口。不关联或不确定时显示未知，不新增硬门禁；范围或测试覆盖语义变化沿用既有确认规则。展示生产完成、整合、验证、评审、交付分别来自各自的 canonical 证据。中途补建无法还原原始历史时保留 history_incomplete，不得伪造初始计划。关闭时不要求任何额外地图产物。
