"""Strict two-declaration recovery policy; constructed evidence only."""

import gzip
import hashlib
import json
import subprocess
from contextlib import contextmanager
from unittest.mock import Mock, patch

from test_html_static import html, isolated_mode
from test_validation import LocalTest
from validation import html_static as h, html_static_session as s
from validation.capture_session import private_write
from validation.common import ROOT
from validation.http import ProbeError


@contextmanager
def duplicate_mode(path):
    names=('DIRECTORY','AUTHORIZATION','UI_READY','READY_STATUS','EXPERIMENT','METADATA_DIRECTORY','DUPLICATE_DIRECTORY')
    before={key:getattr(s,key) for key in names}
    try:
        with isolated_mode():
            s.METADATA_DIRECTORY=path/'closed-C25';s.METADATA_DIRECTORY.mkdir(mode=0o700)
            s.DUPLICATE_DIRECTORY=path/'new-C26';s.select_duplicate_mode()
            yield
    finally:
        for key,value in before.items():setattr(s,key,value)


class DeclarationTests(LocalTest):
    def test_equal_media_charset_and_all_parameters_only(self):
        for values in (['text/html'], ['text/html','text/html'],
                ['text/html;charset=utf-8','Text/HTML; Charset="UTF-8"'],
                ['text/html; charset=utf8; p=PRIVATE','text/html; p="PRIVATE"; charset=utf-8']):
            data=h.declaration_metadata(200,values,'gzip')
            self.assertTrue(data['accepted'])
            self.assertEqual(data['relation'],'single' if len(values)==1 else 'equivalent_declarations')
            self.assertEqual(len(data['declarations']),len(values));self.assertNotIn('PRIVATE',json.dumps(data))

    def test_conflicting_unknown_missing_charset_and_excess_declarations_stop(self):
        cases=([ 'text/html;charset=utf-8','text/html'],
               ['text/html; p=PRIVATE','text/html; p=private'],
               ['text/html;charset=utf-8','text/html;charset=gbk'],
               ['text/html','application/json'],['text/html','text/html;broken'],
               ['text/html; charset=utf-8; charset=utf-8','text/html'],[],['text/html']*3)
        for values in cases:
            data=h.declaration_metadata(200,values,'gzip')
            self.assertFalse(data['accepted'],values)
            self.assertNotIn('PRIVATE',json.dumps(data))

    def test_legacy_double_header_rejection_preserved_and_new_stream_has_no_raw_values(self):
        values=['text/html; charset=utf-8; key=PRIVATE','text/html; key="PRIVATE"; charset=UTF8']
        old=h.StaticSession(Mock(),lambda:True,header_diagnostics=True)
        with self.assertRaisesRegex(ProbeError,'content_type_rejected'):
            old.begin(200,', '.join(values),'gzip',content_type_count=2)
        self.assertEqual(old.summary()['response_metadata']['media'],'ambiguous')
        saved=[];subject=h.StaticSession(saved.append,lambda:True,header_diagnostics=True,equivalent_duplicates=True)
        cb=subject.begin(200,', '.join(values),'gzip',content_type_count=2,content_types=values)
        packed=gzip.compress(html());self.assertEqual(cb(packed),packed);self.assertEqual(cb(b''),b'')
        self.assertTrue(subject.saved);self.assertEqual(saved[0]['response_metadata']['relation'],'equivalent_declarations')
        self.assertNotIn('PRIVATE',json.dumps(saved))

    def test_equal_header_does_not_bypass_body_identity_or_size(self):
        saved=[];subject=h.StaticSession(saved.append,lambda:True,header_diagnostics=True,equivalent_duplicates=True)
        cb=subject.begin(200,'text/html','',content_type_count=2,content_types=['text/html','text/html'])
        cb(html().replace(b'2247498641',b'999'));cb(b'')
        self.assertEqual(subject.reason,'html_identity_unverified');self.assertEqual(saved,[])
        subject=h.StaticSession(saved.append,lambda:True,header_diagnostics=True,equivalent_duplicates=True)
        cb=subject.begin(200,'text/html','',content_type_count=2,content_types=['text/html','text/html'])
        with patch.object(h,'LIMIT',10):cb(b'x'*11)
        self.assertEqual(subject.reason,'html_wire_size_limit');self.assertEqual(saved,[])

    def test_actual_mitmproxy_double_headers_without_network(self):
        script='''
import gzip,json
from importlib.metadata import version
from mitmproxy import connection,http
from validation import html_static as h
from validation.common import ROOT,SAMPLES
from validation.html_static_duplicates_addon import HtmlStaticDuplicatesAddon
raw=(ROOT/'examples/pages/article-static.html').read_bytes()
output=[]
for other,expected in (('Text/HTML; Charset="UTF-8"',True),('application/json',False)):
    flow=http.HTTPFlow(connection.Client(peername=('127.0.0.1',0),sockname=('127.0.0.1',0)),connection.Server(address=('mp.weixin.qq.com',443)))
    flow.request=http.Request.make('GET',SAMPLES['maobidao'],headers={'Cookie':'PRIVATE_NEVER_READ'})
    flow.response=http.Response.make(200,b'',{'Content-Type':'text/html;charset=utf-8','Content-Encoding':'gzip'})
    flow.response.headers.add('Content-Type',other)
    assert len(flow.response.headers.get_all('content-type'))==2
    saved=[];addon=HtmlStaticDuplicatesAddon();addon.select_runtime()
    addon.session=h.StaticSession(saved.append,lambda:True,header_diagnostics=True,equivalent_duplicates=True)
    addon.requestheaders(flow);addon.responseheaders(flow)
    if expected:
        packed=gzip.compress(raw)
        assert flow.response.stream(packed)==packed and flow.response.stream(b'')==b''
        assert len(saved)==1 and 'PRIVATE' not in json.dumps(saved)
    else:assert flow.response.stream is True and not saved
    output.append(addon.session.summary()['response_metadata']['relation'])
print(json.dumps({'mitmproxy':version('mitmproxy'),'relations':output,'network_requests':0,'system_settings_changed':False}))
'''
        result=subprocess.run([str(ROOT/'.venv-capture/bin/python'),'-c',script],cwd=ROOT,capture_output=True,text=True,timeout=20,check=True)
        data=json.loads(result.stdout)
        self.assertEqual(data['relations'],['equivalent_declarations','unacceptable_declaration'])
        self.assertEqual(data['network_requests'],0)


class ModeTests(LocalTest):
    def test_new_scope_twelve_locks_and_no_implicit_authorization(self):
        with duplicate_mode(self.path):
            rt=s.select_runtime();self.assertEqual(len(rt.PREVIOUS),12)
            self.assertEqual(rt.PREVIOUS[-1],s.METADATA_DIRECTORY)
            self.assertEqual(rt.WORKER_FLAG,'--html-static-duplicates-worker')
            self.assertEqual(rt.ADDON.name,'html_static_duplicates_addon.py')
            self.assertTrue(s.review_plan()['equivalent_duplicate_Content_Type_only'])
            with patch.object(rt,'collect_baseline') as preflight:
                with self.assertRaisesRegex(ProbeError,'not_authorized'):s.session()
                preflight.assert_not_called()
            self.assertFalse(s.DIRECTORY.exists());self.assertFalse(s.AUTHORIZATION.exists())

    def test_C26_grant_binds_C25_two_header_rejection(self):
        with duplicate_mode(self.path):
            state={'status':'closed','finished':True,'recovery_completed_at':'2026-10-18T16:11:52+00:00',
                'recovery':{'verified':True,'proxy_verified':True,'process_stopped':True,'keys_removed':True,'trust':{'verified':True}},
                'capture':{'reason':'html_content_type_rejected','matched_response_count':1,
                    'response_metadata':{'http_status':200,'content_type_count':2,'media':'ambiguous','accepted':False}},'static_summary_saved':False}
            p=s.METADATA_DIRECTORY/'state.json';private_write(p,state)
            proof={'experiment':s.EXPERIMENT,'source':'explicit_user_grant','authorized_at':'2026-10-18T16:14:00+00:00',
                'source_result_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'duration_seconds':180,'cleanup_reserve_seconds':120,
                'max_passive_responses':1,'wire_limit_bytes':4194304,'decoded_limit_bytes':4194304,'manual_circular_arrow_refresh_once':True,
                'in_memory_article_HTML_inspection':True,'sanitized_public_script_sources_only':True,'Cookie_headers_read':False,'raw_HTML_persisted':False,
                'fixed_response_metadata':True,'equivalent_duplicate_Content_Type_only':True}
            private_write(s.AUTHORIZATION,proof);s.authorized()
            for key,value in (('experiment','article_static_metadata'),('equivalent_duplicate_Content_Type_only',False)):
                private_write(s.AUTHORIZATION,{**proof,key:value})
                with self.assertRaisesRegex(ProbeError,'not_authorized'):s.authorized()
            private_write(s.AUTHORIZATION,proof);state['capture']['response_metadata']['content_type_count']=1;private_write(p,state)
            with self.assertRaisesRegex(ProbeError,'not_authorized'):s.authorized()

    def test_new_plan_and_fixture_CLI_are_offline(self):
        for action in ('plan','fixture'):
            result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','validation','html-static-duplicates-'+action],cwd=ROOT,capture_output=True,text=True,check=True)
            data=json.loads(result.stdout)
            self.assertNotIn('SECRET',result.stdout)
            if action=='plan':self.assertEqual(data['previous_system_experiments'],12)
            else:self.assertEqual(data['response_metadata']['relation'],'equivalent_declarations')
