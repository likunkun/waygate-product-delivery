# CR-006 产品交付地图验收记录

日期：2026-10-06。版本：1.2.0。结果：通过。

## 实现与行为

- 新增 `progress_map.py`、`progress_map_model.py`、`progress_map_html.py`，通过 workflow facade 和 packaged `waygate-map.py` 使用。
- 默认关闭；项目设置只作用于新交付；delivery 开关绑定身份并在恢复时保留。配置、计划修订、回执和快照均独立于权威状态。
- HTML 在成功状态写入后原子生成，每 5 秒浏览器刷新；无服务器、端口或常驻进程。关闭冻结最后成功发布的页面，导出单文件快照禁用刷新。
- 目标／能力／组件／版本／TASK／场景／测试义务关联，来源和任务哈希验证；产出、整合、验证、评审、闭包分别投影。
- 计划差异、未关联任务、证据失效、历史修订及具体下一步可查看。普通修复和范围确认沿用既有流程，不新增门禁。

## 自动化与集成证据

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

最终结果：**713 tests，OK，204.282 秒**。本次新增 30 项地图相关测试，覆盖开关、项目默认、恢复、身份、只读状态、CLI、哈希、计划修订、错误输入、文件冲突、冻结、快照、UI/non-UI 六阶段 canonical workflow 和 HTML 安全。

UI 与 non-UI 团队集成测试复用真实 workflow API、真实临时文件及受控 host/review fixture，完成六阶段和正式闭包。它们验证 runtime 合同，不冒充本次实际模型宿主演练。此前 V1.2 原生团队宿主演练见 `10-release-exercise-report.md`。

## 浏览器验收

```bash
python3 scripts/verify_progress_map_browser.py --output-dir /tmp/progress-map-browser-final-2
```

Chromium `file://` 实际打开生成的 HTML，**9 组检查通过，浏览器脚本错误 0，网络请求 0**：

1. 架构、六阶段、SVG 接口与依赖。
2. 版本筛选、定位当前任务、独立完成里程碑和证据。
3. 场景—测试义务、语义断言、缺失/待验证/已验证区分及失效来源。
4. 剩余缺口、变化前后、历史、选择/筛选/位置恢复。
5. 键盘导航与焦点。
6. 手机和平板宽度无页面水平溢出。
7. 不可信 HTML 作为文本显示，不执行脚本。
8. 关闭保留内容、时间、身份与历史；关闭页和快照不刷新。
9. 每 5 秒从磁盘加载新内容，带缓存规避参数并保留视图。

验证无需启动 HTTP 服务；页面按普通静态文件部署到用户已有服务。没有对用户外部服务的地址、权限或缓存配置作未经验证的声明。

## 复盘示例

```bash
python3 scripts/build_progress_map_examples.py
```

[示例入口](../../examples/progress-map/index.html) 包含原计划、实现中、评审补漏、批准变更、修复验收五个时点。五页在 Chromium 中检查架构、六阶段、变更摘要及窄屏布局通过；浏览器错误为 0。样例清晰标为演示数据，与实际交付证据分开。

## 独立评审修复

- 修正过期角色评审继续显示通过：复用带项目路径的现有评审有效性校验。
- 工作包（包括无 TASK 的设计工作包）、历史来源及评审文件核验结果纳入派生修订，文件变化可使 freshness 失效。
- HTML 作为最后发布点，回执绑定实际页面哈希；关闭从最后发布页提取冻结内容，避免显示失败刷新中的新数据。
- coordinator 阶段依据 canonical 确认和记录显示进度，缺少架构证据显示待核实。
- 拒绝不匹配测试义务造成的能力误报验证通过。
- 非法集合和引用字段在计划落盘前拒绝，不产生无法渲染的不可变修订。

以上问题均有针对性回归；最终全量回归包括修复后的实现。

## 分发与一致性

- 源码与 packaged runtime：**35 个 Python 模块逐字节一致**。
- `compileall`、依赖检查、`git diff --check`：通过。
- 无源码 Python `-I` CLI 开关、导出、关闭：通过。
- tarball 解包后独立 `-I` CLI smoke：通过；全过程 canonical state 字节未因地图操作改变。
- 包：`dist/waygate-product-delivery-1.2.0.tar.gz`。
- SHA-256：`1b923021e24ac7eb27d063c0432b2dce6d4bd17318c32f71adf0357b5977c65e`。

旧 active delivery 未迁移；当前仓库交付开关未被演示或测试修改。
