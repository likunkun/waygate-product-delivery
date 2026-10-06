# Waygate Product Delivery 1.2.0 深度评估与业界对标

**评估基线**：仓库提交 `780a6d587d8ea8599afc950fa3d8cc653fdfcbd9`，版本 `1.2.0`，日期 2026-10-06。

**证据范围**：当前源码、测试、README、Open Spec、安装脚本、公开项目官方文档，以及 2026-10-06 的 GitHub API 快照。
**结论类型**：这是成熟度评估，不是代码审计，也不是对外市场份额预测。

## 执行摘要

Waygate Product Delivery 解决的是一个明确但尚未被主流编码 Agent 完整解决的问题：让 AI 辅助开发受一个可恢复、可审计、可拒绝绕过的产品交付流程约束。它把需求澄清、Open Spec、场景审查、UI/非 UI 契约、测试义务、实现移交、任务执行证据和正式闭包连接成一个本地状态机。

它最有价值的地方不在于“能不能让模型写出代码”，而在于把“为什么做、做了什么、谁确认过、哪些证据是真的、什么时候可以宣布完成”变成结构化事实。对于需要人机协作、审计追溯和失败恢复的 Codex 用户，这个设计明显高于普通 prompt、Markdown checklist 或单纯的多 Agent 并发脚本。

但它还不能称为业界最佳实践。当前版本更准确的定位是：**交付治理设计先进、运行时验证扎实、生产基础设施和生态成熟度不足的 Codex-native advanced prototype / early beta**。在“AI 交付证据控制面”这个窄领域，它属于第一梯队候选；放到整个 AI 软件工程平台市场，它还没有达到生产级头部水平。

综合评分如下。评分只表示当前仓库相对于公开同类实践的成熟度，不代表代码质量的绝对分数。

| 维度 | 评分 | 判断 |
| --- | ---: | --- |
| 方法论与交付治理设计 | 4.5/5 | 强。阶段边界、确认点、权威状态和闭包规则非常完整。 |
| 证据、哈希与 fail-closed 工程 | 4.0/5 | 强。比多数 SDD 工具更重视证据身份和不可绕过的终态。 |
| 多 Agent 生产编排 | 3.0/5 | 中上。契约和恢复机制完整，但实际执行能力依赖宿主。 |
| 安全隔离与权限边界 | 2.0/5 | 偏弱。`shared_fs` 是协议约束，不是 OS sandbox。 |
| 可观测性、成本和长期运营 | 1.5/5 | 偏弱。usage、质量、返工和长期 SLO 仍不可用或未形成平台能力。 |
| 发布工程与生态 | 1.5/5 | 偏弱。无仓库 CI、tag/release，插件元数据仍有占位 URL。 |
| **总体** | **3.0/5** | **先进原型 / 早期 Beta，不是行业生产基准。** |

## 1. 项目到底提供了什么

### 1.1 交付治理控制面

入口是 Codex 插件和严格 JSON 生命周期控制。插件默认休眠，只有显式调用 `start` 才进入交付模式；`status`、`inspect`、`pause`、`resume`、两阶段 `abandon` 和 `close` 都有明确的动作边界。未知字段、自然语言隐式写入和已退役的 `stop()` 会被拒绝。

新交付先经过 input-understanding confirmation。之后，流程要求当前 feature 的 Open Spec、场景矩阵、UI 原型或非 UI 行为契约、产品基线确认、planned E2E、coverage audit、测试评审和测试覆盖确认全部完成，才自动生成实现授权。用户正式确认只有两次：`product_baseline` 和 `test_coverage_plan`；其他节点由 runtime 根据事实自动推进。

这套顺序解决了几个常见问题：需求还没冻结就开始实现、原型修改后继续沿用旧确认、测试只写了名字却没有绑定用户旅程、实现完成后用聊天总结代替正式闭包。

### 1.2 Codex 执行适配层

Waygate 没有把自己的内部 `delivery_goal` 冒充宿主 Goal，而是把两者分开：

- delivery goal 管理当前交付的 TASK 队列、游标和停止条件；
- Codex Host Goal 负责跨 turn 的真实继续执行；
- handoff 后必须按 `get_goal -> create_goal -> get_goal` 进行激活；
- 后续 canonical 写入要求当前线程、已记录 owner、binding owner 和宿主 Goal `threadId` 一致；
- spawned reviewer 只能产生 review artifact，不能抢占或完成主交付 Goal。

这比“在 prompt 里告诉 Agent 继续做完”可靠得多，因为 Goal 身份、绑定代数、nonce、objective hash 和 transition journal 都参与了校验。它也明确承认宿主限制：没有真实 `get_goal`、真实 Agent 身份或真实浏览器证据时，runtime 不能凭空宣布成功。

### 1.3 证据与闭包验证层

权威状态位于 `.product-delivery/state.json`，权威交付证据位于按 `feature_slug/delivery_id` 隔离的目录。兼容视图不能取代 canonical artifact。关键状态和 artifact 通过 SHA-256、文件哈希、输入快照、review hash、implementation baseline hash 和 hash-linked transition journal 绑定。

UI 分支包含：

- clean product surface 与 review-only annotation 分离；
- 固定 schema 的 semantic snapshot、browser preflight 和截图/region hash；
- prototype design integrity；
- 按 surface/state/viewport/region/interaction 绑定的 TASK；
- production PNG、语义、关系、交互、geometry 和 visual loop 证据；
- 独立 `ui_conformance` review。

非 UI 分支不是把 UI 流程硬套到 API 或后台任务，而是使用 behavior contract，覆盖入口、输入输出、异常、恢复、权限、长任务、状态迁移和边界条件，并通过 `record_executed_behavior_evidence()` 记录真实 CLI/API/service 证据。

正式完成必须经过 canonical closure validator；目标项目自己的脚本、Open Spec 的文字结论、`progress.md` 或聊天摘要只能作为辅助证据。

### 1.4 团队生产编排层

1.2.0 引入六阶段生产流程：产品定义、架构/版本规划、Open Spec/产品表面、测试设计、实现执行、交付准备。生产角色卡共有十个核心职责和五个条件职责，工作包最多两个并行运行，成员在 staging copy 中修改，主线程核对真实文件和 hash 后整合。

TeamRun 有 revision、事件幂等、CAS、attempt、deadline、retry/revise 限额、merge intent、accepted artifact 和独立 review barrier。生产授权与 review 授权分离；生产结果不能直接放行 TASK、Host Goal 或 closure。

这是一个重要的边界设计：Waygate 负责“生产过程是否满足交付契约”，宿主负责真正 spawn Agent、维护 OS 权限、终止进程、提供身份和用量数据。README 也明确声明 `shared_fs` 不是 OS 级隔离。

## 2. 当前实现水平

### 2.1 代码与测试规模

- runtime 源码 35 个 Python 文件、约 29,207 行、753 个函数、31 个类；生成插件 runtime 与 `src` 同步复制。
- `workflow.py` 单文件约 7,411 行、161 个函数、约 992 个分支型节点，是最大的维护风险。
- 测试 63 个文件、约 24,159 行；完整 unittest discovery 已通过 725 项，耗时约 199.7 秒。
- `compileall` 通过；插件打包 smoke 通过。

测试数量和测试代码规模说明项目不是概念草图，至少有持续回归意识。测试覆盖了状态协议、确认策略、UI 原型完整性、任务队列、Host Goal 恢复、TeamRun、插件打包和多版本迁移。

但 725 项测试不能直接推导出生产可靠性。当前测试主要是本地 Python runtime、fixture 和协议回归，没有证明：多 provider 宿主的真实行为一致、多个真实 Agent 的身份和终止可信、共享文件系统无法越权、长期运行的成本和质量稳定、浏览器不可用时的实际恢复 SLO、或用户交付结果确实得到改善。

### 2.2 工程化成熟度

当前仓库没有发现 `.github/workflows`、`pyproject.toml`、`pytest.ini`、`tox.ini`、Ruff/mypy/Pyright 配置。项目有自己的打包、依赖检查和插件验证脚本，但尚未形成公开可见的 CI、类型检查、静态 lint、依赖安全扫描、跨 Python 版本矩阵、SBOM、签名发布或 release promotion 流程。

插件 manifest 的作者、主页、仓库、隐私政策和服务条款仍使用 `example.com` 占位 URL。这不影响本地测试，但会阻碍可信分发、企业审查和生态采纳。

GitHub API 在 2026-10-06 的公开快照显示：仓库 0 stars、0 releases、0 tags、0 workflows，贡献者列表只有一个账号。stars 不是质量指标，但这些信号说明项目仍处于个人/小范围验证阶段，而不是经过社区和发布工程验证的行业产品。

### 2.3 架构风险

**单体 workflow 风险。** `workflow.py` 同时承载生命周期、确认、审查、任务、Host Goal、恢复、实现基线和闭包写入。它有利于保持 canonical authority，但任何新 gate 都可能扩大回归面，schema 迁移和并发修复的认知成本很高。

**跨文件事务边界。** 文件锁、原子 replace 和 merge intent 能减少损坏，但它不是数据库事务。跨 `state.json`、delivery manifest、artifact、journal 和镜像之间的中断仍需要恢复协议；这套恢复是严谨的，但复杂度也随之转移给运维者。

**宿主真实性依赖。** runtime 能验证宿主返回的结构和绑定，但无法独立证明 Agent 真的按声明工作、进程被停止、浏览器使用真实后端或 token 用量没有遗漏。项目对此没有过度宣称，这是优点；但它也意味着产品价值的一部分不在自身可控范围内。

**安全边界不足。** role card 的 `permissions` 和 `allowed_write_paths` 是契约和接纳检查。它们不是容器、VM、seccomp、网络策略或 OS ACL。对于不可信 Agent、恶意代码仓库或企业多租户场景，当前保护等级不够。

## 3. 业界相似项目

以下项目分成两组：前五个是直接的 spec/交付治理竞争面；后五个是执行和编排基础设施，功能相邻但不是同一产品类别。

### 3.1 直接对标

| 项目 | 官方定位与关键能力 | Waygate 相对优势 | Waygate 相对劣势 |
| --- | --- | --- | --- |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | 轻量 artifact-guided SDD；proposal/spec/design/tasks；`explore → propose → apply → archive`；支持 brownfield、cross-repo stores、30+ 工具。 | canonical 状态、用户确认、review artifact、UI/non-UI 分支、执行证据和 closure 更严格。 | 更重、更依赖 Codex，迭代自由度和跨工具普及度更弱；OpenSpec 社区和发布能力远强于 Waygate。 |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | constitution；`specify → plan → tasks → implement → converge`；独立 bug-fix/idea-assessment 流程；扩展、preset、bundle 和多 Agent 集成。 | 对最终闭包、证据身份、Host Goal ownership、UI prototype integrity 的约束更深入。 | Spec Kit 有官方维护、广泛集成、CI、release 和生态；Waygate 缺少通用化和社区验证。 |
| [Spec Kitty](https://github.com/spec-kitty/spec-kitty) | repo-native mission；work-package lanes；Git worktree 隔离；`next → review → accept → merge`；retrospective；支持 Claude/Codex/Cursor/Gemini/Copilot 等。 | 产品基线、E2E 义务、UI 语义/截图证据、canonical closure 和 fail-closed 恢复更细。 | Spec Kitty 在多 Agent 工作包、真实 worktree 隔离、跨 harness 和治理命令上更完整，是最接近的公开 peer。 |
| [Conductor](https://github.com/gemini-cli-extensions/conductor) | `Context → Spec & Plan → Implement`；项目上下文、tracks、review、Git-aware revert；兼容多个 Agent 插件宿主。 | Waygate 的状态与证据权威更严格，终态保护更强。 | Conductor 更易上手，UX 更轻，回滚和 track 模型更直接；Waygate 的 ceremony 和学习成本明显更高。 |
| [AWS Kiro Specs](https://kiro.dev/docs/specs/) | IDE 原生 structured specs、实现计划跟踪、hooks、从 prototype 到 production。 | 本地 first、Codex 插件化、跨宿主证据协议和闭包 authority 更开放。 | Kiro 拥有完整 IDE、交互界面和内建执行体验；Waygate 缺少产品化 UI，也没有 IDE 级上下文整合。 |

### 3.2 相邻基础设施

| 项目 | 强项 | Waygate 的位置 |
| --- | --- | --- |
| [Claude Code subagents/hooks](https://code.claude.com/docs/en/sub-agents) / [hooks](https://code.claude.com/docs/en/hooks) | 每个 subagent 独立 context、工具/权限/model 控制、可选 worktree isolation；hooks 可阻止、放行、异步执行或使用 agent 验证。 | Waygate 可以把这些宿主能力组织成产品交付流程，但不能替代它们提供执行隔离和通用 hook runtime。 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | durable execution、human-in-the-loop、memory、tracing、生产部署。 | Waygate 是面向软件交付的 policy/evidence layer；LangGraph 是更通用的长运行 Agent runtime。 |
| [OpenHands Agent Canvas](https://github.com/OpenHands/OpenHands) | self-hosted control center、多 Agent backend、Docker/VM/cloud、GitHub/Slack/Linear/Datadog 等自动化。 | Waygate 在交付契约和闭包更强，但没有 Agent Server、云端运行、调度、远程沙箱和集成平台。 |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | 以 SWE-bench 等结果衡量 Agent 修复真实仓库问题，强调 benchmark 和执行效果。 | Waygate 解决“是否按交付意图完成”而非“单个 issue 修复率”；当前没有公开 benchmark 证明交付质量收益。 |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | agents、handoffs、guardrails、sandbox agents、sessions、tracing、human-in-the-loop。 | 可作为 Waygate 未来 provider/runtime adapter 的基础，但自身不是产品交付状态机。 |

### 3.3 业界位置

Waygate 的直接竞争集不是 OpenHands 或 LangGraph，而是 OpenSpec、Spec Kit、Spec Kitty、Conductor、Kiro 这类“spec/任务/Agent 工作流”。其中：

- OpenSpec 和 Spec Kit 代表高采用、低到中等治理重量的 SDD 工具；
- Spec Kitty 代表更接近软件工厂的 repo-native 多 Agent 治理；
- Conductor 代表插件化、低摩擦、面向开发者日常使用的流程；
- Kiro 代表 IDE 内建体验；
- Waygate 代表证据优先、fail-closed、以闭包可信度为中心的本地控制面。

它的差异化成立，但市场认知尚未成立：公开采用、release cadence、外部贡献者、CI 和用户结果数据都还不足。

## 4. 优点

### 4.1 把“完成”从聊天语义升级成可验证终态

多数 Agent 工作流的完成条件是模型说“做完了”、测试命令返回 0，或 PR 被合并。Waygate 把 completion 拆成 feature closure、delivery goal、executed evidence、review、Host Goal completion 和 canonical validator，任何一层不满足都不能关闭。

这是对 AI 工作最关键的控制点，因为上下文压缩、任务中断和 Agent 自我报告都会制造“看起来完成”的假象。

### 4.2 证据身份设计明显领先普通 SDD 工具

Open Spec 或任务清单只能说明“应该做什么”；Waygate 进一步绑定输入 snapshot、prototype bundle、截图、semantic snapshot、region、execution segment、review hash 和 journal hash。artifact 不是附件，而是状态机的一部分。

### 4.3 UI 与非 UI 分支设计合理

很多 AI 开发流程默认一切都是网页：有截图就算验证，没截图就退化成模糊文字。Waygate 为 API、CLI、service 和后台任务提供行为契约和 CLI/API 证据，避免 UI 证据模型污染非 UI 项目。

### 4.4 对权限和权威边界保持克制

项目明确规定：生产者不能写 canonical state，reviewer 不能成为 coordinator，role card 不是 OS sandbox，usage 不可用时写 `unavailable`，并行执行不代表完成。能够主动声明“不证明什么”，比宣传自动化覆盖率更可靠。

### 4.5 恢复和迁移思路成熟

Host Goal checkpoint recovery、owner transfer、stale launch package、runtime receipt recovery、orphaned blocked binding 等处理说明作者确实遇到过真实状态漂移和恢复死锁，而不是只设计 happy path。

## 5. 缺点与实际风险

### 5.1 流程重量可能超过多数团队的支付意愿

一个小功能要经过输入理解、Open Spec、场景矩阵、设计完整性、产品基线、planned E2E、覆盖审查、测试覆盖确认、Goal handoff、TASK evidence、实现审查和 closure。对于高风险产品这是合理的；对于日常 bug、小型内部工具或一次性脚本，成本可能超过风险本身。

项目目前更像“严格交付模式”，还没有成熟的风险分级策略：哪些项目可以走轻量 profile、哪些 gate 可以合并、何时使用抽样而不破坏闭包权威，仍需要明确的 policy-as-code。

### 5.2 它管理宿主，但没有提供宿主

TeamRun 可以准备任务、接受事件、校验 staging 和合并结果，但真实 Agent 的 spawn、停止、身份、权限、模型、token、浏览器和外部系统连接仍由 Codex/宿主负责。因而 Waygate 是 control plane，不是完整 software factory。

这也解释了为什么它在设计上比很多 SDD 工具严谨，却在生产能力上落后于 OpenHands、LangGraph 或 Claude Code 的宿主原语。

### 5.3 shared filesystem 不足以支撑不可信执行

当前团队生产适合可信宿主和同一工作区内的协作，不适合多租户、第三方 Agent、恶意仓库或需要合规隔离的企业环境。要达到头部水平，需要真正的 sandbox provider、网络策略、secret redaction、权限审计和可证明的 workspace boundary。

### 5.4 复杂度集中在单个 workflow 模块

7,411 行的 `workflow.py` 把 facade、状态迁移、策略判断和许多异常恢复集中在一处。测试可以防止当前回归，但难以保证未来贡献者理解所有 gate 依赖。随着版本继续增加，schema、迁移和恢复 bug 的风险会按非线性增长。

### 5.5 缺少生产运营证据

1.2.0 的 release exercise 能证明流程可运行，但不是长期运营数据。项目还没有公开：

- gate bypass rate、false block rate、rework rate；
- 每种 gate 的 p50/p95 时间；
- 每个 delivery 的 token/cost；
- coordinator/team 相对于单 Agent 的质量差异；
- 恢复成功率和状态漂移率；
- 用户从 idea 到 closure 的时间收益。

没有这些数据，就不能证明多 Agent 和更多门禁带来的净收益，最多只能证明流程设计自洽。

### 5.6 分发可信度不足

无公开 release/tag、无 CI、无安全扫描、无签名归档、无真实主页和隐私政策 URL，会让企业用户无法把它当作可审查的基础设施依赖。对于一个强调证据可信度的产品，这是与自身定位直接冲突的短板。

## 6. 是否是最佳实践

答案取决于比较对象。

### 在“证据优先的 Codex 交付治理”这个窄领域：接近最佳实践

它具备很多值得复用的模式：

1. artifact/state 优先于聊天上下文；
2. 显式用户确认和 nonce/hash 绑定；
3. deterministic gate 与 subjective review 分离；
4. 生产、评审、整合和正式 closure 分离；
5. UI 与 non-UI 使用不同证据契约；
6. fail-closed、幂等、CAS、transition journal 和恢复入口；
7. 对 host 能力和隔离能力不夸大。

这些设计在公开 SDD 项目中并不常见，尤其是 UI 设计完整性、执行证据、Host Goal ownership 和终态保护的组合。

### 在“通用 AI 软件工程平台”这个宽领域：不是最佳实践

它缺少头部平台通常具备的：

- provider-neutral execution and routing；
- 真正 sandboxed workspace 和网络/secret policy；
- 远程或云端长运行；
- OpenTelemetry/trace/cost/quality dashboard；
- GitHub/Linear/Jira/CI/CD/issue/PR 集成；
- 跨团队 RBAC、租户、审计和合规控制；
- 持续 CI、签名发布、安全供应链和生态插件；
- 公开 benchmark 和真实用户结果。

所以“Waygate 的方法论部分达到最佳实践”可以成立；“Waygate 现在就是行业最佳 AI 交付产品”不成立。

## 7. 距离业界顶尖水平还差什么

### P0：从先进原型到可信生产组件（0–3 个月）

| 缺口 | 目标验收 |
| --- | --- |
| CI 与静态质量 | GitHub Actions 覆盖 Python 3.11–3.13；Ruff、mypy/Pyright、pytest/unittest、coverage、依赖扫描全部作为 required check。 |
| 发布可信度 | 清理 `example.com`；建立真实 homepage/repository/privacy/security 页面；发布 tag、release notes、可复现包、SBOM 和签名校验。 |
| 真实宿主 E2E | 建立最小 Codex/Agent host adapter contract test，覆盖 start→handoff→goal→TASK→evidence→closure、暂停、恢复、超时、重复事件和外部修改。 |
| 安全边界 | 记录威胁模型；提供 Docker/VM/remote sandbox provider；明确 workspace、网络、secret 和 artifact 写权限，不能只依赖 shared_fs。 |
| 可观测性基线 | 每次 run 记录 elapsed time、retry/rework、provider/model、token/cost（不可得时明确 unavailable）、gate latency 和 blocker 分类。 |
| workflow 拆分 | 将 facade、transition policy、recovery、host adapter、closure 和 schema migration 分离；给每个模块定义稳定接口和迁移测试。 |

### P1：从单一 Codex 插件到可扩展交付平台（3–6 个月）

| 缺口 | 目标验收 |
| --- | --- |
| 执行适配层 | 抽象 Codex Host Goal、Claude subagent、OpenAI Agents、LangGraph、OpenHands 等 provider；Waygate 只依赖统一 run/event/evidence contract。 |
| 事件与存储 | 用 SQLite 或 append-only event store 保存 canonical events，文件 artifact 保留为内容层；提供 schema migration、replay、compaction 和 corruption repair。 |
| 外部系统集成 | GitHub issue/PR、Linear/Jira、CI、browser runner、artifact store、Slack/通知通过显式 adapter 接入，不直接耦合核心 workflow。 |
| 公共 conformance suite | 发布 fixture protocol、host adapter contract、malicious/late/duplicate event cases、sandbox tests 和 closure conformance suite。 |
| 经验数据 | 至少积累 30–50 个真实 delivery，报告单 Agent/coordinator/team 的时间、返工、成本、阻塞和 closure 失败分布。 |
| 风险分级 | 提供 low/standard/high assurance profiles；每个 profile 通过 policy-as-code 明确 gate、采样、豁免和审批边界。 |

### P2：达到头部平台能力（6–12 个月）

- 提供团队/组织级 Web 控制台、RBAC、审计检索、delivery search、趋势图和 evidence diff；
- 支持多项目、跨仓库 feature、共享 requirements store 和版本依赖图；
- 对 Agent 质量、成本和 gate 策略做持续评估，形成公开 benchmark；
- 提供企业合规能力：数据保留、密钥隔离、供应链签名、策略审批、网络出口控制和审计导出；
- 在保持 fail-closed 的同时，通过历史数据自动建议最小必要 gate，降低不必要的流程负担。

## 8. 推荐产品定位

建议对外把 Waygate 定位为：

> **Evidence-first delivery control plane for Codex-native AI software work**
> 面向需要可追溯范围、结构化确认、真实执行证据和可信闭包的 AI 软件交付团队。

这个定位能放大它真正的差异化：交付可信度、恢复能力和证据纪律。暂时不要把它描述成：

- 通用 autonomous coding platform；
- 安全 sandbox；
- 多 Agent 云端运行平台；
- 已经证明能提升交付质量或降低成本的生产工厂。

## 9. 结论

Waygate 的核心创新不是又一个 prompt workflow，而是把 AI 交付过程做成了一个带证据身份、用户确认、权限边界、恢复和终态验证的本地控制面。这个设计在公开同类项目中很有竞争力，尤其适合高风险 UI、跨阶段需求和需要审计的 Codex 项目。

它目前的瓶颈不在“还缺几个 gate”，而在产品化基础：真实宿主抽象、sandbox、CI/release、安全供应链、可观测性、跨工具集成和长期实证。继续增加流程规则会进一步提高复杂度；下一阶段应优先把已有规则放进可信运行基础设施，并用真实交付数据证明这些规则的净收益。

**最终判断：** Waygate 处于“治理方法论领先、工程实现扎实、生产运营和生态尚未成熟”的高级原型阶段。它可以作为严肃团队的内部交付控制面试用，但还不应被称为业界通用最佳实践或企业级头部平台。

## 10. 证据与来源

### 仓库内证据

- [README.md](../../README.md)：产品定位、功能边界、V1.2 团队生产、Host Goal 和架构索引。
- [control.py](../../src/product_delivery_agent/control.py)：严格 JSON 控制、未知字段拒绝和生命周期动作。
- [workflow.py](../../src/product_delivery_agent/workflow.py)：canonical workflow facade、确认、handoff、Host Goal、TASK、恢复和 closure 写入。
- [artifact_protocol.py](../../src/product_delivery_agent/artifact_protocol.py)：状态持久化、锁、artifact 根和 lifecycle hash。
- [gatekeeper.py](../../src/product_delivery_agent/gatekeeper.py)：预 handoff、预 closure、hash 和 blocker 校验。
- [team_orchestration.py](../../src/product_delivery_agent/team_orchestration.py)：TeamRun、事件、CAS、整合和 finalize。
- [v1.2 specification](../open-spec/v1.2-team-production-orchestration/02-specification.md)：团队生产契约和明确限制。
- [release exercise](../open-spec/v1.2-team-production-orchestration/10-release-exercise-report.md)：宿主演练、closure 和 usage unavailable 记录。
- [installation guide](../operations/waygate-product-delivery-installation.md)：打包、插件验证和安装流程。

### 业界一手资料

- [OpenSpec README](https://github.com/Fission-AI/OpenSpec)
- [GitHub Spec Kit README](https://github.com/github/spec-kit)
- [Spec Kitty README](https://github.com/spec-kitty/spec-kitty)
- [Conductor README](https://github.com/gemini-cli-extensions/conductor)
- [Kiro Specs](https://kiro.dev/docs/specs/)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents) 与 [hooks](https://code.claude.com/docs/en/hooks)
- [LangGraph README](https://github.com/langchain-ai/langgraph)
- [OpenHands Agent Canvas README](https://github.com/OpenHands/OpenHands)
- [SWE-agent README](https://github.com/SWE-agent/SWE-agent)
- [OpenAI Agents SDK README](https://github.com/openai/openai-agents-python)

GitHub adoption/release/workflow 数字是 2026-10-06 通过公开 GitHub API 读取的快照，不能替代功能和质量评估。
