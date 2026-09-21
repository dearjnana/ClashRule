# Gemini 官方地区与节点筛选

本页由 `config/gemini-regions.json` 自动生成，核对日期：**2026-09-21**。

地区事实来自 Google 官方，中文及常见英文名称参考 Unicode CLDR。只保留整理后的地区数据，不把网页快照入库。

## 三个客户端的组定义

- `🎐 Gemini`：Gemini 网页与 Android 服务组，包含网页、Play 商店或 Assistant 列出的全部普通账号地区，不限制机场。
- `🧪 Gemini API`：AI Studio 与 Gemini API，按开发者服务的独立官方地区清单筛选，不限制机场。
- 原有仅面向 MESL 美国的测试组已删除。两个新组都直接显示匹配节点，不需要美国或某家机场作为中间组。
- 匹配国旗、地区中英文名称、常用城市别名和大写独立地区代码；无匹配节点时为 REJECT。

去重后记录：网页版 241 个普通账号地区、Play 商店 204 个地区、Assistant 225 个地区、API 229 个地区。

网页和安卓并非每种使用方式都在所有地区开放。表中分别标出安装、Assistant 与 API 支持；Assistant 仍可能需要邀请。网页表中的中国大陆条目只面向 Workspace，未纳入普通账号筛选。

**香港、澳门等地区在网页或 Android 清单中，但不在当前 API 清单中。** 因而开发者接口单独分流，避免用网页地区推断 API 可用性。

[GeminiAPI.list](../rules/ai/GeminiAPI.list) 优先于 [Gemini.list](../rules/ai/Gemini.list)。后者保留已有 API 条件，兼容尚未更新整份配置的旧订阅；新配置通过前置规则区分策略。

节点名称不证明真实出口，官方支持地区也不等于每个节点 IP、账号、套餐或功能都可用。地区名称缺失或只有模糊缩写时，先在自己的节点订阅补充真实地区信息；推荐使用国旗与完整地区名称。

## 维护与自动构建

在 GitHub 编辑 [地区源配置](../config/gemini-regions.json) 的地区、服务标记或别名，提交后 Actions 自动生成 OpenClash、Android 和 Clash Party 的筛选条件。日常构建离线使用已核对清单，不自动抓取上游网页。

OpenClash / Android 的组占位定义在 `config/groups.yaml`；Clash Party 中只有标记包围的 Gemini 两个组由构建更新，其余覆写仍手动维护。不要直接修改生成的长正则。

## 官方来源

- [Gemini 网页版可用地区](https://support.google.com/gemini/answer/13575153?hl=en)
- [Gemini Android 下载与 Assistant 可用地区](https://support.google.com/gemini/answer/14579026?hl=en&co=GENIE.Platform%3DAndroid)
- [AI Studio / Gemini API 可用地区](https://ai.google.dev/gemini-api/docs/available-regions?hl=en)
- [Unicode CLDR 地区名称](https://github.com/unicode-org/cldr-json/tree/main/cldr-json/cldr-localenames-full/main)

## 完整地区对照

| 代码 | 国家或地区 | 英文名称 | 网页版 | Play 商店 | Assistant | API |
| --- | --- | --- | --- | --- | --- | --- |
| AD | 安道尔 | Andorra | 是 | 是 | — | 是 |
| AE | 阿拉伯联合酋长国 | United Arab Emirates | 是 | 是 | 是 | 是 |
| AG | 安提瓜和巴布达 | Antigua & Barbuda | 是 | 是 | 是 | 是 |
| AI | 安圭拉 | Anguilla | 是 | 是 | — | 是 |
| AL | 阿尔巴尼亚 | Albania | 是 | 是 | 是 | 是 |
| AM | 亚美尼亚 | Armenia | 是 | 是 | 是 | 是 |
| AO | 安哥拉 | Angola | 是 | 是 | 是 | 是 |
| AQ | 南极洲 | Antarctica | 是 | — | 是 | 是 |
| AR | 阿根廷 | Argentina | 是 | 是 | 是 | 是 |
| AS | 美属萨摩亚 | American Samoa | 是 | 是 | 是 | 是 |
| AT | 奥地利 | Austria | 是 | 是 | 是 | 是 |
| AU | 澳大利亚 | Australia | 是 | 是 | 是 | 是 |
| AW | 阿鲁巴 | Aruba | 是 | 是 | 是 | 是 |
| AX | 奥兰群岛 | Åland Islands | 是 | 是 | 是 | — |
| AZ | 阿塞拜疆 | Azerbaijan | 是 | 是 | 是 | 是 |
| BA | 波斯尼亚和黑塞哥维那 | Bosnia & Herzegovina | 是 | 是 | 是 | 是 |
| BB | 巴巴多斯 | Barbados | 是 | — | 是 | 是 |
| BD | 孟加拉国 | Bangladesh | 是 | 是 | 是 | 是 |
| BE | 比利时 | Belgium | 是 | 是 | 是 | 是 |
| BF | 布基纳法索 | Burkina Faso | 是 | 是 | 是 | 是 |
| BG | 保加利亚 | Bulgaria | 是 | 是 | 是 | 是 |
| BH | 巴林 | Bahrain | 是 | 是 | 是 | 是 |
| BI | 布隆迪 | Burundi | 是 | — | 是 | 是 |
| BJ | 贝宁 | Benin | 是 | 是 | 是 | 是 |
| BL | 圣巴泰勒米 | St. Barthélemy | 是 | 是 | 是 | 是 |
| BM | 百慕大 | Bermuda | 是 | 是 | 是 | 是 |
| BN | 文莱 | Brunei | 是 | — | 是 | 是 |
| BO | 玻利维亚 | Bolivia | 是 | 是 | 是 | 是 |
| BQ | 荷属加勒比区 | Caribbean Netherlands | 是 | 是 | — | 是 |
| BR | 巴西 | Brazil | 是 | 是 | 是 | 是 |
| BS | 巴哈马 | Bahamas | 是 | 是 | 是 | 是 |
| BT | 不丹 | Bhutan | 是 | — | 是 | 是 |
| BW | 博茨瓦纳 | Botswana | 是 | 是 | 是 | 是 |
| BZ | 伯利兹 | Belize | 是 | 是 | 是 | 是 |
| CA | 加拿大 | Canada | 是 | 是 | 是 | 是 |
| CC | 科科斯（基林）群岛 | Cocos (Keeling) Islands | 是 | — | 是 | 是 |
| CD | 刚果（金） | Congo - Kinshasa | 是 | 是 | 是 | 是 |
| CF | 中非共和国 | Central African Republic | 是 | — | 是 | 是 |
| CG | 刚果（布） | Congo - Brazzaville | 是 | 是 | 是 | 是 |
| CH | 瑞士 | Switzerland | 是 | 是 | 是 | 是 |
| CI | 科特迪瓦 | Côte d’Ivoire | 是 | 是 | 是 | 是 |
| CK | 库克群岛 | Cook Islands | 是 | — | 是 | 是 |
| CL | 智利 | Chile | 是 | 是 | 是 | 是 |
| CM | 喀麦隆 | Cameroon | 是 | 是 | 是 | 是 |
| CN | 中国 | China | 仅 Workspace | — | — | — |
| CO | 哥伦比亚 | Colombia | 是 | 是 | 是 | 是 |
| CR | 哥斯达黎加 | Costa Rica | 是 | 是 | 是 | 是 |
| CV | 佛得角 | Cape Verde | 是 | 是 | 是 | 是 |
| CW | 库拉索 | Curaçao | 是 | 是 | 是 | 是 |
| CX | 圣诞岛 | Christmas Island | 是 | — | 是 | 是 |
| CY | 塞浦路斯 | Cyprus | 是 | 是 | 是 | 是 |
| CZ | 捷克 | Czechia | 是 | 是 | 是 | 是 |
| DE | 德国 | Germany | 是 | 是 | 是 | 是 |
| DJ | 吉布提 | Djibouti | 是 | 是 | 是 | 是 |
| DK | 丹麦 | Denmark | 是 | 是 | 是 | 是 |
| DM | 多米尼克 | Dominica | 是 | 是 | 是 | 是 |
| DO | 多米尼加共和国 | Dominican Republic | 是 | 是 | 是 | 是 |
| DZ | 阿尔及利亚 | Algeria | 是 | 是 | 是 | 是 |
| EC | 厄瓜多尔 | Ecuador | 是 | 是 | 是 | 是 |
| EE | 爱沙尼亚 | Estonia | 是 | 是 | 是 | 是 |
| EG | 埃及 | Egypt | 是 | 是 | 是 | 是 |
| EH | 西撒哈拉 | Western Sahara | 是 | — | 是 | 是 |
| ER | 厄立特里亚 | Eritrea | 是 | 是 | 是 | 是 |
| ES | 西班牙 | Spain | 是 | 是 | 是 | 是 |
| ET | 埃塞俄比亚 | Ethiopia | 是 | — | 是 | 是 |
| FI | 芬兰 | Finland | 是 | 是 | 是 | 是 |
| FJ | 斐济 | Fiji | 是 | 是 | 是 | 是 |
| FK | 福克兰群岛 | Falkland Islands | 是 | 是 | — | 是 |
| FM | 密克罗尼西亚 | Micronesia | 是 | 是 | 是 | 是 |
| FO | 法罗群岛 | Faroe Islands | 是 | 是 | 是 | 是 |
| FR | 法国 | France | 是 | 是 | 是 | 是 |
| GA | 加蓬 | Gabon | 是 | 是 | 是 | 是 |
| GB | 英国 | United Kingdom | 是 | 是 | 是 | 是 |
| GD | 格林纳达 | Grenada | 是 | 是 | 是 | 是 |
| GE | 格鲁吉亚 | Georgia | 是 | 是 | 是 | 是 |
| GF | 法属圭亚那 | French Guiana | 是 | 是 | 是 | 是 |
| GG | 根西岛 | Guernsey | 是 | 是 | — | 是 |
| GH | 加纳 | Ghana | 是 | 是 | 是 | 是 |
| GI | 直布罗陀 | Gibraltar | 是 | 是 | 是 | 是 |
| GL | 格陵兰 | Greenland | 是 | 是 | 是 | 是 |
| GM | 冈比亚 | Gambia | 是 | 是 | 是 | 是 |
| GN | 几内亚 | Guinea | 是 | 是 | 是 | 是 |
| GP | 瓜德罗普 | Guadeloupe | 是 | 是 | 是 | — |
| GQ | 赤道几内亚 | Equatorial Guinea | 是 | — | 是 | 是 |
| GR | 希腊 | Greece | 是 | 是 | 是 | 是 |
| GS | 南乔治亚和南桑威奇群岛 | South Georgia & South Sandwich Islands | 是 | — | — | 是 |
| GT | 危地马拉 | Guatemala | 是 | 是 | 是 | 是 |
| GU | 关岛 | Guam | 是 | 是 | 是 | 是 |
| GW | 几内亚比绍 | Guinea-Bissau | 是 | 是 | 是 | 是 |
| GY | 圭亚那 | Guyana | 是 | — | 是 | 是 |
| HK | 中国香港特别行政区 | Hong Kong SAR China | 是 | 是 | — | — |
| HM | 赫德岛和麦克唐纳群岛 | Heard & McDonald Islands | 是 | — | 是 | 是 |
| HN | 洪都拉斯 | Honduras | 是 | 是 | 是 | 是 |
| HR | 克罗地亚 | Croatia | 是 | 是 | 是 | 是 |
| HT | 海地 | Haiti | 是 | 是 | 是 | 是 |
| HU | 匈牙利 | Hungary | 是 | 是 | 是 | 是 |
| ID | 印度尼西亚 | Indonesia | 是 | 是 | 是 | 是 |
| IE | 爱尔兰 | Ireland | 是 | 是 | 是 | 是 |
| IL | 以色列 | Israel | 是 | 是 | 是 | 是 |
| IM | 马恩岛 | Isle of Man | 是 | 是 | — | 是 |
| IN | 印度 | India | 是 | 是 | 是 | 是 |
| IO | 英属印度洋领地 | British Indian Ocean Territory | 是 | 是 | — | 是 |
| IQ | 伊拉克 | Iraq | 是 | 是 | 是 | 是 |
| IS | 冰岛 | Iceland | 是 | 是 | 是 | 是 |
| IT | 意大利 | Italy | 是 | 是 | 是 | 是 |
| JE | 泽西岛 | Jersey | 是 | 是 | — | 是 |
| JM | 牙买加 | Jamaica | 是 | 是 | 是 | 是 |
| JO | 约旦 | Jordan | 是 | 是 | 是 | 是 |
| JP | 日本 | Japan | 是 | 是 | 是 | 是 |
| KE | 肯尼亚 | Kenya | 是 | 是 | 是 | 是 |
| KG | 吉尔吉斯斯坦 | Kyrgyzstan | 是 | 是 | 是 | 是 |
| KH | 柬埔寨 | Cambodia | 是 | 是 | 是 | 是 |
| KI | 基里巴斯 | Kiribati | 是 | — | 是 | 是 |
| KM | 科摩罗 | Comoros | 是 | 是 | 是 | 是 |
| KN | 圣基茨和尼维斯 | St. Kitts & Nevis | 是 | 是 | 是 | 是 |
| KR | 韩国 | South Korea | 是 | 是 | 是 | 是 |
| KW | 科威特 | Kuwait | 是 | 是 | 是 | 是 |
| KY | 开曼群岛 | Cayman Islands | 是 | 是 | 是 | 是 |
| KZ | 哈萨克斯坦 | Kazakhstan | 是 | 是 | 是 | 是 |
| LA | 老挝 | Laos | 是 | 是 | 是 | 是 |
| LB | 黎巴嫩 | Lebanon | 是 | 是 | 是 | 是 |
| LC | 圣卢西亚 | St. Lucia | 是 | 是 | 是 | 是 |
| LI | 列支敦士登 | Liechtenstein | 是 | 是 | 是 | 是 |
| LK | 斯里兰卡 | Sri Lanka | 是 | 是 | 是 | 是 |
| LR | 利比里亚 | Liberia | 是 | 是 | 是 | 是 |
| LS | 莱索托 | Lesotho | 是 | — | 是 | 是 |
| LT | 立陶宛 | Lithuania | 是 | 是 | 是 | 是 |
| LU | 卢森堡 | Luxembourg | 是 | 是 | 是 | 是 |
| LV | 拉脱维亚 | Latvia | 是 | 是 | 是 | 是 |
| LY | 利比亚 | Libya | 是 | 是 | 是 | 是 |
| MA | 摩洛哥 | Morocco | 是 | 是 | 是 | 是 |
| MC | 摩纳哥 | Monaco | 是 | 是 | 是 | 是 |
| MD | 摩尔多瓦 | Moldova | 是 | 是 | 是 | 是 |
| ME | 黑山 | Montenegro | 是 | — | 是 | 是 |
| MF | 法属圣马丁 | St. Martin | 是 | 是 | 是 | — |
| MG | 马达加斯加 | Madagascar | 是 | — | 是 | 是 |
| MH | 马绍尔群岛 | Marshall Islands | 是 | 是 | 是 | 是 |
| MK | 北马其顿 | North Macedonia | 是 | 是 | 是 | 是 |
| ML | 马里 | Mali | 是 | 是 | 是 | 是 |
| MM | 缅甸 | Myanmar (Burma) | 是 | 是 | 是 | — |
| MN | 蒙古 | Mongolia | 是 | — | 是 | 是 |
| MO | 中国澳门特别行政区 | Macao SAR China | 是 | 是 | — | — |
| MP | 北马里亚纳群岛 | Northern Mariana Islands | 是 | 是 | 是 | 是 |
| MQ | 马提尼克 | Martinique | 是 | 是 | 是 | — |
| MR | 毛里塔尼亚 | Mauritania | 是 | — | 是 | 是 |
| MS | 蒙特塞拉特 | Montserrat | 是 | 是 | — | 是 |
| MT | 马耳他 | Malta | 是 | 是 | 是 | 是 |
| MU | 毛里求斯 | Mauritius | 是 | 是 | 是 | 是 |
| MV | 马尔代夫 | Maldives | 是 | 是 | 是 | 是 |
| MW | 马拉维 | Malawi | 是 | — | 是 | 是 |
| MX | 墨西哥 | Mexico | 是 | 是 | 是 | 是 |
| MY | 马来西亚 | Malaysia | 是 | 是 | 是 | 是 |
| MZ | 莫桑比克 | Mozambique | 是 | 是 | 是 | 是 |
| NA | 纳米比亚 | Namibia | 是 | 是 | 是 | 是 |
| NC | 新喀里多尼亚 | New Caledonia | 是 | 是 | 是 | 是 |
| NE | 尼日尔 | Niger | 是 | 是 | 是 | 是 |
| NF | 诺福克岛 | Norfolk Island | 是 | — | 是 | 是 |
| NG | 尼日利亚 | Nigeria | 是 | 是 | 是 | 是 |
| NI | 尼加拉瓜 | Nicaragua | 是 | 是 | 是 | 是 |
| NL | 荷兰 | Netherlands | 是 | 是 | 是 | 是 |
| NO | 挪威 | Norway | 是 | 是 | 是 | 是 |
| NP | 尼泊尔 | Nepal | 是 | 是 | 是 | 是 |
| NR | 瑙鲁 | Nauru | 是 | — | 是 | 是 |
| NU | 纽埃 | Niue | 是 | — | 是 | 是 |
| NZ | 新西兰 | New Zealand | 是 | 是 | 是 | 是 |
| OM | 阿曼 | Oman | 是 | 是 | 是 | 是 |
| PA | 巴拿马 | Panama | 是 | 是 | 是 | 是 |
| PE | 秘鲁 | Peru | 是 | 是 | 是 | 是 |
| PF | 法属波利尼西亚 | French Polynesia | 是 | 是 | 是 | — |
| PG | 巴布亚新几内亚 | Papua New Guinea | 是 | 是 | 是 | 是 |
| PH | 菲律宾 | Philippines | 是 | 是 | 是 | 是 |
| PK | 巴基斯坦 | Pakistan | 是 | 是 | 是 | 是 |
| PL | 波兰 | Poland | 是 | 是 | 是 | 是 |
| PM | 圣皮埃尔和密克隆群岛 | St. Pierre & Miquelon | 是 | 是 | 是 | 是 |
| PN | 皮特凯恩群岛 | Pitcairn Islands | 是 | 是 | — | 是 |
| PR | 波多黎各 | Puerto Rico | 是 | 是 | 是 | 是 |
| PS | 巴勒斯坦领土 | Palestinian Territories | 是 | — | 是 | 是 |
| PT | 葡萄牙 | Portugal | 是 | 是 | 是 | 是 |
| PW | 帕劳 | Palau | 是 | 是 | 是 | 是 |
| PY | 巴拉圭 | Paraguay | 是 | 是 | 是 | 是 |
| QA | 卡塔尔 | Qatar | 是 | 是 | 是 | 是 |
| RE | 留尼汪 | Réunion | 是 | 是 | 是 | 是 |
| RO | 罗马尼亚 | Romania | 是 | 是 | 是 | 是 |
| RS | 塞尔维亚 | Serbia | 是 | 是 | 是 | 是 |
| RW | 卢旺达 | Rwanda | 是 | 是 | 是 | 是 |
| SA | 沙特阿拉伯 | Saudi Arabia | 是 | 是 | 是 | 是 |
| SB | 所罗门群岛 | Solomon Islands | 是 | 是 | 是 | 是 |
| SC | 塞舌尔 | Seychelles | 是 | 是 | 是 | 是 |
| SD | 苏丹 | Sudan | 是 | 是 | 是 | 是 |
| SE | 瑞典 | Sweden | 是 | 是 | 是 | 是 |
| SG | 新加坡 | Singapore | 是 | 是 | 是 | 是 |
| SH | 圣赫勒拿 | St. Helena | 是 | — | — | 是 |
| SI | 斯洛文尼亚 | Slovenia | 是 | 是 | 是 | 是 |
| SJ | 斯瓦尔巴和扬马延 | Svalbard & Jan Mayen | 是 | 是 | 是 | — |
| SK | 斯洛伐克 | Slovakia | 是 | 是 | 是 | 是 |
| SL | 塞拉利昂 | Sierra Leone | 是 | 是 | 是 | 是 |
| SM | 圣马力诺 | San Marino | 是 | 是 | 是 | 是 |
| SN | 塞内加尔 | Senegal | 是 | 是 | 是 | 是 |
| SO | 索马里 | Somalia | 是 | 是 | 是 | 是 |
| SR | 苏里南 | Suriname | 是 | 是 | 是 | 是 |
| SS | 南苏丹 | South Sudan | 是 | — | 是 | 是 |
| ST | 圣多美和普林西比 | São Tomé & Príncipe | 是 | — | 是 | 是 |
| SV | 萨尔瓦多 | El Salvador | 是 | 是 | 是 | 是 |
| SX | 荷属圣马丁 | Sint Maarten | 是 | — | — | — |
| SZ | 斯威士兰 | Eswatini | 是 | — | 是 | 是 |
| TC | 特克斯和凯科斯群岛 | Turks & Caicos Islands | 是 | 是 | 是 | 是 |
| TD | 乍得 | Chad | 是 | 是 | 是 | 是 |
| TF | 法属南部领地 | French Southern Territories | 是 | 是 | — | — |
| TG | 多哥 | Togo | 是 | 是 | 是 | 是 |
| TH | 泰国 | Thailand | 是 | 是 | 是 | 是 |
| TJ | 塔吉克斯坦 | Tajikistan | 是 | 是 | 是 | 是 |
| TK | 托克劳 | Tokelau | 是 | — | 是 | 是 |
| TL | 东帝汶 | Timor-Leste | 是 | — | 是 | 是 |
| TM | 土库曼斯坦 | Turkmenistan | 是 | 是 | 是 | 是 |
| TN | 突尼斯 | Tunisia | 是 | 是 | 是 | 是 |
| TO | 汤加 | Tonga | 是 | 是 | 是 | 是 |
| TR | 土耳其 | Türkiye | 是 | 是 | 是 | 是 |
| TT | 特立尼达和多巴哥 | Trinidad & Tobago | 是 | 是 | 是 | 是 |
| TV | 图瓦卢 | Tuvalu | 是 | — | 是 | 是 |
| TW | 台湾 | Taiwan | 是 | 是 | 是 | 是 |
| TZ | 坦桑尼亚 | Tanzania | 是 | 是 | 是 | 是 |
| UA | 乌克兰 | Ukraine | 是 | 是 | 是 | 是 |
| UG | 乌干达 | Uganda | 是 | 是 | 是 | 是 |
| UM | 美国本土外小岛屿 | U.S. Outlying Islands | 是 | — | 是 | 是 |
| US | 美国 | United States | 是 | 是 | 是 | 是 |
| UY | 乌拉圭 | Uruguay | 是 | 是 | 是 | 是 |
| UZ | 乌兹别克斯坦 | Uzbekistan | 是 | 是 | 是 | 是 |
| VA | 梵蒂冈 | Vatican City | 是 | 是 | 是 | 是 |
| VC | 圣文森特和格林纳丁斯 | St. Vincent & Grenadines | 是 | — | 是 | 是 |
| VE | 委内瑞拉 | Venezuela | 是 | 是 | 是 | 是 |
| VG | 英属维尔京群岛 | British Virgin Islands | 是 | 是 | 是 | 是 |
| VI | 美属维尔京群岛 | U.S. Virgin Islands | 是 | 是 | 是 | 是 |
| VN | 越南 | Vietnam | 是 | 是 | 是 | 是 |
| VU | 瓦努阿图 | Vanuatu | 是 | 是 | 是 | 是 |
| WF | 瓦利斯和富图纳 | Wallis & Futuna | 是 | 是 | 是 | 是 |
| WS | 萨摩亚 | Samoa | 是 | 是 | 是 | 是 |
| XK | 科索沃 | Kosovo | 是 | — | 是 | 是 |
| YE | 也门 | Yemen | 是 | 是 | 是 | 是 |
| YT | 马约特 | Mayotte | 是 | 是 | 是 | — |
| ZA | 南非 | South Africa | 是 | 是 | 是 | 是 |
| ZM | 赞比亚 | Zambia | 是 | 是 | 是 | 是 |
| ZW | 津巴布韦 | Zimbabwe | 是 | 是 | 是 | 是 |
