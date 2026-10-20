"""C21 local tests: constructed fields/bodies, never live credentials or trust."""

import copy
import io
import gzip
import hashlib
import json
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from test_validation import LocalTest
from validation import comment_baseline as c
from validation import compat_session as runtime
from validation.capture_session import private_write
from validation.comment_addon import CommentBaselineAddon
from validation.http import ProbeError, USER_AGENT


def url(**changes):
    fields = {'action': 'getcomment', '__biz': c.BIZ, 'appmsgid': c.IDENTITY['appmsgid'],
        'idx': '1', 'comment_id': '42', 'uin': 'SECRET_UIN', 'key': 'SECRET_KEY',
        'pass_ticket': 'SECRET_TICKET', 'appmsg_token': 'SECRET_TOKEN', **changes}
    return 'https://mp.weixin.qq.com/mp/appmsg_comment?' + urlencode(fields)


def headers(**changes):
    return {'User-Agent': USER_AGENT, 'Accept': '*/*', 'Accept-Language': 'zh-CN',
        'X-Requested-With': '', 'Cookie': 'appmsg_token=SECRET_TOKEN; extra=SECRET_EXTRA',
        'Referer': 'https://mp.weixin.qq.com/', **changes}


def payload(**changes):
    return json.dumps({'base_resp': {'ret': 0}, 'elected_comment': [
        {'content_id': '1', 'nick_name': 'PRIVATE_NAME', 'content': 'PRIVATE_COMMENT'}], **changes}).encode()


def start(subject, head=None, encoding='identity'):
    data = subject.matching(url(), 'GET', 200)
    return subject.begin(data, headers() if head is None else head,
        ['appmsg_token=SECRET_NEW; Path=/; HttpOnly', 'newCookie=SECRET_UPDATED; Path=/'], encoding)


class CaptureTests(LocalTest):
    def test_one_success_stream_unchanged_private_context_without_comment_content(self):
        rows = []
        subject = c.CommentBaselineSession(writer=rows.append, gate=lambda: True)
        stream = start(subject)
        raw = payload()
        self.assertEqual(b''.join(stream(raw[n:n+7]) for n in range(0, len(raw), 7)), raw)
        self.assertEqual(stream(b''), b'')
        self.assertTrue(subject.saved)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['query']['key'], 'SECRET_KEY')
        self.assertEqual(rows[0]['request_cookie'], headers()['Cookie'])
        self.assertEqual(rows[0]['response_cookie_updates']['newCookie'], 'SECRET_UPDATED')
        self.assertNotIn('PRIVATE_', json.dumps(rows))
        self.assertNotIn('SECRET', json.dumps(subject.summary()))
        self.assertEqual(subject.summary()['response']['comment_items_count'], 1)
        self.assertEqual(subject.buffer, b'')
        self.assertIsNone(subject.pending)
        with self.assertRaises(ProbeError): subject.matching(url(), 'GET', 200)
        self.assertEqual(stream(b'unrelated later bytes'), b'unrelated later bytes')

    def test_wrong_scope_duplicate_control_fields_no_headers_or_body_read(self):
        subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: True)
        for address, method in ((url(__biz='other'), 'GET'), (url(appmsgid='1'), 'GET'),
                (url(idx='2'), 'GET'), (url(action='getcommentreply'), 'GET'), (url(), 'POST'),
                (url().replace('https:', 'http:'), 'GET'),
                (url()+'&__biz='+c.BIZ, 'GET'), (url()+'&key=ambiguous', 'GET'),
                (url(key='bad\r\nSECRET'), 'GET')):
            with self.assertRaises(ProbeError): subject.matching(address, method, 200)
        class NoRead:
            def get(self, *_): raise AssertionError('unrelated headers read')
        addon = CommentBaselineAddon();addon.session = subject
        flow = SimpleNamespace(request=SimpleNamespace(url=url(appmsgid='1'),method='GET',headers=NoRead()),
            response=SimpleNamespace(status_code=200,stream=False,headers=NoRead()),metadata={})
        addon.responseheaders(flow)
        self.assertIs(flow.response.stream, True)
        self.assertFalse(subject.attempted)
        subject.writer.assert_not_called()

    def test_gate_time_HTTP_refusal_and_interruption_stop_without_capture(self):
        for gate in (False,):
            subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: gate)
            with self.assertRaises(ProbeError): subject.matching(url(), 'GET', 200)
            self.assertFalse(subject.attempted)
        subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: True)
        with self.assertRaises(ProbeError): subject.matching(url(), 'GET', 302)
        self.assertTrue(subject.stopped);subject.writer.assert_not_called()
        now = [0]
        subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: True, clock=lambda: now[0])
        stream = start(subject);stream(b'partial SECRET')
        now[0] = 61
        self.assertEqual(stream(b'after limit'), b'after limit')
        self.assertTrue(subject.stopped)
        self.assertEqual(subject.reason, 'comment_stream_incomplete')
        self.assertFalse(subject.buffer);subject.writer.assert_not_called()

    def test_business_refusal_empty_malformed_and_large_responses_never_save(self):
        for raw, expected in ((payload(base_resp={'ret': -3}), 'native_comment_business_rejected'),
                (payload(elected_comment=[]), 'native_comment_empty_not_success_baseline'),
                (b'PRIVATE not JSON', 'comment_response_invalid'),
                (payload(base_resp={'ret': 'SECRET'}), 'comment_business_status_unknown'),
                (payload(elected_comment='PRIVATE'), 'native_comment_shape_unknown'),
                (b'x'*(c.LIMIT+1), 'comment_wire_size_limit')):
            subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: True)
            stream = start(subject)
            self.assertEqual(stream(raw), raw)
            stream(b'')
            self.assertEqual(subject.reason, expected)
            self.assertTrue(subject.stopped);subject.writer.assert_not_called()
            self.assertNotIn('PRIVATE', json.dumps(subject.summary()))
            self.assertNotIn('SECRET', json.dumps(subject.summary()))

    def test_bounded_gzip_deflate_truncation_and_bombs(self):
        for encoding, encode in (('gzip', gzip.compress), ('deflate', zlib.compress)):
            raw = payload()
            self.assertEqual(c.decode_body(encode(raw), encoding), raw)
            with self.assertRaises(ProbeError): c.decode_body(encode(raw)[:-1], encoding)
            with self.assertRaisesRegex(ProbeError, 'decoded_size_limit'):
                c.decode_body(encode(b'x'*(c.LIMIT+1)), encoding)
        with self.assertRaisesRegex(ProbeError, 'encoding_unsupported'): c.decode_body(b'x', 'zstd')

    def test_context_failures_write_failure_and_private_no_overwrite(self):
        for head in (headers(Cookie='bad\r\nSECRET'), {**headers(), 'Authorization': 'SECRET'}):
            subject = c.CommentBaselineSession(writer=Mock(), gate=lambda: True)
            with self.assertRaises(ProbeError): start(subject, head)
            self.assertTrue(subject.stopped);subject.writer.assert_not_called()
        subject = c.CommentBaselineSession(writer=Mock(side_effect=OSError('SECRET_DISK')), gate=lambda: True)
        stream = start(subject);stream(payload());stream(b'')
        self.assertEqual(subject.reason, 'comment_baseline_store_failed')
        self.assertFalse(subject.saved)
        with patch.object(c, 'DIRECTORY', self.path):
            c.store_baseline({'constructed': True})
            p=self.path/'baseline.json';before=p.read_bytes()
            self.assertEqual(p.stat().st_mode&0o777, 0o600)
            with self.assertRaises(FileExistsError): c.store_baseline({'other': True})
            self.assertEqual(p.read_bytes(), before)
            with self.assertRaises(ProbeError): c.store_baseline({'huge': 'x'*131073})

    def test_Referer_never_saves_auth_query_or_unrelated_URL(self):
        address='https://mp.weixin.qq.com/s?'+urlencode({'__biz':c.BIZ,'mid':c.IDENTITY['appmsgid'],
            'idx':'1','sn':'public','key':'SECRET'})
        scope, public=c.public_referer(address)
        self.assertEqual(scope,'target_article')
        self.assertNotIn('SECRET',public)
        self.assertEqual(c.public_referer('https://unrelated.invalid/?SECRET'),('other',''))


class GateAndCompareTests(LocalTest):
    def test_CLI_exposes_only_fixed_C21_failure_reasons(self):
        from validation.__main__ import main
        for reason, expected in (
                ('compat_UI_confirmation_required', 'compat_UI_confirmation_required'),
                ('preflight_system_authorization_unavailable', 'preflight_system_authorization_unavailable'),
                ('PRIVATE_TOKEN_OR_UPSTREAM_ERROR', 'comment_baseline_failed')):
            output=io.StringIO()
            with patch.object(sys,'argv',['validation','comment-baseline-session']), \
                    patch.object(c,'session',side_effect=ProbeError(reason)),redirect_stdout(output):
                self.assertEqual(main(),2)
            result=json.loads(output.getvalue())
            self.assertEqual(result['reason'],expected)
            self.assertNotIn('PRIVATE_TOKEN',output.getvalue())

    def test_authorization_binds_C20_scope_and_blocks_session_before_preflight(self):
        old={'at':'2026-10-18T10:42:42+00:00','body_verified':True,
            'requests_attempted':{'body':1,'comments':1},'comments':{'error_code':-3}}
        source=self.path/'functional-cookie-body-result.json';private_write(source,old)
        proof={'experiment':'c21_comment_baseline','source':'explicit_user_grant',
            'authorized_at':'2026-10-18T11:00:00+00:00','source_result_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'max_passive_responses':1,'wire_limit_bytes':c.LIMIT,'decoded_limit_bytes':c.LIMIT,
            'full_single_Cookie_field_private':True,'duration_seconds':180,'cleanup_reserve_seconds':120}
        with patch.object(c,'AUTHORIZATION',self.path/'auth.json'),patch.object(c,'ARTICLE_DIRECTORY',self.path), \
                patch.object(c,'select_runtime') as select:
            with self.assertRaises(ProbeError):c.session()
            select.assert_not_called()
            private_write(c.AUTHORIZATION,proof);c.authorized()
            for change in ({'max_passive_responses':2},{'max_passive_responses':True},{'source_result_sha256':'bad'},
                {'full_single_Cookie_field_private':False},{'wire_limit_bytes':0},
                {'authorized_at':'2000-01-01T00:00:00+00:00'}):
                private_write(c.AUTHORIZATION,{**proof,**change})
                with self.assertRaises(ProbeError):c.authorized()

    def test_selector_previous_recovery_and_default_mode_restoration(self):
        names=('DIRECTORY','PREVIOUS','UI_READY','EXPERIMENT','ADDON','READY_STATUS','WORKER_FLAG','RUN_SLUG')
        original=runtime.EXPERIMENT
        with patch.multiple(runtime,**{n:getattr(runtime,n) for n in names}):
            c.select_runtime()
            self.assertEqual(runtime.EXPERIMENT,'comment_baseline')
            self.assertEqual(len(runtime.PREVIOUS),8)
            self.assertEqual(runtime.WORKER_FLAG,'--comment-baseline-worker')
            with patch.object(runtime.anchor,'previous_closed'),patch.object(runtime,'private_json',return_value={
                'finished':True,'status':'closed','recovery':{'verified':True,'process_stopped':True}}):
                runtime.previous_closed()
            with patch.object(runtime.anchor,'previous_closed'),patch.object(runtime,'private_json',return_value={
                'finished':False,'recovery':{'verified':False}}):
                with self.assertRaises(ProbeError):runtime.previous_closed()
        self.assertEqual(runtime.EXPERIMENT,original)

    def test_offline_compare_exports_fixed_fields_only_and_requires_recovery(self):
        rows=[];subject=c.CommentBaselineSession(writer=rows.append,gate=lambda:True)
        stream=start(subject);stream(payload());stream(b'')
        row=rows[0];row['response']['UNTRUSTED_SECRET']='DO_NOT_EXPORT'
        private_write(self.path/'baseline.json',row)
        instant=datetime.fromisoformat(row['captured_at']).timestamp()
        plan={'wall_deadline':instant+120,'active_deadline':instant+1}
        good={'status':'closed','finished':True,'recovery':{'verified':True,'proxy_verified':True,
            'process_stopped':True,'keys_removed':True,'trust':{'verified':True}}}
        private_write(self.path/'state.json',good)
        fake=SimpleNamespace(load_plan=lambda:plan,KEYS=('never_created.pem',))
        old={'uin':'SECRET_UIN','key':'OLD_SECRET_KEY','pass_ticket':'SECRET_TICKET','appmsg_token':'SECRET_TOKEN',
            'cookie':'appmsg_token=SECRET_TOKEN'}
        with patch.object(c,'DIRECTORY',self.path),patch.object(c,'authorized'), \
                patch.object(c,'select_runtime',return_value=fake),patch.object(c,'read_private_credentials',return_value=old), \
                patch.object(c,'new_run',return_value=self.path/'out'):
            result=c.compare()
            self.assertEqual(result['query']['key'],'changed')
            self.assertEqual(result['query']['comment_id'],'not_retained_in_C20')
            self.assertEqual(result['additional_native_Cookie_count'],1)
            self.assertFalse(result['minus3_cause_verified'])
            self.assertNotIn('SECRET',json.dumps(result));self.assertNotIn('PRIVATE',json.dumps(result))
            for key in ('verified','proxy_verified','process_stopped','keys_removed'):
                bad=copy.deepcopy(good);bad['recovery'][key]=False
                private_write(self.path/'state.json',bad)
                with self.assertRaises(ProbeError):c.compare()


    def test_finish_after_closed_stream_requests_cleanup_without_fake_observation(self):
        fake=SimpleNamespace(load_plan=Mock(),observe=Mock())
        private_write(self.path/'state.json',{'status':c.READY_STATUS,'finished':False})
        private_write(self.path/'capture.json',{'status':'closed','success_baseline_saved':True})
        with patch.object(c,'DIRECTORY',self.path),patch.object(c,'select_runtime',return_value=fake):
            result=c.finish()
            self.assertEqual(result['status'],'cleanup_requested')
            self.assertFalse(result['UI_refresh_verified_by_snapshot'])
            self.assertEqual((self.path/'FINISH').stat().st_mode&0o777,0o600)
            fake.observe.assert_not_called()
            with self.assertRaises(FileExistsError):c.finish()

    def test_finish_rejects_closed_session_before_writing(self):
        private_write(self.path/'state.json',{'status':'closed','finished':True})
        with patch.object(c,'DIRECTORY',self.path),patch.object(c,'select_runtime',return_value=SimpleNamespace(load_plan=Mock())):
            with self.assertRaises(ProbeError):c.finish()
            self.assertFalse((self.path/'FINISH').exists())


class InstalledComponentTests(LocalTest):
    def test_actual_Brotli_and_addon_callback_without_listener_or_account(self):
        code=r'''
import asyncio,brotli,gzip,json,socket,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from validation import comment_baseline as c,compat_session as s
from validation.comment_addon import CommentBaselineAddon
from validation.capture_session import private_write
from validation.common import ROOT
raw=json.dumps({'base_resp':{'ret':0},'elected_comment':[{'content':'PRIVATE_COMMENT'}]}).encode()
assert c.decode_body(brotli.compress(raw),'br')==raw
try:c.decode_body(brotli.compress(b'x'*(c.LIMIT+1)),'br')
except Exception:pass
else:raise AssertionError('unbounded Brotli accepted')
async def run():
 with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as temporary:
  base=Path(temporary);(base/'.auth').mkdir(mode=0o700);(base/'.auth/wechat-capture').mkdir(mode=0o700)
  d=base/'.auth/wechat-capture/comment-baseline-session';d.mkdir(mode=0o700)
  c.DIRECTORY=d;c.ARTICLE_DIRECTORY=d.parent/'old';s.ROOT=base;c.select_runtime()
  identity=s.generate(d)
  proxy={'Enabled':'Yes','Server':'127.0.0.1','Port':'7897','Authenticated Proxy Enabled':'0'}
  baseline={'https_proxy':proxy,'http_proxy':dict(proxy),'pac':{'Enabled':'No','URL':'(null)'},
    'autodiscovery':'Auto Proxy Discovery: Off','review_reasons':[],'bypass_domains':['localhost']}
  now=time.time();plan={'version':1,'experiment':'comment_baseline','duration_seconds':180,
    'cleanup_reserve_seconds':120,'baseline':baseline,'mode':s.upstream_mode(baseline),
    'wall_deadline':now+180,'active_deadline':now+60,**identity}
  private_write(d/'plan.json',plan);private_write(d/'state.json',{'capture_disabled':False,'status':c.READY_STATUS})
  with patch.object(c,'ready',return_value=True):
   master=DumpMaster(Options(server=False,confdir=str(d/'mitmproxy')),with_termlog=True,with_dumper=True)
   addon=CommentBaselineAddon();master.addons.add(addon);opts=master.options
   try:
    opts.update(mode=[plan['mode']],listen_host='127.0.0.1',listen_port=8899,
      allow_hosts=[r'^mp\.weixin\.qq\.com:443$'],ssl_insecure=False,upstream_cert=False,
      add_upstream_certs_to_client_chain=False,flow_detail=0,termlog_verbosity='error',
      command_history=False,strip_ech=False,store_streamed_bodies=False,
      certs=['mp.weixin.qq.com='+str(d/'mitmproxy/target-key-chain.pem')])
    assert addon.session is None
    opts.update(liumo_compat=True)
    q={'action':'getcomment','__biz':c.BIZ,'appmsgid':c.IDENTITY['appmsgid'],'idx':'1','comment_id':'42'}
    request=http.Request.make('GET','https://mp.weixin.qq.com/mp/appmsg_comment?'+urlencode(q),
      headers={'Cookie':'appmsg_token=FAKE_TOKEN; extra=FAKE_OTHER'})
    response=http.Response.make(200,b'',headers={'Content-Encoding':'br'})
    response.raw_content=None
    flow=SimpleNamespace(request=request,response=response,metadata={})
    addon.requestheaders(flow);addon.responseheaders(flow)
    assert callable(flow.response.stream)
    encoded=brotli.compress(raw)
    assert b''.join(flow.response.stream(encoded[n:n+5]) for n in range(0,len(encoded),5))==encoded
    assert flow.response.stream(b'')==b''
    assert response.raw_content is None
    assert addon.session.saved and addon.passthrough_only
    assert list(opts.allow_hosts)==[r'(?!)'] and not opts.liumo_compat
    public=json.dumps(addon.session.summary())
    assert 'PRIVATE_COMMENT' not in public and 'FAKE_TOKEN' not in public
    stored=json.loads((d/'baseline.json').read_text())
    assert 'PRIVATE_COMMENT' not in json.dumps(stored) and stored['response']['comment_items_count']==1
   finally:
    addon.done();master.shutdown()
asyncio.run(run())
print(json.dumps({'actual_component':'passed','listener_started':False,'network_requests':0,'credentials_used':False}))
'''
        result=subprocess.run([str(c.ROOT/'.venv-capture/bin/python'),'-c',code],cwd=c.ROOT,
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['actual_component'],'passed')
