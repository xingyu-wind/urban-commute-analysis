# Windows ZIP 竞赛候选包

状态：T2 候选交付，`SOLO_OWNER_REVIEW`。不创建正式 Release/安装程序，不替代 S9 独立验收。

## 路线选择

| 路线 | 代价与结论 |
|---|---|
| 所有二进制随 ZIP 分发 | 可减少首次网络依赖，但 MySQL/JRE 的源码、声明、完整依赖再分发义务和体积需要额外维护；本轮不采用 |
| 联网首次配置，取得官方便携组件 | 本轮采用。用户无需开发环境、全局 Java/Python/MySQL 安装；需同意依赖条款、网络和本地可写磁盘 |
| Windows 安装程序或服务器 | 不在 T2 交付范围 |

源码包、CI 诊断 ZIP、开发 venv/node_modules 都不是发行包。运行包的 `application.jar` 保留正式构建的全部应用 class/resource 字节及 Apache 许可的 Spring Boot launcher；移除嵌套第三方 JAR，由 `PropertiesLauncher` 加载首次配置从 Maven Central 直接下载的固定依赖。此过程不修改业务 class、迁移、鉴权或发布算法。

## 使用者流程

1. 解压到当前用户可写的本地 NTFS 目录，完整路径短于100字符；先运行 `CHECK-ENV.bat`。
2. 运行 `FIRST-SETUP.bat`，阅读 README 和许可证后输入 `ACCEPT`。自动取得58个固定组件，归档合计约497MB；不是离线包。
3. 私下运行 `CREDENTIALS.bat` 查看本次随机密码；然后运行 `START.bat`，访问显示的回环 URL。
4. 模型场景选择 `s7-city`，查看截止日2026-10-19开始的七日预测。数仓场景先 `STOP.bat` 再 `START-WAREHOUSE.bat`，选择 `s5-city`。
5. 使用 `STOP.bat` 停止。重复首次配置不会覆盖已完成实例；失败的未完成配置保留现场，另选新解压目录。

不需要 IDE/Git/Maven/Node。便携 Python 3.11.9、Zulu JRE21.0.12.1、MySQL8.4.11 由官方归档准备，不复制虚拟环境。Python wheels 和 Java依赖固定版本/URL/SHA256。首次网络下载使用系统证书校验，不关闭TLS验证；之后启动无需联网。

默认无需管理员权限、不注册服务、不改 PATH/防火墙/注册表/全局执行策略。BAT 仅对其子 PowerShell 使用进程级 `ExecutionPolicy Bypass`。缺失 Microsoft VC++ x64 运行库时可能需要用户/管理员按官方说明安装；没有静默提权或捆绑未经审查的微软运行库。

Windows 10/11 x64 是目标平台；本次实际环境为 Windows11 x64，同机隔离目录，不是全新电脑验收。ARM、其他系统、所有Win10版本、缺少VC++的干净系统均未宣称通过。至少预留3GiB磁盘；8GiB内存是准备建议，不是容量承诺。

## 目录、数据与账号

- `launcher/`：PowerShell 引导与 Python 监管器；静态 dist 和同源 API 代理由监管器提供，无 Node/Vite 运行依赖。
- `app/`：正式前端、薄 JAR、现有Python桥接及必要项目模块；中文 stdin 通过打包专用 UTF-8 包装入口解码。
- `database/`：17张允许业务表的两个合成快照、来源说明及原创研究CSV；不是完整数据库dump。
- `config/components.lock.json`：官方组件完整性与来源锁；`BUILD.json` 和 `MANIFEST.sha256` 记录源码和产物身份。
- `runtime/`：首次取得的运行时、依赖及归档；不随本候选ZIP分发。
- `state/`：本份实例配置、Windows当前用户DPAPI密文、私有日志、上传与启动状态。仅当前用户ACL。
- MySQL 为每份安装创建独立目录、端口、随机schema和单库账号，原始业务库完全不参与首次配置。

MySQL Windows原生路径存在中文兼容问题。本包将它放在解压位置或最近可写ASCII父目录下的唯一 `UrbanCommute-LocalData-*`，必要时尝试当前用户LocalAppData的ASCII路径；精确位置在 `state/mysql-location.json`。没有可用位置会拒绝初始化，请换到可写ASCII父目录下解压。不会修改全局8.3/长路径策略或创建系统服务。

**备份**：先STOP，私下保存整个 `state` 和 `mysql-location.json` 指向的目录。DPAPI仅当前Windows账号/机器可用，不能把初始化后的目录当作发行包转交他人。未实现原地升级、跨用户密钥迁移或整机灾备；新版本使用独立新目录，不用 Flyway clean/repair 绕过历史校验。

初始化只接受新数据目录，正式JAR执行原V1–V6迁移；所有允许的业务表为空时才在事务内导入种子。账号通过原 `UserProvisioning` 创建，ADMIN/READER各自随机强密码；没有固定密码或随包密码哈希。两场景独立库，不拼造一个同时拥有两类发布的假数据集。

监管器用文件锁拒绝重复启动，检查端口并验证真实MySQL datadir/server_uuid；只回收其Windows Job Object内的子进程。STOP用私有请求文件，MySQL执行自身正常shutdown；监管器被强制终止时Job回收子进程，下次启动验证实际崩溃恢复。不会按旧PID或端口杀未知进程。正常使用仍应先等待导入任务完成再STOP。

## 构建与验证（维护者）

```powershell
# 构建时才需要现有开发环境。运行者不需要它们。
backend/mvnw.cmd -f backend/pom.xml -B -ntp package -DskipTests
npm.cmd run build --prefix frontend
ml/.venv/Scripts/python.exe scripts/build_windows_zip.py --output dist/t2-candidate-NEW

# 在新解压的独立目录中运行；这是实际MySQL/HTTP/权限/桥接/进程生命周期验收。
ml/.venv/Scripts/python.exe scripts/test_windows_zip.py --root '<独立解压目录>/UrbanCommute-Demo' --output backend/target/t2-test-NEW --browser
```

`--browser`复用现有S9真实Chromium驱动。测试驱动来自开发环境，但被测程序PATH移除Java/Node/Python/MySQL，工作目录在解压位置；没有把开发环境当作软件运行依赖。

`t2_lock_downloads.py`仅供维护者显式更新组件锁，会访问官方元数据并下载/验证归档，不是用户启动步骤。`t2_export_seed.py`只读处理已核验的合成源库，逐点比较4368条原fixture、逐值比较40条Hive对账结果；正式数据门槛和原发布准入不变。不得把它指向真实/未知库，不能把任意dump包装成种子。

## 真实性和发行边界

预测、数仓查询读取先前合法发布的合成快照；没有本机重训、没有Windows集群计算。Python网页上传只产生研究输入。真实交通来源、真实准确率、跨时间/跨城市泛化继续BLOCKED/NOT_EVALUABLE。

候选ZIP仅包含必要的项目文件和已保留声明的前端/launcher内容。JRE、MySQL、Connector/J及其他第三方依赖由接收者直接取得，原license/notice文件保留。`licenses/DEPENDENCIES.txt`明确来源与许可证边界；不能据此把初始化后的二进制目录再次打包公开分发，也不作商业发行或完整软件许可保证。
