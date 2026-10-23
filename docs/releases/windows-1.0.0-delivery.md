# Windows 1.0.0 单机演示版交付报告

状态：**候选 EXE 已能构建；安装/独立窗口被本机 Windows 应用控制阻塞，未达到完整 Windows 安装验收。** 用户确认暂无可信签名证书，选择保留候选并记录阻塞。未正式发布。

基线为 Workbench `13f823b`，完整延续 S9/T2/T3/T3-USB，保留所有旧候选包和数据库。开始时工作区干净；分支 `codex/windows-v1-desktop`。本地全历史备份 `dist/pre-v1-local-history.bundle` 已通过 `git bundle verify`。

复用最新 Workbench 生产前端、原 Java 应用与合成发布种子、58 项离线组件锁、88 项对应源码/元数据、原 Python Job Object 进程监管。新增 Electron 独立窗口、Inno Setup 当前用户安装/卸载、数据分离、备份后迁移及关闭协调。

全部演示数据是合成测试数据，不能宣称真实交通预测效果。没有合并 main、创建 Tag 或正式 Release。

## 安装和使用

双击 `UrbanCommute-Setup-1.0.0.exe`，完成安装后双击桌面“城市通勤演示版”或安装目录 `UrbanCommute.exe`。首次自动初始化，后续直接进入工作台；菜单提供随机账号、两场景切换及数据目录入口。程序默认 `%LOCALAPPDATA%\Programs\UrbanCommute`；数据 `%LOCALAPPDATA%\UrbanCommute\DesktopData`，卸载/升级不删除数据。详见 [桌面版说明](../guides/windows-desktop.md)。

**本机当前无法执行上述安装/启动步骤**：Windows 应用控制返回 WinError 4551，CodeIntegrity 3077，要求可信签名；安装器和官方 Electron 运行时均未签名。未找到现有代码签名证书。未禁用防护、创建自签信任或改安全策略。取得可信签名后仍需重新实测安装/窗口/卸载/重装，不能仅据本报告认定可交付普通终端。

## 实际验收

| 项目 | 结果与限制 |
|---|---|
| 安装程序编译 | Inno Setup 实际生成单文件 EXE，完整内置运行时、原始源码/许可及本人取得的 VC++ 前提安装器 |
| 包内离线初始化 | 通过；新的隔离数据目录、两套独立 schema；未借用旧 runtime、凭据或数据库 |
| 主要页面与预测 | 通过；真实浏览器、生产资源和包内 Java/MySQL；两场景共 32 组页面/视口，七个预测日期和数值逐点对应 API；合成标识可见 |
| 服务生命周期 | 通过；重复启动拒绝，正常停止释放全部端口；模拟桌面父进程退出触发 Job 回收，随后启动恢复；最终全部停止 |
| 数据分离和升级 | 通过服务层测试；程序目录无 state/runtime；测试 JAR 身份变化触发双库 mysqldump、Flyway 校验和重启；两库 17 张业务表及凭据指纹不变，未重新灌种子 |
| 离线运行 | 包内离线路径、不可用代理、清除开发工具 PATH 通过；浏览器断网清状态/恢复通过。未整机物理断网 |
| 安装、独立窗口、快捷方式、卸载、重装 | **BLOCKED / 未实测通过**；本机应用控制在执行 EXE 前拒绝，不能把包内服务通过视为这些项目通过 |
| 缺 VC++、干净 Windows、Windows 10/ARM | 未验证；本机 Windows 11 家庭版 x64，build 26200、已有 VC++；没有可用 Windows Sandbox。ARM 不在支持范围 |
| 真实交通准确率/泛化 | NOT_EVALUABLE；全部合成数据，未重训或虚构真实效果 |

升级测试保留原业务字节码/迁移 SQL，只改变 JAR 身份；未验证未来破坏性迁移、迁移失败后的人工恢复或全机灾备。旧 USB 数据不会自动迁入桌面新数据目录。完整历史阶段证据继续保留。

证据入口：[Windows-v1](../stage-reports/evidence/Windows-v1/README.md)。原始现场位于 `backend/target/desktop-*`。首次初始化后的测试驱动编码错误与安装/窗口拦截均保留；修正驱动后服务全流程通过。截图为系统浏览器，不冒称独立窗口。

## Git 与独立验收

分支 `codex/windows-v1-desktop`，草稿 [PR #11](https://github.com/xingyu-wind/urban-commute-analysis/pull/11) 指向 main。已推送原先本地未同步的祖先历史；本地旧分支与全历史 bundle 均保留。`main` 保持 `222f70d`，无强推、合并、Tag 或正式 Release。

EXE 构建源码提交与最终文件 SHA256 将随最终构建回执补齐；后续证据/报告提交与应用构建提交分开追溯。云端 CI 不能证明本机被拦截的 EXE 已通过验收。
