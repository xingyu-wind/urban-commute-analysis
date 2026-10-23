# Windows 候选的可信签名收尾

2026-10-23 实测：本机 Smart App Control（SAC）处于强制模式，`VerifiedAndReputablePolicyState=1`。CodeIntegrity 3099 记录策略 `VerifiedAndReputableDesktop`，GUID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`；3077 对 Electron 给出 `0xc0e90002`，Requested Signing Level=2、Validated Signing Level=1。这些字段不是要求购买 EV 企业证书的证明。`CiTool -lp` 在当前中等完整性会话返回 Access Denied；没有提权修改策略，结论由实际拒绝事件、策略加载日志和注册表状态共同支持。

## 当前事实

最终 `windows-v1-candidate-04` 的安装器本轮已实际安装、卸载、重装、同版本覆盖，均 exit 0；快捷方式目标和删除也通过。安装器仍为 NotSigned。先前被拒绝的是不同哈希的中间候选，不能把那次结果等同于最终候选。没有证据表明机器已信任全部组件：最终 Electron 通过 Playwright 和无调试参数的直接原生启动均被拒绝，后者 WinError 4551。SAC 可以依据云端信誉允许部分未签名程序，所以安装器运行成功也不构成可靠的签名替代品；本次没有测出其具体云端放行原因。[微软 SAC 工作原理](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview)。

本机 CurrentUser/My、LocalMachine/My 未发现代码签名证书；未发现已安装的 Windows SDK SignTool。用户已说明暂无可用签名身份。未上传候选文件申请外部复审，未购买服务，未导入自签根、创建白名单、改评估模式或绕过执行检查。

## 合法可行的签名路径

由本人或经授权的发布主体取得 **Microsoft Trusted Root Program 信任链内 CA 签发的 Authenticode 代码签名证书**，或符合资格的 **Azure Artifact Signing Public Trust**。需要真实身份验证以及可调用的硬件令牌/云签名私钥；不能只靠下载工具完成。自签证书、Private Trust 服务或给文件附上任意签名，均不能据此认定符合当前 SAC 的公开信任要求。[微软签名要求](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control)。

Azure 当前 Public Trust 个人身份限定美国/加拿大，组织也有列明的地域限制；若签名主体为中国大陆个人，不能把该服务当作现成可用方案。应先确认合法身份与 CA/服务的签发资格，不冒用其他地区或组织身份。[微软服务资格](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart#prerequisites)。

## 复用现有包，不重写应用

保留原候选 EXE、哈希和原始组件归档，在新的签名工作目录复用 `dist/windows-v1-candidate-04/application`：

1. 先签应用。当前 Electron 顶层未签名 PE 为 `UrbanCommute.exe`、`dxcompiler.dll`、`ffmpeg.dll`、`vk_swiftshader.dll`、`vulkan-1.dll`。保留已有 Microsoft 有效签名；对包内其他运行时和动态加载路径逐项审查，不预先假定签这五个文件就覆盖所有执行路径。
2. 使用 SHA256 文件摘要、RFC3161 时间戳（SHA256），并核验签名链/撤销状态。证书选择使用明确指纹或授权云服务身份，不在命令、Git 或日志中保存 PFX 密码/私钥。示意命令如下；目前未执行：

   ```text
   signtool sign /sha1 <授权证书指纹> /fd SHA256 /tr <CA指定的RFC3161地址> /td SHA256 <文件>
   signtool verify /pa /all /v /tw <文件>
   ```

3. 当前 Inno 脚本未配置 `SignTool`。取得签名能力后，在受控签名构建中设置 `[Setup] SignTool=<已定义的签名命令名称>` 及 `SignedUninstaller=yes`，用现有 Inno 编译器重封装已签的 application。它会对安装器、卸载器以及需要的安装临时副本签名。**仅对现有外层 Setup EXE 补签不够**：它不会替换内嵌 Electron，也不能补齐卸载器签名。[Inno SignTool](https://jrsoftware.org/ishelp/topic_setup_signtool.htm)、[SignedUninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm)。
4. 不重编前后端、不重训、不改演示种子。输出到新的候选目录，重新生成签名后大小、SHA256 和构建回执；签名后文件不再具有原 unsigned 候选的哈希。
5. 在 **SAC 仍为强制模式** 的机器验收安装、首次初始化、独立窗口、快捷方式、关闭/重启、管理导入、断网、卸载、重装及真正的跨版本升级。SAC 对加载的组件逐个检查，因此签名验证通过也不能代替实际全链路运行。[微软验收范围](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control)。

完整签名和这些验收目前仍依赖外部可信签名身份；没有为得到测试成功而降低本机安全防护。
