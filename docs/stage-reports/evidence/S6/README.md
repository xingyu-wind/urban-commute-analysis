# S6 真实证据索引

首个全链路成功：[Run39378722907](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39378722907)，[Job118482642419](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39378722907/job/118482642419)，代码05a887136279d3c79d097ff7f83241a1055b2390。原始 artifact12244548425，archive digest `sha256:a6717137b86f1f3caea9c18520c5a4edc69f058606384adb1cf17570f8f6c522`。后续加强与最终 HEAD 的 CI 见正式 PR Checks/正文。

| 证据 | 内容与边界 |
|---|---|
| [environment.json](environment.json) | 本机检查、基线、未安装系统软件、用户限定 format 授权、实际容器版本及镜像摘要 |
| [files.json](files.json) | 每个保留文件的来源、大小和 SHA；日志改后缀为txt但不改原始字节 |
| [runtime.txt](ci-39378722907/hive/runtime.txt) | 实际 Java/Hadoop/Tez 版本、NameNode/DataNode、上传/目录/下载、相同 SHA、重跑导出对比 |
| [namenode-format.txt](ci-39378722907/hive/namenode-format.txt) | 本次空临时目录的真实 format；未操作已有 HDFS |
| [schematool.txt](ci-39378722907/hive/schematool.txt) | 独立 Derby Metastore 初始化 |
| [executed.hql](ci-39378722907/hive/executed.hql) | 含实际 Hive 会话变量初始化的完整执行 SQL |
| [hive-first.txt](ci-39378722907/hive/hive-first.txt)、[hive-repeat.txt](ci-39378722907/hive/hive-repeat.txt) | 原始真实四层建表/写入/Tez任务/分区/控制数及导出；两次结果一致 |
| [hdfs-fsck.txt](ci-39378722907/hive/hdfs-fsck.txt) | 真实 HDFS 文件和块检查 |
| [core-site.xml](ci-39378722907/hive/core-site.xml)、[hdfs-site.xml](ci-39378722907/hive/hdfs-site.xml)、[hive-site.xml](ci-39378722907/hive/hive-site.xml)、[tez-site.xml](ci-39378722907/hive/tez-site.xml) | 实际配置，Tez local mode；通用进度中的 YARN 文案不代表部署了YARN |
| [manifest.json](ci-39378722907/bundle/manifest.json)、[ods.tsv](ci-39378722907/bundle/ods.tsv)、[observations.json](ci-39378722907/bundle/observations.json)、[download.tsv](ci-39378722907/hive/download.tsv) | 成功 ETL 准入后的39条血缘、来源/版本/文件身份；原始上传与下载内容 |
| [ads-first.tsv](ci-39378722907/hive/ads-first.tsv)、[ads-repeat.tsv](ci-39378722907/hive/ads-repeat.tsv) | Hive 真正计算的40行 ADS 原始文件，不是 Python 生成值 |
| [oracle.json](ci-39378722907/oracle.json)、[hive-reconciliation.json](ci-39378722907/hive-reconciliation.json) | 独立 Decimal 逐字段比较，DWD21、DWS18、ADS40 |
| [publication.json](ci-39378722907/publication.json)、[mysql-reconciliation.json](ci-39378722907/mysql-reconciliation.json)、[negative-cases.json](ci-39378722907/negative-cases.json) | 去重发布、故障/恢复、保留旧可见版本、最终 FAILED 头与已发布明细控制总数 |
| [CI summary.json](ci-39378722907/summary.json) | scope=real-hive-chain，全部步骤通过，无复用外部 Hive 证据 |
| [local-regression.json](local-regression.json) | 既有S2–S5核心回归，Java82/Vue63；S6准入验证39→21；后续新增测试见最终CI |
| [local/summary.json](local/summary.json)、[local/mysql-reconciliation.json](local/mysql-reconciliation.json) | 本机新MySQL库重新ETL/对账/发布/Java/Chrome；明确记录复用上述真实CI Hive导出，未在Windows运行HDFS |
| [实际HTTP与浏览器manifest](local/browser/manifest.json)及同目录response-*.json | 真实Java响应及各粒度/参数错误；逐份通过OpenAPI，noRequestMocking=true |
| [桌面截图](local/browser/warehouse-desktop.png)、[手机截图](local/browser/warehouse-mobile.png) | Windows Chrome 中文可读，实际发布结果、来源、窗口、版本和相同窗口MySQL比较；截图不替代日志/响应 |
| [failed-39378301714-hive.txt](failed-39378301714-hive.txt) | 首轮真实变量传递错误及原始异常；随后通过同会话SET修复并实测 |

所有数据均为 synthetic_test。MySQL release 头中的 row_count 是预期数量；失败头不代表持久化了对应明细，故障注入断言和分组总数证明失败明细未可见。总和/样本数只在相同 grain 内对账，不能混加 HOUR、DAY、WINDOW。

增强版 [Run39379190899 / Job118484120279](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39379190899/job/118484120279) 同样 SUCCESS，HEAD83c51a4bf5956f2eb39fe74fa6b5ba150e257e84，artifact12244812508，digest `sha256:5c9f1ec748cd8eedf0ae275525c51298686444a27691c8bdd774bf622abfa377`。

- [增强完整摘要](ci-39379190899/summary.json)、[Hive首跑](ci-39379190899/hive/hive-first.txt)、[Hive重跑](ci-39379190899/hive/hive-repeat.txt)、[实际执行SQL](ci-39379190899/hive/executed.hql)：包括Hive内部层间断言。
- [Hive非法输入原始日志](ci-39379190899/hive/hive-invalid.txt)：真实999.00 km/h输入触发ASSERT_TRUE失败；脚本同时核对错误类型，避免把任意启动失败当成合法拒绝。
- [增强对账](ci-39379190899/hive-reconciliation.json)、[MySQL对账](ci-39379190899/mysql-reconciliation.json)、[实际HTTP/浏览器](ci-39379190899/browser/manifest.json)。

同提交核心回归 [Run39379190936 / Job118484201894](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39379190936/job/118484201894) SUCCESS。最终HEAD对应Checks/Run由[正式PR #7](https://github.com/xingyu-wind/urban-commute-analysis/pull/7)、[实时Checks](https://github.com/xingyu-wind/urban-commute-analysis/pull/7/checks)和最终交付消息记录，上述成功Run不冒充不同HEAD的结果。
