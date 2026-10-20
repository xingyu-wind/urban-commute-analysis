# S7 离线七日拥堵指数预测

目标是单城市、单数据集/版本、CITY 日均拥堵指数（0–10），不是车流量、通勤人数或个人 OD。当前可重复演示全部为 `synthetic_test`；合成回测误差不能作为真实交通预测准确率。

`scripts/s7_fixture.py` 固定 seed=20261020，生成 1092 日 / 156 完整周 / 接近三年季节变化的 4368 条观测。必须经过真实 S5 CLI 成功提交，再使用 S6 `snapshot()` 在 repeatable-read 中核验来源配置、原始文件 SHA、成功批次、数据登记版本及完整逐条血缘。没有以本地候选文件直接伪造已发布观测。S7 消费 S6 准入契约，不重复运行或宣称生成了新的 Hive ADS。

UTC `[from,cutoff)` 两端须为午夜；截止时点为第一个预测日期的 00:00。每日为样本算术均值，不做车辆加权。每天至少四条并覆盖 UTC 0–6、6–12、12–18、18–24 四个时段，允许时段内不规则采样；要求同日采集，晚到样本明确拒绝，确保历史回测起点当时已可用。缺日、覆盖不足、少于365日、版本不一致均拒绝，不补零、不插值。来源的采样策略与真实业务代表性仍需另行核验。

`forecast.py` 特征为 lag1/7/14/28、前7/28日均值、前7日标准差、星期/周末及已知年周期。每个训练样本的特征只使用目标日之前的数据；无全量预处理器。最后56日按时间切为28日验证及28日测试，各4个不重叠七日窗口。每个起点仅用已知历史重新拟合，再递归预测七日；窗口内滞后值来自自己的预测。下一个起点可以使用已经发生的前一窗口观测。最终选定模型在截止日前全部历史上重新拟合并预测。

固定候选：naive、seasonal7、60棵随机森林、80轮 XGBoost。只按验证 MAE、RMSE、固定候选顺序选择；ML 相对最佳基线 MAE 改善不足1%时回退基线。测试结果不参与选模或调参；没有宣称 ML 总能胜出。预测裁剪0–10，发布保留六位小数。`evaluation.json` 保存两种切分、所有模型、起点、七日预测/实际值、MAE/RMSE及逐步长误差。

项目隔离 Python3.11 环境安装：

```powershell
python -m venv ml/.venv
ml/.venv/Scripts/python -m pip install -r ml/requirements.lock.txt -r data-pipeline/requirements.lock.txt -r contracts/requirements.lock.txt
```

在已有**获授权的专用 MySQL8.4 回环实例**上，通过环境提供管理员密码与 `MYSQL_CLIENT`，使用现有隔离工具创建全新 schema 和单库账号：

```powershell
ml/.venv/Scripts/python scripts/s3_database.py --output backend/target/s7-new-db.json -- ml/.venv/Scripts/python scripts/s7_checks.py --output backend/target/s7-new
```

这会运行 Flyway/Java、Python及Vue测试、S5 ETL、两轮训练、发布故障/硬中断恢复、实际HTTP/OpenAPI与Chromium。输出目录必须不存在，不覆盖证据或清理旧库。现有私有实例密码不得复制到命令参数、Git或报告；不适用于任何既有业务库。Linux CI 使用 `python` 替换虚拟环境解释器，保留原S2–S6回归。

在隔离工具的子进程环境及完成迁移后，CLI 可独立运行：

```text
python ml/forecast.py train --batch-output <S5成功输出目录> --city s7-city --dataset s7-synthetic-v1 --from 2023-10-23T00:00:00.000Z --cutoff 2026-10-19T00:00:00.000Z --output <新训练目录>
python ml/forecast.py publish --batch-output <同一S5成功输出目录> --output <训练目录>
```

训练目录保存完整日序列与输入身份、源/批次与内容 SHA、依赖版本/代码 SHA/固定配置、切分与每个回测起点、真实训练/生成时间、最终 `model.joblib` 和工件 SHA。同环境同输入配置重复训练验证评估字节、模型工件及预测一致；不承诺跨操作系统/BLAS版本的权重字节一致。不提交大型权重；完整工件由CI artifact保留14日，精选证据随Git保存。CLI 不加载任意外部 pickle。

发布前重新核验全部S5来源/批次/版本/观测与训练输入，并验证工件 SHA、选模结果及七日连续性。V5 独立 model/job/evaluation/result/current 表，按城市/数据集命名锁串行发布；STAGING先持久化，全部明细、评估、PUBLISHED与指针同事务提交。失败回滚、FAILED保留；进程硬退出可留下STAGING，后继持锁者安全恢复。相同科学输出复用同一任务，不重复明细；旧成功重放不会倒退指针；过期或同生成时间的新任务拒绝覆盖。S6 `warehouse_current` 不变。

`GET /api/v1/predictions?cityId=...&datasetId=...` 只读当前PUBLISHED快照，无模型返回release=null与空数组。Java DTO、OpenAPI、TS运行时验证同步。Vue打开“七日预测”后显示历史实线/预测虚线、七点表、模型/来源/版本/时间/误差/限制；没有HTTP触发训练、Mock曲线或生产调度。
