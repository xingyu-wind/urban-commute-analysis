# S4 执行蓝图｜交通统计、ECharts 和地图大屏

状态：**SUBMITTED_FOR_INDEPENDENT_REVIEW**。本文件保留执行蓝图，实际功能、测试及交付以 [S4 报告](../stage-reports/S4.md) 为准；不代表已经 ACCEPTED。依据 2026-10-19 总规划 V3.0 和已核对的 S3 main `e487e647f8b2737f5377139e5a77c94a2daa27d0`。

分支：`feat/s4-traffic-dashboard`；禁止在独立总规划师裁定与明确合并授权前合并 PR。

## 第一段｜真实统计服务和可核对样本

- 沿用 MySQL 8.4 / Flyway V1/V2、Java 21 Spring JDBC、S3 `ApiResponse` 与 `ResponseMeta`。V1/V2 checksum 不变；必要结构变更只能新增 V3。
- 使用 `traffic_observation`：CITY 层只用于城市 KPI/趋势，REGION 只用于区域对比，ROAD 只用于道路排名。不得跨层级混算，不得把查询记录数当成独立车辆/通勤人数。
- 用户输入：cityId、UTC ISO8601 from/to（左闭右开）、series granularity=hour/day、roads 关键词与有限页码。非法输入返回沿用的 400 封套，不允许无界全表扫描。
- 优先四个 HTTP GET：`/api/v1/traffic/summary`、`/series`、`/regions`、`/roads`。明确城市归属、来源数据集与过滤规则：禁止 forecast/mock/simulation 混入历史观测，不能凭 registry 授权登记宣称授权已外部核验。
- 输出样本算术均值（speed km/h，congestion 0–10）、sampleCount、window、level、sourceType、datasetId、dataAsOf；无样本时 `count=0, mean=null, dataAsOf=null`，但不能把 mean 填零。跨时区归一化到 UTC。
- 同步 Java DTO、`contracts/openapi.yaml`、验证器、示例、前端 TypeScript 运行时校验，注意当前 `contracts/validate_contract.py` 把路径写死成 S2 两个接口，需要扩展而非禁用校验。

## 第二段｜可交互分析工作台和比赛大屏

- 保留已有 /health、城市列表、统一失败提示和请求 ID；新增城市+时段筛选、可追溯 KPI、ECharts 时序折线图、区域比较图、道路分页排序及响应式分析大屏。
- 图表只消费经过客户端校验的 Java API 结果；加载、无数据、错误、稀疏、合成测试醒目标识；城市/时段改变时取消或忽略过期请求。
- 保留 S3 前端已有回归语义，避免推翻现有 UI 的健康检查和城市来源说明。
- ECharts 优先使用 Apache ECharts Apache-2.0 的 npm 锁定版本，并通过正式 `npm ci` 验证。禁止外部未审 CDN 注入或硬编码 KPI。

## 第三段｜合规地图与完整回归

- `region.center_lat/center_lon/coordinate_system` 只有成对合法 WGS84 才可映射；`road_segment` 没有道路几何，不能从路名虚构位置。S4 fixture 中东区的坐标**纯为绘图测试值，不是真实区位**；西区无坐标必须省略地图点，文字计数提示。若有第三方在线底图，需先检查许可/额度/安全，不可自行接入收费或密钥。
- 尽可能选无密钥地图点位视图作为无外部依赖默认功能；对无合法坐标城市要有清晰空状态。
- 在隔离受控 MySQL schema 运行 `database/fixtures/s4-synthetic.sql`，不可在未知或非一次性数据库执行任何测试装载、清理、DROP、REPAIR。
- 真实 SQL 与以下独立手算核对，再更新唯一受控 CITY 观测让 HTTP 和 Chromium 页面指标跟随变化。补全边界日期、无观测、字段缺失、空坐标、区域/道路重复计数、防注入、停库 503、原 S3 回归、CI。
- 更新 README / 架构的旧 S3 与旧队友信息仅为事实纠正；保留 S1–S3 历史报告。
- 完成后真实提交 PR（未合并）、CI Run/Job、HEAD SHA、`docs/stage-reports/S4.md`、`docs/learning/S4-知识关联与项目实现说明.md`、SOLO_OWNER_REVIEW 与总规划师验收摘要。

## Fixture 独立预期值

查询统一窗口 `[2026-10-15T00:00:00Z, 2026-10-17T00:00:00Z)`、`cityId=s4-demo-city`，测试源 `s4-synthetic-v1`、`synthetic_test`：

| 层级 | 对象 | N | 平均速度 (km/h) | 拥堵指数均值 |
|---|---|---:|---:|---:|
| CITY | s4-demo-city | 3 | 36.00 | 5.00 |
| REGION | s4-demo-east | 2 | 25.00 | 6.00 |
| REGION | s4-demo-west | 1 | 50.00 | 2.00 |
| ROAD | s4-demo-road-a | 2 | 15.00 | 8.00 |
| ROAD | s4-demo-road-b | 1 | 40.00 | 3.00 |

城市时间趋势按 UTC 日期：2026-10-15：N=2、速度=36.00、指数=5.00；2026-10-16：N=1、速度=36.00、指数=5.00。按小时则三个独立 bucket。
城市样本量必须是 **3，不是 9**；区域与道路统计不得反向灌入 CITY KPI。

**受控变更证明**：仅把 CITY 中 `2026-10-15 09:00:00.000` 的 `avg_speed_kmh` 从 42 改为 60，在同一窗口重新查询，城市平均速度必须变成 **42.00 km/h**，城市 N 仍为 3，拥堵指数仍为 5.00。随后只对受控测试数据恢复 42，确认回到 36.00。浏览器必须从 API 同步反映这个变化，不允许只改 fixture 截图。

## 执行与安全门槛

- 不假定本机 MySQL 33067 仍在运行；先检查确实归项目持有的隔离实例和凭证。
- 不复制第三方 ZIP、未知许可数据、账号/凭证；不可操作未知进程或覆盖本机原有非托管文件。
- 不安装系统服务、不接入付费地图/账号、不外网部署、不强推、不合并、不提前实现 S5/S6/S7。
- 如果上述任一关键真实验收无法执行，明确标为 NOT_VERIFIED 或 BLOCKED，不能写成 SUCCESS。

本文件是**当前 Codex 执行说明**，不是替代真实 PR、运行日志和总规划师审查的完成证明。
