# S5 标准化数据字典（S6 输入契约 v1）

UTF-8 `normalized.csv`（表头、空字段表示 null）和 `normalized.json`（数组、JSON null）包含清洗合格且文件内去重的候选观测。**成功入库须同时检查 batch.json.status=SUCCEEDED**，不能仅凭标准化文件发布已落库数据。指标采用两位十进制定点字符串，MySQL 为 DECIMAL，Java API 为 JSON number。

| 字段 | 类型 | 约束、单位与含义 |
|---|---|---|
| dataset_id | string ≤64 | 来源及版本数据集；登记内容不可静默改写 |
| city_id | string ≤64 | 城市稳定 ID，必须在校验目录中 |
| target_type | enum | CITY、REGION、ROAD，大小写固定，分别统计 |
| target_id | string ≤64 | 对应城市、区域或路段 ID |
| region_id | string/null | REGION 时等于 target_id，其他层级为 null |
| road_segment_id | string/null | ROAD 时等于 target_id，其他层级为 null |
| observed_at | ISO8601 string | UTC，固定毫秒与 Z；2000–2099年 |
| collected_at | ISO8601 string | UTC，固定毫秒与 Z；不早于 observed_at |
| avg_speed_kmh | decimal string | 0–250 km/h，两位小数，ROUND_HALF_UP |
| congestion_index | decimal string | 0–10，两位小数；仅配置明确的同语义0–10或0–100量表 |

唯一键是 `(dataset_id,target_type,target_id,observed_at)`。全部内容（包括 collected_at 和归属）相同才去重，否则明确冲突。ROAD 的所属区域通过 road_segment.region_id 关联，观测的 region_id 保持 null；路段和区域必须同城。城市可承载多个数据集，聚合必须同时按 dataset_id、层级分组。均值为样本算术平均，不是车辆或通勤人数。

原始输入七个必填逻辑字段：city_id、target_type、target_id、observed_at、collected_at、speed、congestion；具体列名由配置 fields 映射。不补零、不插值、不做未声明的去异常均值。文件内同键同值后续行记 duplicate，异值后续行记 rejected，保留首个合格值。数据库异值则整批观测回滚。

`source.json` 包含 pipeline_version、完整配置、数据集版本、许可核查依据、时间覆盖、粒度、原字段字典、时区和坐标系。`quality.json` 包含原始字节 SHA-256、配置快照 SHA-256、数量及拒绝/重复行号（首条数据记录算1，不是物理文本行）；`rejections.json` 含原始记录和原因。`batch.json` 包含真实数据库状态、attempts、写入/已存在/冲突数量、具体冲突键和差异字段、开始/结束 UTC 时间。etl_batch_observation 逐条关联实际观测。

CSV 允许未映射额外列，但映射字段必须全在表头内，重复表头拒绝，超宽记录拒绝。JSON 顶层是对象数组。原始 BOM 和换行变化会改变 file_sha256；相同标准化内容仍按数据库唯一键去重。

区域坐标只接受合法成对 WGS84，经纬度不推算；缺失保持 null。合成点位不是实采位置。无投影转换或道路几何。已提交 [S6 示例输出](examples/standardized/normalized.csv) 全为 synthetic_test，只供后续设计 ODS/DWD 输入；本阶段没有运行 HDFS/Hive。
