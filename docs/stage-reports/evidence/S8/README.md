# S8 可复核证据索引

- `gate-waiver.md`：用户明确授权、S7真实成功核查、403原因、一次性有限豁免及实际分支操作。
- `local-summary.json`：由实际脚本结果和JUnit XML汇总的实现SHA、Java104、Vue91、ETL40、ML73、安全105次HTTP结果。
- `security/http.json`：实际方法、路由、状态、Content-Type、安全错误封套、requestId；不保存认证或CSRF响应值、Cookie、原始上传内容。
- `security/filesystem.json`：每个非法上传后目录/临时文件/元数据/任务的真实计数；结合脚本断言验证路径隔离和清理。
- `security/database.json`：独立MySQL回读确认人/时间/配置SHA、任务状态/尝试数、输入输出SHA、审计分组；安全库观测和两个指针均0。
- `security/summary.json`：HTTP、并发200/409、文件系统、数据库和浏览器结果。
- `browser/summary.json` 与三张PNG：真实Chromium管理员确认/执行、只读角色无上传入口及服务端403；1440与390宽，已视觉检查截图。
- `core/summary.json`：旧Java/Vue、OpenAPI、独立JAR HTTP、六视口、停止恢复和反向驱动的实际命令与退出码。
- `s4/`：CI失败定位后，实际地图正常点击、渲染坐标就绪及全视口/故障恢复重跑；失败原日志见 `ci-s4-browser-failure.txt`。
- `s5/`：真实ETL/幂等/恢复/网页回归和SQL血缘对账。
- `s7/`：真实训练/重复训练、逐点篡改拒绝、事务回滚/硬退出/陈旧任务保护及真实API/图表回归。
- `resolved-failures.json`：真实失败摘录、原日志路径与SHA；故障不算通过，修复后以最终成功记录为准。

所有文件来自受控本机执行，数据为原项目合成fixture。忽略目录内原件、规范化逐条观测、口令和会话材料未复制。完整本机诊断保留于 `backend/target/s8-*`，不可把全部目录直接上传。CI使用现有临时MySQL和合成fixture，并按工作流白名单上传；最终CI入口与SHA见阶段报告及PR正文。文件清单由 `files.json` 提供（不自包含）；文本校验依据仓库 `.gitattributes` 的 LF 字节，避免 Windows CRLF 转换产生伪差异。`source-sha256.json` 同样记录 LF 规范后的实现源码。
