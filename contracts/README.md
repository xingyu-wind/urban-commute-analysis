# 共享契约模块

负责跨模块 API、字段、时间、空值和来源约定。S2-WP2 已建立 [OpenAPI 契约](openapi.yaml)，只定义 `GET /health` 与 `GET /api/v1/cities`。WP2 只交付静态契约；WP3 后端实现和真实 HTTP 验收见 [后端说明](../backend/README.md)及 [S2 报告](../docs/stage-reports/S2.md)。静态验证不能代替真实 HTTP 验证，其他模块及真实数据接口仍属后续规划。

## 响应语义

| 场景 | HTTP 状态 | JSON 结构 / code |
|---|---|---|
| 健康 | 200 | `{status: "UP", timestamp: "…Z"}`；不使用业务封套 |
| 城市列表（含空列表） | 200 | `{code: "OK", message, data: City[], meta}` |
| 请求不合法 | 400 | `BAD_REQUEST` |
| 路径未映射 | 404 | `NOT_FOUND`，不用于表示列表为空 |
| 方法不支持 | 405 | `METHOD_NOT_ALLOWED`；响应须包含 `Allow` |
| 不接受 JSON | 406 | `NOT_ACCEPTABLE` |
| 内部错误 | 500 | `INTERNAL_ERROR` |
| 服务暂不可用（含健康失败） | 503 | `SERVICE_UNAVAILABLE` |

错误统一为 `{code, message, data: null, meta}`，`meta` 必须包含 `requestId` 以及显式为 `null` 的 `dataAsOf/sourceType/datasetId`。错误不发布业务数据。两条操作列出的 404/405 等表示共同错误处理约定；未映射路径及非 GET 请求由路由/框架处理，并非额外定义了业务接口。当前无鉴权、限流实现，因此不提前声明 401/403/429 策略已实现。

- HTTP 状态码表达协议结果；字符串 `code` 是机器可读业务结果。不得把失败包装成 HTTP 200，也不得把 JSON `code` 写成数字 200/500。
- `message` 供人阅读，客户端只按 HTTP 状态和 `code` 分支；错误消息不含堆栈、内部路径或凭据。
- 城市 `id` 为稳定的小写字符串，`name` 是非空白显示名。固定种子 `dev-city-001` / `dev-city-002` 只是开发样例，不代表真实交通记录。
- 成功 `meta` 必须为 `sourceType: "dev_seed"`、`datasetId: "dev-seed-cities-v1"`、`dataAsOf: null`，包括空数组情形。不能用请求时间替代真实采集截至时间。
- 每次请求生成 UUID `requestId`，用于日志关联，不是访问凭据。样例中固定 UUID 仅用于契约验证。
- `timestamp` 使用带 `Z` 或 `±HH:MM` 偏移的 RFC 3339 / ISO 8601，包含秒，可含小数秒，推荐 UTC。健康时间由服务处理请求时生成。固定样例时间只演示格式，非实时采集。
- `required` 字段全部必须出现；`null` 与缺失不同。所有对象禁止未声明字段。成功的 `data=[]` 是无城市；`data=null` 只用于错误。空列表仍返回 HTTP 200，不能改为 204/404。
- `/health` 是 `/api/v1` 版本前缀和业务封套的明确例外。两个 GET 均不定义请求体、分页或筛选参数。

## 可复现的静态验证

使用 Python 3.11，以项目隔离环境安装依赖，不需要激活脚本或修改 PowerShell 执行策略。在仓库根目录运行：

```powershell
python -m venv contracts\.venv
.\contracts\.venv\Scripts\python.exe -m pip install --cache-dir 'D:\WindXingyu\Temp\urban-commute-S2-WP2\pip-cache' -r contracts\requirements.lock.txt
.\contracts\.venv\Scripts\python.exe -m pip check
.\contracts\.venv\Scripts\python.exe -m openapi_spec_validator contracts\openapi.yaml
.\contracts\.venv\Scripts\python.exe contracts\validate_contract.py
```

创建虚拟环境命令用于首次安装；已有环境时直接使用，不覆盖未知环境。`requirements.in` 固定直接依赖，`requirements.lock.txt` 固定实际解析的全部依赖版本。

验证脚本使用 `openapi-spec-validator` 验证文档结构，再用 `jsonschema` Draft 2020-12、`referencing` 和启用格式校验的 `FormatChecker` 校验操作的实际响应 Schema；不是重新手写另一份 Schema。脚本检查 YAML/JSON 重复键，明确启用日期时间及 UUID 校验，并按 `cases.json` 加载独立 JSON 正反例。它还逐一验证 OpenAPI 的外部响应示例，避免文档示例与测试文件漂移。

完整套件退出 0 表示全部预期成立，包括反例被拒绝。独立验证一份响应时，无效响应退出 1：

```powershell
.\contracts\.venv\Scripts\python.exe contracts\validate_contract.py --instance contracts\examples\cities-success.json
# 预期退出 0
.\contracts\.venv\Scripts\python.exe contracts\validate_contract.py --instance contracts\examples\invalid\city-id-number.json
# 预期退出 1；type@/data/0/id
```

`--path /health --status 503` 等选项指定要验证的实际操作响应。脚本可从其他工作目录运行；`--instance` 文件路径按调用者工作目录解释。该过程不发 HTTP 请求，不证明 Controller、CORS、路由、状态码或响应头已正确实现。

## 后续实现约束

- Java：为健康响应使用独立 DTO；城市与错误使用明确的封套 DTO。城市 ID 使用 `String`。时间使用 `OffsetDateTime` / `Instant`，输出必须带时区。
- Jackson：即使项目全局使用 `NON_NULL`，本契约要求的 `null` 字段也必须序列化，不能省略错误 `data` 或 meta 字段。
- Controller / 错误处理：保留 HTTP 与业务 code 映射；在后续工作包验证框架层 404/405/406 的统一 JSON 错误及 405 `Allow` 响应头。健康 503 使用统一错误封套。
- Vue API 客户端：单独处理健康结构，城市 `data` 是数组；错误 `data` 是 null。不得根据 message 判断业务结果，不得把缺失字段自动补成成功或把 dev_seed 标成实时数据。
- UI：开发样例标识必须可见；`dataAsOf=null` 应显示“开发样例，无采集时间”等语义，不用当前时间填补。
- 后续新增真实数据源或字段必须先修改契约、更新正反例并评审兼容性，不能静默复用 `dev_seed` 数据集标识。

本次验收证据见 [S2 阶段报告](../docs/stage-reports/S2.md)。跨模块契约变更仍须协商与审查；`S1-COLLAB-DEBT` 未关闭。

规范依据：[OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0.html)、[openapi-spec-validator](https://python-openapi.org/openapi-spec-validator/)、[jsonschema 格式校验](https://python-jsonschema.readthedocs.io/en/stable/validate/)。
