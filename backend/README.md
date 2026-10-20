# S4 后端模块

Java 21 / Spring Boot 3.5.16，真实 MySQL 8.4 JDBC 查询，保留城市目录并新增 CITY/REGION/ROAD 四条交通统计接口；不包含鉴权或预测。接口、口径、启动和演示见 [S4 指南](../docs/guides/s4-dashboard.md)。

| 文件 | 职责 |
|---|---|
| `repository/TrafficRepository.java` | 分层聚合、UTC 分桶、来源过滤、参数绑定与只读一致快照 |
| `service/TrafficQuery.java`、`web/TrafficController.java` | 四条统计 API、参数白名单与边界校验 |
| `api/Traffic.java` | 统计 DTO 与明确空值 |
| `repository/CityRepository.java` | 参数化 JOIN、稳定排序、数据库目录读取 |
| `service/CityService.java` | 单一数据集、空目录及混合来源语义 |
| `web/ApiController.java` | `/health` 与 `/api/v1/cities` |
| `web/ApiExceptionHandler.java` | 固定安全错误封套；数据库连接失败 503 |
| `web/RequestIdFilter.java` | 每请求 UUID、响应头和日志关联 |
| `api/` | DTO、必需 null 字段 |
| `src/main/resources/application.yaml` | 回环监听、外部凭据、禁用 clean/baseline、迁移校验 |
| `src/test/java/com/urbancommute/IsolatedMySql.java` | 测试迁移前实际库/账号/服务器身份校验 |
| `src/test/java/com/urbancommute/ApiIntegrationTest.java` | 真实 MySQL 约束、来源、迁移、HTTP 及错误回归 |
| `src/test/java/com/urbancommute/DatabaseOutageIntegrationTest.java` | 真实 JDBC 握手超时与 HTTP 503，无 Service/Repository Mock |

生产包通过 `database/migrations/V*.sql` 资源构建。Flyway 11.20.3；V1 原样保留，V2 修复约束。禁止 repair 掩盖校验和问题。正常应用只读取 DB_URL/DB_USER/DB_PASSWORD；测试没有 DB_URL 回退路径。

运行、隔离回归和本机授权边界见 [S3 操作说明](../docs/guides/s3-mysql.md)。历史 S2 证据仍保留，但内存 seed 配置不再有效。

`/health` 是进程存活检查；数据库断连后仍 UP，不是数据库 readiness。首次启动必须能完成 Flyway，失败时应用拒绝就绪。城市列表允许为空；所有城市目录的 dataAsOf 为 null，不宣称存在真实交通观测。数据库连接/事务建连失败返回 503；其他未预期错误返回 500；不向客户端返回异常细节。
