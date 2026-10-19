# 前端模块

S3 前端：显示真实后端健康状态、选择 MySQL 城市目录、处理加载/空列表/失败与重试。没有交通统计、地图、登录、预测数值或默认 Mock。

## 依赖与命令

Node.js 24.19.0 LTS、npm 11.17.0；Vue 3.5.44、TypeScript 5.9.3、Vite 8.3.4、vue-tsc 3.3.13、Vitest 5.0.5。版本固定在 package.json 和 package-lock.json。TypeScript 7 的编译器导出与当前 vue-tsc 不兼容，因此使用经过本项目真实类型检查的稳定 5.9.3；没有修改全局 TypeScript。

在 `frontend` 目录执行：

```powershell
npm.cmd ci
npm.cmd run dev
```

默认访问 `http://127.0.0.1:5173`；需要另一个终端先启动 Java 后端，见 [backend/README.md](../backend/README.md)。脚本使用严格端口模式，端口占用时不自动结束任何其他程序。

| 脚本 | 用途 |
|---|---|
| `npm.cmd run dev` | Vite 开发服务，127.0.0.1:5173 |
| `npm.cmd run type-check` | vue-tsc 检查 Vue、TS、配置与测试类型 |
| `npm.cmd run build` | 先类型检查，再构建 dist |
| `npm.cmd test` | Vitest API/组件/代理配置测试 |
| `npm.cmd run test:watch` | 单元测试监听 |
| `npm.cmd run preview` | 本地查看静态构建，4173；不包含开发代理 |
| `npm.cmd run test:e2e` | 启动本项目 Java/Vite，执行真实浏览器验收与契约校验 |

## 调用关系与文件

```text
App.vue -> api/client.ts -> fetch('/health', '/api/v1/cities')
           -> Vite 开发代理 -> Spring Boot ApiController -> CityService
```

| 文件 | 职责 |
|---|---|
| `src/App.vue` | 页面、两接口独立结果、15 秒自动检查、重试与清除过期状态 |
| `src/components/CitySelector.vue` | 有标签的原生下拉选择，v-model 传回字符串城市 ID |
| `src/api/client.ts` | 同源 fetch、5 秒超时、HTTP/网络/格式错误，安全解析业务错误标识 |
| `src/types/api.ts` | 对照 OpenAPI 的健康、城市成功与错误类型 |
| `src/style.css` | 中文界面、桌面及窄屏布局、键盘焦点与减少动画支持 |
| `config/proxy.ts`、`vite.config.ts` | 集中配置 `/health` 和 `/api` 的开发代理；不改后端 CORS |
| `config/runtime.ts` | Windows/Linux Java、Python 入口和浏览器选择；支持 CI 进程配置 |
| `tests/` | 使用契约 JSON 样例的单元测试；测试替身不进入正常页面 |
| `scripts/verify-integration.mjs` | 无请求 Mock 的真实浏览器联调、停服/恢复/离线/空列表验收 |
| `scripts/validate-captures.py` | 使用 WP2 的实际 OpenAPI Schema 检查浏览器真实响应并关联 Java 日志 |

健康 JSON 是 `status/timestamp`，不套业务封套。城市成功是 `code/message/data/meta`；空数组是成功，错误 data 为 null。ID 始终为 String，开发样例来源固定 `dev_seed`、数据集 `dev-seed-cities-v1`、dataAsOf=null。页面明确说明没有真实交通观测或预测结果。

客户端先判断 HTTP 状态；只有匹配契约 HTTP/code 映射的合法错误封套才保留 businessCode/requestId，绝不向用户展示原始错误正文或堆栈。Vite 代理断开时产生的非 JSON 502 是基础设施错误，不伪称 Java 的 OpenAPI 业务错误。网络失败、超时和成功响应格式异常另行区分。

类型在运行时会被擦除，因此客户端还检查关键响应字段。完整 Schema 的权威仍是 `contracts/openapi.yaml` 与 WP2 验证器；前端没有维护第二份 OpenAPI。刷新开始即撤下过期健康/城市结果，失败后不会继续显示“服务正常”或旧城市选择。

## 代理与本地端口

开发默认转发到 `http://127.0.0.1:8080`，保留原路径；浏览器始终请求 Vite 的同源 `/health` 和 `/api/v1/cities`。不使用 WP3 的临时验收端口 63016，不在 Vue 组件里写后端地址。

如果 8080 已占用，先诊断监听 PID，不结束其他进程；让自己启动的 Java 使用确认可用的其他端口，并只在当前前端终端指定对应地址：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue
# 例如本次 Java 明确启动于 8081 时：
$env:DEV_BACKEND_URL = 'http://127.0.0.1:8081'
npm.cmd run dev
```

`DEV_BACKEND_URL` 不使用 VITE_ 前缀，不被注入组件。目标仅允许本机 HTTP origin，不允许凭据或附加路径。未修改系统代理、PATH 或安全策略。

Vite 代理只用于开发。`dist` 正式部署必须由部署环境配置同源 API 转发；本轮没有部署生产网站，也不能用 preview 成功加载静态页面证明后端已联通。

## 真实浏览器验收复现

先按后端说明用 Wrapper `verify` 生成 JAR，并安装 WP2 隔离验证依赖。前端依赖已 `npm.cmd ci` 后，在当前终端读取现有 Java 配置：

```powershell
$env:JAVA_HOME = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User')
$env:JDK_JAVA_OPTIONS = [Environment]::GetEnvironmentVariable('JDK_JAVA_OPTIONS', 'User')
npm.cmd run test:e2e
```

需要本机已有 Chrome 或 Edge；本轮使用真实 Chrome 155.0.8059.41，没有安装系统浏览器或操作用户个人浏览器会话。Playwright 启动隔离、无头浏览器，真实加载页面并截图，不拦截接口造成功响应。

脚本先检查 8080/5173；占用时记录只读 PID 诊断，选相邻可用端口，并把实际 Java 端口传给 Vite。启动普通 Java、停止后自动检测失败、恢复后点击重试、真实浏览器离线/恢复、最后真实 Java 空列表配置。只终止自己持有的 Java/Vite 子进程并关闭自己的浏览器，最后确认端口释放。

默认结果保存在 `frontend/outputs/integration`，该目录被 Git 忽略。已存在时拒绝覆盖，复测示例：

```powershell
npm.cmd run test:e2e -- outputs/integration-another-run
```

`manifest.json` 保存命令、PID、端口、响应状态、浏览器版本、步骤、源文件哈希和清理结果；`schema-validation.json` 保存 OpenAPI 校验和真实 Java requestId 日志关联。期望退出 0；浏览器不能启动时明确失败，不会伪造验收。

WP5 要求健康时间属于本次运行、requestId 不重复、四个成功阶段均有两个真实接口响应、停服阶段确实捕获两条代理故障。非 JSON 代理正文保存为 .txt。Java 就绪必须先在本任务子进程日志中出现启动成功信息，避免遗留服务掩盖启动失败。

Windows 默认尝试已有 Chrome/Edge；Linux 默认使用 Playwright Chromium。可通过进程变量 `BROWSER_CHANNEL=chromium` 和 `CONTRACT_PYTHON=python` 指定 CI 浏览器及已装验证依赖的解释器。CI 浏览器二进制仅下载到 runner 临时目录，不安装系统软件；本机验收仍使用已有 Chrome。不要把本机通过视为 Linux 或 GitHub 云端已通过。

成功联调后可执行故障检测自验（第二个输出目录必须不存在）：

```powershell
..\contracts\.venv\Scripts\python.exe scripts/check-regression-failures.py outputs/integration-another-run outputs/negative-another-run
```

它仅篡改自己创建的证据临时副本，确认非法来源、缺失 null 字段、历史时间、null 城市列表、缺失 Java 日志被拒绝，并实际用不存在的 JDK 路径验证启动失败。6 个子检查均应非零，整个检测驱动应退出 0。不是 Mock 接口联调。完整顺序见 [回归与 CI 指南](../docs/guides/s2-regression.md)。

可提交的审阅快照见 [S2-WP4 证据目录](../docs/stage-reports/evidence/S2-WP4)，真实运行结果与边界见 [S2 报告](../docs/stage-reports/S2.md)。

S3：来源标签区分七类登记来源及空/混合目录。混合来源不展示虚假的单数据集 ID，城市目录采集时间不适用。完整 MySQL 联调入口见 docs/guides/s3-mysql.md；不能再用 S2 内存 seed 启动方式运行。
