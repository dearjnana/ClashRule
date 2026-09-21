# Clash Party 覆写使用说明

本目录的 [override.yaml](override.yaml) 用于 [Clash Party](https://github.com/mihomo-party-org/clash-party)。它保留现有订阅的节点和节点集合，替换策略组、规则集、路由规则、DNS 和嗅探配置。**直接导入应用的“覆写”，不经过 SubConverter，也不需要运行 `finalize.py`。**

## 导入链接

```text
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/clients/clash-party/override.yaml
```

这是覆写链接，不是节点订阅。使用前需要在 Clash Party 的“订阅管理”中已有一份包含可用节点的订阅。`proxies` 节点列表和 `proxy-providers` 节点集合均可使用。

## 首次使用

1. 保留当前可用订阅和覆写设置。先给一个订阅试用，确认正常后再决定是否全局启用。
2. 打开 Clash Party 左侧的“覆写”，通过链接导入上面的 Raw 地址；也可导入下载后的 YAML 文件。
3. 把覆写关联到需要使用的节点订阅。单个订阅关联和全局覆写选一种即可；检查是否还有其他覆写在后面覆盖 `rules`、`proxy-groups`、DNS 或规则集。
4. 要使用本文件的 DNS 方案，关闭应用常用设置中的“DNS 覆写”。要使用本文件的嗅探设置，也应关闭应用对应的嗅探覆写；应用受控设置会在 YAML 覆写之后合并。
5. 在应用里选择规则模式。系统代理、TUN 开关、代理监听端口、允许局域网连接和控制器认证继续通过应用管理。本文件不会强制开启 TUN，不会修改系统路由，也不发布固定控制器口令。
6. 如果开启了“自动 Smart 规则覆写”，应用可能再次改变测速组；要按本文件的回退和延迟逻辑使用，应先关闭该功能，避免把其行为误认为本文件的行为。
7. 应用配置后查看“运行配置”、日志和规则集状态。确认规则集都有非零条目、节点组有成员，再测试常用网站。

更新时，先在覆写页面刷新远程覆写，并重新应用对应订阅。单纯更新机场订阅，不一定会刷新另一个独立下载的覆写文件。只修改规则源时，也可以在应用中刷新相应规则集；修改策略组、DNS、规则顺序或地址时，需要更新覆写本身。

## 节点如何分组

保留原文件的四家机场：**良心云、赚钱、宝可梦、MESL**，以及香港、台湾、日本、韩国、新加坡、美国六个地区。

| 策略组 | 行为 |
| --- | --- |
| `🚀 节点选择` | 各服务默认使用的选择入口，可手动选择机场、地区或全部节点 |
| `🛡️ 全局智能容灾-流量` | 按良心云 → 赚钱 → 宝可梦 → MESL 的顺序进行可用性回退；不读取机场剩余流量 |
| `🛡️ 全局智能容灾-速度` | 在机场全区组中比较探测延迟；延迟最低不等于带宽最大 |
| 机场全区“最优”组 | 筛选机场名称并进行延迟测试，四组保留后台探测 |
| 机场与地区组合组 | 同时匹配机场、地区，按需探测 |
| 地区手动组、`🌐 全部节点` | 手动选择匹配节点，排除公告、到期、剩余流量等条目 |
| `🎐 Gemini` | 首选 `🇺🇸 Gemini MESL美国`，可手动切换到其他列出的策略 |
| `📢 谷歌FCM` | 单独管理 Google 推送，默认交给 Google 组 |
| `📥 规则下载` | 专供远程规则下载，默认通过“全部节点”中的节点下载；可手动选择其他路径 |

筛选依赖**节点名称**，不是订阅显示名称。机场未在节点名中标明、订阅只包含其他机场或重命名脚本删除了标记时，机场专用组可能为空。此时可先在“全部节点”选择实际可用节点，并让“节点选择”使用该组；需要自动按机场分组时，再在自己的节点订阅中保留正确标记。

所有筛选组都设置 `empty-fallback: REJECT`：没有匹配节点时不会悄悄变成直连。Gemini 没有 MESL 美国节点时同样如此；请核对节点名称、实际出口和账号可用性。已有的策略选择会被缓存，更新覆写后应手动确认 Gemini 当前仍选择预期路径。

## 规则、DNS 和缓存

| 项目 | 当前方式 |
| --- | --- |
| 自建与已纳入本仓库的列表 | 引用 `rules/` 的分类路径，统一使用 `classical/text` |
| 纯域名及 IP 二进制列表 | 使用 MetaCubeX 的原生 `domain/mrs` 或 `ipcidr/mrs`，保留其分类覆盖 |
| 规则集缓存 | `./rule_provider/clashrule-party/`，相对于应用的内核工作目录，不是仓库目录或固定 Windows 路径 |
| 规则更新 | 每 86400 秒检查更新；也可在应用中手动刷新 |
| 测速周期 | 从原来的主要 300 秒统一调整为 600 秒，四个机场全区组持续探测，其他测试组按使用情况探测 |
| DNS 监听 | `127.0.0.1:1053`，只对本机开放 |
| 节点域名和直连解析 | 指定直连 DNS，为代理连接提供启动解析 |
| 境外业务解析 | 指定经过 `🚀 节点选择` 的加密 DNS |
| 国内域名解析 | 由 `cn_domain` 匹配后使用国内加密 DNS |
| 私有域名解析 | 由 `private_domain` 匹配后使用系统 DNS，保留本地网络解析能力 |

原文件的电报、媒体、游戏、Adobe、自定义“摧城/摧城低速”和 18X 分类继续保留。自建规则的目标策略以本覆写的 `rules` 为准，不由主配置的 `config/routing.json` 控制。比如 `CC_LS.list`、`AdultCloud.list`、`PixivSDK.list` 在这里启用，不代表两个 INI 主入口也启用了它们。

独立覆写的规则顺序与主配置不同，所以引用完整的 `rules/` 维护源，不引用已经按主配置优先级删去重复条件的 `generated/rules/`。以后在 GitHub 修改这些源文件，经 Actions 检查通过后，Clash Party 刷新对应规则集即可获取内容。

## 本次修复与优化

- 将已失效的根目录地址改为仓库分类路径，移除过期时间戳参数；已有仓库来源的列表统一从本仓库获取。
- 统一纠正 `.list` 与 `mrs/yaml` 的格式混用，避免配置语法能通过、规则实际加载失败。
- Adobe 放行先于拦截，Pixiv 例外先于广告列表；Gemini、FCM、YouTube 先于通用 Google，GitHub/Copilot 专项先于通用 AI，Steam 国内下载先于 Steam 通用规则。
- 移除重复的 YouTube Music 下载：其 `music.youtube.com` 已由 YouTube 列表覆盖。原名 GoogleEarth 的通用 Google 二进制列表改名为 `google_domain`，避免把整个 Google 集合误解为只含地球服务。
- 修正美国、韩国等地区的名称筛选，防止 Australia、Russia、Armenia、Ukraine 等名称误匹配；统一美国手动组的旗帜名称。
- 保留本地 IPv4 直连并补充 IPv6 本地网段；移除“所有目标端口 9090 都直连”的过宽条件。当前 IPv6 仍默认关闭，本地规则用于后续由应用开启 IPv6 的场景。
- 所有原生 IP 规则集使用 `no-resolve`，避免为了尝试 IP 匹配而额外触发域名解析。
- 移除写死的控制器口令、外部面板下载、Linux 重定向端口、TUN 强制启用以及已被内核移除的 `global-client-fingerprint`。
- 使用 `dns!`、`sniffer!`、`rule-providers!` 完整替换对应对象，避免与原订阅深度合并后残留旧规则集、旧 DNS 策略或无用下载。节点集合 `proxy-providers` 保留。

## 测试范围

本次核对 Clash Party **v2.0.3** 的官方 YAML 合并实现及其 `yaml 2.9.1` 解析依赖，并使用 **Mihomo v1.19.31** 进行测试。这是已验证基线，不代表其他版本或所有个人订阅都已实测。

1. 原生 YAML 锚点经官方解析器正确展开，官方合并函数与测试合并结果一致；节点、节点集合、TUN 和设备口令保留，待替换对象没有旧内容残留。
2. 70 个策略组无重名、无缺失引用、无循环；42 个规则集全部使用真实内容加载，且条目数非零。
3. 分别验证节点列表、节点集合、没有 MESL 三种场景；没有 MESL 时 Gemini 为 REJECT，韩国组不会错误包含 Ukraine 节点，公告条目被排除。
4. 在全新缓存目录中，通过配置指定的代理下载全部 42 个规则集。下载内容由本地测试代理返回，因此不会依赖真实机场或修改系统网络。
5. 通过实际代理入口建立连接并读取内核连接记录，验证 16 个用例：Gemini 网页和接口、FCM、YouTube Music/API、Adobe 放行/拦截、Pixiv、Copilot、Steam 国内下载、Google、IP 归属地分类、国内网站、9090 端口兜底和回环直连。
6. 测试关闭 TUN 和系统 DNS 接管，仅使用临时回环端口。它验证配置加载和路由行为，不代表真实节点的速度、解锁能力或用户账号一定可用。

[自动构建工作流](../../.github/workflows/build.yml) 已加入此覆写的结构检查和真实内核测试。验证程序为 [tools/verify_party.py](../../tools/verify_party.py)，报告位于忽略入库的 `reports/party-validation.json`，失败日志可在 Actions 的诊断报告中查看。

## 修改与回退

- 改分流条件：编辑对应 `rules/` 文件。
- 改覆写的规则顺序、策略组、DNS、筛选方式：编辑本目录 `override.yaml`，其中带 `&` 的公共模板会被后面的 `*` 引用。
- 改设备端口、TUN、系统代理或控制器认证：在 Clash Party 应用设置中操作。
- 出现问题：先取消该订阅的覆写关联或恢复原覆写，再检查日志和运行配置。无需删除节点订阅，也无需清空整个应用数据目录。

本文件是手动维护的客户端覆写源，不由 `tools/build.py` 自动重建；提交后 Actions 会自动验证。仓库不额外保存旧覆写副本，历史版本通过 Git 提交查看。

参考：[官方覆写导入说明](https://clashparty.org/docs/guide/override)、[YAML 合并规则](https://clashparty.org/docs/guide/override/yaml)、[v2.0.3 合并实现](https://github.com/mihomo-party-org/clash-party/blob/v2.0.3/src/main/utils/merge.ts)、[应用设置合并顺序](https://github.com/mihomo-party-org/clash-party/blob/v2.0.3/src/main/core/factory.ts)、[Mihomo 规则集格式](https://wiki.metacubex.one/config/rule-providers/)、[Mihomo 策略组字段](https://wiki.metacubex.one/config/proxy-groups/)。
