# S4 真实本机回归证据

来源：`scripts/s3_database.py` 新建随机隔离库，子进程执行 `scripts/s4_checks.py --with-core`。MySQL 8.4.11、Java21、真实 Chromium，无 HTTP route mocking。

- core-summary.json：Java 82项、Vue 63项、类型/构建、S2/S3 HTTP/浏览器及反向驱动。
- local-summary.json：独立 SQL、真实 S4 浏览器、实际响应 Schema、恢复后对账。
- independent-oracle.json / restored-oracle.json：固定 SUM/COUNT SQL 与手算五个目标、两天结果一致。
- browser/manifest.json：实际步骤、响应、受控更新与恢复、浏览器版本、自己持有进程的清理。
- browser/response-*.json：真实 Java JSON，schema-validation.json 记录83个响应全部校验（200/400/503）。
- browser/*.png：桌面、390/1024、比赛大屏、数据库修改后42、空观测、断连截图。
- isolation.json：专用随机库、单库账号、服务器 UUID，无密码。
- demo-smoke.json：独立新库的演示启动入口实际就绪并正常退出。

完整原始日志留在本机 backend/target/s4-integrated；CI 日志和短期下载产物以 S4 报告的 GitHub Run/Job 为准。本目录未包含私有实例口令。故障用例中 not-a-real-password 仅为不可达假数据源的固定测试值。
