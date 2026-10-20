# 城市通勤数据分析及智能预测系统

本项目面向城市道路交通运行分析及通勤高峰代理指标预测，计划展示道路运行状态、时段统计和高峰趋势，为交通分析提供可解释的参考。

交通速度、流量、拥堵程度等仅作为候选代理指标，具体以合法数据源与字段定义为准。目前没有真实个人 OD（起讫点）或真实通勤人数数据，不将道路流量直接解释为通勤人数，不推断个人行程。

## 技术规划与当前状态

规划采用 Python 离线清洗、MySQL、HDFS/Hive、机器学习、Spring Boot 和 Vue。S2–S5 已正式 ACCEPTED，S5 PR #6 合并基线为 `99bf4f3`。S6 在此基础上接入 HDFS、Hive 四层数仓、ADS 安全发布与离线分析入口；实现范围、实测环境与独立验收状态见 [S6报告](docs/stage-reports/S6.md)。预测与权限系统尚未实施。

实际接口为 `GET /health`、`GET /api/v1/cities`、`/api/v1/traffic/{summary,series,regions,roads}`，以及 S6 `/api/v1/warehouse/metrics`；城市与历史观测统计来自 MySQL，离线接口读取经校验发布到 MySQL 的 Hive ADS。测试北京/上海标为 `synthetic_test`，不是交通实测；空/混合目录有独立标记，dataAsOf=null。报告与实际证据见 [S4 报告](docs/stage-reports/S4.md)，[启动与演示](docs/guides/s4-dashboard.md)，[知识关联说明](docs/learning/S4-知识关联与项目实现说明.md)。

S1 的 PR #1 已 Squash Merge，main 合并 SHA 为 `b47f0af593f4173d4a5e12af607c47a9343f64a5`。真实队友参与、交叉审核与双机协作的 `S1-COLLAB-DEBT` 仍未关闭；不把文档合并或单人测试当成双人协作补验。

当前入口见 [S5 ETL 使用说明](data-pipeline/README.md)、[标准化数据字典](data-pipeline/DATA_DICTIONARY.md)、[S5阶段报告](docs/stage-reports/S5.md) 和 [知识关联说明](docs/learning/S5-知识关联与项目实现说明.md)。S1–S4 报告保留历史事实，[架构规划](docs/architecture/overview.md)不表示后续模块已经实现。

S6 入口：[数仓使用说明](bigdata/README.md)、[知识关联与项目实现说明](docs/learning/S6-知识关联与项目实现说明.md)。城市工作台点击“打开 Hive 离线分析”，查看已发布版本及同窗口历史统计比较。

## 本地运行

先按 [S3 运行说明](docs/guides/s3-mysql.md) 准备已经授权的 MySQL 实例、库和私有进程变量。启动会执行迁移，不能指向未经授权的既有库。构建使用 Windows Maven Wrapper；集成测试必须通过隔离准备器，不直接在持久开发库运行 verify。

```powershell
.\backend\mvnw.cmd -f backend/pom.xml -B -ntp package -DskipTests
java -jar backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar
```

另开前端终端（Node.js 24 LTS，npm 使用 .cmd，不调整执行策略）：

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

默认 Java `127.0.0.1:8080`、Vite `127.0.0.1:5173`。浏览器访问 Vite，开发代理转发 `/health` 与 `/api`；后端保持本地监听，没有放宽 CORS。端口占用先诊断再选其他端口，不结束未知进程；替代端口通过前端 `DEV_BACKEND_URL` 进程配置统一设置。完整说明见 [frontend/README.md](frontend/README.md)。

## 目录职责

| 目录 | 职责 |
|---|---|
| backend/ | Spring Boot 城市与统计 API、参数校验、JDBC、DTO、错误处理与集成测试；未实现鉴权 |
| frontend/ | 服务与城市目录、ECharts 分析工作台、区域点位地图、大屏及浏览器验证 |
| database/ | MySQL 建表、迁移和字段说明 |
| data-pipeline/ | 数据校验、清洗、标准化和导入 |
| bigdata/ | HDFS、Hive 四层 SQL、独立对账与原子发布；[使用说明](bigdata/README.md) |
| ml/ | 特征、预测训练、评估及推理任务 |
| contracts/ | API、数据字段、指标口径和版本约定 |
| infra/ | 本地及部署环境配置模板 |
| docs/architecture/ | 系统架构和设计决策 |
| docs/guides/ | 开发、协作和操作指南 |
| docs/stage-reports/ | 阶段证据、进度和待办 |
| scripts/ | 可复用的项目检查和辅助脚本 |
| .github/ | Pull Request 模板及只读权限的全链路回归 CI |

## 角色与合作（按本轮确认的 V2.1 口径）

- 用户担任项目工程负责人，主导架构、共享契约、核心开发与集成，负责 Java 后端、Vue 前端和机器学习工作。
- 队友其他模块按后续明确的任务书分配，不沿用旧的 A/B 固定分工，不在本文件臆造具体负责人。
- 双方按已授权工作包异步推进；队友成果通过真实 PR 提交，由负责人审核、测试和整合。共享契约、数据边界和部署配置仍须协商。
- `S1-COLLAB-DEBT` 保持 OPEN：工具协助、负责人独立提交或单人测试不能替代真实队友参与、交叉 Review、对方 PR 和双机同步证据。

GitHub 分支协作入口见 [协作规范](docs/guides/collaboration.md) 和 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)。WP3-A 已初始化本地 Git，并通过21项代表性忽略规则测试；WP3-B 已完成首次提交并推送至本人名下的 [GitHub 私有仓库](https://github.com/xingyu-wind/urban-commute-analysis)。远程仅启用 Squash Merge，合并后自动删除分支。私有仓库分支保护受当前 GitHub 计划限制，尚未生效；稳定 main、功能分支和真实 PR 审核仍须双方遵守。详细验证见 [S1 报告](docs/stage-reports/S1.md)。

## 后续阶段与数据边界

S3 的运行命令、测试隔离与验收证据见 [S3 操作说明](docs/guides/s3-mysql.md) 和 [S3 报告](docs/stage-reports/S3.md)。S4 已随 PR #4 合并；S5 保持未合并并等待总规划师独立验收。S1 协作债务保持 OPEN。

本项目独立实现，不直接复刻或上传第三方毕业设计。参考资料须先核实授权；原始第三方 ZIP、未授权数据、真实凭据和个人数据不得纳入仓库。环境模板见 `.env.example`，复制后填写的本地 `.env` 不应提交。
