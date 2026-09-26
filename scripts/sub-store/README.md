# Sub-Store 节点脚本

[rename.js](rename.js) 用于节点名称、地区、序号、倍率和过滤处理，参数说明在文件开头。

[clash-download-gateway.js](clash-download-gateway.js) 挂在 Sub-Store 前面，对外订阅地址与 3001 端口保持不变。通用订阅不带格式参数；`mihomo`、`Go-http-client`、原样 `ShadowRocket`、空 UA 及其他未识别 UA，由网关统一改成 `clash-meta` 再转发，让 OpenClash、Clash Party、Clash Meta for Android 等 Meta/mihomo 客户端拿到完整节点 YAML，避免把 base64 字符串交给 proxy-provider 解析。

`ClashParty/2.0.3`、`clash-party/`、`MihomoParty/` 等 Party UA 也统一改成 `clash-meta`，避免 Sub-Store 将 Party 误判为普通 Clash 而遗漏 AnyTLS、Hysteria2 等节点。`ClashMetaForAndroid/2.11.32.Meta` 已能被识别为 Meta，保留原 UA。

网关仅改写不带显式格式的订阅下载 GET/HEAD 请求。其他已识别客户端、`platform/target` 参数、路径中的显式格式和管理 API 均保持原样；不按旧内核能力过滤节点或规则。网关只使用 Node.js 内置模块，上游无响应超过 30 秒返回 504，上游断流会终止响应。

离线回归检查：

```sh
node --test scripts/sub-store/clash-download-gateway.test.js
```

修改后还须部署到实际 Sub-Store 入口，再把客户端使用的完整转换链接放入 `E2E_LIVE_URL` 环境变量，执行 `python3 -B scripts/ci/validate.py --live`。需要核验内核支持时，指定客户端实际内核的 `E2E_MIHOMO_BIN` 并追加 `--mihomo`。详细步骤见 [实际服务器校验说明](../ci/README.md)；CI 测试通过不能代替实际部署验证。校验工件保留在工作区 `temp/`，不自动清理。

`rename.js` 默认 `nm=false` 会移除未识别地区的节点；希望保留时加入 `nm` 参数。`blockquic` 会改变节点属性，地区名称也不能证明真实出口位置。
