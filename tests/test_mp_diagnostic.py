"""Safe response-shape inspection and the explicit native transport boundary."""

import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from validation.http import ProbeError, WechatHTTP
from validation.mp_source import profile_shape, scan_profile, diagnose_profile, diagnose_profiles
from test_validation import LocalTest


class NativeTransportTests(unittest.TestCase):
    def test_list_matches_reference_headers_without_article_cookie(self):
        from test_http_route import credential
        from urllib.parse import parse_qs, urlsplit
        url, headers = WechatHTTP.api_request('list', {'offset': 0, 'count': 10}, credential())
        self.assertEqual(urlsplit(url).path, '/mp/profile_ext')
        self.assertEqual(parse_qs(urlsplit(url).query)['scene'], ['124'])
        self.assertEqual(headers['Origin'], 'https://mp.weixin.qq.com')
        self.assertEqual(headers['Accept-Encoding'], 'identity')
        self.assertEqual(headers['Accept'], '*/*')
        self.assertTrue(headers['User-Agent'].endswith('WAE/1.0'))
        self.assertNotIn('Cookie', headers)
        _, comments = WechatHTTP.api_request('comments', {}, credential())
        self.assertIn('Cookie', comments)
    def test_python_tls_verification_retained_without_environment_keylogging(self):
        with patch.dict('os.environ', {'SSLKEYLOGFILE': '/private/keylog'}):
            client = WechatHTTP()
        contexts = [handler._context for handler in client.opener.handlers if hasattr(handler, '_context')]
        self.assertEqual(len(contexts), 1)
        self.assertTrue(contexts[0].check_hostname)
        self.assertIsNone(contexts[0].keylog_filename)

    def call(self, stdout=b'body\n200', returncode=0, **kwargs):
        with patch('validation.http.subprocess.run', return_value=SimpleNamespace(
                stdout=stdout, returncode=returncode)) as run:
            value = WechatHTTP(transport='curl').read(
                'https://mp.weixin.qq.com/s?key=private-key', {'Cookie': 'appmsg_token="private-token"'}, **kwargs)
        return value, run

    def test_secret_only_stdin_and_no_user_config_proxy_redirect_retry_or_keylog(self):
        with patch.dict('os.environ', {'SSLKEYLOGFILE': '/private/keylog', 'HTTPS_PROXY': 'https://untrusted.test',
                                     'CURL_CA_BUNDLE': '/untrusted.pem'}):
            value, run = self.call()
        self.assertEqual(value, b'body')
        args, options = run.call_args
        command = args[0]
        self.assertEqual(command[:2], ['/usr/bin/curl', '--disable'])
        self.assertNotIn('private-', repr(command))
        self.assertIn(b'key=private-key', options['input'])
        self.assertIn(b'\\"private-token\\"', options['input'])
        self.assertEqual(command[command.index('--config') + 1], '-')
        self.assertEqual(command[command.index('--noproxy') + 1], '*')
        self.assertIn('--no-location', command)
        self.assertIn('--no-insecure', command)
        self.assertNotIn('--retry', command)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)
        for key in ('SSLKEYLOGFILE', 'HTTPS_PROXY', 'CURL_CA_BUNDLE'):
            self.assertNotIn(key, options['env'])

    def test_header_injection_and_cdn_cookie_rejected_before_subprocess(self):
        with patch('validation.http.subprocess.run') as run:
            for cookie in ('safe\noutput="leak"', 'safe\rkey=bad', 'x\x00'):
                with self.assertRaisesRegex(ProbeError, 'invalid_request_headers'):
                    WechatHTTP('curl').read('https://mp.weixin.qq.com/', {'Cookie': cookie})
            with self.assertRaisesRegex(ProbeError, 'credential_target_not_allowed'):
                WechatHTTP('curl').read('https://mmbiz.qpic.cn/x', {'Cookie': 'private-token'})
            run.assert_not_called()

    def test_redirect_status_truncation_limit_tls_and_timeout_fail_closed(self):
        cases = [(b'body\n302', 0, 'redirect_blocked'), (b'body\n403', 0, 'http_rejected'),
                 (b'body', 0, 'curl_status_missing'), (b'x' * 20 + b'\n200', 0, 'response_size_limit'),
                 (b'private-key', 63, 'response_size_limit'), (b'private-key', 60, 'tls_verification_failed'),
                 (b'private-key', 6, 'curl_transport_failed')]
        for body, code, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ProbeError, reason):
                self.call(body, code, limit=10)
        with patch('validation.http.subprocess.run', side_effect=subprocess.TimeoutExpired('private-key', 25)):
            with self.assertRaisesRegex(ProbeError, '^curl_transport_failed$'):
                WechatHTTP('curl').read('https://mp.weixin.qq.com/')


class ProfileDiagnosticTests(unittest.TestCase):
    def test_malformed_nested_article_keeps_prior_page_and_records_shape(self):
        valid = {'ret': 0, 'general_msg_list': {'list': []}, 'can_msg_continue': 1, 'next_offset': 10}
        for details in ([], {'multi_app_msg_item_list': 'private-token'},
                        {'content_url': ['private-key']}, {'content_url': 'https://mp.weixin.qq.com/s/x', 'title': {}}):
            bad = {'ret': 0, 'general_msg_list': {'list': [
                {'comm_msg_info': {'datetime': 1792159200}, 'app_msg_ext_info': details}]},
                   'can_msg_continue': 0, 'next_offset': 20}
            pages = [valid, bad]
            result = scan_profile(lambda *_: pages.pop(0), '猫笔刀', 'FIXTURE')
            self.assertEqual(result['reason'], 'source_shape_changed')
            self.assertEqual(result['pages'][0]['cursor'], '0')
            self.assertFalse(result['coverage_complete'])
            self.assertIn('shape', result['pages'][1])
            self.assertNotIn('private-', json.dumps(result))

    def test_unknown_fields_strings_tokens_and_article_content_are_never_emitted(self):
        payload = {'ret': 0, 'general_msg_list': json.dumps({'list': [
            {'comm_msg_info': {'datetime': 'private-key'},
             'app_msg_ext_info': {'title': 'private-reader', 'content_url': 'https://x/?key=private-key'}}]}),
                   'can_msg_continue': 'private-token', 'private-field': 'private-pass',
                   'base_resp': {'ret': 0, 'errmsg': 'private-token'}}
        shape = profile_shape(payload)
        self.assertNotIn('private-', json.dumps(shape))
        self.assertEqual(shape['group_count'], 1)
        self.assertEqual(shape['fields']['can_msg_continue']['type'], 'str')
        self.assertEqual(shape['base_response_code'], 0)

    def test_failed_parser_retains_structure_without_promoting_coverage(self):
        payload = {'ret': 0, 'general_msg_list': '{}', 'can_msg_continue': 0}
        result = scan_profile(lambda *_: payload, '猫笔刀', 'FIXTURE_BIZ')
        self.assertEqual(result['reason'], 'source_shape_changed')
        self.assertFalse(result['coverage_complete'])
        self.assertFalse(result['pages'][0]['shape']['fields']['next_offset']['present'])
        self.assertEqual(result['pages'][0]['shape']['groups_type'], 'NoneType')

    def test_invalid_listing_json_and_non_dictionary_are_diagnostic_only(self):
        shape = profile_shape({'ret': 0, 'general_msg_list': 'not-json-private-token'})
        self.assertFalse(shape['listing_json_valid'])
        self.assertNotIn('private-', json.dumps(shape))
        self.assertEqual(profile_shape([])['payload_type'], 'list')


class DiagnosticExecutionTests(LocalTest):
    def test_missing_credential_makes_zero_requests(self):
        with patch('validation.mp_source.new_run', return_value=self.path), patch(
                'validation.mp_source.load_credentials', side_effect=ProbeError('credentials_missing')), patch(
                'validation.mp_source.WechatHTTP') as client:
            result = diagnose_profile('stormzhang', 'curl')
        client.assert_not_called()
        self.assertEqual(result['requests_attempted'], 0)
        self.assertEqual(result['reason'], 'credentials_missing')

    def test_business_refusal_one_request_no_response_string_or_authentication_claim(self):
        with patch('validation.mp_source.new_run', return_value=self.path), patch(
                'validation.mp_source.load_credentials', return_value={'biz': 'FIXTURE'}), patch(
                'validation.mp_source.WechatHTTP') as client:
            client.return_value.api.return_value = {'ret': -3, 'errmsg': 'private-key'}
            result = diagnose_profile('stormzhang', 'curl')
        self.assertEqual(client.return_value.api.call_count, 1)
        self.assertEqual(result['error_code'], -3)
        self.assertFalse(result['authentication_verified'])
        self.assertNotIn('private-', (self.path / 'diagnostic.json').read_text())

    def test_pair_is_paced_does_not_repeat_or_change_system(self):
        def diagnostic(account, transport):
            return {'account': account, 'status': 'not_verified', 'requests_attempted': 1}
        with patch('validation.mp_source.new_run', return_value=self.path), patch(
                'validation.mp_source.diagnose_profile', side_effect=diagnostic) as run, patch(
                'validation.mp_source.time.sleep') as sleep:
            result = diagnose_profiles('curl')
        self.assertEqual([row.args for row in run.call_args_list], [('猫笔刀', 'curl'), ('stormzhang', 'curl')])
        sleep.assert_called_once_with(2)
        self.assertEqual(result['requests_attempted'], 2)
        self.assertFalse(result['system_changes_made'])


if __name__ == '__main__':
    unittest.main()
