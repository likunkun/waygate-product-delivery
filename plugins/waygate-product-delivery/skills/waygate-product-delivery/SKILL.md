---
name: waygate-product-delivery
description: Codex-native product delivery workflow.
---

# Product Delivery Agent

默认休眠。说 `启动交付` 激活当前项目的产品交付模式，并立即进入 `multi_agent_mode_selection` 等待评审模式选择；说 `启动交付，多 Agent 模式` 显式授权当前 delivery 在结构化 review gate 自动启动 2–3 个独立 subagents；只有在真实 subagents 不可用时，才使用 `启动交付，允许降级评审` 显式允许 role_simulation 弱证据；说 `停止交付` 或使用 `stop` 退出干预。底层命令仍保留 `start` / `stop`。

## Active Mode Hard Rules

启动后必须创建或恢复 `.product-delivery/state.json`，并把它作为当前项目的权威状态。聊天总结、旧版本文档和 `progress.md` 都不能替代 gate evidence。

每次新交付必须生成独立 `delivery_id`，并将 `multi_agent_policy` 同时绑定当前 `delivery_id` 与 `feature_slug`。收到启动请求时，先调用只读 `inspect_startup_request(feature_slug=...)`；已关闭旧 feature 启动新 feature 时必须归档旧 state、创建新 delivery 并重新选择评审模式，未终态的其他 feature 不得被静默覆盖。

模型选择完全由用户和 Codex 宿主管理。Product Delivery 不选择、不记录、不验证、也不声称当前线程或 subagent 使用了任何特定模型。

恢复 v1.0.19–v1.0.21 的 active state 时，如果存在旧 `execution_model_policy`，必须调用公共 `retire_model_execution_policy()` 归档旧 policy、清理模型 blocker 并保留当前 delivery、feature、原型、review 和确认；不得重新 start 当前 delivery，也不得手改 state。旧模型 API 只保留一版明确退役错误。

active mode 下必须先使用这些 baseline skills：`superpowers:using-superpowers`、`planning-with-files`、`waygate-product-delivery`。`planning-with-files` 必须执行 session catchup，并读取或创建 `task_plan.md`、`findings.md`、`progress.md`。

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

handoff 后必须按顺序执行：先调用 `prepare_host_goal_activation()`，再调用宿主 `get_goal`；确认不存在 Goal 后才调用 `create_goal`；创建后再次调用 `get_goal`。每次结果都必须通过 `record_host_goal_observation(checkpoint_id, observation)` 落盘。其他未完成 Goal、objective 不匹配、checkpoint 重放、stale observation 或 Goal 工具不可用都必须 fail closed。Goal 工具不可用时记录 unavailable observation 并阻塞，不能声称自动续跑已经生效。

每个 post-handoff turn 开始，以及 TASK/stage、review、closure、final、stop 和 Goal 状态更新前，调用 `prepare_host_goal_reconciliation(operation, target_gate, host_turn_id=...)`，再使用 `get_goal` 或该 checkpoint 指定的 `update_goal`，最后调用 `record_host_goal_observation()`。同一 stage 内低层文件写入不需要重复查询，但任何 canonical gate 写入都必须消费一条新鲜、目标 gate 匹配的一次性 observation。

`wait_for_user` 必须生成并复用稳定 `decision_id`、prompt hash 和 blocker fingerprint；同一问题只展示一次，自动 Goal turn 不得重复提问，也不得修改产品、测试、证据或 closure。用户回复必须匹配当前 `decision_id`，并通过 `user_resume` 再次观察 Host Goal active 后才能继续。只有三个不同 `host_turn_id` 连续观察到相同 blocker，才允许调用 `update_goal(status=blocked)`。

canonical closure 通过前禁止 `update_goal(status=complete)`；closure 后先 `pre_complete` 对账，再调用 `update_goal(status=complete)`，最后用 `get_goal` 验证 complete，之后才允许正式 final。Goal 曾经 active 后若 missing 或提前 complete，禁止静默创建 replacement，必须调用 `authorize_host_goal_reactivation()` 取得新的用户授权。`停止交付` 需要 `stop_delivery` 对账，停止后 binding 标记为 `stopped_by_user`，不得自动恢复。

V1.0.25 起，Goal 尚未 ever active 且 activation checkpoint 因后续合法 transition 过期时，必须调用 `recover_stale_host_goal_checkpoint(checkpoint_id)`。runtime 会验证 delivery、feature、authorization、generation、nonce、objective 和 journal hash chain，归档旧 checkpoint，追加 `host_goal_checkpoint_superseded` transition，并以相同 binding identity 重新签发 `inspect_before_activation` checkpoint。不得手改 state、重新 start delivery 或重放旧 checkpoint。

V1.0.26 起，每个 delivery 在启动时把宿主 `CODEX_THREAD_ID` 冻结为 `host_goal_owner` 的 coordinator thread。Host Goal activation、observation、reconciliation、post-handoff canonical write 和 completion 必须同时匹配当前 `CODEX_THREAD_ID`、owner thread、binding owner 和宿主 Goal 的 `threadId`；缺失或不匹配全部 fail closed。spawned review subagent 只能产出结构化评审，不得激活、恢复、接管或完成 Host Goal。

v1.0.25 及更早的非终态 state 缺少 owner metadata 时迁移为 `legacy_unverified`，不得从旧 binding 推断 coordinator。必须在没有 active/blocked Goal 的新用户可见顶层线程中使用固定授权语 `恢复交付主线程，接管当前 Host Goal`，依次调用 `prepare_host_goal_owner_claim()`、宿主 `get_goal`、`record_host_goal_owner_claim_observation()`。只有 `get_goal` 返回 missing 或 complete 才允许 transfer；旧 binding 和未消费 checkpoint 完整归档为 `orphaned_unreachable`，journal 追加 `host_goal_owner_transferred`，然后使用新 generation、nonce 和精确 objective 重新执行 `get_goal -> create_goal -> get_goal`。active/blocked foreign Goal 禁止覆盖。owner-claim checkpoint 若因合法 transition 过期，必须调用 `recover_stale_host_goal_owner_claim(checkpoint_id)` 归档旧 claim、追加 `host_goal_owner_claim_superseded` 并签发新 claim；不得手删 `pending_claim`。

active Waygate delivery 只能使用当前安装的 `waygate-product-delivery` runtime。禁止调用旧 `product-delivery-agent@1.0.8` runtime 写入同一 delivery；旧 runtime 产生的历史 evidence 可以保留，但后续 canonical transition 必须由当前 Waygate runtime 完成。

V1.0.27 起，`start()` 必须写入当前 Waygate 的 `runtime_provenance`（插件名、版本和 runtime package hash）、非空 delivery ID、owner metadata，以及 hash-linked `delivery_activated` journal event。`status()` 只能将 active state 报告为 `verified_waygate`、`legacy_unverified` 或 `invalid_runtime`。缺少或不匹配 receipt、policy、owner 或 journal 的 active state 不得推进任何门禁。必须调用 `recover_legacy_active_delivery()` 归档原始 state 后创建新 delivery；不得手改 state，也不得复用旧 confirmation、review 或 implementation authorization。

V1.0.28 起，已确认 UI 的 `implementation_baseline` 是实现阶段的权威产品基线，不是重新设计提示。它必须只读绑定 prototype design bundle、prototype contract、产品 HTML、设计系统、纯净截图、surface/state/viewport、region、interaction 及其 hash。用户可见 TASK 必须声明 `ui_impact` 并通过 `prototype_bindings` 绑定当前任务涉及的精确原型切片；非 UI TASK 必须声明 `ui_impact=none` 及理由。handoff 和当前 TASK 提示只注入当前绑定切片，明确要求保持 route、区域层级、控件顺序、关键状态和交互结果一致；允许调整内部代码架构，禁止自行增删、移动、合并或重设计可见 UI。无法按原型实现时必须停止 TASK 并发起 CR，不得静默降级。

每个 UI TASK 完成前必须调用 `record_task_prototype_conformance()`，记录生产截图、semantic snapshot、结构与交互观察、geometry、computed-style fingerprint 和像素差异。route、region 存在性、父子层级、显示顺序、可访问角色/名称、必要控件及绑定 interaction 零容忍；关键区域像素差异默认不超过 2%，全页面不超过 5%，单像素阈值为 0.2；geometry 偏差默认不超过 4 CSS px 或 viewport 的 1%，取较大值。证据缺失是 `failed`，渲染环境不稳定是 `inconclusive`，两者都阻止 TASK 完成。检查失败必须修复生产实现，不得修改冻结原型、mask 或阈值。确需改变可见设计时必须走 CR 并重开产品基线。

产品域、视觉阈值、mask 或 TASK binding 变化必须让相关 TASK、conformance evidence 和实现授权 stale；仅 `review_annotation_set` 变化不影响 implementation baseline。新 UI delivery 强制执行上述规则；已确认 product baseline 的 active UI delivery 保持 grandfathered，除非原型被重开，重开后必须升级到 V1.0.28 门禁。最终 closure 仍需 full-stack Browser E2E、全量 production conformance 和独立 `ui_conformance` review。

不得使用 20 秒 watchdog、定时发送 `继续`、网络异常后盲目重试或把 hook 输出伪装成用户输入。插件 hook 只能读取状态并提供 guardrail；真正的跨 turn 续跑必须由 Codex Host Goal 调度。只有真实宿主 smoke 证明无需用户发送 `继续` 也会进入下一 turn，才可以宣称自动续跑。

## Goal-Driven Closure

pre-handoff 通过后必须创建 Product Delivery implementation delivery goal，目标覆盖完整 planned TASK queue、executed E2E evidence 和 formal closure。不要在 TASK 未完成时停止；每次准备停止或总结前必须检查 remaining TASK。如果还有 TASK 且没有用户确认、外部环境阻塞或连续失败阻塞，就继续执行下一 TASK。closure validator 未通过时不要 complete goal，closure 失败时 goal 保持 active，下一步必须修复 closure evidence。`progress.md` 和聊天总结不能替代 delivery goal status。

final summary、stop、goal complete 前必须运行 `validate-closure-artifact.py --project-root <repo> --closure-artifact <path>`。该脚本必须非 0 fail closed，并写入 `.product-delivery/artifacts/closure-validator-result.md`。V1.0.8 起，只有调用 installed packaged `product_delivery_agent.finalization` 并写入 `closure_validation.validator=product_delivery_agent.finalization`、`canonical_schema_version=v0.11`、`plugin_version=1.0.28`、`closure_artifact_sha256`、`transition_journal` closure event 的结果才是 Product Delivery closure truth。target-specific validator、repo-local `scripts/verify/validate-closure-artifact.py`、Open Spec closure claim、聊天总结和 `progress.md` 只能作为 supporting evidence，不能解除 closure blocker。任何 closure-like 状态，包括 `closed_local_product_delivery`、`blocking_gates.closure=true`、`implementation.current_task=COMPLETE` 或 `delivery_goal.status=complete`，都必须同时满足 `closure_validation.status=passed`、`feature_closure.status=passed`、`delivery_goal.status=complete`；UI 项目还必须满足 `executed_browser_evidence.status=passed`。missing goal 在 handoff 后、implementation 中或 closure-like 状态下必须阻塞。

V1.0.8 起，critical transitions 必须写入 hash-linked `transition_journal`。handoff、TASK completion、executed browser evidence、closure validation、goal complete 都必须来自 canonical runtime API；手写 `.product-delivery/state.json`、批量补 TASK JSON、旧 feature closure result 或 docs 领先状态必须 fail closed。

multi-agent review 必须记录 `review_mode`。`spawned_subagents` 是强证据；该模式还必须记录 2–3 个唯一的 `reviewer_agent_ids` 和真实 `reviewer_spawn_source`；模型名称不是 review evidence。它只在 `execution_authorization` 对 `authorization_scope=current_delivery` 有效时可接受。授权只覆盖 scenario、test、test_coverage、test_implementation、ui_conformance 结构化 review gate，不授权普通实现、文件读取或串行修复自动并行。`role_simulation` 是弱证据，只有使用 `启动交付，允许降级评审` 后才允许；`blocked_with_reason` 不能通过 handoff。

进入实现前必须记录 canonical `implementation_launch_authorization`，但它是 runtime 自动授权 artifact，不是用户确认 gate。授权必须绑定当前 `feature_slug`、review mode、prototype hash、planned E2E、TASK queue、required commands 和 nonce/hash。scope、TASK、review mode、prototype 或 planned E2E 改变后必须自动刷新授权并继续 handoff。

custom artifact 可以作为 supporting evidence，但不能授权实现。自定义 `*-pre-handoff-gate.json`、Open Spec 总结、task artifact、prototype screenshot 或磁盘 E2E JSON 都不能替代 canonical handoff、delivery goal、implementation launch authorization、executed browser evidence 或 closure validation。

V1.0.18 起，如果当前 authorized launch package 与旧 `delivery_goal` 的 `launch_package_hash` 不一致，必须调用 canonical `recover_stale_launch_package()`；runtime 会归档旧 implementation package、写入 `implementation_package_superseded` transition，并仅按完全一致的 `planned_task_hash` 复用 TASK completion。禁止手改 state 或只删除 stale blocker。

其他技能只能辅助，不能替代 Product Delivery 主流程。项目 `AGENTS.md`、Waygate/controller 规则仍要遵守，但不得绕过 Product Delivery 的 Open Spec、UI/非 UI gate、测试覆盖和 closure evidence。

## Current Feature Evidence

检查 Open Spec 或原型时必须按当前 feature slug 匹配。旧版本 `docs/open-spec/`、旧 prototype、聊天总结、`progress.md` 都不能替代当前 feature gate evidence。
