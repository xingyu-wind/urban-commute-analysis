城市通勤数据分析及智能预测系统 — Windows x64 竞赛候选包
SOLO_OWNER_REVIEW；不是正式 Release。所有演示数据均为 synthetic_test。

首次使用：
1. 将整个 ZIP 解压到当前用户可写的本地 NTFS 目录。路径建议短于100字符；支持空格和中文。
2. 双击 CHECK-ENV.bat，再双击 FIRST-SETUP.bat，阅读 licenses/DEPENDENCIES.txt 后输入 ACCEPT。
   首次需要联网：自动下载校验固定版本的便携 Java、Python、MySQL、Python wheels 和 Java 依赖。
   不需要 IDE、Git、Maven、Node，也不需要自行安装 Java/Python/MySQL 服务。
3. FIRST-SETUP 完成后，私下运行 CREDENTIALS.bat 查看本次安装随机生成的 ADMIN/READER 密码。
   不要录屏、分享密码或 state 目录。密码由 Windows 当前用户 DPAPI 加密保存。
4. 双击 START.bat，复制显示的 http://127.0.0.1:随机端口 到浏览器。
   选择“S7 合成预测城市”查看七日预测；数据截止日是2026-10-19，不是未来系统日期。
5. 查看 Hive 结果：先 STOP.bat，再 START-WAREHOUSE.bat，选择 S5 合成城市，进入“交通分析”→“查看 Hive 数仓快照与同窗比较”。
   两种场景使用独立数据库；数仓结果来自已有真实隔离 CI，Windows 不重新运行 Hadoop/Hive。
6. 退出时执行 STOP.bat；数据保留。再次启动无需联网，也不会重新初始化数据库。

管理演示：ADMIN 可上传 database/research-demo.csv，按界面完整人工确认；research-review.json 是对照，
不代表用户已经确认。上传仅产生隔离研究输入，不自动发布观测、数仓或预测。READER 只读任务。

系统要求：Windows 10/11 x64、Windows PowerShell 5.1、现代浏览器、本地 NTFS可写目录，首次至少3GiB空闲磁盘。
Java/Python/页面可位于中文及空格目录。MySQL使用解压目录内或最近可写ASCII父目录下的随机独立目录，
避免其Windows原生文件路径对中文的限制；位置记录在state/mysql-location.json。
没有可写ASCII父目录时尝试当前用户LocalAppData的ASCII路径；仍无可用位置则明确拒绝。
此时把ZIP解压到如 D:\Demo\城市通勤（D:\Demo须可写）的目录，勿修改系统权限。
备份时先STOP，私下同时备份state目录及mysql-location.json指向的MySQL目录；不得重新打包分享它们。
建议8GiB内存。此数值是保守准备建议，不是容量测试结论。
通常不需要管理员权限。若机器缺少 Microsoft Visual C++ 2015–2022 x64 运行库，
可能需由管理员从 https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist 下载官方运行库。
本包只诊断缺失，不静默提权安装、不改防火墙、PATH、注册表或全局执行策略。
首次配置需访问 python.org、cdn.azul.com、cdn.mysql.com、files.pythonhosted.org、repo.maven.apache.org。
每个下载最多尝试三次，同时校验固定字节大小与SHA256；失败信息包含文件、来源和原因。
未通过的缓存和中断文件保留为 .failed-* 诊断副本，不作为合法依赖使用；完整合法文件安全复用。
下载阶段失败可在原目录重新运行 FIRST-SETUP；不能关闭证书或哈希检查。
可在受控环境预置同名、同哈希的官方归档到 runtime/downloads，但这种情况不是空缓存下载验收。

故障排查：
- 文件损坏：MANIFEST 校验失败时重新解压，不要手改受校验文件。
- 初次数据库失败：保留 state/initialize.log、supervisor.log，以及 mysql-location.json 指向目录中的 mysql.log。不会清空或覆盖；用新的空解压目录重试。
- 端口冲突：脚本拒绝启动并保留现场，不结束占用者。先确认是否本包已运行，运行 STOP。
- 重复启动：拒绝第二个实例；不要直接删除锁文件或运行状态。
- 后端启动失败：检查 state/backend.log；Flyway 不 clean/repair、不跳过校验。
- 强制关闭或进程崩溃：Windows Job Object 回收本包子进程；下次启动由 MySQL 执行正常崩溃恢复。
  不按旧PID批量杀进程。断电/磁盘损坏仍可能丢失数据；这不是完整灾备承诺。
- 首次配置中断：组件下载/解压阶段可以原目录重试；已进入数据库初始化则保留未完成目录，重新解压到新的空目录，不覆盖初始化。
- 修改代码升级、跨Windows用户迁移：不支持覆盖安装。先STOP并私下备份整个state目录；保留原包，另建新目录。
  初始化后的目录不应重新打包分享；DPAPI凭据仅当前Windows用户/机器可用。
- CHECK/START不会自动开放局域网或公网；浏览器只使用显示的127.0.0.1入口。

数据和能力边界：
发行种子是经审查的合成业务快照，只含17张允许的业务表，不含账号、审计、上传、Flyway历史或完整dump。
首次运行正式JAR执行原V1–V6迁移，再在空目标事务导入种子，并通过原安全bootstrap生成账号。
预测与Hive结果是先前合法发布的快照，不代表本机刚完成训练或集群计算。
真实交通数据接入、真实准确率、跨城市泛化仍 BLOCKED / NOT_EVALUABLE。
无公网TLS/登录限速、多节点会话、自动调度、整机灾备或SLA承诺。
发行来源与文件哈希见 BUILD.json、MANIFEST.sha256、database/seed-provenance.json。
本候选仅做当前Windows隔离目录验收；不声称已在全新电脑、所有Win10/11版本、ARM或其他系统通过。
