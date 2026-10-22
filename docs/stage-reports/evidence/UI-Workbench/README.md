# UI-Workbench 验收证据索引

交付状态 **SUBMITTED_FOR_INDEPENDENT_REVIEW / SOLO_OWNER_REVIEW**。应用源码 `65c5394adc2d0a74d489027a3a0f83f25191d307`。总报告见 [UI-Workbench](../../UI-Workbench.md)，机器可读身份、原始证据路径和精选文件哈希见 [delivery.json](delivery.json)。本目录为本地实测证据；没有当前分支云端 CI 承诺。

| 内容 | 入口 |
|---|---|
| 最终 ZIP 身份、58 组件/88 源码/全文件 SHA、本轮私有值零匹配 | [包体检查](validation/final-zip-inspection.json)、[build receipt](validation/build-receipt.json)；实际扫描数量以 JSON 为准 |
| 新目录离线安装、缺件/错误哈希拒绝、网络监管器和最终停止 | [离线验收](validation/final-offline-install.json) |
| 模型/数仓、登录权限、真实研究导入、停止重启 | [包内 HTTP/生命周期](validation/final-package-http-lifecycle.json)、[管理表单](validation/final-browser-management.json) |
| 32 组生产页布局、全屏、七点值、网络失败/恢复 | [模型场景](validation/final-browser-model.json)、[空间/数仓场景](validation/final-browser-spatial.json) |
| 最终前端98测试 | [Vitest JSON](validation/final-frontend-unit.json) |
| 完整 Java116、历史前端92、HTTP/OpenAPI、负向验证器 | [核心回归](validation/core.json)、[真实捕获校验](validation/core-captured-contracts.json)、[负向验证器](validation/negative-verifiers.json) |
| 收尾元数据47真实集成（包括新增来源边界） | [元数据汇总](validation/metadata.json)、[测试数量](validation/metadata-test-counts.txt) |
| 地图/区域/道路、受控数据库变更、恢复和503 | [交通汇总](validation/traffic.json)、[真实浏览器 manifest](validation/traffic-browser.json) |
| 权限465真实HTTP及ADMIN/READER浏览器 | [权限](validation/security.json)、[权限浏览器](validation/security-browser.json) |
| S7完整训练/发布/篡改拒绝/硬退出恢复/七点曲线 | [模型](validation/model.json)、[发布与负测](validation/model-publication.json)、[实际ECharts数组](validation/model-chart-arrays.json)、[实际HTTP](validation/model-browser.json)、[73项Python](validation/model-python.xml) |
| S5真实CSV/JSON/幂等/SQL对账 | [ETL汇总](validation/etl.json)、[40项Python](validation/etl-python.xml) |
| 本轮S6仅本地MySQL/Decimal准入，不冒称Hive实算 | [数仓准入](validation/warehouse-admission.json)；真实HDFS/Hive历史见原S9报告 |
| 失败现场、修复与重测索引 | [resolved-failures.json](resolved-failures.json)；未复制初始化临时口令或私有日志 |

## 实际截图

- [总览1920](screenshots/overview-1920.png)、[总览768](screenshots/overview-768.png)、[总览390](screenshots/overview-390.png)
- [模型大屏1366](screenshots/screen-model-1366.png)、[模型大屏1920](screenshots/screen-model-1920.png)
- [空间大屏1366](screenshots/screen-spatial-1366.png)、[空间大屏1920](screenshots/screen-spatial-1920.png)
- [交通分析1366](screenshots/traffic-1366.png)、[预测390](screenshots/prediction-390.png)
- [仅目录/无模型](screenshots/directory-only.png)、[管理登录](screenshots/management-login.png)、[READER只读](screenshots/reader.png)

测试与安装原始目录保留在 backend/target 和 dist；本目录只归档便于评审的摘要、数值和真实截图，delivery.json 的 source 字段指回完整现场。没有密码、Cookie、CSRF值、DPAPI或数据库dump。模型和数仓的种子来源仍由原fixture provenance证明，不把新测试训练结果放进发行包。

最终包验收为同机独立新目录的离线执行路径：没有物理断网、真实U盘、异机/干净Windows或新的Hive集群实算证明。最后所属进程停止，旧T3-USB ZIP大小和SHA重新核对不变。
