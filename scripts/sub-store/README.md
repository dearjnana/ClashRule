# Sub-Store 节点脚本

[rename.js](rename.js) 用于节点名称、地区、序号、倍率和过滤处理，参数说明在文件开头。

[clash-download-gateway.js](clash-download-gateway.js) 挂在 Sub-Store 前面，占用对外 3001。通用订阅不带格式参数；`mihomo`、`Go-http-client`、原样 `ShadowRocket` 这类会被当成 V2Ray 的 UA，由网关改成 `clash-meta` 再转发，避免内核拿到 base64。

默认 `nm=false` 会移除未识别地区的节点；希望保留时加入 `nm` 参数。`blockquic` 会改变节点属性，地区名称也不能证明真实出口位置。脚本逻辑在本次规范化中保持不变，删除了被注释的旧代码。
