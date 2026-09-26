#!/usr/bin/env python3
"""端到端审核:按 README 配方真实转换并用 mihomo 内核校验,证明"导入不报错"。

在 e2e-compose 网络内运行(python:3.12-slim + pyyaml)。步骤:
1. 向 Sub-Store 种入测试订阅与聚合(用后即删,不碰真实数据);
2. 对每个入口 INI 按 README 转换请求结构调用 SubConverter;
3. 校验输出:组数与 INI 声明一致、无悬空引用。订阅地址不带
   platform/target;转换请求使用 Clash for Windows 的 UA,provider
   按这个 UA 返回 Clash YAML,mihomo -t 通过。
"""

import gzip
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import yaml

CONVERTER = os.environ.get('E2E_CONVERTER', 'http://subconverter:25500')
SUBSTORE_BASE = os.environ.get('E2E_SUBSTORE', 'http://sub-store:3001/e2e-ci')
SUB_NAME = 'ci-seed-sub'
COL_NAME = 'ci-seed-col'
# 生产写法:通用订阅,不带 platform/target。转换器 target=clash,
# 由 Clash for Windows 自己拉取;它的 UA 含 clash,Sub-Store 因此返回 Clash YAML。
CONVERT_REQUEST_UA = 'ClashforWindows/0.20.39'
# 网页转换器会把这个参数写进链接,后端不读。带上是为了确认它不会改格式。
DIY_UA_PARAM = 'diyua=ShadowRocket'
# 只探测和 target=clash 一致的客户端。mihomo、空 UA、原样 ShadowRocket
# 会拿到 base64,那不是这条链路的生产请求方。
PROBE_UAS = [
    'ClashforWindows/0.20.39',
    'clash',
]
BUILTIN = {'DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE', 'GLOBAL', 'no-resolve'}
TEST_NODES = (
    'vless://e0fe7670-0aba-42d1-8959-9ba1892bb13d@hk.example.com:443?security=tls'
    '&type=ws&host=hk.example.com&path=%2Fws#CI 香港 01\n'
    'trojan://ciping-pass@us.example.com:443?security=tls&sni=us.example.com#CI 美国 02\n'
)

errors = []


def fail(msg):
    errors.append(msg)
    print(f'FAIL: {msg}', flush=True)


def http(url, ua='ci-validator/1.0', method='GET', body=None, timeout=60):
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header('User-Agent', ua)
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def seed():
    sub = json.dumps({'name': SUB_NAME, 'source': 'local',
                      'content': TEST_NODES}).encode()
    col = json.dumps({'name': COL_NAME, 'subscriptions': [SUB_NAME]}).encode()
    http(f'{SUBSTORE_BASE}/api/subs', method='POST', body=sub)
    http(f'{SUBSTORE_BASE}/api/collections', method='POST', body=col)


def cleanup():
    for path in (f'/api/sub/{SUB_NAME}', f'/api/collection/{COL_NAME}'):
        try:
            http(f'{SUBSTORE_BASE}{path}', method='DELETE')
        except Exception:
            pass


def convert(ini_url):
    # 通用订阅,不附加 platform/target。
    sub_url = f'{SUBSTORE_BASE}/download/collection/{COL_NAME}'
    params = (
        'target=clash'
        f'&url={urllib.request.quote(sub_url, safe="")}'
        f'&config={urllib.request.quote(ini_url, safe="")}'
        '&insert=false&emoji=true&list=false&xudp=false&udp=false&tfo=false'
        '&expand=true&scv=false&fdn=false&new_name=true'
        f'&{DIY_UA_PARAM}'
    )
    status, data = http(f'{CONVERTER}/sub?{params}', timeout=180,
                        ua=CONVERT_REQUEST_UA)
    if status != 200:
        raise RuntimeError(f'conversion HTTP {status}: {data[:200]!r}')
    try:
        data.decode('utf-8', errors='strict')
    except UnicodeDecodeError as e:
        raise RuntimeError(f'输出含非法 UTF-8: {e}')
    cfg = yaml.safe_load(data)
    if not isinstance(cfg, dict):
        raise RuntimeError('输出不是 YAML 映射')
    return cfg


def ini_group_names(ini_text):
    names = []
    for line in ini_text.splitlines():
        m = re.match(r'^custom_proxy_group=([^`]+)`', line)
        if m:
            names.append(m.group(1).strip())
    return names


def check_groups(cfg, ini_names, label):
    groups = cfg.get('proxy-groups') or []
    defined = {g['name'] for g in groups if isinstance(g, dict) and g.get('name')}
    if len(defined) != len(ini_names):
        fail(f'{label}: INI 声明 {len(ini_names)} 个策略组,输出只有 {len(defined)} 个'
             ' —— 存在组被转换器静默丢弃(url-test 组缺测速 URL 字段时会被丢弃)')
        missing = [n for n in ini_names if n not in defined]
        for n in missing[:5]:
            fail(f'{label}: 被丢弃的组: {n}')
    providers = set((cfg.get('proxy-providers') or {}).keys())
    for g in groups:
        if not isinstance(g, dict):
            continue
        for member in g.get('proxies') or []:
            if member not in defined and member not in BUILTIN and member not in providers:
                fail(f'{label}: 组 [{g.get("name")}] 引用了未定义成员 [{member}]')
    for rule in cfg.get('rules') or []:
        target = str(rule).split(',')[-1].strip()
        if target and target not in defined and target not in BUILTIN:
            fail(f'{label}: 规则目标组未定义 [{rule}]')


def check_providers(cfg, label):
    providers = cfg.get('proxy-providers') or {}
    if not providers:
        fail(f'{label}: 输出缺少 proxy-providers(当前转换链路应生成)')
        return
    for name, p in providers.items():
        url = p.get('url', '')
        if 'platform=' in url or 'target=' in url:
            fail(f'{label}: provider [{name}] 不应携带格式参数,实际 URL 含 platform/target')
        injected = p.get('header', {}).get('User-Agent') if isinstance(p.get('header'), dict) else None
        injected_ua = ''
        if isinstance(injected, list) and injected:
            injected_ua = str(injected[0])
        elif injected:
            injected_ua = str(injected)
        if 'clash' not in injected_ua.lower():
            fail(f'{label}: provider [{name}] 的 header.User-Agent 不含 clash'
                 f'(实际为 {injected_ua or "空"}),Sub-Store 不会按 Clash 返回')
        # 内核若采用配置里的 header,就用这个 UA 拉;生产请求方是 Clash for Windows。
        probe_uas = list(PROBE_UAS)
        if injected_ua and injected_ua not in probe_uas:
            probe_uas.append(injected_ua)
        for ua in probe_uas:
            status, data = http(url, ua=ua)
            if status != 200:
                fail(f'{label}: provider [{name}] 以 UA [{ua}] 拉取返回 HTTP {status}')
                continue
            doc = yaml.safe_load(data)
            proxies = doc.get('proxies') if isinstance(doc, dict) else None
            if not isinstance(proxies, list) or not proxies:
                fail(f'{label}: provider [{name}] 以 UA [{ua}] 拉取的不是含 proxies 列表的'
                     ' Clash YAML —— 内核会报 cannot unmarshal !!str into provider.ProxySchema')
            else:
                for proxy in proxies:
                    if not isinstance(proxy, dict) or not proxy.get('name') \
                            or not proxy.get('type'):
                        fail(f'{label}: provider [{name}] UA [{ua}] 含无效节点条目')


def fetch_mihomo(workdir):
    provided = os.environ.get('E2E_MIHOMO_BIN')
    if provided:
        return provided
    status, data = http('https://api.github.com/repos/MetaCubeX/mihomo/releases/latest')
    tag = json.loads(data)['tag_name']  # e.g. v1.19.31
    asset = f'mihomo-linux-amd64-{tag}.gz'
    url = f'https://github.com/MetaCubeX/mihomo/releases/download/{tag}/{asset}'
    _, blob = http(url, timeout=300)
    binary = os.path.join(workdir, 'mihomo')
    with gzip.open(io.BytesIO(blob), 'rb') as gz, open(binary, 'wb') as out:
        out.write(gz.read())
    os.chmod(binary, 0o755)
    return binary


def check_mihomo(binary, cfg, label, workdir):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', label)
    cfg_path = os.path.join(workdir, f'{safe}.yaml')
    with open(cfg_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)
    home = os.path.join(workdir, f'{safe}-home')
    os.makedirs(home, exist_ok=True)
    result = subprocess.run(
        [binary, '-t', '-d', home, '-f', cfg_path],
        capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or 'test is successful' not in (result.stdout + result.stderr):
        tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
        fail(f'{label}: mihomo -t 未通过: {" | ".join(tail)}')


def main():
    ini_urls = [u for u in os.environ.get('E2E_INI_URLS', '').splitlines() if u.strip()]
    if not ini_urls:
        fail('E2E_INI_URLS 未提供入口 INI 地址')
        return finish()
    seed()
    try:
        with tempfile.TemporaryDirectory() as workdir:
            mihomo = fetch_mihomo(workdir)
            for ini_url in ini_urls:
                label = ini_url.rsplit('/', 1)[-1]
                try:
                    status, ini_data = http(ini_url)
                    ini_text = ini_data.decode('utf-8')
                except Exception as e:
                    fail(f'{label}: 拉取 INI 失败: {e}')
                    continue
                try:
                    cfg = convert(ini_url)
                except Exception as e:
                    fail(f'{label}: 转换失败: {e}')
                    continue
                check_groups(cfg, ini_group_names(ini_text), label)
                check_providers(cfg, label)
                check_mihomo(mihomo, cfg, label, workdir)
                print(f'checked: {label}', flush=True)
    finally:
        cleanup()
    finish()


def finish():
    if errors:
        print(f'\n共 {len(errors)} 个问题', flush=True)
        sys.exit(1)
    print('端到端审核通过:通用订阅、Clash for Windows UA 与 mihomo 加载全部正常。', flush=True)


if __name__ == '__main__':
    main()
