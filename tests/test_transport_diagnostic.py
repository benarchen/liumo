"""Control probes are mocked; component tests never trust a CA or listen."""

import copy
import json
import os
import subprocess
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_validation import LocalTest
from validation.capture_session import (SessionWindow, private_json, private_write,
                                       verify_diagnostic_control)
from validation.http import ProbeError
from validation.capture_plan import check_proxy_options
from validation.mitm_addon import WechatCaptureAddon
from validation.transport_diagnostic import (CONTROL_URL, DiagnosticSession, control_probe,
                                            control_verified, observation_snapshot)


class ObservationSnapshotTests(LocalTest):
    def write_live(self):
        self.plan = {'experiment': 'diagnostic', 'duration_seconds': 120, 'wall_deadline': 220,
                     'baseline': {'PRIVATE': 'PRIVATE_PROXY'}}
        self.state = {'status': 'ready_refresh_maobidao_for_diagnostics', 'finished': False,
                      'capture_disabled': False, 'PRIVATE': 'PRIVATE_TOKEN',
                      'diagnostic_control': {'status': 'https_response_observed', 'proxy_response_observed': True}}
        self.capture = {'running': True, 'status': 'open', 'passthrough_only': False,
                        'diagnostics': {'control_target_requests_seen': 1, 'control_target_responses_seen': 1,
                                        'tls_client_target_reason_certificate_alert': 3, 'PRIVATE': 'PRIVATE_ERROR'}}
        self.save()

    def save(self):
        for name, data in (('plan', self.plan), ('state', self.state), ('capture', self.capture)):
            private_write(self.path / (name + '.json'), data)

    def test_before_after_samples_only_emit_safe_fields_and_do_not_confirm_UI(self):
        self.write_live()
        before = observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)
        self.capture['diagnostics']['tls_client_target_reason_certificate_alert'] = 5
        self.save()
        after = observation_snapshot(self.path, 'after_refresh', clock=lambda: 125)
        key = 'tls_client_target_reason_certificate_alert'
        self.assertEqual(after['counters'][key] - before['counters'][key], 2)
        self.assertEqual(before['seconds_remaining'], 100)
        self.assertEqual(after['seconds_remaining'], 95)
        self.assertTrue(before['at'].endswith('+00:00'))
        self.assertFalse(after['UI_refresh_verified_by_snapshot'])
        self.assertNotIn('PRIVATE', json.dumps([before, after]))
        self.plan['experiment'] = 'ui_diagnostic'
        self.save()
        self.assertEqual(observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)['phase'],
                         'before_refresh')

    def test_closed_stopped_and_unverified_control_cannot_produce_a_sample(self):
        for mutation, reason in [('finished', 'not_running'), ('stopped', 'not_running'),
                                 ('disabled', 'not_running'), ('control', 'control_unverified')]:
            self.write_live()
            if mutation == 'finished': self.state['finished'] = True
            if mutation == 'disabled': self.state['capture_disabled'] = True
            if mutation == 'stopped': self.capture['passthrough_only'] = True
            if mutation == 'control': self.capture['diagnostics']['control_target_responses_seen'] = 0
            self.save()
            with self.assertRaisesRegex(ProbeError, reason):
                observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)

    def test_article_observation_requires_article_ready_state(self):
        self.write_live()
        self.plan['experiment'] = 'article_diagnostic'
        self.save()
        with self.assertRaisesRegex(ProbeError, 'not_running'):
            observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)
        self.state['status'] = 'ready_refresh_maobidao_article_for_diagnostics'
        self.save()
        result = observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)
        self.assertEqual(result['seconds_remaining'], 100)
        self.assertFalse(result['UI_refresh_verified_by_snapshot'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_deadline_clock_rollback_invalid_phase_and_experiment_are_rejected(self):
        self.write_live()
        for now in (99, 220, float('inf'), True):
            with self.assertRaisesRegex(ProbeError, 'window_closed'):
                observation_snapshot(self.path, 'after_refresh', clock=lambda: now)
        with self.assertRaisesRegex(ProbeError, 'phase_invalid'):
            observation_snapshot(self.path, 'PRIVATE')
        self.plan['wall_deadline'] = 1000000000100
        self.save()
        with self.assertRaisesRegex(ProbeError, 'window_closed'):
            observation_snapshot(self.path, 'after_refresh', clock=lambda: 1000000000000)
        self.plan['experiment'] = 'article'
        self.save()
        with self.assertRaisesRegex(ProbeError, 'experiment_invalid'):
            observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)

    def test_malformed_counter_and_state_are_rejected_without_echoing_values(self):
        for bad in (True, -1, 1000000001, 'PRIVATE_TOKEN'):
            self.write_live()
            self.capture['diagnostics']['control_target_requests_seen'] = bad
            self.save()
            with self.assertRaisesRegex(ProbeError, 'counters_invalid') as raised:
                observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)
            self.assertNotIn('PRIVATE', str(raised.exception))
        private_write(self.path / 'state.json', [])
        with self.assertRaisesRegex(ProbeError, 'state_invalid'):
            observation_snapshot(self.path, 'before_refresh', clock=lambda: 120)


class ControlTests(LocalTest):
    def certificate(self):
        directory = self.path / 'mitmproxy'
        directory.mkdir(mode=0o700)
        (directory / 'mitmproxy-ca-cert.pem').write_text('CONSTRUCTED_NOT_TRUSTED')

    def test_fixed_public_control_has_explicit_proxy_CA_no_credentials_or_dump(self):
        self.certificate()
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout='404'))
        with patch.dict(os.environ, {'HTTPS_PROXY': 'PRIVATE_PROXY', 'NO_PROXY': '*',
                                      'SSLKEYLOGFILE': 'PRIVATE_KEYLOG'}):
            result = control_probe(self.path, run)
        args = run.call_args.args[0]
        options = run.call_args.kwargs
        self.assertEqual(args[:2], ['/usr/bin/curl', '--disable'])
        self.assertEqual(args[args.index('--url')+1], CONTROL_URL)
        self.assertEqual(args[args.index('--proxy')+1], 'http://127.0.0.1:8899')
        self.assertEqual(args[args.index('--noproxy')+1], '')
        self.assertEqual(args[args.index('--cacert')+1], str(self.path/'mitmproxy/mitmproxy-ca-cert.pem'))
        self.assertIn('--no-insecure', args)
        self.assertIn('--no-location', args)
        self.assertNotIn('--header', args)
        self.assertNotIn('--retry', args)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)
        self.assertEqual(options['timeout'], 25)
        for key in ('HTTPS_PROXY', 'NO_PROXY', 'SSLKEYLOGFILE'):
            self.assertNotIn(key, options['env'])
        self.assertEqual(result['status'], 'https_response_observed')
        self.assertEqual(result['http_status'], 404)
        self.assertFalse(result['account_access_verified'])
        self.assertFalse(result['proxy_response_observed'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_failure_never_leaks_output_or_exception_and_cannot_pass_control_gate(self):
        self.certificate()
        for outcome in [SimpleNamespace(returncode=60, stdout='000'),
                        SimpleNamespace(returncode=0, stdout='PRIVATE_RESPONSE'),
                        subprocess.TimeoutExpired('PRIVATE_COMMAND', 25), OSError('PRIVATE_ERROR')]:
            run = Mock(**({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome}))
            result = control_probe(self.path, run)
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertFalse(control_verified(result, {'control_target_requests_seen': 1, 'control_target_responses_seen': 1}))

    def test_missing_or_symlinked_certificate_makes_no_request(self):
        self.certificate()
        path = self.path/'mitmproxy/mitmproxy-ca-cert.pem'
        other = self.path/'other.pem'
        path.rename(other)
        path.symlink_to(other)
        run = Mock()
        with self.assertRaisesRegex(ProbeError, 'certificate_missing'):
            control_probe(self.path, run)
        run.assert_not_called()

    def test_proxy_observation_required_in_addition_to_curl_response(self):
        counters = {'control_target_requests_seen': 1, 'control_target_responses_seen': 1}
        private_write(self.path/'capture.json', {'diagnostics': counters})
        journal, saved = {}, []
        probe = Mock(return_value={'status': 'https_response_observed', 'http_status': 200})
        verify_diagnostic_control(self.path, journal, lambda value: saved.append(copy.deepcopy(value)),
                                  lambda: None, time.time()+120, probe)
        probe.assert_called_once_with(self.path)
        self.assertTrue(journal['diagnostic_control']['proxy_response_observed'])
        private_write(self.path/'capture.json', {'diagnostics': {}})
        with patch('validation.capture_session.time.monotonic', side_effect=[0, 3]):
            with self.assertRaisesRegex(ProbeError, 'control_unverified'):
                verify_diagnostic_control(self.path, {}, lambda _: None, lambda: None, time.time()+120,
                                          lambda _: {'status': 'https_response_observed'})
        forbidden = Mock()
        with self.assertRaisesRegex(ProbeError, 'window_expired'):
            verify_diagnostic_control(self.path, {}, lambda _: None, lambda: None, time.time()+20, forbidden)
        forbidden.assert_not_called()


class CredentialFreeTests(unittest.TestCase):
    def test_control_and_normal_traffic_counts_are_separate_without_retaining_queries(self):
        addon = WechatCaptureAddon()
        addon.session = DiagnosticSession()
        for url in (CONTROL_URL, 'https://mp.weixin.qq.com/mp/profile_ext?key=PRIVATE'):
            flow = SimpleNamespace(request=SimpleNamespace(url=url, method='GET', stream=False),
                                   response=SimpleNamespace(status_code=200, stream=False))
            addon.requestheaders(flow)
            addon.responseheaders(flow)
        for phase in ('requests', 'responses'):
            self.assertEqual(addon.diagnostics['control_target_'+phase+'_seen'], 1)
            self.assertEqual(addon.diagnostics['target_host_'+phase+'_seen'], 1)
        self.assertNotIn('PRIVATE', json.dumps(addon.diagnostics))
        self.assertEqual(addon.session.summary()['saved_by_account'], {})
        with self.assertRaisesRegex(ProbeError, 'credentials_disabled'):
            addon.session.observe(object())

    def test_duration_and_both_clocks_enforce_120_seconds(self):
        with self.assertRaisesRegex(ProbeError, 'duration_invalid'):
            DiagnosticSession(600)
        import os
        reader, writer = os.pipe()
        try:
            clock, wall = [0], [0]
            window = SessionWindow(reader, 120, monotonic=lambda: clock[0], wall=lambda: wall[0], seconds=120)
            window.check()
            clock[0] = 120
            with self.assertRaisesRegex(ProbeError, 'expired'):
                window.check()
            clock[0], wall[0] = 0, 120
            with self.assertRaisesRegex(ProbeError, 'expired'):
                window.check()
        finally:
            os.close(reader)
            os.close(writer)

    def test_short_setup_remains_pending_control_and_rejects_mixed_capture_flags(self):
        from test_capture_session import FakeNative
        from validation.capture_session import setup
        from validation.capture_plan import check_proxy_options
        from test_capture import ReviewPlanTests
        native = FakeNative()
        native.plan['experiment'] = 'diagnostic'
        journal = {}
        setup(native, journal, lambda _: None, lambda: None, lambda: object())
        self.assertEqual(journal['status'], 'diagnostic_control_pending')
        options = ReviewPlanTests().options()
        options.liumo_profile_capture = options.liumo_diagnostic_only = True
        with self.assertRaises(ProbeError):
            check_proxy_options(options)


class DiagnosticRoutingTests(LocalTest):
    def test_article_mode_requires_four_closed_runs_and_rejects_existing_directory(self):
        from validation import capture_session as driver
        from test_capture_session import baseline
        keys = ('ARTICLE_SESSION', 'PROFILE_SESSION', 'DIAGNOSTIC_SESSION', 'UI_DIAGNOSTIC_SESSION')
        paths = {key: self.path / key.lower() for key in (*keys, 'ARTICLE_DIAGNOSTIC_SESSION')}
        closed = {'recovery': {'verified': True}, 'proxy_process_stopped': True}
        for key in keys:
            paths[key].mkdir(mode=0o700)
            private_write(paths[key]/'state.json', closed)
        with patch.multiple(driver, **paths, SESSION=self.path/'unused'), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', return_value=baseline()) as collect, patch(
                'validation.capture_preflight.save_baseline', return_value=self.path/'fresh.json'), patch.object(
                driver, 'session', return_value={'status': 'constructed'}) as session:
            for key in keys:
                for bad in ({'recovery': {'verified': False}, 'proxy_process_stopped': True},
                            {'recovery': {'verified': True}, 'proxy_process_stopped': False}):
                    private_write(paths[key]/'state.json', bad)
                    with self.assertRaisesRegex(ProbeError, 'previous_recovery_unverified'):
                        driver.article_diagnostic_session()
                private_write(paths[key]/'state.json', closed)
            collect.assert_not_called()
            self.assertEqual(driver.article_diagnostic_session(), {'status': 'constructed'})
            session.assert_called_once_with(self.path/'fresh.json', diagnostic=True, article_control=True)
            self.assertEqual(driver.SESSION, paths['ARTICLE_DIAGNOSTIC_SESSION'])
            paths['ARTICLE_DIAGNOSTIC_SESSION'].mkdir(mode=0o700)
            with self.assertRaisesRegex(ProbeError, 'article_diagnostic_already_exists'):
                driver.article_diagnostic_session()
            self.assertEqual(collect.call_count, 1)
        for key in keys:
            self.assertEqual(private_json(paths[key]/'state.json'), closed)

    def test_article_parent_and_recovery_use_separate_paths_and_never_probe_sources(self):
        from validation import capture_session as driver
        from test_capture_session import baseline
        (self.path/'.auth').mkdir(mode=0o700)
        parent = self.path/'.auth/wechat-capture'
        parent.mkdir(mode=0o700)
        (parent/'baselines').mkdir(mode=0o700)
        path, directory = parent/'baselines/fresh.json', parent/'article-diagnostic-session'
        private_write(path, baseline())
        child = Mock()
        child.poll.return_value = 0
        def launch(command, **kwargs):
            self.assertEqual(command[-1], '--article-diagnostic-worker')
            private_write(directory/'state.json', {'status': 'restored', 'finished': True,
                                                   'recovery': {'verified': True}, 'proxy_process_stopped': True})
            return child
        with patch.object(driver, 'ROOT', self.path), patch.object(driver, 'SESSION', directory), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', return_value=baseline()), patch.object(
                driver.subprocess, 'Popen', side_effect=launch), patch.object(
                driver, 'new_run', return_value=self.path) as output, patch.object(driver, 'validate_sources') as source:
            driver.session(path, diagnostic=True, article_control=True)
            plan = driver.runtime_plan(directory)
        output.assert_called_once_with('article-transport-diagnostic-session')
        source.assert_not_called()
        self.assertEqual(plan['experiment'], 'article_diagnostic')
        self.assertEqual(plan['duration_seconds'], 120)
        self.assertFalse((directory/'requests').exists())
        self.assertEqual(driver.recovery_entry(plan), 'article-transport-diagnostic-recover')
        with patch.object(driver, 'SESSION', self.path/'old'), patch.object(
                driver, 'ARTICLE_DIAGNOSTIC_SESSION', directory), patch.object(
                driver, 'manual_recover', side_effect=lambda: str(driver.SESSION)):
            self.assertEqual(driver.article_diagnostic_manual_recover(), str(directory))

    def test_article_mixed_modes_and_proxy_flags_are_rejected(self):
        from validation import capture_session as driver
        from test_capture import ReviewPlanTests
        with patch('validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline') as collect:
            for flags in ({'article_control': True}, {'diagnostic': True, 'article_control': True, 'ui': True},
                          {'diagnostic': True, 'article_control': True, 'profile': True}):
                with self.assertRaisesRegex(ProbeError, 'experiment_conflict'):
                    driver.session(self.path/'unused', **flags)
            collect.assert_not_called()
        options = ReviewPlanTests().options()
        options.liumo_article_diagnostic = True
        with self.assertRaisesRegex(ProbeError, 'configuration_rejected'):
            check_proxy_options(options)
        options.liumo_diagnostic_only = options.liumo_ui_diagnostic = True
        with self.assertRaisesRegex(ProbeError, 'configuration_rejected'):
            check_proxy_options(options)

    def test_article_addon_configuration_selects_credential_free_session_and_guards_mismatch(self):
        from test_capture import ReviewPlanTests
        options = ReviewPlanTests().options()
        options.liumo_capture = options.liumo_diagnostic_only = options.liumo_article_diagnostic = True
        options.liumo_capture_seconds = 120
        directory = self.path/'.auth/wechat-capture/article-diagnostic-session'
        options.confdir = str(directory/'mitmproxy')
        plan = {'experiment': 'article_diagnostic', 'mode': 'regular', 'wall_deadline': time.time()+120}
        from validation import capture_plan
        addon = WechatCaptureAddon()
        import sys
        with patch.object(capture_plan, 'ROOT', self.path), patch(
                'validation.capture_session.runtime_plan', return_value=plan), patch.dict(
                sys.modules, {'mitmproxy': SimpleNamespace(ctx=SimpleNamespace(options=options))}):
            addon.configure(set())
            self.assertIsInstance(addon.session, DiagnosticSession)
            self.assertEqual(addon.runtime_directory, directory)
            with self.assertRaisesRegex(ProbeError, 'credentials_disabled'):
                addon.session.observe('PRIVATE', 'GET', 200)
            plan['experiment'] = 'ui_diagnostic'
            with self.assertRaisesRegex(ProbeError, 'configuration_rejected'):
                check_proxy_options(options)

    def test_ui_mode_requires_all_three_recoveries_and_preserves_old_directories(self):
        from validation import capture_session as driver
        from test_capture_session import baseline
        paths = {key: self.path / name for key, name in (
            ('ARTICLE_SESSION', 'article'), ('PROFILE_SESSION', 'profile'),
            ('DIAGNOSTIC_SESSION', 'diagnostic'), ('UI_DIAGNOSTIC_SESSION', 'ui'))}
        closed = {'recovery': {'verified': True}, 'proxy_process_stopped': True}
        for key in ('ARTICLE_SESSION', 'PROFILE_SESSION', 'DIAGNOSTIC_SESSION'):
            paths[key].mkdir(mode=0o700)
            private_write(paths[key] / 'state.json', closed)
        with patch.multiple(driver, **paths, SESSION=self.path/'unused'), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', return_value=baseline()) as collect, patch(
                'validation.capture_preflight.save_baseline', return_value=self.path/'fresh.json'), patch.object(
                driver, 'session', return_value={'status': 'constructed'}) as session:
            for key in ('ARTICLE_SESSION', 'PROFILE_SESSION', 'DIAGNOSTIC_SESSION'):
                private_write(paths[key]/'state.json', {'recovery': {'verified': False}, 'proxy_process_stopped': True})
                with self.assertRaisesRegex(ProbeError, 'previous_recovery_unverified'):
                    driver.ui_diagnostic_session()
                private_write(paths[key]/'state.json', closed)
            collect.assert_not_called()
            self.assertEqual(driver.ui_diagnostic_session(), {'status': 'constructed'})
            session.assert_called_once_with(self.path/'fresh.json', diagnostic=True, ui=True)
            self.assertEqual(driver.SESSION, paths['UI_DIAGNOSTIC_SESSION'])
            paths['UI_DIAGNOSTIC_SESSION'].mkdir(mode=0o700)
            with self.assertRaisesRegex(ProbeError, 'ui_diagnostic_already_exists'):
                driver.ui_diagnostic_session()
        for key in ('ARTICLE_SESSION', 'PROFILE_SESSION', 'DIAGNOSTIC_SESSION'):
            self.assertEqual(private_json(paths[key]/'state.json'), closed)

    def test_ui_parent_uses_separate_plan_worker_output_and_recovery(self):
        from validation import capture_session as driver
        from test_capture_session import baseline
        (self.path/'.auth').mkdir(mode=0o700)
        parent = self.path/'.auth/wechat-capture'
        parent.mkdir(mode=0o700)
        (parent/'baselines').mkdir(mode=0o700)
        path, directory = parent/'baselines/fresh.json', parent/'ui-diagnostic-session'
        private_write(path, baseline())
        child = Mock()
        child.poll.return_value = 0
        def launch(command, **kwargs):
            self.assertEqual(command[-1], '--ui-diagnostic-worker')
            private_write(directory/'state.json', {'status': 'restored', 'finished': True,
                                                   'recovery': {'verified': True}, 'proxy_process_stopped': True})
            return child
        with patch.object(driver, 'ROOT', self.path), patch.object(driver, 'SESSION', directory), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline', return_value=baseline()), patch.object(
                driver.subprocess, 'Popen', side_effect=launch), patch.object(
                driver, 'new_run', return_value=self.path) as output, patch.object(driver, 'validate_sources') as source:
            driver.session(path, diagnostic=True, ui=True)
            plan = driver.runtime_plan(directory)
        output.assert_called_once_with('ui-transport-diagnostic-session')
        source.assert_not_called()
        self.assertEqual(plan['experiment'], 'ui_diagnostic')
        self.assertEqual(plan['duration_seconds'], 120)
        self.assertFalse((directory/'requests').exists())
        self.assertEqual(driver.recovery_entry(plan), 'ui-transport-diagnostic-recover')
        with patch.object(driver, 'SESSION', self.path/'old'), patch.object(
                driver, 'UI_DIAGNOSTIC_SESSION', directory), patch.object(
                driver, 'manual_recover', side_effect=lambda: str(driver.SESSION)):
            self.assertEqual(driver.ui_diagnostic_manual_recover(), str(directory))

    def test_ui_proxy_flags_cannot_fall_back_to_article_or_old_diagnostic(self):
        from test_capture import ReviewPlanTests
        from validation.capture_plan import check_proxy_options
        options = ReviewPlanTests().options()
        options.liumo_ui_diagnostic = True
        with self.assertRaisesRegex(ProbeError, 'configuration_rejected'):
            check_proxy_options(options)
        options.liumo_diagnostic_only = True
        with self.assertRaisesRegex(ProbeError, 'configuration_rejected'):
            check_proxy_options(options)

    def test_unrecovered_prior_experiment_and_existing_directory_block_before_baseline(self):
        from validation import capture_session as driver
        article, profile, diagnostic = [self.path/name for name in ('article', 'profile', 'diagnostic')]
        for path in (article, profile):
            path.mkdir(mode=0o700)
            private_write(path/'state.json', {'recovery': {'verified': path == article}, 'proxy_process_stopped': True})
        with patch.object(driver, 'ARTICLE_SESSION', article), patch.object(driver, 'PROFILE_SESSION', profile), patch.object(
                driver, 'DIAGNOSTIC_SESSION', diagnostic), patch('validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(
                driver, 'collect_baseline') as baseline:
            with self.assertRaisesRegex(ProbeError, 'previous_recovery_unverified'):
                driver.diagnostic_session()
            diagnostic.mkdir(mode=0o700)
            with self.assertRaisesRegex(ProbeError, 'diagnostic_already_exists'):
                driver.diagnostic_session()
            baseline.assert_not_called()

    def test_diagnostic_recovery_routes_to_own_directory(self):
        from validation import capture_session as driver
        with patch.object(driver, 'SESSION', self.path/'old'), patch.object(driver, 'DIAGNOSTIC_SESSION', self.path/'diagnostic'), patch.object(
                driver, 'manual_recover', side_effect=lambda: str(driver.SESSION)):
            self.assertEqual(driver.diagnostic_manual_recover(), str(self.path/'diagnostic'))
        self.assertEqual(driver.recovery_entry({'experiment': 'diagnostic'}), 'transport-diagnostic-recover')

    def test_parent_uses_120_seconds_worker_and_skips_all_credentials_and_sources(self):
        from validation import capture_session as driver
        from test_capture_session import baseline
        (self.path/'.auth').mkdir(mode=0o700)
        parent = self.path/'.auth/wechat-capture'
        parent.mkdir(mode=0o700)
        baselines = parent/'baselines'
        baselines.mkdir(mode=0o700)
        directory = parent/'diagnostic-session'
        path = baselines/'fresh.json'
        private_write(path, baseline())
        child = Mock()
        child.poll.return_value = 0
        def launch(command, **kwargs):
            self.assertEqual(command[-1], '--diagnostic-worker')
            private_write(directory/'state.json', {'status':'restored','recovery':{'verified':True},'proxy_process_stopped':True})
            return child
        with patch.object(driver, 'ROOT', self.path), patch.object(driver, 'SESSION', directory), patch(
                'validation.capture_session.sys.stdin.isatty', return_value=True), patch.object(driver, 'collect_baseline', return_value=baseline()), patch.object(
                driver.subprocess, 'Popen', side_effect=launch), patch.object(driver, 'new_run', return_value=self.path), patch.object(
                driver, 'validate_sources') as source:
            result = driver.session(path, diagnostic=True)
        source.assert_not_called()
        plan = private_json(directory/'plan.json')
        self.assertEqual(plan['duration_seconds'], 120)
        self.assertEqual(plan['experiment'], 'diagnostic')
        self.assertFalse((directory/'requests').exists())
        self.assertEqual(result['profile_probe_results'], [])
