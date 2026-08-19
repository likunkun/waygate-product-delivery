# Waygate Product Delivery

[![Codex plugin](https://img.shields.io/badge/Codex-plugin-2563eb)](plugins/waygate-product-delivery)
[![Version](https://img.shields.io/badge/version-1.0.32-0f766e)](plugins/waygate-product-delivery/.codex-plugin/plugin.json)
[![Tests](https://img.shields.io/badge/tests-full%20suite%20passing-15803d)](#验证)
[![License: MIT](https://img.shields.io/badge/license-MIT-111827)](LICENSE)
[![English](https://img.shields.io/badge/docs-English-374151)](README.md)

Waygate Product Delivery 是一个面向 Codex 的产品交付插件，用来把一个产品想法推进到产品定义、Open Spec、场景评审、UI 或非 UI 门禁、实现移交，以及正式闭包证据。简写命令：`start <slug> [multi-agent|role-play]`、`status`、`pause`、`resume`、`close`、`abandon`、`inspect`。

它适合希望“AI 可以写代码，但不能绕过交付流程”的团队：每个关键阶段都要有本地 artifact、用户确认、评审记录、测试义务和 canonical closure validator。

> English version: [README.md](README.md)

## 为什么需要它

长流程 AI 交付经常会在这些地方出问题：

- 上下文压缩后丢失流程状态；
- HTML 原型生成了，但用户反馈后的第二版没有重新确认；
- 测试做了，但没有追溯到用户旅程；
- 实现还没完成评审和确认就开始写代码；
- 最后用聊天总结或目标项目自己的脚本声称完成。

Waygate Product Delivery 把这些失败模式变成明确的门禁。

## 它提供什么

| 能力 | 结果 |
| --- | --- |
| 仅显式参数控制 | 生命周期变更必须显式调用 `$waygate-product-delivery` 并提交严格 JSON；普通聊天不会修改交付状态。 |
| 按 delivery 隔离证据 | `.product-delivery/state.json` 可跨上下文恢复，权威 artifacts 存储在 `deliveries/<feature_slug>/<delivery_id>/`。 |
| 强制技能门禁 | 按阶段检查 Product Delivery、Open Spec、planning files、UI/UX、浏览器测试和闭包技能。 |
| 分层产品确认 | 先确认需求范围和 UI 原型或非 UI 行为契约，再生成详细测试设计。 |
| 原型设计完整性 | 纯净产品表面必须继承全局产品上下文，评审标注只能放在独立评审页。 |
| 原型绑定 TASK | 每个可见 UI TASK 都绑定冻结原型的精确切片，并在完成前通过逐任务语义与视觉一致性检查。 |
| 非 UI 行为契约 | API、CLI、服务、后台任务用行为契约替代 HTML 原型。 |
| 多 Agent 评审 artifact | 场景和测试覆盖评审必须留下可见 artifact，不能只在聊天里说做过。 |
| Goal 驱动实现 | 实现阶段必须按 TASK 队列推进，不能无阻塞就中途停下。 |
| canonical 闭包权威 | 最终完成由 Product Delivery validator 判定，目标项目脚本只能作为辅助证据。 |

## 快速开始

克隆仓库：

```bash
git clone https://github.com/likunkun/waygate-product-delivery.git
cd waygate-product-delivery
```

安装或更新本地 Codex 插件：

```bash
bash scripts/install_waygate_product_delivery.sh
```

安装后新开一个 Codex thread，然后使用简写命令：

```text
$waygate-product-delivery start v0-5-5-flow-preview multi-agent
```

或使用完整 JSON 格式：

```text
$waygate-product-delivery {"schema_version":"v1","action":"start","feature_slug":"v0-5-5-flow-preview","start_mode":"resume_or_create","review_mode_if_created":"spawned_subagents_authorized"}
```

**可用简写命令：**

- `start <slug>` — 启动，进入评审模式选择
- `start <slug> multi-agent` — 启动，多 Agent 模式（强证据）
- `start <slug> role-play` — 启动，角色扮演模拟（弱证据）
- `status` — 查看当前交付状态
- `pause` — 暂停当前交付
- `resume` — 恢复暂停的交付
- `close` — 关闭已完成的交付
- `abandon` — 放弃当前交付（两步操作）
- `inspect` — 检查启动请求


新建 delivery 时可使用 `spawned_subagents_authorized` 授权结构化 subagent 评审；只有明确接受降级证据时才使用 `role_simulation_allowed`。同一未完成 feature 再次使用 `resume_or_create` 会恢复原 `delivery_id`。

## 安装

可安装插件位于：

```text
plugins/waygate-product-delivery/
```

repo-local marketplace 配置位于：

```text
.agents/plugins/marketplace.json
```

自动安装：

```bash
bash scripts/install_waygate_product_delivery.sh
```

安装脚本会检查旧 `product-delivery-agent` 的 config、cache 和注册信息，通过 Codex 删除旧插件；最后只有 `waygate-product-delivery@repo-local` 是启用的产品交付插件时才会成功。

手动安装：

```bash
python3 scripts/package_waygate_product_delivery.py
python3 <plugin-creator>/scripts/validate_plugin.py plugins/waygate-product-delivery
python3 <plugin-creator>/scripts/update_plugin_cachebuster.py plugins/waygate-product-delivery
codex plugin add waygate-product-delivery@repo-local
```

构建分发包：

```bash
python3 scripts/package_waygate_product_delivery.py
```

输出：

```text
dist/waygate-product-delivery-1.0.32.tar.gz
```

## Codex 使用方式

| JSON action | 作用 |
| --- | --- |
| `inspect` / `status` | 只读查看启动判定、当前阶段、阻塞项、迁移状态和 artifact 身份。 |
| `start` | 按 `resume_or_create`、`resume_only` 或 `create_only` 创建或恢复 delivery。 |
| `pause` / `resume` | 临时关闭或恢复主动介入，保留原 `delivery_id`、确认和证据。 |
| `prepare_abandon` / `abandon` | 使用绑定当前 state 且会过期的两阶段 token 永久废弃 delivery。 |
| `close` | 仅在 canonical closure、feature closure 和 delivery goal 全部通过后关闭。 |

`stop()` 已退役；非 JSON 请求和未知字段不会触发任何状态变更。

进入实现前必须完成：

1. 当前 feature 的 Open Spec、场景矩阵以及 UI 原型或非 UI 行为契约草稿；
2. UI 项目先通过当前 `prototype_design_integrity` bundle，再通过多 Agent 产品/场景评审；
3. 用户确认 `product_baseline`，只确认需求范围和纯净产品表面；
4. 基线确认后生成 planned E2E、coverage audit 和详细测试设计；
5. 多 Agent test/test_coverage 评审通过；
6. 用户确认 `test_coverage_plan`；
7. Runtime 自动生成 implementation launch authorization。

## 工作流

```mermaid
flowchart LR
    A[启动] --> B[产品蓝图]
    B --> C[Open Spec]
    C --> D[场景矩阵和产品表面草稿]
    D --> V[原型设计完整性门禁]
    V --> E[多 Agent 产品和场景评审]
    E --> F[基于纯净原型确认 product_baseline]
    F --> G[planned E2E 和覆盖审计]
    G --> H[多 Agent 测试和覆盖评审]
    H --> I[确认 test_coverage_plan]
    I --> P[Runtime 自动实现授权]
    P --> Q[Codex Goal 移交]
    Q --> R[TASK 队列实现]
    R --> S[执行证据]
    S --> T[多 Agent 测试实现评审]
    T --> U[canonical 闭包验证]
```

核心规则：artifact 和 state 是事实源，聊天总结不是。

### 原型门禁与评审分工

UI 原型生成后，先调用 `record_ui_prototype_design_bundle()`，再进入多 Agent 产品/场景评审。确定性门禁会重建固定 schema 的 semantic snapshot 与 browser-preflight probe artifact，逐个关键 state/viewport 校验 snapshot、截图和 region identity hash，不接受调用方自报 pass flag。全局框架、导航、视觉语言、信息密度、组件体系和响应式行为六个维度都必须绑定结构化、带 hash 的设计证据 artifact；产品 `clean_surface` 与外部 `review_annotation_set` 必须严格分离。

门禁验证客观事实，多 Agent 判断设计质量。评审负责判断基线是否有代表性、局部精美是否与全局产品协调、例外是否合理；不能覆盖门禁失败，也不能用空 findings 代替完整正向评审。

`product_baseline` 只展示纯净原型和纯净截图。仅评审标注变化，只使绑定旧标注的内部 scenario review stale，不影响两次用户确认、测试计划或实现授权；产品页面或全局上下文变化仍触发完整下游失效。已确认基线的 v1.0.22 active delivery 暂时 grandfathered，直到再次修改原型或重开产品基线。用户确认仍严格只有两次：`product_baseline` 和 `test_coverage_plan`；closure schema 保持 `v0.11`。

### Host Goal Checkpoint 恢复

handoff 后，Host Goal 激活必须遵循精确的 `get_goal -> create_goal -> get_goal` 协议。如果后续合法 canonical transition 使尚未 active 的 activation checkpoint 过期，调用 `recover_stale_host_goal_checkpoint(checkpoint_id)`。runtime 会验证当前 delivery 身份、授权、binding generation/nonce、objective hash 和 transition journal hash chain，再归档旧 checkpoint 并签发新的 `inspect_before_activation` checkpoint。

恢复会保留 delivery、artifact、review、TASK 状态和全部旧 journal event。禁止手改 `.product-delivery/state.json`、重新启动当前 delivery 或重放已 supersede 的 checkpoint。active Waygate delivery 必须使用当前安装的 `waygate-product-delivery` runtime，不得混用旧 `product-delivery-agent@1.0.8` runtime 写入。

### Coordinator 独占 Host Goal

每个 delivery 启动时都会从 `CODEX_THREAD_ID` 冻结用户可见顶层 Codex 主线程作为 coordinator。Host Goal 激活、对账、观察、完成以及 handoff 后的 canonical 写入，必须同时匹配当前线程、已记录 owner、binding owner 和宿主 Goal 的 `threadId`。评审 subagent 只能生成 review artifact，禁止激活、恢复、接管或完成 delivery Host Goal。

旧 active state 缺少 owner metadata 时迁移为 `legacy_unverified`，runtime 不会把旧 Goal binding 线程推断成 coordinator。必须新建一个没有 active/blocked Goal 的用户可见顶层线程，调用 `prepare_host_goal_owner_claim("恢复交付主线程，接管当前 Host Goal")`，执行返回要求的 `get_goal`，再调用 `record_host_goal_owner_claim_observation()`。只有 missing 或 complete Goal 允许 transfer；active 或 blocked Goal 必须 fail closed。成功后旧 binding 和 pending checkpoint 会完整归档，journal 只追加 `host_goal_owner_transferred`，然后以新 generation、nonce 和 objective 重新执行 `get_goal -> create_goal -> get_goal`，不会改写原 delivery 证据或旧 journal event。owner-claim checkpoint 若因合法 transition 过期，必须调用 `recover_stale_host_goal_owner_claim(checkpoint_id)`；runtime 会归档旧 claim 并追加 `host_goal_owner_claim_superseded`，不会让恢复永久卡死。

## 架构

```text
waygate-product-delivery
|-- src/product_delivery_agent/          runtime 库
|-- plugins/waygate-product-delivery/    生成的 Codex 插件包
|-- docs/open-spec/                      版本化 Open Spec 文档
|-- docs/operations/                     安装、监控、加固文档
|-- scripts/                             打包和安装自动化
|-- tests/                               runtime 与 packaging 回归测试
`-- .agents/plugins/marketplace.json     repo-local Codex marketplace
```

核心模块：

| 模块 | 职责 |
| --- | --- |
| `workflow.py` | Product Delivery 生命周期 API。 |
| `artifact_protocol.py` | 本地状态和 artifact 持久化。 |
| `startup_guard.py` | planning files、Open Spec、项目类型门禁。 |
| `prototype_design.py` | 纯净表面、产品上下文、标注分离和设计 bundle 校验。 |
| `gatekeeper.py` | handoff、implementation、closure 的 fail-closed invariants。 |
| `delivery_goal.py` | TASK 队列、任务游标、停止门禁。 |
| `host_goal.py` | 经验证的 Codex Host Goal 激活、对账、人工等待与完成。 |
| `transition_journal.py` | hash-linked 关键状态迁移日志。 |
| `finalization.py` | canonical Product Delivery closure validator。 |
| `plugin_packaging.py` | Codex 插件生成和分发打包。 |

## 验证

完整单测：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

编译 runtime：

```bash
python3 -m py_compile src/product_delivery_agent/*.py
```

验证生成的插件：

```bash
python3 <plugin-creator>/scripts/validate_plugin.py plugins/waygate-product-delivery
```

在没有源码 `PYTHONPATH` 的情况下 smoke-test 安装态 validator：

```bash
env -u PYTHONPATH PYTHONNOUSERSITE=1 \
  python3 <codex-home>/plugins/cache/repo-local/waygate-product-delivery/<installed-version>/scripts/validate-closure-artifact.py --help
```

当前基线：

```text
完整单测套件通过
Plugin validation passed
Packaged validator 可在无源码 PYTHONPATH 下运行
```

## 文档

| 文档 | 用途 |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | 发布账本和 1.0 之后的精简版本方向。 |
| [ROADMAP.md](ROADMAP.md) | 版本路线和能力规划。 |
| [docs/README.md](docs/README.md) | 文档索引。 |
| [docs/open-spec/README.md](docs/open-spec/README.md) | V0.1 到 V1.0 的 Open Spec 索引。 |
| [docs/operations/waygate-product-delivery-installation.md](docs/operations/waygate-product-delivery-installation.md) | 构建、打包、安装和 smoke test。 |
| [docs/operations/product-delivery-agent-hardening-plan.md](docs/operations/product-delivery-agent-hardening-plan.md) | 基于交付监控样本沉淀的加固计划。 |

## 边界

Waygate Product Delivery 不是 Waygate controller。

它会：

- 打包 Codex workflow 插件；
- 定义产品交付门禁；
- 持久化本地 Product Delivery 状态和 artifacts；
- 验证闭包证据。

它不会：

- 修改 Waygate controller state；
- 替代目标项目自己的测试；
- 用聊天总结声明生产就绪；
- 让目标项目脚本成为最终闭包权威。

内部 Python import path 仍是 `product_delivery_agent`；外部 Codex 插件名是 `waygate-product-delivery`。

## 贡献

请按插件本身要求的纪律贡献：

1. 行为变化先通过 Open Spec 或聚焦 issue 描述清楚。
2. 修改 runtime 行为前先补测试。
3. 运行[验证](#验证)里的命令。
4. runtime 或模板变化后重新生成插件包。
5. 不要手写终态绕过 closure validation。

## 许可证

MIT。见 [LICENSE](LICENSE)。
