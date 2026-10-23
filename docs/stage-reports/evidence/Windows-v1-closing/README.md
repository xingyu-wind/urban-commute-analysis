# Windows 安装版收尾：SAC 诊断及真实安装生命周期

2026-10-23，在安全策略未更改的前提下复用最终 candidate-04。产品 EXE 字节未变，仍是 SHA256 `f42364651949e57f97c42982359d335c91826a17d092a78bb12c06688005e630`。

- `sac-state.json` + `enforced-policy-load.json`：SAC state=1，实际加载策略 VerifiedAndReputableDesktop、GUID、版本与策略哈希。CiTool 列表查询在当前非提权会话受限；没有借此改策略。
- `blocked-events.json`：本轮最终包和实际安装目录中的 Electron 拒绝事件，均来自同一策略；Requested=2、Validated=1、Status=0xc0e90002。
- `native-launch.json`：不带 inspector 参数，直接原生创建应用进程仍 WinError 4551；不是单纯浏览器驱动故障。
- `electron-signatures.json`：应用 EXE 和四个 DLL 未签；两个 Microsoft DLL 签名有效。CU/LM My 无代码签名证书。
- `setup-lifecycle.json`：**安装后的独立窗口失败与安装本身成功分开记录**。原始 `desktop-closing-install-01` 安装 exit=0；随后实际卸载 exit=0；本目录脚本再完成卸载后重装、同版本覆盖、快捷方式校验和最终卸载，全部 exit=0。
- `shortcuts.json`：实际桌面及开始菜单链接目标，包含中文/空格安装路径；最终卸载后均已移除。
- `retained-data-fingerprint.json`：安装生命周期前后，本任务此前创建的隔离 MySQL 两库/17 张业务表、UUID、DPAPI 账号凭据文件指纹一致。**独立窗口从未初始化，因此不宣称图形应用跨版本迁移已通过**。
- `ci-completed.json`：PR #11 既有应用代码提交 `4d07327` 的 Windows、核心、数仓三个 PR runs 均 completed/success。`6fd6faf` 是后续纯文档提交，原先明确 skip ci。新收尾提交的结果以其实际 checks 为准，不能混用 SHA。

新验收脚本 `scripts/test_desktop_setup_lifecycle.py` 可复现安装生命周期；原始安装、覆盖、卸载日志位于 `backend/target/desktop-closing-*`。测试最终移除本轮软件文件、快捷方式和卸载注册项，保留全部旧测试数据和原候选包。未删除旧数据库、修改 main 或创建正式 Release。

合法解决路径见 [可信签名收尾](../../../guides/windows-signing.md)。本轮没有代码签名证书，因而没有签名后的候选，也没有将独立窗口/物理离线/图形跨版本升级记为通过。
