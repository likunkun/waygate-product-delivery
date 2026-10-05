# V1.2.0 团队生产编排存储设计

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

## 存储方案

本版本沿用本地文件与 canonical state，不新增数据库、后台服务、数据表、索引或 schema migration。production policy 和 run 摘要进入既有 state；不可变 run revisions、staging、accepted artifacts 与 merge intents 存在当前 delivery 目录，状态变更沿用 append_transition 审计 journal。

```text
.product-delivery/deliveries/<feature_slug>/<delivery_id>/team-runs/<run_id>/
  revisions/<revision>-<run-content-hash-prefix>.json
  work/<work_package_id>/<attempt>/workspace/<narrow input and staged files>
  accepted/<work_package_id>/<attempt>/<index>-<artifact-sha256>
  intents/integrate-<source_revision>.json
```

已存在的 staging attempt 目录不会被接管；重建副本使用带唯一后缀的目录。真实相对目录以返回 run 的 staging_root 和各 ref 为准。

## canonical state 引用

| 位置 | 实际内容与约束 |
|---|---|
| production_policy | schema_version、introduced_in=1.2.0、mode、delivery_id、feature_slug、owner_thread_id、max_parallel=2、authorization_source、entry_stage、policy_hash |
| team_runs[run_id] | run_path、run_sha256、stage、status、revision、task_id、work_packages 的 status/attempt/agent_id 摘要 |
| team_review_locks[review_type] | run_id、两个 reviewer_agent_ids、phase、members、input_hash、sources |
| production_contributors | 已整合真实生产成员身份集合，供独立评审排除 |
| transition journal | 既有 append_transition 记录转移、runtime_version、输出 artifact hash 与 run_id/revision 元数据 |

读取 run 必须验证 run_path 文件的实际 SHA-256、run_id 和 delivery_id，不能仅相信摘要。每次成功变更新建 revision 文件并更新 state 引用，保留历史 revision；写入在 workflow state lock 下执行。JSON 与替换文件使用 flush/fsync 和原子 replace。不可变 revision、event hash 与既有 journal 联合用于审计；不是从 event payload 自动重放的数据库事件表。

## 输入、事件和产物

run.input_refs 保留准备时输入绑定，task.input_refs 是各角色的最小子集；staging 只复制该子集和声明写目标。`events` 是 event_id 到 payload hash 的映射，结果全文保存在 work package 的 result/history 中；不虚构 event_seq 或 prev_event_hash 链。哈希根据对象/文件分别计算，不承诺“所有时间字段不参与 hash”。

accepted artifact 按 sha256 命名并在 finalize 时复核，staging 的后续改动不能替代 accepted 证据。run.usage 初始为 unavailable；真实指标另由宿主报告，不能从运行时间推算 token/cost。

## Merge intent 与恢复

intent 保存 run_id、run_sha256、source revision、包 id、changes 和 intent_hash。change 保留 base_sha256/result_sha256、目标路径、操作、staged_path、编码内容和文件 mode。意图中的 run_sha256 绑定 JSON 对象的稳定 hash；state.run_sha256 绑定 revision 文件实际字节，二者用途不同。

整合前校验全部包、输入和目标；重入恢复接受目标为获准的 pre 或 post hash，其他内容拒绝。已达到 post hash 的目标不重复写。receipt 保存 intent_path/intent_hash/source_revision/outputs/integrated_at，用于校验幂等重放。未消费 intent 必须先完成或恢复，不能通过 cancel/pause/new events 隐藏部分文件写入。恢复不会自动回滚外部编辑或猜测缺失证据。

## 兼容、保留与边界

- 旧 active delivery 保持旧 coordinator 语义，不迁移、不补造 production_policy/TeamRun/确认记录。
- 新建交付默认 coordinator；同版本当前 delivery 可在 02 所列安全边界显式切换。切换不是跨版本迁移接口。
- run 失败时保留 revisions、intent、staging 与已接受证据；owner 按既有变更路径处理 canonical 内容，不删除证据掩盖失败。
- 沿用既有 artifact retention 与 host 隐私策略；本版本不引入自动压缩、归档、TTL、GC 或数据库回滚脚本。

## 信息缺口与追溯

- Blocker：无。真实宿主证据与正式发布演练已完成；中断/外部编辑恢复回归也已纳入自动化验证。
- Assumption：本地文件系统提供现有 state lock 和原子文件 replace 所依赖的语义；跨文件整合通过 intent 恢复，不宣称事务原子性。
- Nice-to-know：长期文件保留体量可后续评估，当前不扩大为清理服务。

FR-005/007/009/011/012、NFR-001..005/010 → TASK-005/006/009/012/015 → TC-008/009/012/022/024。
