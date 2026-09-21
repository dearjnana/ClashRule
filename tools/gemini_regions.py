"""由官方地区事实生成三个客户端共用的 Gemini 筛选组和中文对照表。"""
from pathlib import Path
import copy
import json
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
WEB_GROUP = '🎐 Gemini'
API_GROUP = '🧪 Gemini API'
PARTY_BEGIN = '# 自动生成的 Gemini 地区组开始；请维护 config/gemini-regions.json。'
PARTY_END = '# 自动生成的 Gemini 地区组结束。'


def load_regions():
    data = json.loads((ROOT / 'config/gemini-regions.json').read_text(encoding='utf-8'))
    codes = [item['code'] for item in data['regions']]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch('[A-Z]{2}', code) for code in codes)
    for item in data['regions']:
        assert item['aliases'] and len(item['aliases']) == len(set(item['aliases']))
        assert set(item['services']) <= {'web', 'android', 'assistant', 'api', 'workspace_web_only'}
    return data


def supported(item, name):
    wanted = {'api'} if name == API_GROUP else {'web', 'android', 'assistant'}
    return bool(wanted.intersection(item['services']))


def flag(code):
    return ''.join(chr(0x1F1E6 + ord(letter) - ord('A')) for letter in code)


def name_pattern(alias):
    if re.fullmatch('[A-Z]{2}', alias):
        return '(?<![A-Za-z])(?-i:' + alias + ')(?![A-Za-z])'
    escaped = re.escape(alias).replace(r'\ ', r'\s*')
    if re.search('[\u3400-\u9fff]', alias):
        return escaped
    # 英文名称要求词边界，避免 Iran 命中其他词等子串误识别。
    return '(?<![A-Za-z])' + escaped + '(?![A-Za-z])'


def region_filter(data, group_name):
    patterns = set()
    accepted_names = [alias.casefold() for item in data['regions'] if supported(item, group_name) for alias in item['aliases']]
    rejected = set()
    for item in data['regions']:
        if not supported(item, group_name):
            rejected.add(flag(item['code']))
            # 完整的不支持地区优先排除，避免属地名称中的挪威等母国词造成误匹配。
            for alias in item['aliases']:
                if not any(alias.casefold() in allowed for allowed in accepted_names):
                    rejected.add(name_pattern(alias))
            continue
        patterns.add(flag(item['code']))
        # 简写只接受大写独立标记，避免英文普通单词中的 in、at、no 被当成国家。
        patterns.add('(?<![A-Za-z])(?-i:' + item['code'] + ')(?![A-Za-z])')
        patterns.update(name_pattern(alias) for alias in item['aliases'])
    excluded = data['exclude_filter'].removeprefix('(?i)')
    region_exclusion = '(?!.*(?:' + '|'.join(sorted(rejected)) + '))' if rejected else ''
    return '(?i)^(?!.*' + excluded + ')' + region_exclusion + '(?=.*(?:' + '|'.join(sorted(patterns)) + ')).*$'


def gemini_groups(data=None):
    data = data or load_regions()
    return [{'name': name, 'type': 'select', 'include-all': True,
             'filter': region_filter(data, name), 'empty-fallback': 'REJECT'}
            for name in [WEB_GROUP, API_GROUP]]


def resolve_groups(groups):
    generated = {group['name']: group for group in gemini_groups()}
    assert set(generated) <= {g['name'] for g in groups}, '缺少 Gemini 服务组占位定义'
    return [copy.deepcopy(generated.get(g['name'], g)) for g in groups]


def render_party_groups():
    groups = yaml.safe_dump(gemini_groups(), allow_unicode=True, sort_keys=False, width=100000)
    return PARTY_BEGIN + '\n' + ''.join('  ' + line + '\n' for line in groups.splitlines()) + PARTY_END


def update_party_groups():
    path = ROOT / 'clients/clash-party/override.yaml'
    content = path.read_text(encoding='utf-8')
    assert content.count(PARTY_BEGIN) == content.count(PARTY_END) == 1
    start, end = content.index(PARTY_BEGIN), content.index(PARTY_END) + len(PARTY_END)
    path.write_text(content[:start] + render_party_groups() + content[end:], encoding='utf-8', newline='\n')


def write_region_doc():
    data = load_regions()
    counts = {key: sum(key in r['services'] for r in data['regions']) for key in ['web', 'android', 'assistant', 'api']}
    lines = [
        '# Gemini 官方地区与节点筛选', '',
        '本页由 `config/gemini-regions.json` 自动生成，核对日期：**' + data['checked_on'] + '**。', '',
        '地区事实来自 Google 官方，中文及常见英文名称参考 Unicode CLDR。只保留整理后的地区数据，不把网页快照入库。', '',
        '## 三个客户端的组定义', '',
        '- `🎐 Gemini`：Gemini 网页与 Android 服务组，包含网页、Play 商店或 Assistant 列出的全部普通账号地区，不限制机场。',
        '- `🧪 Gemini API`：AI Studio 与 Gemini API，按开发者服务的独立官方地区清单筛选，不限制机场。',
        '- 原有仅面向 MESL 美国的测试组已删除。两个新组都直接显示匹配节点，不需要美国或某家机场作为中间组。',
        '- 匹配国旗、地区中英文名称、常用城市别名和大写独立地区代码；无匹配节点时为 REJECT。', '',
        f'去重后记录：网页版 {counts["web"]} 个普通账号地区、Play 商店 {counts["android"]} 个地区、Assistant {counts["assistant"]} 个地区、API {counts["api"]} 个地区。', '',
        '网页和安卓并非每种使用方式都在所有地区开放。表中分别标出安装、Assistant 与 API 支持；Assistant 仍可能需要邀请。网页表中的中国大陆条目只面向 Workspace，未纳入普通账号筛选。', '',
        '**香港、澳门等地区在网页或 Android 清单中，但不在当前 API 清单中。** 因而开发者接口单独分流，避免用网页地区推断 API 可用性。', '',
        '[GeminiAPI.list](../rules/ai/GeminiAPI.list) 优先于 [Gemini.list](../rules/ai/Gemini.list)。后者保留已有 API 条件，兼容尚未更新整份配置的旧订阅；新配置通过前置规则区分策略。', '',
        '节点名称不证明真实出口，官方支持地区也不等于每个节点 IP、账号、套餐或功能都可用。地区名称缺失或只有模糊缩写时，先在自己的节点订阅补充真实地区信息；推荐使用国旗与完整地区名称。', '',
        '## 维护与自动构建', '',
        '在 GitHub 编辑 [地区源配置](../config/gemini-regions.json) 的地区、服务标记或别名，提交后 Actions 自动生成 OpenClash、Android 和 Clash Party 的筛选条件。日常构建离线使用已核对清单，不自动抓取上游网页。', '',
        'OpenClash / Android 的组占位定义在 `config/groups.yaml`；Clash Party 中只有标记包围的 Gemini 两个组由构建更新，其余覆写仍手动维护。不要直接修改生成的长正则。', '',
        '## 官方来源', '',
        '- [Gemini 网页版可用地区](' + data['sources']['web'] + ')',
        '- [Gemini Android 下载与 Assistant 可用地区](' + data['sources']['android'] + ')',
        '- [AI Studio / Gemini API 可用地区](' + data['sources']['api'] + ')',
        '- [Unicode CLDR 地区名称](' + data['sources']['names'] + ')', '',
        '## 完整地区对照', '',
        '| 代码 | 国家或地区 | 英文名称 | 网页版 | Play 商店 | Assistant | API |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for item in data['regions']:
        states = [('仅 Workspace' if key == 'web' and 'workspace_web_only' in item['services'] else '是' if key in item['services'] else '—') for key in counts]
        lines.append('| ' + ' | '.join([item['code'], item['name_zh'], item['name_en']] + states) + ' |')
    path = ROOT / 'docs/Gemini地区说明.md'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def validate_gemini_groups(groups):
    byname = {g['name']: g for g in groups}
    assert not any('Gemini' in name and 'MESL' in name for name in byname)
    data = load_regions()
    for group in gemini_groups(data):
        assert byname[group['name']] == group, group['name']
        pattern = re.compile(group['filter'])
        for item in data['regions']:
            is_allowed = supported(item, group['name'])
            for label in [flag(item['code']), item['code'], *item['aliases']]:
                actual = bool(pattern.search('[任意机场] ' + label + ' 01'))
                assert actual == is_allowed, (group['name'], item['code'], label, actual)
        for label in ['[OTHER]🇺🇸 美国 01', '[另一机场]JP-Tokyo-01', '[OTHER]🇦🇲 亚美尼亚', '[OTHER]Australia']:
            assert pattern.search(label), (group['name'], label)
        for label in ['[MESL]剩余流量 美国', '[OTHER]🇷🇺 Russia', '[OTHER]🇧🇾 Belarus', '[OTHER]🇮🇷 Iran', '[OTHER]🇰🇵 North Korea', '[OTHER]unknown relay', '[OTHER]in transit', '[OTHER]auto']:
            assert not pattern.search(label), (group['name'], label)
    return {name: sum(supported(r, name) for r in data['regions']) for name in [WEB_GROUP, API_GROUP]}
