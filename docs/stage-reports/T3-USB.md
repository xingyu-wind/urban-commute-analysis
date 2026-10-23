# T3-USB｜离线答辩候选交付

结论：**USB_CANDIDATE_LOCAL_PASS（同机全新运输/部署目录、独立离线执行路径）**。首次配置和答辩核心流程真实通过；整机未断网，没有真实U盘设备/异机/干净Windows/Windows10验证，不作普遍兼容或正式发行承诺。T3.1的 **BLOCKED** 历史保留，按本任务要求不再作为USB交付前置。

## 候选身份

- ZIP：`D:/WindXingyu/Code/urban-commute-analysis/dist/t3-usb/UrbanCommute-USB-Demo-0.9.0-offline-candidate-windows-x64.zip`
- 大小：**1021842976字节**，477个文件。
- 完整SHA256：**`e473a2d912b72be98171a55aa55f882139b5dfac0bbc4f99299f78f8b1377e19`**。
- 业务基线：`97f30db15a5292c0be9a0103359ccc7e97f5ddfa`；USB打包提交：`5f846e0964ff2ea8c08fb46eee53313d4290c79d`，构建时工作区干净。
- 原fat JAR：`9ab652e6f98e4625f479710c318f9c57aa58e16460ff4780a725150e4d11f433`；薄JAR：`17b8b48e9127cc984b01f2a464c24d34c1505f766f777005e91e6533e3c79608`。应用class/resource、前端3文件和业务程序与T3相同，没有重编业务或重训。
- 完整逐文件清单/哈希、58项组件校验见[evidence/T3-USB/zip-inspection.json](evidence/T3-USB/zip-inspection.json)，来源与构建身份见[evidence/T3-USB/identity.json](evidence/T3-USB/identity.json)。

开始时实际HEAD为 `31c29dd8a64dfe2cb278d0ae7375d1f25ba6e3de`，分支codex/s9-system-release，工作区干净；核实5940420、4ad09c4、31c29dd完整提交后新建本地 `codex/t3-usb-offline`。原T3 ZIP仍为722218字节、SHA256 `9acbe39f35bf69dcf4bfcb35ac63a38ac0feeffeedea34afc455352f5c450f2f`，未覆盖。全部历史提交、失败现场及证据保留，无push、merge、Tag/Release、公开仓库、公网部署或远端重型CI。

## 离线内容与分发边界

包内 `vendor/components` 含58份原始官方归档，共 **497107997字节**：Python3.11.9嵌入包、Zulu JRE21.0.12.1、MySQL8.4.11、12个Python wheel和43个Java JAR。固定版本、官方URL、大小及SHA256沿用并复核原组件锁。制包允许复用已下载且逐项重新校验的原始归档；不复制已安装runtime、数据库、DPAPI或凭据。

`vendor/sources` 再提供88份对应源码/元数据，共 **523466183字节**：MySQL8.4.11完整官方源码、Python3.11.9源码、43份Java sources JAR和43份POM；有单独源码锁。MySQL源码INFO_SRC与二进制INFO_SRC同为 `fe442869f39a69d69f2cb4384d6c6b5763faa1d0`，源码包含构建脚本。上游源码SHA256由官方HTTPS取得完整文件后固定，不冒称独立供应链签名认证。

保留全部原始归档及内部LICENSE/NOTICE，并额外提取可直接阅读的许可/声明，建立NOTICE-INDEX。Zulu原readme包含上游三年源码提供书、邮箱和精确构建身份，完整转交；非商业分发按GPLv2第3(c)项保留上游提供书信息，不虚构本项目自己的源码承诺。MySQL、Connector/J及Java源码随行。**交付范围为用户本人受控、非商业答辩迁移；没有改项目许可证，也不授予任意第三方/商业再分发权。** 此范围不限制各第三方自身许可证已授予的权利；向其他主体转交组合产品需另核适用条款。

微软VC++再分发资格不能由“可以下载”推定。官方说明要求再分发者具有适用Visual Studio许可，因此安装器**不纳入通用ZIP**。本次已为用户从微软直接取得单独的离线安装程序，供本人受控安装并与ZIP共同携带：

- `D:/WindXingyu/Code/urban-commute-analysis/dist/t3-usb-prerequisites/VC_redist.x64.exe`
- 18731856字节，版本 **14.51.36247.0**；Authenticode Valid、Microsoft Corporation。
- SHA256：`843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c`。
- 同目录receipt.json含官方固定解析URL、版本/哈希/签名。本次没有执行该安装器。
- 获取及资格依据：[微软官方说明](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)。需要补库时由有权限者交互运行，接受微软条款，可能需要管理员；不静默提权，不私拷系统DLL，不把本记录当再分发授权。

因此：Java/Python/MySQL/桥接与应用依赖全部包内离线准备；VC++属于明确的系统前提，**缺库的完全离线现场必须同时携带上述本人直接取得的安装程序**。只带ZIP且目标缺VC++时会明确拒绝，不能声称这种条件也开箱即用。

## 真实测试与失败保留

系统为Windows11家庭中文版x64、10.0.26200，非管理员；本机已有VC++ x64 v14.50.35719.00。运输目录 `D:/WindXingyu/Apps/USB 答辩 01/UrbanCommute-Demo` 从最终ZIP新解压，初始无runtime/state；本地目标 `D:/UC-USB-1021-01` 原先不存在。运输目录模拟USB来源，未假称实际移动介质或另一台电脑。

| 验收 | 真实结果 |
|---|---|
| 包体与依赖 | CRC、清单覆盖全部477文件、逐文件SHA、58项原始组件、88项源码/元数据大小及SHA全部通过 |
| 一键本地部署 | RUN-FROM-USB实际复制白名单文件到全新本地NTFS目录，CHECK→FIRST-SETUP→START成功；中文/空格来源路径通过 |
| 首次离线配置 | 58项逐一显示Verified offline component，Python/科学计算库导入通过；独立MySQL、两个schema、正式V1–V6和种子/随机账号初始化完成；没有runtime/downloads或旧缓存复制 |
| 健康与业务 | 实际首页/health/cities、交通summary/series、七日预测、数仓查询成功；城市4项，预测7点，WINDOW数仓API3项（库内40条各粒度指标） |
| 登录与权限 | ADMIN/READER实际登录；匿名管理401、READER上传403、ADMIN无CSRF上传403；角色任务读取正确 |
| Python与研究 | 真实Chromium表单上传原创CSV、Python分析、未确认执行按钮禁用、完整JSON明确确认、导入SUCCEEDED、READER只读；独立HTTP链路也通过 |
| 图表页面 | 真实production dist，1440/390两宽度交通、预测、数仓页面；无请求拦截/页面异常，未使用Mock API |
| 生命周期 | 重复START拒绝，端口占用拒绝且未杀占用者；STOP/重复STOP/重启通过，旧会话401，导入状态持久化，最终所属端口释放 |
| 重复USB部署 | 只复验相同包文件，保留本地state和DPAPI凭据字节，启动/停止成功；未知或不同包目标不覆盖 |
| 离线缺件 | 新运输目录暂移Python归档：明确缺件、未下载、未生成runtime/state；恢复原文件 |
| 离线错误哈希 | 在运输副本破坏spring-jcl归档：校验拒绝、未下载/初始化；恢复原字节。最终ZIP未改动 |
| 非回环阻断 | 已安装离线监管器启用进程级审计钩子；外部域名及非回环IP连接测试在连接前拒绝；正常MySQL/Java/HTTP回环允许 |

测试驱动使用开发机现有Python/Node/Chromium，但被测BAT移除开发Java/Node/Python/MySQL的PATH，程序仅使用本包运行组件。另传入失效代理，回环请求由显式NO_PROXY保障；没有禁用TLS、哈希、认证或系统安全设置。

**网络边界**：整机没有断网，也没有系统级防火墙/抓包断言；Python监管器的外部DNS/非回环阻断不覆盖整台Windows、浏览器及全部原生子进程。因此结论是“全新目录、完整包内依赖、禁止下载的独立离线执行路径真实成功”，不是“已完成物理断网/异机验收”。缺VC++、实际低容量卷及初始化中途杀进程仍未实测，不改写为通过。

保留的首轮失败：维护者取得MySQL源码时先只收到135816593字节，旧收集器最初仅固定了收到的字节；随后的完整tar校验真实失败。该文件从未进入候选ZIP。修复收集器，增加Content-Length、tar/ZIP/XML完整性检查，保留坏文件并重取；整文件传输停滞后只停止经核实的本轮源码下载进程，改用官方206 Range逐段核对Content-Range和长度。最终479170675字节归档通过完整解压检查及INFO_SRC对照，才更新源码锁并生成唯一候选ZIP。失败与复测日志均保留。

既有T3的420秒演示、监管器硬退出和MySQL崩溃恢复、S9真实Hive链路采用历史证据引用；没有重新执行计时排练、训练或HDFS/Hive。USB新增初始化进程纳入Job并在本轮正常初始化/退出中实际使用；未另外声称完成“初始化中强杀”故障测试。

## 现场最短步骤与限制

1. U盘带完整新ZIP及单独的 `t3-usb-prerequisites` 文件夹。ZIP约1.02GB，建议U盘至少2GB可用；目标本地盘至少5GiB空闲，建议8GiB以上，建议8GiB内存。
2. 目标需Windows x64、PowerShell5.1、浏览器、VC++ x64 v14。缺VC++先由有权限者交互安装事先携带的官方程序；不需要IDE/Git/Maven/Node或手工配置Java/Python/MySQL。
3. 解压ZIP，双击RUN-FROM-USB，选本地可写固定NTFS目录（优先合适的数据盘），阅读声明输入ACCEPT，等待配置并打开显示的127.0.0.1地址。
4. 在显示的本地目录私下运行CREDENTIALS查看随机账号；s7-city点击“合成样本时段”查看交通/预测；数仓先STOP再START-WAREHOUSE、选s5-city；结束本地STOP。

MySQL使用每安装唯一ASCII原生存储，位置见私有state/mysql-location.json。任意C盘/LocalAppData/企业目录不保证可用；初始化失败保留日志、换可写本地盘的新目录，不能覆盖旧数据。初始化状态/DPAPI不跨电脑迁移，复制中断且目标文件不完整时另选新目标。尚未验证真实U盘设备、独立电脑、干净Windows、Win10/ARM（ARM被拒绝）、缺运行库/实际低磁盘、所有安全软件与磁盘策略。

可直接把 **`D:/WindXingyu/Code/urban-commute-analysis/dist/t3-usb-delivery` 整个目录复制到U盘**：已经汇集同SHA候选ZIP、独立VC++前提文件夹、START-HERE速查、DEMO及HISTORICAL-EVIDENCE。历史目录包含S9实现基线的真实Hive/对账/恢复摘要和T3真实演示证据；显式标注为历史，不当成本次Windows现场计算或USB提交CI。

操作指南：[windows-usb](../guides/windows-usb.md)；[一页速查](../guides/usb-defense-quickref.md)；[5–7分钟流程及备用方案](../guides/usb-defense-demo.md)；[知识关联](../learning/T3-USB-知识关联与实现说明.md)。指南已随候选ZIP携带，现场目录也提供独立可读速查与备用证据。

真实性保持 **synthetic_test / BLOCKED / NOT_EVALUABLE**：预测和数仓是合法已发布的合成快照，非现场实时训练、非真实交通准确率或普遍跨城市泛化；研究导入只产生隔离研究输入，不自动ETL、Hive、训练或正式发布。

## 重建与证据

```powershell
# 维护者联网收集，仅在显式更新源码锁时执行；不属于目标配置入口。
ml/.venv/Scripts/python.exe scripts/prepare_usb_sources.py --output dist/t3-usb-sources
# 使用当前锁定输入，从打包提交5f846e0的干净树构建到新的不存在目录。
ml/.venv/Scripts/python.exe scripts/build_windows_zip.py --output dist/t3-usb --jar dist/t2-frozen-application/backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar --application-source 97f30db15a5292c0be9a0103359ccc7e97f5ddfa --version 0.9.0-offline-candidate --offline-components '<已验证官方归档目录>' --offline-sources dist/t3-usb-sources
ml/.venv/Scripts/python.exe scripts/check_windows_zip.py --zip dist/t3-usb/UrbanCommute-USB-Demo-0.9.0-offline-candidate-windows-x64.zip --output backend/target/t3-usb-evidence/zip-inspection-before.json
ml/.venv/Scripts/python.exe scripts/test_usb_offline.py --zip dist/t3-usb/UrbanCommute-USB-Demo-0.9.0-offline-candidate-windows-x64.zip --media 'D:/WindXingyu/Apps/USB 答辩 01' --destination D:/UC-USB-1021-01 --output backend/target/t3-usb-acceptance
```

输出/测试目录须不存在；重建仍需重新计算ZIP和清单、对新身份验证，不保证跨机器逐字节相同ZIP。全部测试日志位于backend/target/t3-usb-evidence、t3-usb-acceptance；[永久USB证据](evidence/T3-USB/README.md)记录本次候选和受影响验证结果。测试结束本地副本停止；通用ZIP只含静态白名单/原始第三方归档，没有state、私有数据库、DPAPI、账号/审计表dump、个人凭据、外部原始数据或权重。到此停止，等待总规划师独立验收，不自动进入T4。
