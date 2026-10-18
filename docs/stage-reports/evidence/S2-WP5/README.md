# WP5 实测快照

verification-summary.json 汇总真实退出码、数量与验证边界；browser/ 保存本次浏览器清单、8 份真实 Java JSON、2 份 Vite 502 文本与 Schema 结论；http/ 保存独立 JAR 的清单与 12 份实际响应；negative-checks.json 保存 6 项预期失败的真实退出码。

快照供审阅，不是预先生成的通过凭证。完整日志、JUnit XML、截图和故障诊断仍在被忽略的 backend/target/wp5-http、frontend/outputs/wp5-browser、frontend/outputs/wp5-negative；manifest 中的本机绝对路径是本次历史记录。Java 日志关联已在原始运行目录实测通过；未复制日志或浏览器二进制到 Git。复现时按回归指南运行驱动生成新的完整证据，不对历史快照冒称重新进行了 HTTP 验收。

本次正常 Maven verify、npm ci、type-check、test、build、HTTP、浏览器、故障自验、最终 actionlint 和 CI 策略检查均退出 0。actionlint 首次退出 1，发现 job.env 不允许 runner 上下文；改为运行步骤向 GITHUB_ENV 写入 RUNNER_TEMP 路径后退出 0。故障注入的各子进程退出 1 是预期拒绝，外层驱动退出 0。Windows 终止自己 Java 服务的进程退出 1 不代表测试驱动失败，清理已另行核实。
