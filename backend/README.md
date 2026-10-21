# 后端模块（S9）

Java21 / Spring Boot3.5.16 / MySQL8.4 JDBC：城市目录、CITY/REGION/ROAD交通统计、已发布Hive ADS及每日拥堵指数预测；会话认证、ADMIN/READER、CSRF、受保护上传/确认/任务管理与默认拒绝。当前[部署](../docs/guides/s9-deployment.md)、[权限](../docs/guides/s9-security.md)、[架构](../docs/architecture/overview.md)。以下统计模块说明继续适用。

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
| `security/` | 精确路由授权、数据库用户/审计、受保护适配导入与有界重试 |
| `web/WarehouseController.java`、`repository/WarehouseRepository.java` | 已发布Hive结果的一致性只读查询 |
| `web/PredictionController.java`、`repository/PredictionRepository.java` | 当前已发布CITY日0–10预测与评估，不在线训练 |
| `api/` | DTO、必需 null 字段 |
| `src/main/resources/application.yaml` | 回环监听、外部凭据、禁用 clean/baseline、迁移校验 |
| `src/test/java/com/urbancommute/IsolatedMySql.java` | 测试迁移前实际库/账号/服务器身份校验 |
| `src/test/java/com/urbancommute/ApiIntegrationTest.java` | 真实 MySQL 约束、来源、迁移、HTTP 及错误回归 |
| `src/test/java/com/urbancommute/DatabaseOutageIntegrationTest.java` | 真实 JDBC 握手超时与 HTTP 503，无 Service/Repository Mock |

生产包通过 `database/migrations/V*.sql` 资源构建，当前V1–V6；S9未改历史迁移。Flyway11.20.3；禁止repair掩盖校验和问题。应用数据源读取DB_URL/DB_USER/DB_PASSWORD，安全/适配配置见.env.example；测试没有DB_URL回退路径。

运行、隔离回归和本机授权边界见 [S3 操作说明](../docs/guides/s3-mysql.md)。历史 S2 证据仍保留，但内存 seed 配置不再有效。

`/health` 是进程存活检查；数据库断连后仍 UP，不是数据库 readiness。首次启动必须能完成 Flyway，失败时应用拒绝就绪。城市列表允许为空；所有城市目录的 dataAsOf 为 null，不宣称存在真实交通观测。数据库连接/事务建连失败返回 503；其他未预期错误返回 500；不向客户端返回异常细节。
