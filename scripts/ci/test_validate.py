"""Offline regressions: provider strings must fail without leaking subscription data."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
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
        'proxy-groups': [{'name': 'group', 'type': 'select', 'use': ['private-provider-name']}],
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
        opener.open.return_value.__enter__.return_value = io.BytesIO(
            b'{"providers":{"private-provider-name":{"proxies":[{"name":"private-node-name"}]}}}')
        with patch.dict(os.environ, {'E2E_GEOIP_FILE': ''}), \
                patch.object(validator.subprocess, 'Popen', return_value=process), \
                patch.object(validator.urllib.request, 'build_opener', return_value=opener):
            self.assertTrue(validator.check_runtime('mock-core', original, 'test', workdir,
                            {'private-provider-name': {'private-node-name'}}))
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assert_private_values_absent()


if __name__ == '__main__':
    unittest.main()
