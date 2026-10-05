# V1.2.0 团队生产编排规范

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Specification |
| 日期 | 2026-09-29 |
| 状态 | 设计已对齐当前实现；自动化验证、真实宿主验收与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按角色目录、编排模块及 workflow 的真实契约修正；保留验证缺口。 | CR-005 |

## 事实来源与权威

接口与字段以 `src/product_delivery_agent/production_profiles.py`、`team_orchestration.py`、`workflow.py` 为事实来源。这里只规定生产编排；既有 startup input understanding、用户确认、review gate、HostGoalOwner、TASK 和正式 closure 保留其权威。`ready_for_integration` 是成员声明，`TeamRun.status=completed` 是生产轮次完成，两者均不代表正式闭环。

## 核心契约

### ProductionRoleCard

`get_production_role_card(role_id)` 返回独立副本并验证角色定义。字段为：`role_id`、`role_version`、`display_name`、`mission`、`when_to_invoke`、`scope`、`non_goals`、`required_inputs`、`optional_inputs`、`task_steps`、`must_check`、`must_not_do`、`required_capabilities`、`permissions`、`required_outputs`、`output_schema`、`evidence_requirements`、`completion_criteria`、`escalation_conditions`、`quality_rubric`、`examples`、`runtime_policy`、`provenance`、`definition_hash`、`template_hash`。十个核心职责与五个条件职责的完整方法见 09。

`permissions={read:[role_brief,input_snapshot_refs],write:[staging_artifacts,member_result_return],canonical_write:false}`。`runtime_policy={timeout_seconds:1800,max_recovery:1,max_revision_rounds:1,model_control:host_managed}`。definition hash 排除 `definition_hash/template_hash/provenance`；template hash 包含固定 task_format 和 instructions，instructions 另排除 `display_name`；均使用稳定 JSON 的 SHA-256。

### StageProfile 与 work package

`get_stage_profile(stage, project_type='non_ui')` 返回 `stage/profile_version/project_type/required_role_ids/conditional_roles/depends_on/role_dependencies/max_parallel`，其中 `max_parallel=2`。

`build_stage_tasks(stage, context, work_packages)` 返回 `{profile,tasks}`；工作包必须覆盖全部启用职责、具有唯一 `work_package_id` 和无环依赖。输入工作包字段为 `work_package_id`、非空 `role_ids`、`allowed_write_paths`，可附加 `depends_on`、`required_outputs`。同一包可合并多个职责；工作包总数不限制为两个，但同时 running 上限为两个。并行包写路径不能相交，依赖包须已 integrated 才能派发。

条件通过固定 `condition_flags` 启用，取值为 `domain_research/data_migration/security_engineering/performance_reliability/build_deployment`；具体阶段映射见 09。未知标志拒绝，已启用角色必须纳入工作包。不存在运行时角色注册、动态条件表达式或自动能力降级接口。

### ProductionTask

任务包含 `delivery_id/feature_slug/project_type/input_snapshot_hash/stage/profile_version/profile_hash/work_package_id/role_ids/role_cards/role_definition_hashes/task_template_hashes/must_check/required_outputs/required_inputs/input_refs/depends_on/allowed_write_paths/permissions/runtime_policy/output_schema/condition_flags/task_hash`。实施阶段另有当前 `task_id`，按调用可有 `implementation_roles`。没有独立 `canonical_task_version`、`precondition_hash` 或 task-level deadline 字段；执行 attempt 的 deadline 位于 run 中的 work package 记录。

`input_refs` 是逻辑输入名到 `{ref,sha256}` 的映射，调用时可带匹配 `project_type` 或 `shared` 的分支信息。每个任务只选择其角色 required inputs 和已提供的 optional inputs；缺 required input 拒绝。路径为精确规范化相对文件，禁止通配符、路径穿越和控制文件写入；实施前的写目标限定为文档/原型。前置阶段不依赖尚未建立的 canonical TASK。

### ProductionResult

必填字段为 `task_hash/input_snapshot_hash/role_ids/status/artifacts/changes/check_records/completion_evidence/risks/blockers/unresolved_questions/handoff`；可选身份字段为 `agent_id/spawn_source/identity_kind/simulated_identity`。不接受 schema 之外的字段。

| 结构 | 真实字段与约束 |
|---|---|
| status | `ready_for_integration / needs_input / needs_rework / failed` |
| artifacts[] | `{path,sha256,artifact_type}`，路径相对于该 attempt 的 staging workspace |
| changes[] | `{path,operation,base_sha256,result_sha256,staged_path}`；operation 为 add/modify/delete；path 必须是获准写目标 |
| check_records[] | `{check_id,outcome,reason,evidence_refs}`；outcome 为 satisfied/blocked/not_applicable |
| completion_evidence | 产物类型到非空证据引用列表的映射，引用对应类型的已声明产物 |

ready 结果必须覆盖全部 required_outputs 与 must_check、检查具有理由和绑定证据、无未决 blocker/question；可写包必须含 changes。未完成结果须解释 blocker/question。add 的 base 为 null，delete 的 result/staged_path 为 null；其余摘要为小写 SHA-256。结果必须匹配真实 task hash、snapshot hash 和 role_ids。profile 校验只验证结构；owner engine 另验证身份、真实文件字节、输入新鲜度和 staging 边界。真实运行拒绝 simulated 身份。

### TeamRun

初始字段为 `schema_version=team-run-v1/run_id/delivery_id/stage/project_type/task_id/profile/revision/status/input_refs/scope_hash/created_at/events/work_packages/protection_level/usage/merge_intent`。`protection_level=shared_fs`，初始 `usage={status:unavailable}`。

`events` 存 `event_id→payload hash`。`work_packages` 按包 id 索引，初始含 `task/baseline/attempt/status/recovery_count/revision_count/history/agent_id`，执行后附加 `spawn_source/started_at/deadline/staging_root/workspace_inputs/result/accepted_artifacts` 等证据。integration receipts 含 `source_revision/intent_path/intent_hash/outputs/integrated_at`。TeamRun 的 revision 和文件 hash 由 canonical state 引用，评审锁在 `team_review_locks` 中，不虚构 run-level `event_seq/review_freeze` 字段。

## 六阶段与既有确认顺序

| 顺序 / stage | 必需核心职责（均为 production.*） | 阶段出口及下一道既有门禁 |
|---|---|---|
| 1 product_definition | product_requirements | 产品蓝图、验收；进入架构规划，尚未要求 product baseline confirmed |
| 2 architecture_version_planning | architecture_contract | 架构契约、version_plan；进入产品面生产 |
| 3 open_spec_product_surface | scenario_interaction；UI 另有 ui_prototype | 整合后 scenario review，再由既有用户确认冻结产品基线 |
| 4 test_design | test_design | product baseline confirmed 后进入；整合后 test + test_coverage review，再确认 test_coverage_plan |
| 5 implementation_execution | 默认 backend、test_automation、integration；UI 默认增加 frontend | 已确认测试覆盖、canonical handoff 与实施授权；按当前 TASK 逐轮实施和证据校验 |
| 6 delivery_preparation | delivery_evidence | 全部实施 TASK 已完成；整合后 test_implementation review，UI 另有 ui_conformance review |

UI prototype 依赖 scenario_interaction；integration 依赖该阶段其他启用职责。实施 `implementation_roles` 可选择 frontend/backend 中至少一个及可选 test_automation，integration 始终保留；non_ui 不允许 frontend。test_automation 属于实施生产职责，不能提前把前置测试设计当代码实现。

新交付按上述次序；同版本安全边界开启 team 时 policy.entry_stage 由已有真实进度确定，不重跑已冻结阶段。已确认产品/覆盖不能直接返工，须走既有变更路径。完成 TeamRun 后仍由 owner 调用既有 TASK 推进、交付复验和正式 closure。

## Owner APIs

```python
prepare_team_run(stage, work_packages, *, input_refs,
                 task_id=None, condition_flags=None, implementation_roles=None)
inspect_team_run(run_id)
record_team_events(run_id, events, *, expected_revision)
integrate_team_run(run_id, *, expected_revision)
finalize_team_run(run_id, *, expected_revision)
inspect_production_mode_change(mode, *, delivery_id)
set_production_mode(mode, *, delivery_id)
```

前五个 API 返回当前 run dict。prepare 构建任务、验证阶段和输入；inspect 校验 state 引用的 run 文件 hash；record 接纳结构化事件；integrate 自动选择所有 ready 包并生成 receipt；finalize 检查已整合产物、阶段所需独立评审及实施证据后把 run 标为 completed。没有 requester、result_ids、expected_seq、runtime_version 参数或独立 Receipt 类型。

non-UI 的真实 CLI/API/service 行为通过 `ProductDeliveryWorkflow.record_executed_behavior_evidence(records)` 写入独立的 `executed_behavior_evidence` canonical state 和 `executed-behavior-evidence.md` artifact；UI 继续使用 `record_executed_browser_evidence(records)`。行为证据必须包含 `test_id`、`obligation_id`、`command`、`exit_code=0`、`semantic_assertions`、`evidence_path`、`trace_path`、`execution_segment_id`、`test_title_or_step`，并对真实 `evidence_path` 与 `trace_path` 文件落 hash；可选 `stdout_path`、`stderr_path`、`log_path` 也必须存在并落 hash。non-UI 不接受 browser-only 的 screenshot、acceptance_url、browser evidence_strength、network probe、mocked_routes 或 probe_artifact_path 作为契约字段。两类证据都绑定当前 planned obligations、输入/输出 hash 和 `test_implementation` review，不能直接写入 closure 或 TASK 完成状态。

startup 的 `production_mode_if_created` 默认 coordinator，仅新建交付时使用。team 授权记录在独立 `production_policy`，绑定 delivery/feature/owner 与 policy_hash；review authorization 不能替代它。set_production_mode 返回 canonical state，仅允许同一 V1.2 delivery 的安全边界：无未完成 run、无活动评审、当前 TASK 尚无开始或部分执行证据。旧 active delivery 不迁移、不回填 policy，也不能借此 API 跨版本切换。

## 事件、拒绝与恢复

| event.type | 关键输入与规则 |
|---|---|
| dispatched | event_id、work_package_id、attempt、真实 agent_id、spawn_source；建立最小 staging copy 和 1800 秒 deadline |
| result | 同一包/attempt/agent_id，加 result；迟到或身份不符拒绝 |
| failed / timeout | 同一包/attempt/agent_id，加 reason；timeout 必须已经超时 |
| retry / revise | work_package_id、reason；分别消耗 recovery_count / revision_count 的一次额度 |
| cancel | work_package_id、reason；成员必须停止，未完成 merge intent 须先恢复 |
| review_started | review_type、两个独立 reviewer_agent_ids；生产产物须已整合 |
| review_member | review_type、agent_id、phase、artifact={ref,sha256}；phase 为 independent→challenge→revision |
| review_rejected | review_type、reason、work_package_ids；三阶段 review barrier 完成后汇总批量修复 |

每个事件均有 event_id；同 id 同 payload 全批重放返回当前 run，不重复消费状态推进；不同 payload 或混合新旧事件拒绝。新事件使用 expected_revision CAS。needs_input 要求新输入快照，不能用 retry 偷换输入。超时和额度耗尽由 owner 记录原因并决定取消/交接，模块不自动无限恢复，也不把失败静默判通过。

真实拒绝是 `TeamError`、`ProductionProfileError` 及既有 workflow/HostGoal 异常与明确说明，例如 `event revision conflict`、`late result after deadline`、`target baseline conflict; external edits preserved`。这些不是稳定的数字或字符串错误码协议；拒绝不生成成功 revision，也不承诺自动追加 rejection event。

## 信息缺口与追溯

- Blocker：无。真实 UI/non-UI host exercise、对照报告与 canonical closure 演练已完成，证据见 `10-release-exercise-report.md`。
- Assumption：宿主负责实际 spawn、身份真实性、执行证据和必要文件权限隔离；shared_fs 只提供最小副本与结果校验。
- Nice-to-know：长期多样本质量、返工和成本分布仍需持续观测；本次用量记录为 unavailable。

FR-001..020、NFR-001..010、AC-001..008 → TASK-001..018 → TC-001..024；运行、存储和验收边界分别见 03、04、06–08。
