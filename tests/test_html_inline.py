"""C28 constructed HTML/flow and isolated authorization; no WeChat/system edits."""

import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
from contextlib import contextmanager
from unittest.mock import Mock, patch

from test_html_static import html, isolated_mode
from test_validation import LocalTest
from validation import html_inline as h, html_static as static, html_static_session as s
from validation import compat_session as runtime
from validation.capture_session import private_write
from validation.common import ROOT
from validation.http import ProbeError


def with_scripts(source):
    return html().replace(b'</body>', source.encode() + b'</body>')


@contextmanager
def inline_mode(path):
    names = ('DIRECTORY', 'AUTHORIZATION', 'UI_READY', 'READY_STATUS', 'EXPERIMENT',
             'DUPLICATE_DIRECTORY', 'INLINE_DIRECTORY')
    before = {key: getattr(s, key) for key in names}
    try:
        with isolated_mode():
            s.DUPLICATE_DIRECTORY = path/'closed-C26'
            s.DUPLICATE_DIRECTORY.mkdir(mode=0o700)
            s.INLINE_DIRECTORY = path/'new-C28'
            s.select_inline_mode()
            yield
    finally:
        for key, value in before.items():
            setattr(s, key, value)


class HtmlInlineTests(LocalTest):
    def test_identity_failure_never_starts_node(self):
        with patch.object(h.js, 'analyze_scripts') as child:
            with self.assertRaisesRegex(ProbeError, 'identity_unverified'):
                h.analyze(html().replace(b'2247498641', b'999'))
            child.assert_not_called()

    def test_types_external_shapes_and_private_source_never_escape(self):
        data = with_scripts('''
<script>fetch('/mp/'+'appmsg_comment?token=PRIVATE_SECRET');</script>
<script type="module">await fetch(dynamic);</script>
<script type="application/json">{"PRIVATE_KEY":"PRIVATE_SECRET"}</script>
<script type="PRIVATE_TYPE">PRIVATE_SECRET</script>
<script src="https://PRIVATE_HOST.invalid/PRIVATE_PATH?token=PRIVATE_SECRET"></script>
''')
        result = h.analyze(data)
        self.assertEqual(result['script_coverage'],
            {'classic': 2, 'module': 1, 'data': 1, 'unknown_type': 1, 'external': 2, 'nomodule': 0})
        self.assertEqual(result['inline_syntax']['fetch_endpoint_candidates']['comment'], 1)
        self.assertEqual(result['external_source_shapes']['unknown_host'], 1)
        self.assertEqual(result['inline_syntax']['scripts_total'], 3)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['all_page_scripts_analyzed'])
        self.assertFalse(result['comment_channel_verified'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_rejection_shape_categories_do_not_relax_download_policy(self):
        values = {'bad\nPRIVATE':'invalid_shape', '/PRIVATE.js':'relative_source',
            'http://res.wx.qq.com/PRIVATE.js':'non_https',
            'https://PRIVATE.invalid/x.js':'unknown_host',
            'https://PRIVATE@res.wx.qq.com/x.js':'authority_rejected',
            'https://res.wx.qq.com/PRIVATE.js':'known_host_path_rejected',
            '//res.wx.qq.com/mmbizwap/public.js?PRIVATE=1':'accepted_public'}
        for value, expected in values.items():
            self.assertEqual(h.source_shape(value), expected)
            if expected != 'accepted_public':
                self.assertIsNone(static.public_script(value))

    def test_only_analyzed_inline_code_can_finish_static_scope(self):
        # Remove external element as a whole, preserving the valid article fixture.
        data = html().split(b'<script src=')[0] + b'</body></html>'
        result = h.analyze(data)
        self.assertEqual(result['status'], 'inline_syntax_observed')
        self.assertTrue(result['all_page_scripts_analyzed'])
        data = data.replace(b'</body>', b'<script type="application/json">{}</script></body>')
        self.assertEqual(h.analyze(data)['status'], 'partial')

    def test_script_limit_parser_failure_and_missing_component_are_explicit(self):
        with patch.object(h.js, 'analyze_scripts') as child:
            with self.assertRaisesRegex(ProbeError, 'script_count_limit'):
                h.analyze(with_scripts('<script></script>'*127))
            child.assert_not_called()
        result = h.analyze(with_scripts('<script>const PRIVATE = ;</script>'))
        self.assertEqual(result['inline_syntax']['status'], 'partial')
        self.assertEqual(result['status'], 'partial')
        with patch.object(h.js.shutil, 'which', return_value=None):
            result = h.analyze(html())
        self.assertEqual(result['inline_syntax']['reason'], 'parser_unavailable')

    def test_passthrough_once_and_zero_raw_source_persistence(self):
        saved = []
        subject = static.StaticSession(saved.append, lambda: True, header_diagnostics=True,
                                       equivalent_duplicates=True, inline_analysis=True)
        cb = subject.begin(200, 'text/html', 'gzip', content_types=['text/html', 'text/html'], content_type_count=2)
        raw = gzip.compress(with_scripts('<script>fetch("/mp/appmsg_comment?token=PRIVATE_SECRET")</script>'))
        self.assertEqual(cb(raw), raw); self.assertEqual(cb(b''), b'')
        self.assertTrue(subject.saved); self.assertEqual(len(saved), 1)
        self.assertEqual(subject.buffer, bytearray())
        self.assertNotIn('PRIVATE', json.dumps(saved))
        with self.assertRaises(ProbeError):
            subject.begin(200, 'text/html', '')

    def test_analysis_uses_remaining_budget_and_gate_expiry_discards_output(self):
        now = [0]; gate = [True]; saved = []
        subject = static.StaticSession(saved.append, lambda: gate[0], clock=lambda: now[0], inline_analysis=True)
        cb = subject.begin(200, 'text/html', ''); cb(html())
        def expire(raw, remaining_seconds):
            self.assertEqual(remaining_seconds, 59)
            now[0] = 61
            return {'reason': 'PRIVATE_SECRET'}
        with patch.object(h, 'analyze', side_effect=expire):
            cb(b'')
        self.assertFalse(subject.saved); self.assertEqual(saved, [])
        self.assertEqual(subject.reason, 'html_gate_closed')
        with patch.object(h.js.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE', .1)):
            result = h.analyze(html(), remaining_seconds=.1)
        self.assertEqual(result['inline_syntax']['reason'], 'parser_timeout')

    def test_make_session_deadline_is_bounded_by_system_active_window(self):
        with inline_mode(self.path):
            with patch.object(s, 'private_json', return_value={'active_deadline': 103}), patch.object(s.time, 'time', return_value=100):
                subject = s.make_session()
            self.assertLessEqual(subject.deadline - subject.clock(), 3)
            self.assertTrue(subject.inline_analysis)

    def test_new_mode_requires_fresh_grant_before_system_preflight(self):
        with inline_mode(self.path):
            rt = s.select_runtime()
            self.assertEqual(len(rt.PREVIOUS), 13)
            self.assertEqual(rt.PREVIOUS[-1], s.DUPLICATE_DIRECTORY)
            self.assertEqual(rt.WORKER_FLAG, '--html-inline-worker')
            self.assertEqual(rt.ADDON.name, 'html_inline_addon.py')
            self.assertTrue(s.review_plan()['inline_JS_AST_in_memory'])
            with patch.object(rt, 'collect_baseline') as preflight:
                with self.assertRaisesRegex(ProbeError, 'not_authorized'):
                    s.session()
                preflight.assert_not_called()
            self.assertFalse(s.DIRECTORY.exists()); self.assertFalse(s.AUTHORIZATION.exists())

    def test_grant_binds_C26_identity_and_full_recovery(self):
        with inline_mode(self.path):
            state = {'status':'closed', 'finished':True, 'recovery_completed_at':'2026-10-18T16:25:45+00:00',
                'recovery':{'verified':True, 'proxy_verified':True, 'process_stopped':True,
                    'keys_removed':True, 'trust':{'verified':True}}, 'static_summary_saved':True,
                'capture':{'body_identity_verified':True, 'matched_response_count':1}}
            p = s.DUPLICATE_DIRECTORY/'state.json'; private_write(p, state)
            proof = {'experiment':s.EXPERIMENT, 'source':'explicit_user_grant',
                'authorized_at':'2026-10-19T00:00:00+00:00', 'source_result_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'duration_seconds':180, 'cleanup_reserve_seconds':120, 'max_passive_responses':1,
                'wire_limit_bytes':4194304, 'decoded_limit_bytes':4194304, 'manual_circular_arrow_refresh_once':True,
                'in_memory_article_HTML_inspection':True, 'sanitized_public_script_sources_only':True,
                'Cookie_headers_read':False, 'raw_HTML_persisted':False, 'fixed_response_metadata':True,
                'equivalent_duplicate_Content_Type_only':True, 'inline_JS_AST_in_memory':True,
                'script_text_persisted':False, 'parser_timeout_seconds':10, 'max_script_elements':128,
                'external_source_fixed_shape_counts':True, 'stop_owned_proxy_group_with_Node_child':True}
            private_write(s.AUTHORIZATION, proof); s.authorized()
            for key, value in (('experiment', 'article_static_duplicates'), ('parser_timeout_seconds', 20),
                               ('script_text_persisted', True), ('source_result_sha256', 'wrong')):
                private_write(s.AUTHORIZATION, {**proof, key:value})
                with self.assertRaisesRegex(ProbeError, 'not_authorized'): s.authorized()
            private_write(s.AUTHORIZATION, proof); state['capture']['body_identity_verified'] = False
            private_write(p, state)
            with self.assertRaisesRegex(ProbeError, 'not_authorized'): s.authorized()

    def test_actual_mitmproxy_and_node_constructed_flow_no_network(self):
        script = '''
import gzip,json
from mitmproxy import connection,http
from validation import html_static as h
from validation.common import ROOT,SAMPLES
from validation.html_inline_addon import HtmlInlineAddon
flow=http.HTTPFlow(connection.Client(peername=('127.0.0.1',0),sockname=('127.0.0.1',0)),connection.Server(address=('mp.weixin.qq.com',443)))
flow.request=http.Request.make('GET',SAMPLES['maobidao'],headers={'Cookie':'PRIVATE_COOKIE_NEVER_READ'})
flow.response=http.Response.make(200,b'',{'Content-Type':'text/html;charset=utf-8','Content-Encoding':'gzip'})
flow.response.headers.add('Content-Type','Text/HTML;Charset="UTF-8"')
saved=[]; addon=HtmlInlineAddon(); addon.select_runtime()
addon.session=h.StaticSession(saved.append,lambda:True,header_diagnostics=True,equivalent_duplicates=True,inline_analysis=True)
addon.requestheaders(flow);addon.responseheaders(flow)
packed=gzip.compress((ROOT/'examples/pages/article-static.html').read_bytes())
assert flow.response.stream(packed)==packed and flow.response.stream(b'')==b''
assert len(saved)==1 and saved[0]['inline_syntax']['status']=='passed'
assert 'PRIVATE' not in json.dumps(saved) and not addon.session.buffer
print(json.dumps({'passed':True,'active_requests':0,'system_settings_changed':False}))
'''
        p = subprocess.run([str(ROOT/'.venv-capture/bin/python'), '-c', script],
                           cwd=ROOT, capture_output=True, text=True, check=True, timeout=20)
        self.assertTrue(json.loads(p.stdout)['passed'])

    def test_proxy_child_group_cleanup_refuses_unknown_ownership(self):
        parent = Mock(); parent.poll.return_value = 0
        with patch.object(runtime.os, 'getpgid') as identity, patch.object(runtime.os, 'killpg') as kill:
            self.assertFalse(runtime.stop_inline_group(456, parent))
            identity.assert_not_called(); kill.assert_called_once_with(456, 0)
        with patch.object(runtime.os, 'getpgid', return_value=123), patch.object(runtime.os, 'killpg') as kill:
            self.assertFalse(runtime.stop_inline_group(456))
            kill.assert_not_called()
        with patch.object(runtime.os, 'getpgid', side_effect=ProcessLookupError), patch.object(runtime.os, 'killpg') as kill:
            self.assertFalse(runtime.stop_inline_group(456))
            kill.assert_called_once_with(456, 0)
        with patch.object(runtime.os, 'getpgid', side_effect=ProcessLookupError), patch.object(runtime.os, 'killpg', side_effect=ProcessLookupError):
            self.assertTrue(runtime.stop_inline_group(456))

    def test_owned_local_process_group_is_reaped(self):
        # Real local Python parent plus Node child; not native WeChat recovery.
        code = '''import subprocess,time
subprocess.Popen(['/opt/homebrew/bin/node','-e','setInterval(()=>{},1000)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('ready',flush=True)
time.sleep(30)
'''
        p = subprocess.Popen([sys.executable, '-c', code],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            self.assertEqual(p.stdout.readline(), b'ready\n')
            self.assertTrue(runtime.stop_inline_group(p.pid, p))
            self.assertIsNotNone(p.poll())
        finally:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            if p.poll() is None: p.kill(); p.wait()
            p.stdout.close()

    def test_cli_offline_fixture_partial(self):
        for action, expected in (('plan', 0), ('fixture', 2)):
            p = subprocess.run([sys.executable, '-m', 'validation', 'html-static-inline-'+action],
                               cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(p.returncode, expected)
            out = json.loads(p.stdout)
            if action == 'plan': self.assertEqual(out['previous_system_experiments'], 13)
            else: self.assertEqual(out['inline_syntax']['status'], 'passed')
            self.assertNotIn('CONSTRUCTED_SECRET', p.stdout)
