# S9 路由权限与响应兼容

盘点对象：ApiController、TrafficController、WarehouseController、PredictionController、AuthController、OperationsController，以及 Security 的登录/退出过滤器。无 Swagger UI、Actuator 或独立文档 HTTP 路由；OpenAPI 作为仓库文件维护，不凭空开放文档、error 或管理通配符。

| 方法 | 精确路径 | 权限 |
|---|---|---|
| GET / HEAD | `/health` | 公开健康探针，不表示数据库/预测健康 |
| GET / HEAD | `/api/v1/cities` | 公开目录 |
| GET / HEAD | `/api/v1/traffic/summary`、`series`、`regions`、`roads` | 公开只读，仍保留参数、窗口及粒度校验 |
| GET / HEAD | `/api/v1/warehouse/metrics` | 公开已发布 ADS |
| GET / HEAD | `/api/v1/predictions` | 公开已发布 CITY 日拥堵指数 |
| GET | `/api/v1/auth/csrf` | 公开当前会话 token |
| POST | `/api/v1/auth/login` | 公开认证入口，CSRF |
| GET | `/api/v1/auth/me` | 已登录 |
| POST | `/api/v1/auth/logout` | 会话退出、CSRF |
| GET | `/api/v1/operations/tasks` | ADMIN / READER |
| POST | `/api/v1/operations/uploads` | ADMIN + CSRF |
| POST | `/api/v1/operations/imports/{id}/confirm`、`execute`、`retry` | ADMIN + CSRF，服务层仍校验 UUID、确认、许可、状态和次数 |
| 其他 | 所有未列入的方法/路径 | denyAll，不调用 Controller |

`/traffic/**`、`/warehouse/**`、`/operations/**` 不再作为授权规则。新 Controller 即使位于旧公开前缀，也须显式加入清单并补权限测试，不能继承匿名访问。

兼容策略：公开业务 GET 保持原200/400/406/503等语义；HEAD 明确支持。对八个公开只读路径使用写方法，安全层直接返回统一405与 `Allow: GET, HEAD`，不将请求放进 MVC。未知路径安全层直接404、NOT_FOUND、requestId，不转发、不执行未来 Controller；保留原未知404外观，同时由允许请求改为拒绝请求。已知管理路径匿名401、已登录越权403；畸形 UUID 继续由服务层400，不存在的合法 UUID404。auth/operations 的非安全方法保持 CSRF；未知路径即使提交有效 token 仍拒绝。严格防火墙对编码分隔符、分号、双斜线等还可更早400，不放宽它来制造404。

拒绝可以写必要审计，但不得写业务观测、导入/任务元数据、私有文件或 current 指针。真实 HTTP 三身份矩阵及 MySQL/文件系统前后断言在 `scripts/s8_checks.py`；`DefaultDenialIntegrationTest` 实际注册未来写 Controller，以嵌入式服务器验证18次请求均404、方法调用计数0。原404/405测试保留原预期，未更新断言掩盖契约破坏。

保留 BCrypt12、登录更换会话、20分钟空闲、HttpOnly/SameSite Strict、CSRF、审计失败撤销登录和退出失效保证。仍无公网限速、多节点会话或即时撤销既存会话的账户管理功能；候选回环演示不构成公网就绪声明。
