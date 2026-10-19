# S3 工程运行与验证

## 普通应用

需要 MySQL 8.4、Java 21。只对经过授权的目标库设置 DB_URL、DB_USER、DB_PASSWORD；不要把密码放在命令行、VITE_*、Git 或截图中。Spring Boot 不会自动读取仓库根目录的 .env；模板仅供变量参考。

构建（不连接数据库）：

```powershell
.\backend\mvnw.cmd -f backend/pom.xml -B -ntp package -DskipTests
```

启动会执行 Flyway，属于数据库结构变更，目标库必须已获授权。不要使用参考 ZIP 的库。V1 不变，V2 新增约束；应用默认禁止 Flyway clean、禁止非空库自动 baseline，并验证历史 checksum。不要用 repair 绕过错误。

```powershell
java -jar backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar
```

空库 API 返回 `data=[]`、`database_catalog/null`。城市目录非交通观测，dataAsOf 永远 null。CITY_DATASET_FILTER 仅为部署/验证筛选配置，不是公开 API 参数。

## 隔离集成测试

直接 `mvn verify` 不会回退到普通应用的 DB_URL；缺少 TEST_DB_* 时拒绝启动测试。先使用 `scripts/s3_database.py` 在已授权的专用实例创建全新随机库和单库权限账号。它从进程环境读取 S3_ADMIN_PASSWORD、S3_ADMIN_USER（默认 root）、S3_MYSQL_PORT（默认 33067）及 MYSQL_CLIENT。

```powershell
python scripts/s3_database.py --probe-isolation --output backend/target/s3-new-run.json -- cmd /c backend\mvnw.cmd -f backend/pom.xml -B -ntp verify
```

每次选择新的证据文件名。准备器不 DROP、不复用库；SQL 对库名转义，账号无全局权限。密码随机生成且只传给子进程，不写证据。CI 为后续 JAR/浏览器步骤通过 GITHUB_ENV 传递受遮蔽的单库凭据。

测试迁移前使用实际连接验证 SELECT DATABASE()、CURRENT_USER()、@@server_uuid；库名必须完整匹配 s3test_ 加 32 位十六进制标识，账号匹配独立随机账号。验证发生在 FlywayMigrationStrategy 内，迁移之前，且测试禁用其他 SQL 初始化。错误库身份或服务器 UUID 的真实 Spring 启动必须失败；准备器检查目标库仍为零张表，防止把编译失败冒充保护生效。

完整本机测试（同一授权实例上另建隔离库）：

```powershell
.\contracts\.venv\Scripts\python.exe scripts/s3_database.py --output backend/target/s3-full-run.json -- contracts\.venv\Scripts\python.exe scripts/s3_checks.py --output backend/target/s3-full-evidence
```

该入口依次执行 Windows Maven Wrapper、CI 策略、OpenAPI、契约、独立 JAR HTTP、前端类型/单元测试/构建、真实 Chrome/Edge 浏览器及反向驱动验证。依赖已按锁文件安装。首次需使用项目 Python venv 和 npm ci；不需要全局安装或改 PATH。只停止由测试驱动持有的 Java/Vite 子进程。MySQL 实例由授权管理者持有，不由测试驱动批量终止。

## 核验与失败边界

只读核验 SQL：SELECT VERSION(), DATABASE(); SHOW TABLES; SELECT version,checksum,success FROM flyway_schema_history ORDER BY installed_rank; SHOW CREATE TABLE traffic_observation;

数据库不可用：先检查自己实例的端口、配置和权限；不要改防火墙或结束未知进程。V2 遇到历史脏数据会失败；MySQL DDL 不能保证整文件原子回滚，应保留现场、评审数据修复，不 repair、不清库。

本机生成的凭据位于工程外、仅当前 Windows 用户可访问的私有实例目录。不可上传该目录。需要停止实例时先核验可执行路径、配置路径和监听进程身份；保留数据目录，不删除既有数据。

最新实际结果、环境和代码索引见 [S3 报告](../stage-reports/S3.md)。
