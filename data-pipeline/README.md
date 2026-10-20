# S5 Python 数据准入与 ETL

Python3.11、小型离线批次（原始文件≤100MiB，整体驻内存）。无需 Pandas 或 Hive。复用 Java Flyway V1/V2，新增 V3；Python 不自行迁移。仅接受 synthetic_test/not_applicable，或人工核验并填写依据的 historical_snapshot、authorized_live/authorized。候选见 [sources.json](sources.json)，来源登记不构成外部授权证明，当前实测全部是合成测试。

在仓库根安装及生成样例：

```powershell
contracts/.venv/Scripts/python.exe -m pip install -r data-pipeline/requirements.lock.txt
contracts/.venv/Scripts/python.exe data-pipeline/examples/generate.py
```

进入 data-pipeline，无需数据库即可清洗：

```powershell
../contracts/.venv/Scripts/python.exe -m commute_etl --config examples/csv-config.json --input examples/traffic.csv --batch demo-csv --output ../outputs/s5-csv
../contracts/.venv/Scripts/python.exe -m commute_etl --config examples/json-config.json --input examples/traffic.json --batch demo-json --output ../outputs/s5-json
```

output 必须是新目录；重试同一 batch ID 也选新报告目录，避免覆盖证据。配置决定格式、字段映射、源单位、版本、来源和空间目录。带偏移时间统一 UTC，无偏移默认拒绝，仅明确 naive_timezone=UTC 时例外，不猜测当地 DST 时间。速度只支持 km/h、m/s、mph；拥堵只接受同语义的0–10或0–100，不把通行时间比转成拥堵。字段见 [字典](DATA_DICTIONARY.md)。

加 `--load` 入库。凭据仅从 S3 准备器的 TEST_DB_* 私有子进程环境读取；当前 CLI 仅支持 S3 随机新隔离库/单库账号，校验真实数据库、账号、服务器 UUID 和 MySQL8.4，绝不回退到 DB_URL、管理员或持久库。普通库部署不是本阶段入口。

完整验证在仓库根、已授权实例环境运行；S3_ADMIN_PASSWORD 和 MYSQL_CLIENT 配置沿用 [S3指南](../docs/guides/s3-mysql.md)，不要将密码写进命令或配置：

```powershell
contracts/.venv/Scripts/python.exe scripts/s3_database.py --output backend/target/s5-db-new.json -- contracts/.venv/Scripts/python.exe scripts/s5_checks.py --output backend/target/s5-new
```

入口执行 Flyway、Java82项测试、pytest（真 MySQL）、Python CLI、Java/Vite/Chromium和实际响应契约。原 `scripts/s4_checks.py --with-core` 保留 S2–S4 全量回归。Linux CI 同样另建 S5 隔离库。无 DROP/TRUNCATE/repair，测试库不自动删除。

事务和恢复：

1. 获取 dataset_id 命名锁，校验或注册来源及空间目录；提交 RUNNING 和清洗拒绝记录。
2. 单事务写观测及逐条血缘。同值记 EXISTING，任一异值记录具体键及差异字段，整批观测回滚为 FAILED，不使用 INSERT IGNORE 或覆盖式 upsert。
3. 观测、血缘与 SUCCEEDED 原子提交。异常回滚，FAILED 的 written/existing 为0。进程硬退出由 MySQL 回滚，保留 RUNNING；后续进程取得同一锁后才可增加 attempts、重放，避免把仍运行的进程当作失联。
4. 同一 batch ID 绑定原文件和完整配置/解析版本哈希，改文件或映射必须用新 ID。同文件新批次全部按 EXISTING 去重。成功批次重试返回原计数和 reused=true，不表示再次写入。提交成功但客户端丢失响应也可安全重试。

对账：input=accepted+rejected+duplicate；成功时 accepted=written+existing=该批血缘行数，rejected=etl_rejection行数；失败批没有已提交血缘。标准化文件只证明清洗结果，必须联看数据库批次状态。保留 attempts，但尚无逐次尝试事件历史或自动调度。
