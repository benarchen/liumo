"""Normal homepage-context gates; all credentials and responses are synthetic."""

import json
import unittest
from unittest.mock import Mock, patch

from test_http_route import credential
from validation.profile_context import check_profile_context
from validation.curl_bridge import profile_cookie
from validation.http import ProbeError, WechatHTTP


class ProfileContextTests(unittest.TestCase):
    def test_standard_https_client_returns_only_homepage_session_cookie_once(self):
        client = WechatHTTP()
        response = Mock()
        response.status = 200
        response.read.return_value = b'<p>profile</p>'
        response.headers.get_all.return_value = ['poc_sid=private-sid; HttpOnly', 'unrelated=private-other']
        with patch.object(client.opener, 'open') as open_request:
            open_request.return_value.__enter__.return_value = response
            client.read('https://mp.weixin.qq.com/mp/profile_ext?action=home')
            self.assertEqual(client.take_profile_cookie(), 'private-sid')
            self.assertIsNone(client.take_profile_cookie())
            client.read('https://mmbiz.qpic.cn/picture')
            self.assertIsNone(client.take_profile_cookie())

    def data(self):
        return {**credential(), 'biz': 'MzE5ODk2NjUwOA=='}

    def run_probe(self, html, sid='private-sid', payload=None):
        client = Mock()
        client.read.side_effect = [html.encode(), json.dumps(payload or {'ret': -3}).encode()]
        client.take_profile_cookie.return_value = sid
        with patch('validation.profile_context.load_credentials', return_value=self.data()), patch(
                'validation.profile_context.time.sleep'):
            result = check_profile_context('猫笔刀', client)
        return result, client

    def test_missing_or_wrong_identity_token_or_restriction_never_queries_list(self):
        for html, sid, reason in (
            ('<p>环境异常，请完成验证</p>', 'private-sid', 'access_restricted'),
            ("<script>var biz='OTHER'; var poc_token='private-token';</script>", 'private-sid', 'profile_identity_unverified'),
            ("<script>var biz='MzE5ODk2NjUwOA==';</script>", 'private-sid', 'profile_session_fields_missing'),
            ("<script>var biz='MzE5ODk2NjUwOA=='; var poc_token='private-token';</script>", None, 'profile_session_fields_missing')):
            result, client = self.run_probe(html, sid)
            self.assertEqual(result['reason'], reason)
            self.assertEqual(client.read.call_count, 1)
            self.assertEqual(result['requests_attempted']['list'], 0)
            self.assertNotIn('private-', json.dumps(result))

    def test_verified_context_uses_new_fields_only_in_memory_and_refusal_stops(self):
        result, client = self.run_probe("<script>var biz='MzE5ODk2NjUwOA=='; var poc_token='private-token';</script>")
        self.assertEqual(result['reason'], 'business_rejected')
        self.assertEqual(result['error_code'], -3)
        self.assertEqual(client.read.call_count, 2)
        self.assertIn('poc_token=private-token', client.read.call_args.args[0])
        self.assertIn('poc_sid=private-sid', client.read.call_args.args[1]['Cookie'])
        self.assertNotIn('private-', json.dumps(result))
        self.assertFalse(result['new_credentials_saved'])

    def test_missing_credential_or_http_refusal_does_not_probe_another_endpoint(self):
        client = Mock()
        with patch('validation.profile_context.load_credentials', side_effect=ProbeError('credentials_missing')):
            result = check_profile_context('猫笔刀', client)
        client.read.assert_not_called()
        self.assertEqual(result['requests_attempted']['home'], 0)
        client.read.side_effect = ProbeError('http_rejected', 403)
        with patch('validation.profile_context.load_credentials', return_value=self.data()):
            result = check_profile_context('猫笔刀', client)
        self.assertEqual(client.read.call_count, 1)
        self.assertEqual(result['error_code'], 403)

    def test_only_profile_cookie_is_selected_without_attributes_or_unknown_cookies(self):
        value = profile_cookie(b'Set-Cookie: unrelated=private-other\r\nSet-Cookie: poc_sid=private-sid; HttpOnly; Path=/\r\n')
        self.assertEqual(value, 'private-sid')
        self.assertIsNone(profile_cookie(b'Set-Cookie: unrelated=private-other\r\n'))
