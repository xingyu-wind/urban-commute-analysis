# Windows 1.0.0 候选证据

本轮 **包内服务通过，安装器/独立窗口受本机 Windows 应用控制阻塞**。禁止把本目录的浏览器截图解释成 Electron 窗口实测。

- `services-summary.json`：包内 Python/Java/MySQL 全流程，开发工具 PATH 移除、不可用代理、两场景、启动/停止、父进程退出回收及恢复、升级前备份。
- `browser-model.json` / `browser-warehouse.json`：实际生产前端 → 包内代理 → Java → MySQL，无请求拦截；各 16 组布局、预测七点/API、全屏、断网恢复、匿名管理拒绝。
- `business-fingerprint.json`：两 schema 的 17 张业务表逐表行数和规范内容 SHA256、MySQL UUID、DPAPI 文件 SHA256；没有密码、密文原件、完整数据库或上传文件。
- `upgrade-receipt.json`：测试专用 JAR 身份变化，未改变业务字节码/迁移 SQL，触发真实 mysqldump、双库 Flyway 校验、重启；业务和账号指纹不变。不是破坏性新迁移或失败恢复验证。
- 两张 PNG：真实浏览器截图，已目视检查。
- `management-summary.json` / `management-reader.png`：升级后原随机账号登录、真实上传/包内 Python 分析、人工确认、研究导入 SUCCEEDED、READER 只读和退出；凭据只通过匿名管道传递，没有入日志。
- `build-receipt.json`：最终候选完整路径、大小、SHA256、构建源码和工具/文件锁。
- `app-control.json`：实测拦截的整理回执；系统策略未修改，用户选择保留候选。

本地原始输出：`backend/target/desktop-acceptance-01`（安装拦截）、`desktop-window-02/03`（独立窗口拦截）、`desktop-services-01`（首次初始化成功后验收脚本 GBK 读 UTF-8 失败）、`desktop-services-02`（修正驱动并复用本轮新隔离库后全部通过）。失败现场保留，不用成功覆盖失败。

管理链路额外补验：`desktop-management-01/02` 因旧浏览器驱动对包内 Python 的上传分析/映射确认仅等待 5 秒而提前退出；实际界面仍为处理中。改为等待真实操作完成（最多 60 秒，仍要求相同成功响应和内容断言）后，`desktop-management-03` 全链路 13 秒通过。前两次失败保留；不将它们归因成新的产品故障，也不隐去驱动修正。

`desktop-services-02/upgrade-fixture` 只为身份变化测试，不能分发；真实候选程序与所有原 ZIP 保留。私有备份位于本轮数据目录，未入 Git。

首次制包 `windows-v1-candidate-01` 暴露 Windows 许可证副本路径超长；后续缩短副本路径并建立内容/原路径索引，原始组件归档和许可保持。后续候选保留，最终推荐身份见交付报告及构建回执。
