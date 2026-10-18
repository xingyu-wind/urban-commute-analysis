# WP6 证据说明

- local-verification.json：本轮重新运行的 Windows 命令退出码和数量，不复用 WP5 结论。
- prepush-audit.json：首推前 4 个提交的历史 blob/敏感模式及忽略规则核查。
- browser/：本轮真实 Chrome 清单、Java 响应、两份 Vite 502 文本、实际 Schema/日志关联结果。
- http/：本轮独立 JAR 启动/停止清单和 12 份响应；JUnit 真实网络响应另由相同验证器检查。
- negative-checks.json：6 个故障子检查真实退出 1，外层驱动退出 0。
- cloud-initial.json：GitHub API 实际返回的首次技术 Head 两次成功 Run、PR Job 全部步骤状态。
- cloud-log-summary.txt：下载真实 PR Job 日志后保留的测试/HTTP/浏览器/故障自验输出；完整日志留在项目外 D 盘临时目录，GitHub 仍可核查。

这些是历史快照，不是预生成的测试输入，也不包含完整 Java 日志、浏览器二进制、缓存或 JAR。完整本机日志/截图在被忽略的 backend/target/wp6-http、frontend/outputs/wp6-browser、frontend/outputs/wp6-negative；要复验应重新运行回归指南，不对历史快照冒称重新访问了 HTTP。

首次云端证据 SHA 为 f966378d3721b5409413f25098f12d4bcf5613c8；本证据文件所在报告提交也会产生新 Head。最终 Head 对应的云端验证完成后，在 PR #2 正文和最终执行摘要记录完整 SHA、Run/Job/结论，不循环补交只为自引用 SHA 的提交。请独立审核者核对最新 PR Head 与 Checks。
