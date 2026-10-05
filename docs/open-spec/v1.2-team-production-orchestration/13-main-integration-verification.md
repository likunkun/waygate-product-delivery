# V1.2 主分支整合验证

本次整合将功能提交 `7653e29` 与主分支 `a4c7b8e` 的恢复并发保护、生命周期校验和终态闭包幂等修复合并。插件版本保持 1.2.0；已有孤立 blocked-binding 恢复测试改为使用当前版本的精确授权语，其余恢复规则不变。

验证结果：

- 功能提交前完整回归：713 tests，OK，259.870 秒。
- 合并后恢复／生命周期／闭包／地图入口专项：59 tests，OK。
- 合并后完整回归：`PYTHONPATH=src python3 -m unittest discover -s tests`，725 tests，OK，215.048 秒。
- 地图 Chromium 浏览器验收：9 组通过，脚本错误和网络请求均为 0。
- 35 个源码与 packaged runtime 模块逐字节一致；compileall、依赖检查、diff-check 通过。

当前分发包：`dist/waygate-product-delivery-1.2.0.tar.gz`。

SHA-256：`49230584b98d63f52b98250a7caf22b0c97ad6bdeeb050e8dbd608c51e62e35e`。

本报告补充报告 10 与 12；旧报告的验证结果及包哈希保留为历史记录。
