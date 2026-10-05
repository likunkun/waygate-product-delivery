# V1.2.0 团队生产编排技术方案

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 作者 | Open Spec Solution |
| 日期 | 2026-09-29 |
| 状态 | 设计已对齐当前实现；自动化验证、真实宿主验收与正式 closure 演练完成 |
| 关联 CR | CR-005 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
|---|---|---|---|---|
| REV-20260929-01 | 2026-09-29 | Codex | 建立团队生产编排设计文档。 | CR-005 |
| REV-20260929-02 | 2026-09-29 | Codex | 按角色目录、编排模块及 workflow 的真实契约修正；保留验证缺口。 | CR-005 |

## 架构与职责

- `production_profiles.py` 无 I/O，提供 15 张版本化角色卡、六阶段 profiles、工作包依赖构建与结果 schema/evidence 校验。
- `team_orchestration.py` 在 owner workflow 锁内处理 run revision、真实文件验证、派发事件、staging、整合意图、评审屏障和有限恢复；它不自行 spawn 进程。
- `workflow.py` 暴露 02 中 owner APIs，消费必要的 HostGoalOwner 授权观测；精确幂等重放不重复消费 Goal transition。
- 既有 startup、确认、review artifact 提交、TASK 和 closure API 保持 canonical authority；生产完成不替代这些门禁。

## 状态与调度

run 初始 `prepared`，派发后为 `running`；未完成结果/成员失败进入 `needs_remediation`，全包整合后为 `integrated`，finalize 后为 `completed`。暂停使用 `paused` 并保留 `resume_status`，恢复时输入失效可成为 `stale`；owner 可在成员停止后 `cancelled`。没有独立的 timed_out/recovering/finalized run 状态。

包状态为 `pending→running→ready→integrated`；结果也可进入 `needs_input/needs_rework/failed`。retry/revise 创建新 attempt 并保留旧 history。每包最多一次 recovery 与一次 revision，deadline 是每次实际派发后 1800 秒。宿主负责感知 deadline 并报 timeout，模块校验超时是否真实发生。

整个 run 可包含多个依赖包；任意时刻至多两个 running。同一 agent 不同时承接两个包，成员身份不得等于 owner；并发写路径不得交叉。依赖必须 integrated。integration 角色在各实现贡献整合后执行，角色卡可合并到同一包，不要求 15 个常驻 agent。

## 输入与 staging

prepare 校验 owner 给定的 `input_refs` 的实际文件 hash 和当前确认/TASK scope，生成绑定角色版本、profile hash 和 task hash 的简报。任务只携带角色所需输入；派发时 workspace 只复制该简报输入和获准写目标，避免复制整个仓库或会话历史。依赖已整合时，下游简报更新为实际依赖字节及 hash，并留存 brief_history。

成员写自己的 attempt workspace，返回 artifacts/changes/check_records 等结构化 ProductionResult；只读输入被改、越权路径、symlink、artifact hash 不符、未绑定证据或 simulated 身份均被拒绝。`shared_fs` 描述共享文件系统的实际保护等级，不能声称提供 OS 沙箱或物理阻断任意 agent 读取。

## 整合与中断恢复

1. owner 选择 run 内所有 ready 包，校验产物、任务/输入新鲜度、无重复目的路径和目标 `base_sha256`。
2. 将 run/revision/包清单、before/after hashes、操作与内容写入不可变 merge intent，再逐文件原子应用。
3. 重入时核对 intent 自身 hash 和原 run hash；整批先检查目标只可能为获准 pre 或 post hash。命中 post 表示该文件已应用，跳过重复写；出现第三种字节则拒绝并保留外部编辑。
4. 复制 accepted artifacts、记录 contributor、integration receipt 与新 run revision。pending intent 未处理前禁止新事件或暂停掩盖部分整合。

该方案按声明的 add/modify/delete 应用文件内容，没有文本三方自动合并。文件批次中断可能留下部分应用，必须按意图恢复；不承诺跨文件事务原子性，也不以旧副本覆盖 owner 的新编辑。存储布局见 04。

## 评审与确认

生产阶段顺序为产品定义→架构/版本计划→Open Spec 产品面→测试设计→当前 TASK 实施→交付准备。产品面整合后启动 scenario review，再由用户确认产品基线；测试设计整合后完成 test/test_coverage review 和覆盖确认，再 handoff 与实施授权。交付准备整合后执行 test_implementation，UI 再执行 ui_conformance。

review_started 冻结输入与 accepted artifacts；每个 gate 的两个独立 reviewer 依次提交 independent、challenge、revision 的 hash 绑定证据。生产 contributor 和 owner 均不得作为独立 reviewer。期间禁止生产派发与整合；多个 gate 的拒绝先汇总 work_package_ids，所有相关锁处理完毕后由 owner 一次批量修复。三屏障完成不等于 gate 通过：原 review API 仍验证当前快照与 reviewer 身份并提交 gate 裁决。

non-UI 交付在真实 CLI/API/service 执行后调用 `record_executed_behavior_evidence()`；该入口使用独立 behavior evidence builder，校验成功退出码、语义断言、真实 `evidence_path` 与 `trace_path` 文件，并为这些文件写入 hash；可选 stdout/stderr/log 文件也必须存在且写入 hash。它复用当前 planned obligation 的覆盖绑定和 review stale 规则，但只写 `executed_behavior_evidence`，不会冒充 UI browser evidence，也不要求或记录 screenshot、acceptance_url、browser evidence_strength、network probe、mocked_routes 或 probe_artifact_path。没有这一步时 non-UI canonical closure 保持 fail closed。

## 指标与验证限制

run 保存时间、attempt、失败、rework 和整合证据，`usage.status` 初始 unavailable。质量/返工/耗时/可用用量的 coordinator/team 对照由真实 host exercise 记录；不能把 schema、fixture 或 Python 测试等同于真实宿主成功，也不能推断多 agent 必然提高质量。

## 信息缺口与追溯

- Blocker：无。真实宿主闭环证据、对照报告与正式发布演练已完成，详细记录见 `10-release-exercise-report.md`。
- Assumption：宿主能停止旧 attempt 并提供真实 spawn source；共享文件系统的 OS 权限由宿主负责。
- Nice-to-know：本次同机 smoke 对照记录 usage 为 `unavailable`，未推断质量、返工、耗时或成本收益；长期差异仍需多样本观测。

FR-003..017、NFR-001..010 对应 TASK-002..009/012/015/017 与 TC-003..016/022..024。
