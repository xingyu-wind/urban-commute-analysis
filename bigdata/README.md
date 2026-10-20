# S6 Hadoop / HDFS / Hive 离线数仓

数据链路：S5 成功 ETL 报告 + MySQL 逐条血缘核验 → HDFS → Hive ODS/DWD/DWS/ADS → 独立 Decimal 对账 → MySQL 待发布批次 → 事务切换可见版本 → Java API → Vue 离线比较。

## 文件与统计口径

| 文件 | 职责 |
|---|---|
| `warehouse.py` | 读取 S5 normalized.json、source.json、batch.json；在数据库一致性快照中核验 SUCCEEDED、完整候选内容和逐条血缘；生成 ODS TSV 和带 SHA 的不可变输入包；独立计算、ADS 逐字段对账、发布及回读 |
| `sql/warehouse.hql` | Hive 实际建表、分区、写入、聚合、层间对账和 HDFS 导出；不接收 Python 聚合结果 |
| `runner/isolated-hive.sh` | 临时容器配置、空目录 format 门槛、HDFS 文件往返、Beeline/Tez 执行和重跑、非法输入断言、原始日志 |
| `run.py` | snapshot / reconcile / publish CLI |
| `../scripts/s6_checks.py` | 成功 ETL、跨批去重、边界样例、真实容器、失败发布与恢复、HTTP/Chromium 自动验证 |
| `../database/migrations/V4__warehouse_publication.sql` | 新增发布头、指标明细、当前版本指针；V1–V3 不改动 |

ODS 分区为 `snapshot_id`，每行保留观测 ID、标准化字段、dataset_version、source_type、source_sha256、batch_id 及道路目录区域。候选文件的完整行集合必须与该成功批次实际落库血缘完全一致。标准化文件缺少成功批次证明时拒绝；不把文件存在视为提交成功。HDFS `/s6/manifests/<snapshot>` 保留窗口、SQL/输入 SHA 和批次身份。

DWD 按唯一观测去重，保留各 batch ID 与来源快照 SHA 数组，按 UTC observed_date 分区。多次 ETL 中同一观测只统计一次；不同内容不得静默覆盖。ROAD 区域来自 road_segment 目录，同城约束由 MySQL 外键及 S5 校验保证，ROAD 的原始 region_id 仍为 null。

DWS 按 dataset_id、dataset_version、source_type、city_id、target_type、target_id、道路目录区域、UTC 小时聚合，保留 `sample_count`、`speed_sum`、`congestion_sum`、最早/最晚观测时间；按日期分区。ADS 由这些总和/数量生成 HOUR、DAY、WINDOW 三种粒度。**不能跨粒度相加样本数**，每一种粒度覆盖相同的去重输入。跨城市/数据集的控制总和仅用于审计，不是混合交通统计。

窗口是明确的 UTC `[from,to)`，窗口外记录即使已经 ETL 成功也不进入数仓。小时/日桶也只包含窗口内观测，部分窗口不宣称覆盖完整小时/日期。速度 DECIMAL(6,2)、拥堵 DECIMAL(4,2)、总和 DECIMAL(24,2)，最终 SUM/COUNT 后 ROUND_HALF_UP 到两位；不平均已舍入均值。当前 S5 输入双指标均须有效，缺失在 ETL 拒绝，数仓不补零；无观测的 API 返回空列表，页面显示未发布状态，不生成虚假零值。

## 可复现验证

正式重型入口为 [S6 workflow](../.github/workflows/s6-warehouse.yml)。使用官方 `apache/hive:4.1.0` 并锁定镜像 digest，容器内 Hadoop 3.4.1、Hive 4.1.0、Tez 0.10.5、JRE17；宿主 Java21 负责 Spring Boot。单 NameNode/DataNode、Tez local mode、独立 Derby Metastore；是真实 HDFS 和 Hive 运算，未声称验证多节点集群或 YARN。

Linux runner 已安装 Docker，按项目锁文件安装 Python、Node 依赖后：

```bash
# 管理员凭据仅通过已授权实例的进程环境 S3_ADMIN_PASSWORD 提供。
# 只有本项目获授权的临时 GitHub Actions 环境可以执行空目录 format。
python scripts/s3_database.py --output backend/target/s6-db-new.json -- \
  python scripts/s6_checks.py --output backend/target/s6-new
```

需要 `GITHUB_ACTIONS=true` 和 `S6_ALLOW_EMPTY_FORMAT=yes`，以及实际位于 `/tmp/s6-warehouse.*` 下新建且为空的 NameNode 目录。脚本不使用 `-force`、不挂载已有 HDFS、不发布宿主端口、不使用 privileged。禁止为了在其他机器运行而虚报 GITHUB_ACTIONS；新的环境授权后应单独调整门槛。

Windows 不安装系统功能也可验证准入、边界与独立计算：

```powershell
contracts/.venv/Scripts/python.exe scripts/s3_database.py --output backend/target/s6-local-db-new.json -- contracts/.venv/Scripts/python.exe scripts/s6_checks.py --admission-only --output backend/target/s6-local-new
```

此模式明确写 `scope=mysql-admission-only`，**不能作为 Hive 实算证据**。需要在 Windows 验证已导出的真实 Hive 结果时，使用 `--hive-evidence <从CI下载的hive目录>`；会重新在新 MySQL 库执行 ETL、逐值对账、发布、HTTP 和浏览器，summary 明示复用来源，不假称本机运行 HDFS。

## 单步 CLI 与发布

下列命令需由 S3 准备器产生的私有 TEST_DB_* 子进程环境调用，沿用 S5 对随机隔离库、单库账号、服务器 UUID、MySQL8.4 的实际身份门槛。当前不支持未经授权的普通持久库加载；不回退到管理员凭据或 DB_URL。

```bash
python bigdata/run.py snapshot --batch-dir <成功S5输出1> --batch-dir <成功S5输出2> \
  --from 2026-10-15T00:00:00.000Z --to 2026-10-17T00:00:00.000Z --output <新输入目录>
python bigdata/run.py reconcile --bundle <输入目录> --ads <Hive导出的TSV>
python bigdata/run.py publish --bundle <输入目录> --ads <Hive导出的TSV> --release <发布ID>
```

发布先比较 Hive 和独立 Decimal 计算的所有行、样本数、总和、均值、覆盖、唯一性；校验输入 SHA 和目标库批次身份。全局发布命名锁串行化写入，持久化 STAGING 头；指标插入、完整 MySQL 回读比对、PUBLISHED 状态及 current 指针在同一事务提交。异常回滚明细和指针，头记 FAILED；重试相同身份安全恢复。硬退出可留下 STAGING，事务由 MySQL 回滚，下一锁持有者可重试。相同发布 ID 不允许换身份，旧快照不能覆盖较新快照。

发布身份使用排序、定点规范化 ADS 内容 SHA，避免 Hive 物理输出顺序变化导致虚假新版本；原始 TSV、原始文件 SHA 和日志仍由验证证据保留。成功发布的旧 ID 重放返回 reused，不倒退 current 指针。API 使用 repeatable-read，只读取 current JOIN PUBLISHED；新失败批次不会遮挡旧发布。

`GET /api/v1/warehouse/metrics?cityId=<id>&datasetId=<可选>&grain=WINDOW`（也支持 DAY/HOUR），返回发布版本、UTC 窗口、来源、成功批次/源快照 SHA、总和/样本数及指标。无发布时 release=null、items=[]；单次上限10000行，超过时拒绝。Vue 在城市工作台点击“打开 Hive 离线分析”，可按数据集查询，展示 CITY/REGION/ROAD 并使用同窗口请求既有 MySQL CITY 历史统计。所有数值由 API 查询，无静态 KPI、Mock 或预测。

完整结果与限制见 [S6报告](../docs/stage-reports/S6.md)及其证据索引。来源全部是 synthetic_test，不代表真实交通采集、实时状态或真实通勤人数。
