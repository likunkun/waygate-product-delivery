# V1.2.0 团队生产编排阶段交接

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Workflow Lead |
| 日期 | 2026-09-29 |
| 状态 | 交接契约、自动化验证与真实六阶段宿主演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按真实接口与文件存储纠正计划及验收边界。 | CR-005 |

## 阶段交接表

| 顺序 / stage | stage lead 关注 | 入口及出口 |
|---|---|---|
| 1 product_definition | 用户目标、范围、来源与验收 | 保留 startup input understanding；产出产品蓝图/验收，不要求当前 canonical TASK |
| 2 architecture_version_planning | 组件/接口、版本递进和风险 | 接收产品定义；形成架构契约与版本计划，此时尚不要求产品基线 confirmed |
| 3 open_spec_product_surface | 场景/行为契约；UI prototype 依赖 scenario | 接收架构/版本计划；整合后执行 scenario review，再经既有用户确认冻结产品基线 |
| 4 test_design | 需求/旅程/异常的测试矩阵与执行条件 | product baseline confirmed 后生产；test 与 test_coverage review 后确认覆盖计划 |
| 5 implementation_execution | 当前 canonical TASK、实现/测试自动化/集成 | 已确认覆盖、canonical handoff 和实施授权；每轮只绑定当前 task_id，整合和证据校验后仍由原 TASK API 推进 |
| 6 delivery_preparation | 交付证据、构建准备、恢复说明 | 全部实施 TASK 完成后进入；test_implementation review，UI 另有 ui_conformance；正式 closure 仍独立 |

同版本安全边界从 policy.entry_stage 接续真实进度；冻结基线的返工使用既有变更路径，不能伪造已完成前置阶段。完成一阶段不会自动确认下一阶段的用户门禁。

## 最小交接内容

owner 从 `inspect_team_run(run_id)` 的真实字段构建交接，成员只收到对应 package 的 task 与 staging_root：

- delivery_id、run_id、stage、profile.profile_version、revision、status；实施时附 task_id。
- 工作包 work_package_id、role_ids、depends_on、allowed_write_paths、attempt/status/agent_id，以及 task_hash、role_definition_hashes、task_template_hashes。
- task.input_refs、input_snapshot_hash、required_outputs、must_check；实际 staging_root 与产物/变化/evidence manifests。
- deadline、recovery_count、revision_count、未决 blocker/question、已整合依赖和 integration receipts。
- 相应 review lock 的 phase、members、input_hash；由 owner 查看及提交评审，不能将他人未冻结结果塞入生产简报。
- 下一动作、责任和 Memory Delta（事实、风险、未决问题）；Memory Delta 是交接说明，不是新增 TeamRun schema 字段。

work package 总数可大于二，调度时最多二个 running。实施前没有 canonical_task_version，不能在交接中虚构已存在的 TASK、event_seq 或 review_freeze 字段。

## 运行摘要示例（仅字段示意，不是执行证据）

```yaml
run_id: <actual run id>
delivery_id: <current delivery id>
stage: implementation_execution
profile_version: 1.2.0 # 从 run.profile 提取
revision: <actual revision>
status: <actual run status>
task_id: <current canonical task id>
work_packages:
  - work_package_id: <id>
    status: <actual package status>
    attempt: <actual attempt>
    task_hash: <sha256>
    input_snapshot_hash: <sha256>
    depends_on: []
    recovery_count: 0
    revision_count: 0
usage: {status: unavailable}
```

此摘要不是 API 可提交 payload，也不代表零计数或 unavailable 已在某真实运行中观测；运行交接须逐项取实际值和 ref。API payload 使用 02 的严格字段。

## 交接检查

owner 核对当前 policy/确认 scope、输入与 accepted artifact hash、任务 role/profile/hash、依赖整合与 attempt；实施阶段另核对当前 TASK。需要评审的产品面/测试设计/交付准备阶段必须完成对应三屏障并通过原 gate。无 review 的阶段不额外虚构 review freeze 条件。

缺输入报告 needs_input，hash/范围冲突报告实际拒绝原因；不能自动把旧结果接到新 TASK。TeamRun completed 后继续原确认/TASK/正式 closure 路径，HostGoalOwner 保持唯一目标推进者。

## 信息缺口与追溯

- Blocker：无。真实 UI/non_ui 六阶段 handoff/run 摘要已归档于 `10-release-exercise-report.md` 及其 `/tmp` 证据目录。
- Assumption：owner 可取得真实 spawn 和执行记录并维护最小成员交接；shared_fs 的进程隔离由宿主负责。
- Nice-to-know：跨 run 长期 Memory Delta 汇总可后续评估，不新增存储契约。

FR-003..007/013..018/020 → TASK-004/008..010/014/017 → TC-003..006/013..019/023。
