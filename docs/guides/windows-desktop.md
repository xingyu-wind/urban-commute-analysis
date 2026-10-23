# Windows 单机演示版

候选产品版本 1.0.0；未创建正式 Release。全部内置观测、发布预测及误差均为 `synthetic_test`，不能用于证明真实交通准确率。

## 安装和使用

在 Windows 10 2004+/Windows 11 x64 双击 `UrbanCommute-Setup-1.0.0.exe`，接受随附组件许可说明，完成安装。默认安装到 `%LOCALAPPDATA%\Programs\UrbanCommute`，不要求开发环境。缺少 VC++ x64 运行库时安装器调用本人已取得的随附微软安装程序，可能需要 UAC/许可确认；不联网下载。

双击桌面“城市通勤演示版”或安装目录 `UrbanCommute.exe`。首次校验、解压和建库可能需要数分钟；等待窗口自动进入工作台。建议至少 8 GB 可用空间。菜单“帮助 / 本机演示账号”查看随机 ADMIN/READER 账号；普通分析与预测无需登录。“应用”菜单切换预测/数仓两套独立合成库；数仓读取发布快照，本机不运行 Hadoop/Hive。

关闭窗口会等待服务退出。再次双击继续使用。菜单支持刷新、缩放、全屏、打开数据目录。启动失败会显示原因并保留日志，可通过菜单重试；不得为解决错误而删除已有数据库。

## 数据与升级

程序文件与用户数据分离。数据位置 `%LOCALAPPDATA%\UrbanCommute\DesktopData`，含 state、runtime、浏览器本地资料及独立 MySQL 目录；MySQL 实际位置记录在 `state/mysql-location.json`，中文 Windows 用户路径必要时另选同用户 ASCII 存储路径。凭据为当前 Windows 用户 DPAPI 密文，不能直接复制给另一 Windows 账号解密。

安装程序保持固定 AppId；安装前关闭旧窗口，覆盖安装较新版本或重装相同版本。卸载通过 Windows 设置“已安装的应用”或开始菜单卸载入口。卸载保留数据，不删除旧 USB/Workbench 安装或其他 MySQL 实例。更改安装目录仍使用同一用户数据目录；请勿并行启动不同版本。安装器拒绝覆盖降级。

后端 JAR 未变化的升级直接复用数据库；变化时监管器先对两套自有 schema 创建受 ACL 保护的逻辑备份，再执行新版本 Flyway，成功后更新版本身份，不重新导入种子。失败保留 `state/upgrade-pending.json` 和备份并阻止重试，需人工核验恢复；不自动回滚或覆盖数据库。备份仅覆盖 MySQL，完整迁移还需停机备份整个数据目录及 mysql-location 指向目录。

旧 T2/T3/USB 候选的数据不会自动迁入新桌面数据目录；避免将旧目录误认为本次已初始化的数据。已有历史库继续保留，可另行安排受控迁移。

## 开发复现与追溯

使用 `scripts/build_desktop_installer.py --output dist/新的候选目录`。构建器要求干净 Git 工作区，核验原 Workbench payload 的每个文件、应用源码一致性和新工具 SHA256；保留原源码/组件锁、许可与基线 BUILD 身份，生成新的桌面 BUILD、清单与构建回执。

构建工具锁见 `infra/desktop/tools.lock.json`。独立窗口按 [Electron 官方分发结构](https://github.com/electron/electron/blob/main/docs/tutorial/application-distribution.md) 组装，安装采用 [Inno Setup 的当前用户模式](https://jrsoftware.org/is6help/topic_setup_privilegesrequired.htm)。工具本身不属于用户运行前提。安装器及应用未申请项目代码签名；独立验收和 Windows 环境实测边界见交付报告。
