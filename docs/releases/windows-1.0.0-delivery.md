# Windows 1.0.0 单机演示版交付报告

状态：构建与验收进行中，待独立验收；未正式发布。最终 EXE 身份、实际测试与 Git/PR/CI 回执将在构建后填入。

基线为 Workbench `13f823b`，完整延续 S9/T2/T3/T3-USB，保留所有旧候选包和数据库。开始时工作区干净；分支 `codex/windows-v1-desktop`。本地全历史备份 `dist/pre-v1-local-history.bundle` 已通过 `git bundle verify`。

复用最新 Workbench 生产前端、原 Java 应用与合成发布种子、58 项离线组件锁、88 项对应源码/元数据、原 Python Job Object 进程监管。新增 Electron 独立窗口、Inno Setup 当前用户安装/卸载、数据分离、备份后迁移及关闭协调。

全部演示数据是合成测试数据，不能宣称真实交通预测效果。没有合并 main、创建 Tag 或正式 Release。
