# S7 真实证据索引

## V3.2 最终证据（本轮）

- `v32-final/summary.json`：最终本机完整训练、独立重放、新MySQL、HTTP/OpenAPI和Chromium命令及结果。Python73 / Java104 / Vue91通过；`pytest.xml`、backend.txt、frontend-unit.json保留实测。
- `v32-final/prediction-integrity.json`：仅第4点5.166635→5.291635，输入/日期/合法范围不变；拒绝、指针不变、错误任务0行。合法发布/幂等/回滚/硬退出恢复/陈旧任务及S6指针边界见mysql-publication.json和summary.json。
- `v32-final/train/run.json`：最终本机模型2710e7d636bf7b89dec4a4d48e65de01881434f39e254edd3f1ed1438ada5f55；新锁含tzdata2025.2。输入SHA仍f16c59557271ffcf6965883bdf0624674f199efb6a542b727174a8b52be651ea，模型/锁/代码/时间及七点均可追溯。不同环境模型版本可能不同。
- `v32-final/browser/`：实际HTTP响应、ECharts读数/像素、运行清单、桌面/窄屏截图；七日2026-10-19至25、数据截止UTC19日00:00，合成RF测试MAE .107515 / RMSE .130473。
- `v32-b/summary.json`：CSV/JSON完整CLI，无网络或外部原文件；alpha/beta质量及四模型验证/测试逐窗口/逐步误差在各自evaluation.json，重复运行完全一致。`transfer.json`冻结源域拟合，合成泛化结论NOT_EVALUABLE。
- `v32-b/sources/*-quality.json`：真实Zenodo v6仅聚合质量/文件哈希，实际截断且分发校验FAILED，两者NOT_EVALUABLE。无真实行值、无真实可执行映射；许可与深圳/PeMS阻塞见[来源台账](../../../../ml/DATA_SOURCES.md)。
- `v32-a/`：先完成A再进入B的本机门槛。提交8ac732aea0085287c1b0d25440531f1701040ed2的核心[Run39435341094 / Job118670826364](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39435341094/job/118670826364)、S6实际HDFS/Hive [Run39435341191 / Job118670771001](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39435341191/job/118670771001)均SUCCESS。最终HEAD另外通过PR正文/Checks核验，不能用A替代。
- V3.2全文SHA与用户暂不放行真实评估的决定保留在v32-a/basis.json。原始外部文件仅本机忽略目录，未进入Git/CI；精选证据通过私有凭据扫描。

以下为首轮S7的历史证据，旧模型/19项测试计数不代表V3.2最终版本。

## 首轮历史证据

本机最终训练/发布/HTTP/Chromium：`backend/target/s7-final-review`，新隔离库与账号见 local/isolation.json；没有删除既有数据。所有输入均 synthetic_test。2026-10-20 Windows / Python3.11 / Java21 / MySQL8.4 / Node24 / Chrome；具体版本见 environment.json。

- 数据集：s7-synthetic-v1 / version=1 / batch=s7-history；4368条已提交CITY观测，1092完整日。ETL成功/来源/质量原件在 local/etl/。
- 本机模型：random_forest / `fccd905b7b9b860336b09e739776aee05dfe3ce21dc31afe4387f5406587b58a`。
- 输入 SHA-256：`f16c59557271ffcf6965883bdf0624674f199efb6a542b727174a8b52be651ea`。
- 科学配置、依赖/源码SHA、工件SHA、实际训练/生成时间、七个预测值：local/train/run.json。
- 完整日序列与来源、批次、原始文件/输入身份：local/train/training-input.json；所有模型/切分/起点/逐步长误差：local/train/evaluation.json。
- 两次真实训练字节与结果一致：local/reproducibility.json、train.txt、train-repeat.txt。完整model.joblib在本机原始训练目录及CI上传工件；不把大型权重放入Git。
- 当前PUBLISHED、失败任务/重试次数、MySQL七点回读：local/mysql-publication.json；独立断言列表及实际执行命令：local/summary.json。
- 真实Java/OpenAPI响应：local/browser/response-0至7.json；浏览器运行、无请求替换、实际响应及异常列表：manifest.json。
- 窄屏七点像素坐标及画布尺寸：local/browser/mobile-geometry.json；实际ECharts实例读出的35个日期、实际/预测系列与样式：local/browser/chart-data.json；可读中文截图：prediction-desktop.png、prediction-mobile.png。
- Java104 / Vue91 / S7 Python19；S2–S5全量回归与S5 Python40：regression/与local测试报告。原始Java/训练日志只改.log后缀为.txt，字节未改写。
- 修复记录：failures/same-generation-test.txt是时间相等保护触发的测试失败；floating-point-test.txt是跨语言约2e-16数值差异。均保留，后继完整重跑通过。

数据截止 `2026-10-19T00:00:00.000Z`；七日预测为2026-10-19至25，相对于数据截止时点的未来。合成测试MAE=0.107515、RMSE=0.130473，不是实采交通准确率。

最终HEAD对应CI Run/Job及结果由PR正文/Checks和最终交付消息记录，不能把此前本机或早期CI结果当作最终HEAD通过。CI完整训练工件保留14日。本目录files.json列出精选证据逐文件SHA-256。
