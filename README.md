# ClashRule

个人 Clash 分流规则仓库。三个客户端入口都放在仓库根目录,规则源按分类放在 `rules/`。
**日常维护就是在 GitHub 网页上直接改文件、提交,不需要本地构建,也没有自动生成的文件。**

## 1. 三个入口

| 客户端 | 入口文件 | 用法 |
| --- | --- | --- |
| OpenClash(路由器) | [openclash.ini](openclash.ini) | 填到 SubConverter 的"外部配置",配合机场订阅转换后导入 |
| Clash Meta for Android | [android.ini](android.ini) | 同上,转换出的 YAML 导入手机 |
| Clash Party(桌面) | [clash-party.yaml](clash-party.yaml) | 直接导入应用的"覆写"页面,再绑定已有节点订阅,不走转换器 |

Raw 地址(填到对应位置):

```text
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/openclash.ini
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/android.ini
https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/clash-party.yaml
```

OpenClash / 安卓的转换请求结构(`url` 和 `config` 都要 URL 编码):

```text
https://你的转换器地址/sub?target=clash&url=编码后的个人订阅地址&config=编码后的INI地址&expand=true&new_name=true
```

转换结果就是完整配置,直接导入客户端;不需要再运行任何整理脚本。
Clash Party 不需要转换器,但没有节点订阅时覆写无法生效。

## 2. 目录结构

```text
├─ openclash.ini / android.ini   # 转换入口:规则引用顺序 + 全部策略组定义
├─ clash-party.yaml              # Clash Party 覆写
├─ rules/                        # 规则源(唯一的规则存放处)
│   ├─ ai/  block/  games/  google/  media/  messaging/
│   └─ network/  privacy/  services/
├─ deploy/                       # 自建转换器等服务的 compose 部署示例
├─ scripts/sub-store/            # Sub-Store 节点重命名脚本
└─ licenses/                     # 引用的上游规则许可证
```

部分列表(如 `BanAD.list`、`AdultCloud.list`、`CC_LS.list` 等)未被两个 INI 引用,是备用列表;Clash Party 覆写启用了其中一部分,以 `clash-party.yaml` 的 `rules!` 段为准。

## 3. 日常改规则(网页操作)

1. 打开 `rules/` 里对应的 `.list` 文件,点编辑。每行一条条件,注释用 `#`,只写条件本身,不写目标策略组:

   ```text
   # 精确匹配一个主机
   DOMAIN,api.example.com
   # 匹配域名本身及其所有子域名
   DOMAIN-SUFFIX,example.net
   ```

2. 提交到 `main`,等 [Actions 检查](https://github.com/dearjnana/ClashRule/actions/workflows/lint.yml)通过。检查内容:规则语法、INI 引用的文件是否存在、策略组引用是否完整、同文件重复行。
3. 让客户端拿到新配置:INI 入口需要重新转换一次;Clash Party 在应用里刷新对应规则集即可。

**给某份列表换策略组或调优先级**:改 INI 里的 `ruleset=组名,规则地址` 行,顺序即优先级(从上到下匹配,`MATCH` 兜底必须在最后)。`openclash.ini` 和 `android.ini` 内容保持一致,两份同步改。

**新增一份规则文件**:在 `rules/` 建文件,然后在两个 INI 里加一行 `ruleset=组名,https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/rules/分类/文件.list`,目标组用已有的;要新组就照旁边的行加一条 `custom_proxy_group`。

## 4. 策略组结构(两个 INI 相同)

- 业务组(YouTube、奈飞、Gemini、GitHub、摧城等)默认走 `🚀 节点选择`,可手动切换到机场组、地区组或直连。
- 机场分组:良心云、赚钱、宝可梦、LD士多、MESL 五家,各含"最优"全区组 + 港/台/日/韩/新/美地区组(url-test 自动测速)。
- `🛡️ 全局智能容灾-流量/速度`:机场间可用性回退与延迟比较。
- `🥒 寡妇网`:通用代理列表(ProxyGFWlist + ProxyLite),个人叫法,不代表某类网站。
- Gemini 两个组按 **Google 官方支持地区** 筛选,组内再分子组、每组 url-test 自动选最优:`♻️ Gemini 最优` 在全部支持地区里自动挑最快节点;香港、台湾、日本、韩国、新加坡、美国单独成组;冷门国家按相邻大洲归入欧洲、美洲其他、大洋洲、中东、非洲、亚洲其他(俄罗斯不在官方清单,不纳入)。API 组比网页组少香港、澳门、缅甸三个地区。筛选正则按 2026-09-21 的官方清单整理后直接写在文件里,想调整就改对应的 `custom_proxy_group` 行(或覆写里的 `filter` 字段)。子组没有匹配节点时为 REJECT,不会悄悄直连。

基础配置(端口、DNS 等)使用 [ACL4SSR 公共 base](https://github.com/ACL4SSR/ACL4SSR/blob/master/Clash/GeneralClashConfig.yml);要改就换 INI 末尾的 `clash_rule_base` 地址。

## 5. Clash Party 要点

- 覆写不是订阅:先在"订阅管理"里有可用节点订阅,再导入 `clash-party.yaml` 并绑定。带 `!` 的字段是应用的对象替换语法,不能直接交给内核当完整配置。
- 要使用文件里的 DNS / 嗅探方案,需关闭应用设置里对应的"DNS 覆写"等开关;TUN、系统代理、端口由应用管理。
- 首次绑定后确认"规则下载"组里有可用节点,规则集才能下载(缓存 86400 秒,可手动刷新)。
- 出问题先取消该订阅的覆写关联即可回退,不影响节点订阅。

## 6. 自建服务(可选)

- [deploy/](deploy/README.md):SubConverter-Extended、Sub-Store、DDNS、NPM 等容器部署示例,改完自行 `docker compose up -d`。
- [scripts/sub-store/rename.js](scripts/sub-store/rename.js):节点地区识别与重命名脚本,用法见[脚本说明](scripts/sub-store/README.md)。

## 7. 旧链接迁移对照

2026-09 简化目录结构,旧地址按此替换(GitHub Raw 不提供重定向):

| 旧路径 | 新路径 |
| --- | --- |
| `profiles/openclash.ini` | `openclash.ini` |
| `profiles/android.ini` | `android.ini` |
| `clients/clash-party/override.yaml` | `clash-party.yaml` |
| `generated/rules/...` | `rules/...` |
| `rules/...` | 不变 |
| `templates/`、`config/`、`tools/` | 已删除(不再需要转换后整理步骤) |

## 8. 来源与许可

部分规则源自 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 等上游项目,许可证见 [licenses/](licenses/ACL4SSR-LICENSE.txt);Clash Party 覆写另引用 MetaCubeX meta-rules-dat 的 `.mrs` 规则集。历史版本通过 Git 提交查看,仓库不保存旧文件副本。
