"""C24 synthetic HTML/streams/controller gates; never operate system settings."""

import copy
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import zlib
from contextlib import contextmanager, redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_validation import LocalTest
from validation import html_static as h, html_static_session as s, compat_session as runtime
from validation.capture_session import private_write
from validation.common import ROOT, SAMPLES
from validation.html_static_addon import HtmlStaticAddon
from validation.http import ProbeError

FIXTURE = ROOT/'examples/pages/article-static.html'


def html():
    return FIXTURE.read_bytes()


@contextmanager
def isolated_mode():
    names = ('DIRECTORY', 'PREVIOUS', 'UI_READY', 'EXPERIMENT', 'ADDON', 'READY_STATUS', 'WORKER_FLAG', 'RUN_SLUG')
    before = {name: getattr(runtime, name) for name in names}
    try:
        yield
    finally:
        for name, value in before.items():
            setattr(runtime, name, value)


class ParserTests(LocalTest):
    def test_valid_fixture_output_only_counts_and_sanitized_sources(self):
        data = h.analyze(html())
        self.assertTrue(data['body_identity_verified'])
        self.assertEqual(data['public_script_sources'], ['https://res.wx.qq.com/mmbizwap/zh_CN/htmledition/js/fixture.js'])
        self.assertEqual(data['stripped_query_or_fragment_count'], 1)
        self.assertEqual(data['inline_marker_counts']['WeixinJSBridge'], 1)
        self.assertFalse(data['comment_channel_verified'])
        self.assertFalse(data['comment_baseline_verified'])
        self.assertEqual(data['script_fetch_requests'], 0)
        for value in ('CONSTRUCTED_SECRET', '构造正文', '2247498641', '上个月最值的一笔消费'):
            self.assertNotIn(value, json.dumps(data, ensure_ascii=False))

    def test_verification_empty_and_wrong_identity_never_release_scripts(self):
        cases = [(b'<p>empty</p>', 'html_body_missing'),
                 ('<p>环境异常，请完成验证</p>'.encode(), 'html_access_restricted')]
        for old, new in (('2247498641', '999'), ('MzE5ODk2NjUwOA==', 'OTHER_SECRET'),
                         ('猫笔刀', '其他号'), ('上个月最值的一笔消费', 'PRIVATE_TITLE')):
            cases.append((html().replace(old.encode(), new.encode()), 'html_identity_unverified'))
        cases.append((html().replace(b'var idx = "1";', b''), 'html_identity_unverified'))
        for raw, reason in cases:
            with self.subTest(reason=reason, size=len(raw)):
                with self.assertRaises(ProbeError) as caught:
                    h.analyze(raw)
                self.assertEqual(caught.exception.reason, reason)
                self.assertNotIn('SECRET', str(caught.exception))

    def test_ambiguous_identity_and_paid_content_are_rejected(self):
        for raw, expected in (
            (html().replace(b'var idx = "1";', b'var idx = "1"; var idx = "2";'), 'html_identity_unverified'),
            (html().replace(b'</body>', b'<h1 id="activity-name">PRIVATE</h1></body>'), 'html_identity_ambiguous'),
            (html().replace(b'id="js_content"', b'id="js_content" id="OTHER"'), 'html_identity_ambiguous'),
            (html().replace(b'is_pay_subscribe = "0"', b'is_pay_subscribe = "1"'), 'html_paid_content_unverified'),
        ):
            with self.assertRaisesRegex(ProbeError, expected):
                h.analyze(raw)

    def test_malformed_text_and_decoded_size_reject_without_replacement(self):
        with self.assertRaisesRegex(ProbeError, 'text_encoding_invalid'):
            h.analyze(html()+b'\xff')
        with patch.object(h, 'LIMIT', 128):
            with self.assertRaisesRegex(ProbeError, 'decoded_size_limit'):
                h.analyze(html())
        self.assertTrue(h.analyze(b'\xef\xbb\xbf'+html())['body_identity_verified'])
        with self.assertRaisesRegex(ProbeError, 'structure_incomplete'):
            h.analyze(html().replace(b'</body></html>', b''))

    def test_script_allowlist_and_queries_fragments_never_leak(self):
        valid = 'https://res2.wx.qq.com/a/wx_fed/test/js/abc.123.js'
        self.assertEqual(h.public_script(valid+'?key=PRIVATE_SECRET#TOKEN'), valid)
        self.assertEqual(h.public_script(valid.replace('https:', '')), valid)
        invalid = ('http://res.wx.qq.com/mmbizwap/a.js',
                   valid.replace('res2.wx.qq.com', 'evil.invalid'), valid.replace('.com/', '.com:443/'),
                   valid.replace('/a/wx_fed/', '/private/'), valid.replace('test/', '../'),
                   valid.replace('test/', '%2e%2e/'), valid.replace('test/', 'test//'),
                   valid.replace('https://', 'https://user:SECRET@'),
                   valid.replace('abc.123.js', 'dynamic'), valid+'\n', 'javascript:PRIVATE', None)
        for value in invalid:
            self.assertIsNone(h.public_script(value))

    def test_duplicate_scripts_and_unknown_sources_remain_partial(self):
        raw = html().replace(b'</body>', b'<script src="https://unknown.invalid/PRIVATE.js?token=SECRET"></script>'
            b'<script src="https://res.wx.qq.com/mmbizwap/zh_CN/htmledition/js/fixture.js?uin=PRIVATE"></script></body>')
        result = h.analyze(raw)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['rejected_script_sources_count'], 1)
        self.assertEqual(len(result['public_script_sources']), 1)
        self.assertEqual(result['stripped_query_or_fragment_count'], 2)
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('unknown.invalid', json.dumps(result))

    def test_script_count_bound_and_no_clues_not_success(self):
        with self.assertRaisesRegex(ProbeError, 'script_count_limit'):
            h.analyze(html().replace(b'</body>', b'<script src="https://res.wx.qq.com/mmbizwap/a.js"></script>'*129+b'</body>'))
        raw = html().replace(b'var comment_id = "42";', b'')
        raw = raw.replace(b'// cgiDataNew WeixinJSBridge appmsg_comment getcomment elected_comment', b'')
        raw = raw[:raw.index(b'<script src=')]+b'</body></html>'
        self.assertEqual(h.analyze(raw)['reason'], 'html_no_static_clues')

    def test_target_gate_does_not_decode_private_query_values(self):
        url = 'https://mp.weixin.qq.com/s?__biz=MzE5ODk2NjUwOA%3D%3D&mid=2247498641&idx=1&key=PRIVATE_SECRET'
        seen = []
        original = h.unquote_plus
        def decode(value):
            seen.append(value)
            return original(value)
        with patch.object(h, 'unquote_plus', side_effect=decode):
            self.assertTrue(h.is_target(url, 'GET'))
        self.assertNotIn('PRIVATE_SECRET', seen)
        self.assertTrue(h.is_target(SAMPLES['maobidao']+'?key=PRIVATE_SECRET', 'GET'))
        for value in (url+'&idx=1', url.replace('2247498641','999'), url+'#fragment',
                      SAMPLES['stormzhang'], url.replace('https:', 'http:')):
            self.assertFalse(h.is_target(value, 'GET'))
        self.assertFalse(h.is_target(url, 'POST'))


class DecodeAndStreamTests(LocalTest):
    def test_identity_gzip_deflate_roundtrip_and_bad_streams(self):
        raw = html()
        for encoding, packed in (('identity', raw), ('gzip', gzip.compress(raw)), ('deflate', zlib.compress(raw))):
            self.assertEqual(h.decode_body(packed, encoding), raw)
            if encoding != 'identity':
                for bad in (packed[:-1], packed+b'PRIVATE_TRAILER', b'not a compressed body'):
                    with self.assertRaisesRegex(ProbeError, 'encoded_body_invalid'):
                        h.decode_body(bad, encoding)
        with self.assertRaisesRegex(ProbeError, 'encoding_unsupported'):
            h.decode_body(raw, 'zstd')

    def test_wire_and_decompressed_budgets(self):
        with patch.object(h, 'LIMIT', 1024):
            self.assertEqual(len(h.decode_body(b'x'*1024,'identity')), 1024)
            with self.assertRaisesRegex(ProbeError, 'wire_size_limit'):
                h.decode_body(b'x'*1025, 'identity')
            for encoding, packed in (('gzip', gzip.compress(b'x'*1025)), ('deflate', zlib.compress(b'x'*1025))):
                with self.assertRaisesRegex(ProbeError, 'decoded_size_limit'):
                    h.decode_body(packed, encoding)

    def test_one_success_unchanged_chunks_and_no_second_attempt(self):
        saved = []; subject = h.StaticSession(saved.append, lambda: True)
        callback = subject.begin(200, 'text/html; charset="UTF-8"', 'gzip')
        wire = gzip.compress(html())
        chunks = [wire[:40], wire[40:], b'']
        self.assertEqual([callback(chunk) for chunk in chunks], chunks)
        self.assertTrue(subject.saved)
        self.assertEqual(subject.buffer, b'')
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['wire_bytes'], len(wire))
        self.assertFalse(subject.summary()['comment_baseline_verified'])
        self.assertNotIn('SECRET', json.dumps(saved))
        with self.assertRaises(ProbeError):
            subject.begin(200, 'text/html', '')
        callback(b'new response PRIVATE_SECRET')
        self.assertEqual(len(saved), 1)

    def test_rejection_consumes_first_match_without_reading_body(self):
        for status, content, encoding, expected in (
            (302, 'text/html', '', 'html_HTTP_rejected'),
            (200, 'text/html; charset=gbk', '', 'html_content_type_rejected'),
            (200, 'application/json', '', 'html_content_type_rejected'),
            (200, 'text/html', 'unsupported SECRET', 'html_encoding_unsupported'),
        ):
            writer = Mock(); subject = h.StaticSession(writer, lambda: True)
            with self.assertRaisesRegex(ProbeError, expected):
                subject.begin(status, content, encoding)
            self.assertTrue(subject.attempted and subject.stopped)
            writer.assert_not_called()
            self.assertNotIn('SECRET', json.dumps(subject.summary()))

    def test_overlap_timeout_gate_and_size_limits_drop_buffer(self):
        now = [0]; writer = Mock(); gate = [True]
        subject = h.StaticSession(writer, lambda: gate[0], clock=lambda: now[0])
        callback = subject.begin(200, 'text/html', '')
        callback(b'PRIVATE_PARTIAL')
        with self.assertRaises(ProbeError):
            subject.begin(200, 'text/html', '')
        now[0] = 60
        self.assertEqual(callback(b'still passthrough'), b'still passthrough')
        self.assertEqual(subject.reason, 'html_gate_closed');self.assertEqual(subject.buffer, b'')
        writer.assert_not_called()
        subject = h.StaticSession(writer, lambda: gate[0]);callback = subject.begin(200,'text/html','')
        gate[0] = False;callback(b'PRIVATE');self.assertTrue(subject.stopped)
        writer.assert_not_called()
        subject = h.StaticSession(writer, lambda: True);callback = subject.begin(200,'text/html','')
        with patch.object(h,'LIMIT',10):
            callback(b'x'*11)
        self.assertEqual(subject.reason,'html_wire_size_limit');self.assertEqual(subject.buffer,b'')

    def test_invalid_body_interruption_and_store_failure_do_not_claim_saved(self):
        for payload, writer, expected in ((b'\xff', Mock(), 'html_text_encoding_invalid'),
                (html(), Mock(side_effect=OSError('PRIVATE_PATH')), 'html_analysis_or_store_failed'),
                (html(), Mock(side_effect=ProbeError('PRIVATE_TOKEN')), 'html_analysis_or_store_failed')):
            subject = h.StaticSession(writer, lambda: True)
            callback = subject.begin(200, 'text/html', '')
            callback(payload); callback(b'')
            self.assertEqual(subject.reason, expected);self.assertFalse(subject.saved)
            self.assertNotIn('PRIVATE', json.dumps(subject.summary()))
        subject = h.StaticSession(Mock(),lambda:True);subject.begin(200,'text/html','')
        subject.stream(b'PRIVATE');subject.stop()
        self.assertEqual(subject.reason,'html_stream_incomplete');self.assertEqual(subject.buffer,b'')


class AdapterAndModeTests(LocalTest):
    def test_existing_capture_components_without_listener_or_system_changes(self):
        script = '''
import gzip, json, zlib
from importlib.metadata import version
import brotli
from mitmproxy import connection, http
from validation import html_static as h
from validation.common import ROOT, SAMPLES
from validation.html_static_addon import HtmlStaticAddon
from validation.http import ProbeError
raw = (ROOT/'examples/pages/article-static.html').read_bytes()
results = []
for encoding, packed in (('identity',raw), ('gzip',gzip.compress(raw)), ('deflate',zlib.compress(raw)), ('br',brotli.compress(raw))):
    flow = http.HTTPFlow(connection.Client(peername=('127.0.0.1',0),sockname=('127.0.0.1',0)), connection.Server(address=('mp.weixin.qq.com',443)))
    flow.request = http.Request.make('GET',SAMPLES['maobidao'],headers={'Cookie':'PRIVATE_NEVER_READ'})
    flow.response = http.Response.make(200,b'',{'Content-Type':'text/html; charset=UTF-8; fixture="PRIVATE_PARAMETER"','Content-Encoding':encoding})
    saved = []
    addon = HtmlStaticAddon(); addon.session = h.StaticSession(saved.append,lambda:True,header_diagnostics=True)
    addon.requestheaders(flow); addon.responseheaders(flow)
    chunks = [packed[:13],packed[13:],b'']
    assert [flow.response.stream(c) for c in chunks] == chunks
    assert addon.session.saved and len(saved)==1 and 'PRIVATE' not in json.dumps(saved)
    assert saved[0]['response_metadata']['accepted'] is True
    results.append(encoding)
old = h.LIMIT; h.LIMIT = 1024
try:
    for encoding, packed in (('br',brotli.compress(b'x'*1025)), ('gzip',gzip.compress(b'x'*1025)), ('deflate',zlib.compress(b'x'*1025))):
        try: h.decode_body(packed,encoding)
        except ProbeError as error: assert error.reason == 'html_decoded_size_limit'
        else: raise AssertionError('over-limit accepted')
finally: h.LIMIT = old
packed = brotli.compress(raw)
for value in (packed[:-1], packed+b'PRIVATE_TRAILER', b'not brotli'):
    try: h.decode_body(value,'br')
    except ProbeError as error: assert error.reason == 'html_encoded_body_invalid'
    else: raise AssertionError('invalid stream accepted')
print(json.dumps({'status':'constructed_components_passed','encodings':results,'mitmproxy':version('mitmproxy'),'brotli':version('brotli'),'network_requests':0,'system_settings_changed':False}))
'''
        result=subprocess.run([str(ROOT/'.venv-capture/bin/python'),'-c',script],cwd=ROOT,
            capture_output=True,text=True,timeout=20,check=True)
        data=json.loads(result.stdout)
        self.assertEqual(data['encodings'],['identity','gzip','deflate','br'])
        self.assertEqual(data['mitmproxy'],'12.2.3');self.assertEqual(data['brotli'],'1.2.0')
        self.assertEqual(data['network_requests'],0)

    def flow(self, url=None):
        class ResponseHeaders:
            def get(self, key, default=''):
                if key not in ('content-type','content-encoding'):
                    raise AssertionError('Non-whitelist header read')
                return 'text/html' if key == 'content-type' else ''
        return SimpleNamespace(request=SimpleNamespace(url=url or SAMPLES['maobidao'],method='GET',headers=Mock()),
            response=SimpleNamespace(status_code=200,headers=ResponseHeaders(),stream=False),metadata={})

    def test_default_off_unmatched_no_header_or_body_read(self):
        addon=HtmlStaticAddon();self.assertIsNone(addon.session)
        flow=self.flow(SAMPLES['stormzhang']);flow.response.headers=Mock()
        addon.responseheaders(flow);flow.response.headers.get.assert_not_called()
        addon.session=h.StaticSession(Mock(),lambda:True)
        addon.requestheaders(flow);addon.responseheaders(flow)
        self.assertIs(flow.request.stream,True);self.assertIs(flow.response.stream,True)
        flow.response.headers.get.assert_not_called();flow.request.headers.get.assert_not_called()
        self.assertFalse(addon.session.attempted)

    def test_adapter_success_stream_preserves_bytes_and_early_cleanup(self):
        saved=[];addon=HtmlStaticAddon();addon.session=h.StaticSession(saved.append,lambda:True)
        addon.request_cleanup=Mock();flow=self.flow()
        addon.requestheaders(flow);addon.responseheaders(flow)
        for chunk in (html()[:100],html()[100:],b''):
            self.assertEqual(flow.response.stream(chunk),chunk)
        self.assertEqual(len(saved),1);self.assertTrue(addon.session.saved)
        flow.request.headers.get.assert_not_called();addon.request_cleanup.assert_called()

    def test_adapter_error_marks_incomplete_and_requests_cleanup(self):
        addon=HtmlStaticAddon();addon.session=h.StaticSession(Mock(),lambda:True)
        addon.request_cleanup=Mock();flow=self.flow();addon.responseheaders(flow)
        flow.response.stream(b'PRIVATE_PARTIAL');addon.error(flow)
        self.assertEqual(addon.session.reason,'html_stream_incomplete')
        self.assertEqual(addon.session.buffer,b'');addon.request_cleanup.assert_called()

    def proof(self):
        self.path.chmod(0o700)
        self.old=self.path/'closed';self.old.mkdir(mode=0o700)
        state={'status':'closed','finished':True,'recovery_completed_at':'2026-10-18T14:45:25+00:00',
            'recovery':{'verified':True,'proxy_verified':True,'process_stopped':True,'keys_removed':True,'trust':{'verified':True}}}
        private_write(self.old/'state.json',state)
        proof={key:value for key,value in s.review_plan().items() if key in (
            'experiment','duration_seconds','cleanup_reserve_seconds','max_passive_responses',
            'wire_limit_bytes','decoded_limit_bytes','manual_circular_arrow_refresh_once','Cookie_headers_read','raw_HTML_persisted')}
        proof.update(source='explicit_user_grant',authorized_at='2026-10-18T15:00:00+00:00',
            source_result_sha256=hashlib.sha256((self.old/'state.json').read_bytes()).hexdigest(),
            in_memory_article_HTML_inspection=True,sanitized_public_script_sources_only=True)
        self.authorization=self.path/'authorization.json';private_write(self.authorization,proof)
        return proof,state

    def test_fresh_authorization_binding_types_and_recovery(self):
        proof,state=self.proof()
        with patch.object(s,'AUTHORIZATION',self.authorization),patch.object(s,'PREVIOUS_REFRESH',self.old):
            s.authorized()
            for key,value in (('experiment','comment_refresh'),('max_passive_responses',True),
                    ('wire_limit_bytes',4194305),('Cookie_headers_read',True),('raw_HTML_persisted',True),
                    ('authorized_at','2026-10-18T01:00:00+00:00'),('source_result_sha256','0'*64)):
                bad={**proof,key:value};private_write(self.authorization,bad)
                with self.assertRaisesRegex(ProbeError,'html_static_not_authorized'):s.authorized()
            private_write(self.authorization,proof)
            state['recovery']['trust']['verified']=False;private_write(self.old/'state.json',state)
            with self.assertRaisesRegex(ProbeError,'html_static_not_authorized'):s.authorized()

    def test_missing_grant_stops_before_preflight_and_does_not_create_directory(self):
        with patch.object(s,'AUTHORIZATION',self.path/'absent'),patch.object(s,'select_runtime') as select:
            with self.assertRaisesRegex(ProbeError,'html_static_not_authorized'):s.session()
            select.assert_not_called()
        self.assertFalse((self.path/'absent').exists())

    def test_new_mode_ten_locks_routing_and_closed_directory_refusal(self):
        with isolated_mode(),patch.object(s,'DIRECTORY',self.path/'new'):
            rt=s.select_runtime()
            self.assertEqual(len(rt.PREVIOUS),10)
            self.assertEqual(rt.PREVIOUS[-1],s.PREVIOUS_REFRESH)
            self.assertEqual(rt.EXPERIMENT,'article_static');self.assertEqual(rt.WORKER_FLAG,'--html-static-worker')
            good={'status':'closed','finished':True,'recovery':{'verified':True,'proxy_verified':True,'process_stopped':True,
                'keys_removed':True,'trust':{'verified':True}}}
            with patch.object(rt.anchor,'previous_closed'),patch.object(rt,'private_json',return_value=good),patch.object(s,'authorized') as grant:
                rt.previous_closed();grant.assert_called_once()
            rt.DIRECTORY.mkdir(mode=0o700)
            with patch.object(s,'authorized'),patch.object(rt,'collect_baseline') as preflight:
                with self.assertRaisesRegex(ProbeError,'session_already_exists'):s.session()
                preflight.assert_not_called()

    def test_private_summary_is_exclusive_and_finish_after_stream_closed(self):
        self.path.chmod(0o700)
        with patch.object(s,'DIRECTORY',self.path):
            data=h.analyze(html());s.store_summary(data)
            self.assertEqual((self.path/'static-summary.json').stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):s.store_summary(data)
            fake=SimpleNamespace(load_plan=Mock())
            private_write(self.path/'state.json',{'status':s.READY_STATUS,'finished':False,'capture':{'status':'closed'}})
            with patch.object(s,'select_runtime',return_value=fake):
                self.assertEqual(s.finish()['status'],'cleanup_requested')
                with self.assertRaises(FileExistsError):s.finish()
                private_write(self.path/'state.json',{'status':'closed','finished':True})
                with self.assertRaisesRegex(ProbeError,'not_running'):s.finish()

    def test_fixed_cli_fixture_plan_and_unknown_error_sanitization(self):
        from validation.__main__ import main
        for action in ('plan','fixture'):
            output=io.StringIO()
            with patch.object(sys,'argv',['validation','html-static-'+action]),redirect_stdout(output):
                self.assertEqual(main(),0)
            data=json.loads(output.getvalue())
            self.assertNotIn('SECRET',output.getvalue())
            if action=='plan':self.assertFalse(data['executed'])
            else:self.assertEqual(data['evidence'],'constructed_HTML_no_network')
        output=io.StringIO()
        with patch.object(sys,'argv',['validation','html-static-session']), \
                patch.object(s,'session',side_effect=ProbeError('PRIVATE_SECRET')),redirect_stdout(output):
            self.assertEqual(main(),2)
        self.assertEqual(json.loads(output.getvalue())['reason'],'html_static_failed')
