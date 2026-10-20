"""Synthetic diagnostics only; never capture, request or mutate systems."""

import json
import unittest
from types import SimpleNamespace

from validation.capture import CaptureSession
from validation.mitm_addon import WechatCaptureAddon
from validation.transport_diagnostic import tls_error_category


class CaptureObservationTests(unittest.TestCase):
    def addon(self):
        addon = WechatCaptureAddon()
        addon.session = CaptureSession(writer=lambda _: self.fail('unexpected credential write'))
        return addon

    def test_tls_scope_uses_connection_sni_without_retaining_names_or_errors(self):
        addon = self.addon()
        for sni in ('mp.weixin.qq.com', 'MP.WEIXIN.QQ.COM.', 'PRIVATE_OTHER.example', None, b'PRIVATE', 'BAD\nPRIVATE'):
            data = SimpleNamespace(conn=SimpleNamespace(sni=sni, error='PRIVATE_ERROR'))
            addon.tls_failed_client(data)
            addon.tls_failed_server(data)
        for side in ('client', 'server'):
            self.assertEqual(addon.diagnostics['tls_' + side + '_failures_seen'], 6)
            self.assertEqual(addon.diagnostics['tls_' + side + '_failures_target'], 2)
            self.assertEqual(addon.diagnostics['tls_' + side + '_failures_other'], 1)
            self.assertEqual(addon.diagnostics['tls_' + side + '_failures_unknown'], 3)
        self.assertNotIn('PRIVATE', json.dumps(addon.diagnostics))
        self.assertNotIn('weixin', json.dumps(addon.diagnostics))

    def test_request_stage_counts_unknown_path_without_headers_or_response(self):
        addon = self.addon()
        class HeadersForbidden:
            def __getattr__(self, _):
                raise AssertionError('headers must not be inspected')
        for path in ('/mp/profile_ext', '/s/PRIVATE_ARTICLE', '/PRIVATE_NEW_PATH'):
            flow = SimpleNamespace(request=SimpleNamespace(url='https://mp.weixin.qq.com' + path + '?token=PRIVATE',
                                                          headers=HeadersForbidden(), stream=False))
            addon.requestheaders(flow)
            self.assertTrue(flow.request.stream)
        self.assertEqual(addon.diagnostics['target_host_requests_seen'], 3)
        for category in ('profile_path', 'article_like', 'other_target_path'):
            self.assertEqual(addon.diagnostics[category + '_requests_seen'], 1)
        self.assertNotIn('target_host_responses_seen', addon.diagnostics)
        self.assertNotIn('PRIVATE', json.dumps(addon.diagnostics))
        self.assertFalse(addon.session.summary()['authentication_verified'])

    def test_response_counter_precedes_scope_filter_but_does_not_read_headers(self):
        addon = self.addon()
        flow = SimpleNamespace(request=SimpleNamespace(url='https://mp.weixin.qq.com/PRIVATE_NEW_PATH?token=PRIVATE',
                                                       method='GET'),
                               response=SimpleNamespace(status_code=200, stream=False))
        addon.responseheaders(flow)
        self.assertTrue(flow.response.stream)
        self.assertEqual(addon.diagnostics['target_host_responses_seen'], 1)
        self.assertEqual(addon.diagnostics['other_target_path_responses_seen'], 1)
        self.assertNotIn('PRIVATE', json.dumps(addon.diagnostics))

    def test_off_stopped_expired_and_other_host_do_not_add_target_observations(self):
        addon = WechatCaptureAddon()
        opaque = object()
        addon.requestheaders(opaque)
        addon.tls_failed_client(opaque)
        self.assertEqual(addon.diagnostics, {})
        addon = self.addon()
        flow = SimpleNamespace(request=SimpleNamespace(url='https://PRIVATE.example/path?key=PRIVATE', stream=False))
        addon.requestheaders(flow)
        self.assertEqual(addon.diagnostics, {})
        addon.session.stop()
        addon.requestheaders(SimpleNamespace(request=SimpleNamespace(stream=False)))
        addon.tls_failed_client(opaque)
        self.assertEqual(addon.diagnostics, {})
        addon.session = CaptureSession(seconds=1, clock=lambda: 0)
        addon.session.clock = lambda: 2
        addon.requestheaders(SimpleNamespace(request=SimpleNamespace(stream=False)))
        addon.tls_failed_server(opaque)
        self.assertEqual(addon.diagnostics, {})

    def test_component_error_categories_do_not_treat_generic_trust_hint_as_proof(self):
        cases = [
            ('The client does not trust the proxy certificate (tlsv1 alert unknown ca)', 'certificate_alert'),
            ('ssl/tls alert bad certificate', 'certificate_alert'),
            ('Certificate verify failed: PRIVATE_HOST', 'certificate_verification'),
            ('Client and mitmproxy cannot agree on a TLS version to use.', 'protocol_error'),
            ('wrong version number', 'protocol_error'),
            ('The client disconnected during the handshake. This may indicate that the client does not trust the proxy certificate.', 'connection_closed'),
            ('The client may not trust the proxy certificate (PRIVATE_ERROR)', 'other'),
            ('bad certificate; connection closed', 'ambiguous'),
            (None, 'unavailable'), (b'PRIVATE', 'unavailable'),
            ('PRIVATE' * 1000, 'unavailable'), (object(), 'unavailable'),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(tls_error_category(error), expected)

    def test_reason_counters_are_target_only_and_never_retain_raw_errors(self):
        addon = self.addon()
        class OtherConnection:
            sni = 'PRIVATE.example'
            @property
            def error(self):
                raise AssertionError('other host error must not be read')
        addon.tls_failed_client(SimpleNamespace(conn=OtherConnection()))
        for side in ('client', 'server'):
            hook = getattr(addon, 'tls_failed_' + side)
            hook(SimpleNamespace(conn=SimpleNamespace(sni='mp.weixin.qq.com', error='unknown ca PRIVATE_TOKEN')))
            hook(SimpleNamespace(conn=SimpleNamespace(sni='mp.weixin.qq.com', error='PRIVATE_REASON')))
            self.assertEqual(addon.diagnostics['tls_' + side + '_target_reason_certificate_alert'], 1)
            self.assertEqual(addon.diagnostics['tls_' + side + '_target_reason_other'], 1)
        before = dict(addon.diagnostics)
        addon.session.stop()
        addon.tls_failed_client(SimpleNamespace(conn=object()))
        self.assertEqual(addon.diagnostics, before)
        self.assertNotIn('PRIVATE', json.dumps(addon.diagnostics))
