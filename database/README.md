# 数据库模式｜MySQL 8.4 / Flyway

S3 采用全新 **MySQL 8.4** 业务模式，不复用原 ZIP 的任何建表或插入脚本。结构源：`migrations/V1__commute_core.sql`（历史不变）和 `migrations/V2__strengthen_core_constraints.sql`（编译时纳入后端 classpath:/db/migration）。迁移仅建表/调整约束与索引，不插入样例、不删表、不清库。V2 的 DROP CHECK / DROP INDEX 仅替换约束或索引，不删除业务行。

S5新增 `migrations/V3__etl_audit.sql`，由现有Java启动/Flyway统一执行。etl_source保存解析版本和完整来源配置快照；etl_batch保存文件哈希、质量数量、落库数量、状态、时间和冲突明细；etl_rejection保存清洗拒绝；etl_batch_observation逐条关联WRITTEN/EXISTING观测。Python导入器仅操作已迁移的S3新隔离库，V1/V2校验和不变。[ETL事务及操作说明](../data-pipeline/README.md)与[标准化字典](../data-pipeline/DATA_DICTIONARY.md)。

## 字段字典与关联

| 表 | 主键 | 核心字段 / 单位 | 约束与关系 |
| --- | --- | --- | --- |
| `dataset_registry` | `dataset_id VARCHAR(64)` | `source_name`、`source_type`、`license_status`、`dataset_version`、许可链接和登记时间 | 来源类型和许可状态大小写严格；历史/实时必须 authorized，生成来源必须 not_applicable |
| `city` | `id VARCHAR(64)` | `name`、`dataset_id`、`created_at` | `dataset_id` FK；城市 ID 小写 kebab-case |
| `region` | `id VARCHAR(64)` | `city_id`、`name`、可选中心点经纬度 | (id,city_id) 复合唯一；WGS84 经纬度范围与三字段同时存在 CHECK |
| `road_segment` | `id VARCHAR(64)` | `city_id`、可选 `region_id`、`name` | 所属区域必须与路段同城；同城路段名允许重复，稳定路段 ID 唯一 |
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
- City Repository 将 `city` 与 `dataset_registry` JOIN 返回稳定 id/name 和列表 provenance；S4已增加分层交通统计API，S5通过Python导入实际改变其观测结果。
- MySQL 8.4.11 实测约束、重复迁移和空库结构由 S3 GitHub Actions 流水线证据记录；Windows 实测证据见 S3 阶段报告。

可复现步骤与风险边界：`docs/guides/s3-mysql.md`。合成样例：`fixtures/s3-synthetic.sql`（不可提前导入将运行集成测试的空库）。

V2 修复坐标部分 NULL、城市 ID 大小写/空白名称、采集不早于观测时间等约束。速度单位 km/h，范围 0～250；拥堵指数为本项目标准化 0～10，尚无外部数据源的换算承诺。两指标必填；缺失或其他量纲不得填零冒充，S4 数据接入前需明确转换与拒绝策略。观测时间为该指标的时间点，S3 不声称已支持不同采样窗口的混合统计。

来源登记枚举覆盖合成、模拟和预测，但 S3 不提供预测结果存储契约；traffic_observation 的 collected_at 必须不早于 observed_at，不能把它直接当作未来预测结果表。后续真实观测统计必须 JOIN 来源登记并显式筛选授权历史/实时来源，不能混合聚合。登记为 authorized 仍不能替代外部授权证明。
