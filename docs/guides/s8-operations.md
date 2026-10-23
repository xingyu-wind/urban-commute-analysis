# S8 认证、导入与运行管理

使用正式 V3.2。S7/S8 已由总规划师验收并合并，最终记录见 [PR #9](https://github.com/xingyu-wind/urban-commute-analysis/pull/9)；历史报告与 [门禁记录](../stage-reports/evidence/S8/gate-waiver.md) 不追溯改写。当前 S9 部署入口见 [安装部署手册](s9-deployment.md)，权限收口见 [S9权限清单](s9-security.md)。仍只允许受控回环部署。

## 本机启动

沿用 [S3 隔离与数据库指南](s3-mysql.md)。应用启动会执行新增 V6 迁移，只连接已授权目标库；V1–V5 不改写。运行目录为仓库根目录。后端与 Vite 均保持回环监听，通过 Vite `/api` 同源代理访问，没有开放跨源凭证访问。

使用 Java 21、Node 24、MySQL 8.4 和现有项目科学计算虚拟环境。后端 Maven 自动解析 Boot 管理的 Spring Security 6.5 依赖；Python 沿用 `data-pipeline/requirements.lock.txt`、`ml/requirements.lock.txt`。本机设 `COMMUTE_PYTHON` 为 `ml/.venv/Scripts/python.exe` 的绝对路径，`COMMUTE_BRIDGE` 为 `scripts/s8_adapter_bridge.py` 的绝对路径；Linux 使用对应项目虚拟环境，不安装全局包。

`COMMUTE_PRIVATE_ROOT` 指向仅应用账号可访问的非公开目录，默认 `data/private/s8`，被 Git 忽略，不在静态资源目录。不要把目录映射到 Web 服务或 CI artifact。Unix 设置根目录 0700；Windows 沿用用户私有目录 ACL，部署负责人须确保其他系统用户没有访问权。可显式设置 `COMMUTE_UPLOAD_TMP` 为事先准备的专用非公开临时目录；默认使用操作系统临时目录，Servlet 请求结束后清理 multipart 临时文件。数据库里的原始提案样例也仅能经管理员上传响应访问，不出现在只读任务投影、审计或证据中。

默认没有任何可登录账号。需要账号时，通过私有进程环境显式提供 `COMMUTE_BOOTSTRAP_ADMIN_USER` / `COMMUTE_BOOTSTRAP_ADMIN_PASSWORD`，以及可选的 READER 同名变量。账号限 3–64 位 ASCII 字母、数字、下划线或短横线；口令限 16–72 字符，建议使用 24 字节以上随机生成的 ASCII 口令，BCrypt cost 12。密码不放命令参数、源码、`.env.example`、截图或 PR。启动器只 INSERT 不存在的账号，绝不覆盖已有账号；启动后应移除 bootstrap 环境。账号停用/密码轮换由授权数据库管理员处理，本阶段不提供账户 CRUD 或自动轮换。现有会话最长空闲 20 分钟，服务重启失效；禁用账号不会立即撤销已存在的内存会话。

HTTP 回环开发 Cookie 为 HttpOnly、SameSite=Strict、无持久化记住登录，仅 Cookie 追踪会话，登录更换会话 ID，退出使会话失效。只有将来获得 HTTPS 部署授权后才设置 `COMMUTE_COOKIE_SECURE=true`；本阶段未部署公网。CSRF 使用服务端会话 token 和 Spring 的掩码请求 token，登录/退出后必须重新获取。前端不使用 localStorage 储存身份凭证。

## 实际操作

导航“数据管理”打开登录面板。ADMIN 可上传、确认、执行及重试；READER 只能查看任务。原有分析仍为公开只读，不要求登录。

1. 上传有权使用的 CSV 或平面 JSON 对象数组。最多 2 MiB、20,000 行、400 列；仅 ASCII 安全文件名与匹配的文件类型。文件实际解析必需成功，扩展名或 Content-Type 声明不能替代内容验证。拒绝路径、二进制、空表、列宽异常、重复 JSON 键和嵌套 JSON。服务器使用 UUID 目录和固定文件名，绝不使用上传名称拼接路径。
2. 展开字段建议，核对所有不确定项，在完整审查 JSON 输入明确配置。结构可参考仓库原有 `ml/examples/synthetic-review.json`，但必须将来源、许可、城市/域、字段、时间格式、时区、频率、目标、单位、空间粒度和缺失策略改为实际含义。没有自动批准模板。确认请求只接受 review 和精确提案哈希；操作者由登录会话取得，时间/配置哈希由 S7 和数据库记录。确认后映射不可覆盖；修订须新上传、新确认。
3. 执行导入校验。服务器调用既有 `convert` / `suitability`；文件哈希变化、未验证真实来源权利或 NOT_EVALUABLE 均失败。成功生成隔离的 `traffic-series-v1` 标准化研究输入和适用性结果，不自动发布交通观测、训练模型或切换指针。S5 正式观测导入与 S6/S7 发布继续使用原有受控 CLI 及其完整性准入；速度不会被伪装成拥堵指数。
4. 任务卡显示状态和失败码；展开追溯查看任务、批次、输入/输出/映射版本和操作者。ETL/Hive/ML 读取原有表，历史 CLI 任务没有伪造 Web 操作者。只允许 FAILED 的 S8 导入任务重试，最多总计三次；数据库唯一键与状态比较更新防止重复执行。先修复真实故障，再重试。成功任务、运行任务或达到上限的任务返回 409；合法但不存在的导入 UUID 返回 404，畸形 UUID 返回 400。

## 安全故障排查

- 401：尚未登录、会话过期或已退出。403：只读用户越权，或已登录用户缺少/提交陈旧 CSRF token。没有登录页重定向、Basic Auth 或默认管理员。
- 400/413/415/422：名称或参数不合法、过大、类型不符、内容/映射/许可/适用性拒绝。UPLOAD 失败会清理其隔离文件夹；导入失败清理规范化输出，但保留已审查原件和确认记录，供核查与安全重试。
- WORKER_BUSY/UNAVAILABLE/TIMEOUT：固定 Python 进程不可用或超过 45 秒；检查受控 Python 环境与部署配置。最多同时两个适配进程，无 shell 命令拼接，子进程移除数据库口令及 bootstrap 等秘密环境，解析异常不回传原始片段。
- 进程硬退出后的 RUNNING 保持不可重试，避免猜测是否已完成。管理员需离线核对私有输入/输出和任务状态；本阶段不提供自动租约接管、强制状态修改或任务终止接口。
- `security_audit` 保存 UTC 时间、会话操作者、动作、对象、结果和请求 ID。`managed_import` / `managed_job` 保存确认、哈希和状态，不存口令、Cookie、CSRF token 或任意命令。审计库不可写时，正常管理写操作失败；登录审计失败立即撤销刚建立的认证并返回503。退出审计失败只记录无秘密告警，仍完成会话失效，不能让审计故障阻止退出。拒绝请求始终保持拒绝。
- 上传成功后文件保留供追溯；没有自动保留期清理。大规模部署前需授权后补容量/保留策略、登录限速及多节点会话方案。本阶段不声称已具备公网生产运维能力。

## 复现安全测试

由受控父进程设置 S3_ADMIN_PASSWORD / MYSQL_CLIENT 等现有隔离配置，调用：

```text
python scripts/s3_database.py --output backend/target/s8-db-NEW.json -- python scripts/s8_checks.py --output backend/target/s8-NEW
```

实际 Python 必须包含已有 ML、ETL、OpenAPI 验证依赖，先构建最新可执行 JAR；Windows 可替换为 `ml/.venv/Scripts/python.exe`。输出路径必须从未存在。脚本只创建随机测试 schema/单库账号，不 DROP、不清理旧库；私有合成文件与随机口令留在忽略目录/子进程环境，证据只输出 HTTP 状态/安全错误封套、哈希、数据库状态、清理计数及 Chromium 结果。测试把空闲会话设置为一分钟并真实等到过期，正式默认仍为二十分钟。

Spring 行为依据：[CSRF](https://docs.spring.io/spring-security/reference/6.5/servlet/exploits/csrf.html)、[退出](https://docs.spring.io/spring-security/reference/servlet/authentication/logout.html)。这些文档解释设计，测试证据另见 [S8 报告](../stage-reports/S8.md)。
