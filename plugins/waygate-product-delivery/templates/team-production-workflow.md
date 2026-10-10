## V1.2 Team Production

只有当前 delivery 的 `production_policy.mode=team` 才允许派发生产专家；`multi-agent` 本身只授权评审。新 start 可设 `production_mode_if_created=team`，默认 coordinator。恢复始终沿用原策略。显式切换使用严格 JSON `{"schema_version":"v1","action":"set_production_mode","delivery_id":"<current>","mode":"team"}`，仅同版安全阶段边界可用；旧 active delivery 不迁移。

使用当前插件 runtime 的 ProductDeliveryWorkflow；主线程独占全部下述 API 和 Host Goal。成员不得调用这些 API。复用既有 input enrichment、product_baseline、test_coverage_plan 确认，不新增团队审批。

### 生产步骤

1. 从 `production_profiles.get_stage_profile(stage, project_type)` 和 `get_production_role_card(role_id)` 获取角色方法；完整目录在 `templates/production-role-catalog.json`。六阶段依次为 product_definition、architecture_version_planning、open_spec_product_surface、test_design、implementation_execution、delivery_preparation。产品基线确认在产品表面 scenario review 后；详细测试设计在该确认后。实现期只能绑定当前权威 TASK。
2. 主线程准备输入引用 `{logical_input:{ref,sha256}}` 和工作包 `{work_package_id,role_ids,depends_on,allowed_write_paths}`。路径必须逐文件明确；需要的新文件也必须列出。调用 `prepare_team_run(stage, work_packages, input_refs=..., task_id=..., condition_flags=...)`，可用 implementation_roles 裁剪 frontend/backend/test_automation；integration 仍必需。条件角色不能突破当前阶段权限。
3. 读取 run.work_packages 内任务，只把该任务、角色方法、输入及分配目录交给真实子 Agent。不得 fork 完整历史或注入评审预设结论。宿主创建 Agent 后，用实际返回身份记录 `dispatched` 事件：event_id/type/work_package_id/agent_id/spawn_source/attempt。以 API 返回的 staging_root 为唯一工作目录。一次至多两个 running 成员，依赖必须已整合，同文件任务串行。
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
