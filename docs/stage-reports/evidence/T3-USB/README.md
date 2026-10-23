# T3-USB 离线答辩专项证据

**USB_CANDIDATE_LOCAL_PASS**：最终ZIP在同机全新运输/本地目录的离线执行路径及核心答辩功能通过。未物理断网、未测试真实U盘设备/异机/干净Windows/Win10或缺VC++。T3.1 BLOCKED历史不改写，也不作为当前USB交付前置。

候选477文件、1021842976字节，SHA256 `e473a2d912b72be98171a55aa55f882139b5dfac0bbc4f99299f78f8b1377e19`；业务基线97f30db，打包提交 `5f846e0964ff2ea8c08fb46eee53313d4290c79d`。原T3 ZIP的SHA256仍为 `9acbe39f35bf69dcf4bfcb35ac63a38ac0feeffeedea34afc455352f5c450f2f`。

| 证据 | 内容 |
|---|---|
| identity.json | Git、业务/JAR/前端与原T3逐字节一致、最终与原ZIP身份、来源锁、运行组件/源码数量与字节数 |
| zip-inspection.json | 全477文件路径与SHA256、CRC/MANIFEST全覆盖、58运行组件/88源码锁验证、4个本次随机秘密排除匹配0 |
| acceptance.json | 最终ZIP新解压→本地部署→真实离线首次配置→重复部署保留凭据→缺件/错哈希拒绝→非回环阻断与最终STOP；总304.58秒，非420秒演讲重跑 |
| core-acceptance.json | 新USB运行路径31次真实HTTP、两角色、CSRF/权限、Python研究导入、V1–V6、重复启动/端口冲突、会话失效、恢复、数仓查询 |
| browser-model.json、browser-management.json、browser-warehouse.json | 当前包真实production Chromium，1440/390，ADMIN上传/明确确认/成功研究导入及READER只读；无请求拦截 |
| first-offline-deployment.txt、repeat-owned-deployment.txt | 58项Verified offline component、依赖导入、首次初始化及本地URL；重复部署不覆盖本机状态 |
| offline-missing-component.txt、offline-wrong-hash.txt | 暂移Python归档/破坏运输副本JAR的真实拒绝；恢复原文件，不修改ZIP、不下载或初始化 |
| offline-process-guard.txt | 本包Python监管器在外部DNS/非回环IP测试中实际拒绝；不是整个Windows的断网/抓包证明 |
| source-validation-first.txt、source-validation-final.txt、source-transfer-recovery.txt | MySQL源码135816593字节截断的真实失败、专属传输恢复、最终479170675字节完整tar与二进制源提交对照 |
| source-acquisition-first.txt、source-acquisition-final.txt | 维护者来源收集记录；运行电脑不执行此联网脚本，不把它当离线现场下载 |
| sources.lock.json、components.json | 88源码/元数据与58官方运行组件的固定文件/版本来源、大小与SHA；完整原组件锁/许可也在候选ZIP |
| vc-prerequisite.json | 本人为用户从微软直接取得的独立离线安装器、固定解析URL、14.51.36247.0/18731856字节/SHA及Valid微软签名；未纳入通用ZIP，未在主机安装 |
| environment.json | 实际OS、非管理员、VC++现状、全新部署已停止、所属端口释放；物理网络/异机等明确未验证 |
| delivery-files.json | 可直接复制到U盘的dist/t3-usb-delivery全部文件哈希；包含相同候选ZIP、独立前提安装器、速查及已选历史Hive/演示证据 |
| files.json | 本目录文字证据UTF-8/LF的归档哈希，不包含清单自身 |

完整本机失败与测试日志保留在backend/target/t3-usb-evidence和t3-usb-acceptance；截断源码和分段取得记录在dist/t3-usb-sources，未塞进候选包。没有保存DPAPI、SQL临时口令日志、真实密码、Cookie/token、上传原件或私人数据库。

现场备用目录中S9-warehouse-ci是0be0d11实现基线的真实历史Hive证据，T3-remote-baseline记录97f30db的历史最终CI；它们不代表本次Windows现场重跑Hive，也不代表未推送USB提交的远端CI。T3七分钟排练为历史引用，本轮只重验新增离线路径及受影响核心流程。

全部演示为synthetic_test；真实数据BLOCKED、真实准确率及普遍跨城市泛化NOT_EVALUABLE。源码/许可提供条件与VC++分发边界详见[T3-USB报告](../../T3-USB.md)，现场使用[USB指南](../../../guides/windows-usb.md)。不授予商业或任意第三方再分发权，不修改第三方许可证本身的授权。
