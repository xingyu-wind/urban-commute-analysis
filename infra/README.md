# 基础设施模块

当前采用回环单机候选部署，入口 `python scripts/s9_runtime.py --check`，启动 `python scripts/s9_runtime.py --output <新的忽略日志目录>`。依赖、私有配置、顺序、停止、恢复与故障定位见 [S9安装部署手册](../docs/guides/s9-deployment.md)。

配置参考根目录 `.env.example`，不自动加载；真实密钥、卷、dump、运行状态不入库。未引入 Compose 或系统服务；HDFS/Hive 沿用已有锁定镜像隔离 CI，不允许在本机格式化或接管未知集群。
