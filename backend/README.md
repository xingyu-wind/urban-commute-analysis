# 后端模块

S2-WP3 实现 Java 21 / Spring Boot 3.5.16 的两个真实 HTTP 接口，遵守 [OpenAPI 契约](../contracts/openapi.yaml)。当前仅内存开发样例；没有数据库、Security、Hadoop/Hive、预测模型或 Vue 工程。

## 目录与职责

| 路径 | 职责 |
|---|---|
| `pom.xml` | 固定 Boot 3.5.16、Java 21；Web、Validation、测试依赖 |
| `mvnw` / `mvnw.cmd` / `.mvn/wrapper` | 官方 Wrapper 3.3.4 only-script，Maven 3.9.16，分发包 SHA-256 固定 |
| `src/main/java/com/urbancommute/UrbanCommuteApplication.java` | 启动类 |
| `api/` | 健康、城市、统一响应和 meta DTO；显式保留 null |
| `service/CityService.java` | 不可变内存开发种子与空列表配置 |
| `web/ApiController.java` | 两条 GET 路由及无请求参数/请求体约束 |
| `web/RequestIdFilter.java` | 每请求 UUID、响应头、日志关联；不信任客户端传入 ID |
| `web/ApiExceptionHandler.java` | Spring MVC 错误和服务异常的安全封套；保留 Allow 等框架头 |
| `src/main/resources/application.yaml` | 默认仅绑定 127.0.0.1:8080，不包含凭据 |
| `src/test/java/com/urbancommute/ApiIntegrationTest.java` | MockMvc、真实随机端口 HTTP、空列表/故障替身、序列化和 Bean Validation 测试 |
| `scripts/verify_http.py` | 独立启动已打包 JAR，抓取真实响应并校验实际 OpenAPI Schema |

## Windows 构建与运行

在 `backend` 目录执行。需要 Java 21；环境变量只对当前终端设置，不修改用户或系统配置：

```powershell
# 已有 JAVA_HOME 时保留；本机 WP1 的 JDK 位于以下路径。
$env:JAVA_HOME = 'D:\WindXingyu\Apps\Java\jdk-21.0.12.1+1'
# 若旧终端未继承 WP1 已有 Java 参数，从现有用户配置读取，不写入配置。
$env:JDK_JAVA_OPTIONS = [Environment]::GetEnvironmentVariable('JDK_JAVA_OPTIONS', 'User')
$env:MAVEN_USER_HOME = 'D:\WindXingyu\Temp\urban-commute-S2-WP3\maven-user-home'
.\mvnw.cmd -v
.\mvnw.cmd -B -ntp '-Dmaven.repo.local=D:\WindXingyu\Temp\urban-commute-S2-WP3\maven-repository' verify
& "$env:JAVA_HOME\bin\java.exe" -jar target\urban-commute-backend-0.1.0-SNAPSHOT.jar
```

其他机器可使用自己的 JDK 和缓存路径；仓库未固定本机路径。`MAVEN_USER_HOME` 控制 Wrapper 下载目录，`maven.repo.local` 控制 Maven 依赖缓存。保留 WP1 的 `jdk.net.unixdomain.tmpdir` 参数以避免本机默认临时目录的 NIO 问题；不要修改代理、执行策略或全局环境来解决普通构建错误。

手动启动前先检查 8080 是否已被使用：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue
# 若被占用，先检查 OwningProcess，不终止其他程序；可显式使用 --server.port=8081。
```

默认访问 `http://127.0.0.1:8080/health`、`http://127.0.0.1:8080/api/v1/cities`。手动前台运行时用该终端 Ctrl+C 停止自己的服务。不要用进程名批量终止 Java。

空列表使用真实配置，不增加额外接口：

```powershell
& "$env:JAVA_HOME\bin\java.exe" -jar target\urban-commute-backend-0.1.0-SNAPSHOT.jar --commute.cities.seed-enabled=false
```

## 接口与错误边界

- `/health`：HTTP 200，`status=UP`，请求处理时动态生成 UTC ISO 8601 时间。不声明数据库或机器学习模块健康。
- `/api/v1/cities`：HTTP 200、`code=OK`；String ID；`dataAsOf=null`、`sourceType=dev_seed`、`datasetId=dev-seed-cities-v1`。配置关闭种子时 `data=[]`，meta 仍完整。
- 每个请求的 `X-Request-Id` 与封套 `meta.requestId` 一致；健康响应仅在头中包含 ID。日志以该 UUID 关联请求，不复用固定样例 UUID。
- 两个 GET 不接受查询参数或请求体；收到这些内容返回 400 `BAD_REQUEST`，不静默接受尚未定义的分页或筛选功能。
- Spring MVC 未映射路径 / 不支持方法 / 不接受 JSON 分别返回 404/405/406；405 保留 `Allow`。406 由真实 `produces=application/json` 协商失败触发，错误说明按契约输出 JSON，状态仍为 406，不把成功结果强制转换成 XML 或改为 200。
- 未预期服务异常返回 500；明确不可用异常返回 503。客户端只收到固定安全消息，堆栈仅留服务端日志。不提供触发故障的生产路由。
- 自动化测试用 `MockitoSpyBean` 替代 Service 的单次结果/异常，验证空列表、500、503。这些故障替身仅存在于测试，不等于真实系统当前依赖故障。
- Tomcat 在 Servlet/MVC 之前拒绝的畸形 HTTP、连接中断等容器错误不承诺本业务 JSON 封套；本阶段没有统一替换 Servlet 容器的协议错误页面。

## 真实 HTTP 与契约验证

先执行 Wrapper `verify` 构建，再从仓库根目录使用 WP2 的隔离 Python：

```powershell
.\contracts\.venv\Scripts\python.exe backend\scripts\verify_http.py
```

脚本需要当前进程的 `JAVA_HOME`，并继承现有 `JDK_JAVA_OPTIONS`。它两次启动生产 JAR（普通种子及禁用种子），显式 `--server.port=0` 请求系统分配可用端口，避免抢占其他服务。没有测试服务替身。

原始 JSON、HTTP 状态、必要响应头、启动命令、PID、停止结果和驱动退出码保存到 `backend/target/live-http-evidence`。输出目录已存在时脚本拒绝覆盖；复测用 `--output` 指向一个新的目录。正常结果应退出 0。脚本在 `finally` 中只停止自己持有的 Popen 子进程；Windows 主动终止服务的退出码可能非零，必须与验证驱动退出码区分。

JUnit 的真实随机端口响应另外保存在 `target/http-test-evidence`，其中明确标记空列表/500/503 使用测试替身。测试报告在 `target/surefire-reports`。这些构建证据与缓存均被 Git 忽略；阶段报告保留可审阅的响应快照和实测结果。

框架错误处理依据：[Spring ResponseEntityExceptionHandler](https://docs.spring.io/spring-framework/docs/6.2.8/javadoc-api/org/springframework/web/servlet/mvc/method/annotation/ResponseEntityExceptionHandler.html)。Wrapper 来源：[Apache Maven Wrapper](https://maven.apache.org/tools/wrapper/index.html)。
