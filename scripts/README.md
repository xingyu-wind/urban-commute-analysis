# 辅助脚本模块

脚本使用项目 Python3.11 依赖，不需要全局安装。数据库写入与集成测试通过 `s3_database.py` 创建全新随机隔离库/单库账号，并核验真实服务器 UUID；管理员凭据只从已授权实例的私有进程环境读取。不会回退到持久应用库或自动清理旧数据。

| 入口 | 职责与说明 |
|---|---|
| `s3_database.py` | 准备独立测试库并运行子进程；[MySQL指南](../docs/guides/s3-mysql.md) |
| `s3_checks.py` / `s4_checks.py --with-core` | Java、OpenAPI、Vue、真实 HTTP/Chromium 与既有统计/响应式回归 |
| `s5_checks.py --with-core` | S2–S5 核心、真实 ETL/事务故障/恢复与页面链路；[S5使用说明](../data-pipeline/README.md) |
| `s6_checks.py` | 成功批次准入、HDFS/Hive 真算、对账、ADS 发布/恢复、HTTP/Chrome；[数仓指南](../bigdata/README.md) |
| `s6_edge_fixture.py` | 自主生成 synthetic_test 边界输入，不替代 S5 ETL |
| `check_ci.py` | CI 静态策略检查，不代表云端测试或 Hive 实算 |

每次提供新的 `--output` 目录，避免覆盖旧证据。S6 默认重型模式只允许本轮获授权的临时 GitHub Actions 空目录 HDFS format；Windows 可使用 `--admission-only`，其输出明确不代表 Hive 实算。`--hive-evidence` 可复核真实 CI 导出到本机 MySQL/API/Chrome 的链路，并记录复用来源。所有模式都不下载真实未授权交通数据。
