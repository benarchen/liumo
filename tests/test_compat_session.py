"""C16 lifecycle tests: system operations are constructed, not device evidence."""

import copy
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_validation import LocalTest
from test_anchor_scope import ConstructedNative
from test_capture_session import baseline
from validation import compat_session as s
from validation.http import ProbeError


class Native(ConstructedNative):
    def __init__(self, failure=None):
        super().__init__(failure)
        self.plan = {'baseline': baseline(), 'keys': {n: 'hash' for n in s.KEYS}, 'active_deadline': 10000}
        self.current = dict(self.plan['baseline']['https_proxy'])

    def snapshot(self): return self.plan['baseline']
    def proxy(self): return self.current
    def set_proxy(self, value):
        self.events.append(('proxy', value))
        self.current = dict(value)


class LifecycleTests(LocalTest):
    def setUp(self):
        super().setUp()
        self.saved = []
        self.save = lambda state: self.saved.append(copy.deepcopy(state))
        self.window = SimpleNamespace(guard=lambda n=5: n, timeout=lambda n=4: n)

    def recover(self, native, state, **kwargs):
        with patch.object(s, 'stop_process', return_value=True), patch.object(s, 'delete_keys', return_value=True):
            return s.recover(native, state, kwargs.get('save', self.save))

    def run_evaluation(self, failure=None, control_failure=False, window=None, save=None):
        native, state = Native(failure), {'capture_disabled': False, 'finished': False}
        (self.path / 'capture.json').touch(mode=0o600)
        (self.path / 'FINISH').touch(mode=0o600)
        process = SimpleNamespace(pid=1234, poll=lambda: None)
        def control(*_args):
            if control_failure: raise ProbeError('diagnostic_control_unverified')
        with patch.object(s, 'DIRECTORY', self.path), patch.object(s, 'digest', return_value='hash'), \
                patch.object(s, 'verify_diagnostic_control', side_effect=control):
            try:
                s.evaluate(native, state, save or self.save, window or self.window, lambda: process)
            except (ProbeError, OSError):
                pass
            self.recover(native, state)
        return native, state

    def test_full_constructed_scope_control_write_ahead_and_recovery(self):
        native, state = self.run_evaluation()
        self.assertTrue(state['installed_matrix_passed'])
        self.assertEqual(len(state['after']), 17)
        self.assertEqual(state['reason'], 'compat_observation_finished')
        self.assertTrue(state['recovery']['verified'])
        self.assertTrue(any(row.get('proxy_attempted') for row in self.saved))
        self.assertFalse(native.trusted)
        self.assertEqual(native.current, baseline()['https_proxy'])

    def test_unknown_controls_partial_install_and_scope_escape_never_become_ready(self):
        for failure in (('unconstrained', 'target'), ('before', 'target'), 'partial_install', 'scope_escape'):
            native, state = self.run_evaluation(failure)
            self.assertFalse(any(row.get('status') == 'ready_refresh_maobidao_article_for_compatibility' for row in self.saved))
            self.assertFalse(state.get('proxy_attempted'))
            self.assertFalse(native.trusted)

    def test_control_failure_revokes_restores_and_never_announces_ready(self):
        native, state = self.run_evaluation(control_failure=True)
        self.assertTrue(state['proxy_attempted'])
        self.assertTrue(state['recovery']['verified'])
        self.assertFalse(any(row.get('status') == 'ready_refresh_maobidao_article_for_compatibility' for row in self.saved))

    def test_budget_parent_cancel_and_write_ahead_failure_stop_and_recover(self):
        for failure in ('budget', 'parent', 'journal'):
            def guard(n=5):
                if failure != 'journal': raise ProbeError('compat_cleanup_reserve_reached' if failure == 'budget' else 'session_parent_closed_or_cancelled')
                return n
            def save(state):
                if state.get('trust_attempted'): raise OSError('constructed journal unavailable')
            native, state = self.run_evaluation(window=SimpleNamespace(guard=guard, timeout=guard), save=save)
            self.assertFalse(any(e[0] == 'install' for e in native.events))
            self.assertFalse(native.trusted)

    def test_recovery_preserves_external_proxy_and_continues_after_log_failure(self):
        native = Native()
        native.current = {**s.APPLIED, 'Server': 'localhost', 'Port': '7000'}
        state = {'proxy_attempted': True, 'trust_attempted': True}
        result = self.recover(native, state, save=Mock(side_effect=OSError('disk')))
        self.assertFalse(result['verified'])
        self.assertTrue(result['safe_to_stop'])
        self.assertTrue(result['process_stopped'])
        self.assertTrue(result['keys_removed'])
        self.assertTrue(state['journal_write_failed'])
        self.assertEqual(native.current['Port'], '7000')
        self.assertIn(('revoke',), native.events)

    def test_proxy_unknown_keeps_process_and_keys_but_still_revokes(self):
        native = Native()
        native.proxy = Mock(side_effect=ProbeError('unknown'))
        state = {'proxy_attempted': True, 'trust_attempted': True}
        with patch.object(s, 'stop_process') as stop, patch.object(s, 'delete_keys') as remove:
            result = s.recover(native, state, self.save)
        stop.assert_not_called()
        remove.assert_not_called()
        self.assertFalse(result['verified'])
        self.assertIn(('revoke',), native.events)

    def test_unknown_revocation_and_live_process_prevent_success(self):
        native = Native('recovery_failure')
        state = {'trust_attempted': True}
        self.assertFalse(self.recover(native, state)['verified'])
        with patch.object(s, 'stop_process', return_value=False), patch.object(s, 'delete_keys') as remove:
            result = s.recover(Native(), {}, self.save)
            self.assertFalse(result['keys_removed'])
            self.assertFalse(result['verified'])
            remove.assert_not_called()

    def test_both_clocks_and_real_parent_EOF(self):
        read_fd, write_fd = os.pipe()
        mono, wall = [100.], [1000.]
        try:
            window = s.Window(read_fd, 1180, monotonic=lambda: mono[0], wall=lambda: wall[0])
            self.assertEqual(window.guard(30), 30)
            mono[0] = 131
            with self.assertRaises(ProbeError): window.guard(30)
            mono[0], wall[0] = 100, 1031
            with self.assertRaises(ProbeError): window.guard(30)
            wall[0] = 1000
            os.close(write_fd)
            write_fd = None
            with self.assertRaisesRegex(ProbeError, 'parent'): window.guard(1)
        finally:
            os.close(read_fd)
            if write_fd is not None: os.close(write_fd)

    def test_closed_recovery_makes_no_system_calls(self):
        state = {'finished': True, 'recovery': {'verified': True}}
        with patch.object(s, 'load_plan', return_value={}), patch.object(s, 'locks') as lock, \
                patch.object(s, 'private_json', return_value=state), patch.object(s, 'Native') as native, \
                patch.object(s, 'DIRECTORY', self.path):
            (self.path / 'state.json').touch(mode=0o600)
            self.assertEqual(s.manual_recover()['status'], 'already_closed_no_changes')
        native.assert_not_called()

    def test_read_only_preflight_rejection_leaves_fixed_directory_unused(self):
        current = self.path / 'one-use'
        with patch.object(s, 'DIRECTORY', current), patch.object(s, 'previous_closed'), \
                patch.object(s, 'check_private'), patch.object(s, 'collect_baseline', side_effect=ProbeError('preflight_system_authorization_unavailable')), \
                patch.object(s, 'generate') as generate, patch.object(s.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ProbeError, 'authorization'): s.session()
        generate.assert_not_called()
        popen.assert_not_called()
        self.assertFalse(current.exists())

    def test_changed_key_and_symlink_preserved_and_process_PID_identity_guard(self):
        directory = self.path / 'mitmproxy'
        directory.mkdir(mode=0o700)
        for name in s.KEYS:
            path = directory / name
            path.write_bytes(b'private test fixture')
            path.chmod(0o600)
        plan = {'keys': {n: s.digest(directory / n) for n in s.KEYS}}
        (directory / s.KEYS[0]).write_bytes(b'changed owner data')
        with patch.object(s, 'DIRECTORY', self.path):
            self.assertFalse(s.delete_keys(plan))
            self.assertEqual((directory / s.KEYS[0]).read_bytes(), b'changed owner data')
            (directory / s.KEYS[1]).symlink_to(directory / s.KEYS[0])
            with self.assertRaises(ProbeError): s.delete_keys(plan)
        response = SimpleNamespace(returncode=0, stdout=b'501 /some/other/process')
        with patch.object(s.subprocess, 'run', return_value=response), patch.object(s.os, 'kill') as kill:
            self.assertFalse(s.stop_process(None, {'mode': 'upstream:http://127.0.0.1:7897'}, {'proxy_pid': 1234}))
        kill.assert_not_called()
        self.assertFalse(s.stop_process(None, {}, {'proxy_start_attempted': True}))

    def test_observation_requires_live_control_and_preserves_fixed_counter_schema(self):
        state = {'status': 'ready_refresh_maobidao_article_for_compatibility', 'finished': False,
                 'capture_disabled': False, 'diagnostic_control': {'status': 'https_response_observed'}}
        capture = {'running': True, 'status': 'open', 'passthrough_only': False,
                   'diagnostics': {'control_target_requests_seen': 1, 'control_target_responses_seen': 1,
                                   'private_url': 'not exported'}}
        plan = {'active_deadline': 1060}
        with patch.object(s, 'DIRECTORY', self.path), patch.object(s, 'load_plan', return_value=plan), \
                patch.object(s.time, 'time', return_value=1000), \
                patch.object(s, 'private_json', side_effect=lambda p: state if p.name == 'state.json' else capture):
            self.assertNotIn('private_url', s.observe('before_refresh')['counters'])
            capture['diagnostics']['article_like_requests_seen'] = True
            with self.assertRaisesRegex(ProbeError, 'counters'): s.observe('after_refresh')
            del capture['diagnostics']['article_like_requests_seen']
            state['capture_disabled'] = True
            with self.assertRaisesRegex(ProbeError, 'not_running'): s.observe('after_refresh')
            state['capture_disabled'] = False
            capture['diagnostics'].clear()
            with self.assertRaisesRegex(ProbeError, 'control'): s.observe('after_refresh')

    def test_native_recovery_uses_own_CA_and_unknown_trust_does_not_pass(self):
        plan = {'ca_name': 'fixed', 'certificate_sha256': 'AA'}
        responses = [SimpleNamespace(returncode=0, stdout=b'', stderr=b'')]
        native = s.Native(self.path, plan, run=Mock(return_value=responses[0]))
        with patch.object(s, 'load_plan', return_value=plan):
            native.trust(30)
            argv = native.run.call_args.args[0]
            self.assertEqual(argv[-1], str(self.path / 'mitmproxy/mitmproxy-ca-cert.pem'))
            self.assertNotIn('-s', argv)
            with patch.object(native, 'present', return_value=False), \
                    patch.object(native, 'verify', return_value={'outcome': 'not_verified'}):
                self.assertFalse(native.revoke()['verified'])


class ActualConfigurationTests(LocalTest):
    def test_actual_addon_component_options_no_listener_or_account_access(self):
        python = s.ROOT / '.venv-capture/bin/python'
        code = r'''
import asyncio,json,socket,tempfile
from pathlib import Path
from unittest.mock import patch
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from validation import compat_session as s
from validation.compat_addon import CompatibilityAddon,validate_options
from validation.capture_session import private_write
from validation.common import ROOT
def baseline():
 proxy={'Enabled':'Yes','Server':'127.0.0.1','Port':'7897','Authenticated Proxy Enabled':'0'}
 return {'active_service':'Wi-Fi','interface':'en0','https_proxy':proxy,'http_proxy':dict(proxy),
  'pac':{'Enabled':'No','URL':'(null)'},'autodiscovery':'Auto Proxy Discovery: Off',
  'bypass_domains':['localhost','*.local'],'review_reasons':[]}
async def check():
 with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
  base=Path(raw)
  (base/'.auth').mkdir(mode=0o700)
  (base/'.auth/wechat-capture').mkdir(mode=0o700)
  d=base/'.auth/wechat-capture/current';d.mkdir(mode=0o700)
  identity=s.generate(d)
  plan={'version':1,'experiment':'wechat_compat','duration_seconds':180,'cleanup_reserve_seconds':120,
        'wall_deadline':time.time()+180,'active_deadline':0,'baseline':baseline(),'mode':s.upstream_mode(baseline()),**identity}
  plan['active_deadline']=plan['wall_deadline']-120
  private_write(d/'plan.json',plan);private_write(d/'state.json',{'capture_disabled':False})
  with patch.object(s,'DIRECTORY',d),patch.object(s,'ROOT',base):
   assert s.load_plan()==plan
   options=Options(server=False,confdir=str(d/'mitmproxy'))
   master=DumpMaster(options,with_termlog=True,with_dumper=True)
   addon=CompatibilityAddon();master.addons.add(addon)
   try:
    options.update(mode=[plan['mode']],listen_host='127.0.0.1',listen_port=8899,
      allow_hosts=[r'^mp\.weixin\.qq\.com:443$'],ssl_insecure=False,upstream_cert=False,
      certs=['mp.weixin.qq.com='+str(d/'mitmproxy/target-key-chain.pem')],
      add_upstream_certs_to_client_chain=False,flow_detail=0,termlog_verbosity='error',command_history=False,strip_ech=False)
    validate_options(options,plan,d)
    options.update(liumo_compat=True)
    assert addon.session is not None
    flow=SimpleNamespace(request=SimpleNamespace(url='https://mp.weixin.qq.com/s/fixed',method='GET'),
                         response=SimpleNamespace(status_code=200))
    addon.requestheaders(flow);addon.responseheaders(flow)
    assert addon.diagnostics['article_like_requests_seen']==1 and addon.diagnostics['article_like_responses_seen']==1
    assert flow.request.stream and flow.response.stream
    for changed in ('ssl_insecure','upstream_cert','store_streamed_bodies'):
     values={k:getattr(options,k) for k in ('confdir','listen_host','listen_port','ssl_insecure','upstream_cert',
      'add_upstream_certs_to_client_chain','flow_detail','termlog_verbosity','command_history','strip_ech',
      'save_stream_file','store_streamed_bodies','mode','allow_hosts','certs')}
     values[changed]=True
     try:validate_options(SimpleNamespace(**values),plan,d)
     except s.ProbeError:pass
     else:raise AssertionError('unsafe options accepted')
    addon.diagnostics['article_like_requests_seen']+=1
    with patch('validation.capture_session.private_write',side_effect=OSError('constructed journal failure')):
     addon.publish()
    assert addon.passthrough_only and not options.liumo_compat
    private_write(d/'state.json',{'capture_disabled':True});addon.capture_disabled()
    assert addon.passthrough_only and not options.liumo_compat and list(options.allow_hosts)==[r'(?!)']
    assert s.load_plan()==plan
    assert s.delete_keys(plan) and s.load_plan()==plan
    assert not any((d/'mitmproxy'/n).exists() for n in s.KEYS)
    assert s.delete_keys(plan)
   finally:master.shutdown()
  print(json.dumps({'actual_component':True,'listener_started':False,'credentials_read':False}))
import time
from types import SimpleNamespace
actual=socket.socket
def local_only(family=socket.AF_INET,*args,**kwargs):
 if family in (socket.AF_INET,socket.AF_INET6):raise AssertionError('network prohibited')
 return actual(family,*args,**kwargs)
with patch.object(socket,'socket',side_effect=local_only):asyncio.run(check())
'''
        response = subprocess.run([str(python), '-c', code], cwd=s.ROOT, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=25, env={**os.environ, 'PYTHONPATH': str(s.ROOT / 'tests')})
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn('"credentials_read": false', response.stdout)
