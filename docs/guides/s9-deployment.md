# S9 安装、候选部署与恢复手册

范围：已授权 MySQL8.4 专用实例上的回环单机候选演示。不会安装系统服务、修改防火墙、接管未知端口或格式化持久 HDFS。没有引入 Compose：本机没有 Docker/Hadoop/Hive 入口，沿用既有隔离 CI 更可复现。正式业务库部署和公网部署仍需单独授权。

## 依赖和配置

Java21 / Spring Boot3.5.16 / Flyway11.20.3；Node24.19 / npm11；Python3.11；MySQL8.4（本机8.4.11）。Python 锁文件为 contracts、data-pipeline、ml 下的 requirements.lock.txt；Node 用 frontend/package-lock.json，Java 用 Maven Wrapper/pom.xml。已有环境优先复用。下列项目级依赖安装不修改全局环境，首次准备时执行；不得覆盖未知的现有虚拟环境。

```powershell
python -m venv ml/.venv
ml/.venv/Scripts/python.exe -m pip install -r contracts/requirements.lock.txt -r data-pipeline/requirements.lock.txt -r ml/requirements.lock.txt
npm.cmd ci --prefix frontend --no-audit --no-fund
```

`.env.example` 是模板，Spring/Python 不自动读取它。通过私有进程环境提供 DB_URL、DB_USER、DB_PASSWORD；DB_URL 必须指向已授权库，包含 `connectionTimeZone=UTC`。普通后端空库启动可迁移，ETL/数仓/ML 写入 CLI 仍只接受准备器核验过的 TEST_DB_* 隔离环境；不能以删掉门槛的方式宣称正式业务库部署已完成。

`COMMUTE_PYTHON` 指向项目虚拟环境绝对路径，`COMMUTE_BRIDGE` 指向 scripts/s8_adapter_bridge.py，`COMMUTE_PRIVATE_ROOT` 与 `COMMUTE_UPLOAD_TMP` 指向应用账号专用非公开目录（预先创建）。仅在需要创建显式演示用户时提供 bootstrap 用户/口令，绝无默认密码；详见 [S8指南](s8-operations.md)。bootstrap 只插入不存在的账号，不轮换口令，运行后从后续环境移除。DB及账号凭据不放命令行、VITE_*、PR、截图或 Git。

```powershell
ml/.venv/Scripts/python.exe scripts/s9_runtime.py --check
backend/mvnw.cmd -f backend/pom.xml -B -ntp package -DskipTests
npm.cmd run build --prefix frontend
ml/.venv/Scripts/python.exe scripts/s9_runtime.py --output backend/target/s9-candidate-NEW
```

`--check` 仅输出依赖/变量是否存在，不输出秘密，也不保证数据库授权或连通。启动器依次启动 Java→等待 /health→启动 production dist 的 Vite preview→等待首页；打印随机回环 URL。runtime.json 记录地址和所持子进程 PID，java.log/web.log 为本次日志。Ctrl+C 逆序停止所持 Web/Java，finally 写 stopped.json；绝不查找端口所有者并批量杀进程。若启动失败同样回收已启动子进程，保留日志。终端被系统强制关闭时，先核对 runtime.json、可执行路径和命令再人工停止，仅凭 PID 不可操作（可能复用）。

前端与 API 同源代理，preview.proxy 与开发代理共用回环目标校验。Vite preview 只用于受控演示，没有生产 TLS/守护进程/登录限速。MySQL 服务归已有环境所有；启动器不启动/停止它。HDFS/Hive 不影响已发布查询，只有数仓重算依赖它。

## 启动顺序、迁移与数据目录

1. 核验获授权的 MySQL 版本、回环监听、实例配置及账号。测试用 `scripts/s3_database.py` 新建随机 schema/单库账号，不复用/删除旧库。Windows MYSQL_CLIENT 可指向现有 mysql.exe；管理员口令仅在私有父进程设置 S3_ADMIN_PASSWORD，子进程被移除管理员口令。
2. Java 启动校验并执行 Flyway V1–V6。V1目录→V2观测/约束→V3 ETL审计→V4仓库发布→V5预测发布→V6权限管理。clean禁用，非空库不自动baseline，历史校验失败不repair。先备份并在隔离副本验证升级；本阶段未改历史迁移，也未新建 V7。
3. S8 inspect/confirm/convert/quality 的上传输出仅为研究输入。S5 正式 ETL 另需满足 data-pipeline/DATA_DICTIONARY.md，得到成功批次与逐条血缘；断连/异常不产生半批成功。目录 `data/raw/` 存真实外部输入，`data/private/` 存上传/私有dump；两者不进Git或artifacts。样例配置在各模块 examples，明确 synthetic_test。
4. S6 读取已成功 ETL 输出生成不可变包，真实 HDFS→Hive四层→导出→独立对账→原子切换 warehouse_current。Linux隔离CI使用 apache/hive4.1.0 的锁定digest，Hadoop3.4.1、Tez0.10.5/JRE17。没有连接本机未知集群；严禁为本机验证伪造 GITHUB_ACTIONS 或 format。复现命令/原有空目录CI授权见 [bigdata README](../../bigdata/README.md)。
5. S7 从经S6准入的CITY拥堵观测构建日序列，验证选模、独立测试、可信重训重算后原子切换 prediction_current；不依赖本次 Hive ADS、不改变 warehouse_current。速度/流量只走研究评估，不能发布到此指针。命令见 [ml README](../../ml/README.md)。最后 Java查询→Vue展示，查询不训练。

## 可复现验收与隔离备份恢复

先配置上述专用实例变量和 CONTRACT_PYTHON（Windows 项目 Python 的绝对路径）；所有输出路径须不存在。

```powershell
ml/.venv/Scripts/python.exe scripts/s3_database.py --output backend/target/s9-core-NEW-db.json -- ml/.venv/Scripts/python.exe scripts/s3_checks.py --output backend/target/s9-core-NEW
ml/.venv/Scripts/python.exe scripts/s3_database.py --output backend/target/s9-auth-NEW-db.json -- ml/.venv/Scripts/python.exe scripts/s8_checks.py --output backend/target/s9-auth-NEW
ml/.venv/Scripts/python.exe scripts/s3_database.py --with-restore-target --output backend/target/s9-model-NEW-db.json -- ml/.venv/Scripts/python.exe scripts/s7_checks.py --release-checks --output backend/target/s9-model-NEW
```

最后一条执行真实合成ETL、模型训练/重放、发布、HTTP/Chromium，并调用 s9_release_checks.py。准备器额外创建一个**空的、不同的随机schema和单库账号**；两库核对实际DATABASE/CURRENT_USER/server_uuid。备份前启动候选production dist，测4类API各40次/并发4（另各3次预热）及桌面/手机页面；停止源应用后 mysqldump `--single-transaction --no-tablespaces --skip-lock-tables --skip-add-locks --set-gtid-purged=OFF --skip-add-drop-table`，只导出本轮合成隔离库。mysql只导入预先核验为空的目标库，不DROP、不覆盖。

逐表将行按规范JSON排序并SHA256，对比所有表的行数和内容（含迁移历史、观测、任务、模型/评估/结果、权限、两类current指针），再核对源库未变；启动恢复库应用，Flyway校验、4类API data与源相等，再确认启动未改恢复表。数仓CI同样带 `--with-restore-target` 与 `s6_checks.py --release-checks`，验证实际Hive发布指针的恢复。两种发布指针在各自真实生产链路的隔离库中分别非空验证，不人为拼造一个混合发布库。

完整dump留在 `data/private/s9-backup-*/synthetic.sql`，不可进Git/附件/CI artifacts；即使是合成库也含密码哈希和上传提案。证据只保存dump大小/哈希、逐表内容哈希、指针和相等结论。备份不包含私有上传文件/ML权重/HDFS实体；完整系统恢复还须由负责人按许可单独备份这些目录及受控环境配置。这次演练验证 MySQL 逻辑恢复，不承诺整机灾难恢复、RPO/RTO 或生产备份可用性。

## 故障定位

| 现象 | 定位与恢复 |
|---|---|
| Java启动失败 | 查本轮java.log；确认目标库/权限/连接、迁移checksum，保留现场，不clean/repair |
| health200但业务503 | health仅进程探针；再查cities/predictions/warehouse真实请求与数据库服务，恢复连接后重查；不回退Mock |
| 前端502/空页 | 查web.log、dist与代理目标；只重启本次所持进程，不开放跨源或网络 |
| 401/403/404/405 | 按[权限表](s9-security.md)检查会话、角色、CSRF、精确路径与方法，不能通过放开默认规则解决 |
| 导入失败/重复 | 查审计requestId和任务错误码，修复原因后仅FAILED有界重试；RUNNING硬退出不能Web强改 |
| Hive失败 | 检查CI该HEAD原始HDFS/Beeline日志和逐字段对账；保留旧发布，不能把admission-only当实算 |
| 发布失败 | 保留STAGING/FAILED，按已有CLI同身份重试；current保留旧成功版本，不手改指针 |
| 恢复失败 | 停止目标副本服务并保留两个库/dump/日志，申请新空目标再演练；不删除既存业务数据 |

性能数据来自本机小合成库和温缓存，仅记录p50/p95/最大值、吞吐及页面加载时间，不能推导公网容量、真实大数据性能或SLA。最终实际数值见 S9 evidence/performance 与PR最终CI artifacts。
