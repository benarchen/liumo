"""C22 fixed public categories and independent scope; no live system experiment."""

import copy
import hashlib
import io
import json
import subprocess
import sys
from contextlib import contextmanager, redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from test_validation import LocalTest
from validation import comment_baseline as c, compat_session as runtime
from validation.capture_session import private_write
from validation.comment_refresh_addon import CommentRefreshAddon
from validation.http import ProbeError


@contextmanager
def isolated_mode():
    names=('DIRECTORY','AUTHORIZATION','UI_READY','READY_STATUS','EXPERIMENT','BASELINE_DIRECTORY','REFRESH_DIRECTORY')
    runtime_names=('DIRECTORY','PREVIOUS','UI_READY','EXPERIMENT','ADDON','READY_STATUS','WORKER_FLAG','RUN_SLUG')
    with patch.multiple(c,**{n:getattr(c,n) for n in names}), \
            patch.multiple(runtime,**{n:getattr(runtime,n) for n in runtime_names}):
        yield


def address(**changes):
    fields={'action':'getcomment','__biz':c.BIZ,'appmsgid':c.IDENTITY['appmsgid'],'idx':'1','comment_id':'42'}
    for key,value in changes.items():
        if value is None:fields.pop(key,None)
        else:fields[key]=value
    return 'https://mp.weixin.qq.com/mp/appmsg_comment?'+urlencode(fields)


class MatchTests(LocalTest):
    def test_public_categories_include_missing_fields_and_never_echo_values(self):
        cases=({},'public_shape_matches'),({'action':'SECRET_ACTION'},'action_other'), \
            ({'__biz':None},'account_missing'),({'__biz':'SECRET_OTHER'},'account_other'), \
            ({'appmsgid':None},'article_missing'),({'appmsgid':'SECRET_OTHER'},'article_other'), \
            ({'idx':None},'idx_missing'),({'idx':'2'},'idx_other'), \
            ({'comment_id':None},'comment_id_invalid'),({'comment_id':'SECRET'},'comment_id_invalid')
        for changes,expected in cases:
            result=c.comment_match_category(address(**changes),'GET')
            self.assertEqual(result,expected)
            self.assertIn('comment_requests_'+result,c.MATCH_COUNTERS)
            self.assertNotIn('SECRET',result)
        self.assertEqual(c.comment_match_category(address(),'POST'),'non_GET')
        self.assertEqual(c.comment_match_category(address()+'&idx=1','GET'),'query_ambiguous')
        self.assertEqual(c.comment_match_category(address()+'&broken','GET'),'query_invalid')
        self.assertEqual(c.comment_match_category(address(comment_id='x\r\nsecret'),'GET'),'query_invalid')
        for value in ('https://other.invalid/mp/appmsg_comment?SECRET','https://mp.weixin.qq.com/unknown?SECRET',
                address().replace('https:','http:')):
            self.assertIsNone(c.comment_match_category(value,'GET'))

    def test_secret_query_values_are_not_decoded_and_full_capture_gates_unchanged(self):
        seen=[]
        original=c.unquote_plus
        def decode(value):
            seen.append(value)
            return original(value)
        with patch.object(c,'unquote_plus',side_effect=decode):
            result=c.comment_match_category(address()+'&key=SECRET_ENCODED&arbitrary=OTHER_SECRET','GET')
        self.assertEqual(result,'public_shape_matches')
        self.assertNotIn('SECRET_ENCODED',seen);self.assertNotIn('OTHER_SECRET',seen)
        subject=c.CommentBaselineSession(writer=Mock(),gate=lambda:True)
        seen.clear()
        with patch.object(c,'unquote_plus',side_effect=decode):
            result=subject.matching(address()+'&unknown=SECRET_UNLISTED','GET',200)
        self.assertEqual(result['additional_query_count'],1)
        self.assertNotIn('SECRET_UNLISTED',seen)
        duplicate=address()+'&key=SECRET&key=SECOND'
        self.assertEqual(c.comment_match_category(duplicate,'GET'),'public_shape_matches')
        with self.assertRaises(ProbeError):subject.matching(duplicate,'GET',200)
        subject.writer.assert_not_called()

    def test_addon_only_fixed_counts_no_unmatched_headers_or_body_reads(self):
        class NoRead:
            def get(self,*_):raise AssertionError('unmatched headers read')
            def get_all(self,*_):raise AssertionError('unmatched headers read')
        addon=CommentRefreshAddon()
        self.assertIsNone(addon.session)
        addon.session=c.CommentBaselineSession(writer=Mock(),gate=lambda:True)
        addon.session.matching=Mock(side_effect=AssertionError('unmatched private query parser entered'))
        for changes in ({'idx':None},{'__biz':'OTHER_ACCOUNT'},{'action':'OTHER_ACTION'}):
            flow=SimpleNamespace(request=SimpleNamespace(url=address(**changes),method='GET',headers=NoRead()),
                response=SimpleNamespace(status_code=200,headers=NoRead(),stream=False),metadata={})
            addon.requestheaders(flow);addon.responseheaders(flow)
            self.assertIs(flow.request.stream,True);self.assertIs(flow.response.stream,True)
        addon.session.writer.assert_not_called()
        self.assertEqual(addon.diagnostics['comment_responses_idx_missing'],1)
        self.assertEqual(addon.diagnostics['comment_requests_account_other'],1)
        text=json.dumps(addon.diagnostics)
        self.assertNotIn('OTHER_ACCOUNT',text);self.assertNotIn('OTHER_ACTION',text)
        before=dict(addon.diagnostics);addon.session.stop()
        addon.observe_shape(flow,'requests')
        self.assertEqual(before,addon.diagnostics)

    def test_addon_success_reuses_one_bounded_byte_preserving_callback(self):
        rows=[];addon=CommentRefreshAddon()
        addon.session=c.CommentBaselineSession(writer=rows.append,gate=lambda:True)
        headers={name:'' for name in (*c.HEADER_FIELDS,'Cookie','Referer')}
        headers['Cookie']='appmsg_token=PRIVATE_TOKEN; extra=PRIVATE_OTHER'
        class ResponseHeaders:
            def get_all(self,_):return []
            def get(self,*_):return ''
        flow=SimpleNamespace(request=SimpleNamespace(url=address(),method='GET',headers=headers),
            response=SimpleNamespace(status_code=200,headers=ResponseHeaders(),stream=False),metadata={})
        addon.requestheaders(flow);addon.responseheaders(flow)
        raw=json.dumps({'base_resp':{'ret':0},'elected_comment':[{'content':'PRIVATE_COMMENT'}]}).encode()
        self.assertEqual(flow.response.stream(raw),raw)
        self.assertEqual(flow.response.stream(b''),b'')
        self.assertTrue(addon.session.saved);self.assertEqual(len(rows),1)
        self.assertNotIn('PRIVATE_COMMENT',json.dumps(rows))
        self.assertNotIn('PRIVATE',json.dumps(addon.diagnostics))
        self.assertEqual(addon.diagnostics['comment_responses_public_shape_matches'],1)


class ModeTests(LocalTest):
    def test_C22_authorization_binds_closed_C21_and_refuses_old_grant(self):
        with isolated_mode():
            c.REFRESH_DIRECTORY=self.path/'refresh';c.BASELINE_DIRECTORY=self.path/'baseline'
            c.BASELINE_DIRECTORY.mkdir(mode=0o700)
            source=c.BASELINE_DIRECTORY/'state.json'
            old={'status':'closed','finished':True,'recovery_completed_at':'2026-10-18T12:05:36+00:00',
                'comment_baseline_observed':False,'capture':{'matched_response_count':0},
                'recovery':{'verified':True,'proxy_verified':True,'process_stopped':True,'keys_removed':True,
                            'trust':{'verified':True}}}
            private_write(source,old);c.select_refresh_mode()
            proof={'experiment':'c22_comment_refresh','source':'explicit_user_grant',
                'authorized_at':'2026-10-18T13:00:00+00:00','source_result_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'max_passive_responses':1,'wire_limit_bytes':c.LIMIT,'decoded_limit_bytes':c.LIMIT,
                'full_single_Cookie_field_private':True,'duration_seconds':180,'cleanup_reserve_seconds':120,
                'manual_menu_refresh_once':True,'fixed_comment_match_counters':True}
            private_write(c.AUTHORIZATION,proof);c.authorized()
            for change in ({'experiment':'c21_comment_baseline'},{'manual_menu_refresh_once':False},
                    {'source_result_sha256':'bad'},{'authorized_at':'2026-10-18T12:00:00+00:00'}):
                private_write(c.AUTHORIZATION,{**proof,**change})
                with self.assertRaises(ProbeError):c.authorized()
            private_write(c.AUTHORIZATION,proof)
            old['recovery']['trust']['verified']=False;private_write(source,old)
            proof['source_result_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();private_write(c.AUTHORIZATION,proof)
            with self.assertRaises(ProbeError):c.authorized()
            self.assertFalse(c.DIRECTORY.exists())

    def test_selector_nine_locks_and_old_mode_restored(self):
        original=c.EXPERIMENT
        with isolated_mode():
            c.select_refresh_mode();rt=c.select_runtime()
            self.assertEqual(len(rt.PREVIOUS),9)
            self.assertEqual(rt.PREVIOUS[-1],c.BASELINE_DIRECTORY)
            self.assertEqual(rt.WORKER_FLAG,'--comment-refresh-worker')
            self.assertEqual(rt.EXPERIMENT,'comment_refresh')
            good={'status':'closed','finished':True,'recovery':{'verified':True,'proxy_verified':True,
                'process_stopped':True,'keys_removed':True,'trust':{'verified':True}}}
            with patch.object(rt.anchor,'previous_closed'),patch.object(rt,'private_json',return_value=good):
                rt.previous_closed()
            bad=copy.deepcopy(good);bad['recovery']['keys_removed']=False
            with patch.object(rt.anchor,'previous_closed'),patch.object(rt,'private_json',return_value=bad):
                with self.assertRaisesRegex(ProbeError,'comment_refresh_previous'):rt.previous_closed()
        self.assertEqual(c.EXPERIMENT,original)

    def test_closed_new_directory_cannot_start_or_touch_preflight(self):
        with isolated_mode():
            c.select_refresh_mode();c.DIRECTORY=self.path
            rt=c.select_runtime()
            with patch.object(c,'authorized'),patch.object(rt,'collect_baseline') as preflight:
                with self.assertRaisesRegex(ProbeError,'session_already_exists'):c.session()
                preflight.assert_not_called()

    def test_observation_exports_fixed_numeric_counts_only(self):
        with isolated_mode():
            c.select_refresh_mode();c.DIRECTORY=self.path
            private_write(self.path/'capture.json',{'diagnostics':{
                'comment_requests_public_shape_matches':2,'ARBITRARY_SECRET':99}})
            fake=SimpleNamespace(observe=lambda phase:{'phase':phase})
            with patch.object(c,'select_runtime',return_value=fake):
                result=c.observe('after_refresh')
                self.assertEqual(result['comment_match_counters']['comment_requests_public_shape_matches'],2)
                self.assertNotIn('ARBITRARY',json.dumps(result))
                self.assertEqual(set(result['comment_match_counters']),c.MATCH_COUNTERS)
                private_write(self.path/'capture.json',{'diagnostics':{'comment_requests_non_GET':True}})
                with self.assertRaises(ProbeError):c.observe('after_refresh')

    def test_readonly_plan_CLI_and_fixed_failure_output(self):
        result=subprocess.run([str(c.ROOT/'.venv/bin/python'),'-m','validation','comment-refresh-plan'],
            cwd=c.ROOT,capture_output=True,text=True,check=True)
        data=json.loads(result.stdout)
        self.assertEqual(data['experiment'],'c22_comment_refresh')
        self.assertTrue(data['manual_menu_refresh_once']);self.assertFalse(data['executed'])
        from validation.__main__ import main
        with isolated_mode(),patch.object(sys,'argv',['validation','comment-refresh-session']), \
                patch.object(c,'session',side_effect=ProbeError('comment_refresh_previous_unverified')):
            output=io.StringIO()
            with redirect_stdout(output):self.assertEqual(main(),2)
            self.assertEqual(json.loads(output.getvalue())['reason'],'comment_refresh_previous_unverified')
