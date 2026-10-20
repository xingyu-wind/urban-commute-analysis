# 共享契约模块

S6 OpenAPI 3.1 定义七条 GET：`/health`、`/api/v1/cities` 、`/api/v1/traffic/{summary,series,regions,roads}` 和 `/api/v1/warehouse/metrics`。正式约定在 [openapi.yaml](openapi.yaml)，统计参数与口径见 [S4 指南](../docs/guides/s4-dashboard.md)。

## 响应语义

- `/health` 返回 `{status,timestamp}`，是进程存活检查，不证明数据库可用。
- 业务成功使用 `{code:"OK",message,data,meta}`。城市 data 为列表，统计 data 为窗口及指标/列表。城市目录 meta.dataAsOf 永远 null。
- 交通指标 N 是样本行数，速度 km/h、指数0–10，算术平均；N=0 时两项指标和截至时间必须为 null。CITY、REGION、ROAD 严格隔离；时间统一 UTC `[from,to)`。
- 交通 meta 描述单一查询数据集及来源，默认使用城市登记数据集。禁止 forecast/mock/simulation 混入历史统计；sourceType 登记不表示外部授权已核实。
- 空城市目录使用 database_catalog/null，混合目录 mixed_catalog/null；其他城市目录源与 datasetId 关联。不得沿用 S2 内存种子固定元数据规则。
- 错误使用真实 HTTP 400/404/405/406/500/503，对应 BAD_REQUEST/NOT_FOUND/METHOD_NOT_ALLOWED/NOT_ACCEPTABLE/INTERNAL_ERROR/SERVICE_UNAVAILABLE，data 与来源/截至时间均为 null；requestId 始终为 UUID，与响应头、日志关联。
- 每个 required 字段必须出现，null 不等于缺失；所有对象拒绝未声明字段。

## 可复现校验

在项目隔离 Python 环境安装 `requirements.lock.txt`，无需全局安装或修改执行策略：

```powershell
python -m venv contracts/.venv
contracts/.venv/Scripts/python.exe -m pip install -r contracts/requirements.lock.txt
contracts/.venv/Scripts/python.exe -m openapi_spec_validator contracts/openapi.yaml
contracts/.venv/Scripts/python.exe contracts/validate_contract.py
contracts/.venv/Scripts/python.exe contracts/validate_contract.py --instance contracts/examples/traffic-summary.json --path /api/v1/traffic/summary
```

`validate_contract.py` 仍严格校验完整七路径白名单、GET、全部错误状态、重复 YAML/JSON 键、格式、正反案例及全部外部示例。S4 扩展了原先 S2 两路径限制，没有绕过检查。

`cases.json` 包含21条正例和13条反例；其中 S4 覆盖四个接口、空指标、负样本数、指数越界和非法坐标。静态样例不是实时采集。真实 Java 响应由 `scripts/s4_validate_captures.py` 再按同一 OpenAPI Schema 校验，集成结果见 [S4 报告](../docs/stage-reports/S4.md)。Vue 类型及运行时验证器位于 `frontend/src/types/traffic.ts` 和 `frontend/src/api/traffic.ts`。

S6 离线接口默认返回最新已发布快照的 WINDOW 指标，也支持 DAY/HOUR。发布为空时 release=null、items=[]；版本、UTC 窗口、来源、批次、源 SHA 及规范化 ADS 内容 SHA 随结果返回。后端只读 current JOIN PUBLISHED，均值按总和/有效样本数 HALF_UP 到两位，不混合目标层级或数据版本。真实 HTTP 响应/粒度与 Chromium 验证由 `frontend/scripts/verify-s6.mjs` 执行；其实际响应逐份通过同一 OpenAPI 校验。类型与运行时校验位于 `frontend/src/types/warehouse.ts`、`frontend/src/api/warehouse.ts`。
