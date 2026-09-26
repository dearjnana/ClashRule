# ClashRule

[![检查](https://github.com/dearjnana/ClashRule/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/dearjnana/ClashRule/actions/workflows/lint.yml)

个人 Clash 分流规则仓库。三个客户端入口都在根目录,规则源在 `rules/`,在 GitHub 网页上直接编辑、提交即生效,没有本地构建步骤。

**顶部的徽章就是自动审核状态。** 每次提交先检查规则、INI、覆写文件与回归用例，再在固定镜像的隔离容器中进行真实转换，检查策略组、引用、不同客户端 UA 的 provider YAML，并用内核校验配置及实际加载 provider。全部通过才更新下方审核时间。绿色证明 CI 测试拓扑通过；生产服务器必须部署同一网关，并另行运行 [真实链接校验](scripts/ci/README.md)，不能仅凭徽章判断线上已经修好。

<!-- audit-start -->**最后审核通过:2026-09-26 13:53:18.374(北京时间)**<!-- audit-end -->

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

**订阅地址用通用订阅,不要加 `?platform=ClashMeta` 或 `?target=ClashMeta`。** 转换器保持 `target=clash`。它会把订阅透传成 `proxy-providers`,内核再去拉这个地址,并把下载转换链接时的 User-Agent 写进 provider header。网页上的 `diyua=ShadowRocket` 后端不读。

Sub-Store 认不出 `mihomo/…`、`Go-http-client/1.1`、原样 `ShadowRocket` 时会返回 base64,开头是 `dmxlc3M`(vless)。内核就报 `cannot unmarshal !!str into provider.ProxySchema`。这和 INI 无关,只改 GitHub 上的规则也不会消失。

`deploy/sub-store/` 把 3001 交给下载网关 [`scripts/sub-store/clash-download-gateway.js`](scripts/sub-store/clash-download-gateway.js)。订阅地址仍是下面这种无参数形式;网关只在 UA 会被当成 V2Ray 时,改写转发给 Sub-Store 的 User-Agent,让内核拿到 YAML。已识别的客户端和显式格式参数不动。

```text
http://Sub-Store地址/后台路径/download/collection/聚合
```

改完要在跑 Sub-Store 的机器上重新部署 `deploy/sub-store`。只推这个仓库、不重新部署 3001,现有链接还会报同样的错。

排障时要检查两次请求：客户端先从转换后端下载配置，再按配置中的 `proxy-providers` 地址与 `header` 下载节点。只看转换请求 HTTP 200，或只运行 `mihomo -t`，无法证明远程 provider 已成功装载。`scripts/ci/validate.py --live --mihomo` 用真实转换链接检查这两步；链接从 `E2E_LIVE_URL` 环境变量读取，日志不打印订阅内容。测试文件保留在 `temp/`，不会自动删除。

客户端验收以 OpenClash、Clash Party、Clash Meta for Android 等 Meta 内核为准。CFW 0.11.0 的 2020 年内核既不支持 VLESS，也不支持本仓库的 `PROCESS-NAME` 等规则；给地址追加 `target=ClashMeta` 不能补上旧内核缺失的能力。本仓库不会为它过滤节点或删减规则。

另外,`list=true` 让后端代取并展开节点,在 v1.9.7 对该聚合订阅无论 base64 还是 YAML 均解析失败(预处理层会把 base64 中的 `+` 还原成空格),不能作为替代方案,维持 provider 透传即可。

## 怎么改

- **改分流条件**:编辑 `rules/` 里对应的 `.list`,每行一条(`DOMAIN,api.example.com`、`DOMAIN-SUFFIX,example.net`),注释用 `#`。
- **换策略组 / 调优先级**:改 INI 里的 `ruleset=组名,规则地址` 行,从上到下就是匹配顺序,`MATCH` 兜底必须在最后。两个 INI 内容保持一致,同步修改。
- **url-test 组必须带测速 URL 字段**:`custom_proxy_group` 的 url-test 组要按 `` `url-test`正则`[]REJECT`http://www.gstatic.com/generate_204`300,,50 `` 的老格式写全测速地址与间隔字段,否则 SubConverter-Extended 会**静默丢弃该组**,引用它的主组悬空,内核直接拒绝整个配置(2026-09 的 Gemini 子组丢组事故即由此而来,端到端审核的"组数一致"检查就是防它复发)。
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
