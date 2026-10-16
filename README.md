# 城市通勤数据分析及智能预测系统

本项目面向城市道路交通运行分析及通勤高峰代理指标预测，计划展示道路运行状态、时段统计和高峰趋势，为交通分析提供可解释的参考。

交通速度、流量、拥堵程度等仅作为候选代理指标，具体以合法数据源与字段定义为准。目前没有真实个人 OD（起讫点）或真实通勤人数数据，不将道路流量直接解释为通勤人数，不推断个人行程。

## 技术规划与当前状态

规划采用 Python 离线清洗、MySQL 结构化存储、HDFS/Hive 历史数据分析、Python 机器学习、Spring Boot API 和 Vue 前端。技术版本、数据授权、指标口径和预测方法须在后续阶段确认。

当前处于 S1 工程准备阶段，仅建立目录、职责说明与协作规范；尚无可运行的正式业务代码，未启动系统、未执行业务测试。架构和实现安排见 [架构规划](docs/architecture/overview.md)，阶段进度见 [S1 报告](docs/stage-reports/S1.md)。

## 目录职责

| 目录 | 职责 |
|---|---|
| backend/ | Spring Boot 查询 API、权限及服务层 |
| frontend/ | Vue 页面、图表及 API 调用 |
| database/ | MySQL 建表、迁移和字段说明 |
| data-pipeline/ | 数据校验、清洗、标准化和导入 |
| bigdata/ | HDFS 分区规划、Hive DDL 与离线聚合 |
| ml/ | 特征、预测训练、评估及推理任务 |
| contracts/ | API、数据字段、指标口径和版本约定 |
| infra/ | 本地及部署环境配置模板 |
| docs/architecture/ | 系统架构和设计决策 |
| docs/guides/ | 开发、协作和操作指南 |
| docs/stage-reports/ | 阶段证据、进度和待办 |
| scripts/ | 可复用的项目检查和辅助脚本 |
| .github/ | Pull Request 模板及未来协作自动化 |

## 双人合作

角色 A 初步负责数据链路、数据库与后端，角色 B 初步负责前端、图表与预测评估；角色是工作分工建议，具体任务双方确认。每项工作由一人实现、另一人真实审查，双方共同维护 contracts、database 和 infra。

GitHub 分支协作入口见 [协作规范](docs/guides/collaboration.md) 和 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)。WP3-A 已初始化本地 Git，并通过21项代表性忽略规则测试；WP3-B 已完成首次提交并推送至本人名下的 [GitHub 私有仓库](https://github.com/xingyu-wind/urban-commute-analysis)。远程仅启用 Squash Merge，合并后自动删除分支。私有仓库分支保护受当前 GitHub 计划限制，尚未生效；稳定 main、功能分支和真实 PR 审核仍须双方遵守。详细验证见 [S1 报告](docs/stage-reports/S1.md)。

## 后续阶段与数据边界

后续先完成 S1 剩余工作包，再依阶段任务确认契约和数据源、实现数据链路、开发 API 与页面、开展预测评估和联调。阶段编号以阶段执行对话确认为准。

本项目独立实现，不直接复刻或上传第三方毕业设计。参考资料须先核实授权；原始第三方 ZIP、未授权数据、真实凭据和个人数据不得纳入仓库。环境模板见 `.env.example`，复制后填写的本地 `.env` 不应提交。
