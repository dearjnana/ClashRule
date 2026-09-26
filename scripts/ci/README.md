# 订阅转换校验

`validate.py` 检查转换后的完整配置、策略组引用，以及每个 HTTP proxy-provider 返回的数据。它会实际请求 provider，要求响应为含非空 `proxies` 列表的 YAML 映射。base64 通用订阅虽然可以被 YAML 解析成字符串，仍必须判定失败，不能仅靠 HTTP 200 或 YAML 解析成功判断。

Gemini 使用仓库固定约定：只保留一个可见的 `🎐 Gemini` 组，类型必须为 `url-test`，供 Web 与 API/AI Studio 共用。校验会拒绝旧 API 组、地区子组、手动选择类型、隐藏状态及继续引用策略子组的结构。

离线测试直接读取 `openclash.ini`、`android.ini`、`clash-party.yaml` 的 Gemini 筛选表达式，确认带机场前缀的美国、英国节点仍能入选，而香港和到期提示不能入选，防止表达式错误地要求地区必须位于节点名开头。

依赖 Python 3 和 PyYAML。离线回归测试：

```sh
python3 -B -m unittest discover -s scripts/ci -p 'test_validate.py' -v
```

## 只读检查实际服务器

把**客户端实际导入的完整转换链接**放入 `E2E_LIVE_URL` 环境变量，避免在命令参数和日志里暴露订阅令牌。Linux 交互终端可隐藏输入：

```sh
read -r -s -p '转换链接: ' E2E_LIVE_URL
export E2E_LIVE_URL
python3 -B scripts/ci/validate.py --live
```

该模式只向订阅服务发送 GET，不创建、修改或删除 Sub-Store 对象。它分别使用 Clash Party、Clash Meta for Android、`ClashforWindows`、`mihomo`、`Go-http-client`、`ShadowRocket`、`clash` 的 UA 下载完整配置，再用这些 UA 以及 provider 自己声明的 UA 拉取节点文件。配置中的其他请求头会保留。订阅地址继续使用不带 `platform/target` 的通用链接。

如果转换链接包含 `config`，脚本还会读取该 INI，比较策略组名称集合；未提供时检查生成配置内部引用。日志只显示用例编号、HTTP 状态、结构错误类型，不打印订阅 URL、节点或响应正文。失败退出码为 1。

默认不运行内核。需要额外验证时，在运行机器上指定现有 mihomo 或旧 Clash 二进制。建议使用客户端实际内核，这样能发现不同内核对节点类型、provider header 等功能的支持差异：

```sh
export E2E_MIHOMO_BIN=/path/to/mihomo
export E2E_GEOIP_FILE=/path/to/Country.mmdb
python3 -B scripts/ci/validate.py --live --mihomo
```

`E2E_GEOIP_FILE` 可选；设置后会把已有 Country.mmdb 复制到本次独立内核目录，避免内核自动联网下载该文件。未指定 `E2E_MIHOMO_BIN` 时会下载当前发布的 Linux amd64 mihomo；其他系统或架构必须指定匹配的本地二进制。内核原始输出可能含私人订阅信息，因此不会打印。

**`-t` 只检查配置，不能证明 provider 已实际下载。** `--mihomo` 还会运行隔离内核副本：关闭 TUN、DNS 和代理监听，在随机本地端口启用带随机口令的控制器，最多等 30 秒，确认每个 provider 已加载源订阅的全部预期节点。预期名称取自配置实际声明的 User-Agent 对应响应；未声明时另以 `clash.meta` 获取，避免混用不同客户端格式。只加载部分节点或 `COMPATIBLE` 占位均判失败。原始配置和正在使用的内核均不修改；验证进程结束时仅终止该测试进程，保留所有文件。

隔离内核还必须通过 `/proxies` 接口确认 `🎐 Gemini` 为可见的自动优选组，候选列表至少包含一个已下载的真实节点。空列表、只有 `REJECT`/`COMPATIBLE` 占位或其他策略组都不能通过；日志不输出候选节点名称。CI 的美国 Trojan 测试节点用于覆盖 Web/API 共同地区池。该检查验证候选池实际形成，不宣称测试节点能访问 Gemini，也不要求虚构的 CI 节点完成外网测速。

**CI 通过只证明 CI 拓扑正常。修改网关后还须在实际服务器部署并运行 `--live`，才能证明生产链路已修复。**

## CI 模式与保留工件

不加 `--live` 时保持原 CI 接口：`E2E_INI_URLS` 为换行分隔的 INI 地址，`E2E_CONVERTER`、`E2E_SUBSTORE` 可覆盖隔离服务地址。CI 会创建唯一名称的测试订阅和中文聚合，不覆盖已有对象，也不执行 DELETE。该模式始终运行 mihomo 校验。

CI 使用 GitHub Actions 自动提供的只读 token，经 `E2E_GITHUB_TOKEN` 环境变量传入验证容器，避免共享 runner 的匿名 GitHub API 限流。该 token 仅用于固定的官方 mihomo 版本查询 API，且此请求禁止重定向；二进制、规则和订阅下载均不携带它。指定 `E2E_MIHOMO_BIN` 时完全跳过版本查询。日志分别标明版本查询、二进制下载和测试数据创建阶段，错误信息不包含 token 或私人 URL。

所有运行工件保留于仓库根目录的 `temp/subscription-validation-*`，使用唯一目录且不自动清理。可用 `E2E_WORK_ROOT` 指定另一个工作区根目录，工件仍置于其 `temp/` 下。容器运行时需允许该目录写入。`summary.json` 只包含模式、通过状态、错误数及是否请求内核验证。

启用内核验证时，保留的 YAML 配置可能包含订阅地址、节点和请求头；`temp/` 必须排除 Git 提交，勿公开上传这些配置。脚本不自动清空 `temp/`。
