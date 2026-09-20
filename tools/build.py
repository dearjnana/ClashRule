"""从规则源和配置源离线构建订阅入口，不依赖原始快照，也不访问设备。"""
from pathlib import Path
from collections import defaultdict
import argparse, copy, ipaddress, json
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/'
HEALTH = 'https://cp.cloudflare.com/generate_204'

def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')

def rules(path):
    return [s.strip() for s in read(path).splitlines() if s.strip() and not s.lstrip().startswith('#')]

def write(path, content):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n', encoding='utf-8', newline='\n')

def generated(path):
    return 'generated/' + path

def optimize(entries):
    """仅删除被同一策略较早条件覆盖的规则，保持跨策略顺序和解析选项。"""
    exact, suffix, keywords, nets = defaultdict(set), defaultdict(set), defaultdict(list), defaultdict(set)
    result = {}
    for entry in entries:
        if 'path' not in entry:
            continue
        policy, kept = entry['target'], []
        for rule in rules(entry['path']):
            a = rule.split(',')
            covered = rule in exact[policy]
            if a[0] in ('DOMAIN', 'DOMAIN-SUFFIX'):
                labels = a[1].split('.')
                covered |= any('.'.join(labels[k:]) in suffix[policy] for k in range(len(labels)))
                covered |= any(word in a[1] for word in keywords[policy])
            elif a[0] in ('IP-CIDR', 'IP-CIDR6'):
                net, options = ipaddress.ip_network(a[1]), tuple(a[2:])
                covered |= any((net.supernet(new_prefix=n), options) in nets[policy] for n in range(net.prefixlen + 1))
            if covered:
                continue
            kept.append(rule)
            exact[policy].add(rule)
            if a[0] == 'DOMAIN-SUFFIX':
                suffix[policy].add(a[1])
            elif a[0] == 'DOMAIN-KEYWORD':
                keywords[policy].append(a[1])
            elif a[0] in ('IP-CIDR', 'IP-CIDR6'):
                nets[policy].add((ipaddress.ip_network(a[1]), tuple(a[2:])))
        result[entry['path']] = kept
    return result

def with_policy(rule, policy):
    a = rule.split(',')
    return ','.join(a + [policy]) if a[0] == 'MATCH' else ','.join(a[:2] + [policy] + a[2:])

def build_index(entries):
    """根据当前规则源生成文件索引，避免网页修改后数量过期。"""
    active = {e['path'] for e in entries if 'path' in e}
    directories = [
        ('rules/', '唯一维护的规则源，按服务分类'),
        ('config/', '规则顺序、策略组、基础设置和来源地址'),
        ('generated/rules/', '按主配置顺序去重后的生成规则'),
        ('providers/', '原生域名和 IP 规则集合'),
        ('profiles/', 'OpenClash、Android 和完全展开配置'),
        ('templates/', '生成的基础模板'),
        ('clients/', 'Clash Party 等客户端覆写'),
        ('scripts/', 'Sub-Store 节点脚本'),
        ('deploy/', '容器部署示例和配置说明'),
        ('tools/', '构建、检查和转换后整理工具'),
        ('.github/workflows/', 'GitHub 自动构建与发布流程'),
        ('docs/、licenses/', '中文说明和来源许可'),
    ]
    lines = ['# 仓库文件索引', '', '本页由构建工具自动更新，请修改规则源后等待自动构建。', '',
             '| 目录 | 用途 |', '|---|---|']
    lines += ['| `' + path + '` | ' + purpose + ' |' for path, purpose in directories]
    lines += ['', '## 规则清单', '', '| 文件 | 有效条件数 | 主配置使用 |', '|---|---:|---|']
    for path in sorted((ROOT / 'rules').rglob('*.list'), key=lambda p: p.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        lines.append(f'| [{relative}](../{relative}) | {len(rules(relative))} | '
                     + ('是' if relative in active else '独立或可选') + ' |')
    write('docs/仓库文件索引.md', '\n'.join(lines))

def build(base=BASE):
    base = base.rstrip('/') + '/'
    entries = json.loads(read('config/routing.json'))
    groups = yaml.safe_load(read('config/groups.yaml'))
    files = optimize(entries)
    # 删除不再被主配置引用的生成列表，防止规则改名后残留旧输出。
    expected = {ROOT / generated(path) for path in files}
    for path in (ROOT / 'generated/rules').rglob('*.list'):
        if path not in expected:
            path.unlink()
    for path, items in files.items():
        write(generated(path), '# 自动生成，请修改 ' + path + ' 后等待自动构建。\n'
              '# 本文件的去重依赖主配置顺序，不宜单独移植。\n' + '\n'.join(items))
    china_paths = ['rules/network/ChinaIp.list', 'rules/network/ChinaCompanyIp.list']
    china = list(ipaddress.collapse_addresses([ipaddress.ip_network(s.split(',')[1]) for p in china_paths for s in files[p]]))
    gfw_path = 'rules/network/ProxyGFWlist.list'
    if any(not s.startswith('DOMAIN-SUFFIX,') for s in files[gfw_path]):
        raise ValueError('ProxyGFWlist 仅维护域名后缀，正则等补充条件请放入 ProxyLite.list')
    gfw = [s.split(',')[1] for s in files[gfw_path]]
    write('providers/ChinaIP.txt', '\n'.join(map(str, china)))
    write('providers/ProxyGFW.txt', '\n'.join('+.' + s for s in gfw))
    template = yaml.safe_load(read('config/base.yaml'))
    template['x-clashrule-native-groups'] = groups
    template['rule-providers'] = {
        'ChinaIP': {'type': 'http', 'behavior': 'ipcidr', 'format': 'text', 'url': base + 'providers/ChinaIP.txt', 'path': './rule_provider/local-ChinaIP.txt', 'interval': 86400},
        'ProxyGFW': {'type': 'http', 'behavior': 'domain', 'format': 'text', 'url': base + 'providers/ProxyGFW.txt', 'path': './rule_provider/local-ProxyGFW.txt', 'interval': 86400},
    }
    for expanded in (False, True):
        value = copy.deepcopy(template)
        if expanded:
            value.pop('rule-providers')
        name = 'templates/' + ('expanded' if expanded else 'openclash') + '.yaml'
        write(name, '# 自动生成；转换后执行 tools/finalize.py 恢复原生策略组。\n' + yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110))

    def make_ini(expanded=False):
        lines = ['[custom]', '; 自动生成，请维护 config/ 和 rules/ 后等待自动构建。',
                 '; 使用 expand=true 转换，再执行 tools/finalize.py，方可导入客户端。',
                 '; 原生策略组保存在基础模板的 x-clashrule-native-groups 字段中。', '']
        emitted_china = False
        for e in entries:
            path = e.get('path')
            if path and not files[path]:
                continue
            if 'inline' in e:
                ref = '[]' + e['inline']
            elif not expanded and path in china_paths:
                if emitted_china:
                    continue
                ref, emitted_china = '[]RULE-SET,ChinaIP,no-resolve', True
            elif not expanded and path == gfw_path:
                ref = '[]RULE-SET,ProxyGFW'
            else:
                ref = base + generated(path)
            lines.append('ruleset=' + e['target'] + ',' + ref)
        lines += ['', '; 转换器兼容策略组；转换后整理为原生组。']
        for group in groups:
            parts = [group['name'], group['type']] + ['[]' + p for p in group.get('proxies', [])]
            if 'filter' in group:
                parts += [group['filter'], '[]REJECT']
            if group['type'] in ('url-test', 'fallback'):
                parts += [HEALTH, '300,5,150']
            lines.append('custom_proxy_group=' + '`'.join(parts))
        lines += ['', 'clash_rule_base=' + base + 'templates/' + ('expanded' if expanded else 'openclash') + '.yaml',
                  'enable_rule_generator=true', 'overwrite_original_rules=true']
        return '\n'.join(lines)

    for expanded, name in ((False, 'openclash'), (True, 'expanded')):
        write('profiles/' + name + '.ini', make_ini(expanded))
    # 手机与路由器共用分流规则，仅基础设置和健康检查周期不同。
    android = copy.deepcopy(template)
    android.update(yaml.safe_load(read('config/android.yaml')))
    android.pop('socks-port', None)
    for group in android['x-clashrule-native-groups']:
        if 'interval' in group:
            group['interval'] = 900
    write('templates/android.yaml', '# 手机基础模板；VPN 接管由 Android 应用负责。\n'
          + yaml.safe_dump(android, allow_unicode=True, sort_keys=False, width=110))
    write('profiles/android.ini', make_ini().replace('templates/openclash.yaml', 'templates/android.yaml'))
    flattened = [with_policy(r, e['target']) for e in entries for r in ([e['inline']] if 'inline' in e else files[e['path']])]
    write('reports/rules-expanded.txt', '\n'.join(flattened))
    summary = {'source_rule_files': len(list((ROOT / 'rules').rglob('*.list'))), 'expanded_rules': len(flattened), 'groups': len(groups),
               'china_provider_prefixes': len(china), 'gfw_provider_domains': len(gfw),
               'main_rules': len(flattened) - sum(len(files[p]) for p in china_paths) - len(gfw) + 2, 'base_url': base}
    write('reports/build.json', json.dumps(summary, ensure_ascii=False, indent=2))
    build_index(entries)
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=BASE)
    print(json.dumps(build(parser.parse_args().base_url), ensure_ascii=False, indent=2))
