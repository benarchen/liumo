"""Constructed trust commands and real public-only signing, never install trust."""

import copy
import json
import os
import subprocess
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_validation import LocalTest
from validation import anchor_scope as subject
from validation.certificate_scope import cases
from validation.common import ROOT
from validation.http import ProbeError


def decision(accepted=False, code=-25318):
    return {'outcome': 'accepted' if accepted else 'rejected', 'exit_code': 0 if accepted else 1,
            'trust_result': 4 if accepted else 5, 'OSStatus_codes': [] if accepted else [code]}


class ConstructedNative:
    def __init__(self, failure=None):
        self.trusted = False
        self.failure = failure
        self.events = []

    def present(self):
        return self.trusted

    def verify(self, case, root=None, timeout=4, include_root=False):
        stage = root or ('after' if self.trusted else 'before')
        self.events.append((stage, case['id']))
        if self.failure == (stage, case['id']):
            return {'outcome': 'not_verified', 'reason': 'constructed_unknown'}
        if root == 'unconstrained':
            return decision(case['valid_control'])
        if root == 'exact_dns_no_ip':
            return decision(case['in_scope'])
        if not self.trusted:
            return decision()
        if self.failure == 'scope_escape' and case['id'] == 'other':
            return decision(True)
        return decision(case['in_scope'])

    def trust(self, timeout):
        self.events.append(('install', timeout))
        self.trusted = True
        if self.failure == 'partial_install':
            raise ProbeError('constructed_install_failure')

    def revoke(self):
        self.events.append(('revoke',))
        self.trusted = False
        return {'verified': self.failure != 'recovery_failure', 'certificate_absent': True,
                'target_after_removal': decision()}


class AnchorLifecycleTests(LocalTest):
    def run_constructed(self, native, save=None, window=None):
        state = {'trust_attempted': False, 'installed_matrix_passed': False}
        saved = []
        save = save or (lambda value: saved.append(copy.deepcopy(value)))
        window = window or SimpleNamespace(timeout=lambda *args: 4)
        try:
            subject.evaluate(native, state, save, window)
        except (ProbeError, OSError):
            pass
        finally:
            subject.recover(native, state, save)
        return state, saved

    def test_positive_controls_preinstall_matrix_and_cleanup_all_required(self):
        native = ConstructedNative()
        state, saved = self.run_constructed(native)
        self.assertEqual(len(state['controls']), 34)
        self.assertEqual(len(state['before']), 17)
        self.assertEqual(len(state['after']), 17)
        self.assertTrue(state['installed_matrix_passed'])
        self.assertTrue(state['recovery']['verified'])
        self.assertFalse(native.trusted)
        self.assertTrue(any(s.get('trust_attempted') and not s.get('after') for s in saved))
        self.assertEqual(native.events[-1], ('revoke',))

    def test_control_unknown_and_preinstall_unknown_never_install(self):
        for failure in (('unconstrained', 'target'), ('exact_dns_no_ip', 'other'), ('before', 'target')):
            with self.subTest(failure=failure):
                native = ConstructedNative(failure)
                state, _ = self.run_constructed(native)
                self.assertFalse(state['trust_attempted'])
                self.assertFalse(any(e[0] == 'install' for e in native.events))
                self.assertFalse(state['installed_matrix_passed'])

    def test_scope_escape_partial_install_unknown_and_recovery_failure(self):
        for failure in ('scope_escape', 'partial_install', ('after', 'other'), 'recovery_failure'):
            with self.subTest(failure=failure):
                native = ConstructedNative(failure)
                state, _ = self.run_constructed(native)
                self.assertIn(('revoke',), native.events)
                self.assertFalse(native.trusted)
                if failure == 'recovery_failure':
                    self.assertFalse(state['recovery']['verified'])
                    self.assertEqual(state['status'], 'manual_recovery_required')
                else:
                    self.assertFalse(state['installed_matrix_passed'])

    def test_write_ahead_and_later_log_failures_do_not_leave_trust(self):
        for stage in ('before_install', 'after_install'):
            native = ConstructedNative()
            def save(value):
                if (stage == 'before_install' and value.get('trust_attempted')) or (
                        stage == 'after_install' and native.trusted):
                    raise OSError('constructed disk failure')
            state, _ = self.run_constructed(native, save)
            self.assertFalse(native.trusted)
            self.assertIn(('revoke',), native.events)
            if stage == 'before_install':
                self.assertFalse(any(e[0] == 'install' for e in native.events))
            self.assertTrue(state['finished'])

    def test_already_trusted_or_cleanup_reserve_never_install(self):
        native = ConstructedNative()
        native.trusted = True
        state, _ = self.run_constructed(native)
        self.assertFalse(state['trust_attempted'])
        self.assertFalse(any(e[0] == 'install' for e in native.events))
        window = SimpleNamespace(timeout=Mock(side_effect=ProbeError('anchor_cleanup_reserve_reached')))
        native = ConstructedNative()
        state, _ = self.run_constructed(native, window=window)
        self.assertFalse(state['trust_attempted'])

    def test_parent_cancellation_after_install_still_revokes(self):
        native = ConstructedNative()
        def budget(*_args):
            if native.trusted:
                raise ProbeError('session_parent_closed_or_cancelled')
            return 4
        state, _ = self.run_constructed(native, window=SimpleNamespace(timeout=budget))
        self.assertTrue(state['trust_attempted'])
        self.assertFalse(state['installed_matrix_passed'])
        self.assertFalse(native.trusted)
        self.assertEqual(native.events[-1], ('revoke',))

    def test_parent_pipe_and_both_clock_bounds(self):
        read_fd, write_fd = os.pipe()
        clock = [100.0]
        wall = [1000.0]
        try:
            window = subject.Window(read_fd, 1120, monotonic=lambda: clock[0], wall=lambda: wall[0], seconds=120)
            self.assertEqual(window.timeout(), 4)
            clock[0] = 149
            self.assertEqual(window.timeout(), 1)
            clock[0] = 150
            with self.assertRaises(ProbeError): window.timeout()
            clock[0] = 100
            wall[0] = 1120
            with self.assertRaises(ProbeError): window.timeout()
            wall[0] = 1000
            os.close(write_fd)
            write_fd = None
            with self.assertRaises(ProbeError): window.timeout()
        finally:
            os.close(read_fd)
            if write_fd is not None: os.close(write_fd)

    def test_previous_failure_existing_directory_and_lifecycle_overlap(self):
        old = []
        for i in range(5):
            path = self.path / ('old' + str(i))
            path.mkdir(mode=0o700)
            subject.private_write(path / 'state.json', {
                'finished': True, 'recovery': {'verified': True}, 'proxy_process_stopped': True})
            (path / '.lifecycle.lock').touch(mode=0o600)
            old.append(path)
        current = self.path / 'current'
        current.mkdir(mode=0o700)
        with patch.object(subject, 'PREVIOUS', tuple(old)), patch.object(subject, 'DIRECTORY', current):
            subject.previous_closed()
            with subject.locks():
                with self.assertRaises(ProbeError):
                    with subject.locks(): pass
            with patch.object(subject.subprocess, 'run') as run:
                with self.assertRaises(ProbeError): subject.session()
                run.assert_not_called()
            subject.private_write(old[2] / 'state.json', {'finished': True, 'recovery': {'verified': False}})
            with self.assertRaises(ProbeError): subject.previous_closed()

    def test_closed_manual_recovery_does_not_issue_system_commands(self):
        with patch.object(subject, 'load_plan', return_value={}), patch.object(subject, 'locks', return_value=nullcontext()), \
                patch.object(subject, 'DIRECTORY', self.path), patch.object(subject, 'private_json', return_value={
                    'finished': True, 'recovery': {'verified': True}}), patch.object(subject, 'Native') as native:
            (self.path / 'state.json').touch(mode=0o600)
            self.assertEqual(subject.manual_recover()['status'], 'already_closed_no_changes')
            native.assert_not_called()


class AnchorNativeTests(LocalTest):
    def native(self, response=None):
        run = Mock(return_value=response or SimpleNamespace(returncode=0, stdout=b'TrustResultValue = 4;', stderr=b''))
        native = subject.Native(self.path, {'ca_name': 'liumo-anchor-' + 'a' * 32,
            'certificate_sha256': 'B' * 64}, run)
        return native, run

    def test_installed_chain_uses_only_leaf_keychain_offline_and_explicit_controls_separate(self):
        native, run = self.native()
        self.assertEqual(native.verify(cases()[0])['outcome'], 'accepted')
        command = run.call_args.args[0]
        self.assertIn('-k', command)
        self.assertNotIn('-r', command)
        self.assertNotIn('-N', command)
        self.assertEqual(command.count('-c'), 1)
        self.assertEqual(command[command.index('-R') + 1], 'offline')
        self.assertIn('-L', command)
        native.verify(cases()[0], include_root=True)
        command = run.call_args.args[0]
        self.assertEqual(command.count('-c'), 2)
        self.assertNotIn('-r', command)
        native.verify(cases()[0], 'unconstrained')
        command = run.call_args.args[0]
        self.assertIn('-r', command)
        self.assertIn('-N', command)
        self.assertNotIn('-k', command)
        with self.assertRaises(ProbeError): native.verify(dict(cases()[0], host='evil.invalid'))
        with self.assertRaises(ProbeError): native.verify(cases()[0], '/arbitrary/root')

    def test_exact_user_SSL_trust_scope_and_no_raw_errors(self):
        native, run = self.native()
        with patch.object(subject, 'load_plan', return_value=native.plan):
            native.trust(12)
        command = run.call_args.args[0]
        self.assertEqual(command[:7], [subject.SECURITY, 'add-trusted-cert', '-r', 'trustRoot', '-p', 'ssl', '-k'])
        self.assertNotIn('-s', command)
        self.assertNotIn('-d', command)
        self.assertNotIn('-a', command)
        self.assertEqual(run.call_args.kwargs['timeout'], 12)
        run.side_effect = subprocess.TimeoutExpired('PRIVATE', 4)
        result = native.verify(cases()[0])
        self.assertEqual(result['outcome'], 'not_verified')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_presence_unknown_and_untrusted_reason_require_valid_decision(self):
        native, run = self.native(SimpleNamespace(returncode=44, stdout=b'', stderr=b'PRIVATE'))
        self.assertFalse(native.present())
        run.return_value = SimpleNamespace(returncode=0, stdout=b'WRONG_FINGERPRINT', stderr=b'')
        with self.assertRaises(ProbeError): native.present()
        self.assertTrue(subject.not_trusted(decision()))
        self.assertTrue(subject.not_trusted(decision(code=-67843)))
        for bad in ({'outcome': 'not_verified', 'OSStatus_codes': [-25318]}, decision(True),
                    decision(code=-26276), decision(code=-67818)):
            self.assertFalse(subject.not_trusted(bad))

    def test_identity_failure_blocks_deletion_and_delete_is_attempted_after_remove_failure(self):
        native, run = self.native()
        with patch.object(subject, 'load_plan', side_effect=ProbeError('anchor_plan_identity_mismatch')):
            with self.assertRaises(ProbeError): native.revoke()
        run.assert_not_called()
        run.side_effect = [SimpleNamespace(returncode=1, stdout=b'', stderr=b''),
                           SimpleNamespace(returncode=0, stdout=b'', stderr=b'')]
        with patch.object(subject, 'load_plan', return_value=native.plan), patch.object(native, 'present', return_value=False), \
                patch.object(native, 'verify', return_value=decision()):
            result = native.revoke()
        self.assertTrue(result['verified'])
        self.assertEqual(len(result['removal_command_issues']), 1)
        command = run.call_args.args[0]
        self.assertEqual(command, [subject.SECURITY, 'delete-certificate', '-Z', 'B' * 64, '-t', native.keychain])

    def test_changed_manifest_and_unconfirmed_post_removal_never_pass(self):
        native, run = self.native()
        with patch.object(subject, 'load_plan', return_value={'certificate_sha256': 'C' * 64}):
            with self.assertRaises(ProbeError): native.trust(4)
            with self.assertRaises(ProbeError): native.revoke()
        run.assert_not_called()
        with patch.object(subject, 'load_plan', return_value=native.plan), \
                patch.object(native, 'present', return_value=False), patch.object(native, 'verify',
                    return_value={'outcome': 'not_verified', 'reason': 'native_security_framework_error'}):
            self.assertFalse(native.revoke()['verified'])

    def test_recovery_prompt_budget_and_timeout_diagnostic_are_separate(self):
        native, run = self.native()
        self.assertEqual(native.recovery_timeout, 30)
        with patch.object(subject, 'load_plan', return_value=native.plan), \
                patch.object(native, 'present', return_value=False), patch.object(native, 'verify', return_value=decision()):
            self.assertTrue(native.revoke()['verified'])
        self.assertEqual([call.kwargs['timeout'] for call in run.call_args_list], [30, 30])
        run.side_effect = subprocess.TimeoutExpired('PRIVATE', 30)
        with self.assertRaises(ProbeError) as caught:
            native.command(['fixed'], 30)
        self.assertEqual(caught.exception.reason, 'anchor_native_command_timed_out')
        self.assertNotIn('PRIVATE', str(caught.exception))


class AnchorActualSigningTests(LocalTest):
    def test_signing_child_public_only_short_lifetime_and_failed_preflight_no_fixed_directory(self):
        python = ROOT / '.venv-capture/bin/python'
        if not python.exists(): self.skipTest('optional isolated cryptography not installed')
        code = r'''
import json,socket,tempfile,os
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from validation import anchor_scope as s
from validation.common import ROOT
with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
 base=Path(raw); materials=base/'public'; materials.mkdir(mode=0o700)
 with patch.object(socket,'socket',side_effect=AssertionError('network prohibited')), \
      patch.object(serialization,'NoEncryption',side_effect=AssertionError('private export prohibited')):
  s.generate_public(materials,'liumo-anchor-'+'a'*32)
  plan=s.material_plan(materials,'liumo-anchor-'+'a'*32)
 assert len(plan['materials'])==20
 for p in materials.iterdir():
  assert b'PRIVATE KEY' not in p.read_bytes()
  cert=x509.load_pem_x509_certificate(p.read_bytes())
  assert cert.not_valid_after_utc<=datetime.now(timezone.utc)+timedelta(minutes=20)
 assert not any(p.name.endswith('key.pem') for p in materials.iterdir())
 ca=x509.load_pem_x509_certificate((materials/'exact_dns_no_ip-root.pem').read_bytes())
 ca.verify_directly_issued_by(ca)
 assert ca.extensions.get_extension_for_class(x509.NameConstraints).critical
 old=(materials/'target-leaf.pem').read_bytes()
 (materials/'target-leaf.pem').write_bytes(old+b'\nPRIVATE KEY')
 try:s.material_plan(materials,'liumo-anchor-'+'a'*32)
 except s.ProbeError:pass
 else:raise AssertionError('private content accepted')
 auth=base/'.auth'; auth.mkdir(mode=0o700); parent=auth/'wechat-capture'; parent.mkdir(mode=0o700)
 output=base/'output'; output.mkdir(mode=0o700)
 with patch.object(s,'ROOT',base),patch.object(s,'DIRECTORY',parent/'anchor-scope-session'), \
      patch.object(s,'previous_closed'),patch.object(s,'new_run',return_value=output), \
      patch.object(s.Native,'verify',return_value={'outcome':'not_verified','reason':'constructed_internal_error'}), \
      patch.object(s.Native,'trust',side_effect=AssertionError('trust prohibited')), \
      patch.object(s.subprocess,'Popen',side_effect=AssertionError('system worker prohibited')):
  # Keep real signing invocation, with original Python/cwd; only system worker must be blocked.
  def signer(*args,**kwargs):
   s.generate_public(Path(args[0][-2]),args[0][-1])
   from types import SimpleNamespace
   return SimpleNamespace(returncode=0)
  with patch.object(s.subprocess,'run',side_effect=signer): result=s.session()
 assert result['status']=='blocked' and result['experiment_created'] is False
 assert not (parent/'anchor-scope-session').exists()
 assert not list((base/'.tmp/wechat-session-validation').iterdir())
 print(json.dumps({'public_certificates':20,'keys_exported':False,'system_trust_changed':False,'network':False}))
'''
        result = subprocess.run([str(python), '-c', code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['public_certificates'], 20)
