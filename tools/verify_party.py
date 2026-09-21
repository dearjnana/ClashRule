"""验证 Clash Party 覆写；可选启动隔离 Mihomo，检查真实规则集、分组和分流。

用法：python tools/verify_party.py --mihomo 内核可执行文件
测试仅使用回环监听、合成节点和本地响应，不接管系统代理、DNS 或 TUN。
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlsplit, unquote
from urllib.request import Request, build_opener, ProxyHandler
import argparse
import copy
import hashlib
import ipaddress
import json
import re
import socket
import socketserver
import subprocess
import threading
import time

import yaml
from gemini_regions import API_GROUP, WEB_GROUP, flag, load_regions, supported, validate_gemini_groups

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/'
FILE = ROOT / 'clients/clash-party/override.yaml'
RUN = ROOT / '.test-work/party'
CREATE_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
OPENER = build_opener(ProxyHandler({}))
NODES = [
    '[MESL]🇺🇸 美国 01', '[MESL]🇺🇸 美国 02', '[OTHER]🇺🇸 美国 01',
    '[MESL]🇦🇲 亚美尼亚 01', '[MESL]🇦🇺 Australia', '[MESL]🇷🇺 Russia',
    '[MESL]🇺🇦 Ukraine', '[MESL]🇨🇾 Cyprus', '[MESL] South America',
    '[MESL]剩余流量 美国', '[MESL]🇭🇰 香港 01', '[MESL]🇹🇼 台湾 01',
    '[MESL]🇯🇵 日本 01', '[MESL]🇸🇬 新加坡 01', '[OTHER] network relay',
    '[OTHER] JapanTest JP-01', '[良心云]🇭🇰 香港 01',
]
REGIONS = load_regions()['regions']
REGION_NODES = {'[地区测试]' + flag(item['code']) + ' 01': item for item in REGIONS}
NODES += list(REGION_NODES)


def load_override():
    return yaml.safe_load(FILE.read_text(encoding='utf-8'))


def validate_override(config):
    """检查客户端专用语法、引用完整性及已修复问题的回归约束。"""
    forbidden = {'proxies', 'proxy-providers', 'tun', 'port', 'socks-port', 'mixed-port',
                 'redir-port', 'tproxy-port', 'allow-lan', 'external-controller', 'secret',
                 'external-ui', 'external-ui-url'}
    assert not forbidden.intersection(config), '覆写不应接管节点凭据、设备端口或 TUN'
    assert {'dns!', 'sniffer!', 'rule-providers!'} <= config.keys()
    groups = config['proxy-groups']
    byname = {g['name']: g for g in groups}
    assert len(byname) == len(groups), '策略组重名'
    names = set(byname) | {'DIRECT', 'REJECT'}
    for g in groups:
        assert set(g.get('proxies', [])) <= names, g['name']
        if g.get('include-all'):
            assert g.get('empty-fallback') == 'REJECT', g['name']
        if 'filter' in g:
            re.compile(g['filter'])
        if 'url' in g:
            assert g['interval'] >= 600 and g['expected-status'] == '204', g['name']
    visiting, visited = set(), set()

    def visit(name):
        assert name not in visiting, '策略组循环引用：' + name
        if name in visited or name not in byname:
            return
        visiting.add(name)
        for child in byname[name].get('proxies', []):
            visit(child)
        visiting.remove(name)
        visited.add(name)

    for name in byname:
        visit(name)
    providers = config['rule-providers!']
    paths, urls, referenced = set(), set(), set()
    for name, provider in providers.items():
        assert provider['type'] == 'http' and provider['proxy'] in names, name
        path = provider['path']
        assert path.startswith('./rule_provider/clashrule-party/') and '..' not in path[2:], path
        assert path not in paths and provider['url'] not in urls, '规则缓存或下载地址重复'
        paths.add(path)
        urls.add(provider['url'])
        assert provider['interval'] >= 3600 and not urlsplit(provider['url']).query
        if provider['format'] == 'mrs':
            assert provider['behavior'] in {'domain', 'ipcidr'}
            assert provider['url'].endswith('.mrs')
        else:
            assert provider['format'] == 'text' and provider['behavior'] == 'classical', name
            assert provider['url'].startswith(BASE + 'rules/'), name
            assert (ROOT / provider['url'].removeprefix(BASE)).is_file(), name
    rules = config['rules']
    assert len(set(rules)) == len(rules)
    assert rules[-1] == 'MATCH,🐟 漏网之鱼'
    assert sum(r.startswith('MATCH,') for r in rules) == 1
    for rule in rules:
        parts = rule.split(',')
        assert parts[1 if parts[0] == 'MATCH' else 2] in names, rule
        if parts[0] == 'RULE-SET':
            assert parts[1] in providers, rule
            referenced.add(parts[1])
            if providers[parts[1]]['behavior'] == 'ipcidr':
                assert parts[-1] == 'no-resolve', rule
        if parts[0] in {'IP-CIDR', 'IP-CIDR6'}:
            ipaddress.ip_network(parts[1])
    for early, late in [
        ('Adobe_direct', 'Adobe_reject'), ('pixiv', 'BanAD'), ('Gemini', 'Google'),
        ('Gemini', 'ai'), ('GoogleFCM', 'Google'), ('YouTube', 'Google'),
        ('YouTube', 'google_domain'), ('GCD', 'ai'), ('SteamCN', 'Games4_domain'),
    ]:
        position = lambda name: next(i for i, rule in enumerate(rules) if rule.startswith('RULE-SET,' + name + ','))
        assert position(early) < position(late), (early, late)
    assert not any(r.startswith('DST-PORT,9090,') for r in rules)
    dns = config['dns!']
    assert dns['listen'].startswith('127.0.0.1:')
    assert dns['proxy-server-nameserver'] and dns['respect-rules']
    for key in dns['nameserver-policy']:
        assert key.startswith('rule-set:')
        for name in key.removeprefix('rule-set:').split(','):
            assert providers[name]['behavior'] == 'domain'
            referenced.add(name)
    for value in dns['fake-ip-filter']:
        if value.startswith('rule-set:'):
            name = value.removeprefix('rule-set:')
            assert providers[name]['behavior'] == 'domain'
            referenced.add(name)
    assert referenced == set(providers), '存在未使用的规则集'
    validate_gemini_groups(groups)
    assert rules.index('RULE-SET,GeminiAPI,🧪 Gemini API') < rules.index('RULE-SET,Gemini,🎐 Gemini')
    return {'groups': len(groups), 'providers': len(providers), 'rules': len(rules)}


def merge_fixture(base, override):
    """应用此文件用到的对象替换和数组覆盖，合并语义已与官方第二版源码核对。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key.endswith('!'):
            result[key[:-1]] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_fixture(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def fetch_bytes(url, timeout=25):
    with OPENER.open(url, timeout=timeout) as response:
        return response.read()


def prepare_payloads(config):
    """仓库规则取本次工作树，上游二进制规则实际下载并交给内核解析。"""
    download_dir = RUN / 'downloaded'
    download_dir.mkdir(parents=True, exist_ok=True)

    def fetch(item):
        name, provider = item
        url = provider['url']
        if url.startswith(BASE):
            data = (ROOT / url.removeprefix(BASE)).read_bytes()
            origin = '本次仓库工作树'
        else:
            for attempt in range(3):
                try:
                    data = fetch_bytes(url)
                    break
                except Exception:
                    if attempt == 2:
                        raise
            # 上游规则使用压缩容器，内容格式最终由 Mihomo 加载结果校验。
            assert not data.lstrip().startswith((b'<', b'{')), (name, '上游返回错误页面')
            origin = '上游实际下载'
        assert data
        (download_dir / (name + '.' + provider['format'])).write_bytes(data)
        return name, data, {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'origin': origin}

    payloads, report = {}, {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, data, metadata in pool.map(fetch, config['rule-providers!'].items()):
            payloads[name] = data
            report[name] = metadata
    return payloads, report


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class FixtureServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class FixtureProxy(socketserver.StreamRequestHandler):
    """只返回测试数据的 HTTP 代理，不转发到任何实际网站。"""
    def handle(self):
        self.connection.settimeout(10)
        try:
            first = self.rfile.readline().decode('latin1').strip()
            if not first:
                return
            while self.rfile.readline().strip():
                pass
            if first.startswith('CONNECT '):
                self.wfile.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                self.wfile.flush()
                first = self.rfile.readline().decode('latin1').strip()
                while first and self.rfile.readline().strip():
                    pass
            if first.startswith('GET '):
                name = unquote(urlsplit(first.split()[1]).path).lstrip('/')
                payload = self.server.payloads.get(name)
                if payload is not None:
                    self.server.downloads.add(name)
                    self.wfile.write(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(payload)).encode() + b'\r\nConnection: close\r\n\r\n' + payload)
                else:
                    self.wfile.write(b'HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n')
                self.wfile.flush()
        except (OSError, ValueError):
            pass


def api(port, path, data=None):
    request = Request(f'http://127.0.0.1:{port}' + path)
    if data is not None:
        request.data = json.dumps(data).encode()
        request.method = 'PUT'
        request.add_header('Content-Type', 'application/json')
    with OPENER.open(request, timeout=3) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def wait_for(port, process, predicate, timeout=25):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError('测试内核提前退出：' + str(process.returncode))
        try:
            result = predicate()
            if result:
                return result
        except (OSError, ValueError):
            pass
        time.sleep(.1)
    raise TimeoutError('等待测试内核就绪超时：' + str(port))


def dump(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False), encoding='utf-8', newline='\n')


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_tests(core, override, payloads):
    server = FixtureServer(('127.0.0.1', 0), FixtureProxy)
    server.payloads, server.downloads = payloads, set()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    proxy_port = server.server_address[1]
    outcomes = {}
    try:
        for scenario in ['节点列表', '节点集合', '缺少MESL', '没有可用地区']:
            home = RUN / {'节点列表': 'nodes', '节点集合': 'provider', '缺少MESL': 'no-mesl', '没有可用地区': 'no-region'}[scenario]
            names = NODES if scenario != '缺少MESL' else [n for n in NODES if '[MESL]' not in n]
            if scenario == '没有可用地区':
                names = ['[OTHER]🇷🇺 Russia', '[OTHER]🇨🇳 中国大陆', '[OTHER]unknown relay']
            nodes = [{'name': name, 'type': 'http', 'server': '127.0.0.1', 'port': proxy_port} for name in names]
            base = {'proxies': nodes, 'proxy-providers': {}, 'proxy-groups': [{'name': '旧策略', 'type': 'select', 'proxies': ['DIRECT']}],
                    'rules': ['MATCH,DIRECT'], 'dns': {'fallback': ['127.0.0.1'], 'nameserver-policy': {'rule-set:旧规则': '127.0.0.1'}},
                    'rule-providers': {'旧规则': {'type': 'file', 'path': './must-not-load.txt', 'behavior': 'domain'}},
                    'sniffer': {'skip-dst-address': ['203.0.113.1/32']}, 'profile': {'unrelated': True},
                    'mixed-port': 0, 'socks-port': 0, 'port': 0, 'allow-lan': False, 'tun': {'enable': False},
                    'external-controller': '', 'secret': 'fixture-only'}
            if scenario == '节点集合':
                dump(home / 'synthetic-nodes.yaml', {'proxies': nodes})
                base['proxies'] = []
                base['proxy-providers'] = {'测试订阅': {'type': 'file', 'path': './synthetic-nodes.yaml', 'health-check': {'enable': False}}}
            config = merge_fixture(base, override)
            assert config['proxies'] == base['proxies'] and config['proxy-providers'] == base['proxy-providers']
            assert config['tun'] == base['tun'] and config['secret'] == base['secret']
            assert config['profile']['unrelated']
            assert '旧规则' not in config['rule-providers'] and 'fallback' not in config['dns']
            assert not any(key.endswith('!') for key in config)
            for name, provider in config['rule-providers'].items():
                cache = home / provider['path']
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(payloads[name])
            # 保留正式 DNS、嗅探和策略组字段进行语法验证，不打开任何端口或 TUN。
            candidate = home / 'merged.yaml'
            dump(candidate, config)
            checked = subprocess.run([str(core), '-t', '-d', str(home), '-f', str(candidate)], capture_output=True,
                                     text=True, encoding='utf-8', errors='replace', timeout=90, creationflags=CREATE_FLAGS)
            (home / 'syntax.log').write_text(checked.stdout + checked.stderr, encoding='utf-8')
            assert checked.returncode == 0, checked.stdout + checked.stderr
            assert 'level=error' not in checked.stdout + checked.stderr, '语法检查包含内核错误日志'
            # 实际运行仅使用回环代理和控制器；关闭 DNS 监听、探测及进程识别，不读取真实设备状态。
            controller, listener = free_port(), free_port()
            config.update({'external-controller': f'127.0.0.1:{controller}', 'secret': '', 'mixed-port': listener,
                           'bind-address': '127.0.0.1', 'dns': {'enable': False}, 'sniffer': {'enable': False},
                           'find-process-mode': 'off', 'log-level': 'info', 'profile': {'store-selected': False, 'store-fake-ip': False}})
            for group in config['proxy-groups']:
                if 'url' in group:
                    group.update({'url': 'http://rules.fixture.invalid/health', 'interval': 0, 'lazy': True})
            if scenario == '节点列表':
                # 用全新缓存路径验证首启下载；请求仍经过正式配置的规则下载组，由本地代理返回真实规则数据。
                for name, provider in config['rule-providers'].items():
                    provider['url'] = 'http://rules.fixture.invalid/' + quote(name)
                    provider['path'] = './cold-rules/' + str(time.time_ns()) + '-' + name + '.' + provider['format']
            else:
                for provider in config['rule-providers'].values():
                    provider['type'] = 'file'
                    for key in ['url', 'proxy', 'interval']:
                        provider.pop(key, None)
            runtime = home / 'runtime.yaml'
            dump(runtime, config)
            with (home / 'runtime.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen([str(core), '-d', str(home), '-f', str(runtime)], stdout=log,
                                           stderr=subprocess.STDOUT, creationflags=CREATE_FLAGS)
                try:
                    wait_for(controller, process, lambda: api(controller, '/version'))
                    counts = wait_for(controller, process, lambda: provider_counts(controller, len(payloads)))
                    gemini_members = {}
                    for group_name in [WEB_GROUP, API_GROUP]:
                        group = api(controller, '/proxies/' + quote(group_name, safe=''))
                        base_allowed = {n for i,n in enumerate(NODES[:17]) if i not in {5,8,9,14}}
                        if group_name == API_GROUP:
                            base_allowed.discard('[MESL]🇭🇰 香港 01')
                            base_allowed.discard('[良心云]🇭🇰 香港 01')
                        expected = {n for n,item in REGION_NODES.items() if supported(item, group_name)} | base_allowed
                        expected &= set(names)
                        assert set(group['all']) == (expected or {'REJECT'}), (group_name, set(group['all']) ^ expected)
                        gemini_members[group_name] = len(expected)
                    korean = api(controller, '/proxies/' + quote('🇰🇷 韩国节点', safe=''))['all']
                    assert not any('Ukraine' in n for n in korean)
                    assert api(controller, '/proxies/' + quote('⚡🇰🇷 MESL-韩国', safe=''))['all'] == ['REJECT']
                    all_nodes = api(controller, '/proxies/' + quote('🌐 全部节点', safe=''))['all']
                    assert not any('剩余流量' in n for n in all_nodes)
                    outcomes[scenario] = {'syntax': 'PASS', 'providers': counts, 'gemini_members': gemini_members, 'all_official_regions_checked': True, 'korea_false_match_excluded': True}
                    if scenario == '节点列表':
                        assert server.downloads == set(payloads), sorted(set(payloads) - server.downloads)
                        outcomes[scenario]['cold_downloads'] = len(server.downloads)
                        outcomes[scenario]['routes'] = route_tests(controller, listener, proxy_port)
                    print(scenario, '通过', flush=True)
                finally:
                    stop(process)
    finally:
        server.shutdown()
        server.server_close()
    return outcomes


def provider_counts(controller, expected):
    providers = api(controller, '/providers/rules')['providers']
    if len(providers) != expected or not all(p['ruleCount'] > 0 for p in providers.values()):
        return None
    return {name: provider['ruleCount'] for name, provider in providers.items()}


def route_tests(controller, listener, fixture_port):
    """经实际代理入口建立连接，通过控制器确认规则命中；测试代理不会访问目标网站。"""
    for group, member in [('🚀 节点选择', '🌐 全部节点'), ('🌐 全部节点', NODES[0]),
                          ('🎯 全球直连', '🚀 节点选择'), ('🚫 广告拦截', '🚀 节点选择'),
                          ('🛸 IP归属地伪装', '🚀 节点选择')]:
        api(controller, '/proxies/' + quote(group, safe=''), {'name': member})
    cases = [
        ('gemini.google.com', 443, 'RuleSet', 'Gemini', '🎐 Gemini'),
        ('robinfrontend-pa.googleapis.com', 443, 'RuleSet', 'Gemini', '🎐 Gemini'),
        ('generativelanguage.googleapis.com', 443, 'RuleSet', 'GeminiAPI', '🧪 Gemini API'),
        ('aistudio.google.com', 443, 'RuleSet', 'GeminiAPI', '🧪 Gemini API'),
        ('mtalk.google.com', 443, 'RuleSet', 'GoogleFCM', '📢 谷歌FCM'),
        ('music.youtube.com', 443, 'RuleSet', 'YouTube', '📹 YouTube'),
        ('youtubei.googleapis.com', 443, 'RuleSet', 'YouTube', '📹 YouTube'),
        ('lcs-cops.adobe.io', 443, 'RuleSet', 'Adobe_direct', '🎯 全球直连'),
        ('ic.adobe.io', 443, 'RuleSet', 'Adobe_reject', '🚫 广告拦截'),
        ('ads-pixiv.net', 443, 'RuleSet', 'pixiv', '🔞 18X'),
        ('githubcopilot.com', 443, 'RuleSet', 'GCD', '🖥️ GitHub-Cloudflare-Docker'),
        ('cdn.steamcontent.com', 443, 'RuleSet', 'SteamCN', '🎯 全球直连'),
        ('www.google.com', 443, 'RuleSet', 'Google', '🍀 Google'),
        ('www.baidu.com', 443, 'RuleSet', 'IPweizhuang', '🛸 IP归属地伪装'),
        ('www.tsinghua.edu.cn', 443, 'RuleSet', 'cn_domain', '🎯 全球直连'),
        ('clashrule-route-check-20260921.com', 9090, 'Match', '', '🐟 漏网之鱼'),
        ('127.0.0.1', fixture_port, 'IPCIDR', '127.0.0.0/8', 'DIRECT'),
    ]
    results = []
    for host, port, rule_type, payload, group in cases:
        with socket.create_connection(('127.0.0.1', listener), timeout=5) as connection:
            source_port = str(connection.getsockname()[1])
            connection.sendall(f'CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n'.encode())
            response = connection.recv(4096)
            assert b'200' in response.split(b'\r\n', 1)[0], (host, response)
            until = time.monotonic() + 4
            item = None
            while time.monotonic() < until:
                entries = api(controller, '/connections')['connections'] or []
                item = next((c for c in entries if str(c['metadata'].get('sourcePort')) == source_port), None)
                if item:
                    break
                time.sleep(.05)
            assert item, ('缺少测试连接记录', host)
            assert item['rule'] == rule_type and item['rulePayload'] == payload, (host, item)
            assert group in item['chains'], (host, item['chains'])
            results.append({'host': host, 'rule': rule_type, 'provider': payload, 'group': group})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mihomo', type=Path)
    args = parser.parse_args()
    config = load_override()
    summary = {'structure': validate_override(config)}
    print('覆写结构检查通过', summary['structure'], flush=True)
    if args.mihomo:
        RUN.mkdir(parents=True, exist_ok=True)
        payloads, downloads = prepare_payloads(config)
        summary['downloads'] = downloads
        print('已读取全部规则集', len(payloads), flush=True)
        summary['runtime'] = run_tests(args.mihomo.resolve(), config, payloads)
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    (reports / 'party-validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Clash Party 验证通过', flush=True)


if __name__ == '__main__':
    main()
