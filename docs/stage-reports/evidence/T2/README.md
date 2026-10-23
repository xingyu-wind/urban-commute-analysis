# T2 实测证据

最终ZIP SHA256 `d8b115918b4a2d4184bcec6e59736c29c339e3b5324f1aa7798d7336f7bdc3de`，721109字节，46文件；业务基线97f30db，打包提交79f9162，构建时工作区干净。

- acceptance.json：这份ZIP在独立中文/空格目录的实际BAT、MySQL、HTTP权限、研究导入、重启与异常退出验收；不是全新电脑。
- zip-inspection.json：完整文件清单、哈希/嵌套JAR/允许表和已知私有值检查。
- environment.json：实际Windows/运行存储、独立安装密码差异、凭据查看命令、原实例备份/正常停止；不含密码。
- browser-model.json、browser-warehouse.json及四张截图：真实production dist与API，1440/390，无请求拦截；截图已目视核对。
- resolved-failures-and-limits.json：初次失败的修复与仍未验证的环境边界。
- files.json：其他精选文件的SHA256，不包含清单自身。原始日志在忽略目录backend/target/t2-package-final。

全部业务演示为synthetic_test。两个独立种子不包含账号/审计/上传/Flyway历史；真实数据、真实预测准确率、跨城市泛化未解除。完整源库dump、私有配置、运行时目录和口令不随证据归档。
