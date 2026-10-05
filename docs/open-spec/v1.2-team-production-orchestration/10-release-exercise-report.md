# V1.2.0 真实宿主演练与发布闭环证据

本报告记录 CR-005 团队模式原生演练及当时的分发包。CR-006 地图增补后的最终回归和当前分发包哈希见 [地图验收记录](12-progress-map-verification.md)；下表历史哈希保留用于追溯，不代表当前 dist 文件。

| 字段 | 值 |
|---|---|
| 版本 | V1.2.0 |
| 日期 | 2026-09-29 |
| 状态 | UI/non-UI team 与 coordinator 对照演练完成；两条 team 链路均通过 packaged canonical closure 并关闭 |
| 证据目录 | `/tmp/waygate-v12-native-release-report/` |
| 分发包 | `dist/waygate-product-delivery-1.2.0.tar.gz` |
| 分发包 SHA-256 | `8c04c592acd25edf31a11304c84b1660a784410b0d310d96b43fb26922fa8df8` |

## 执行命令

```bash
PYTHONPATH=src python3 /tmp/waygate_v12_native_release_exercise.py
PYTHONPATH=src python3 /tmp/waygate_v12_coordinator_comparison.py
```

演练使用当前源码 runtime，在临时目标项目中实际创建 delivery、六阶段 `TeamRun`、独立评审屏障、用户确认、Host Goal、TASK、证据、canonical closure 和 close。演练项目不写入本仓库的 `.product-delivery/state.json`。

## Team 结果

| 分支 | delivery | TeamRun | Host Goal | closure | 关键证据 |
|---|---|---|---|---|---|
| UI | `bb62027d558b4707a9e50fdf577f4b84` | 6 个阶段全部 `completed` | `complete` | `passed`，最终 `closed` | Chromium 截图、trace、semantic probe |
| non-UI | `f84b73a912a9414a8b7385bcc92f0cda` | 6 个阶段全部 `completed` | `complete` | `passed`，最终 `closed` | 真实 CLI 有效/无效输入、输出文件和执行 trace |

UI 证据：

- `browser-e2e-results.json` SHA-256：`7c20a219e2a40a83078e440fa180a8c2e3734cd93dc75fa5f853bef5bd70d739`
- `browser-e2e-probe.json` SHA-256：`83e3e8b5f9cd885fbf96f928e1446edd64742f90e397d81df9d642f2d995b069`
- 截图：`e2e/ui-empty.png`、`e2e/ui-created.png`、`e2e/ui-duplicate-error.png`
- trace：`e2e/ui-trace.zip`
- packaged canonical validator：`closure_validation=passed`，`canonical_schema_version=v0.11`

non-UI 证据：

- `behavior-e2e-results.json` SHA-256：`1ac64e55bd7ff4e52a27be75c6420758f58fdd801f89b720e7437b539a9b598f`
- `behavior/roster-import.log` SHA-256：`8db3f9795ecf94d41d4194504cc4186276ab701ae788621079b328c3cb2e7998`
- `behavior/roster-import.txt` SHA-256：`ee5864079280dcb3c3239025d14f2f80ad69a249ccb78ee80a13ba1bb4a11e1a`
- 三个文件记录有效 CSV 成功和重复邮箱输入失败；non-UI 证据没有 browser probe 或 browser-only 字段。
- packaged canonical validator：`closure_validation=passed`，`canonical_schema_version=v0.11`

non-UI 正式证据现在通过 `ProductDeliveryWorkflow.record_executed_behavior_evidence()` 进入 canonical state；没有该证据时 closure 仍 fail closed。

## Coordinator 对照

| 分支 | delivery | TeamRun 数 | Host Goal | closure | usage |
|---|---|---:|---|---|---|
| UI coordinator | `702c563edaef47d1afa7946c83012495` | 0 | `complete` | `passed`，最终 `closed` | `unavailable` |
| non-UI coordinator | `e8a503b2603e4c5aa3234c38414df337` | 0 | `complete` | `passed`，最终 `closed` | `unavailable` |

这是同机单样本 smoke 对照，只报告观察到的闭环状态和用量缺口，不推断质量收益、返工收益或成本收益。两组对照均为 0 次 review remediation；后续需要更多相同输入样本再比较缺陷、返工、耗时和资源。

## 结论边界

- 本报告证明当前 runtime 能在真实临时目标项目中完成 UI/non-UI team 六阶段、评审、Host Goal 和 canonical closure。
- `TeamRun completed` 仍不等于 TASK 或 closure；本次演练明确执行了原有 TASK、证据、closure 和 close API。
- 证据目录在 `/tmp`，用于本次验收复核；分发包不携带临时目标项目。
