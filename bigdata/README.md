# 大数据模块

负责规划中的 HDFS 历史数据组织、Hive 分区表与离线统计。未来存放 Hive DDL、聚合 SQL、任务配置模板和分区说明，不在本轮安装 Hadoop/Hive 或执行任务。

接收 data-pipeline 标准化数据，与 contracts 统一口径，向 ml 提供特征输入并将聚合结果写入 database。预计在后续大数据实现阶段开始，先评估数据规模与环境；阶段编号待确定。
