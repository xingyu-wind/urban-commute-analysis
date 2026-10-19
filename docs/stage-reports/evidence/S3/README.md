# S3 本机证据

这些文件来自 2026-10-19 Windows 正式工程的实际运行，非手填模拟响应。local-summary 包含真实子命令和退出码；数据库和环境信息来自实际工具查询；browser 保存请求、源码哈希、JAR 哈希与进程清理证据。只有明确标记 synthetic_test 的虚构样例，没有真实交通观测。

原始构建日志位于 backend/target/s3-isolation-final-console.log、backend/target/s3-verified、backend/target/s3-development；预期失败日志与最终成功套件分开。持久库和账号未被清理。CI 引用见上级 S3.md 与 PR 最新 checks。凭据没有复制到此目录。
