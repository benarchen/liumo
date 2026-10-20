"""Constructed profile events; no real credentials or system mutations."""

import json
import stat
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from test_validation import LocalTest
from validation.capture import TARGETS
from validation.capture_session import private_json, private_write, probe_new_profiles
from validation.profile_capture import (ENDPOINT, ProfileCaptureSession, extract_profile,
                                        probe_profile_snapshot, select_profile)
from validation.http import ProbeError

BIZ = next(biz for biz, row in TARGETS.items() if row['account'] == '猫笔刀')


def query(**changes):
    return {'action': 'getmsg', '__biz': BIZ, 'uin': 'PRIVATE_UIN', 'key': 'PRIVATE_KEY',
            'pass_ticket': 'PRIVATE_PASS', 'appmsg_token': 'PRIVATE_APP', 'poc_token': 'PRIVATE_POC',
            'offset': '0', 'count': '10', 'f': 'json', **changes}


def address(**changes):
    return ENDPOINT + '?' + urlencode(query(**changes))


def headers():
    return {'User-Agent': 'NormalWeChat/CONSTRUCTED', 'Cookie': 'poc_sid=PRIVATE_SID; unrelated=DISCARD',
            'Referer': ENDPOINT + '?' + urlencode({'action': 'home', '__biz': BIZ, 'uin': 'PRIVATE_UIN'})}


def snapshot():
    target, values = select_profile(address(), 'GET', 200)
    return extract_profile(target, values, headers())


class ProfileMatchingTests(unittest.TestCase):
    def test_target_only_before_private_fields_are_parsed(self):
        for value, method, code in [(address(__biz='OTHER'), 'GET', 200), (address(action='other'), 'GET', 200),
                                    (address() + '&__biz=' + BIZ, 'GET', 200),
                                    (address().replace('https:', 'http:'), 'GET', 200),
                                    (address().replace('/mp/profile_ext', '/s'), 'GET', 200),
                                    (address().replace('mp.weixin.qq.com', 'evil.test'), 'GET', 200),
                                    (address(), 'POST', 200), (address(), 'GET', 302)]:
            with patch('validation.profile_capture.parse_qs', side_effect=AssertionError('private decode')):
                with self.assertRaises(ProbeError):
                    select_profile(value, method, code)

    def test_allowlists_drop_unknown_query_cookies_and_headers(self):
        target, values = select_profile(address(unrelated='DISCARD'), 'GET', 200)
        value = extract_profile(target, values, {**headers(), 'Authorization': 'DISCARD'},
                                ['poc_sid=PRIVATE_NEW; Secure; HttpOnly'])
        self.assertNotIn('DISCARD', json.dumps(value))
        self.assertIn('poc_sid=PRIVATE_NEW', value['headers']['Cookie'])
        self.assertEqual(value['omitted_query_fields'], 1)
        self.assertFalse(value['raw_request_saved'])

    def test_ambiguous_credentials_controls_missing_session_and_cross_account_referer_stop(self):
        target, values = select_profile(address() + '&key=SECOND', 'GET', 200)
        with self.assertRaisesRegex(ProbeError, 'ambiguous'):
            extract_profile(target, values, headers())
        for changes in [{'User-Agent': 'BAD\nPRIVATE'}, {'Origin': 'https://evil.test'},
                        {'Referer': ENDPOINT + '?action=home&__biz=OTHER'}]:
            target, values = select_profile(address(), 'GET', 200)
            with self.assertRaises(ProbeError):
                extract_profile(target, values, {**headers(), **changes})
        for changes, reason in [({'offset': '10'}, 'first_page'), ({'count': '100'}, 'outside_scope')]:
            target, values = select_profile(address(**changes), 'GET', 200)
            with self.assertRaisesRegex(ProbeError, reason):
                extract_profile(target, values, headers())
        target, values = select_profile(ENDPOINT + '?action=home&__biz=' + BIZ, 'GET', 200)
        with self.assertRaisesRegex(ProbeError, 'session_fields_missing'):
            extract_profile(target, values, {'User-Agent': 'CONSTRUCTED'})


class ProfilePrivateTests(LocalTest):
    def test_once_per_action_private_and_old_files_never_overwritten(self):
        session = ProfileCaptureSession(self.path)
        result = session.observe(address(), 'GET', 200, headers())
        self.assertEqual(result, 'profile_capture_saved_not_authentication_verified')
        path = self.path / 'maobidao-getmsg.json'
        old = path.read_bytes()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(session.observe(address(), 'GET', 200, headers()), 'profile_capture_already_saved')
        second = ProfileCaptureSession(self.path)
        self.assertEqual(second.observe(address(), 'GET', 200, headers()), 'profile_capture_existing_file')
        self.assertEqual(path.read_bytes(), old)
        summary = json.dumps(session.summary())
        self.assertNotIn('PRIVATE_', summary)
        self.assertFalse(session.summary()['authentication_verified'])

    def test_expiry_stop_and_store_failure_do_not_leak(self):
        now = [0]
        session = ProfileCaptureSession(self.path, seconds=1, clock=lambda: now[0])
        now[0] = 1
        self.assertEqual(session.observe(address(), 'GET', 200, headers()), 'profile_capture_window_closed')
        self.assertEqual(list(self.path.iterdir()), [])
        session = ProfileCaptureSession(self.path)
        with patch('validation.capture_session.private_write', side_effect=OSError('PRIVATE_KEY')):
            self.assertEqual(session.observe(address(), 'GET', 200, headers()), 'profile_capture_store_failed')
        self.assertNotIn('PRIVATE_', json.dumps(session.summary()))
        session.stop()
        self.assertEqual(session.observe(address(), 'GET', 200, headers()), 'profile_capture_window_closed')

    def test_worker_marks_once_before_probe_and_never_retries_refusal(self):
        directory = self.path / 'requests'
        directory.mkdir(mode=0o700)
        private_write(directory / 'maobidao-getmsg.json', snapshot())
        journal = {}
        probe = Mock(return_value={'account': '猫笔刀', 'status': 'not_verified', 'reason': 'business_rejected'})
        with patch('validation.capture_session.time.sleep'):
            for _ in range(2):
                probe_new_profiles(self.path, journal, lambda: None, time.time() + 600, probe)
        probe.assert_called_once()
        self.assertEqual(private_json(self.path / 'state.json')['profile_probe_results']['猫笔刀']['reason'],
                         'profile_probe_started')
        self.assertEqual(journal['profile_probe_results']['猫笔刀']['reason'], 'business_rejected')

    def test_no_request_near_deadline_or_other_account_input(self):
        directory = self.path / 'requests'
        directory.mkdir(mode=0o700)
        private_write(directory / 'maobidao-getmsg.json', snapshot())
        probe = Mock()
        with self.assertRaisesRegex(ProbeError, 'window_expired'):
            probe_new_profiles(self.path, {}, lambda: None, time.time() + 25, probe)
        value = snapshot()
        value['account'] = 'stormzhang'
        private_write(directory / 'maobidao-getmsg.json', value)
        with self.assertRaisesRegex(ProbeError, 'scope_mismatch'):
            probe_new_profiles(self.path, {}, lambda: None, time.time() + 600, probe)
        probe.assert_not_called()


class ProfileProbeTests(unittest.TestCase):
    def test_rejection_one_request_safe_shape_no_extra_endpoint(self):
        client = Mock()
        client.read.return_value = b'{"ret":-3,"errmsg":"PRIVATE_TEXT"}'
        result = probe_profile_snapshot(snapshot(), client)
        client.read.assert_called_once()
        self.assertEqual(result['reason'], 'business_rejected')
        self.assertEqual(result['error_code'], -3)
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertFalse(result['authentication_verified'])

    def test_stale_wrong_identity_unknown_fields_and_http_refusal_stop(self):
        for change in [{'captured_at': '2026-10-01T00:00:00+08:00'}, {'biz': 'OTHER'},
                       {'action': 'home'}, {'query': {**query(), 'unknown': 'PRIVATE'}}]:
            client = Mock()
            result = probe_profile_snapshot({**snapshot(), **change}, client)
            client.read.assert_not_called()
            self.assertEqual(result['requests_attempted'], 0)
        client = Mock()
        client.read.side_effect = ProbeError('http_rejected', 403)
        result = probe_profile_snapshot(snapshot(), client)
        client.read.assert_called_once()
        self.assertEqual(result['error_code'], 403)

    def test_list_shape_is_not_full_acceptance_or_verified_source_time(self):
        client = Mock()
        client.read.return_value = json.dumps({'ret': 0, 'general_msg_list': {'list': []},
                                               'can_msg_continue': 0, 'next_offset': 0}).encode()
        result = probe_profile_snapshot(snapshot(), client)
        self.assertEqual(result['status'], 'list_shape_observed')
        self.assertFalse(result['account_identity_verified'])
        self.assertFalse(result['publication_times_verified'])
        client.read.return_value = b'{"ret":0,"can_msg_continue":0}'
        self.assertEqual(probe_profile_snapshot(snapshot(), client)['reason'], 'source_list_missing')


class ProfileDriverTests(LocalTest):
    def test_fresh_baseline_failure_creates_no_experiment_or_system_changes(self):
        from validation import capture_session as driver
        old, new = self.path / 'old', self.path / 'new'
        old.mkdir(mode=0o700)
        private_write(old / 'state.json', {'recovery': {'verified': True}, 'proxy_process_stopped': True})
        with patch.object(driver, 'ARTICLE_SESSION', old), patch.object(driver, 'PROFILE_SESSION', new), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', side_effect=ProbeError('preflight_system_authorization_unavailable')), patch.object(
                driver, 'session') as run:
            with self.assertRaisesRegex(ProbeError, 'authorization_unavailable'):
                driver.profile_session()
            run.assert_not_called()
        self.assertFalse(new.exists())
        self.assertEqual(private_json(old / 'state.json')['recovery'], {'verified': True})

    def test_prior_recovery_or_existing_new_session_blocks_new_experiment(self):
        from validation import capture_session as driver
        old, new = self.path / 'old', self.path / 'new'
        old.mkdir(mode=0o700)
        private_write(old / 'state.json', {'recovery': {'verified': False}})
        with patch.object(driver, 'ARTICLE_SESSION', old), patch.object(driver, 'PROFILE_SESSION', new), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline') as baseline:
            with self.assertRaisesRegex(ProbeError, 'previous_recovery_unverified'):
                driver.profile_session()
            new.mkdir(mode=0o700)
            with self.assertRaisesRegex(ProbeError, 'already_exists'):
                driver.profile_session()
            baseline.assert_not_called()

    def test_profile_recovery_selects_only_profile_directory(self):
        from validation import capture_session as driver
        with patch.object(driver, 'SESSION', self.path / 'old'), patch.object(driver, 'PROFILE_SESSION', self.path / 'new'), patch.object(
                driver, 'manual_recover', side_effect=lambda: str(driver.SESSION)):
            self.assertEqual(driver.profile_manual_recover(), str(self.path / 'new'))

    def test_native_default_directory_and_recovery_hint_use_profile_run(self):
        from validation import capture_session as driver
        with patch.object(driver, 'SESSION', self.path):
            native = driver.Native({'baseline': {'active_service': 'Wi-Fi'}, 'experiment': 'profile'})
            self.assertEqual(native.directory, self.path)

    def test_finished_old_recovery_cannot_restore_over_new_experiment(self):
        from validation import capture_session as driver
        private_write(self.path / 'state.json', {'recovery': {'verified': True}, 'proxy_process_stopped': True})
        with patch.object(driver, 'SESSION', self.path), patch.object(driver, 'runtime_plan', return_value={}), patch.object(
                driver, 'Native') as native:
            result = driver._manual_recover()
        self.assertEqual(result['status'], 'already_closed_no_changes')
        self.assertFalse(result['current_system_state_rechecked'])
        native.assert_not_called()

    def test_profile_parent_launches_correct_worker_and_skips_old_source_probe(self):
        from test_capture_session import baseline
        from validation import capture_session as driver
        (self.path / '.auth').mkdir(mode=0o700)
        parent = self.path / '.auth/wechat-capture'
        parent.mkdir(mode=0o700)
        directory = parent / 'profile-session'
        baselines = parent / 'baselines'
        baselines.mkdir(mode=0o700)
        baseline_path = baselines / 'fresh.json'
        private_write(baseline_path, baseline())
        child = Mock()
        child.poll.return_value = 0
        child.stdin = Mock()
        def launch(command, **kwargs):
            self.assertEqual(command[-1], '--profile-worker')
            self.assertEqual(kwargs['stdout'], -3)
            private_write(directory / 'state.json', {'status': 'restored', 'recovery': {'verified': True},
                                                     'proxy_process_stopped': True})
            return child
        with patch.object(driver, 'ROOT', self.path), patch.object(driver, 'SESSION', directory), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', return_value=baseline()), patch.object(driver.subprocess, 'Popen', side_effect=launch), patch.object(
                driver, 'new_run', return_value=self.path), patch.object(driver, 'validate_sources') as old_probe:
            result = driver.session(baseline_path, profile=True)
        old_probe.assert_not_called()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(private_json(directory / 'plan.json')['experiment'], 'profile')
        self.assertTrue((directory / 'requests').is_dir())
