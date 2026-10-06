# Product Delivery Agent Plugin Roadmap And Version Plan

This roadmap describes the planned evolution of the Waygate Product Delivery Agent as a Codex-native agent plugin. Version labels are planning labels, not release promises.

## Roadmap

Product shape: Codex-native Product Delivery Agent Plugin.

The plugin is dormant by default. It only enters product delivery mode after the user explicitly starts it for a project.

Core route:

1. Turn the methodology into an executable roadmap.
2. Define the local artifact and state protocol.
3. Validate the main workflow with a repo or local skill.
4. Add hooks to preserve continuity across compaction, resume, and long sessions.
5. Package the stable workflow as a Codex plugin.

Key rules:

- V1 supports both UI and non-UI projects.
- Only UI projects enable a local 1:1 HTML prototype gate.
- Non-UI projects use a behavior contract confirmation gate instead of an HTML prototype.
- Every project must pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Specialized workflow skills must be assigned to relevant stages; generic Skill routing and code refinement remain Codex-native concerns.
- V1 produces roadmap and version-planning artifacts first; implementation design, detailed interfaces, and runtime automation come later.

## Version Plan

### V0.1 - Roadmap And Product Definition

Goal: define the product shape, capability boundary, version route, and skill allocation.

Scope:

- Define the product as a Codex-native Agent Plugin.
- Define an explicit project-level `start` and `stop` switch.
- Define the UI and non-UI project branches.
- Map the main flow from product idea to Codex Goal handoff.
- Map Waygate baseline skills to workflow stages.
- Produce roadmap and version planning only; do not enter implementation design.

### V0.2 - Artifact And State Protocol

Goal: define the local state and artifact protocol the plugin will use.

Scope:

- Define the `.product-delivery/` workspace.
- Define `state.json` responsibilities for stage, project type, confirmation points, and artifact paths.
- Define the core document templates:
  - product brief
  - version scope
  - UI prototype review
  - non-UI behavior contract
  - test coverage audit
  - handoff
- Define that state files take precedence over chat context.

### V0.3 - Local Skill Workflow Prototype

Goal: validate the product delivery workflow with a repo or local skill before packaging a plugin.

Scope:

- Support `start`, `status`, `pause`, `resume`, and `stop`.
- Guide the user through product blueprint, version scope, and project type selection.
- Route UI projects into prototype confirmation.
- Route non-UI projects into behavior contract confirmation.
- Generate a test coverage audit and Codex Goal handoff draft.

### V0.4 - Skill Allocation And Review Gates

Goal: explicitly include the Waygate README recommended skills in the workflow.

Skill allocation:

| Stage | Skills |
| --- | --- |
| Long-running work and recovery | `planning-with-files` |
| Product blueprint and scope shaping | `superpowers:brainstorming` |
| Version plan and implementation plan | `superpowers:writing-plans` |
| Test coverage audit | `test-strategy` or `testing-strategy` |
| UI, Web, and prototype work | `ui-ux-pro-max` |
| Browser-visible verification | `webapp-testing` |
| Pre-handoff evidence expectations | `superpowers:verification-before-completion` |
| Later implementation execution | `superpowers:test-driven-development`, `superpowers:executing-plans`, or `superpowers:subagent-driven-development` |
| Later rework and failure analysis | `superpowers:systematic-debugging` |
| Later review loop | `superpowers:requesting-code-review` and `superpowers:receiving-code-review` |
| Document-specific work | `pdf`, `docx`, and `pptx` only when the corresponding file type is involved |

### V0.5 - Hooks And Recovery Guardrails

Goal: preserve workflow continuity across compaction, resume, and long sessions.

Scope:

- Inject the current state when an active project starts or resumes.
- Add current stage context before user prompts in active projects.
- Check that state is written before compaction.
- Check missing artifacts or confirmation records before stopping.
- Keep hooks silent for inactive projects.

### V0.6 - UI Prototype Gate

Goal: provide local 1:1 HTML prototype confirmation for UI projects.

Applies only when `project_type = ui`.

Scope:

- Generate or guide creation of a local HTML prototype.
- Cover key pages, states, and user journeys.
- Require user confirmation before test coverage audit.
- Carry prototype limitations into the handoff.

### V0.7 - Non-UI Behavior Contract Gate

Goal: provide a behavior confirmation gate for non-UI projects.

Applies only when `project_type = non_ui`.

Scope:

- Define API, CLI, service, or background job entry points.
- Define input/output contracts, error paths, state transitions, and boundaries.
- Require user confirmation before test coverage audit.

### V0.8 - Test Coverage Audit

Goal: confirm test obligations before implementation handoff.

Scope:

- Map user stories, journeys, failure paths, acceptance criteria, and planned tests.
- For UI projects, check browser E2E coverage or explicit exemptions.
- For non-UI projects, check API, service, or CLI E2E coverage or explicit exemptions.
- Block handoff when critical coverage is missing and not exempted.

### V0.9 - Codex Goal Handoff

Goal: generate a frozen version package that can be handed to implementation Codex.

Scope:

- Generate the handoff document.
- Generate a Codex Goal prompt.
- Include scope, non-goals, confirmation results, test obligations, verification commands, and prohibited work.
- Require scope changes after freeze to return to version scope confirmation.

### V1.0 - Codex Plugin Packaging

Goal: package the stable workflow as an installable Codex plugin.

Scope:

- Package the skill, hooks, templates, and validation scripts.
- Provide repo marketplace configuration.
- Keep the plugin dormant after installation.
- Enter active mode only after `start`.
- Exit intervention after `stop`.
- Preserve existing `.product-delivery/` artifacts across plugin upgrades.

## Post-1.0 Version Plan

The post-1.0 line is intentionally compact. Technical support work such as runtime entrypoints, schema migration, and dashboards should not become standalone versions unless they solve a new user-visible delivery problem.

### V1.0.x - Patch Line

Goal: preserve release and closure trust without expanding product scope.

Scope:

- Fix urgent gate leaks, packaging failures, validator failures, or version drift.
- Keep release metadata aligned across README, manifest, runtime version, generated plugin package, distribution archive, and installed package evidence.
- Do not introduce new product capabilities in `V1.0.x`.

### V1.0.11 - Release Consistency Patch

Goal: reconcile the current `1.0.10` release drift and record the simplified post-1.0 roadmap.

Scope:

- Align planning files, README badges, manifest output, runtime `PLUGIN_VERSION`, generated templates, distribution archive naming, and test expectations.
- Add a concise changelog / version ledger.
- Keep behavior unchanged.

### V1.0.34 - Prototype Acceptance-Content Separation

Goal: keep the frozen high-fidelity prototype as a clean statement of the real product rather than a mixed product-and-acceptance surface.

Scope:

- Require new or reopened UI prototype bundles to use v2 and bind a review-only acceptance-content scan report.
- Scan static/rendered DOM, semantic text, attributes, resources, and review modes for acceptance, test, review, evidence, and developer-only content.
- Treat contamination as a hard integrity failure while preserving real product copy through lifecycle-bound callout mappings.
- Keep historical v1 bundles and already confirmed active deliveries unchanged until the prototype is modified or reopened.

### V1.0.42 - Chrome Visual Loop

Goal: keep prototype screenshots as a layout brief, not a pixel oracle for live data.

Scope:

- Revert the 1.0.39 capture-registry platform from the product line.
- Add a development visual loop that compares one bound TASK unit at a time.
- Pass or fail chrome structure and geometry only; treat data cardinality and pixel gaps as diagnostics.
- Keep 1.0.38 prototype conformance for deliveries that never enabled the visual-loop policy.

### V1.1 - Review Expert Panel Orchestration

目标版本：**1.1.0**。状态：角色卡、任务契约与复合席位已发布；完整 PanelRun 自动编排仍待实施。V1.2 复用已发布的契约能力。

目标：把现有多 Agent 评审升级为职责明确、过程可恢复、结论有证据的评审专家团。

范围（CR-002 / REV-20260926-01）：

- 固定八个角色：产品意图、用户旅程、负面边界、测试策略、追溯覆盖、测试断言、测试实现、UI 一致性。每个角色定义身份/版本、使命、方法、输入、输出、能力与权限、运行限制和证据要求。
- 按 `scenario`、`test`、`test_coverage`、`test_implementation`、`ui_conformance` 五类门禁组织 2–3 个独立成员；当前主线程担任协调者，不计评审席位。
- 从当前 feature 的 Open Spec、场景、原型或行为契约、计划测试义务及执行证据生成任务；固定输入快照与所用角色/模板哈希。
- 独立评审 → 一次交叉质疑 → 一次修订 → 汇总裁决，阶段全员屏障；成员只回传结果，修复回到原工作流。
- 记录成员身份、证据、裁决、运行事件、超时/替换、恢复及真实用量。每席位每阶段默认 600 秒、失败后重试或替换一次；一次自动周期最多初审加一次复验。
- 复用既有有效评审授权；`role_simulation` 仍只在既有显式降级授权下使用，不能冒充真实子 Agent。必需门禁不可因低风险跳过，`test` 与 `test_coverage` 都保留。
- 保持两次用户确认、runtime 自动实现授权、Host Goal owner、delivery 工件隔离和 canonical closure 权威。角色声明不等于文件系统沙箱，模型选择及具体模型记录继续由宿主管理。
- 四个拟议 workflow 接口负责准备、只读检查、事件登记和收敛；详细运行记录与现有评审摘要分离。新交付启用契约，旧 active 交付保持原 runtime/策略，历史记录保持可读。

不包含：生产专家、并行实现、动态角色市场、管理界面、外部编排平台和新的数据库/后台服务。

完成标准：角色与输入可追溯、缺角色/证据/屏障不可通过、迟到与重复事件可判定、失效与中断恢复可靠，且未改变既有门禁权威。质量收益需与当前多 Agent 评审在相同材料和相近预算下比较，不预先声称提升。

角色任务书：[八角色设定、约束与40个例子](docs/open-spec/v1.1-multi-agent-review-orchestration/09-role-cards.md)。

设计文档：[V1.1 产品需求](docs/open-spec/v1.1-multi-agent-review-orchestration/01-requirements.md)、[技术方案](docs/open-spec/v1.1-multi-agent-review-orchestration/03-technical-solution.md)。

### V1.1.x - Review Expert Panel Patch Line

目标：修复 V1.1 的稳定性、恢复、兼容性、成本记录及包装一致性问题。已有能力所需的 schema/API 修正随补丁交付；生产专家、管理界面或新的编排范式不作为补丁混入。

### V1.2 - Stage-Based Expert Production Orchestration

目标版本：**1.2.0**。状态：规范、团队运行实现、自动化回归、真实 UI/non-UI 宿主演练、coordinator 对照和 formal closure 演练均已完成。依赖 V1.1 已实现的评审契约，不依赖完整 PanelRun。详见 [V1.2 规范](docs/open-spec/v1.2-team-production-orchestration/02-specification.md) 与 [发布演练证据](docs/open-spec/v1.2-team-production-orchestration/10-release-exercise-report.md)。

目标：把专家角色扩展到各阶段实际产出，让生产成果经过独立评审和既有门禁。

| 阶段 | 生产职责 | 主要产出 |
| --- | --- | --- |
| 产品定义 | 产品、领域、用户研究专家 | 产品蓝图、用户故事、非目标与成功指标 |
| 架构与版本规划 | 架构、集成、风险及规划专家 | 模块边界、数据流、技术风险、版本范围 |
| Open Spec 与产品表面 | 需求、场景、交互或行为契约专家 | 需求、验收标准、旅程、原型或非 UI 行为契约 |
| 测试设计 | 测试策略、E2E、边界专家 | 测试义务、覆盖矩阵、E2E 计划 |
| 实现执行 | 按任务需要配置的前端、后端、测试、集成专家 | 代码、迁移、测试及实现证据 |
| 交付准备 | 发布、证据、回归专家 | 验收包、执行证据与发布材料 |

- 复用 V1.1 角色契约与运行记录，新增阶段输入/输出、生产任务交接、允许写入范围及冲突处理。
- 按阶段改造，以里程碑推进，不给每个角色单独创建版本。只并行执行边界清晰、写入不冲突的任务；同文件或强依赖任务串行处理。
- 生产角色不得自行修改冻结产品范围、删除测试义务、合并权威 TASK 或放行自己的成果；生产者与独立评审者职责分开。
- 继续保留用户确认、原型/行为契约、实施授权、Host Goal 与最终闭包权威；架构阶段不因增加专家角色自动升级为新的硬门禁。

完成标准：各阶段具备可追溯的生产职责和交接契约，独立任务可协作完成，成果接受 V1.1 评审及既有验证，并能度量返工、质量和资源消耗。

### V1.2.x - Expert Production Patch Line

V1.2 增补：默认关闭的产品交付地图，覆盖产品目标、架构、版本、当前工作、剩余缺口与计划变化。项目默认可被交付设置覆盖；静态 HTML 使用已有 HTTP 服务并每 5 秒刷新，提供离线快照。只读解释权威进度，不新增门禁或管理服务。详见 [地图契约](docs/open-spec/v1.2-team-production-orchestration/11-progress-map.md)。

目标：修复 V1.2 已有生产协作能力的恢复、写入冲突、兼容性及度量问题；不引入新的专家团范式。

### V1.2.6 - Delivery Observability Baseline

目标版本：**1.2.6**。状态：**已规划，尚未实现**。

目标：在不改变 canonical state、Goal、TASK、review 或 closure 权威的前提下，为交付生命周期、阶段执行、阻塞、证据、Host Goal 和资源消耗建立统一的可观测性基线。该版本先解决“能否准确看见交付发生了什么”，不提前声称多 Agent 已带来质量或成本收益。

核心指标：

| 指标 | 定义 | 最小数据来源 |
| --- | --- | --- |
| `delivery_cycle_time` | 从 delivery 创建到 canonical closure 通过的总时长，拆分暂停与等待；未闭包显示进行中，abandon 单列，不混入成功交付耗时 | lifecycle transition、closure/abandon event |
| `stage_duration` | 每个 workflow stage 从进入到离开的耗时，区分 active、waiting、blocked | stage transition journal、Host Goal observation |
| `blocked_duration` | 用户确认、宿主、环境、证据或恢复阻塞的累计时长，记录 blocker 类型和开始/结束原因 | blocker state、human wait、recovery transition |
| `gate_failure_rate` | 按 gate 统计首次尝试失败的实例占比；总尝试失败率作为独立明细，不混用分母 | gate attempt/result、error class、retry metadata |
| `first_pass_acceptance_rate` | 已有首次提交结果的工作单元中，首次提交即通过的比例；生产包、review、evidence、TASK 分别统计 | attempt/revision、review result、evidence status |
| `rework_rate` | 已提交工作单元中发生 retry、revision 或批量返工的单元占比；work package/TASK 分开统计，并附返工次数及原因 | TeamRun history、review rejection、TASK journal |
| `evidence_latency` | 记录的实现/生产结果完成时点到对应 executed evidence 被 canonical runtime 接纳的时长；不使用已经依赖证据的 TASK 完成时点作为起点 | production completion observation、evidence recorded、artifact manifest |
| `closure_failure_rate` | 已尝试 canonical closure 的交付中，首次校验失败的比例；另列总尝试失败率和 blocker 分类 | finalization attempt/result、closure validator artifact |
| `host_goal_health` | 展示宿主观测的 active、blocked、missing、unavailable、complete；绑定/checkpoint stale 和 observation freshness 单独标注 | Host Goal checkpoint/observation/recovery |
| `usage_cost_per_delivery` | 每次 delivery 的 input/output tokens、缓存 tokens、费用和币种；仅接纳宿主提供的用量与可用来源信息，缺失部分显式标记 `unavailable` | host usage receipt、TeamRun usage |

实现范围：

- 统一指标所需的本地观测记录，以 `delivery_id` 关联可用的 run、TASK、gate、attempt、时间、结果与证据引用。覆盖 coordinator/team、UI/non-UI；新补充的尝试、拒绝和失败记录与已提交的 canonical transition 分开，不能把操作拒绝记成状态推进。
- 复用现有 journal、TeamRun、Host Goal 和 artifact 数据，补齐缺失的计时及尝试结果。重复事件去重；未记录的历史区间、零分母和不适用项明确显示未知或不适用，不补造历史，不将缺失当作零。
- 提供本地 timeline 查询和机器可读导出；`status/inspect` 增加当前 telemetry freshness、最近事件、活跃阻塞和数据可用性，progress map 只消费这些事实，不成为第二权威。
- 观测数据独立于 canonical state，采集/展示/导出失败不阻塞交付，并可见地报告数据缺口。通过已有本地入口提示超时、持续阻塞、证据失效和重复失败；Prometheus/OpenTelemetry、独立 dashboard、后台监控服务及外部告警集成留作后续扩展。
- 对 usage 建立宿主数据接入契约；禁止从耗时推算 token/cost，缺失时保留 `unavailable` 并记录缺失原因。不改变宿主模型选择和权限规则，不记录未脱敏的 prompt、源码或 secret。

验收标准：

- 一个 UI delivery 和一个 non-UI delivery 的完整演练都能生成从 start 到 closure 的可关联 timeline，并可由 `delivery_id`、`run_id`、`task_id`、`gate` 查询。
- 十个指标均有明确统计口径和来源，能从 canonical event/artifact 及绑定的观测/宿主用量记录重新计算；比率展示分子、分母和数据完整率，重放或重复事件不重复计数。
- 阶段重入分别计时，重叠阻塞区间不重复计入总阻塞时长；人工等待、暂停和环境故障可区分，abandon、未结束交付、缺失历史和缺失用量不会被误计为成功或零成本。
- 至少覆盖 pause/resume、user wait、TeamRun retry/revision、review rejection、Host Goal blocked/recovery、evidence stale 和 closure failure 这些负向路径。
- telemetry 导出失败不改变交付状态；观测记录仅引用证据路径/hash，不复制证据正文；观测数据保留与清理不删除 canonical 证据。
- 发布一份 observability exercise report，报告十个指标、不可用字段、已知事件缺口、重复计数检查和异常提示结果；不把一次演练当作长期质量收益证明。

规划顺序：**V1.1 评审专家团 → V1.2 分阶段生产专家团 → V1.2.6 交付可观测性基线 → V2.0–V2.3 OpenCode 能力**。以下 V2.x 版本边界保持原规划，不以平台接入代替本地生产与评审能力建设。

### V2.0.0 - OpenCode Native Plugin MVP

Goal: make Product Delivery load and operate from OpenCode as a native plugin while preserving the local canonical runtime.

Scope:

- Package an OpenCode JavaScript plugin under `.opencode/plugins/`.
- Register Product Delivery skills through the OpenCode `config` hook.
- Inject activation, state authority, and closure authority rules through OpenCode chat transforms.
- Expose minimal OpenCode tools for status, start, stop, and closure validation.
- Reuse the Python Product Delivery runtime; do not reimplement gate logic in JavaScript.

### V2.1.0 - Execution Target Abstraction

Goal: generalize the frozen implementation handoff beyond Codex Goal.

Scope:

- Add `execution_target` with `codex_goal` and `opencode_run`.
- Preserve `generate_codex_goal_handoff` as a compatibility wrapper.
- Generate OpenCode-specific prompt and execution contract artifacts.
- Keep the same pre-handoff gate and implementation launch authorization for every execution target.

### V2.2.0 - OpenCode Evidence Ingestion

Goal: turn OpenCode execution output into Product Delivery evidence only through runtime ingestion.

Scope:

- Define and validate OpenCode execution evidence records.
- Reject summary-only and chat-only OpenCode evidence.
- Convert accepted OpenCode evidence into `executed_behavior_evidence` or `executed_browser_evidence`.
- Record ingestion through the transition journal.

### V2.3.0 - OpenCode Multi-Agent / External Orchestration

Goal: allow OpenCode to participate in external multi-agent orchestration without becoming closure authority.

Scope:

- Adapt OpenCode review output into the V1.1 structured review artifact schema.
- Record OpenCode as supporting external orchestration evidence.
- Fail closed with `blocked_with_reason` when OpenCode orchestration fails.
- Keep Product Delivery review artifacts and closure validation as the authoritative gates.

## Assumptions

- V1.1 已发布角色契约与复合评审席位；完整 PanelRun 编排仍属后续工作。
- V1.2 已完成团队模式及可选地图实现与验证；原生团队演练见报告 10，地图增补与最新分发包校验见报告 12。后续版本仍需按阶段更新规范和验收。
- Codex Goal remains the current supported implementation handoff target.
- OpenCode support is planned as a future `execution_target=opencode_run` capability.
- Waygate/controller integration remains read-only unless a later version defines an official import route.
