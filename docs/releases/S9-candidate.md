# S9 候选发布说明

候选名建议：`v0.9.0-rc.1`。仅建议，未创建Tag、未发布GitHub Release、未公网部署。状态 SUBMITTED_FOR_INDEPENDENT_REVIEW / SOLO_OWNER_REVIEW；最终精确HEAD及Run/Job回执随正式PR正文保存，避免在报告内递归固化自身提交SHA。

安全：所有Controller按精确路径/HTTP方法授权，八个公开只读路径与auth入口显式公开；ADMIN/READER、CSRF、会话和审计保留，默认denyAll。旧未知404与只读错误方法405/Allow由安全层直接生成。新增Controller默认无法执行。

部署：生产Vue dist通过回环preview同源代理到Java，规范脚本支持依赖预检、健康等待、日志和所持子进程回收；MySQL/HDFS服务不由脚本接管。既有HDFS/Hive隔离CI不减配。新增独立空库逻辑备份恢复、全表行数/哈希/指针和API结果比对、适度HTTP与主要页面实测。

兼容：无新增数据库迁移，V1–V6不变；现有S5/S6/S7完整性、时间语义与发布指针不变。auth/operations错误方法现在被明确拒绝401/403；未注册路径404。没有新增训练/发布Web API或速度→拥堵指数转换。详见[权限表](../guides/s9-security.md)。

数据：全部验收演示为合成数据；METR-LA/PEMS-BAY本地片段校验仍失败，深圳没有核实历史资源，PeMS缺用户授权账号/导出。真实单集回测、跨时间、跨域均NOT_EVALUABLE。阻塞证据和解除条件在[来源台账](../../ml/DATA_SOURCES.md)。

上线限制：当前为受控单机演示，没有公网限速/TLS代理、多节点会话、正式业务库ETL准入、自动调度/容量保留、完整系统备份或大规模SLA证明。性能测量仅代表本轮小合成库和温缓存。发布/合并须等待总规划师独立裁定；真实数据交付门槛未通过，不能将候选名解释为完整真实数据交付。
