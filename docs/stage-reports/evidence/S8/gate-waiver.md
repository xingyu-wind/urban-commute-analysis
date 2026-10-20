# S7 门禁有限豁免记录

授权来源：本次聊天中用户明确指示：“将门禁跳过。进行一次有记录、范围有限的 S7 门禁豁免……然后正式开始S8。”

执行日期：2026-10-21（Asia/Shanghai）。范围仅为本次 S8 启动，不形成后续阶段通用豁免。

保留的真实核查：PR #8 已合并至 main；远程 main 与合并提交均为
`f52f66980988fa293d814928ba296bbbb285e197`；Run 39449864006（S6）及
39449864011（S7）均 completed/success、head_sha 与该提交一致。
该提交 check-runs 总数为 2，warehouse 与 regression 均 success；传统 statuses 为空。
用户授权后再次只读查询 main 和两个 Run，结果一致。

豁免项：不能通过分支保护/规则 API 独立证明“没有遗漏其他必需检查”。
连接器分支保护查询为 403 Resource not accessible by integration；本地既有 Git
认证查询 branches/main/protection、rules/branches/main、rulesets 均为 403，提示
Upgrade to GitHub Pro or make this repository public。main 返回 protected=false。
不把 403 或空 statuses 的 pending 当作 CI 成功证据。

操作：在该明确授权下解除 S8 启动阻塞，从上述 main 创建
`codex/s8-security-operations`。创建前工作区干净且该分支不存在。
未修改仓库可见性、订阅、规则、历史报告或 S7 验收状态；未取消、重跑或跳过任何实际 CI。
没有将 S7 自行标记 ACCEPTED。S8 仍须独立测试、真实 PR/CI 和独立验收；不授权合并或 S9。

复核链接：
- https://github.com/xingyu-wind/urban-commute-analysis/pull/8
- https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39449864006
- https://github.com/xingyu-wind/urban-commute-analysis/actions/runs/39449864011
