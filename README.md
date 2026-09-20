# ClashRule

Clash / OpenClash 规则仓库。2026-09-20 新增完整的 V1 本地规则包：下载并审查原 INI 的全部 44 个依赖文件，按用途分类、去重、修正规则并补充 Gemini 网页与手机 App 分流。

**旧入口保留，新版位于 `profiles/`。新版必须在订阅转换后执行 `tools/finalize.py`，不能直接把转换中间文件当作最终配置。** 使用、自动更新限制和回退方法见 [使用与回退](docs/使用与回退.md)。

## 从这里开始

- [优化版 INI](profiles/MyRuleClash_Plus_V1.optimized.ini)：主规则 2,842 条，另有两份原生规则集合。
- [完全展开版 INI](profiles/MyRuleClash_Plus_V1.expanded.ini)：14,702 条，便于对照与排查规则集合下载问题。
- [优化报告](docs/优化报告.md)：具体修改、每份文件前后数量和验证范围。
- [Gemini 专用规则](rules/ai/Gemini.list)：24 条；由自己的仓库维护，不再依赖修改 ACL4SSR 上游文件。
- [来源与维护](docs/来源与维护.md)、[仓库文件索引](docs/仓库文件索引.md)。

## 目录

| 目录 | 内容 |
|---|---|
| `profiles/` | 新版转换入口 |
| `rules/ai/` | Gemini、其他 AI |
| `rules/block/` | Adobe 拦截 / 放行例外、应用广告 |
| `rules/google/` | Google、FCM、国内 Google CDN、Google Earth |
| `rules/media/` | 视频、音乐及其他媒体 |
| `rules/games/` | 游戏平台、Steam 国内下载 |
| `rules/services/` | GitHub / Cloudflare / Docker、Microsoft、Apple、Samsung 等 |
| `rules/messaging/` | Telegram |
| `rules/privacy/` | IP 归属地分流 |
| `rules/network/` | 国内、代理、局域网、下载等通用规则 |
| `providers/` | 优化版使用的原生 domain / ipcidr 集合 |
| `templates/` | 基础模板和需要恢复的 Mihomo 原生分组字段 |
| `tools/` | 可复现构建、离线验证、转换结果整理 |
| `audit/` | 原始快照、下载清单、15,398 条逐条审计及验证结果 |
| `docs/`、`licenses/` | 使用说明、分类索引、来源和许可证 |

根目录原有规则、旧 INI、`ChinaConn/`、`clash-party/`、`docker-compose/` 等保留旧路径，避免仓库整理导致已有订阅和外部引用失效。原 README 保存在 [历史说明](docs/legacy/README-before-20260920.md)。

## 本地复核

```powershell
python -m pip install -r tools/requirements.txt
python tools/build.py
python tools/verify.py
```

构建完全使用审计快照，不访问运行中的路由器。验证覆盖域名优先级、IP 边界、同策略去重、CIDR / no-resolve 覆盖、规则集合等价、Gemini / FCM / Adobe 等回归场景，以及分组引用和循环。

已通过 SubConverter-Extended v1.9.6 → 本地整理 → Mihomo v1.19.31 的隔离集成测试。这不是生产环境吞吐量测试，也不代表 Gemini 已登录账号的网页及手机 App 全功能验收。
