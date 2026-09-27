# V1.1.0 评审专家团编排 - 04 存储设计

| 字段 | 值 |
| --- | --- |
| 版本 | V1.1.0 |
| 作者 | Codex / Open Spec Lead（合并方案阶段分析） |
| 日期 | 2026-09-26 |
| 状态 | CR-003 角色摘要/报告存储已接入；完整 PanelRun 存储仍是设计，未发布 |
| 源基线 | V1.0.42 |

## 修订记录

| 修订号 | 日期 | 作者 | 变更摘要 | 关联 CR |
| --- | --- | --- | --- | --- |
| REV-20260701-01 | 2026-07-01 | Codex | 历史 V1.1 存储草案。 | CR-001 |
| REV-20260926-01 | 2026-09-26 | Codex / Open Spec Lead | 按当前 delivery store 合并方案分析，定义 panel 数据、提交恢复、权限及兼容边界。 | CR-002 |
| REV-20260926-02 | 2026-09-26 | Codex | 同步角色契约实现、存储/交接和验证边界，保留历史。 | CR-003 |
| REV-20260926-03 | 2026-09-26 | Codex / Open Spec Implementation | 固定两个复合 reviewer 席位，保留八个逻辑角色并同步席位身份、存储、测试和兼容规则。 | CR-004 |

## CR-003 角色增强的实际存储（REV-20260926-02）

本次已接入 RoleCard/task/result 校验与现有 review 工件，不创建下文目标架构中的 `review-panels/<run_id>/` 或四个 PanelRun API。源与插件发布版本保持 1.0.42，角色契约版本为 1.1.0。

- `multi-agent-<review_type>-review.md` 的 Role Contract JSON 保存完整 `role_context`、`role_tasks`、`role_results`，可核对逐项证据、身份和方法。
- `multi_agent_reviews[type]` 保存角色/模板/任务 hash、输入绑定、coordinator ID、工件 canonical 路径/hash 和 `role_binding_sha256`；完整任务和成员对话不进入 state。
- `input_snapshot_hash` 沿用现有业务快照；`task_hash` 另绑定 delivery、feature、项目分支、选定输入文件内容、角色定义和任务方法。只绑定 profile 实际使用的输入，未选中输入变化不失效。
- `prepare_review_role_tasks()` 只读；提交通过原 `record_multi_agent_review()`，校验 owner、实际文件内容、任务、成员身份与现有 gate。`load_state()`/gatekeeper 只读投影 stale，不悄悄写 state。
- 已绑定该 gate 的评审不可用 legacy passed 字典替换；未启用角色契约的旧 gate 保持原语义。closed/abandoned 历史保留；无关角色变化不影响当前 gate。
- 当前固定 catalog 是该 runtime 的方法来源；活跃记录绑定的方法/template 被改写会 stale。完整的 per-run 冻结 catalog、阶段事件恢复与自动新交付 activation 属于下文 CR-002 目标架构。

## 变更关联与存储权威

依据 [00 变更](00-change-request.md)、[01 需求](01-requirements.md)、[02 规范](02-specification.md) 和 [03 方案](03-technical-solution.md)，本文件定义待实现的存储契约。当前代码仍为 1.0.42，不表示以下目录或 API 已经生成。

沿用本地 JSON/Markdown，不新增数据库、外部队列或后台服务。canonical 工件位于 delivery 目录；当前控制面 `.product-delivery/state.json` 与 delivery 的 state 副本由现有写入路径保持一致。根 `.product-delivery/artifacts/` 只作兼容镜像。

```text
.product-delivery/
  state.json
  current.json
  deliveries/<feature_slug>/<delivery_id>/
    state.json
    manifest.json
    artifacts/
      review-panels/<run_id>/
        snapshot.json
        roles.json
        run.json
        briefs/<seat_id>/<phase>/attempt-<n>.json
        events/<event_id>.json
        members/<seat_id>/<phase>/attempt-<n>.json
        intents/<commit_id>.json
        decision.json
      multi-agent-<review_type>-review.md
```

- `manifest.json` 登记每个工件的 artifact type、feature/delivery、路径和 SHA-256；run/seat/phase/attempt/commit 等动态工件使用唯一类型键，避免新轮次覆盖旧索引。
- `current.json` 绑定当前 feature/delivery 与 manifest hash；沿用现有状态、指针、镜像及 journal 完整性检查。
- `snapshot.json` 和 `roles.json` 在 run 内不可覆盖；成员输出按 phase/attempt 分开保存，旧尝试保留供追溯。
- 所有路径由 facade 从校验后的 ID 构造，不使用成员提供的任意输出路径；证据路径须在允许来源内解析，不能通过路径穿越或外部符号链接写出交付目录。

## 数据对象与字段

以下 `hash` 均为小写 SHA-256；身份字段为非空字符串，`ref` 是经过 owner/内容哈希校验的引用。不是仅检查路径存在或调用方自报 passed。

### RoleDefinition 与 PanelProfile

角色的完整必填字段以 02 的 RoleCard 22 字段为规范，方法字段使用 `task_steps`，输出字段使用 `output_schema`；逐角色内容见 [09 角色卡](09-role-cards.md)。

`roles.json` 固定本 run 所用的完整角色定义、模板正文、输出契约及渲染版本，不只是保存无法复现的哈希。方法来源是参考记录，不授予新工具或写入权限。具体模型和模型配置不保存。

| Profile 字段 | 类型 | 约束 |
| --- | --- | --- |
| `profile_id` / `profile_version` | string | 固定五类 profile 的身份与版本 |
| `review_type` | enum | scenario/test/test_coverage/test_implementation/ui_conformance |
| `required_roles` | list[string] | 02 所列完整 role_id，精确 2 或 3 个，不重复 |
| `required_inputs` | list[object] | 按阶段和项目分支声明证据要求 |
| `interaction_policy` | object | 独立检查、一次质疑、一次修订、裁决及全员屏障 |
| `runtime_policy` | object | 每席位/阶段 600 秒；每席位每 run 一次重试或替换；每自动周期最多两次 run |
| `profile_hash` | string | Profile 规范化内容哈希，不包含自身 |

目录版本用于追溯；运行有效性只绑定本次使用的角色、profile 和模板，不把全目录更新当作失效触发器。

### ReviewSnapshot

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `delivery_id` / `feature_slug` / `project_type` | string | 与当前授权及分支精确匹配 |
| `review_type` / `review_mode` | enum | gate 与实际模式；真实或已授权模拟 |
| `authorization_policy_ref` / `authorization_policy_hash` | string | 已有 current-delivery 评审授权，不新建批准节点 |
| `user_acceptance_ref` / `user_acceptance_hash` | string/null | simulation 必需；真实模式不伪造降级接受记录 |
| `source_refs` | list[object] | canonical 工件或受控仓库文件，含路径、内容哈希、证据锚点及冻结副本引用 |
| `profile_hash` | string | 当前冻结 profile |
| `role_definition_hashes` / `template_hashes` | map[string,string] | 精确覆盖 profile 中全部角色 |
| `policy_hash` | string | 当前 run 限制策略 |
| `snapshot_hash` | string | 对 02 指定的稳定输入事实计算 |
| `created_at` / `runtime_provenance` | string/object | 创建时间、包来源；不把时间戳混入业务失效哈希 |

Open Spec 和实际测试源码通常在仓库文件中，不强制其原路径位于 delivery artifacts；读取时固定路径、字节哈希和必要副本。权威业务工件必须通过当前 delivery 的 manifest 解析。根兼容镜像、聊天总结不能代替来源身份。

快照哈希不包含运行进度、receipt、usage、revision、pending、最终投影或自身。禁止形成哈希循环或每次成员回传都触发自我失效。

### PanelRun

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `run_id` | string | delivery 内唯一 |
| `parent_run_id` | string/null | 复验或新修复周期关联同 delivery、同 gate 的旧 run |
| `cycle_id` / `cycle_index` | string/integer | 每周期 index 为 0（初审）或 1（复验）；新周期需新修复证据和原因 |
| `review_type` / `review_mode` | enum | 与快照、授权及结果身份一致 |
| `profile_hash` / `snapshot_ref` / `snapshot_hash` | string | 冻结输入身份 |
| `authorization_policy_ref/hash` / `user_acceptance_ref/hash` | string/null | 与 Snapshot 同义；按模式校验 |
| `phase` | enum | prepared/independent_review/cross_challenge/revision/adjudication/validating/completed |
| `status` | enum | prepared/running/passed/blocked/stale/needs_remediation |
| `revision` | integer | 成功接纳一次事件批次递增一次；失败或重复确认不递增 |
| `seat_summaries` | list[object] | profile 每个角色有且仅有一个有效席位，旧尝试不算额外席位 |
| `pending_commit` | object/null | intent_ref、intent_hash、commit_id、基准 revision；不能作为通过证据 |
| `artifact_refs` | object | 运行详情、输出、decision 和最终 review 的引用 |
| `failure_reason` / `stale_reason` | string/null | 不能用状态摘要隐藏未完成原因 |
| `protection_level` | enum | host_enforced_readonly/shared_fs/unavailable；只记录宿主真实提供的保障 |
| `usage` | object | 宿主实测值或 unavailable；不根据模型价格推算 |

只有 `phase=completed,status=passed` 可参与正式投影；`completed/needs_remediation` 表示评审完成但尚不能通过。blocked/stale 保留停止时 phase 和部分排查材料，不能当作完整评审。

### MemberResult、Event 与 Decision

| 对象 | 最小字段及约束 |
| --- | --- |
| MemberResult | run/seat/phase/attempt、role_id/version/definition_hash、snapshot_hash、identity_kind、结构化检查覆盖、独立立场、findings、证据和不确定项；无发现也需正向覆盖 |
| Spawned identity | `identity_kind=spawned`，真实 agent_id 互异且非 coordinator，spawn_source 和可用宿主返回引用；不能用模型名替代身份 |
| Simulated identity | `identity_kind=simulated`，逻辑 seat 和模拟执行者；agent_id/spawn_source 为空，不编造真实回执；run 绑定降级 policy 和用户接受 |
| Finding | finding_id、role/seat 来源、rule/check、subject_ref、evidence_refs、severity、blocking、影响、建议和处置；主线程合并时保留全部来源与分歧 |
| Event | event_id、payload_hash、event_type、run_id、expected_revision、时间和 payload；成员事件绑定 seat/phase/attempt，adjudication 由 coordinator 提交 |
| ReviewDecision | coordinator、去重 finding-set、accepted/rejected suggestions、驳回证据、unresolved_questions、blocking_findings、最终校验结果与 decision hash |

事件类型与阶段要求以 02 为准。`blocked_with_reason` 是阻塞报告，不产生通过投影；可以保留已收集的部分成员材料用于排查。

## 当前状态摘要与索引

`state.multi_agent_review_runs[run_id]` 只保存 run/profile/delivery、phase/status/revision、快照/运行详情引用、席位状态、pending 引用和阻塞原因；全量意见、事件与 brief 在独立工件中。

`state.multi_agent_reviews[review_type]` 保持已有字段：`status`、`artifact`、`review_id`、`artifact_version`、`review_mode`、`reviewer_agent_ids`、`reviewer_spawn_source`、`input_snapshot_hash`。新契约增加 panel_run_id/profile/角色绑定引用；这些字段对历史读取可选，对新 1.1 交付通过必需。

最终 `input_snapshot_hash` 从当前业务来源及冻结角色/profile/template重算，与正式 run 匹配；不盲信客户端提供的 hash。真实模式投影 2–3 个有效席位的真实 ID，历史失败/替换 ID 留在 run 中。simulation 投影继续带显式弱证据标记。

## 提交、幂等与崩溃恢复

### 提交协议

1. 公开 mutation 校验原 coordinator、runtime receipt、delivery policy 和业务输入。handoff 后需有效且 fresh 的 stage_transition 观察；内部候选计算不重复消费。
2. 进入一层 state lock，重读当前 state 和 run revision。先识别已提交同 ID/同 payload 的重试，再核对新事件的 expected_revision；同 ID 异内容或新事件旧 revision 拒绝，整批不部分提交。
3. 在内存中生成确定的候选 run、必要 artifact 内容和限定 state patch。原子持久化不可变 intent（临时文件+替换），保存原请求/事件、基准 revision、业务输入、目标工件内容或可校验 durable refs、哈希和 commit_id。只有哈希而无内容来源的 intent 不可重放。
4. 在同一锁内使用 locked helper 登记 pending 引用，再通过现有 artifact store 写权威工件、manifest、pointer、mirror。按 run/commit 使用独立名称，intent 的存在不代表业务提交或评审通过。
5. 校验目标工件完整性，追加一次对应 journal 事件；在同一提交完成 run、正式投影（若通过）、revision 和 pending 清除。继承现有 root/delivery state 同步机制，不先写 passed 再补结果。

公共 `write_state()` 已自持锁；外层持锁时必须用内部 locked helper，不能再调用公共写 API。锁只覆盖本地提交，不在等待成员或调用模型期间持有。当前存储是多文件写入；进程级锁与单文件替换不能被称为跨文件原子事务。

### 恢复判定

| 中断点 | 恢复行为 |
| --- | --- |
| intent 尚未完整持久化 | 当前 gate 不推进；不接纳临时文件，可按原请求重试 |
| intent 已写、尚无 pending | 视为未提交意图；原 mutation 用原请求/业务输入/基准 revision 校验后登记，不能凭孤立文件放行 |
| pending 已登记、目标工件或镜像欠写 | 仅按已校验 intent 补写指定内容；状态保持不可通过 |
| 内容、引用或输入与 intent 不符 | 明确 blocked/stale，不盲目覆盖现有文件 |
| 工件完整、state 最终提交未完成 | 重新核对当前修订及 journal，应用限定 patch 并完成提交，不还原旧全量 state |
| state 已提交但响应丢失，或 state 副本/镜像未刷新 | 根据 commit/event ID 确认已有结果，补齐可验证镜像；不重复增加 revision/journal 或重复放行 |

`inspect_review_panel()` 只能报告 pending 和恢复动作，不写文件、不清 pending、不消费 Goal。恢复由原 mutation 执行；handoff 后重新取得 fresh 对账，不重放旧 checkpoint，不覆盖最新 Goal 状态。恢复路径可识别并修复 intent 精确说明的中断欠写，但不能一般性跳过 owner、runtime、journal 或来源哈希检查。

## 失效、兼容与回滚

- 新 delivery 把 V1.1 panel policy 绑定到 activation/runtime 身份；缺字段不能自动降级为 legacy。
- 原 1.0.42 active delivery 在原 runtime/策略下完成，其原评审保留原规则的 gate 效力。新交付不得把这些历史记录直接当成新 panel 通过。
- 安装 catalog 更新不替换冻结 active profile；无关角色和历史 closed 交付不失效。实际绑定输入或定义不匹配使本 run stale，新材料用新 run，不覆盖旧快照。
- 同快照席位替换保留旧输出，失效依赖它的后续质疑/修订/裁决，再按 02 重新收集。
- 回滚先停止新 dispatch 并保留所有工件；不改 passed/blocked/stale，不删除 policy、不混写旧 runtime、不还原整份 state。新版本交付需要修复兼容路径后恢复，不能靠关闭检查继续通过。
- 本轮不执行迁移、回填、清理或任何 runtime 写入。

## 可观测性与验收追溯

以 delivery/run/gate/role/seat 和事件 ID 定位记录，不新建数据库索引。receipt 包含 phase/status/attempt、开始结束/耗时、失败或替换原因、证据和 journal 引用、真实保护等级、用量数值或 unavailable。保留复现任务所需模板/brief，避免保存模型配置、密钥和无关完整对话。

| 存储验收 | 追溯 |
| --- | --- |
| 角色/profile/授权及输入可复现，错 gate 不替代 | FR-001～007、FR-013～020；NFR-001～008、NFR-010 |
| 事件重复确认、冲突整批拒绝、修订号保护、超时/恢复限制 | FR-008～011、FR-023；NFR-003、NFR-010～011 |
| 各中断点不得出现无工件的 passed，恢复不重放 Goal、不覆盖新 state | FR-017、FR-021～023；NFR-006、NFR-009、NFR-011 |
| 精确失效、新旧 policy 和历史有效性保持 | FR-012、FR-021；NFR-004、NFR-012 |
| 完整 receipt、模式身份、真实保护等级、用量 unavailable | FR-009～011、FR-022～024；NFR-002、NFR-009、NFR-013 |

后续实施需在 06 同步并执行并发 mutation、每个中断点、重复恢复、身份错配和镜像完整性测试。本轮只完成存储设计，不把上述验收表作为已执行证据。

## 信息缺口

| 等级 | 项目 | 处理 |
| --- | --- | --- |
| Blocker | 无设计级阻塞 | 数据对象、权威来源、提交/恢复和兼容边界已确定 |
| Assumption | 复用当前 file-backed store 并提供内部 locked helper | 实施验证单层锁、CAS、journal 和多文件恢复；不新增数据库 |
| Assumption | 宿主隔离和用量可能不可得 | 记录 shared_fs/unavailable，不据此捏造保障或费用 |
| Nice-to-know | 实际运行规模与性能 | 后续用真实交付测量，不承诺未测延迟 |

## 存储阶段门禁

**设计自检 PASS（CR-002 / REV-20260926-01）**：覆盖数据、路径、索引、幂等、恢复、失效和兼容。该结论不代表 runtime 已实现、实际故障恢复已验证或正式交付门禁通过。


## CR-004 席位存储增量

`multi_agent_reviews[type]` 新增 `seat_contract_version`、`review_seats`、`seat_ids`、`seat_agent_ids`、`seat_task_hashes`、`role_seat_ids`。完整席位任务和逻辑角色结果仅写入 review artifact，state 仅保留摘要。

`role_binding_sha256` 覆盖席位 profile、席位身份、席位任务 hash 和逻辑角色映射。席位变化、角色错配、实际输入文件漂移或业务快照变化使 active review stale；无关输入、无关角色和 terminal 历史不失效。
