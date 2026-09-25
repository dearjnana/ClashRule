# ClashRule

[![检查](https://github.com/dearjnana/ClashRule/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/dearjnana/ClashRule/actions/workflows/lint.yml)

个人 Clash 分流规则仓库。三个客户端入口都在根目录,规则源在 `rules/`,在 GitHub 网页上直接编辑、提交即生效,没有本地构建步骤。

**顶部的徽章就是自动审核状态。** 每次提交分三步:先对 `openclash.ini`、`android.ini`、`clash-party.yaml` 做语法与引用校验(策略组结构、正则能否编译、引用的规则文件是否存在、同文件重复行);再在与线上一致(同镜像摘要)的 SubConverter-Extended + Sub-Store 容器里按本文档配方做**真实转换**,校验策略组一个不丢、无悬空引用、订阅源对任意 User-Agent 都返回 Clash YAML,并用 mihomo 内核 `-t` 实际加载;全部通过才在下方盖章并提交。绿色即全链路可用;变红点徽章进 Actions 看具体问题。

<!-- audit-start -->**最后审核通过:2026-09-25 21:40:35.443(北京时间)**<!-- audit-end -->

## 三个入口

| 客户端 | 入口 | 用法 |
| --- | --- | --- |
| OpenClash(路由器) | [openclash.ini](openclash.ini) | 填到 SubConverter 的"外部配置",配合机场订阅转换后导入 |
| Clash Meta for Android | [android.ini](android.ini) | 同上,转换出的 YAML 导入手机 |
| Clash Party(桌面) | [clash-party.yaml](clash-party.yaml) | 直接导入应用的"覆写"页,再绑定已有节点订阅,不走转换器 |

```text
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/openclash.ini
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/android.ini
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/clash-party.yaml
```

OpenClash / 安卓的转换请求结构(`url` 和 `config` 各自做 URL 编码):

```text
https://你的转换器地址/sub?target=clash&url=编码后的订阅地址&config=编码后的INI地址&expand=true&new_name=true
```

转换结果就是完整配置,直接导入,不需要任何整理脚本。

**订阅地址保持无后缀,格式强制由 gateway 网关完成。** SubConverter-Extended 对 `target=clash` 会把订阅原样透传成 `proxy-providers`,由客户端内核直接拉取订阅(这是该转换器的设计行为,策略组筛选以组内 `filter` 正则下发,不受影响)。但 Sub-Store 按"请求方 User-Agent"决定返回格式:mihomo 内核刷新 provider 时的 UA(如 `mihomo/v…`)不在其识别清单里,会拿到 base64 的 v2ray 订阅,内核按 YAML 解析即报 `cannot unmarshal !!str 'dmxlc3M…' into provider.ProxySchema`。因此 `deploy/sub-store/` 的 compose 在 Sub-Store 前部署了一个 nginx 网关(`gateway.conf`):对不带目标后缀的订阅/聚合下载请求自动追加 `/ClashMeta` 强制输出 Clash YAML,其余路径(前端、API)原样透传。**客户端与转换请求里的订阅地址一律写原始无后缀形式**(如 `http://Sub-Store地址/后台路径/download/collection/聚合`),不要手工添加格式后缀。

另外,`list=true` 让后端代取并展开节点,在 v1.9.7 对该聚合订阅无论 base64 还是 YAML 均解析失败(预处理层会把 base64 中的 `+` 还原成空格),不能作为替代方案,维持 provider 透传即可。

## 怎么改

- **改分流条件**:编辑 `rules/` 里对应的 `.list`,每行一条(`DOMAIN,api.example.com`、`DOMAIN-SUFFIX,example.net`),注释用 `#`。
- **换策略组 / 调优先级**:改 INI 里的 `ruleset=组名,规则地址` 行,从上到下就是匹配顺序,`MATCH` 兜底必须在最后。两个 INI 内容保持一致,同步修改。
- **url-test 组必须带测速 URL 字段**:`custom_proxy_group` 的 url-test 组第 5 个字段要写测速地址(如 `https://cp.cloudflare.com/generate_204`),否则 SubConverter-Extended 会**静默丢弃该组**,引用它的主组悬空,内核直接拒绝整个配置(2026-09 的 Gemini 子组丢组事故即由此而来,端到端审核的"组数一致"检查就是防它复发)。
- **新增规则文件**:在 `rules/` 建文件,然后在两个 INI 里各加一行 `ruleset=组名,https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/rules/分类/文件.list`,组名用已有的。
- **Clash Party**:改 `clash-party.yaml`。只改了规则源的话在应用里刷新规则集即可;改了覆写本身要更新覆写并重新应用。
- **链接缓存**:三个文件里指向本仓库的链接都带 `?timestamp=` 参数,用来绕过 GitHub Raw 的各级缓存。改完规则如果客户端/转换器还在用旧内容,把文件里的时间戳全局替换成一个新数字即可强制刷新(当前为 `1790042073`)。
- 提交后看徽章,绿了再去设备上更新配置。

部分列表(如 `BanAD.list`、`AdultCloud.list`、`CC_LS.list` 等)未被两个 INI 引用,是备用列表;Clash Party 覆写启用了其中一部分,以它的 `rules!` 段为准。

## 策略组一览

- 业务组(YouTube、奈飞、GitHub、摧城等)默认走 `🚀 节点选择`,可手动切换到机场组、地区组或直连。
- 机场分组:INI 入口保留五家机场的"最优"全区组 + 港/台/日/韩/新/美地区组;Clash Party 覆写已精简为四家"机场最优"+ 六个"地区自动"组(跨全部机场按地区筛选、自动测速),业务组切换菜单约 21 项;另有全局容灾组做机场间回退。
- **Gemini** 两个组按 Google 官方支持地区筛选,组内再分子组、每组自动选最快:`♻️ Gemini 最优` 在全部支持地区里自动挑;常用地区(港/台/日/韩/新/美)单独成组;冷门国家按相邻大洲归入欧洲、美洲其他、大洋洲、中东、非洲、亚洲其他。俄罗斯不在官方清单,不纳入;API 组不含香港/澳门/缅甸。想调整筛选就改对应的 `custom_proxy_group` 行(或覆写里的 `filter` 字段)。子组没有匹配节点时为 REJECT,不会悄悄直连。
- 基础配置(端口、DNS 等)使用 [ACL4SSR 公共 base](https://github.com/ACL4SSR/ACL4SSR/blob/master/Clash/GeneralClashConfig.yml),要换就改 INI 末尾的 `clash_rule_base` 地址。

## 目录

```text
├─ openclash.ini / android.ini / clash-party.yaml   # 三个客户端入口
├─ rules/               # 规则源(ai/ games/ google/ media/ network/ services/ ...)
├─ deploy/              # SubConverter、Sub-Store 等自建服务 compose 示例
├─ scripts/sub-store/   # 节点地区识别与重命名脚本
├─ scripts/ci/          # 端到端审核用的 compose 与验证脚本
└─ licenses/            # 上游规则许可证
```

## 来源与许可

部分规则源自 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR),Clash Party 覆写另引用 MetaCubeX meta-rules-dat 的规则集;许可证见 [licenses/](licenses/ACL4SSR-LICENSE.txt)。历史版本通过 Git 提交查看。
