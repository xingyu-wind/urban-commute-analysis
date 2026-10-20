# 项目文档

负责记录可核实的规划、协作流程与阶段证据，与全部工程模块共同维护。文档从 S1-WP2 开始建立，后续实现时随对应 PR 更新，不以规划代替完成证据。

- `architecture/`：系统架构、数据流与后续设计决策，当前入口为 `overview.md`。
- `guides/`：双人协作与后续开发操作指南，当前入口为 `collaboration.md`。
- `stage-reports/`：工作包执行结果、验证及遗留事项，当前入口为 `S1.md`。

后续设计阶段补充架构，开发阶段补充操作指南，各阶段结束前更新报告；未确定的阶段编号不提前承诺。

S4 当前入口：[阶段报告](stage-reports/S4.md)、[运行与演示](guides/s4-dashboard.md)、[知识关联与讲述方法](learning/S4-知识关联与项目实现说明.md)。S1–S3 报告保留历史原文。

S5 当前入口：[阶段报告](stage-reports/S5.md)、[Python ETL与恢复操作](../data-pipeline/README.md)、[S6输入字典](../data-pipeline/DATA_DICTIONARY.md)、[知识关联与项目实现说明](learning/S5-知识关联与项目实现说明.md)。S4/S5 已正式 ACCEPTED，阶段报告保留当时提交事实。

S6 当前入口：[阶段报告](stage-reports/S6.md)、[真实数仓与发布运行说明](../bigdata/README.md)、[知识关联与项目实现说明](learning/S6-知识关联与项目实现说明.md)。单人执行，采用 SOLO_OWNER_REVIEW，提交独立验收，不自行 ACCEPTED 或合并。

S7 当前入口：[阶段报告](stage-reports/S7.md)、[离线训练与发布](../ml/README.md)、[知识关联与项目实现说明](learning/S7-知识关联与项目实现说明.md)。采用 SOLO_OWNER_REVIEW，状态 SUBMITTED_FOR_INDEPENDENT_REVIEW；合成演示不代表真实交通预测准确率。
