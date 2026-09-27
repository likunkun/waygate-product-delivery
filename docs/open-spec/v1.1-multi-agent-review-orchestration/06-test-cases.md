# V1.1 Multi-Agent Review Orchestration - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | 1.1.0（CR-004 复合席位增量；完整 panel 仍为目标架构） |
| Author | Codex / Open Spec QA |
| Date | 2026-09-26 |
| Status | CR-003 定向 QA PASS；未发布；历史 CR-001 用例仍 Not Run |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | Initial testing-stage test case design. Implementation has not started. | CR-001 |
| REV-20260702-01 | 2026-07-02 | Codex | Added per-TC trace/evidence matrix and aligned non-UI planned evidence layers before test coverage re-review. | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex | 保留测试用例历史正文，标记待按 CR-002 同步 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex / Open Spec QA | 新增角色契约 FR/TASK/TC 矩阵、41 项运行验证、已修复缺陷和未执行边界；保留 CR-001 历史正文。 | CR-003 |
| REV-20260926-03 | 2026-09-26 | Codex / Open Spec Implementation | 复合席位、席位身份、兼容和测试交接。 | CR-004 |

## 当前状态与续接边界（CR-003 / REV-20260926-02）

本轮仅验收已授权的八张角色卡、最小任务输入、结果契约以及 opt-in review 投影。依据 [02 规范 AC-ROLE-001～006](02-specification.md)、[03 实施路线](03-technical-solution.md)、[05 TASK-ROLE-101～106](05-development-plan.md) 和 [09 角色任务书](09-role-cards.md) 建立新测试矩阵，历史 `TASK-001～007` / `TC-001～026` 不被复用为本轮完成证据。

**QA PASS（CR-004 当前增量）**：2026-09-26 03:21（Asia/Shanghai），QA Agent 独立执行角色单元与 workflow 集成测试，共 **55 targeted tests，0 failures，exit 0**。测试数据是临时目录中的受控文件和结构化结果 fixture，模拟宿主身份仅用于验证契约；不构成现场真实 reviewer 已执行的证据。

完整 PanelRun、四 API（prepare/inspect/events/finalize）、阶段屏障、自动派发/恢复、receipt 和 canonical snapshot 提交仍为 CR-002 目标架构；本轮不验证或宣称已完成。角色契约按输入 opt-in；从未启用角色契约的旧 review 保持兼容，已接纳角色契约的 gate 不可降级回 legacy payload。本轮未运行真实 review 现场或上线；QA后追加 [四案例历史摘录对照](evaluation/README.md)，两组判断相同，没有证明质量提高。

## CR-004 测试策略与数据（继承 CR-003 角色契约测试）

- **unit**：直接调用 catalog/task/result 函数，遍历八角色、五 profile、适用 UI/non-UI 项目类型；断言结构、绑定和拒绝行为，不做提示词或文档全文匹配。
- **runtime integration**：在 `TemporaryDirectory` 激活 delivery，创建带当前 SHA-256 的实际输入文件，经过公开 prepare/record API、canonical artifact、load_state 和 gatekeeper；验证 owner、审计投影、真实字节漂移及兼容。
- **document review**：检查 09 的每角色五类例子有具体对象、证据、检查和结果，业界来源仅作设计借鉴；catalog 结构检查验证 22 必需字段及 completion/escalation/peer 类型分离。
- **恢复原则**：拒绝非法任务/结果后不登记 passed；必需材料漂移时显示 stale，修复材料后须重新准备与评审。无关输入变化、无关角色变更及 closed 历史不误失效。

执行入口：

```sh
PYTHONPATH=src python -m unittest tests.test_review_profiles tests.test_review_role_contract_integration -v
```

下表 `U` 指 `tests/test_review_profiles.py`，`I` 指 `tests/test_review_role_contract_integration.py`。每条 TC 聚焦一个核心断言；测试方法中的子场景覆盖对应边界。文件路径均相对仓库根目录。

## CR-003 FR → TASK → TC 矩阵

| TC | FR / AC / TASK | 层级 | 前置与步骤 | 期望结果 / 恢复 | 可执行或审阅证据 |
| --- | --- | --- | --- | --- | --- |
| TC-RC-001 | FR-018、FR-020 / AC-ROLE-001 / TASK-ROLE-101～102 | unit + document | 读取八卡；逐卡检查 22 字段、方法及五类例子；核对 09 的对象/证据/检查/结果。 | 8 卡、40 例完整，完成标准、升级条件、peer 契约类型分离。 | U:`test_every_role_can_return_evidenced_no_findings`；本轮 catalog 结构检查；09 八角色表人工审阅。 |
| TC-RC-002 | FR-018～019 / AC-ROLE-001 / TASK-ROLE-102 | unit | 删除 task_steps/must_check/must_not_do/completion_criteria/output_schema 后构建任务。 | 缺必需字段时抛 `RoleProfileError`，不派发任务；补全卡后重建。 | U:`test_card_missing_mandatory_method_cannot_be_dispatched`。 |
| TC-RC-003 | FR-018～019、FR-021 / AC-ROLE-001 / TASK-ROLE-102 | unit | 将卡改为不支持版本并重算定义/模板 hash。 | 仍拒派，重算 hash 不能使错误版本有效。 | U:`test_unsupported_role_version_is_rejected_before_dispatch`。 |
| TC-RC-004 | FR-019 / AC-ROLE-001 / TASK-ROLE-103～104 | unit | 遍历五固定组合；构造缺失、重复或错 gate 角色集合。 | 只接受对应完整 profile，未知/重复/缺席被拒绝。 | U:`test_fixed_profiles_cannot_pass_missing_duplicate_or_wrong_seats`、`test_wrong_gate_and_unknown_role_cannot_be_dispatched`。 |
| TC-RC-005 | FR-019～020 / AC-ROLE-002 / TASK-ROLE-103 | unit | 遍历 UI/non-UI；删必需输入；向 non-UI 提交 UI 引用；实现评审缺源码/执行证据。 | 适用组合可构建；ui_conformance 限 UI，缺/错来源拒派。 | U:`test_all_profiles_support_ui_and_applicable_non_ui_branches`、`test_missing_input_wrong_branch_or_implementation_source_blocks_dispatch`。 |
| TC-RC-006 | FR-020、FR-022 / AC-ROLE-003 / TASK-ROLE-103 | unit | 在输入加入 unrelated、coordinator_conclusion、peer_results 后构建任务。 | task 仅包含角色允许输入和方法，无预设答案或其他席位结论。 | U:`test_task_filters_unrelated_inputs_and_coordinator_or_peer_conclusions`。 |
| TC-RC-007 | FR-020～022 / AC-ROLE-002 / TASK-ROLE-103～104 | unit + integration | 修改 delivery、feature、project_type、snapshot、文件 digest 或任务步骤；尝试复用旧结果或重算被改任务 hash。 | 旧/串任务不能通过，当前任务绑定变化可检测。 | U:`test_task_hash_binds_input_content_delivery_and_instructions`、`test_missing_bound_task_or_rehashed_modified_instructions_cannot_validate`；I:`test_records_reject_old_snapshot_delivery_or_project_branch`、`test_task_tampering_is_rejected_even_with_original_task_hash`。 |
| TC-RC-008 | FR-020 / AC-ROLE-004 / TASK-ROLE-104 | unit | 各角色返回无发现结果，再分别移除必查、逐项记录、总证据或完成标准证据。 | 完整无发现允许通过；空/缺失逐项证据不能以总声明代替。 | U:`test_each_role_insufficient_evidence_cannot_pass`、`test_every_role_can_return_evidenced_no_findings`。 |
| TC-RC-009 | FR-020～022 / AC-ROLE-004 / TASK-ROLE-104 | unit | 将证据替为未绑定路径/伪 URI/空值；再使用任务内具体章节 anchor。 | 未绑定或无效证据拒绝；合法文件上的具体锚点可引用。 | U:`test_unknown_evidence_or_unstructured_finding_is_rejected`、`test_result_rejects_forged_evidence_and_conflicting_completion_claims`、`test_bound_evidence_allows_specific_anchors`。 |
| TC-RC-010 | FR-020、FR-022 / AC-ROLE-005 / TASK-ROLE-104 | unit + integration | passed 带未解 blocker、悬空 blocker、失败 check 或 findings 中的 open question。 | 不得登记 passed；需回报 blocked/needs_remediation 或修复并复验。 | U:`test_each_role_blocking_findings_cannot_be_hidden_in_passed_result`、`test_open_unresolved_question_cannot_be_hidden_inside_findings`；I:`test_failed_role_cannot_be_hidden_by_passed_projection`。 |
| TC-RC-011 | FR-020 / AC-ROLE-005 / TASK-ROLE-104 | unit | 把误报候选标 rejected 并提供当前证据与理由；随后删拒绝理由。 | 有证据/理由的拒绝可记录；无理由不能消除 finding。 | U:`test_each_role_false_positive_requires_evidence_and_reason_to_reject`。 |
| TC-RC-012 | FR-020～022 / AC-ROLE-002 / TASK-ROLE-104～105 | unit + integration | 伪造 agent、coordinator、重复身份、模拟/真实混写或空真实身份字段。 | 身份须与 review 模式和 reviewer 集合一致，不能冒充 coordinator 或宿主 spawn。 | U:`test_simulation_cannot_claim_spawn_and_requires_explicit_identity`；I:`test_agent_identity_must_match_declared_reviewers_and_mode`、`test_simulation_cannot_claim_spawned_reviewer_metadata`。 |
| TC-RC-013 | FR-022 / AC-ROLE-005 / TASK-ROLE-104 | unit | 八角色分别返回 change_scope/edit_TASK/write_code/edit_tests/update_Goal/close_delivery 写意图。 | 任一非空 write_intents 都拒绝接纳。 | U:`test_each_role_scope_task_code_test_goal_and_closure_writes_rejected`。 |
| TC-RC-014 | FR-021～022 / AC-ROLE-006 / TASK-ROLE-105 | integration | 当前 owner 准备任务；再切换非 owner；分别使用错 hash、绝对路径、父目录或逃逸 symlink。 | 合法准备只读；非 owner、非当前文件或越仓库路径拒绝。 | I:`test_preparation_is_read_only_and_bound_to_current_delivery`、`test_preparation_rejects_non_owner_even_before_host_goal`、`test_preparation_rejects_wrong_hash_and_path_escape`。 |
| TC-RC-015 | FR-021 / AC-ROLE-002 / TASK-ROLE-103、105 | integration | 准备后修改实际输入文件再 record；接纳后再修改输入文件/业务快照/所用角色定义。 | record 重新校验字节；load/gatekeeper 将已接纳但内容漂移的 review 标 stale。 | I:`test_record_rehashes_files_after_task_preparation`、`test_file_drift_invalidates_accepted_review_on_load_and_gatekeeping`、`test_business_snapshot_drift_invalidates_accepted_review`、`test_catalog_definition_change_invalidates_active_review`。 |
| TC-RC-016 | FR-021 / AC-ROLE-006 / TASK-ROLE-105 | integration | 接纳 scenario review 后修改未被任何任务选中的输入、UI 专属角色，或读取 closed 历史。 | 无关变更和 closed 历史不产生新的 stale。 | I:`test_unbound_input_does_not_invalidate_a_completed_review`、`test_unrelated_catalog_change_does_not_invalidate_review`、`test_closed_delivery_retains_historical_review_after_catalog_update`。 |
| TC-RC-017 | FR-019、FR-021～022 / AC-ROLE-006 / TASK-ROLE-105 | integration | 提交完整角色结果；删 context/tasks/results 或只去掉 role_contract_version。 | 完整契约先验后投影；Markdown 留全量审计，state 留摘要；部分字段不能绕过校验。 | I:`test_complete_role_results_are_validated_before_projection`、`test_role_contract_requires_tasks_context_and_complete_results`、`test_partial_role_payload_cannot_bypass_validation_by_removing_version`、`test_render_retains_full_role_contract_for_audit`。 |
| TC-RC-018 | FR-021～022 / AC-ROLE-006 / TASK-ROLE-105～106 | integration | 未启用角色契约时提交旧 review；已启用角色契约后再提交旧 passed payload。 | 前者保持兼容；后者拒绝降级，不能抹除已绑定证据。 | I:`test_legacy_review_without_role_contract_remains_compatible`、`test_bound_review_cannot_be_replaced_by_legacy_pass_dictionary`。 |

## 本轮执行与缺陷记录

执行人：`open-spec-role-qa` 临时 QA Agent；日期：2026-09-26；环境：当前工作树 Python `unittest`、`PYTHONPATH=src`。代码和测试由主线程修改，QA 只读运行；本 Agent 只编辑本文件。

| 批次 | 执行证据 | 结果 | 关联缺陷 |
| --- | --- | --- | --- |
| QA-RC-01 | 两个 discover 命令分别运行 U / I。 | U 18/18 PASS；I 20 中 3 FAIL。 | 缺陷 001～003 暴露后留在当前阶段修复。 |
| QA-RC-02 | 手工调用公开 validator/workflow：未解 question 放 findings、错版本重算 hash、模拟身份空字段、无关输入漂移。 | 复现 004～007；不是现场评审或质量收益测试。 | 004～007 已提交主线程修复。 |
| QA-RC-03 | `PYTHONPATH=src python -m unittest tests.test_review_profiles tests.test_review_role_contract_integration -v`；2026-09-26 03:21 +08:00。 | **41/41 PASS（20 unit + 21 integration）；0.429s，exit 0。** | 001～007 全部修复后独立复验；007 新增回归已在本批执行。 |
| QA-RC-04 | catalog 结构断言：八 role 均含正式 22 字段；每卡五类例子；completion/escalation 为 list，peer 为 dict。 | **PASS：8 卡 / 40 例条目。** | 结合 09 的具体例子人工审阅；不以字符串全文匹配证明行为质量。 |

| 缺陷 | 具体位置 / 原复现 | 修复与回归证据 | 当前状态 / 发布阻断 |
| --- | --- | --- | --- |
| DEF-RC-001 | `review_gates.validate_multi_agent_review` 只在 version 字段存在时校验；删除 version 并保留空结果可走旧分支。 | 任一角色标记触发校验；I:`test_partial_role_payload_cannot_bypass_validation_by_removing_version`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-002 | `workflow.record_multi_agent_review` 允许已绑定角色 review 被旧 passed 字典覆盖。 | 禁止 bound → legacy 降级；I:`test_bound_review_cannot_be_replaced_by_legacy_pass_dictionary`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-003 | canonical review artifact ref 缺 `.product-delivery/` 前缀，接纳后读取即 stale，使无关 catalog 测试误失败。 | 记录正确仓库相对 artifact 路径；I:`test_unrelated_catalog_change_does_not_invalidate_review`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-004 | `review_profiles.validate_role_result` 对 findings 中 open unresolved_question 未拒绝，顶层空问题数组可隐藏必查证据缺口。 | passed 拒绝未解决 question；U:`test_open_unresolved_question_cannot_be_hidden_inside_findings`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-005 | `review_profiles.validate_role_card` 只要求 version 非空；改为 9.9.9 并重算 hash 仍可派发。 | 明确要求受支持 role_version；U:`test_unsupported_role_version_is_rejected_before_dispatch`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-006 | `review_profiles.validate_role_result` 用 truthiness 判断不适用身份字段，模拟身份可携带空 agent_id/spawn_source。 | 不适用身份字段必须为 null/缺省；U:`test_simulation_cannot_claim_spawn_and_requires_explicit_identity`。 | CLOSED / 已解除本轮阻断。 |
| DEF-RC-007 | workflow 在 role_context 留下未被任一 task 选中的 unrelated input；修改该文件使 review 错误 stale。 | 只保留实际 task 引用并复核；I:`test_unbound_input_does_not_invalidate_a_completed_review`。 | CLOSED / 已解除本轮阻断。 |

## 主线程最终回归补充

`PYTHONPATH=src python3 -m unittest discover -s tests`：**582 tests / 145.366s / OK / exit 0**。定向角色/集成/打包52项通过；源码与packaged runtime逐文件一致、编译和插件结构校验通过。原始执行摘要见 [verification.json](evaluation/verification.json)。输出中的 `invalid JSON` 来自既有负向CLI测试，最终退出码为0。

全量首轮发现两项历史初始化回归：失效投影为缺失state添加空review字典，导致 `initialize_workspace(project_type="ui")` 跳过初始化。已修复为空state不增加字段；现有 `ArtifactProtocolTests.test_state_records_required_responsibility_categories` 与 `test_initialize_workspace_preserves_existing_state_and_artifacts` 及集成共31项通过，再跑全量582项通过。记录为 **DEF-RC-008 CLOSED**。

## 未执行事项、信息缺口与阶段交接

| 等级 | 事项 | 结论与处理 |
| --- | --- | --- |
| Blocker | 本轮已发现缺陷均已修复并完成定向复验。 | 无 CR-003 定向 QA 未关闭 blocker；更广回归/打包和发布判断由主线程记录，不能用本文件 41 项替代。 |
| Assumption | 结构化 fixture 证明规则执行，不证明 Agent 真的读取/理解材料；hash 与身份字段不是密码学身份认证。 | host 运行记录、隔离与完整 panel 仍按后续架构实现，不能虚构 receipt。 |
| Pilot / Not Run | QA后已运行四案例摘录组件对照；完整历史工件A/B、现场真实评审、模型相关性仍未验证。 | [原始记录和比较](evaluation/README.md)：两组均2有效缺口/0漏检/0误报；小样本不构成收益证明。 |
| Not Run | 完整 panel 四 API、全员屏障、幂等/并发、超时/重试/替换、崩溃恢复、receipt。 | CR-002 后续范围；当前 opt-in 角色投影不等价于完整 panel 完成。 |
| Not Run | CR-001 `TC-001～TC-026` 历史执行记录。 | 下文原样保留 Not Run；本轮 PASS 不向历史或完整 V1.1 发布扩展。 |

供 08 使用的交接摘要：**CR-003 QA PASS**，TC-RC-001～018 对应 FR-018～022、TASK-ROLE-101～106；两目标模块共 41/41 PASS，七项边界缺陷已修复并复验。八卡与 40 类例条目已审阅。当前角色契约和复合席位 opt-in 投影通过定向验证；现场评审、完整历史工件 A/B、完整 PanelRun/四 API 与发布均未执行；QA后完成的四摘录试验独立记录。可交给主线程汇总回归和发布边界，不能声称整体 V1.1 编排或评审质量提升。

---

## CR-004 复合席位测试矩阵（REV-20260926-03）

| TC | 场景 | 预期 |
| --- | --- | --- |
| TC-SEAT-001 | 遍历五个 gate 的 SeatProfile | 每个 gate 正好两个席位，角色并集完整且无重复。 |
| TC-SEAT-002 | 同一席位的多个逻辑角色使用同一 Agent | 结果通过；逻辑角色仍逐项保存。 |
| TC-SEAT-003 | 不同席位复用 Agent 或同席角色使用不同 Agent | 拒绝结果或 review。 |
| TC-SEAT-004 | 篡改 seat_id、seat_role_ids、seat_task_hash 或 review_seats | 任务重建失败，不能投影 passed。 |
| TC-SEAT-005 | 复合席位 review 记录 reviewer_agent_ids | 只允许两个席位身份，coordinator 不能占用。 |
| TC-SEAT-006 | 旧的无 seat_contract_version review | 继续兼容读取；新席位 review 不得降级 legacy。 |
| TC-SEAT-007 | 席位/输入/角色定义漂移 | active review stale；无关输入和 terminal 历史不受影响。 |
| TC-SEAT-008 | artifact/state/render/package | 完整席位和角色结果在 artifact，state 为摘要，源码与包一致。 |

定向测试覆盖 `tests/test_review_profiles.py`、`tests/test_review_role_contract_integration.py` 和 `tests/test_plugin_packaging.py`；最终执行记录在本文件和 08 交接中回填。

## CR-001 历史草案（仅供追溯，不作为执行指令）

## Change Linkage

- Change Request: CR-001
- Feature: `v1.1-multi-agent-review-orchestration`
- Requirements Source: `01-requirements.md`
- Specification Source: `02-specification.md`
- Development Plan Source: `05-development-plan.md`
- Test Strategy: Python `unittest` runtime behavior tests first; packaging/validator smoke for release verification; no browser E2E because this is not a UI project.
- Execution Status: Not Run - implementation not started

## Coverage Summary

| Coverage Area | Test Cases |
| --- | --- |
| FR-001..FR-017 | TC-001..TC-026 |
| TASK-001 | TC-001, TC-002, TC-003, TC-012, TC-016 |
| TASK-002 | TC-004..TC-013, TC-017..TC-019, TC-022 |
| TASK-003 | TC-003, TC-008, TC-010, TC-014, TC-020 |
| TASK-004 | TC-010, TC-013, TC-014, TC-015 |
| TASK-005 | TC-004, TC-006, TC-007, TC-009, TC-011, TC-012, TC-018, TC-019, TC-022, TC-023, TC-024, TC-026 |
| TASK-006 | TC-021, TC-022, TC-024, TC-025, TC-026 |
| TASK-007 | TC-001..TC-026 |

## Scenario Journey Acceptance Trace

Each `AC-V11-*` anchor is defined by the Expected Result of its mapped `TC-*` row. A coverage review must reject an acceptance anchor that is listed in this table but has no mapped executable expected result.

| Scenario | User Story | Journey Anchor | Acceptance Anchors | Planned Tests |
| --- | --- | --- | --- | --- |
| SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-001, AC-V11-002, AC-V11-003, AC-V11-004, AC-V11-013, AC-V11-014, AC-V11-024 | TC-001, TC-002, TC-003, TC-004, TC-013, TC-014, TC-024 |
| SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-005, AC-V11-006, AC-V11-007, AC-V11-017, AC-V11-018, AC-V11-023, AC-V11-024 | TC-005, TC-006, TC-007, TC-017, TC-018, TC-023, TC-024 |
| SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-008, AC-V11-009, AC-V11-019, AC-V11-023, AC-V11-024 | TC-008, TC-009, TC-019, TC-023, TC-024 |
| SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-010, AC-V11-011, AC-V11-012 | TC-010, TC-011, TC-012 |
| SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-015, AC-V11-021, AC-V11-022, AC-V11-025 | TC-015, TC-021, TC-022, TC-025 |
| SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-020, AC-V11-021, AC-V11-022, AC-V11-026 | TC-020, TC-021, TC-022, TC-026 |
| SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-023, AC-V11-024 | TC-023, TC-024 |
| SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-011, AC-V11-012, AC-V11-016, AC-V11-024, AC-V11-025, AC-V11-026 | TC-011, TC-012, TC-016, TC-024, TC-025, TC-026 |

## Per-TC Trace And Planned Evidence Matrix

This matrix is the pre-implementation coverage contract for `test_coverage` review. `Acceptance Role=Acceptance` means the TC contributes directly to scenario/journey acceptance. `Acceptance Role=Supporting` means the TC supports compatibility, packaging, static contract, or release-boundary confidence and must not be counted as the only proof for a scenario journey.

| TC | SC | US | Journey | AC | TASK | Planned Evidence Layer | Acceptance Role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-001 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-001 | TASK-001, TASK-007 | unit | Supporting |
| TC-002 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-002 | TASK-001, TASK-007 | unit | Acceptance |
| TC-003 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-003 | TASK-001, TASK-003, TASK-007 | runtime_integration | Acceptance |
| TC-004 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-004 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-005 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-005 | TASK-002, TASK-007 | unit | Acceptance |
| TC-006 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-006 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-007 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-007 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-008 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-008 | TASK-002, TASK-003, TASK-007 | unit | Acceptance |
| TC-009 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-009 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-010 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-010 | TASK-002, TASK-003, TASK-004, TASK-007 | runtime_integration | Acceptance |
| TC-011 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-011 | TASK-002, TASK-005, TASK-007 | runtime_integration | Acceptance |
| TC-012 | SC-V11-004 | US-V11-004 | J-V11-004 | AC-V11-012 | TASK-001, TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-013 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-013 | TASK-002, TASK-004, TASK-007 | unit | Supporting |
| TC-014 | SC-V11-001 | US-V11-001 | J-V11-001 | AC-V11-014 | TASK-003, TASK-004, TASK-007 | runtime_integration | Supporting |
| TC-015 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-015 | TASK-004, TASK-007 | unit | Acceptance |
| TC-016 | SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-016 | TASK-001, TASK-007 | unit | Acceptance |
| TC-017 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-017 | TASK-002, TASK-007 | unit | Acceptance |
| TC-018 | SC-V11-002 | US-V11-002 | J-V11-002 | AC-V11-018 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-019 | SC-V11-003 | US-V11-003 | J-V11-003 | AC-V11-019 | TASK-002, TASK-005, TASK-007 | unit | Acceptance |
| TC-020 | SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-020 | TASK-003, TASK-007 | runtime_integration | Acceptance |
| TC-021 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-021 | TASK-006, TASK-007 | packaging_smoke | Acceptance |
| TC-022 | SC-V11-005 | US-V11-005 | J-V11-005 | AC-V11-022 | TASK-002, TASK-005, TASK-006, TASK-007 | runtime_integration | Acceptance |
| TC-023 | SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-023 | TASK-005, TASK-007 | gatekeeper | Acceptance |
| TC-024 | SC-V11-007 | US-V11-007 | J-V11-007 | AC-V11-024 | TASK-005, TASK-006, TASK-007 | gatekeeper | Acceptance |
| TC-025 | SC-V11-008 | US-V11-008 | J-V11-008 | AC-V11-025 | TASK-006, TASK-007 | static_contract | Acceptance |
| TC-026 | SC-V11-006 | US-V11-006 | J-V11-006 | AC-V11-026 | TASK-005, TASK-006, TASK-007 | release_gate | Acceptance |

## Test Cases

| TC ID | Type | Level | FR | TASK | Core Assertion |
| --- | --- | --- | --- | --- | --- |
| TC-001 | Positive | Unit | FR-001 | TASK-001, TASK-007 | Review profile lookup identifies the exact review type and required reviewer responsibility set for each gate. |
| TC-002 | Positive | Unit | FR-002, FR-013 | TASK-001, TASK-007 | Non-UI review input snapshot includes current feature slug, Open Spec artifacts, scenario matrix, behavior contract, obligations, and stage evidence instead of static prompt text only. |
| TC-003 | Positive | Runtime integration | FR-003, FR-007 | TASK-001, TASK-003, TASK-007 | A valid `scenario` review artifact records product intent, journeys, negative boundaries, deliberation sections, and can advance the scenario gate. |
| TC-004 | Negative | Unit / Runtime integration | FR-003, FR-008 | TASK-002, TASK-005, TASK-007 | A `scenario` review with unresolved `blocking_findings` fails closed and cannot satisfy freeze. |
| TC-005 | Positive | Unit | FR-004 | TASK-002, TASK-007 | A valid `test_coverage` review accepts complete `US/J/SC/AC/TASK/TC` traceability with no coverage gaps or missing assertions. |
| TC-006 | Negative | Unit / Runtime integration | FR-004, FR-008 | TASK-002, TASK-005, TASK-007 | A `test_coverage` review missing required trace targets, coverage items, or executable assertions blocks handoff. |
| TC-007 | Negative / Regression | Unit | FR-006 | TASK-002, TASK-005, TASK-007 | `scenario`, `test_coverage`, `test_implementation`, and legacy `test` reviews are rejected when used to satisfy the wrong split gate. |
| TC-008 | Positive | Unit | FR-005 | TASK-002, TASK-003, TASK-007 | A valid `test_implementation` review requires actual test code paths, execution evidence paths, reviewed test IDs, and verified action assertions. |
| TC-009 | Negative | Unit / Runtime integration | FR-005, FR-008 | TASK-002, TASK-005, TASK-007 | A `test_implementation` review without executable assertion evidence fails closure readiness. |
| TC-010 | Compatibility | Unit / Runtime integration | FR-009, FR-012 | TASK-002, TASK-003, TASK-004, TASK-007 | Legacy records with missing `review_mode` are interpreted as `spawned_subagents`, while newly accepted V1.1 artifacts persist `review_mode` explicitly without changing existing artifact path/status semantics. |
| TC-011 | Negative / Compatibility | Unit / Runtime integration | FR-010 | TASK-002, TASK-005, TASK-007 | `role_simulation` reviews are rejected unless workflow policy allows degradation and explicit user acceptance is recorded; under `spawned_subagents_required`, user acceptance alone and role-simulation fallback cannot satisfy the gate. |
| TC-012 | Negative | Unit | FR-011 | TASK-001, TASK-002, TASK-005, TASK-007 | `blocked_with_reason`, including spawned-subagent-unavailable results, always records the visible reason and fails closed. |
| TC-013 | Negative | Unit | FR-007 | TASK-002, TASK-004, TASK-007 | Review artifact validation rejects missing or empty deliberation sections required for accepted artifacts. |
| TC-014 | Positive | Runtime integration | FR-012 | TASK-003, TASK-004, TASK-007 | Accepted V1.1 review records preserve artifact path, review ID, artifact version, review mode, and passed/missing state fields. |
| TC-015 | Compatibility / Regression | Unit | FR-012 | TASK-004, TASK-007 | Existing V1.0.10/V1.0.11 review state remains readable and only fails for documented V1.1 gate reasons. |
| TC-016 | Positive / Compatibility | Unit | FR-013 | TASK-001, TASK-007 | Branch evidence selection uses behavior contract evidence for `non_ui` and UI prototype/browser obligations for `ui` without mixing them. |
| TC-017 | Positive | Unit | FR-014 | TASK-002, TASK-007 | Collection coverage passes only when every declared item has covered items and item-level assertions. |
| TC-018 | Negative | Unit | FR-014 | TASK-002, TASK-005, TASK-007 | Collection coverage fails when any declared item lacks item-level coverage or assertion evidence. |
| TC-019 | Negative / Regression | Unit | FR-015 | TASK-002, TASK-005, TASK-007 | Marker-only, function-name-only, static-panel-only, and first-button-only assertions are classified as unresolved false-positive risks and fail the review. |
| TC-020 | Regression | Runtime integration | FR-002, FR-003, FR-004, FR-005, FR-008, FR-012 | TASK-003, TASK-007 | Workflow helpers route accepted artifacts through canonical `record_multi_agent_review` validation and cannot bypass fail-closed review validation. |
| TC-021 | Packaging | Packaging smoke | FR-001..FR-017 | TASK-006, TASK-007 | Packaged plugin runtime, skill text, and templates include V1.1 split gate rules, review modes, review templates, and artifact contract wording. |
| TC-022 | Compatibility / Packaging / Regression | Runtime integration / Packaging smoke | FR-006, FR-012 | TASK-002, TASK-005, TASK-006, TASK-007 | Legacy generic `test` review remains interpretable where already required but does not satisfy V1.1 `test_coverage` or `test_implementation` gates. |
| TC-023 | Negative / Runtime integration | Gatekeeper | FR-016 | TASK-005, TASK-007 | Non-UI pre-handoff blocks without authoritative `test_coverage`, and non-UI pre-closure blocks without authoritative `test_implementation` after implementation evidence exists. |
| TC-024 | Negative / Regression | Runtime integration / Gatekeeper | FR-017, NFR-006 | TASK-005, TASK-006, TASK-007 | Chat/session/status-only/Open Spec/custom artifact claims, including deceptive records with the right `review_type` but missing canonical fields, cannot satisfy `scenario`, `test_coverage`, or `test_implementation` gates. |
| TC-025 | Documentation / Packaging | Static contract | FR-016, FR-017, NFR-006 | TASK-006, TASK-007 | Generated package/runtime/skill/template outputs use non-UI behavior/planned evidence terminology, do not mislabel required non-UI coverage as browser-only `Planned E2E`, and do not introduce dashboard UI, external workflow/controller integration, or standalone Runtime API versioning behavior. |
| TC-026 | Negative / Release gate | Runtime integration / Packaging smoke | FR-008, FR-017, NFR-006 | TASK-005, TASK-006, TASK-007 | Release and Product Delivery closure derivation remain not eligible when TASKs are not complete, tests are not run, formal closure evidence is absent, only status/custom summary claims exist, or out-of-scope dashboard/external/API-versioning claims appear. |

## Detailed Case Design

| TC ID | Preconditions | Steps | Expected Result |
| --- | --- | --- | --- |
| TC-001 | Runtime exposes V1.1 review profiles. | Request profiles for `scenario`, `test_coverage`, and `test_implementation`. | Each profile returns exact review type, gate purpose, and required responsibilities matching the specification. |
| TC-002 | Non-UI feature state has Open Spec, scenario matrix, behavior contract, obligations, and optional executed evidence. | Build review input snapshot for each review type. | Snapshot references current feature artifacts and non-UI evidence anchors; generic prompt-only payload is rejected or incomplete. |
| TC-003 | Valid `scenario` review payload has required deliberation and no blockers. | Validate and record the review through workflow. | State records `multi_agent_reviews.scenario.status=passed`; next gate is freeze confirmation. |
| TC-004 | `scenario` review payload has non-empty `blocking_findings`. | Validate or record the review. | Review raises gate error; freeze remains blocked. |
| TC-005 | Valid `test_coverage` payload has `US/J/SC/AC/TASK/TC`, empty gaps, and collection coverage. | Validate `test_coverage`. | Validation passes. |
| TC-006 | `test_coverage` payload omits one trace target or includes missing executable assertions. | Validate or derive pre-handoff blockers. | Review fails and handoff blocker remains. |
| TC-007 | Valid artifact body is supplied under the wrong required gate. | Validate substituted review types, including legacy `test` for split gates. | Validation rejects every substitution. |
| TC-008 | `test_implementation` payload includes real code paths, evidence paths, reviewed IDs, and action assertions. | Validate `test_implementation`. | Validation passes. |
| TC-009 | `test_implementation` payload omits code paths, evidence paths, or verified assertions. | Validate and check pre-closure readiness. | Validation fails; closure blocker remains. |
| TC-010 | Existing legacy review record omits `review_mode`; a new V1.1 review is recorded. | Load compatible state, then record a new accepted review. | Legacy mode is interpreted as `spawned_subagents`; new review state persists explicit `review_mode` and expected review state semantics. |
| TC-011 | Review mode is `role_simulation`; current policy is `spawned_subagents_required`. | Validate without acceptance, then with user acceptance but default policy, then with explicit degradation policy and acceptance. | First two paths fail; user acceptance alone cannot override `spawned_subagents_required`; only accepted degradation under allowed policy passes outside this current run. |
| TC-012 | Review mode is `blocked_with_reason`, including spawned-subagent-unavailable output. | Validate review. | Validation fails closed and exposes blocked reason; no role-simulation fallback is accepted under `spawned_subagents_required`. |
| TC-013 | Review omits `independent_positions`, `cross_challenges`, `revisions`, `final_adjudication`, or `blocking_findings`. | Validate review. | Validation fails with missing-field error. |
| TC-014 | Workflow records an accepted V1.1 review. | Inspect state fields after recording. | State preserves artifact path, review ID, artifact version, review mode, and status. |
| TC-015 | Fixture uses V1.0.10/V1.0.11 review state shape. | Load/normalize state and validate documented gates. | Existing fields remain interpretable; failures are only documented gate failures. |
| TC-016 | Project type varies between `non_ui` and `ui`. | Build prompt/input snapshot for both project types. | `non_ui` uses behavior contract/evidence; `ui` uses UI prototype/browser obligations. |
| TC-017 | Collection coverage declares all required items and assertions. | Validate coverage review. | Validation passes. |
| TC-018 | Collection coverage declares an item missing from `covered_items` or `item_level_assertions`. | Validate coverage review. | Validation fails and names the missing item. |
| TC-019 | Assertions contain marker-only, function-name-only, static-panel-only, or first-button-only evidence. | Validate coverage or implementation review. | Validation classifies unresolved false-positive risk and fails. |
| TC-020 | Workflow helper receives valid and invalid review artifacts. | Record through helper and compare with direct canonical validation behavior. | Helper cannot bypass canonical validation; invalid payloads fail identically. |
| TC-021 | Packaging function builds plugin distribution. | Inspect generated runtime assets, skill text, and templates. | Package contains V1.1 orchestration wording, split review templates, and review mode/fail-closed rules. |
| TC-022 | Legacy generic `test` review exists in state. | Check compatibility loading plus split gate validation. | Legacy state is readable; split V1.1 gates still require authoritative review types. |
| TC-023 | Non-UI state has behavior contract and scenario matrix, but one split review gate is missing or substituted. | Derive pre-handoff blockers before `test_coverage`, then derive pre-closure blockers after implementation evidence without `test_implementation`. | Pre-handoff names missing `test_coverage`; pre-closure names missing `test_implementation`; legacy `test` and wrong split reviews do not clear either blocker. |
| TC-024 | State or custom artifact claims a review is `passed` without a matching structured artifact and validated gate-specific fields. | Attempt to satisfy `scenario`, `test_coverage`, and `test_implementation` with chat/session/status/Open Spec/progress/custom-only evidence, then with a deceptive record using the right `review_type` but missing deliberation or gate-specific fields. | Every gate remains blocked and reports that supporting evidence or incomplete canonical-looking records cannot replace the validated structured review artifact. |
| TC-025 | Package generation renders non-UI instructions, templates, planned obligation wording, and runtime assets. | Inspect generated runtime/package/skill/template outputs for `non_ui`, behavior evidence, split review gates, browser-only wording, dashboard behavior, external workflow/controller integration behavior, and standalone Runtime API versioning behavior. | Non-UI text references planned behavior evidence or planned obligations; browser E2E wording is only branch-specific UI compatibility text; dashboard UI behavior, external workflow/controller integration behavior, and standalone Runtime API versioning behavior are absent or explicitly out of scope. |
| TC-026 | State, Open Spec, package output, or closure derivation claims release/closure readiness while TASKs are incomplete, TC execution records are `Not Run`, closure validation is missing, or out-of-scope dashboard/external/API-versioning claims appear. | Run release-readiness/closure gate derivation against the incomplete state and inspect generated package/release text and closure blocker output. | Release remains Draft / Not Released; Product Delivery closure remains Not Eligible; status/custom-only closure claims and out-of-scope dashboard/external/API-versioning claims are rejected by gate derivation. |

## Execution Records

| TC ID | Executor | Execution Date | Result | Defect |
| --- | --- | --- | --- | --- |
| TC-001 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-002 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-003 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-004 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-005 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-006 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-007 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-008 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-009 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-010 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-011 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-012 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-013 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-014 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-015 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-016 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-017 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-018 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-019 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-020 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-021 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-022 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-023 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-024 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-025 | N/A | N/A | Not Run - implementation not started | N/A |
| TC-026 | N/A | N/A | Not Run - implementation not started | N/A |

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None for test-case design. | Testing-stage case design can proceed. | PASS |
| Assumption | Runtime implementation names may shift during TASK-001..TASK-006. | Test filenames and helper names may need minor alignment after RED-first implementation starts. | Carry forward |
| Constraint | Implementation has not started. | No test execution or pass/fail evidence is available. | All execution records remain Not Run |
