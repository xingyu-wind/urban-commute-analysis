# S2 回归与 CI

契约仍为 contracts/openapi.yaml；WP5 不增加业务接口或修改业务 DTO。源码需要 Java 21、Node 24、Python 3.11。依赖分别由 Maven Wrapper、package-lock.json、contracts/requirements.lock.txt 固定。

## Windows 本地顺序

在仓库根目录执行。先按 contracts/README.md 准备隔离 Python 依赖；输出目录如已存在，改用新的目录名，保留已有证据。

```powershell
$env:JAVA_HOME = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User')
$env:JDK_JAVA_OPTIONS = [Environment]::GetEnvironmentVariable('JDK_JAVA_OPTIONS', 'User')
$env:MAVEN_USER_HOME = 'D:\WindXingyu\Temp\urban-commute-S2-WP3\maven-user-home'
.\contracts\.venv\Scripts\python.exe scripts/check_ci.py
.\contracts\.venv\Scripts\python.exe -m openapi_spec_validator contracts/openapi.yaml
.\contracts\.venv\Scripts\python.exe contracts/validate_contract.py
.\backend\mvnw.cmd -f backend/pom.xml -B -ntp '-Dmaven.repo.local=D:\WindXingyu\Temp\urban-commute-S2-WP3\maven-repository' verify
# 应在 verify 后立即验证，JUnit HTTP 证据最多允许 10 分钟。
.\contracts\.venv\Scripts\python.exe backend/scripts/verify_http.py --output backend/target/regression-new
Set-Location frontend
npm.cmd ci --no-audit --no-fund
npm.cmd run type-check
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e -- outputs/regression-new
..\contracts\.venv\Scripts\python.exe scripts/check-regression-failures.py outputs/regression-new outputs/negative-new
```

上述是顺序执行命令清单；逐条检查 `$LASTEXITCODE`，任何非零即停止后续验收并修复，不以最后一条成功掩盖前面的失败。仅在当前进程读取现有用户 Java 参数，不写入环境配置。Windows 使用 npm.cmd，不放宽执行策略。

## GitHub Actions

工作流 `.github/workflows/s2-ci.yml`：main PR、main/feat/** push 或手工 dispatch 触发；Ubuntu 24.04 单一回归 job，20 分钟超时，同一 ref 新运行取消旧运行。contents:read 是唯一 token 权限，checkout 不保留凭据，所有 Action 使用完整提交 SHA。

流程为工具配置 → 锁定验证依赖 → CI 策略/OpenAPI/正反例 → `bash backend/mvnw ... verify` → 独立 Java HTTP/Schema → npm ci → 类型/单测/build → Playwright Chromium → 无请求 Mock 浏览器联调 → 故障检测自验。任一步失败阻断后续正常测试，最后 always 上传诊断，保存 7 天。没有部署、自动合并或远端写入。

Linux 使用 bash Wrapper 和 PATH 中的 python；Windows 使用 mvnw.cmd 与隔离 Scripts/python.exe。浏览器驱动使用平台对应 Java 路径；CI 显式设置 CONTRACT_PYTHON=python、BROWSER_CHANNEL=chromium。Chromium 仅下载到 RUNNER_TEMP/s2-playwright，无 --with-deps/apt；依赖标准 Ubuntu Runner 已有的 Chrome 系统库。参考 [Runner 软件清单](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md) 和 [Playwright CI 文档](https://playwright.dev/docs/ci)。首次云端运行仍须核实该假设与完整 Linux 流程，不能用本地 Windows 结果替代。

Maven/npm/pip 缓存按相应 pom/lock 文件生成。产物仅上传 surefire-reports、独立 HTTP 证据与 frontend/outputs，不上传 JAR、node_modules、虚拟环境或浏览器二进制。第三方依赖仍需下载网络；不使用真实密钥。

## 验收边界与失败诊断

- JUnit 的空列表/500/503 使用测试层替身；独立 JAR 空列表使用真实配置。不要将故障替身声称为生产故障。
- 浏览器真实选择北京/上海，检查 dev_seed、停服自动失败、恢复重试、真实浏览器断网及恢复、Java 空列表。成功响应经同一 OpenAPI Schema 校验，并关联真实 Java 日志和动态 requestId。
- Vite 停服代理错误属于基础设施故障；本机实测 502/text/plain，单独记录，不冒充 Java JSON 错误。
- 启动失败、Schema 不符、缺失阶段、历史时间、失去日志关联或清理失败均使验证非零。故障自验只有确认 6 个预期失败后才退出 0。
- 驱动只关闭自己的浏览器及 Java/Vite 子进程，端口占用先诊断并选可用端口，不结束未知进程。Ctrl+C/外部强制中断不应当作成功验收；查阅 manifest 清理字段。

`scripts/check_ci.py` 检查项目 CI 规则；另使用官方 [actionlint](https://github.com/rhysd/actionlint) 做工作流语法/上下文校验，不把前者等同完整 Actions 语义验证。WP5 本地临时 actionlint 1.7.12 检查退出 0，详情见阶段报告。未推送，未触发 GitHub 云端 CI；首次获授权的 PR/CI 运行必须另行留存结果。
