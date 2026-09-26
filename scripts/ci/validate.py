#!/usr/bin/env python3
"""转换审核。默认创建隔离 CI 数据；--live 只读检查真实转换链接。

不删除测试对象或文件，运行产物保留于工作区 temp/。日志不包含订阅
URL、响应正文、节点名称或内核原始输出。用法见同目录 README.md。
"""

import argparse
import copy
import gzip
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import yaml

CONVERTER = os.environ.get('E2E_CONVERTER', 'http://subconverter:25500')
SUBSTORE_BASE = os.environ.get('E2E_SUBSTORE', 'http://sub-store:3001/e2e-ci')
# 每次使用唯一名称，已有对象不覆盖、不删除。中文名称覆盖实际聚合路径。
RUN_ID = uuid.uuid4().hex[:12]
SUB_NAME = f'ci-seed-sub-{RUN_ID}'
COL_NAME = f'ci-聚合-{RUN_ID}'
# 生产写法:通用订阅,不带 platform/target。转换器 target=clash。
# 网页转换器会把 diyua 写进链接,后端不读。
DIY_UA_PARAM = 'diyua=ShadowRocket'
# 客户端下载转换链接时的 UA。mihomo 会把这个 UA 写进 provider header,
# 内核再拿它去拉订阅;不经网关时 Sub-Store 返回 base64。
CONVERT_REQUEST_UAS = [
    'mihomo/v1.19.13',
    'ClashforWindows/0.20.39',
]
# 同时覆盖已识别客户端，以及直连 Sub-Store 会落到 base64 的 UA。
PROBE_UAS = [
    'mihomo.party/v2.0.3 (clash.meta)',
    'ClashMetaForAndroid/2.11.32',
    'mihomo/v1.19.13',
    'Go-http-client/1.1',
    'ShadowRocket',
    'ClashforWindows/0.20.39',
    'clash',
]
DEFAULT_CORE_UA = 'clash.meta'
BUILTIN = {'DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE', 'GLOBAL', 'no-resolve'}
TEST_NODES = (
    'vless://e0fe7670-0aba-42d1-8959-9ba1892bb13d@hk.example.com:443?security=tls'
    '&type=ws&host=hk.example.com&path=%2Fws#CI 香港 01\n'
    'trojan://ciping-pass@us.example.com:443?security=tls&sni=us.example.com#CI 美国 02\n'
)

errors = []


class ValidationError(Exception):
    """只含可公开诊断信息；禁止附带 URL、正文或下游异常原文。"""


def fail(msg):
    errors.append(msg)
    print(f'FAIL: {msg}', flush=True)


def http(url, ua='ci-validator/1.0', method='GET', body=None, timeout=60,
         headers=None):
    # 转换器可能把已编码的中文聚合路径恢复为字面中文。urllib 不像浏览器
    # 自动处理 IRI；保留已有百分号转义及查询分隔符，避免二次编码 %E8 -> %25E8。
    parts = urllib.parse.urlsplit(url)
    safe_path = "/:@!$&'()*+,;=-._~%"
    safe_query = safe_path + '?[]'
    uri = urllib.parse.urlunsplit((parts.scheme, parts.netloc,
                                  urllib.parse.quote(parts.path, safe=safe_path),
                                  urllib.parse.quote(parts.query, safe=safe_query),
                                  urllib.parse.quote(parts.fragment, safe=safe_query)))
    req = urllib.request.Request(uri, method=method, data=body,
                                 headers=headers or {})
    req.add_header('User-Agent', ua)
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def request(url, **kwargs):
    try:
        status, data = http(url, **kwargs)
    except urllib.error.HTTPError as exc:
        raise ValidationError(f'HTTP {exc.code}') from None
    except Exception as exc:
        raise ValidationError(f'请求失败 ({type(exc).__name__})') from None
    if status != 200:
        raise ValidationError(f'HTTP {status}')
    return data


def yaml_document(data):
    try:
        text = data.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        raise ValidationError('响应不是有效 UTF-8') from None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        # PyYAML 的原始异常包含正文，不能直接输出。
        raise ValidationError('响应不是有效 YAML') from None


def seed():
    sub = json.dumps({'name': SUB_NAME, 'source': 'local',
                      'content': TEST_NODES}).encode()
    col = json.dumps({'name': COL_NAME, 'subscriptions': [SUB_NAME]}).encode()
    request(f'{SUBSTORE_BASE}/api/subs', method='POST', body=sub)
    request(f'{SUBSTORE_BASE}/api/collections', method='POST', body=col)


def convert(ini_url, request_ua):
    # 通用订阅,不附加 platform/target。
    sub_url = f'{SUBSTORE_BASE}/download/collection/{urllib.parse.quote(COL_NAME, safe="")}'
    params = (
        'target=clash'
        f'&url={urllib.parse.quote(sub_url, safe="")}'
        f'&config={urllib.parse.quote(ini_url, safe="")}'
        '&insert=false&emoji=true&list=false&xudp=false&udp=false&tfo=false'
        '&expand=true&scv=false&fdn=false&new_name=true'
        f'&{DIY_UA_PARAM}'
    )
    return load_conversion(f'{CONVERTER}/sub?{params}', request_ua)


def load_conversion(url, request_ua):
    cfg = yaml_document(request(url, timeout=180, ua=request_ua))
    if not isinstance(cfg, dict):
        raise ValidationError('转换输出不是 YAML 映射')
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
    if not isinstance(groups, list) or not groups:
        fail(f'{label}: 缺少有效 proxy-groups 列表')
        return
    defined = {g['name'] for g in groups if isinstance(g, dict)
               and isinstance(g.get('name'), str)}
    if len(defined) != len(groups):
        fail(f'{label}: 策略组名称缺失、重复或条目无效')
    if ini_names is not None and defined != set(ini_names):
        fail(f'{label}: 策略组与 INI 不一致 (声明 {len(ini_names)}，输出 {len(defined)})')
    providers = cfg.get('proxy-providers') or {}
    providers = set(providers) if isinstance(providers, dict) else set()
    inline = cfg.get('proxies') or []
    inline_names = {p['name'] for p in inline if isinstance(p, dict)
                    and isinstance(p.get('name'), str)} if isinstance(inline, list) else set()
    for index, g in enumerate(groups, 1):
        if not isinstance(g, dict):
            continue
        members = g.get('proxies') or []
        uses = g.get('use') or []
        if not isinstance(members, list) or not isinstance(uses, list):
            fail(f'{label}: 策略组 #{index} 的 proxies/use 不是列表')
            continue
        for member in members:
            if not isinstance(member, str) or member not in defined | BUILTIN | inline_names:
                fail(f'{label}: 策略组 #{index} 存在未定义节点/组引用')
        for provider in uses:
            if not isinstance(provider, str) or provider not in providers:
                fail(f'{label}: 策略组 #{index} 存在未定义 provider 引用')
    rules = cfg.get('rules') or []
    if not isinstance(rules, list) or not rules:
        fail(f'{label}: 缺少有效 rules 列表')
        return
    for index, rule in enumerate(rules, 1):
        parts = str(rule).split(',')
        target = parts[-2].strip() if parts[-1].strip() == 'no-resolve' and len(parts) > 1 else parts[-1].strip()
        if target and target not in defined | BUILTIN | inline_names:
            fail(f'{label}: 规则 #{index} 的目标未定义')


def check_providers(cfg, label):
    observed_names = {}
    providers = cfg.get('proxy-providers') or {}
    if not isinstance(providers, dict) or not providers:
        fail(f'{label}: 输出缺少 proxy-providers(当前转换链路应生成)')
        return observed_names
    for index, (provider_name, p) in enumerate(providers.items(), 1):
        name = f'#{index}'  # provider 名也可能含私人机场/节点名称。
        if not isinstance(p, dict):
            fail(f'{label}: provider [{name}] 不是映射')
            continue
        url = p.get('url', '')
        if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme not in {'http', 'https'}:
            fail(f'{label}: provider [{name}] 缺少有效 HTTP(S) URL')
            continue
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query, keep_blank_values=True)
        if 'platform' in query or 'target' in query:
            fail(f'{label}: provider [{name}] 不应携带格式参数,实际 URL 含 platform/target')
        headers = {}
        if isinstance(p.get('header'), dict):
            for key, value in p['header'].items():
                if isinstance(value, list):
                    value = value[0] if value else ''
                headers[str(key).lower()] = str(value)
        injected_ua = headers.pop('user-agent', '')
        expected_ua = injected_ua or DEFAULT_CORE_UA
        probe_uas = list(PROBE_UAS)
        if expected_ua not in probe_uas:
            probe_uas.append(expected_ua)
        for ua in probe_uas:
            # 未知 header 不输出，避免其中嵌有令牌等私人内容。
            ua_label = ua if ua in PROBE_UAS else 'provider-header'
            try:
                doc = yaml_document(request(url, ua=ua, headers=headers))
            except ValidationError as exc:
                fail(f'{label}: provider [{name}] UA [{ua_label}] {exc}')
                continue
            proxies = doc.get('proxies') if isinstance(doc, dict) else None
            if not isinstance(proxies, list) or not proxies:
                kind = 'YAML 标量字符串（可能为 base64 通用订阅）' if isinstance(doc, str) else '无效 provider schema'
                fail(f'{label}: provider [{name}] UA [{ua_label}] {kind}，不是含非空 proxies 列表的'
                     ' Clash YAML —— 内核会报 cannot unmarshal !!str into provider.ProxySchema')
            else:
                for proxy in proxies:
                    if not isinstance(proxy, dict) or not isinstance(proxy.get('name'), str) \
                            or not proxy['name'] or not isinstance(proxy.get('type'), str) or not proxy['type']:
                        fail(f'{label}: provider [{name}] UA [{ua_label}] 含无效节点条目')
                        break
                else:
                    # 预期必须对应本次配置实际下载所用 UA，不能把各客户端的
                    # 格式差异合成并集，也不能让仅装载部分节点蒙混通过。
                    if ua == expected_ua:
                        observed_names[provider_name] = {p['name'] for p in proxies}
    return observed_names


def fetch_mihomo(workdir):
    provided = os.environ.get('E2E_MIHOMO_BIN')
    if provided:
        return provided
    data = request('https://api.github.com/repos/MetaCubeX/mihomo/releases/latest')
    tag = json.loads(data)['tag_name']  # e.g. v1.19.31
    asset = f'mihomo-linux-amd64-{tag}.gz'
    url = f'https://github.com/MetaCubeX/mihomo/releases/download/{tag}/{asset}'
    blob = request(url, timeout=300)
    binary = os.path.join(workdir, 'mihomo')
    with gzip.open(io.BytesIO(blob), 'rb') as gz, open(binary, 'xb') as out:
        out.write(gz.read())
    os.chmod(binary, 0o755)
    return binary


def check_mihomo(binary, cfg, label, workdir):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', label)
    cfg_path = os.path.join(workdir, f'{safe}.yaml')
    with open(cfg_path, 'x', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)
    home = os.path.join(workdir, f'{safe}-home')
    os.makedirs(home, exist_ok=False)
    geoip = os.environ.get('E2E_GEOIP_FILE')
    if geoip:
        shutil.copy2(geoip, os.path.join(home, 'Country.mmdb'))
    result = subprocess.run(
        [binary, '-t', '-d', home, '-f', cfg_path],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    output = result.stdout + result.stderr
    if result.returncode != 0 or 'test is successful' not in output \
            or 'cannot unmarshal' in output or re.search(r'initial proxy provider .* error', output):
        fail(f'{label}: 内核 -t 未通过 (exit={result.returncode}，原始输出含私人配置故不打印)')
        return False
    return True


def runtime_config(cfg, controller_port, secret):
    """独立运行副本：禁止流量接管/对外监听，provider 缓存只写本次目录。"""
    runtime = copy.deepcopy(cfg)
    for port in ('port', 'socks-port', 'redir-port', 'tproxy-port', 'mixed-port'):
        runtime[port] = 0
    runtime.update({'allow-lan': False, 'bind-address': '127.0.0.1', 'listeners': [],
                    'tun': {'enable': False}, 'dns': {'enable': False},
                    'profile': {'store-selected': False, 'store-fake-ip': False},
                    'external-controller': f'127.0.0.1:{controller_port}', 'secret': secret})
    for key in ('external-controller-unix', 'external-controller-pipe',
                'external-controller-tls', 'external-ui', 'external-ui-url'):
        runtime.pop(key, None)
    for index, provider in enumerate((runtime.get('proxy-providers') or {}).values(), 1):
        if isinstance(provider, dict):
            provider['path'] = f'./provider-{index}.yaml'
            provider['health-check'] = {'enable': False}
    for group in runtime.get('proxy-groups') or []:
        if isinstance(group, dict) and group.get('type') in {'url-test', 'fallback', 'load-balance'}:
            group.update({'lazy': True, 'interval': 86400})
    return runtime


def runtime_providers_ready(document, expected_names):
    providers = document.get('providers') if isinstance(document, dict) else None
    if not isinstance(providers, dict) or not expected_names:
        return False
    for name, expected in expected_names.items():
        provider = providers.get(name)
        proxies = provider.get('proxies') if isinstance(provider, dict) else None
        if not isinstance(proxies, list):
            return False
        actual = {p.get('name') for p in proxies if isinstance(p, dict)
                  and isinstance(p.get('name'), str)}
        # 初始失败时某些内核只放 COMPATIBLE 占位节点，不能算加载成功。
        if not expected or not expected.issubset(actual):
            return False
    return True


def check_runtime(binary, cfg, label, workdir, expected_names):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', label)
    home = Path(workdir) / f'{safe}-runtime'
    home.mkdir(mode=0o700)
    geoip = os.environ.get('E2E_GEOIP_FILE')
    if geoip:
        shutil.copy2(geoip, home / 'Country.mmdb')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        controller_port = listener.getsockname()[1]
    secret = secrets.token_urlsafe(32)
    runtime = runtime_config(cfg, controller_port, secret)
    config_path = home / 'config.private.yaml'
    with config_path.open('x', encoding='utf-8') as out:
        yaml.safe_dump(runtime, out, allow_unicode=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request_info = urllib.request.Request(f'http://127.0.0.1:{controller_port}/providers/proxies',
                                         headers={'Authorization': f'Bearer {secret}'})
    process = None
    with (home / 'core.private.log').open('x', encoding='utf-8') as log:
        try:
            process = subprocess.Popen([binary, '-d', str(home), '-f', str(config_path)],
                                       stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    with opener.open(request_info, timeout=1) as response:
                        document = json.load(response)
                    if runtime_providers_ready(document, expected_names):
                        print(f'PASS: {label} 内核实际加载 {len(expected_names)} 个 provider', flush=True)
                        return True
                except Exception:
                    # 控制器尚未就绪或 provider 尚在下载，且下游异常可能带秘密。
                    pass
                time.sleep(0.25)
            fail(f'{label}: 内核运行时未在 30 秒内加载全部 provider（仅 -t 通过不足以证明成功）')
            return False
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def read_ini(url):
    try:
        text = request(url).decode('utf-8')
    except UnicodeDecodeError:
        raise ValidationError('INI 不是有效 UTF-8') from None
    names = ini_group_names(text)
    if not names:
        raise ValidationError('INI 不含 custom_proxy_group 声明')
    return names


def validate_case(cfg, ini_names, label, mihomo, workdir):
    before = len(errors)
    check_groups(cfg, ini_names, label)
    expected_names = check_providers(cfg, label)
    if mihomo:
        if check_mihomo(mihomo, cfg, label, workdir) and len(errors) == before:
            check_runtime(mihomo, cfg, label, workdir, expected_names)
    print(f'{"PASS" if len(errors) == before else "FAIL"}: {label}', flush=True)


def run_live(mihomo, workdir):
    url = os.environ.get('E2E_LIVE_URL', '').strip()
    if not url:
        raise ValidationError('--live 需要环境变量 E2E_LIVE_URL（完整转换链接）')
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in {'http', 'https'}:
        raise ValidationError('E2E_LIVE_URL 必须为 HTTP(S) 转换链接')
    ini_urls = urllib.parse.parse_qs(parts.query).get('config', [])
    ini_names = read_ini(ini_urls[0]) if ini_urls else None
    if ini_names is None:
        print('INFO: 转换链接没有 config 参数，仅检查输出结构与引用。', flush=True)
    # 实际转换服务可能按下载方 UA 改写 provider header；每个 UA 都重新转换。
    for index, ua in enumerate(PROBE_UAS, 1):
        label = f'live-{index} ua={ua}'
        try:
            cfg = load_conversion(url, ua)
            validate_case(cfg, ini_names, label, mihomo, workdir)
        except ValidationError as exc:
            fail(f'{label}: {exc}')
        except Exception as exc:
            fail(f'{label}: 校验失败 ({type(exc).__name__})')


def run_ci(mihomo, workdir):
    ini_urls = [u for u in os.environ.get('E2E_INI_URLS', '').splitlines() if u.strip()]
    if not ini_urls:
        raise ValidationError('E2E_INI_URLS 未提供入口 INI 地址')
    seed()
    for index, ini_url in enumerate(ini_urls, 1):
        label = f'ini-{index}'
        try:
            ini_names = read_ini(ini_url)
        except ValidationError as exc:
            fail(f'{label}: {exc}')
            continue
        for request_ua in CONVERT_REQUEST_UAS:
            case = f'{label} ua={request_ua}'
            try:
                cfg = convert(ini_url, request_ua)
                validate_case(cfg, ini_names, case, mihomo, workdir)
            except ValidationError as exc:
                fail(f'{case}: {exc}')
            except Exception as exc:
                fail(f'{case}: 校验失败 ({type(exc).__name__})')
    print('INFO: CI 测试对象保留在隔离 Sub-Store 中，不执行 DELETE。', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='只读检查 E2E_LIVE_URL 的生产链路')
    parser.add_argument('--mihomo', action='store_true', help='live 模式也运行内核 -t 和隔离 provider 加载；CI 默认运行')
    args = parser.parse_args(argv)
    workdir = None
    try:
        # mkdtemp 只创建目录，没有 TemporaryDirectory 的退出删除行为。
        workspace = Path(os.environ.get('E2E_WORK_ROOT', Path(__file__).resolve().parents[2]))
        temp_root = workspace / 'temp'
        temp_root.mkdir(parents=True, exist_ok=True)
        workdir = tempfile.mkdtemp(prefix='subscription-validation-', dir=temp_root)
        mihomo = fetch_mihomo(workdir) if not args.live or args.mihomo else None
        if args.live:
            run_live(mihomo, workdir)
        else:
            run_ci(mihomo, workdir)
    except ValidationError as exc:
        fail(str(exc))
    except Exception as exc:
        fail(f'审核运行失败 ({type(exc).__name__})')
    finally:
        if workdir:
            with open(Path(workdir) / 'summary.json', 'x', encoding='utf-8') as out:
                json.dump({'mode': 'live' if args.live else 'ci',
                           'success': not errors, 'error_count': len(errors),
                           'mihomo_requested': not args.live or args.mihomo}, out)
            print(f'INFO: 工件保留于 {workdir}', flush=True)
    finish()


def finish():
    if errors:
        print(f'\n共 {len(errors)} 个问题', flush=True)
        sys.exit(1)
    print('审核通过：转换结构、引用与 provider 多 UA 响应均有效。', flush=True)


if __name__ == '__main__':
    main()
