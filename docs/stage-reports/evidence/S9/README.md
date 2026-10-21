# S9 可追溯证据

本目录只保存实际运行的精选汇总、哈希和合成页面截图。原始外部CSV、含观测样例的外部报告、dump、账号哈希、数据库口令、会话/Cookie/CSRF不进入Git、PR附件或CI artifacts。完整测试诊断在忽略的backend/target；CI保留14日，长期精选证据在此。

| 文件/目录 | 内容与边界 |
|---|---|
| preflight.json | 干净工作区、base、环境、正式规划SHA、S7/S8合并和基线Job核查；不是S9最终CI |
| sources/ | 2026-10-21公共HTTP元数据摘要和本地片段哈希；真实NOT_EVALUABLE，不含观测行 |
| core/ | Java105/Vue91、核心HTTP/浏览器/停止恢复执行摘要 |
| security/ | 最终453次真实HTTP、真实MySQL/目录零业务写入、审计故障/会话/角色/CSRF/重试/并发与Chromium |
| model/ | 合成4368条训练/复现/篡改拒绝/发布/真实浏览器摘要；不是真实预测准确率 |
| release/ | 生产dist部署、全表备份恢复哈希/指针/API相等、HTTP性能和真实页面截图 |
| warehouse-ci/、ci-baseline.json | 实现提交0be0d11真实HDFS/Hive成功产物、22表/非空数仓指针恢复及实际production截图；基线不是最终HEAD |
| resolved-failures.json | 首轮405分类失败、原始日志SHA与修复后回归事实 |
| files.json | 精选证据SHA清单（不包括清单自身），便于检查篡改/遗漏 |

最终精确HEAD/Run/Job与artifact身份在正式S9 PR正文及Checks记录，作为本索引组成部分；报告内基线成功不代表最终HEAD。仓库两条工作流仍保留S2–S8回归/真实HDFS-Hive，新增S7预测发布和S6 Hive发布后的独立空库恢复。后续读取可用GitHub API按PR head.sha核对两条run.head_sha、Job步骤与artifact SHA，不能把cancelled/旧SHA计为通过。

本机没有HDFS/Hive/Docker，真实HDFS/Hive只能由最终warehouse Job证明。最终Run/Job回执和实际导出汇总应与PR HEAD一起查看；没有在本机截图中伪装Hadoop执行。详细命令与限制见[S9报告](../../S9.md)和[部署手册](../../../guides/s9-deployment.md)。

最终精确回执入口：[PR #10正文与Checks](https://github.com/xingyu-wind/urban-commute-analysis/pull/10)。实现基线[Run39524285566 / Job118975195112](https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39524285566/job/118975195112)已SUCCESS；最终文档提交仍重新核验两条HEAD绑定CI。
