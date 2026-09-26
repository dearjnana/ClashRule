"""Offline regressions: provider strings must fail without leaking subscription data."""

import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, mock_open, patch
import urllib.error

import yaml

spec = importlib.util.spec_from_file_location('validator', Path(__file__).with_name('validate.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

SECRET_URL = 'http://localhost/private-token/download/collection/test'
VALID_PROVIDER = b'proxies:\n- name: private-node-name\n  type: trojan\n'


def config():
    return {
        'proxy-providers': {'private-provider-name': {'type': 'http', 'url': SECRET_URL}},
        'proxy-groups': [
            {'name': 'group', 'type': 'select', 'use': ['private-provider-name']},
            {'name': '🎐 Gemini', 'type': 'url-test', 'use': ['private-provider-name'],
             'url': 'https://www.gstatic.com/generate_204', 'interval': 300},
        ],
        'rules': ['MATCH,group'],
    }


class ProviderValidationTests(unittest.TestCase):
    def setUp(self):
        validator.errors.clear()
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)

    def assert_private_values_absent(self):
        for value in ('private-token', 'private-node-name', 'private-provider-name', SECRET_URL):
            self.assertNotIn(value, self.output.getvalue())

    def test_base64_yaml_scalar_fails_every_ua(self):
        payload = b'dmxlc3M6Ly9wcml2YXRlLWNvbnRlbnQ='
        with patch.object(validator, 'http', return_value=(200, payload)):
            validator.check_providers(config(), 'case')
        self.assertEqual(len(validator.PROBE_UAS) + 1, len(validator.errors))
        self.assertIn('YAML 标量字符串', self.output.getvalue())
        self.assertIn('provider.ProxySchema', self.output.getvalue())
        self.assertNotIn(payload.decode(), self.output.getvalue())
        self.assert_private_values_absent()

    def test_http_encodes_chinese_provider_path_once(self):
        base = 'http://localhost/private-token/download/collection/'
        encoded = '%E8%81%9A%E5%90%88'
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = VALID_PROVIDER
        with patch.object(validator.urllib.request, 'urlopen', return_value=response) as client:
            validator.http(base + '聚合?existing=%E8%81%9A&name=聚合&keep=a+b')
            self.assertEqual(base + encoded + '?existing=%E8%81%9A&name=' + encoded + '&keep=a+b',
                             client.call_args.args[0].full_url)
            validator.http(base + encoded)
            self.assertEqual(base + encoded, client.call_args.args[0].full_url)

    def test_valid_provider_passes_all_required_clients(self):
        with patch.object(validator, 'http', return_value=(200, VALID_PROVIDER)) as client:
            validator.check_providers(config(), 'case')
        self.assertFalse(validator.errors)
        seen = {call.kwargs['ua'] for call in client.call_args_list}
        self.assertTrue({'ClashforWindows/0.20.39', 'Go-http-client/1.1',
                         'mihomo/v1.19.13', 'ShadowRocket'} <= seen)
        # Windows 默认代码页不能决定内核 UTF-8 输出的解码方式。
        def core_result(*args, **kwargs):
            self.assertEqual('utf-8', kwargs['encoding'])
            self.assertEqual('replace', kwargs['errors'])
            output = '中文策略组 test is successful'.encode('utf-8') + b'\xff'
            decoded = output.decode(kwargs['encoding'], errors=kwargs['errors'])
            return validator.subprocess.CompletedProcess(args=[], returncode=0,
                                                         stdout=decoded, stderr='')

        with patch.dict(os.environ, {'E2E_GEOIP_FILE': ''}), \
                patch.object(validator.os, 'makedirs'), \
                patch('builtins.open', mock_open()), \
                patch.object(validator.subprocess, 'run', side_effect=core_result):
            validator.check_mihomo('core', config(), 'case', 'unused-mocked-workdir')
        self.assertFalse(validator.errors)
        self.assert_private_values_absent()

    def test_empty_or_invalid_schema_fails(self):
        for payload in (b'proxies: []', b'proxies: string', b'proxies: [string]',
                        b'proxies: [{name: node}]', b'[]'):
            with self.subTest(payload=payload):
                validator.errors.clear()
                with patch.object(validator, 'http', return_value=(200, payload)):
                    validator.check_providers(config(), 'case')
                self.assertTrue(validator.errors)

    def test_yaml_error_does_not_echo_document(self):
        with patch.object(validator, 'http', return_value=(200, b'private-token: [broken')):
            validator.check_providers(config(), 'case')
        self.assertIn('响应不是有效 YAML', self.output.getvalue())
        self.assert_private_values_absent()

    def test_http_failure_does_not_echo_url_or_body(self):
        failure = urllib.error.HTTPError(SECRET_URL, 403, 'private-token', {}, None)
        with patch.object(validator, 'http', side_effect=failure):
            validator.check_providers(config(), 'case')
        self.assertEqual(len(validator.PROBE_UAS) + 1, len(validator.errors))
        self.assertIn('HTTP 403', self.output.getvalue())
        self.assert_private_values_absent()

    def test_seed_accepts_created_but_get_stays_strict(self):
        with patch.object(validator, 'http', return_value=(201, b'{"status":"success"}')) as client:
            validator.seed()
            self.assertEqual(2, client.call_count)
            self.assertTrue(all(call.kwargs['method'] == 'POST' for call in client.call_args_list))
            with self.assertRaisesRegex(validator.ValidationError, '^HTTP 201$'):
                validator.request(SECRET_URL)

    def test_release_token_is_used_only_for_fixed_metadata_api(self):
        metadata_url = 'https://api.github.com/repos/MetaCubeX/mihomo/releases/latest'
        archive = validator.gzip.compress(b'fixture executable')

        def fake_http(url, **kwargs):
            if url == metadata_url:
                self.assertEqual({'Authorization': 'Bearer test-action-token'}, kwargs['headers'])
                self.assertFalse(kwargs['allow_redirects'])
                return 200, b'{"tag_name":"v1.19.31"}'
            self.assertFalse(kwargs.get('headers'))
            return 200, archive if url.startswith('https://github.com/MetaCubeX/mihomo/') else VALID_PROVIDER

        with patch.dict(os.environ, {'E2E_MIHOMO_BIN': '', 'E2E_GITHUB_TOKEN': 'test-action-token'}), \
                patch.object(validator, 'http', side_effect=fake_http) as client, \
                patch('builtins.open', mock_open()), patch.object(validator.os, 'chmod'):
            validator.fetch_mihomo('unused-mocked-workdir')
            validator.request(SECRET_URL)
        self.assertEqual(3, client.call_count)
        self.assertEqual(metadata_url, client.call_args_list[0].args[0])
        self.assertEqual('https://github.com/MetaCubeX/mihomo/releases/download/v1.19.31/'
                         'mihomo-linux-amd64-v1.19.31.gz', client.call_args_list[1].args[0])
        self.assertNotIn('test-action-token', self.output.getvalue())
        self.assert_private_values_absent()

    def test_provided_core_skips_metadata_api_and_token(self):
        with patch.dict(os.environ, {'E2E_MIHOMO_BIN': 'provided-core',
                                     'E2E_GITHUB_TOKEN': 'test-action-token'}), \
                patch.object(validator, 'request') as client:
            self.assertEqual('provided-core', validator.fetch_mihomo('unused'))
        client.assert_not_called()

    def test_release_and_seed_errors_have_safe_stage_labels(self):
        failure = urllib.error.HTTPError(SECRET_URL, 403, 'test-action-token', {}, None)
        stages = [
            ([failure], '查询 mihomo 官方版本失败'),
            ([(200, b'{"tag_name":"v1.19.31"}'), failure], '下载 mihomo 二进制失败'),
        ]
        for responses, stage in stages:
            with self.subTest(stage=stage), \
                    patch.dict(os.environ, {'E2E_MIHOMO_BIN': '', 'E2E_GITHUB_TOKEN': 'test-action-token'}), \
                    patch.object(validator, 'http', side_effect=responses):
                with self.assertRaises(validator.ValidationError) as caught:
                    validator.fetch_mihomo('unused')
                self.assertEqual(f'{stage}：HTTP 403', str(caught.exception))
                self.assertNotIn('test-action-token', str(caught.exception))
                self.assertNotIn(SECRET_URL, str(caught.exception))
        with patch.object(validator, 'http', side_effect=failure):
            with self.assertRaisesRegex(validator.ValidationError, '^创建 CI 测试数据失败：HTTP 403$'):
                validator.seed()

    def test_metadata_redirect_is_rejected_without_forwarding_token(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append((self.path, self.headers.get('Authorization')))
                if self.path == '/release':
                    self.send_response(302)
                    self.send_header('Location', f'http://localhost:{self.server.server_port}/target')
                else:
                    self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaisesRegex(validator.ValidationError, '^HTTP 302$'):
                validator.request(f'http://127.0.0.1:{server.server_port}/release',
                                  headers={'Authorization': 'Bearer test-action-token'},
                                  allow_redirects=False)
            self.assertEqual([('/release', 'Bearer test-action-token')], observed)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertNotIn('test-action-token', self.output.getvalue())

    def test_configured_header_is_probed_but_not_printed(self):
        cfg = config()
        cfg['proxy-providers']['private-provider-name']['header'] = {
            'user-agent': ['private-token'], 'Authorization': ['Bearer private-token'],
        }
        with patch.object(validator, 'http', return_value=(200, b'base64-string')) as client:
            validator.check_providers(cfg, 'case')
        self.assertEqual(len(validator.PROBE_UAS) + 1, client.call_count)
        self.assertEqual('private-token', client.call_args.kwargs['ua'])
        self.assertEqual('Bearer private-token', client.call_args.kwargs['headers']['authorization'])
        self.assertIn('provider-header', self.output.getvalue())
        self.assert_private_values_absent()

    def test_same_group_count_different_names_fails(self):
        validator.check_groups(config(), ['different-group'], 'case')
        self.assertTrue(validator.errors)

    def test_single_visible_gemini_auto_group_passes(self):
        cfg = config()
        validator.check_groups(cfg, ['group', '🎐 Gemini'], 'case')
        self.assertFalse(validator.errors)

    def test_repository_gemini_filters_accept_prefixed_supported_regions(self):
        root = Path(__file__).resolve().parents[2]
        filters = {}
        for filename in ('openclash.ini', 'android.ini'):
            groups = [line.split('`') for line in (root / filename).read_text(encoding='utf-8').splitlines()
                      if line.startswith('custom_proxy_group=') and 'Gemini' in line.split('`')[0]]
            self.assertEqual(['custom_proxy_group=🎐 Gemini'], [fields[0] for fields in groups])
            self.assertEqual('url-test', groups[0][1])
            filters[filename] = groups[0][2]
        party = yaml.safe_load((root / 'clash-party.yaml').read_text(encoding='utf-8'))
        groups = party.get('proxy-groups') or party.get('proxy-groups!') or []
        gemini = [group for group in groups if 'Gemini' in group.get('name', '')]
        self.assertEqual(['🎐 Gemini'], [group['name'] for group in gemini])
        self.assertEqual('url-test', gemini[0]['type'])
        self.assertFalse(gemini[0].get('hidden', False))
        filters['clash-party.yaml'] = gemini[0]['filter']
        fixtures = [
            ('CI 机场 🇺🇸 美国 01', True), ('CI 机场 🇬🇧 英国 02', True),
            ('CI 机场 🇭🇰 香港 01', False), ('CI 机场 🇺🇸 美国 到期', False),
            # CI 本身也是国家代码，额外使用无国家别名的前缀覆盖错误的起始锚定。
            ('示例机场前缀 🇺🇸 美国 01', True), ('示例机场前缀 🇬🇧 英国 02', True),
        ]
        for filename, expression in filters.items():
            pattern = re.compile(expression)
            for node_name, expected in fixtures:
                with self.subTest(file=filename, synthetic_node=node_name):
                    self.assertEqual(expected, bool(pattern.search(node_name)))

    def test_gemini_contract_rejects_old_groups_manual_hidden_or_nested_groups(self):
        for mutation in ('missing', 'old-api', 'old-subgroup', 'manual', 'hidden', 'nested'):
            with self.subTest(mutation=mutation):
                validator.errors.clear()
                cfg = config()
                group = cfg['proxy-groups'][1]
                if mutation == 'missing':
                    cfg['proxy-groups'] = cfg['proxy-groups'][:1]
                elif mutation in {'old-api', 'old-subgroup'}:
                    cfg['proxy-groups'].append({'name': '🧪 Gemini API' if mutation == 'old-api'
                                               else '♻️ Gemini 美国', 'type': 'url-test'})
                elif mutation == 'manual':
                    group['type'] = 'select'
                elif mutation == 'hidden':
                    group['hidden'] = True
                else:
                    group['proxies'] = ['group']
                validator.check_groups(cfg, None, 'case')
                self.assertTrue(validator.errors)
        self.assert_private_values_absent()

    def test_live_mode_is_get_only_and_never_seeds(self):
        live_url = 'http://localhost/sub?target=clash&url=private-token'
        cfg_bytes = yaml.safe_dump(config()).encode()

        def fake_http(url, **kwargs):
            self.assertEqual('GET', kwargs.get('method', 'GET'))
            return 200, VALID_PROVIDER if url == SECRET_URL else cfg_bytes

        with patch.dict(os.environ, {'E2E_LIVE_URL': live_url}), \
                patch.object(validator, 'seed') as seed, \
                patch.object(validator, 'http', side_effect=fake_http) as client:
            validator.run_live(None, 'unused-without-mihomo')
        seed.assert_not_called()
        self.assertFalse(validator.errors)
        self.assertEqual(len(validator.PROBE_UAS) * (len(validator.PROBE_UAS) + 2), client.call_count)
        self.assert_private_values_absent()

    def test_runtime_requires_real_nodes_not_placeholder(self):
        expected = {'provider': {'real-node'}}
        self.assertFalse(validator.runtime_providers_ready(
            {'providers': {'provider': {'proxies': [{'name': 'COMPATIBLE'}]}}}, expected))
        self.assertFalse(validator.runtime_providers_ready({'providers': {}}, expected))
        self.assertTrue(validator.runtime_providers_ready(
            {'providers': {'provider': {'proxies': [{'name': 'real-node'}]}}}, expected))

    def test_runtime_rejects_239_of_669_nodes(self):
        expected = {'provider': {f'node-{index}' for index in range(669)}}
        partial = {'providers': {'provider': {'proxies': [{'name': f'node-{index}'} for index in range(239)]}}}
        complete = {'providers': {'provider': {'proxies': [{'name': f'node-{index}'} for index in range(669)]}}}
        self.assertFalse(validator.runtime_providers_ready(partial, expected))
        self.assertTrue(validator.runtime_providers_ready(complete, expected))

    def test_runtime_gemini_requires_real_candidates_not_reject_or_other_groups(self):
        expected = {'private-provider-name': {'private-node-name'}}
        cfg = config()
        for candidates, ready in [(['private-node-name'], True), (['REJECT'], False),
                                  (['COMPATIBLE'], False), (['group'], False),
                                  ([], False), (['unknown-node'], False)]:
            with self.subTest(candidates=candidates):
                document = {'proxies': {'🎐 Gemini': {'type': 'URLTest', 'all': candidates}}}
                self.assertEqual(ready, validator.runtime_gemini_ready(document, expected, cfg))
        for invalid in ({}, {'type': 'Selector', 'all': ['private-node-name']},
                        {'type': 'URLTest', 'hidden': True, 'all': ['private-node-name']}):
            self.assertFalse(validator.runtime_gemini_ready({'proxies': {'🎐 Gemini': invalid}},
                                                           expected, cfg))
        self.assert_private_values_absent()

    def test_expected_names_follow_actual_provider_ua(self):
        cfg = config()
        cfg['proxy-providers']['private-provider-name']['header'] = {'User-Agent': ['mihomo/v1.19.13']}

        def fake_http(url, **kwargs):
            names = ['meta-node', 'vless-node'] if kwargs['ua'] in {'mihomo/v1.19.13', validator.DEFAULT_CORE_UA} else ['other-client-node']
            return 200, yaml.safe_dump({'proxies': [{'name': name, 'type': 'vless'} for name in names]}).encode()

        with patch.object(validator, 'http', side_effect=fake_http):
            observed = validator.check_providers(cfg, 'case')
            self.assertEqual({'meta-node', 'vless-node'}, observed['private-provider-name'])
            cfg['proxy-providers']['private-provider-name'].pop('header')
            observed = validator.check_providers(cfg, 'case')
            self.assertEqual({'meta-node', 'vless-node'}, observed['private-provider-name'])
        self.assertFalse(validator.errors)

    def test_runtime_fails_when_provider_loads_but_gemini_has_only_reject(self):
        test_root = Path(__file__).resolve().parents[2] / 'temp'
        test_root.mkdir(exist_ok=True)
        workdir = tempfile.mkdtemp(prefix='validator-empty-gemini-test-', dir=test_root)
        process = MagicMock()
        process.poll.return_value = None
        opener = MagicMock()
        opener.open.side_effect = [
            io.BytesIO(b'{"providers":{"private-provider-name":{"proxies":[{"name":"private-node-name"}]}}}'),
            io.BytesIO(validator.json.dumps({'proxies': {'🎐 Gemini': {
                'type': 'URLTest', 'all': ['REJECT']}}}).encode()),
        ]
        with patch.dict(os.environ, {'E2E_GEOIP_FILE': ''}), \
                patch.object(validator.subprocess, 'Popen', return_value=process), \
                patch.object(validator.urllib.request, 'build_opener', return_value=opener), \
                patch.object(validator.time, 'monotonic', side_effect=[0, 0, 31]), \
                patch.object(validator.time, 'sleep'):
            self.assertFalse(validator.check_runtime('mock-core', config(), 'test', workdir,
                             {'private-provider-name': {'private-node-name'}}))
        self.assertTrue(validator.errors)
        self.assertIn('真实候选节点', self.output.getvalue())
        process.terminate.assert_called_once()
        self.assert_private_values_absent()

    def test_runtime_is_isolated_and_terminates_only_its_process(self):
        original = config()
        original.update({'mixed-port': 7890, 'tun': {'enable': True},
                         'dns': {'enable': True}, 'external-controller-unix': '/original/socket'})
        isolated = validator.runtime_config(original, 12345, 'test-secret')
        self.assertEqual(7890, original['mixed-port'])
        self.assertTrue(original['tun']['enable'])
        self.assertEqual(0, isolated['mixed-port'])
        self.assertFalse(isolated['tun']['enable'])
        self.assertFalse(isolated['dns']['enable'])
        self.assertEqual('127.0.0.1:12345', isolated['external-controller'])
        self.assertNotIn('external-controller-unix', isolated)
        self.assertEqual(SECRET_URL, isolated['proxy-providers']['private-provider-name']['url'])
        test_root = Path(__file__).resolve().parents[2] / 'temp'
        test_root.mkdir(exist_ok=True)
        workdir = tempfile.mkdtemp(prefix='validator-runtime-test-', dir=test_root)
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [validator.subprocess.TimeoutExpired('mock-core', 5), 0]
        opener = MagicMock()

        def controller_response(request, **kwargs):
            if request.full_url.endswith('/providers/proxies'):
                data = {'providers': {'private-provider-name': {'proxies': [{'name': 'private-node-name'}]}}}
            else:
                self.assertTrue(request.full_url.endswith('/proxies'))
                data = {'proxies': {'🎐 Gemini': {'type': 'URLTest', 'all': ['private-node-name']}}}
            return io.BytesIO(validator.json.dumps(data).encode())

        opener.open.side_effect = controller_response
        with patch.dict(os.environ, {'E2E_GEOIP_FILE': ''}), \
                patch.object(validator.subprocess, 'Popen', return_value=process), \
                patch.object(validator.urllib.request, 'build_opener', return_value=opener):
            self.assertTrue(validator.check_runtime('mock-core', original, 'test', workdir,
                            {'private-provider-name': {'private-node-name'}}))
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(2, opener.open.call_count)
        self.assert_private_values_absent()


if __name__ == '__main__':
    unittest.main()
