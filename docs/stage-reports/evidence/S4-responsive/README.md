# S4 PR #4 响应式专项证据（2026-10-20）

原 HEAD 0d0202d 的 PR/Push CI 都在原 verify-integration.mjs:169 的390px断言失败；ci-original.json摘录实际日志，original-ci-failure.png来自PR Run39281005692的上传产物，图片宽908px。

根因通过真实Java/Vite/MySQL、Playwright Chromium156.0.8078.4测量：1024→390时外层图表298px，ECharts渲染div/SVG仍862px、右边界908px。保持原生ResizeObserver回调尚未交付的状态，复现页面scrollWidth908；释放回调恢复390。root-before.json为修复前测量，root-after.json为修复后同一缩窄场景（同时覆盖S4地图图表）。此探针仅推迟原生observer交付，无HTTP替身；正常原始断言仍按原样立即执行。

唯一产品改动是 .traffic-chart 增加overflow:auto：回调前完整旧图面可内部滚动访问，页面不变宽；回调后渲染器、SVG和容器同宽且无需横向滚动。没有全局隐藏、缩放或裁切关键内容。此前本机Chrome155.0.8059.80；这次使用与CI同版本Chromium156.0.8078.4，仍为Windows本机，Linux结果由当前HEAD的真实CI复核。

local-summary.json / core-summary.json：scripts/s4_checks.py --with-core完整运行成功，Java82、Vue63、类型/构建、原S2/S3真实回归和反向验证、独立SQL、S4浏览器、真实响应Schema及修改恢复均通过。所有库均为准备器新建随机隔离库。

四份*-layout.json覆盖320/375/390/768/1024/1440：原城市目录正常页、断连错误页、S4有数据页、大屏。断言包括立即检查页面宽度、关键组件边界、KPI文字未裁切、控件中心可命中、表格末列可滚动访问、图表最终尺寸。deferred-chart-resize.json额外验证回调前仍然不撑宽页面、完整图面可滚动访问，释放原生回调后真实重排完成。

s4-*.png和presentation-*.png为本次真实浏览器截图；完整响应/日志/其余截图在gitignored backend/target/s4-responsive-fixed，云端相同驱动产物由Actions保存。新增探针和矩阵没有删除、跳过或放宽原390px断言。

cloud-fix-success.json记录修复提交76fa63a的真实云端PR/Push完整Job均SUCCESS及日志摘录；原390px检查、全部新增检查均执行通过。最后的证据/报告补记HEAD还需单独检查，最终状态见PR正文。
