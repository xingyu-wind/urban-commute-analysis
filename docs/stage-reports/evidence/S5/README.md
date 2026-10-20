# S5 实测证据

2026-10-20，实际MySQL8.4.11、Java21、Python3.11、Node24.19、真实Chrome155.0.8059.85。原始完整日志在本地backend/target，云端同入口输出通过Actions artifact保留7天。此目录只归档无凭据的合成测试结果，未上传私有实例配置、账号密码或原始第三方数据。

- `local-summary.json`：s5_checks.py --with-core的所有入口通过。
- `core-summary.json`：Java82、Vue63、原HTTP/前端/契约/反向测试通过；`s4-summary.json`：原S4独立SQL、Chromium及恢复验证通过。
- `pytest.xml`：40项通过、0失败/错误/跳过，其中7项真MySQL，含事务异常和真实子进程os._exit(73)恢复。
- `isolation.json`：首次全量运行创建的新schema/单库账号身份，existingDataDeleted=false。
- `browser-manifest.json`：实际请求、浏览器、自己持有的服务进程及清理结果；无pageerror、无request mocking。
- `etl-oracle.json`：导入前、CSV后、JSON后、重复后及额外数据集后的实际四API与独立SQL快照；CITY均速null/54/40/40，其他数据集200不混算。
- `schema-validation.json`：38个真实API响应通过完整OpenAPI Schema检查。
- `s5-before.png`、`s5-after-json-presentation.png`：真实空状态和Python导入后大屏。
- `mysql-reconciliation.json`、`audit-summary.json`、`audit-isolation.json`：另一新库重新执行S5后的最终批次、质量、逐条血缘、冲突、重试次数、分层观测及Flyway校验和对账。

主运行命令（私有凭据仅预先配置进程环境）：

```text
scripts/s3_database.py --output backend/target/s5-final2-db.json -- <python> scripts/s5_checks.py --with-core --output backend/target/s5-final2
scripts/s3_database.py --output backend/target/s5-audit-db.json -- <python> scripts/s5_checks.py --output backend/target/s5-audit
```

早期失败保留在backend/target：V3开发稿使用MySQL保留字、原迁移数断言未更新、合法坐标的ECharts浮点断言。均通过新库重跑修复，不repair或清理失败库；没有将这些失败运行当作通过。一次误将复合检查脚本传入S3的Maven专用隔离探针，已保留失败，最终完整运行使用正确入口；云端仍直接对Maven执行原隔离探针。

CI最终HEAD、Run/Job与结论由[PR #6 正文](https://github.com/xingyu-wind/urban-commute-analysis/pull/6)和[实时Checks](https://github.com/xingyu-wind/urban-commute-analysis/pull/6/checks)记录。此目录是本机实测快照，不冒充云端结果。
