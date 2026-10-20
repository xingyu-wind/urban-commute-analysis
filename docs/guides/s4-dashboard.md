# S4 运行、统计口径与演示

## 启动应用

沿用 [S3 MySQL 准备与凭据规则](s3-mysql.md)。需要 Java 21、MySQL 8.4、Node 24、项目 Python 契约环境。只给已授权的库设置 `DB_URL`、`DB_USER`、`DB_PASSWORD`；Java 不自动读取 `.env`。保留 V1/V2 checksum，没有新增迁移，没有自动装载样本。

```powershell
.\backend\mvnw.cmd -f backend/pom.xml -B -ntp package -DskipTests
java -jar backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar
# 另一终端
cd frontend
npm.cmd ci --no-audit --no-fund
npm.cmd run dev
```

访问 `http://127.0.0.1:5173`，选城市后进入分析区。开始日期为 UTC 当日零点，结束日期为不包含的 UTC 当日零点。界面自动刷新筛选结果；“刷新分析”重新查询数据库。“比赛大屏”在浏览器内部占满视口，退出按钮返回。图表和点位都支持鼠标，区域也提供可用键盘操作的等价按钮；趋势可展开数据表。

普通开发库可以为空，不能为了画面效果自动填入假统计。合成演示必须使用专门隔离库，不能导入未知或正式库。

## 四个接口

公共必填参数：`cityId`、`from`、`to`。时间必须带秒及 `Z` 或偏移，最多毫秒精度，归一化为 UTC，年份 2000–2099；`from < to`。区间 `[from,to)`，最长 366 天。显式偏移中的加号在 URL 里写 `%2B`。

`datasetId` 可选，默认城市登记的数据集；一次仅查一个数据集，不能把不同来源混平均。允许 `dev_seed`、`synthetic_test`、`historical_snapshot`、`authorized_live`；拒绝 `forecast`、`mock`、`simulation`。来源标签仅表示数据库登记，不证明外部授权已经核实。城市目录的部署筛选对交通接口同样有效。

| API | 层级 | 附加参数及行为 |
|---|---|---|
| `/api/v1/traffic/summary` | CITY | 整个窗口的样本均值 |
| `/api/v1/traffic/series` | CITY | `granularity=day` 默认；`hour` 最长 31 天，UTC 整点/整日分桶，首尾桶只统计窗口内观测 |
| `/api/v1/traffic/regions` | REGION | 返回城市登记区域及各自观测、WGS84 坐标，可无观测 |
| `/api/v1/traffic/roads` | ROAD | `regionId` 同城校验；`search` 最多 100 字，字面子串；`page` 1–10000，`pageSize` 1–100，默认 1/10 |

道路按拥堵指数降序、ID 升序稳定排序，未观测道路排后。`total` 是匹配登记道路数，不是样本数；越界页可为空。`%`、`_`、引号不成为 SQL 通配符或语句。所有接口拒绝未知参数、重复参数、GET 请求体、非法城市/数据集/区域；保留 S2 错误封套及请求 ID。

```text
/api/v1/traffic/summary?cityId=s4-demo-city&from=2026-10-15T00:00:00Z&to=2026-10-17T00:00:00Z
```

`metrics.sampleCount` 是观测行数。`avgSpeedKmh` 为速度算术平均（km/h），`congestionIndex` 为 0–10 指数算术平均；没有车辆数加权，也不是通勤人数。服务保留 MySQL AVG 精度，页面显示两位小数。CITY、REGION、ROAD 严格隔离。

无观测：N=0，两项指标与 `dataAsOf` 都是 null。趋势空桶保留 null，不补零或跨空桶连线。`meta.dataAsOf` 是该接口完整筛选范围的 MAX observed_at，道路分页仍覆盖所有匹配道路。区域和路段行也带各自截至时间。每个响应使用一个 MySQL repeatable-read 快照；四个独立 HTTP 请求不承诺跨响应事务快照。

## 隔离自动化与合成演示

在已授权的本地专用 MySQL 8.4 实例设置 `S3_ADMIN_PASSWORD`、`S3_ADMIN_USER`（默认 root）、`S3_MYSQL_PORT`（默认 33067）、`MYSQL_CLIENT`（mysql 可执行文件）。不要把凭据写入命令参数或 Git。准备器建立新随机库和单库账号，不 DROP、不复用旧库。

```powershell
.\contracts\.venv\Scripts\python.exe scripts/s3_database.py --output backend/target/s4-run-01.json -- contracts/.venv/Scripts/python.exe scripts/s4_checks.py --with-core --output backend/target/s4-run-01
```

每次使用新的证据路径。该入口运行 S2/S3 完整回归、新增 Java 测试、契约、Vue 测试与构建，然后装载 S4 fixture、独立 SQL 对账、真实 Chromium 和实际响应 Schema 校验。浏览器使用本机 Chrome/Edge 或已配置的 Playwright Chromium；不自动安装系统软件。CI 使用临时 runner 的 Chromium 和 mysql:8.4。

合成样本导入脚本为 `scripts/s4_database.py fixture`，只允许准备器产生的随机隔离库及账号；存在同名数据时直接失败。独立预期 SQL 为 `database/fixtures/s4-expected.sql`：CITY N=3、36 km/h、指数5；东区25/6、西区50/2；道路A15/8、B40/3。浏览器回归实际把唯一 CITY 速度42改成60，页面均值应为42，再恢复为36，并重新核对 SQL。修改仅针对这一条受控样本。

自动驱动完成后关闭自己持有的 Java/Vite 子进程，保留隔离库和诊断。手动演示可在构建 JAR、npm ci 后使用同一准备器建立另一个新库：

```powershell
.\contracts\.venv\Scripts\python.exe scripts/s3_database.py --output backend/target/s4-demo-01.json -- contracts/.venv/Scripts/python.exe scripts/s4_demo.py
```

该入口在迁移前核对真实库/账号/服务器和空库状态，迁移后装载样本并对账，再启动本地前端。端口占用时会退出，可通过 `--java-port 8081 --vite-port 5174` 选择其他回环端口；不停止占用者。Ctrl+C 只关闭自己启动的 Java/Vite，库保留。选择“S4合成演示城市”并点击“合成样本时段”（10月15日至17日）。这个按钮只设时间筛选，不提供指标。不要尝试从公开报告恢复随机口令。

## 地图、许可与实现边界

地图是离线经纬度点位视图，使用数据库成对完整、范围合法且明确为 WGS84 的区域中心点；图表轴标明经纬度。允许缩放、点选以及等价按钮操作，选择联动道路区域筛选。没有行政边界或街道底图，不能用于导航或距离测量。缺坐标区域省略并明确计数，路段无几何就不画道路。

合成东区点位只是渲染测试，不能宣称是真实采集位置；西区故意无坐标。无在线地图服务、商业密钥、地图账号、外部瓦片或地理数据下载。Apache ECharts 固定为 6.1.0，按 [Apache ECharts LICENSE](https://github.com/apache/echarts/blob/master/LICENSE) 保留 Apache-2.0 许可，依赖锁定于 package-lock.json；图表接口依据 [官方文档](https://echarts.apache.org/en/api.html)。无 ETL、Hive 或模型训练功能。
