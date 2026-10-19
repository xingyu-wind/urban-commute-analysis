# S3｜MySQL + Flyway 可复现验收指南

> **操作边界：** 下列是供用户或获授权的 Codex 在 Windows 上执行的步骤。当前 ChatGPT 无权访问 `D:\WindXingyu\Code\urban-commute-analysis`，未在该电脑安装 MySQL、创建数据库或改动其文件。不得重置现有数据库、执行参考 ZIP 原 SQL 或复制明文账号。

## 1. 核对环境（只读）

在 PowerShell 中到正式工程目录，核对 `git status -sb`、`git log -1 --format=%H`、`java -version`、`node --version`、`mysql --version`（若存在）、MySQL 服务运行情况。先保存任何未提交工作，不在已有目录里重新 clone 或强制 reset。创建/切换 S3 本地分支仅在同步并保护现有改动后执行。

S3 GitHub 分支：`feat/s3-mysql-flyway`；PR #3：<https://github.com/xingyu-wind/urban-commute-analysis/pull/3>；**保持 main 不变，未经总规划师审核不得合并**。

## 2. 准备独立数据库（需用户授权后由本人或 Codex 执行）

使用 MySQL **8.4.x**，在 MySQL 管理工具中单独创建新数据库 `urban_commute`（开发）和 `urban_commute_ci`（隔离测试），**切勿使用原参考库或现有业务库**。使用 UTF8MB4、现代 MySQL 8.4 默认排序规则。应用账号只授予自身模式所需的 SELECT/INSERT/UPDATE/DELETE 和 Flyway 建表需用的 CREATE/ALTER/INDEX/REFERENCES 权限，不用生产 root；密钥只保存在本机私有环境中。若 MySQL 未安装或需修改 PATH/Windows 服务，先向用户申请明确授权。

PowerShell 会话中按实际环境配置：

```powershell
$env:DB_URL = 'jdbc:mysql://127.0.0.1:3306/urban_commute?connectionTimeZone=UTC'
$env:DB_USER = 'urban_commute'
$env:DB_PASSWORD = '<从安全位置读取的本机密码，不写入 Git>'
```

生产迁移目录来自 Maven 自动打包的 `database/migrations/`，不要使用 Spring `ddl-auto` 替代 Flyway；schema `V1` 在空库上运行一次，第二次启动应记录 `No migration necessary`。

## 3. 运行与观察

```powershell
.\backend\mvnw.cmd -f backend\pom.xml -B -ntp package -DskipTests
java -jar backend\target\urban-commute-backend-0.1.0-SNAPSHOT.jar
```

新开一个 PowerShell 终端执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/api/v1/cities
```

空 `urban_commute` 的城市 API 返回 `data=[]`、`sourceType=database_catalog`、`datasetId=null`；`/health` 仍返回 UP + 带时区时间，**不代表数据库存在真实观测数据**。若城市非空，先审查该库来源再判断；不能以“页面能显示城市”证明数据真实性。

### MySQL 可复制核验 SQL（只读）

```sql
SELECT VERSION(), DATABASE();
SELECT installed_rank, version, success FROM flyway_schema_history ORDER BY installed_rank;
SELECT COUNT(*) AS city_count FROM city;
SELECT COUNT(*) AS source_count FROM dataset_registry;
SELECT COUNT(*) AS observation_count FROM traffic_observation;
SHOW CREATE TABLE traffic_observation;
```

## 4. 隔离合成数据与自动测试

**仅在已获授权且确认是独立新建的测试库** `urban_commute_ci` 执行回归；`ApiIntegrationTest` 在插入合成 fixture 前硬性校验 JDBC URL 包含该名称、`city` 表为空，避免误碰开发库。不要预先手动导入 `fixtures/s3-synthetic.sql` 后再运行这些 JUnit 测试，否则“初始空库”断言会拒绝执行。

```powershell
$env:DB_URL = 'jdbc:mysql://127.0.0.1:3306/urban_commute_ci?connectionTimeZone=UTC'
.\backend\mvnw.cmd -f backend\pom.xml -B -ntp verify
```

测试由真实 MySQL 插入合成数据，断言：空库 Flyway V1、重复 `migrate()` 不重复执行、外键/跨城市约束、速度负数 CHECK、观测记录重复键、`city` JOIN 查询、健康/异常响应。后续独立验证 JAR 和浏览器 E2E 需要保持该测试库中的 fixture，并有 Java21、Node24、Python3.11、Chromium 等依赖。CI 自动提供可丢弃 MySQL 8.4 service，可直接查 PR #3 的 Actions 和测试日志。

```powershell
cd frontend
npm ci
npm run type-check
npm test
npm run build
```

注意前端不会直接访问 SQL；Vue 通过 Vite 的代理调用 Spring Boot。浏览器对合成测试城市应显示 `synthetic_test`，空目录应显示 `database_catalog`。不得将本机步骤写成已验收，除非保留真实运行日志、MySQL 版本、数据库名称（不含凭据）、API 响应及浏览器证据。

## 5. 常见问题与责任边界

- `Communications link failure`：先检查 MySQL 8.4 服务、端口、独立库、账号；不直接修改防火墙或暴露公网端口。
- `Flyway checksum mismatch`：不要修改已应用的 V1 或使用 `repair` 掩盖差异；新增 V2 并履行迁移评审。
- `duplicate entry`：通常证明观测唯一键生效；先检查 dataset/target/time，不能用删除旧数据来绕过。
- `CHECK 3819/HY000`：MySQL 8.4 正常拒绝非法行；Spring JDBC 异常包装类型不一定是 `DataIntegrityViolationException`。
- `flyway upgrade recommended`：当前被 BOM 管理的 Flyway 有版本兼容性提示，实际执行通过也不能等于官方已保证所有 MySQL 8.4 行为；后续升级前应单独评审和复跑迁移。

流程：Controller 接收 HTTP → CityService 定义查询语义与来源 → CityRepository(JdbcTemplate) JOIN MySQL → City DTO/ResponseMeta → JSON → Vue。Flyway 在 Spring Boot 启动时负责**版本化建表**，不在浏览器请求时迁移表。
