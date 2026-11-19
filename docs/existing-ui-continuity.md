# 已有产品的原型对照

当 `ui_change_type` 是 `incremental_existing_surface` 或 `new_surface_in_existing_product`，Waygate 要求原型来自对真实产品的浏览器观察。从学生课程列表走到原生播放器，再添加字幕，就是一个增量设计。原型同时保留课程列表中的学习路径、搜索、分页和移动工具，以及播放器的全宽底栏。

## 采集

1. 在指定的当前发布构建或同源研发构建中，以场景矩阵中的角色从普通入口进入。先锁定构建身份和可比较的业务状态，按每个受影响的页面、角色及合同视口采集。打开新页面的需求先采集真实入口和共享壳层。
2. 在项目的 Playwright 脚本中导入 `product_delivery_agent.existing_ui_capture`。`observe_action(page, ...)` 操作真实控件并检查可见结果，返回前后路由和观察值。默认使用点击，键盘、表单等操作可通过 `perform` 使用 Playwright locator。`capture_unit(page, ...)` 检查角色及业务状态标记，采集浏览器 DOM、控件、父层级、定位样式和视口 PNG。通过 `regions` 和 `controls` 提供稳定标识。采集器也会从整个文档中发现常见可见控件，已经标记的区域应包含真实页面壳层和业务相关布局，例如全宽底栏及其父级。
3. 用 `write_capture(..., build_id=..., origin=...)` 保存真实产品清单，再制作可点击原型。构建身份取自项目的部署或运行收据，由评审对照来源。用相同角色、业务上下文和视口采集原型。HTTP 原型使用实际路由。独立 HTML 记录真实文件 URL，用 `route_for_url` 把浏览器实际观察到的页面切换映射到产品合同路由。用 `write_capture(..., baseline_path=..., prototype_path=...)` 保存原型清单，并将其 PNG 复用为 v2 bundle 中对应的纯净截图。

`context_id` 是两侧共享的业务状态标识，例如 `published-course-ordinary-entry`。`baseline_unit` 按 `[surface_id, state_id, viewport, actor_role]` 指向真实采集单元。新页面或新状态可指向最接近的现有表面，同一个已采集的真实单元可以支持多个新状态。对于课程列表等容量随数据变化的区块，用 `dynamic_regions` 标记区域，并仅为列表项的重复控件指定 `repeated_controls` 选择器。内容名称、数量、换行和页面滚动可以变化。搜索、筛选、分页等固定操作仍逐项比较。

## 提交与评审

将 `.product-delivery/artifacts` 下的两份清单加入现有原型设计 bundle。对于差异，引用已定义本次需求的文档和具体 ID。下面的示例只声明手机播放器新增字幕开关。

```json
{
  "existing_ui_continuity": {
    "baseline_path": ".product-delivery/artifacts/prototype-design/existing-product.json",
    "prototype_capture_path": ".product-delivery/artifacts/prototype-design/interactive-prototype.json",
    "requirements_path": "docs/open-spec/player-captions/01-requirements.md",
    "changes": [
      {
        "change_id": "mobile-caption-toggle",
        "unit": ["learner-player", "ready", "mobile", "student"],
        "kind": "elements",
        "target": "caption-toggle",
        "requirement_ids": ["FR-V211-001"]
      }
    ]
  }
}
```

`kind` 也可为 `actions`、`elements_order`、`actions_order` 或 `route`。顺序变化的 `target` 是父级 ID，顶层用 `root`。路由变化的 `target` 是 `route` 或 `entry_route`。声明只覆盖具体单元和差异，新增元素不会改变其他兄弟元素的相对顺序。

`record_ui_prototype_design_bundle()` 根据捕获结果生成对照。记录中的 `report_path` 指向正式 bundle，`existing_ui_continuity` 章节包含真实入口、截图引用、保留项和每项改动的前后值。场景评审检查来源和差异，用 `existing_ui_continuity_review` 提交报告的 `comparison_sha256`、`baseline_identity_verified: true` 和排序后的 `reviewed_change_ids`。产品基线确认和实现移交沿用同一份报告。

这项门禁用于新的及重新打开的已有产品 UI 基线。已确认的历史基线可继续使用到下一次设计变更。全新产品使用设计体系证据。浏览器文件的哈希和结构可以由 Waygate 验证，构建来源、账号身份和采集操作由项目提供观察结果，交给场景评审核对。
