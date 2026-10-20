"""C25 headers and separate authorization; C24 live receipts never modified."""

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
def metadata_mode(path):
    names=('DIRECTORY','AUTHORIZATION','UI_READY','READY_STATUS','EXPERIMENT','STATIC_DIRECTORY','METADATA_DIRECTORY')
    values={key:getattr(s,key) for key in names}
    try:
        with isolated_mode():
            s.STATIC_DIRECTORY=path/'closed-C24'
            s.STATIC_DIRECTORY.mkdir(mode=0o700)
            s.METADATA_DIRECTORY=path/'new-C25'
            s.select_metadata_mode()
            yield
    finally:
        for key,value in values.items():setattr(s,key,value)


class HeaderTests(LocalTest):
    def test_legal_formats_and_old_false_negative_are_reproducible(self):
        samples=('text/html;charset=utf-8','Text/HTML;Charset="utf-8"',
                 'text/html; charset="utf-8"','text/html;charset=UTF-8',
                 'text/html; charset=utf8','text/html; charset=utf_8',
                 'text/html; charset="utf-8"; example="PRIVATE;VALUE"')
        for value in samples:
            data=h.response_metadata(200,value,'gzip')
            self.assertTrue(data['accepted'],value)
            self.assertEqual(data['media'],'html')
            self.assertNotIn('PRIVATE',json.dumps(data))
        subject=h.StaticSession(Mock(),lambda:True)
        with self.assertRaisesRegex(ProbeError,'content_type_rejected'):
            subject.begin(200,samples[-1],'gzip')
        subject=h.StaticSession(Mock(),lambda:True,header_diagnostics=True)
        subject.begin(200,samples[-1],'gzip')
        self.assertEqual(subject.summary()['response_metadata']['parameter_count'],2)

    def test_missing_ambiguous_malformed_non_UTF8_and_non_HTML_are_rejected(self):
        for value,count in (('',1),('text/html',0),('text/html',2),('text/html',True),
                ('text/html; charset=gbk',1),('application/json',1),('application/xhtml+xml',1),
                ('text/html; charset=utf-8; charset=gbk',1),('text/html; charset=utf-8; charset=utf-8',1),
                ('text/html; charset="utf-8',1),('text/html\r\nX-Secret: PRIVATE',1),
                ('text/html;'+ ';'.join('p'+str(i)+'=PRIVATE' for i in range(17)),1)):
            data=h.response_metadata(200,value,'identity',count)
            self.assertFalse(data['accepted'],(value,count))
            self.assertNotIn('PRIVATE',json.dumps(data))
        self.assertFalse(h.response_metadata(True,'text/html','')['accepted'])
        self.assertFalse(h.response_metadata(200,'text/html','PRIVATE_ENCODING')['accepted'])

    def test_failure_and_success_summary_retain_only_fixed_metadata(self):
        subject=h.StaticSession(Mock(),lambda:True,header_diagnostics=True)
        with self.assertRaises(ProbeError):
            subject.begin(200,'application/json; key=PRIVATE_SECRET','')
        meta=subject.summary()['response_metadata']
        self.assertEqual(meta['media'],'json');self.assertEqual(meta['http_status'],200)
        self.assertNotIn('PRIVATE',json.dumps(subject.summary()))
        rows=[];subject=h.StaticSession(rows.append,lambda:True,header_diagnostics=True)
        cb=subject.begin(200,'text/html; charset=utf8; key="PRIVATE_SECRET"','')
        cb(html());cb(b'')
        self.assertTrue(subject.saved);self.assertTrue(rows[0]['response_metadata']['accepted'])
        self.assertNotIn('PRIVATE_SECRET',json.dumps(rows))

    def test_duplicate_header_count_stops_before_body_without_cookie_read(self):
        from validation.html_static_addon import HtmlStaticAddon
        from types import SimpleNamespace
        from validation.common import SAMPLES
        class Headers:
            def get_all(self,key):
                assert key=='content-type'
                return ['text/html','application/json']
            def get(self,key,default=''):
                assert key in ('content-type','content-encoding')
                return 'text/html' if key=='content-type' else ''
        flow=SimpleNamespace(request=SimpleNamespace(url=SAMPLES['maobidao'],method='GET',headers=Mock()),
            response=SimpleNamespace(status_code=200,headers=Headers(),stream=False),metadata={})
        addon=HtmlStaticAddon();addon.session=h.StaticSession(Mock(),lambda:True,header_diagnostics=True)
        addon.responseheaders(flow)
        self.assertIs(flow.response.stream,True);self.assertTrue(addon.session.stopped)
        self.assertEqual(addon.session.summary()['response_metadata']['media'],'ambiguous')
        flow.request.headers.get.assert_not_called();addon.session.writer.assert_not_called()


class ModeTests(LocalTest):
    def test_C25_new_directory_eleven_locks_and_missing_grant(self):
        with metadata_mode(self.path):
            rt=s.select_runtime()
            self.assertEqual(len(rt.PREVIOUS),11)
            self.assertEqual(rt.PREVIOUS[-1],s.STATIC_DIRECTORY)
            self.assertEqual(rt.WORKER_FLAG,'--html-static-metadata-worker')
            self.assertEqual(rt.ADDON.name,'html_static_metadata_addon.py')
            from validation.html_static_metadata_addon import HtmlStaticMetadataAddon
            addon=HtmlStaticMetadataAddon();addon.select_runtime()
            with patch.object(s,'authorized'):
                self.assertTrue(addon.make_session().header_diagnostics)
            plan=s.review_plan();self.assertTrue(plan['fixed_response_metadata'])
            self.assertTrue(plan['requires_fresh_authorization_bound_to_closed_C24'])
            with self.assertRaisesRegex(ProbeError,'not_authorized'):s.authorized()
            with patch.object(rt,'collect_baseline') as preflight:
                with self.assertRaisesRegex(ProbeError,'not_authorized'):s.session()
                preflight.assert_not_called()
            self.assertFalse(s.DIRECTORY.exists());self.assertFalse(s.AUTHORIZATION.exists())

    def test_C25_grant_binds_closed_C24_and_rejects_old_grant_or_changed_receipt(self):
        with metadata_mode(self.path):
            state={'status':'closed','finished':True,'recovery_completed_at':'2026-10-18T15:55:47+00:00',
                'recovery':{'verified':True,'proxy_verified':True,'process_stopped':True,'keys_removed':True,'trust':{'verified':True}},
                'capture':{'reason':'html_content_type_rejected','matched_response_count':1},'static_summary_saved':False}
            private_write(s.STATIC_DIRECTORY/'state.json',state)
            proof={'experiment':s.EXPERIMENT,'source':'explicit_user_grant','authorized_at':'2026-10-18T16:00:00+00:00',
                'source_result_sha256':hashlib.sha256((s.STATIC_DIRECTORY/'state.json').read_bytes()).hexdigest(),
                'duration_seconds':180,'cleanup_reserve_seconds':120,'max_passive_responses':1,
                'wire_limit_bytes':4194304,'decoded_limit_bytes':4194304,'manual_circular_arrow_refresh_once':True,
                'in_memory_article_HTML_inspection':True,'sanitized_public_script_sources_only':True,
                'Cookie_headers_read':False,'raw_HTML_persisted':False,'fixed_response_metadata':True}
            private_write(s.AUTHORIZATION,proof);s.authorized()
            for key,value in (('experiment','article_static'),('fixed_response_metadata',False),('max_passive_responses',2)):
                private_write(s.AUTHORIZATION,{**proof,key:value})
                with self.assertRaisesRegex(ProbeError,'not_authorized'):s.authorized()
            private_write(s.AUTHORIZATION,proof)
            state['capture']['reason']='different';private_write(s.STATIC_DIRECTORY/'state.json',state)
            with self.assertRaisesRegex(ProbeError,'not_authorized'):s.authorized()

    def test_readonly_C25_cli_and_C24_mode_unchanged_in_new_processes(self):
        for prefix in ('html-static','html-static-metadata'):
            result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','validation',prefix+'-plan'],cwd=ROOT,
                capture_output=True,text=True,check=True)
            data=json.loads(result.stdout)
            self.assertEqual(data['experiment'],'article_static_metadata' if prefix.endswith('metadata') else 'article_static')
            self.assertFalse(data['executed'])
