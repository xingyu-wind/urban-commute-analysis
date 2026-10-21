# USB 答辩现场速查（一页）

**带齐**：完整USB候选ZIP、SHA256记录、单独为本人取得的微软VC_redist.x64.exe、随包许可/源码、S9真实Hive历史证据。不要带个人数据库、state、DPAPI或已初始化目录。

**目标要求**：Windows x64、PowerShell5.1、浏览器、VC++ x64 v14；本地固定NTFS可写，至少5GiB空闲，建议8GiB。缺VC++时有权限者先交互安装随行官方安装器，不临场联网。

**最短启动**：解压完整ZIP → 双击 RUN-FROM-USB → 选本地目录 → 阅读声明输入ACCEPT → 等待初始化/健康 → 私下运行本地CREDENTIALS → 浏览器打开显示的127.0.0.1 URL。

**交通/预测**：选 `s7-city` → “合成样本时段” → 统计/趋势/图表 → “打开七日预测”。未来七日从数据截止日计算，不一定从今天计算；误差是合成回测误差。

**权限/研究**：“权限与运行管理” → ADMIN登录 → 选本地 `database/research-demo.csv` → 上传并分析 → 读建议 → 对照 `research-review.json` 核实完整审查JSON并明确确认 → 执行导入SUCCEEDED → 退出 → READER登录展示只读任务、没有上传入口。

**数仓**：本地STOP → START-WAREHOUSE → 显示的URL → `s5-city` → “打开Hive离线分析”；解释已发布合成快照来自既有真实HDFS/Hive链路，Windows只在线读取展示。

**结束**：本地STOP。需要回到预测：STOP → START，检查发布结果恢复、旧会话失效。不要直接拔运行中的数据库工作盘。

**卡住时**：缺库先官方离线安装；缺文件重解压；权限/空间换本地盘；端口冲突不杀未知进程；初始化失败保留现场另建目录。不能用Mock伪装成功；备用展示已核验的历史真实截图/HTTP/Hive证据，并明确当前现场失败。

**必说边界**：synthetic_test；非实时训练；非真实预测精度；研究导入不是正式发布；真实数据BLOCKED/泛化NOT_EVALUABLE。仅本机新目录验证，不保证所有Windows/硬件兼容，不宣称干净客机验收已完成。
