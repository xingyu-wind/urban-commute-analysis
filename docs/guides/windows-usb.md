# USB 离线答辩操作指南

这是用户本人受控、非商业演示迁移候选。T3.1干净Windows验收仍为BLOCKED；本包改走包内依赖，不再等待该环境，不把本机测试说成异机通过。

1. 出发前携带完整 `UrbanCommute-USB-Demo-0.9.0-offline-candidate-windows-x64.zip`；同时携带单独取得的 `t3-usb-prerequisites/VC_redist.x64.exe` 和 receipt.json。ZIP的最终大小/哈希以USB专项报告为准，原T3联网ZIP保持不变。
2. 目标电脑需Windows x64、PowerShell5.1、现代浏览器、Microsoft VC++ x64 v14运行库。缺库时由有权限者交互运行微软官方离线安装器；可能需要管理员。系统库不是Java/Python/MySQL开发环境，不静默提权安装。微软安装器不纳入通用ZIP，不能假定有向第三方再分发的权利。
3. 将完整ZIP解压到短路径；双击 `RUN-FROM-USB.bat`，选择本地可写固定NTFS目录，优先合适的数据盘，至少5GiB空闲，建议8GiB以上。路径尽量短，含中文/空格可以；不要用U盘/网络盘作为数据库工作盘。读取声明后输入 `ACCEPT`。
4. 启动器校验包、复制白名单文件、离线解压58项依赖、初始化每电脑独立MySQL及V1–V6、导入合成快照并生成随机账号，然后启动回环服务、打开浏览器。缺失/错误哈希立即失败，**不尝试联网补齐**。
5. 记下显示的本地安装路径。私下在该目录运行 `CREDENTIALS.bat` 获取本次ADMIN/READER密码，不分享、不录屏；打开 START 显示的 `http://127.0.0.1:端口`，不要猜固定端口。
6. 结束只在本地安装目录运行 `STOP.bat`。以后从本地 `START.bat` 启动。数仓场景先STOP再 `START-WAREHOUSE.bat`。两个数据库独立，不把数仓和预测伪装为同一个发布数据集。

可用的非交互参数（供维护者测试）：`RUN-FROM-USB.bat -Destination "D:\UC-Defense" -AcceptLicenses -NoBrowser`。普通用户双击即可；`-AcceptLicenses`代表操作者已阅读并接受随包声明。

MySQL写入每安装唯一ASCII原生目录，具体位置在 `state/mysql-location.json`。C盘、LocalAppData、受管目录可能存在原生路径/权限问题；保留失败现场，换另一可写本地磁盘的新目录，不改全局安全设置，不清库，不从其他电脑搬已初始化目录。

现场故障：文件缺失/哈希不符→从完整ZIP另解压；缺VC++→运行事先携带的官方离线安装器；空间/权限不足→换本地可写磁盘；端口冲突/重复启动→确认本份是否运行，正常STOP，不结束未知进程；DB初始化失败→保留本地state/initialize.log及MySQL原生日志，另建目录；已开始初始化的副本不会被覆盖重建。USB复制中断且目标文件不完整时也另选新目标，原文件保留。

本地备份需先STOP，再私下保存state及指向的MySQL目录；DPAPI仅当前Windows用户/机器有效。发行包不包含这些个人运行状态。第三方归档、来源、锁、许可和对应源码/源码提供书都随包保留；详见 `licenses/DEPENDENCIES.txt`，不作商业/公开发行许可保证。

所有预测/数仓均为synthetic_test已发布快照。真实交通授权仍BLOCKED，真实准确率和跨城市泛化NOT_EVALUABLE；研究导入不自动ETL/训练/发布，Windows现场不搭建Hadoop/Hive。

## 工作台候选版

0.9.0-workbench-candidate 沿用本页离线安装和停止重启流程。首页默认选择有数据城市及最近有效 UTC 观测时段，无需手动指定合成样本日期。五入口和数据语义见 [工作台使用说明](workbench.md)。预测保留发布截止日，绝不滚动成今天的预测。
