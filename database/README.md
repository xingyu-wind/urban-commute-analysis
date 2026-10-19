# S3 数据库模式｜MySQL 8.4 / Flyway

S3 采用全新 **MySQL 8.4** 业务模式，不复用原 ZIP 的任何建表或插入脚本。唯一结构源：`migrations/V1__commute_core.sql`（编译时纳入后端 classpath:/db/migration）。迁移只做 `CREATE TABLE`，**不插入样例、DROP、TRUNCATE 或自动清库**。

## 字段字典与关联

| 表 | 主键 | 核心字段 / 单位 | 约束与关系 |
| --- | --- | --- | --- |
| `dataset_registry` | `dataset_id VARCHAR(64)` | `source_name`、`source_type`、`license_status`、`dataset_version`、许可链接和登记时间 | 来源类型和许可状态 CHECK；`authorized_live` 必须 `authorized` |
| `city` | `id VARCHAR(64)` | `name`、`dataset_id`、`created_at` | `dataset_id` FK；城市 ID 小写 kebab-case |
| `region` | `id VARCHAR(64)` | `city_id`、`name`、可选中心点经纬度 | (id,city_id) 复合唯一；WGS84 经纬度范围与三字段同时存在 CHECK |
| `road_segment` | `id VARCHAR(64)` | `city_id`、可选 `region_id`、`name` | 所属区域必须与路段同城；城市内路段名唯一 |
| `traffic_observation` | `id BIGINT` | `dataset_id`、`city_id`、`target_type/target_id`、`observed_at`、`collected_at`、`avg_speed_kmh`、`congestion_index` | target-type 与关联 ID 一致；速度 0～250 km/h、指数 0～10；同源目标时刻唯一 |

时间字段为 **DATETIME(3)，按 UTC 语义存储**；MySQL DATETIME 本身不携带时区，后续 ETL 必须显式转换为 UTC。数据库不声称这些是个人通勤人次、OD 或真实车辆计数。

### 来源类型（不可混淆）

- `dev_seed`：前端或开发调试样例（S3 不自动装载）。
- `synthetic_test`：明确人工构造的合成测试样例。
- `historical_snapshot`：历史快照，不能宣称实时；需审查授权。
- `authorized_live`：有可追溯授权来源的采集数据，数据库强制许可状态为 authorized。
- `simulation` / `mock` / `forecast`：模拟、模拟接口和模型预测，不得充当真实观测。

`dataset_registry` 是数据来源的登记记录，不是版权合规审计本身；填写 `authorized` 仍需要可核查的外部证明。本阶段只提供合成数据，不提供“真实城市实时交通”演示。

### 模式、索引和幂等性

- `traffic_observation` 的 `uq_obs_dataset_target_time` 去重键防止同一来源、同一目标、同一观测时刻重复导入。
- `idx_obs_city_time`、`idx_obs_region_time`、`idx_obs_road_time` 支持后续按时空维度读取。
- City Repository 将 `city` 与 `dataset_registry` JOIN 返回稳定 id/name 和列表 provenance；当前 API 只有城市目录，只做来源说明，不暴露未完成的交通 KPI。
- MySQL 8.4.11 实测约束、重复迁移和空库结构由 S3 GitHub Actions 流水线证据记录；本地数据库仍须单独验收。

可复现步骤与风险边界：`docs/guides/s3-mysql.md`。合成样例：`fixtures/s3-synthetic.sql`（不可提前导入将运行集成测试的空库）。
