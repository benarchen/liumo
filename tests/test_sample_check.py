"""Credentialed sample requests and independent original-page gating."""

import json
import base64
from unittest.mock import patch

from test_validation import LocalTest
from test_http_route import credential, fixture_pages, request_from
from validation.common import ROOT, SAMPLES
from validation.credentials import load_sample_credentials, sample_browser_cookies
from validation.http import ProbeError
from validation.http_archive import archive_http
from validation.mp_source import scan_profile
from validation.sample_check import check_samples
from validation.archive import credential_page_matches, archive


def sample_credential():
    return {**credential(), 'biz': 'MzE5ODk2NjUwOA==', 'source_identity': {'mid': '2247498641', 'idx': '1'},
            'cookie': 'appmsg_token=private-token; pass_ticket=private-pass; wap_sid2=private-sid'}


class MissingListTests(LocalTest):
    def test_observed_missing_list_is_not_empty_success_and_does_not_advance(self):
        payload = json.loads((ROOT / 'examples/profile-list-missing.json').read_text())
        calls = []
        def request(*args):
            calls.append(args)
            return payload
        result = scan_profile(request, '猫笔刀', 'FIXTURE')
        self.assertEqual(result['reason'], 'source_list_missing')
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['status'], 'not_verified')
        self.assertEqual(len(calls), 1)
        from validation.state import ingest, empty_state
        state = empty_state()
        result = ingest(state, result['pages'], '2026-10-16T00:00:00+08:00')
        self.assertFalse(result['complete_scan'])
        self.assertIsNone(state['last_complete_check'])


class SampleCredentialTests(LocalTest):
    def test_public_scope_required_before_requests_and_cookie_host_only(self):
        good = sample_credential()
        with patch('validation.credentials.load_credentials', return_value=good):
            self.assertEqual(load_sample_credentials('maobidao')['account'], '猫笔刀')
        for change in ({'biz': 'OTHER'}, {'source_identity': {'mid': 'wrong', 'idx': '1'}}, {'cookie': ''}):
            with patch('validation.credentials.load_credentials', return_value={**good, **change}), self.assertRaises(ProbeError):
                load_sample_credentials('maobidao')
        cookies = sample_browser_cookies({**good, 'cookie': good['cookie'] + '; unrelated=must-not-keep'})
        self.assertTrue(all(c['url'] == 'https://mp.weixin.qq.com/' and c['secure'] for c in cookies))
        self.assertNotIn('domain', cookies[0])
        self.assertNotIn('unrelated', [c['name'] for c in cookies])

    def test_browser_identity_check_is_atomic_and_mismatch_rejected(self):
        good = sample_credential()
        observation = {'article_identity_candidates': {'biz': good['biz'], **good['source_identity']}}
        with patch('validation.archive.public_page_observations', return_value=observation) as read:
            self.assertTrue(credential_page_matches(object(), good))
            read.assert_called_once()
        observation['article_identity_candidates']['mid'] = 'other'
        with patch('validation.archive.public_page_observations', return_value=observation):
            self.assertFalse(credential_page_matches(object(), good))

    def test_invalid_browser_sample_never_launches_or_reads_other_profiles(self):
        with patch('validation.archive.new_run', return_value=self.path), patch('validation.archive.sync_playwright') as driver:
            result = archive(SAMPLES['stormzhang'], credential_sample='maobidao')
        driver.assert_not_called()
        self.assertEqual(result['reasons'], ['credential_article_scope_mismatch'])


class CredentialedHttpTests(LocalTest):
    def test_body_uses_cookie_images_do_not_and_session_links_are_redacted(self):
        html = (ROOT / 'examples/pages/http-article.html').read_text()
        html = html.replace('FIXTURE_BIZ', 'MzE5ODk2NjUwOA==').replace("mid = '100'", "mid = '2247498641'")
        inline = html.split('data:image/png;base64,', 1)[1].split('"', 1)[0]
        html = html.replace('data:image/png;base64,' + inline, 'https://mmbiz.qpic.cn/sample.png')
        html = html.replace('BODY-END', 'BODY-END<a href="https://mp.weixin.qq.com/s/x?key=private-link&uin=private-user&scene=1">链接</a>')
        with patch('validation.http_archive.new_run', return_value=self.path), patch(
                'validation.http_archive.load_sample_credentials', return_value=sample_credential()), patch(
                'validation.http_archive.WechatHTTP') as client:
            client.return_value.read.side_effect = [html.encode(), base64.b64decode(inline)]
            request = request_from(fixture_pages(), [])
            client.return_value.api.side_effect = lambda action, fields, _credential: request(action, fields)
            result = archive_http('maobidao', credentialed=True, transport='curl')
        first, second = client.return_value.read.call_args_list
        self.assertEqual(first.args, (SAMPLES['maobidao'], {'Cookie': sample_credential()['cookie']}))
        self.assertEqual(second.args, ('https://mmbiz.qpic.cn/sample.png',))
        self.assertEqual(second.kwargs, {'limit': 25 * 1024 * 1024})
        self.assertEqual(result['comments']['status'], 'loaded')
        self.assertEqual(result['status'], 'partial')
        self.assertNotIn('html_sha256', result)
        self.assertNotIn('private-', (self.path / 'article.md').read_text())
        self.assertNotIn('private-', (self.path / 'http-metadata.json').read_text())
        self.assertEqual(result['requests_attempted'], {'body': 1, 'images': 1, 'comment_api': 4})

    def test_missing_or_wrong_scope_zero_requests_and_no_anonymous_fallback(self):
        with patch('validation.http_archive.new_run', return_value=self.path), patch(
                'validation.http_archive.load_sample_credentials', side_effect=ProbeError('credential_article_scope_mismatch')), patch(
                'validation.http_archive.WechatHTTP') as client:
            result = archive_http('maobidao', credentialed=True, transport='curl')
        client.assert_not_called()
        self.assertEqual(result['requests_attempted']['body'], 0)
        self.assertEqual(result['reason'], 'credential_article_scope_mismatch')

    def test_body_refusal_stops_comments_and_no_raw_credentials_persist(self):
        with patch('validation.http_archive.new_run', return_value=self.path), patch(
                'validation.http_archive.load_sample_credentials', return_value=sample_credential()), patch(
                'validation.http_archive.WechatHTTP') as client:
            client.return_value.read.return_value = '<p>环境异常，请完成验证</p>'.encode()
            result = archive_http('maobidao', credentialed=True, transport='curl')
        self.assertEqual(client.return_value.read.call_count, 1)
        client.return_value.api.assert_not_called()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['requests_attempted']['comment_api'], 0)
        self.assertNotIn('private-', (self.path / 'http-metadata.json').read_text())

    def test_body_identity_guard_prevents_wrong_article_images_or_comments(self):
        html = (ROOT / 'examples/pages/http-article.html').read_text()
        with patch('validation.http_archive.new_run', return_value=self.path), patch(
                'validation.http_archive.load_sample_credentials', return_value=sample_credential()), patch(
                'validation.http_archive.WechatHTTP') as client:
            client.return_value.read.return_value = html.encode()
            result = archive_http('maobidao', credentialed=True)
        client.return_value.api.assert_not_called()
        self.assertIn('credential_article_scope_mismatch', result['reasons'])
        self.assertFalse((self.path / 'article.md').exists())


class SampleOrchestrationTests(LocalTest):
    def test_no_list_requests_browser_after_gate_only_and_each_account_once(self):
        rows = [{'status': 'blocked', 'reason': 'access_restricted'},
                {'status': 'partial', 'account_identity_verified': True, 'comments': {'status': 'unknown'}}]
        with patch('validation.sample_check.new_run', return_value=self.path), patch(
                'validation.sample_check.archive_http', side_effect=rows) as http, patch(
                'validation.archive.archive', return_value={'status': 'partial'}) as browser, patch(
                'validation.sample_check.time.sleep') as sleep:
            result = check_samples('curl', browser=True)
        self.assertEqual([c.args[0] for c in http.call_args_list], ['maobidao', 'stormzhang'])
        self.assertTrue(all(c.kwargs == {'credentialed': True, 'transport': 'curl'} for c in http.call_args_list))
        browser.assert_called_once_with(SAMPLES['stormzhang'], credential_sample='stormzhang')
        sleep.assert_called_once_with(2)
        self.assertFalse(result['formal_subscription_enabled'])
        self.assertFalse(result['system_changes_made'])
        self.assertEqual(len(json.loads((self.path / 'samples.json').read_text())['results']), 2)

    def test_comment_refusal_does_not_trigger_browser_retry(self):
        row = {'status': 'partial', 'account_identity_verified': True, 'comments': {'status': 'failed'}}
        with patch('validation.sample_check.new_run', return_value=self.path), patch(
                'validation.sample_check.archive_http', return_value=row), patch(
                'validation.archive.archive') as browser, patch('validation.sample_check.time.sleep'):
            check_samples(browser=True)
        browser.assert_not_called()

    def test_both_blocked_are_not_described_as_partial_success(self):
        with patch('validation.sample_check.new_run', return_value=self.path), patch(
                'validation.sample_check.archive_http', return_value={'status': 'blocked'}), patch(
                'validation.sample_check.time.sleep'):
            result = check_samples()
        self.assertEqual(result['status'], 'not_verified')
        self.assertTrue(all(row['http']['status'] == 'blocked' for row in result['results']))
