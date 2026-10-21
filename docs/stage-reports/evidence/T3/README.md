# T3 实测证据索引

最新USB任务另见[专项证据](../T3-USB/README.md)及[T3-USB报告](../../T3-USB.md)：本机独立离线路径通过，原候选ZIP与以下历史证据保留；T3.1 BLOCKED仍是历史裁定，不再作为USB交付前置。

当前T3.1状态：**BLOCKED**，缺少可直接使用的干净Windows11 x64环境。T3历史状态仍为 **T3_PARTIAL**：最终ZIP本机空缓存配置、功能/故障验证和420.0秒七分钟连续验收通过。无干净Windows、Windows10、缺VC++或实际低磁盘容量环境通过证据。T3.1没有使用宿主机个人演示实例替代客机。

最终包：`dist/t3-final/UrbanCommute-Demo-0.9.0-t3-candidate-windows-x64.zip`，722218字节、46文件，SHA256 `9acbe39f35bf69dcf4bfcb35ac63a38ac0feeffeedea34afc455352f5c450f2f`。业务冻结97f30db，打包源码完整提交 `59404200921b97f86b3b57288a33b491244c793d`；BUILD记录构建时工作区干净。验证脚本和本证据提交不改变该ZIP。

| 文件 | 内容与边界 |
|---|---|
| preflight.json、remote.json | 实际Git/OS/磁盘/VC++/旧演示健康、PR与基线远端CI状态；不把旧CI算作新打包提交CI |
| original-zip.json | T2原包重新检查；原字节数/SHA256一致 |
| original-interruption.json、original-setup-interrupted.txt、original-retry-rejected.txt | 原包中断及真实重试失败；数据库尚未初始化，失败未删除 |
| final-empty-cache.json | 最终ZIP新解压后runtime/state均不存在、复制缓存为0 |
| final-cold-01-tls-failure.txt | 官方Java TLS EOF三次，退出1；未关闭TLS |
| final-interruption.json、final-cold-02-interrupted.txt | 最终包MySQL组件解压后人为终止专属组件准备进程，尚未初始化数据库 |
| final-cold-03-recovered.txt、acquisition.json | 本轮下载安全续跑、58个组件逐大小/SHA复核、数据库初始化成功；497107997字节为唯一合法归档合计，不是包括重试的总网络字节 |
| zip-inspection.json | 最终ZIP完整46文件和每文件SHA256；CRC、MANIFEST全覆盖、应用/前端/种子与8个当前秘密排除扫描通过 |
| acceptance.json | 新包真实BAT/32次HTTP/权限/桥接/导入/SQL V1–V6/重复启动/端口占用/正常重启及异常Job回收 |
| browser-model.json、browser-warehouse.json、browser-management.json | 1440/390真实Chromium；管理表单ADMIN→原创CSV→明确审查→SUCCEEDED→READER任务/无上传控件→退出；没有请求拦截 |
| download-faults.json、download-faults.txt | 发行包下载函数与真实回环HTTP故障服务器；截断响应、错误哈希、损坏缓存、partial、重试耗尽；明确不算官方下载或业务API成功 |
| unwritable.json、unwritable-check.txt、license-declined.json、license-declined.txt | 专用副本不可写失败、恢复后通过；拒绝许可后未下载/未生成状态。没有修改系统ACL |
| startup-faults.json、startup-faults.txt、startup-owned-errors.txt | 真实MySQL日志写共享失败、MySQL已启动后的Java临时路径失败；专属监听回收；解除故障后重启正常，数据库文件未删除 |
| seven-minute.json、seven-minute-timeline.json | 420秒连续自动化验收，含讲述预留、真实启动/HTTP/浏览器/场景切换/重启预测逐值相等；不是人工现场演讲或性能测试 |
| prediction-public.json | 排练中真实HTTP返回的合成预测、七点及误差；不含凭据，不是Mock或真实预测准确率证明 |
| environment-final.json、failures-and-limits.json | 实际运行时版本、原T2实例保持健康、测试副本已停止；未验收范围明确列出 |
| files.json | 其他归档文件的逐字节SHA256，不包含清单自身 |
| t3-1-verification.json | T3.1启动时Git完整SHA、工作区、37份旧证据复核及BLOCKED裁定；列出未执行项和最小环境配合要求 |
| t3-1-environment.json | 本轮Windows版本、命令/可执行路径/常见客机路径、产品注册表、服务、客机进程、磁盘及已有VC++探测；明确搜索范围，不冒称穷尽所有机器 |
| t3-1-zip-inspection.json | 原候选包本轮CRC、清单覆盖及逐文件复验；SHA未变。未解密现有安装秘密，本轮privateCredentialValuesChecked=0，不覆盖T3历史的8值排除结果 |

精选截图由本轮运行的production页面取得：prediction-1440/390、warehouse-1440/390及reader。截图不替代HTTP或功能证据；没有密码、Cookie、CSRF token、DPAPI、数据库dump、SQL临时口令日志或上传原件。

完整本机日志保留在 `backend/target/t3-evidence`、`t3-package-final`、`t3-download-faults`、`t3-startup-faults`、`t3-seven-minute`；原包/最终包中断现场保留在各自安装目录。私有MySQL日志位于每安装ASCII本地存储，不能把它当公开证据整份复制（初始化日志可能含临时口令）。

本目录文字证据统一为UTF-8/LF，与仓库换行策略一致；仅规范化归档副本的编码/换行，原始本机文件不改写。files.json绑定本目录归档字节，避免Git换行转换导致跨环境哈希失效。

全部业务结果仍为synthetic_test合成发布快照，真实来源BLOCKED、真实准确率及跨城市评估NOT_EVALUABLE；没有Windows现场Hive集群或浏览器训练，研究导入不自动产生正式发布。完整结论见[T3报告](../../T3.md)。
