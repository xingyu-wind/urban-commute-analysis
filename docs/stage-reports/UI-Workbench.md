# UI-Workbench｜前端体验与可视化重构验收报告

状态：**SUBMITTED_FOR_INDEPENDENT_REVIEW**。治理方式 **SOLO_OWNER_REVIEW**；本报告不自行认定 ACCEPTED。工作包 A、B 连续实施，最终交回项目总规划师独立验收。

## 基线与保护

正式目录 `D:/WindXingyu/Code/urban-commute-analysis`。起始分支 `codex/t3-usb-offline`，HEAD `31227bee30a36905b279416f4ea2ddfc6b5b351e`，工作区干净。从这个实际 HEAD 新建 `codex/frontend-workbench`，完整保留 S9、T2、T3、T3-USB 祖先及尚未合并成果；没有从旧 main 覆盖。只读 fetch 后 main/origin main 仍为 `222f70d`，S9 origin 为 `97f30db`，本地 S9 后续交付历史保留。

实现提交依次为 `b228627`（导航与元数据）、`71faf73`（视觉、回归与发行说明）、`d571cbd`（空间面板与道路摘要）、`65c5394adc2d0a74d489027a3a0f83f25191d307`（空预测紧凑布局和坐标可读性）。最后一个是**候选应用/打包源码身份**；报告证据提交另见最终交付回执及 `git log`。制包时工作树干净。没有 reset、clean、未知文件覆盖、清理旧数据库、远程 push、merge、Tag 或正式 Release。

已读 S9/T2/T3/T3-USB 报告、实际 API/权限/迁移及打包流程。本轮只有一个执行子对话，负责元数据后端和既有浏览器驱动适配；主对话负责工作台、大屏、联调及发行验证。

## 工作包交付

| 入口 | 最终行为 |
|---|---|
| 总览首页 | 无需登录；优先选择实际有数据城市，统一城市/数据集、速度/拥堵/样本/覆盖指标、历史趋势、区域概况及七日摘要 |
| 交通分析 | UTC 日期、小时/日趋势与缩放、独立 REGION 对比、实际 WGS84 点位、ROAD 搜索/区域联动/分页、趋势明细、Hive 快照同窗比较 |
| 智能预测 | 已发布数据的历史 28 日与预测 7 日曲线、七个日期及数值、最后观测/预测截止日、模型与 MAE/RMSE；完整版本/输入 SHA/ETL 批次/回测折叠 |
| 数据管理 | 沿用登录、ADMIN/READER、CSRF、上传限制、完整映射人工确认、隔离研究导入和任务查询；分析页面不要求登录 |
| 全屏大屏 | 深海军蓝；浏览器全屏及退出、城市/数据时间、指标、趋势、可用空间分析、前五道路与预测；无数据不画地图或空坐标系 |

浅色工作台统一导航、面板、筛选、按钮、标签与表格。桌面常驻导航、窄屏五入口均直接可见；hash 支持深链接和前进/后退。大屏默认折叠统计日期表单，仍可展开调整；无模型空态缩短，避免以大空白占屏。模型版本/来源限制保留可检查入口，没有删除数据库审计、来源或真实性记录。

城市/数据集切换由 Java 元数据给出真实范围，默认取最近最多七日且包含最后观测当天的 UTC 半开窗口。用户可手动修改日期，切页保留筛选；切城市/数据集重算。请求版本和组件卸载清理拒绝晚到旧结果。失败有明确状态及重试，刷新失败清除失效分析。城市状态区分统计、预测、仅目录及范围读取失败。simulation/mock/forecast 保留目录与真实原始范围信息，但不会被当作允许公开统计或预测的来源。CITY、REGION、ROAD 不互相替代。

预测展示继续使用既有发布指针与 Java API；截止日不会改成今天，前端没有随机数或运行时 Mock。候选包继续装载原有合成发布种子；本轮 S7 回归在另一个新隔离库训练/发布，未替换交付包模型。

## 关键文件与接口

| 文件 | 职责 |
|---|---|
| `frontend/src/App.vue` | 五入口、hash 导航、公共城市/数据集状态、服务检查、全屏控制及来源详情 |
| `frontend/src/api/availability.ts` | 严格响应校验、城市/数据集状态、来源读权限语义、有效 UTC 窗口 |
| `frontend/src/components/TrafficDashboard.vue` | 四类统计、日期/区域/道路联动、真实点位及空态、桌面道路摘要 |
| `frontend/src/components/PredictionPanel.vue` | 28+7 双曲线、七点表、模型误差与可展开技术信息 |
| `frontend/src/components/WarehousePanel.vue` | 全局数据集联动、发布快照与同窗口 CITY 比较、折叠版本信息 |
| `frontend/src/components/TrafficChart.vue` | 沿用 SVG ECharts、ResizeObserver、图例/Tooltip 及销毁生命周期 |
| `frontend/src/components/OperationsPanel.vue` | 沿用会话、CSRF、角色、人工确认与研究任务操作；仅改变入口和外层视觉 |
| `frontend/src/style.css` | 品牌变量、浅色/深色、网格和响应式断点、紧凑大屏及键盘焦点 |
| `backend/.../api/TrafficAvailability.java`、`repository/AvailabilityRepository.java`、`web/AvailabilityController.java` | 新的只读范围契约、参数化 SQL、repeatable-read 快照与严格参数拒绝 |
| `contracts/openapi.yaml`、examples/cases/validator | 新元数据契约和原有正负例校验 |
| `frontend/scripts/verify-*.mjs`、`responsive-layout.mjs` | 原 S2–S9/T3 驱动适配；可见控件、图表、预测数组与真实生产包验证 |
| `scripts/verify_workbench_regression.py` | 本轮测试安装的归属校验、新随机隔离库与回归编排 |
| `scripts/build_windows_zip.py`、`infra/windows/*README*` | 复用 T3-USB 锁与构建逻辑，增加随包工作台说明 |

新增 **GET/HEAD `/api/v1/traffic/availability?cityId=...`**，返回默认数据集、与城市关联的数据集、各层级实际样本数/首末 UTC 时间、兼容来源/版本的已发布预测状态及截止日。错误处理沿用原封套，拒绝多值、未知参数、非法 cityId 和未知城市。仅在 SecurityConfig 的有限公开 GET/HEAD 清单中增加此精确路径；其余默认拒绝、角色、CSRF 与会话配置不变。

**无数据库迁移、无旧业务数据改写、无预测/训练算法变更。** 只查询现有 city、dataset_registry、traffic_observation、prediction_current/job。真实 SQL 测试确认无跨城市数据集泄漏、层级范围独立、发布状态/来源/版本不符不冒充预测可用。接口对既有调用保持兼容。

## 实际验证与证据

以下均为本机结果，不借用旧提交 CI 证明本分支：

| 验证 | 实际结果 | 原始证据目录 |
|---|---|---|
| Spring Boot 完整回归 | 116 项，0 失败/错误/跳过；含原安全默认拒绝与 API 集成 | `backend/target/ui-regression-04/core/core` |
| 收尾元数据真实集成 | 47 项通过，含 9 控制器、24 统计、14 预测；新增目录来源边界 | `backend/target/ui-metadata-final` |
| Vue / TypeScript / build | 最终 98 项单元、类型检查、生产构建通过；dist 哈希与候选 ZIP 一致 | `backend/target/ui-final-unit-65c5394`、`frontend/dist`、build receipt |
| OpenAPI | 24 正例、16 负例、63 external examples 通过；实际 HTTP 捕获额外按 schema 和 Java requestId 日志校验 | `backend/target/ui-final-checks`、core/browser |
| S2–S4 浏览器 | 城市切换、六历史宽度、数据库受控变更/恢复、真实 SVG 点位联动、分页/关键词、空窗口、后端停止恢复、真实断网、真实 DB 503 | `backend/target/ui-regression-04/core` |
| S5 ETL | 40 项 Python 通过，真实 CSV→JSON→幂等→MySQL→Java→Vue/ECharts 及独立 SQL 对账 | `backend/target/ui-regression-02/etl` |
| S6 本地准入 | MySQL、独立 Decimal 对账/边界与发布准入通过；不等于本轮执行 Hive | `backend/target/ui-regression-02/warehouse-admission` |
| S7 | 73 项 Python、两轮一致训练、篡改拒绝、原子发布/硬退出恢复、MySQL/API、实际 ECharts 的 28+7 数组逐点一致 | `backend/target/ui-regression-04/model` |
| S8 安全 | 465 次真实 HTTP；三身份/有效 CSRF 拒绝矩阵、零越权写入、真实上传/确认/导入/READER 只读通过 | `backend/target/ui-regression-04/security` |
| 最终离线候选 | 162.53 秒内全流程通过：新目录安装、模型/数仓 32 组页面布局、全屏、权限上传、生命周期、缺件/错误哈希及回环限制；最终停止 | `backend/target/ui-workbench-acceptance-03` |

最终候选浏览器使用真实 Chromium、正式 dist 和 Java/MySQL，**不拦截/伪造 API**。模型与数仓两场景分别在 1920×1080、1366×768、768×1024、390×844 检查四个分析入口、可见控件、页面横向溢出、ECharts 容器尺寸；桌面大屏额外断言整页高度不超过视口。浏览器全屏进入/退出、日期表单展开、七点表与 API、模型详情、空目录/无模型、手动无数据窗口与最近时段恢复、真实离线/重试均有断言。ADMIN 与 READER 在真实表单中验证人工确认后导入和只读限制。

精选可读证据集中于 [evidence/UI-Workbench](evidence/UI-Workbench/README.md)，包括 [总览](evidence/UI-Workbench/screenshots/overview-1920.png)、[模型大屏 1366](evidence/UI-Workbench/screenshots/screen-model-1366.png)、[空间大屏 1920](evidence/UI-Workbench/screenshots/screen-spatial-1920.png)、[预测窄屏](evidence/UI-Workbench/screenshots/prediction-390.png)。截图为实际浏览器输出。

**云端 CI：本轮未推送分支，未触发/宣称当前 HEAD 云端 CI 成功。** check_ci 策略仅是本地校验。S9 真实 HDFS/Hive、恢复、历史云端 Run/Job 继续保留原报告证据；它们属于历史，不冒称本轮本机实算。若独立评审要求当前分支云端运行，需要单独授权 push。

## 离线交付

- 新 ZIP：`D:/WindXingyu/Code/urban-commute-analysis/dist/ui-workbench-candidate-03/UrbanCommute-USB-Demo-0.9.0-workbench-candidate-windows-x64.zip`
- 大小：**1021855459 字节**；478 文件。
- SHA256：**`6405050a506717ae50ce1d764990490ee39c1fd41768d1f2435d1d6dfda17cfb`**。
- 应用与打包源码：`65c5394adc2d0a74d489027a3a0f83f25191d307`；新正式前端文件、Java JAR、原合成预测/数仓种子、原 Python 业务及离线依赖均随包。
- 保留 58 项二进制组件与 88 项对应源码/元数据锁、许可证及逐文件哈希。没有加入额外框架、外部地图或图片资源。
- 全新运输目录 `dist/ui-workbench-media-03`，实际部署 `dist/ui-workbench-install-03`；同一 Windows11 x64 主机，独立 runtime/state/MySQL、随机账号，未复制旧安装缓存或私有数据。
- 旧 T3-USB ZIP 保持原大小及 SHA256，未覆盖。候选 01/02 和失败证据保留，不作为推荐交付。

复现构建（输出目录必须不存在）：

```powershell
ml/.venv/Scripts/python.exe scripts/build_windows_zip.py --output dist/new-ui-candidate --version 0.9.0-workbench-candidate --offline-components dist/component-cache --offline-sources dist/t3-usb-sources
ml/.venv/Scripts/python.exe scripts/check_windows_zip.py --zip dist/new-ui-candidate/UrbanCommute-USB-Demo-0.9.0-workbench-candidate-windows-x64.zip --output backend/target/new-ui-inspection.json
```

构建前需从上述应用源码提交重新正式构建前后端；打包器会拒绝声明源码与工作区应用代码不一致。最终包的 build receipt、逐文件检查及验收汇总见证据目录。

使用：携带新 ZIP 与原先单独取得的官方 VC++ x64 前提安装器；解压后 RUN-FROM-USB，选择新的本地可写 NTFS 目录，接受许可、等待配置。私下用本地 CREDENTIALS 查看随机账号，浏览器进入显示地址；结束用 STOP。数仓演示沿用 STOP→START-WAREHOUSE。说明已同步到包内 `guides/workbench.md`、速查和演示流程，见 [工作台说明](../guides/workbench.md) 与 [USB 指南](../guides/windows-usb.md)。

## 失败记录与边界

保留首次沙箱中 MySQL 已就绪但回环探测超时的现场；在用户批准的沙箱外新目录重新验证。原浏览器驱动发现三类时序/语义问题：空目录刷新未结束就断言、响应采集未结束即停止服务、把已有 ROAD 记录的北京目录误当完全无观测；分别增加真实完成等待、采集收口和独立层级断言。折叠详情控件被测试辅助程序错误当成遮挡，按实际可见性修复，仍检查全部可见控件。

新回归编排首轮误指定不存在的 bigdata/tests，真实失败保留；修正为 ml/tests，数仓另由真实 admission 流程验证。一次布局命令使用已结束的测试服务得到 502，随后由同一驱动负责服务全生命周期。离线候选02真实暴露无模型空态高度继承大图表（1920 高度1182），修复紧凑空态后从新目录重建03；没有降低整屏高度断言、禁用测试或伪造成功。失败索引与 SHA 见证据目录。

本轮仍是**同机新目录离线执行路径验收**，没有物理断网、真实 U 盘、异机、干净 Windows、Windows10/ARM/缺 VC++ 环境证明；不宣称普遍兼容。Windows仅读取已有 Hive 快照，本轮本机没有 Hadoop/Hive 集群。真实数据门槛仍 BLOCKED、真实准确率/跨城市泛化 NOT_EVALUABLE；合成 MAE/RMSE 不能外推真实交通效果。Vite 保留共享 ECharts 大块提示，未新增框架；构建和浏览器功能通过不等于公网性能 SLA。

## 参考与学习

参考 [vue-pure-admin 布局源码](https://github.com/pure-admin/vue-pure-admin/blob/main/src/layout/index.vue)、[Superset](https://github.com/apache/superset)、[DataScreen](https://github.com/Christa137/DataScreen)、[ECharts examples](https://github.com/apache/echarts-examples) 的布局/筛选/大屏/时间序列表达。本轮未复制这些项目的源码、素材或引入其框架；pure-admin 的 [MIT](https://github.com/pure-admin/vue-pure-admin/blob/main/LICENSE)、Superset 的 [Apache-2.0](https://github.com/apache/superset/blob/master/LICENSE.txt)、ECharts examples 的 [Apache-2.0](https://github.com/apache/echarts-examples/blob/gh-pages/LICENSE) 已查看。DataScreen 的 LICENSE 子链接未取得可核实内容，因此不复用其代码或素材。实际交付的 Vue/ECharts 及运行组件继续按 T3-USB 携带原有许可和源码资料。

简短关系说明见 [前端重构知识关联与实现说明](../learning/前端重构知识关联与实现说明.md)，覆盖 Vue 页面/导航、共享状态、API、ECharts、权限、数据库及预测发布之间的联系。
