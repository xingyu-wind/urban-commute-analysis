城市通勤系统 — USB 离线答辩候选包（Windows x64）

最快操作：
1. 将完整 ZIP 带到目标电脑，解压到 U 盘或本地短路径。
2. 双击 RUN-FROM-USB.bat，选择本地可写 NTFS 目录（优先可写 D 盘），
   阅读许可证并输入 ACCEPT。自动复制、逐文件校验、初始化独立数据库并启动。
3. 在显示的本地目录私下运行 CREDENTIALS.bat 查看本机随机 ADMIN/READER 密码；
   浏览器打开显示的 http://127.0.0.1:端口。不要录制或分享密码。
4. 默认进入总览，自动选择有数据的城市及最近有效时段；导航“交通分析”“智能预测”“全屏大屏”分别查看统计、七日预测和大屏。
5. 数仓场景：本地目录 STOP.bat → START-WAREHOUSE.bat → 选择 s5-city。
6. 结束用本地目录 STOP.bat；数据库保留，再次 START.bat 可恢复。

包内包含全部锁定 Java/Python/MySQL/桥接依赖归档；目标首次配置不下载。
缺失/损坏文件会停止，不尝试上网补齐。不要只复制 app 或 launcher。
需要 Windows10/11 x64（本轮只验证Windows11）、PowerShell5.1、现代浏览器、
可写本地固定 NTFS 盘，部署前至少5GiB空闲（建议8GiB以上）、建议8GiB内存。
路径尽量短，中文/空格可用；MySQL放在每安装专属ASCII原生目录，
实际位置由本地 state/mysql-location.json 记录。任意C盘/受管目录不保证可用；
出现初始化错误保留日志并换另一可写本地磁盘的新目录，不清理旧数据。

VC++ 系统前提：需要 Microsoft Visual C++ x64 v14 运行库。
若缺失，启动器明确停止；不会静默提权或修改系统设置。
出发前由用户从微软直接取得官方离线安装程序并与ZIP一起携带：
https://aka.ms/vc14/vc_redist.x64.exe
本次已为用户取得单独的 t3-usb-prerequisites/VC_redist.x64.exe，见同目录receipt.json；
把它也复制到U盘。缺库电脑由有权限者交互运行该官方安装器，接受微软条款后重试。
不要临场上网下载，不要从系统目录随意复制DLL。该安装器未纳入通用ZIP，
微软再分发要求需合法Visual Studio许可；这里不假定用户已取得该资格。

仅供用户本人受控、非商业答辩迁移，不是公开发行或商业授权。
原始第三方归档、LICENSE/NOTICE、MySQL/Python及Java依赖源码/元数据、
Zulu原始源码提供书完整保留；见 licenses/DEPENDENCIES.txt。
不要向其他人转交初始化后的runtime/state/MySQL目录或DPAPI凭据。

本机新目录已验证不代表所有电脑兼容或干净Windows验收完成。
预测与数仓均为已发布 synthetic_test 合成快照，不是现场训练或真实预测精度证明。
Windows不启动Hadoop/Hive集群；研究上传/明确确认/研究导入不自动贯通正式发布。
真实数据门槛 BLOCKED，真实准确率/跨城市泛化 NOT_EVALUABLE。
详细操作、现场速查及5–7分钟流程见 guides/。
