---
name: waygate-product-delivery
description: Codex-native product delivery workflow.
---

# Product Delivery Agent

默认休眠。说 `启动交付` 激活当前项目的产品交付模式，并立即进入 `startup_mode_selection`，一次选择模型执行模式和评审模式。`启动交付，自动模式，多 Agent 模式` 使用逐阶段模型配置并授权结构化 review gate；`启动交付，全速模式，多 Agent 模式` 要求主线程、阶段 Agent 和 review subagent 统一使用 full-speed profile；说 `启动交付，多 Agent 模式` 只授权评审维度，仍必须补选模型执行模式。只有在真实 subagents 不可用时，才使用 `启动交付，允许降级评审` 显式允许 role_simulation 弱证据；说 `停止交付` 或使用 `stop` 退出干预。底层命令仍保留 `start` / `stop`。

## Active Mode Hard Rules

启动后必须创建或恢复 `.product-delivery/state.json`，并把它作为当前项目的权威状态。聊天总结、旧版本文档和 `progress.md` 都不能替代 gate evidence。

V1.0.19 起，启动必须同时授权 `execution_model_policy` 和 `multi_agent_policy`。自动模式按 discovery、product_design、implementation、browser_evidence、review、closure 选择模型；连续两次失败、跨服务一致性、权限/迁移、review blocker 和 closure 必须升级到 escalation profile。全速模式默认使用 `gpt-5.6-sol/xhigh`，也可通过用户、项目或 delivery 配置覆盖，但覆盖后所有 Agent 仍必须统一使用该 profile。用户配置位于 `~/.codex/waygate-product-delivery/model-profiles.json`，项目配置位于 `.product-delivery/config/model-profiles.json`，优先级为 delivery > project > user > builtin。启动时必须将解析后的 profile 和 hash 冻结到 state；配置文件变化不得静默改变当前 delivery。普通阶段 Agent 必须 `fork_context=false`，只接收当前任务的必要 evidence packet，并且不得写 canonical state；canonical state 只由主协调线程写入。主线程在 spawn 前必须调用 `begin_execution_stage()` 取得 model、reasoning_effort 和 service_tier；spawn 返回后再次绑定 agent ID。自动模式普通阶段最多一个 worker，review gate 可按 `multi_agent_policy` 启动 2–3 个 reviewer。全速模式下每个 reviewer 必须使用同一个 full-speed assignment；自动模式的 Skeptic/final adjudicator 必须带 `skeptic_adjudication` risk flag 使用 escalation profile。全速模式下当前主线程模型无法由插件热切换，必须记录匹配的 main-thread observation；不匹配时等待用户切换或新开线程，禁止伪称全速模式已生效。

active mode 下必须先使用这些 baseline skills：`superpowers:using-superpowers`、`planning-with-files`、`waygate-product-delivery`。`planning-with-files` 必须执行 session catchup，并读取或创建 `task_plan.md`、`findings.md`、`progress.md`。

## Blocking Gates

禁止实现，直到以下门禁全部满足：

1. 当前 feature slug 已写入 `.product-delivery/state.json`。
2. 当前 feature 已使用 `open-spec` 生成 `docs/open-spec/<feature-slug>/`，包含 `00-change-request.md` 到 `08-stage-handoff.md`。
3. 项目类型已经确认。UI 项目必须进入本地 1:1 HTML 原型 gate；非 UI 项目必须进入 behavior contract gate。
4. UI 项目必须使用 `ui-ux-pro-max` 评审原型，并使用 `webapp-testing` 做浏览器验证；没有当前 feature 的 HTML 原型确认前禁止实现。
5. 测试覆盖审计必须使用 `test-strategy` 或 `testing-strategy`。
6. closure 必须使用 `open-spec-feature-closure` 和 `superpowers:verification-before-completion`。

禁止实现的条件：未完成 combined requirements freeze + planned E2E 确认、未确认 prototype、未冻结 planned E2E obligations、或 closure validator 未通过。实现前只能冻结 planned E2E，真实 browser evidence 必须在实现后落盘并校验。

V1.0.3 强制两道状态机出口：pre-handoff gate 和 pre-closure gate。pre-handoff 通过前禁止开始实现；pre-closure 和 closure validator 通过前禁止声明完成。

UI 项目未显式确认本地 1:1 HTML prototype 前禁止实现。截图、Playwright evidence、static review 只能作为辅助证据，不能替代用户确认；必须通过 `confirm_ui_prototype` 写入 `ui_prototype.confirmed_by_user=true` 和 user confirmation artifact。prototype 每次修订后都必须重新确认；用户反馈导致 prototype 文件、截图或 review evidence 变化时，旧 confirmation 自动失效。`confirm_ui_prototype` 只能确认当前 pending confirmation 的 artifact hash、prototype revision 和 nonce；裸 `继续` 不能替代当前版本确认。

V1.0.14 起，UI prototype review 必须声明 `ui_change_type`。默认增量 UI 是 `incremental_existing_surface`，必须记录上一版 feature、baseline surface paths、baseline user journey、continuity mapping 和 prototype delta summary。增量 UI 不得用独立工作台或平行新页面替代上一版真实主路径。`new_surface_in_existing_product` 和 `greenfield_ui` 只有在记录有意义的 `new_surface_justification` 且有显式用户确认时才允许作为例外。用户反馈或已有 prototype revision 后，旧 prototype confirmation、scenario/test review、planned E2E confirmation 和实现授权必须 stale；重新 review 前不得进入实现。

多 agent scenario/test review 必须落成结构化 artifact，包含 independent positions、cross challenges、revisions、final adjudication 和 blocking findings。session log、Open Spec 摘要、quick review 不能替代这些 artifact。

planned E2E、executed browser evidence、coverage audit 和 closure artifact 必须按 `scenario_id`、`obligation_id`、`test_id`、user story、journey 对账；UI planned E2E obligation 必须记录 `baseline_entry_path`，测试必须从上一版真实入口进入；supporting evidence 不能替代 UI journey browser E2E。V1.0.13 起，UI journey closure 只接受 `full_stack_browser_e2e`。`mocked_api_browser_e2e` 和 `static_or_prototype_browser_check` 只能作为 supporting evidence，除非有结构化豁免允许 closure。executed browser evidence 必须记录 acceptance URL、API health identity、network probe artifact、business API request summary 和 `mocked_routes`；未豁免 business API mock 必须阻塞 closure。

V1.0.15 起，UI journey closure 还必须是 role-accurate、ordinary-path、independently verifiable evidence。UI planned E2E obligation 必须记录 `required_actor_roles`、`path_kind`、`ordinary_entry_path` 和 `data_state_contract`。executed browser evidence 必须记录 `executed_actor_roles`、`primary_actor_role`、`actor_identity_evidence`、`ordinary_path_observed`、`execution_segment_id` 和 `test_title_or_step`。Teacher 主路径不能由 admin browser E2E 关闭；主路径、可见异常和权限拒绝必须有可定位、可失败的独立 execution segment。API/Go/Vitest 等 supporting evidence 可以证明后端行为，但不能替代 role-accurate Browser E2E。

V1.0.16 起，prototype confirmation 必须冻结 canonical `prototype_contract`、prototype HTML hash 和 prototype PNG screenshot set hash。实现与 full-stack Browser E2E 完成后，必须调用 `record_prototype_production_conformance`，为每个冻结 surface/state/viewport 记录 production PNG、controlled semantic snapshot、region/relationship/interaction observation 和 execution segment 绑定，并声明 production route/component provenance。`.txt`、HTML、JSON、伪 PNG、路径逃逸或被修改的证据必须 fail closed。formal closure 前还必须有独立 `ui_conformance` multi-agent review，完整覆盖所有冻结 region；`test_implementation` 不能替代它。closure schema `v0.11` 必须绑定 prototype、contract、production conformance 和 UI conformance review hashes。

用户面对的确认只保留两次：`ui_prototype` 原型确认，以及 combined requirements freeze + planned E2E coverage 确认。后者必须一次写入 `open_spec_freeze` 需求范围和 `planned_e2e_obligations` 测试用例覆盖情况两个 canonical state fact；legacy 单独记录 API 只用于兼容旧调用。`handoff`、coverage/review 接受、`implementation_launch_authorization`、closure 等都是内部 evidence/gate；满足条件后必须自动推进，不得要求额外用户确认。

V1.0.9 起，测试审查拆成两个不可互相替代的 gate。实现授权前必须通过 `multi_agent_test_coverage_review`，评审对象是测试用例覆盖范围，必须检查 `US/J/SC/AC/TASK/TC` 映射，并把集合型场景展开到 item-level coverage。例如二级工作台 tab、三级详情入口、人员维护、模板、Agent 规则、绑定、供应商、白名单、告警忽略等，必须看到每一项的 action assertion。实现和 E2E 运行后、formal closure 前必须通过 `multi_agent_test_implementation_review`，评审对象是真实测试代码、Playwright/browser 脚本、执行日志、截图和 trace。`marker exists`、函数名存在、静态说明面板、只点第一个按钮，都必须标记为 false-positive risk。如果发现 Playwright、MSW、service worker、fetch/XHR patch 或 fixture server mock 了当前 journey 依赖的 business API，却仍声称覆盖 UI journey，必须作为 blocking finding，并记录在 `business_api_mock_findings`。V1.0.15 起，`multi_agent_test_coverage_review` 必须记录 `role_journey_coverage`、`ordinary_path_coverage` 和 `scenario_granularity_findings`；`multi_agent_test_implementation_review` 必须记录 `actor_role_findings`、`evidence_distribution_findings`、`annotation_only_findings` 和 `ordinary_path_findings`。`reviewed_test_ids` 必须覆盖 planned test IDs，`verified_action_assertions` 必须覆盖每个 planned coverage item，不能只抽样代表项或只靠 annotation 关闭场景。如果发现 coverage gap，必须先补 RED test 让当前浅实现失败，再继续修 UI 或 E2E。

## Main Flow Continuation

active mode 下每次准备 final summary、普通 stop guard 或交付总结前，必须先运行 Product Delivery continuation guard，并以 `.product-delivery/state.json` 推导 `must_continue`、`wait_for_user`、`blocked`、`complete`。当结果是 `must_continue` 时，说明主流程已有 next gate 或 remaining TASK，如果没有 pending user confirmation、需求澄清、外部环境阻塞或连续失败阻塞，就必须继续推进下一 gate，不要用聊天总结结束当前交付主流程。

`wait_for_user` 只允许用于真实用户输入点：当前 prototype 确认、combined requirements freeze + planned E2E coverage 确认、必要需求澄清、startup execution/review mode 选择、full-speed 主线程模型确认、用户主动暂停或停止。`blocked` 必须说明 blocker；如果 blocker 是 `canonical_closure_plugin_version`，下一步是使用当前 installed packaged `product_delivery_agent.finalization` 重新生成 canonical closure，或在启动新 feature 前显式清理/迁移旧状态。`complete` 只有在 canonical closure、feature closure 和 delivery goal 都满足当前插件规则时才成立。

## Goal-Driven Closure

pre-handoff 通过后必须创建 Product Delivery implementation delivery goal，目标覆盖完整 planned TASK queue、executed E2E evidence 和 formal closure。不要在 TASK 未完成时停止；每次准备停止或总结前必须检查 remaining TASK。如果还有 TASK 且没有用户确认、外部环境阻塞或连续失败阻塞，就继续执行下一 TASK。closure validator 未通过时不要 complete goal，closure 失败时 goal 保持 active，下一步必须修复 closure evidence。`progress.md` 和聊天总结不能替代 delivery goal status。

final summary、stop、goal complete 前必须运行 `validate-closure-artifact.py --project-root <repo> --closure-artifact <path>`。该脚本必须非 0 fail closed，并写入 `.product-delivery/artifacts/closure-validator-result.md`。V1.0.8 起，只有调用 installed packaged `product_delivery_agent.finalization` 并写入 `closure_validation.validator=product_delivery_agent.finalization`、`canonical_schema_version=v0.11`、`plugin_version=1.0.19`、`closure_artifact_sha256`、`transition_journal` closure event 的结果才是 Product Delivery closure truth。target-specific validator、repo-local `scripts/verify/validate-closure-artifact.py`、Open Spec closure claim、聊天总结和 `progress.md` 只能作为 supporting evidence，不能解除 closure blocker。任何 closure-like 状态，包括 `closed_local_product_delivery`、`blocking_gates.closure=true`、`implementation.current_task=COMPLETE` 或 `delivery_goal.status=complete`，都必须同时满足 `closure_validation.status=passed`、`feature_closure.status=passed`、`delivery_goal.status=complete`；UI 项目还必须满足 `executed_browser_evidence.status=passed`。missing goal 在 handoff 后、implementation 中或 closure-like 状态下必须阻塞。

V1.0.8 起，critical transitions 必须写入 hash-linked `transition_journal`。handoff、TASK completion、executed browser evidence、closure validation、goal complete 都必须来自 canonical runtime API；手写 `.product-delivery/state.json`、批量补 TASK JSON、旧 feature closure result 或 docs 领先状态必须 fail closed。

multi-agent review 必须记录 `review_mode`。`spawned_subagents` 是强证据；它只在 `execution_authorization` 对 `authorization_scope=current_delivery` 有效时可接受。授权只覆盖 scenario、test、test_coverage、test_implementation、ui_conformance 结构化 review gate 的 2–3 Agent fan-out。普通实现、探索和证据采集如果使用阶段 Agent，必须由独立的 `execution_model_policy` 授权，且同一时刻最多一个、`fork_context=false`、不得写 canonical state；不能借模型模式扩大 multi-agent review 授权范围。`role_simulation` 是弱证据，只有使用 `启动交付，允许降级评审` 后才允许；`blocked_with_reason` 不能通过 handoff。

进入实现前必须记录 canonical `implementation_launch_authorization`，但它是 runtime 自动授权 artifact，不是用户确认 gate。授权必须绑定当前 `feature_slug`、review mode、prototype hash、planned E2E、TASK queue、required commands 和 nonce/hash。scope、TASK、review mode、prototype 或 planned E2E 改变后必须自动刷新授权并继续 handoff。

custom artifact 可以作为 supporting evidence，但不能授权实现。自定义 `*-pre-handoff-gate.json`、Open Spec 总结、task artifact、prototype screenshot 或磁盘 E2E JSON 都不能替代 canonical handoff、delivery goal、implementation launch authorization、executed browser evidence 或 closure validation。

V1.0.18 起，如果当前 authorized launch package 与旧 `delivery_goal` 的 `launch_package_hash` 不一致，必须调用 canonical `recover_stale_launch_package()`；runtime 会归档旧 implementation package、写入 `implementation_package_superseded` transition，并仅按完全一致的 `planned_task_hash` 复用 TASK completion。禁止手改 state 或只删除 stale blocker。

其他技能只能辅助，不能替代 Product Delivery 主流程。项目 `AGENTS.md`、Waygate/controller 规则仍要遵守，但不得绕过 Product Delivery 的 Open Spec、UI/非 UI gate、测试覆盖和 closure evidence。

## Current Feature Evidence

检查 Open Spec 或原型时必须按当前 feature slug 匹配。旧版本 `docs/open-spec/`、旧 prototype、聊天总结、`progress.md` 都不能替代当前 feature gate evidence。
