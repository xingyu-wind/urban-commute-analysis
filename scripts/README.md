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
| `s9_runtime.py` | 回环候选部署预检、Java/production dist启动与所持子进程停止；[部署手册](../docs/guides/s9-deployment.md) |
| `s9_release_checks.py` | S7/S6真实发布后的独立空库逻辑备份恢复、逐表哈希/指针/API比较、production Chromium与适度性能实测 |
| `s9_sources.py` | 无账号公开来源重查与本地片段哈希；不下载观测、不训练、不自动确认真实许可 |
| `build_windows_zip.py` | 按允许清单生成Windows候选ZIP、薄JAR、源码/文件哈希；不复制runtime/state/dump |
| `test_windows_zip.py` | 实际BAT/MySQL/HTTP权限/研究桥接/停止重启/异常Job回收验收，按需复用S9 Chromium |
| `t2_lock_downloads.py` | 维护者更新官方归档和Windows wheels锁；不安装全局软件 |
| `t2_export_seed.py` | 已核验合成源库的只读允许表导出及fixture/Hive逐值核对；不导出账号/审计/上传 |

每次提供新的 `--output` 目录，避免覆盖旧证据。S6 默认重型模式只允许本轮获授权的临时 GitHub Actions 空目录 HDFS format；Windows 可使用 `--admission-only`，其输出明确不代表 Hive 实算。`--hive-evidence` 可复核真实 CI 导出到本机 MySQL/API/Chrome 的链路，并记录复用来源。所有模式都不下载真实未授权交通数据。
