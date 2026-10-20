# S7 V3.2 数据来源核查与字段契约

核查日期：2026-10-20。用户明确决定“先完成适配与质量核查，真实评估暂不放行”。以下为实际访问结果，不是数据使用授权。原始文件、含样例的检查报告仅在被 Git 忽略的 `data/raw/s7-v32-research/`；不上传 Git、LFS、CI 或 PR。仓库证据只有聚合计数、版本、校验和与许可核查状态。

## 优先来源：Zenodo / DCRNN

选定 [Zenodo 5724362 v6](https://zenodo.org/records/5724362)，DOI `10.5281/zenodo.5724362`，标题 PEMS-BAY and METR-LA in csv，提交者 Semin Kwak。实际读取[元数据 API](https://zenodo.org/api/records/5724362)：4433 字节，SHA256 `cd3da13e463b3bbf1b479210e23333db144e8b67114646d6161ed44fd4e1bbfe`；metadata.license.id 声明 `cc-by-4.0`，access_right=open。该声明只证明存储库提交者的标记，尚未独立确认上游数据再分发/派生使用依据。

[DCRNN 原始项目](https://github.com/liyaguang/DCRNN)的 README 指向 HDF5 数据与下载渠道；[MIT LICENSE](https://github.com/liyaguang/DCRNN/blob/master/LICENSE)是代码许可证，不能推定数据也适用 MIT。本次只适配实际查看的 v6 CSV，未加载外部 pickle/joblib/HDF5，不承诺兼容其他分发版本。

| 文件 | 元数据声明完整字节 / MD5 | 本次实际收到字节 / SHA256 |
|---|---|---|
| METR-LA.csv | 72467662 / `7c463fcbd28ecc6c9cd93e1ca120aaaa` | 2930156 / `71e310d27b32344a1f04f7373b57bed9c6a4ca567ce66520f97c15831112957d` |
| PEMS-BAY.csv | 85718439 / `c8dea58987a5882e946217c22fdb8256` | 2604200 / `1fe1d5893c4922d164e3bf5831ebf6f0e85c51f11a506024e346e87c073c3d97` |

访问方式为公开 HTTPS API 文件 content 链接。传输返回了截断文件，预期 MD5 断言失败；另一次限定 Range 请求超时。片段的实际 MD5、末端残行、缺失/零值计数见证据 `sources/*-quality.json`。未覆盖或删除片段，未把传输失败改写为完整下载。

实际首列为空名日期索引，后续分别为207/325个数字传感器列；相邻已收到时间行间隔300秒。METR片段1364行、2012-03-01至03-05，BAY片段1582行、2017-01-01至01-06，各末行宽度不全。这些只是收到的前缀，**不代表完整数据覆盖**。时间文本不带时区，CSV头未标单位；常见研究版本的 mph 和时区描述不能当作当前版本已确认事实。单位、时区、零值含义、历史覆盖、上游权利均待确认。

适用性：**NOT_EVALUABLE**。未生成真实可执行映射，未开展真实训练/跨域评估，也没有把传感器速度转成0–10拥堵指数。后续最少条件：核验完整分发文件大小/MD5、补齐该版本单位/时区/零值政策及上游许可依据，再由用户明确确认映射与允许用途。之后仍须通过任务适用性检查。

## 深圳市政府数据开放平台

检查[平台](https://opendata.sz.gov.cn/)、[候选资源入口29200_00403590](https://opendata.sz.gov.cn/data/api/toApiDetails/29200_00403590)、[另一个被索引入口](https://opendata.sz.gov.cn/wap/data/dataSet/toDataDetails/29200_00403666)及[服务条款](https://opendata.sz.gov.cn/maintenance/forward/toTermOfService)。网页检索可见“路段速度数据”调用榜，但资源入口返回通用门户内容，本机直接请求详情/条款403；未取得可验证字段字典、资源版本、历史长度或交通观测文件。“交通运行状态”的检索未核验到可用的具体历史资源，不能凭门户榜单赋予资源ID含义。

网页可读条款涉及来源署名、资源转交限制及撤回后处理义务，不能视为任意再分发许可证；需针对具体资源复核最新条款与使用条件。状态 **BLOCKED / NOT_EVALUABLE**。下一步由用户提供获准的具体资源详情/字段与历史导出方式，核实授权后下载到受控本地目录。静态资源目录、接口调用量、一次快照均未作为预测训练序列。

## Caltrans PeMS

核查[官方说明](https://dot.ca.gov/programs/traffic-operations/mpr/pems-source)与[PeMS门户](https://pems.dot.ca.gov/)。官方说明历史数据访问需要申请账户并审批。本次未注册、登录、代用户接受条款或使用个人账号；未取得实际历史文件，因此无文件版本/哈希可报告。状态 **BLOCKED / NOT_EVALUABLE**。

已实现 `pems-user-export-csv-v1`，仅面向用户提供的**带头部导出**，要求显式映射、时间格式、单位、时区、采样周期与目标；使用原创合成样例测试速度/流量区分。未声称已核验官方无头5分钟原始格式。后续最少步骤：用户自行申请并确认条款；提供合法历史导出及该版本字段字典；本地检查完整性和语义；用户确认映射后再评估。

## 统一字段字典与适配边界

| 字段 | 约束 |
|---|---|
| dataset_id / dataset_version / domain_id / city_id | 数据集、版本与城市/路网域分别保留；不能用改名复制伪造迁移 |
| source_type / source_url / license_status / license_evidence / allowed_uses | synthetic_test 或真实快照；许可未核验不得执行真实转换/评估 |
| source_sha256 / mapping_sha256 / normalized_sha256 | 原文件、人工确认配置、规范序列分别计算内容哈希 |
| target / unit / original_unit | speed、flow、congestion_index分开；速度显式转km/h，流量保留每时段/每小时语义，指数限0–10 |
| timezone / frequency_seconds / spatial_grain | 明确IANA时区、300/3600/86400秒任务及CITY/REGION/ROAD/SENSOR粒度 |
| mapping_version / preprocessing_version | 当前均为1；不兼容版本拒绝，不静默迁移 |
| rows[].entity_id / timestamp / value | 实体、UTC毫秒Z时间、有限非负值或缺失；冲突重复拒绝，完全相同重复计数去重 |

通用CSV/平面JSON检查字段类型、空值、时间和有限样例，推荐仅为 PROPOSED。`confirm` 必须收到完整人工复核、actor和精确proposal SHA确认，才生成 CONFIRMED；不自动推断单位或日期时区。夏令时歧义/不存在时刻要求显式偏移，未确认的零值不擅自当缺失。

质量门槛与任务相关：5分钟速度预测未来12步，小时序列6步，日序列7步；周期分别为一天/一天/一周。完整候选评估需要7个训练周期+2个验证周期+2个测试周期；有限基线需要1个周期+4个预测窗口。有效覆盖至少90%、最长缺口不超过一个周期；还检查每步有评估标签，不能以补全标签放行。工程门槛不等于真实交通有效性保证。此策略独立于现有CITY日拥堵指数发布的365日/四时段契约，不降低其准入。

训练特征只用过去，缺失特征向前填充，训练/评分标签不插值；窗口内递归使用预测。只按验证误差选模，测试不调参。按域报告总体、每个步长及每个窗口误差；迁移冻结源域验证选择与源域拟合，目标历史只作滞后上下文。相同城市/数据文件、>=20%精确时间值重叠、不可比单位/目标/粒度及源训练晚于目标起点均拒绝。该重复筛查是保守防线，不是证明所有现实域完全独立。

新的通用速度/流量任务仅在**离线研究评估契约**中运行，报告 `evaluationOnly=true, apiPublication=false`。无共享DB迁移；不写S5观测、S6 warehouse_current或V5预测指针。现有Java/OpenAPI/Vue `/api/v1/predictions`继续只接纳CITY每日0–10拥堵指数；没有把新目标混入其模型或图表。

原创合成流程命令：`python scripts/s7_data_checks.py --output <不存在的输出目录>`。该命令无网络访问，只生成自己的CSV/JSON与明确合成fixture-owner确认，不能充当真实用户对外部映射的许可。实际CLI参数见 `python ml/data_cli.py --help`，先inspect，人工review/confirm，再convert、quality、evaluate、transfer。
