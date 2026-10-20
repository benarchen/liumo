"""C17 constructed flow/HTTP tests, never installed trust or real credentials."""

import copy
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

from test_capture_session import baseline
from test_validation import LocalTest
from validation import compat_session as runtime
from validation import functional_capture as capture
from validation import functional_check as check
from validation import curl_size_probe as size_probe
from validation.capture_session import private_write
from validation.http import ProbeError, WechatHTTP


def address(**changes):
    fields = {'__biz': check.BIZ, 'mid': check.EXPECTED['mid'], 'idx': '1', 'sn': 'publicsn',
              'uin': 'SECRET_UIN', 'key': 'SECRET_KEY', 'pass_ticket': 'SECRET_TICKET',
              'appmsg_token': 'SECRET_TOKEN', **changes}
    return 'https://mp.weixin.qq.com/s?' + urlencode(fields)


def credential():
    rows = []
    session = capture.ArticleCandidateSession(writer=rows.append, ready=lambda: True)
    session.observe(address(), 'GET', 200, 'appmsg_token=SECRET_TOKEN; wap_sid2=SECRET_WAP; unrelated=NEVER_KEEP')
    return rows[0]


def html(biz=None, mid=None, comments='42'):
    return (f'<h1 id="activity-name">上个月最值的一笔消费</h1><div id="js_name">猫笔刀</div>'
        f'<div id="js_content"><p>用于构造测试的正文。</p></div>'
        f'<script>var biz="{biz or check.BIZ}";var mid="{mid or check.EXPECTED["mid"]}";'
        f'var idx="1";var comment_id="{comments}";</script>').encode()


def comments(**changes):
    return {'base_resp': {'ret': 0}, 'enabled': 1, 'continue_flag': 0,
            'elected_comment_total_cnt': 0, 'elected_comment': [], **changes}


def curl_output(body=b'ok', status=b'200'):
    return body + b'\nLIUMO_CURL_V1:' + status + b':200:0:0.001000:0.012000:' + str(len(body)).encode()


class Client:
    def __init__(self, body=None, payload=None, failure=None):
        self.body = html() if body is None else body
        self.payload = comments() if payload is None else payload
        self.failure, self.attempts = failure, {'body': 0, 'comments': 0}

    def read(self, kind, *_):
        self.attempts[kind] += 1
        if self.failure == kind: raise ProbeError('http_rejected', 403)
        return self.body if kind == 'body' else json.dumps(self.payload).encode()


class CandidateTests(LocalTest):
    def test_only_first_fixed_identity_and_no_unrelated_cookie_or_secrets_in_summary(self):
        rows = []
        session = capture.ArticleCandidateSession(writer=rows.append, ready=lambda: True)
        for change in ({'mid': '1'}, {'idx': '2'}, {'__biz': 'other'}):
            session.observe(address(**change), 'GET', 200, 'appmsg_token=SECRET_TOKEN')
        self.assertEqual(rows, [])
        session.observe(address(), 'GET', 200, 'appmsg_token=SECRET_TOKEN; unrelated=NEVER_KEEP')
        session.observe(address(), 'GET', 200, 'appmsg_token=NEW')
        self.assertEqual(len(rows), 1)
        self.assertNotIn('NEVER_KEEP', json.dumps(rows))
        self.assertNotIn('SECRET', rows[0]['public_article_url'])
        self.assertNotIn('SECRET', json.dumps(session.summary()))
        self.assertEqual(session.saved, {'猫笔刀': 1})

    def test_closed_gate_missing_fields_and_failed_store_never_retry_candidate(self):
        writer = Mock()
        session = capture.ArticleCandidateSession(writer=writer, ready=lambda: False)
        session.observe(address(), 'GET', 200)
        writer.assert_not_called()
        for writer in (Mock(), Mock(side_effect=OSError('SECRET'))):
            session = capture.ArticleCandidateSession(writer=writer, ready=lambda: True)
            session.observe(address(appmsg_token=''), 'GET', 200)
            session.observe(address(), 'GET', 200, 'appmsg_token=SECRET_TOKEN')
            self.assertTrue(session.attempted)
            writer.assert_not_called()
        session = capture.ArticleCandidateSession(writer=Mock(side_effect=OSError('SECRET')), ready=lambda: True)
        session.observe(address(), 'GET', 200)
        session.observe(address(), 'GET', 200)
        self.assertEqual(session.saved, {})
        self.assertNotIn('SECRET', json.dumps(session.summary()))

    def test_private_candidate_no_overwrite_symlink_or_wide_directory(self):
        with patch.object(capture, 'DIRECTORY', self.path):
            capture.store_candidate(credential())
            path = self.path / 'candidate.json'
            before = path.read_bytes()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): capture.store_candidate(credential())
            self.assertEqual(before, path.read_bytes())
        second = self.path / 'second'
        second.mkdir(mode=0o700)
        (second / 'candidate.json').symlink_to(self.path / 'candidate.json')
        with patch.object(capture, 'DIRECTORY', second):
            with self.assertRaises(FileExistsError): capture.store_candidate(credential())
        second.chmod(0o755)
        with patch.object(capture, 'DIRECTORY', second):
            with self.assertRaises(ProbeError): capture.store_candidate(credential())

    def test_selector_old_seven_and_fixed_worker_addon_boundaries(self):
        names = ('DIRECTORY', 'PREVIOUS', 'UI_READY', 'EXPERIMENT', 'ADDON', 'READY_STATUS', 'WORKER_FLAG', 'RUN_SLUG')
        with patch.multiple(runtime, **{n: getattr(runtime, n) for n in names}):
            subject = capture.select_runtime()
            self.assertEqual(len(subject.PREVIOUS), 7)
            self.assertIn(runtime.COMPAT_DIRECTORY, subject.PREVIOUS)
            self.assertEqual(subject.EXPERIMENT, 'article_functional')
            self.assertEqual(subject.WORKER_FLAG, '--functional-worker')
            argv = subject.proxy_command({'mode': 'upstream:http://127.0.0.1:7897'})
            self.assertIn(str(capture.ROOT / 'validation/functional_addon.py'), argv)
            self.assertNotIn(str(capture.ROOT / 'validation/compat_addon.py'), argv)
        self.assertEqual(runtime.EXPERIMENT, 'wechat_compat')

    def test_check_once_and_failed_recovery_prevent_network(self):
        with patch.object(check, 'DIRECTORY', self.path):
            with check.once():
                with self.assertRaises(ProbeError):
                    with check.once(): pass
            with self.assertRaises(FileExistsError):
                with check.once(): pass
        with patch.object(check, 'once'), patch.object(check, 'recovered_plan', side_effect=ProbeError('functional_recovery_unverified')), \
                patch.object(check, 'LimitedHTTP') as client:
            with self.assertRaises(ProbeError): check.check()
        client.assert_not_called()

    def test_public_candidate_scope_time_and_duplicate_fields_rejected(self):
        data = credential()
        plan = {'wall_deadline': datetime.now(timezone.utc).timestamp() + 120}
        with patch.object(check, 'read_private_credentials', return_value=data):
            self.assertEqual(check.candidate(plan), data)
            for change in (('source_identity', {'mid': 'bad', 'idx': '1'}),
                           ('captured_at', '2000-01-01T00:00:00+00:00'),
                           ('public_article_url', data['public_article_url'] + '&key=SECRET')):
                value = copy.deepcopy(data); value[change[0]] = change[1]
                with patch.object(check, 'read_private_credentials', return_value=value):
                    with self.assertRaises(ProbeError): check.candidate(plan)

    def test_delayed_recovery_keeps_trial_candidate_but_rejects_outside_capture_window(self):
        now = datetime.now(timezone.utc).timestamp()
        plan = {'wall_deadline': now - 800}
        data = credential()
        def at(value):
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        data['captured_at'] = at(plan['wall_deadline'] - 145)
        with patch.object(check, 'read_private_credentials', return_value=data):
            self.assertEqual(check.candidate(plan), data)
        for instant in (plan['wall_deadline'] - 186, plan['wall_deadline'] - 60, now + 1):
            changed = {**data, 'captured_at': at(instant)}
            with patch.object(check, 'read_private_credentials', return_value=changed):
                with self.assertRaises(ProbeError): check.candidate(plan)


class FunctionTests(LocalTest):
    def test_recovery_gate_requires_all_parts_and_private_key_absence(self):
        base = self.path
        (base / '.auth').mkdir(mode=0o700)
        parent = base / '.auth/wechat-capture'; parent.mkdir(mode=0o700)
        current = parent / 'current'; current.mkdir(mode=0o700)
        for name in ('mitmproxy', 'probes'): (current / name).mkdir(mode=0o700)
        paths = ['mitmproxy/' + n for n in ('mitmproxy-ca-cert.pem', 'unconstrained-root.pem', 'target-leaf.pem')]
        paths += ['probes/' + c['id'] + '-leaf.pem' for c in check.cases()]
        import hashlib
        for name in paths:
            path = current / name;path.write_bytes(b'public constructed cert');path.chmod(0o600)
        plan = {'version': 1, 'experiment': 'article_functional', 'duration_seconds': 180,
                'cleanup_reserve_seconds': 120, 'baseline': baseline(), 'mode': runtime.upstream_mode(baseline()),
                'materials': {name: hashlib.sha256((current / name).read_bytes()).hexdigest() for name in paths}}
        state = {'finished': True, 'status': 'closed', 'recovery': {'verified': True, 'proxy_verified': True,
                 'trust': {'verified': True}, 'process_stopped': True, 'keys_removed': True}}
        private_write(current / 'plan.json', plan)
        private_write(current / 'state.json', state)
        with patch.object(check, 'DIRECTORY', current), patch.object(check, 'ROOT', base):
            self.assertEqual(check.recovered_plan(), plan)
            for key in ('verified', 'proxy_verified', 'process_stopped', 'keys_removed'):
                changed = copy.deepcopy(state);changed['recovery'][key] = False
                private_write(current / 'state.json', changed)
                with self.assertRaises(ProbeError): check.recovered_plan()
            private_write(current / 'state.json', state)
            path = current / 'mitmproxy/mitmproxy-ca.pem';path.write_bytes(b'private fixture');path.chmod(0o600)
            with self.assertRaisesRegex(ProbeError, 'keys_still_present'): check.recovered_plan()

    def test_parent_never_checks_HTTP_before_successful_recovery(self):
        for result in ({'status': 'blocked'}, {'recovery': {'verified': False}}):
            fake = SimpleNamespace(session=lambda: result)
            with patch.object(capture, 'select_runtime', return_value=fake), \
                    patch.object(capture.subprocess, 'run') as run:
                self.assertEqual(capture.session(), result)
            run.assert_not_called()

    def test_same_body_and_empty_API_conflict_are_not_full_archive_or_no_comments(self):
        client = Client()
        result = check.verify(credential(), client, self.path)
        self.assertTrue(result['body_verified'])
        self.assertEqual(result['comments']['status'], 'unknown')
        self.assertTrue(result['comments']['api_reported_empty'])
        self.assertIn('api_empty_conflicts_with_known_sample_comments', result['comments']['reasons'])
        self.assertFalse(result['full_archive_verified'])
        self.assertEqual(client.attempts, {'body': 1, 'comments': 1})
        self.assertNotIn('SECRET', json.dumps(result))

    def test_response_identity_comes_from_HTML_not_request_query(self):
        for body in (html(biz='other'), html(mid='1'), html().replace('猫笔刀'.encode(), '其他号'.encode()),
                     b'<p>access denied</p>'):
            client = Client(body=body)
            result = check.verify(credential(), client, self.path)
            self.assertFalse(result['body_verified'])
            self.assertEqual(client.attempts['comments'], 0)

    def test_restricted_redirect_transport_or_no_comment_id_never_probe_comments(self):
        client = Client(failure='body')
        result = check.verify(credential(), client, self.path)
        self.assertFalse(result['body_verified'])
        self.assertEqual(client.attempts['comments'], 0)
        client = Client(body=html(comments='0'))
        result = check.verify(credential(), client, self.path)
        self.assertTrue(result['body_verified'])
        self.assertEqual(result['comments']['status'], 'unknown')
        self.assertEqual(client.attempts['comments'], 0)

    def test_comment_disabled_business_reject_and_incomplete_are_not_empty(self):
        for payload, expected in ((comments(enabled=0), 'inaccessible'),
                                  ({'base_resp': {'ret': -3}}, 'failed'),
                                  (comments(continue_flag=1, buffer='next'), 'failed')):
            client = Client(payload=payload)
            result = check.verify(credential(), client, self.path)
            self.assertEqual(result['comments']['status'], expected)
            self.assertEqual(client.attempts['comments'], 1)

    def test_reply_requires_more_requests_keeps_inline_content_partial(self):
        row = {'content_id': '1', 'content': '公开构造留言',
               'reply_new': {'reply_total_cnt': 1, 'reply_list': [], 'max_reply_id': '0'}}
        client = Client(payload=comments(elected_comment_total_cnt=1, elected_comment=[row]))
        result = check.verify(credential(), client, self.path)
        self.assertEqual(result['comments']['status'], 'partial')
        self.assertIn('functional_request_budget_exhausted', result['comments']['reasons'])
        self.assertEqual(client.attempts['comments'], 1)

    def test_limited_transport_stdin_secrets_fixed_target_proxy_and_timeouts(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=curl_output()))
        record = Mock()
        subject = check.LimitedHTTP(baseline(), record, run=runner)
        self.assertEqual(subject.read('body', address(), {'Cookie': 'appmsg_token=SECRET_TOKEN'}), b'ok')
        args, kwargs = runner.call_args.args[0], runner.call_args.kwargs
        self.assertNotIn('SECRET', ' '.join(args))
        self.assertIn(b'SECRET_KEY', kwargs['input'])
        self.assertEqual(args[args.index('--proxy') + 1], 'http://127.0.0.1:7897')
        self.assertIn('--no-insecure', args)
        self.assertIn('--no-location', args)
        self.assertEqual(kwargs['timeout'], 20)
        with self.assertRaises(ProbeError): subject.read('body', address(), {})
        self.assertEqual(runner.call_count, 1)

    def test_write_ahead_failure_wrong_target_redirect_and_timeout_stop(self):
        runner = Mock()
        subject = check.LimitedHTTP(baseline(), Mock(side_effect=OSError('disk')), run=runner)
        with self.assertRaises(OSError): subject.read('body', address(), {})
        runner.assert_not_called()
        for body in (curl_output(status=b'302'), curl_output(status=b'403'), curl_output(status=b'000'), b'bad status'):
            subject = check.LimitedHTTP(baseline(), lambda _: None,
                run=Mock(return_value=SimpleNamespace(returncode=0, stdout=body)))
            with self.assertRaises(ProbeError): subject.read('body', address(), {})
        subject = check.LimitedHTTP(baseline(), lambda _: None, run=Mock(side_effect=subprocess.TimeoutExpired('SECRET', 20)))
        with self.assertRaisesRegex(ProbeError, 'transport_failed'): subject.read('body', address(), {})
        subject = check.LimitedHTTP(baseline(), lambda _: None, run=runner)
        for url in (address().replace('mp.weixin.qq.com', 'other.invalid'), address(mid='1'),
                    address().replace('/s?', '/mp/profile_ext?')):
            with self.assertRaises(ProbeError): subject.read('body', url, {})
        runner.assert_not_called()

    def test_receive_failure_preserves_bounded_observation_but_never_accepts_partial_body(self):
        response = SimpleNamespace(returncode=56, stdout=curl_output(body=b'SECRET_PARTIAL'),
            stderr=b'curl: (56) Recv failure: Connection reset by peer https://SECRET.invalid')
        subject = check.LimitedHTTP(baseline(), lambda _: None, run=Mock(return_value=response))
        result = check.verify(credential(), subject, self.path)
        self.assertFalse(result['body_verified'])
        self.assertEqual(result['error_code'], 56)
        self.assertEqual(result['requests_attempted'], {'body': 1, 'comments': 0})
        self.assertEqual(result['transport_observations']['body']['http_status'], 200)
        self.assertEqual(result['transport_observations']['body']['proxy_connect_status'], 200)
        self.assertEqual(result['transport_observations']['body']['error_category'], 'connection_reset_message')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_error_categories_unknown_mixed_oversize_and_invalid_metadata_never_leak(self):
        for raw, category in ((b'', 'unavailable'), (b'X' * 8193, 'unavailable'),
                (b'proxy CONNECT aborted SECRET', 'proxy_tunnel_message'),
                (b'SSLRead() return SECRET', 'tls_read_message'),
                (b'SSLRead() connection reset by peer SECRET', 'ambiguous'), (b'SECRET', 'other')):
            body, observed = check.curl_observation(SimpleNamespace(returncode=56, stdout=b'SECRET_BODY', stderr=raw))
            self.assertEqual(body, b'')
            self.assertFalse(observed['metadata_valid'])
            self.assertEqual(observed['error_category'], category)
            self.assertNotIn('SECRET', json.dumps(observed))
        for tail in (b'LIUMO_CURL_V1:200:200:0:nan:0.000000:0',
                     b'LIUMO_CURL_V1:200:200:0:61.000000:0.000000:0',
                     b'LIUMO_CURL_V1:200:200:0:0.000000:0.000000:2097153'):
            _, observed = check.curl_observation(SimpleNamespace(returncode=0, stdout=b'\n'+tail, stderr=b''))
            self.assertFalse(observed['metadata_valid'])

    def test_reached_size_limit_is_observation_not_a_root_cause_or_success(self):
        for code in (0, 56, 63):
            response = SimpleNamespace(returncode=code,
                stdout=b'x' * size_probe.LIMIT + b'\nLIUMO_CURL_V1:200:200:0:0.001000:0.012000:2097152',
                stderr=b'Exceeded the maximum allowed file size SECRET' if code else b'')
            body, observed = check.curl_observation(response)
            self.assertTrue(observed['download_limit_reached'])
            self.assertNotIn('SECRET', json.dumps(observed))
            self.assertEqual(len(body), size_probe.LIMIT)
            if code:
                self.assertEqual(observed['error_category'], 'size_limit_message')
                client = check.LimitedHTTP(baseline(), lambda _: None, run=Mock(return_value=response))
                result = check.verify(credential(), client, self.path)
                self.assertFalse(result['body_verified'])
                self.assertEqual(result['requests_attempted'], {'body': 1, 'comments': 0})

    def test_observation_needs_new_grant_before_creating_marker_or_loading_credential(self):
        with patch.object(check, 'DIRECTORY', self.path), \
                patch.object(check, 'candidate') as data, patch.object(check, 'LimitedHTTP') as client:
            with self.assertRaises(ProbeError): check.check(observation=True)
            self.assertFalse((self.path/'functional-observation-attempt.json').exists())
        data.assert_not_called();client.assert_not_called()
        plan = check.observation_plan()
        self.assertFalse(plan['executed'])
        self.assertFalse(plan['system_settings_changed'])
        self.assertTrue(plan['requires_new_explicit_authorization'])

    def test_bounded_body_accepts_large_complete_identity_but_keeps_comment_budget(self):
        large = html() + b' ' * check.RESPONSE_LIMIT
        run = Mock(side_effect=[SimpleNamespace(returncode=0, stdout=curl_output(large), stderr=b''),
            SimpleNamespace(returncode=0, stdout=curl_output(json.dumps(comments()).encode()), stderr=b'')])
        client = check.LimitedHTTP(baseline(), lambda _: None, run=run, body_limit=check.BOUNDED_BODY_LIMIT)
        result = check.verify(credential(), client, self.path)
        self.assertTrue(result['body_verified'])
        self.assertEqual(result['requests_attempted'], {'body': 1, 'comments': 1})
        self.assertFalse(result['full_archive_verified'])
        self.assertEqual(result['comments']['status'], 'unknown')
        budgets = [args.args[0][args.args[0].index('--max-filesize')+1] for args in run.call_args_list]
        self.assertEqual(budgets, [str(check.BOUNDED_BODY_LIMIT), str(check.RESPONSE_LIMIT)])
        default = check.LimitedHTTP(baseline(), lambda _: None,
            run=Mock(return_value=SimpleNamespace(returncode=0, stdout=curl_output(large), stderr=b'')))
        self.assertFalse(check.verify(credential(), default, self.path)['body_verified'])

    def test_body_cookie_reference_fields_are_separate_from_comment_API_fields(self):
        client = Client()
        calls = []
        read = client.read
        def observe(kind, url, headers):
            calls.append((kind, url, headers))
            return read(kind, url, headers)
        client.read = observe
        result = check.verify(credential(), client, self.path)
        self.assertTrue(result['body_verified'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(set(parse_qs(urlsplit(calls[0][1]).query)), {'__biz', 'mid', 'idx', 'sn'})
        self.assertEqual(calls[0][2], {'Cookie': 'pass_ticket=SECRET_TICKET;wap_sid2=SECRET_WAP'})
        self.assertTrue({'uin', 'key', 'pass_ticket', 'appmsg_token'} <=
            set(parse_qs(urlsplit(calls[1][1]).query)))
        self.assertNotIn('SECRET', json.dumps(result))

    def test_body_cookie_missing_or_delimiters_stop_before_any_request(self):
        for changes in ({'cookie': ''}, {'cookie': 'appmsg_token=SECRET_TOKEN'},
                        {'cookie': 'wap_sid2="bad;injected"'}, {'pass_ticket': 'bad;extra=SECRET'},
                        {'pass_ticket': 'bad\r\nSECRET'}):
            client = Client()
            result = check.verify({**credential(), **changes}, client, self.path)
            self.assertFalse(result['body_verified'])
            self.assertEqual(result['reason'], 'functional_body_cookie_missing_or_invalid')
            self.assertEqual(client.attempts, {'body': 0, 'comments': 0})
            self.assertNotIn('SECRET', json.dumps(result))

    def test_cookie_body_no_grant_stops_before_credentials_and_plan_is_readonly(self):
        with patch.object(check, 'DIRECTORY', self.path), patch.object(check, 'candidate') as data, \
                patch.object(check, 'LimitedHTTP') as client:
            with self.assertRaises(ProbeError): check.check(cookie_body=True)
            self.assertFalse((self.path/'functional-cookie-body-attempt.json').exists())
            with self.assertRaises(ProbeError): check.check(cookie_body=True, bounded_body=True)
        data.assert_not_called();client.assert_not_called()
        plan = check.cookie_body_plan()
        self.assertFalse(plan['executed'])
        self.assertTrue(plan['requires_new_explicit_authorization'])
        self.assertEqual(plan['body_response_limit_bytes'], check.BOUNDED_BODY_LIMIT)

    def test_cookie_body_grant_binds_C19_and_preserves_three_old_markers(self):
        old = {'at': '2026-10-18T10:15:03+00:00', 'reason': 'redirect_blocked', 'error_code': 302,
            'body_verified': False, 'requests_attempted': {'body': 1, 'comments': 0},
            'transport_observations': {'body': {'http_status': 302, 'curl_exit_code': 0, 'proxy_connect_status': 200}}}
        with patch.object(check, 'DIRECTORY', self.path):
            private_write(self.path/'functional-bounded-body-result.json', old)
            proof = {'experiment': 'c20_cookie_body', 'source': 'explicit_user_grant',
                'authorized_at': '2026-10-18T10:20:00+00:00', 'max_body_requests': 1,
                'max_comment_requests': 1, 'same_candidate_only': True,
                'body_response_limit_bytes': check.BOUNDED_BODY_LIMIT,
                'comment_response_limit_bytes': check.RESPONSE_LIMIT,
                'source_result_sha256': hashlib.sha256((self.path/'functional-bounded-body-result.json').read_bytes()).hexdigest()}
            private_write(self.path/'functional-cookie-body-authorization.json', proof)
            check.cookie_body_authorized()
            for change in ({'max_body_requests': 2}, {'same_candidate_only': False},
                           {'comment_response_limit_bytes': 0}, {'source_result_sha256': 'bad'},
                           {'authorized_at': '2000-01-01T00:00:00+00:00'}):
                private_write(self.path/'functional-cookie-body-authorization.json', {**proof, **change})
                with self.assertRaises(ProbeError): check.cookie_body_authorized()
            with check.once(): pass
            with check.once(observation=True): pass
            with check.once(bounded_body=True): pass
            originals = {p.name: p.read_bytes() for p in self.path.glob('*-attempt.json')}
            with check.once(cookie_body=True): pass
            for name, raw in originals.items(): self.assertEqual((self.path/name).read_bytes(), raw)
            with self.assertRaises(FileExistsError):
                with check.once(cookie_body=True): pass

    def test_bounded_limits_reject_invalid_budgets_oversize_and_nonzero_complete_body(self):
        run = Mock()
        for limit in (True, 0, -1, check.BOUNDED_BODY_LIMIT+1):
            with self.assertRaises(ProbeError): check.LimitedHTTP(baseline(), Mock(), run=run, body_limit=limit)
            with self.assertRaises(ProbeError): check.curl_observation(SimpleNamespace(), limit)
        run.assert_not_called()
        large = html() + b' ' * check.RESPONSE_LIMIT
        client = check.LimitedHTTP(baseline(), lambda _: None, body_limit=check.BOUNDED_BODY_LIMIT,
            run=Mock(return_value=SimpleNamespace(returncode=56, stdout=curl_output(large), stderr=b'')))
        result = check.verify(credential(), client, self.path)
        self.assertFalse(result['body_verified'])
        self.assertEqual(result['requests_attempted'], {'body': 1, 'comments': 0})
        metadata = b'\nLIUMO_CURL_V1:200:200:0:0.001000:0.012000:10485761'
        self.assertFalse(check.curl_observation(SimpleNamespace(returncode=0, stdout=metadata, stderr=b''),
            check.BOUNDED_BODY_LIMIT)[1]['metadata_valid'])
        lied = check.LimitedHTTP(baseline(), lambda _: None,
            run=Mock(return_value=SimpleNamespace(returncode=0, stdout=large+b'\nLIUMO_CURL_V1:200:200:0:0.001000:0.012000:2', stderr=b'')))
        with self.assertRaisesRegex(ProbeError, 'response_size_limit'): lied.read('body', address(), {})

    def test_bounded_body_requires_separate_grant_before_credentials_or_marker(self):
        with patch.object(check, 'DIRECTORY', self.path), patch.object(check, 'candidate') as data, \
                patch.object(check, 'LimitedHTTP') as client:
            with self.assertRaises(ProbeError): check.check(bounded_body=True)
            self.assertFalse((self.path/'functional-bounded-body-attempt.json').exists())
            with self.assertRaises(ProbeError): check.check(observation=True, bounded_body=True)
        data.assert_not_called();client.assert_not_called()
        plan = check.bounded_body_plan()
        self.assertFalse(plan['executed'])
        self.assertTrue(plan['requires_new_explicit_authorization'])
        self.assertEqual(plan['body_response_limit_bytes'], check.BOUNDED_BODY_LIMIT)

    def test_bounded_body_grant_binds_old_result_and_preserves_all_consumed_markers(self):
        old = {'at': '2026-10-18T10:01:01+00:00', 'reason': 'functional_tls_or_transport_failed',
            'error_code': 56, 'body_verified': False, 'requests_attempted': {'body': 1, 'comments': 0},
            'transport_observations': {'body': {'http_status': 200, 'proxy_connect_status': 200,
                'downloaded_bytes': check.RESPONSE_LIMIT}}}
        with patch.object(check, 'DIRECTORY', self.path):
            private_write(self.path/'functional-observation-result.json', old)
            proof = {'experiment': 'c19_bounded_body', 'source': 'explicit_user_grant',
                'authorized_at': '2026-10-18T10:10:00+00:00', 'max_body_requests': 1,
                'max_comment_requests': 1, 'same_candidate_only': True,
                'body_response_limit_bytes': check.BOUNDED_BODY_LIMIT,
                'comment_response_limit_bytes': check.RESPONSE_LIMIT,
                'source_result_sha256': hashlib.sha256((self.path/'functional-observation-result.json').read_bytes()).hexdigest()}
            private_write(self.path/'functional-bounded-body-authorization.json', proof)
            check.bounded_body_authorized()
            for change in ({'max_body_requests': 2}, {'same_candidate_only': False},
                           {'body_response_limit_bytes': 0}, {'comment_response_limit_bytes': check.BOUNDED_BODY_LIMIT},
                           {'authorized_at': '2000-01-01T00:00:00+00:00'}, {'source_result_sha256': 'bad'}):
                private_write(self.path/'functional-bounded-body-authorization.json', {**proof, **change})
                with self.assertRaises(ProbeError): check.bounded_body_authorized()
            with check.once(): pass
            with check.once(observation=True): pass
            originals = {p.name: p.read_bytes() for p in self.path.glob('*-attempt.json')}
            with check.once(bounded_body=True): pass
            for name, raw in originals.items(): self.assertEqual((self.path/name).read_bytes(), raw)
            with self.assertRaises(FileExistsError):
                with check.once(bounded_body=True): pass

    def test_observation_grant_scope_time_and_distinct_consumed_markers(self):
        old = {'reason': 'functional_tls_or_transport_failed', 'error_code': 56,
            'requests_attempted': {'body': 1, 'comments': 0}, 'at': '2026-10-18T09:45:48+00:00'}
        proof = {'experiment': 'c18_functional_observation', 'source': 'explicit_user_grant',
            'authorized_at': '2026-10-18T10:00:00+00:00', 'max_body_requests': 1,
            'max_comment_requests': 1, 'same_candidate_only': True}
        with patch.object(check, 'DIRECTORY', self.path):
            private_write(self.path/'functional-result.json', old)
            private_write(self.path/'functional-observation-authorization.json', proof)
            check.observation_authorized()
            for change in ({'max_body_requests': 2}, {'same_candidate_only': False},
                           {'authorized_at': '2000-01-01T00:00:00+00:00'}):
                private_write(self.path/'functional-observation-authorization.json', {**proof, **change})
                with self.assertRaises(ProbeError): check.observation_authorized()
            with check.once(): pass
            original = (self.path/'functional-attempt.json').read_bytes()
            with check.once(observation=True): pass
            self.assertEqual((self.path/'functional-attempt.json').read_bytes(), original)
            with self.assertRaises(FileExistsError):
                with check.once(observation=True): pass


class SizeProbeTests(LocalTest):
    def test_stimuli_exercise_exact_oversize_and_incomplete_chunk_boundaries(self):
        for name in size_probe.CASES:
            parts = []
            size_probe.send_fixture(SimpleNamespace(sendall=parts.append), name)
            header, payload = b''.join(parts).split(b'\r\n\r\n', 1)
            if name == 'small':
                self.assertIn(b'Content-Length: 2', header)
                self.assertEqual(payload, b'ok')
            elif name == 'known_too_large':
                self.assertIn(str(size_probe.LIMIT + 1).encode(), header)
                self.assertEqual(len(payload), size_probe.LIMIT + 1)
            else:
                self.assertIn(b'Transfer-Encoding: chunked', header)
                total, finished = 0, False
                while payload:
                    line, payload = payload.split(b'\r\n', 1)
                    length = int(line, 16)
                    if not length:
                        self.assertEqual(payload, b'\r\n')
                        finished = True
                        break
                    self.assertEqual(payload[length:length+2], b'\r\n')
                    total += length
                    payload = payload[length+2:]
                expected = {'chunked_too_large': size_probe.LIMIT + 1,
                    'chunked_exact': size_probe.LIMIT, 'chunked_interrupted': 20}[name]
                self.assertEqual(total, expected)
                self.assertEqual(finished, name != 'chunked_interrupted')

    def test_unix_permission_failure_stops_before_native_HTTP_without_fallback(self):
        listener = Mock()
        listener.bind.side_effect = PermissionError(1, 'SECRET_NATIVE_DETAIL')
        with patch.object(size_probe.socket, 'socket', return_value=listener) as make_socket, \
                patch.object(size_probe.subprocess, 'run') as native:
            result = size_probe.run_case('small', self.path)
        self.assertEqual(result, {'case': 'small', 'status': 'unix_IPC_unavailable', 'errno': 1})
        self.assertEqual(make_socket.call_args.args, (size_probe.socket.AF_UNIX, size_probe.socket.SOCK_STREAM))
        native.assert_not_called()
        listener.close.assert_called_once()
        self.assertNotIn('SECRET', json.dumps(result))


class ComponentTests(LocalTest):
    def test_actual_C17_component_isolated_target_gate_and_no_default_header_access(self):
        code = r'''
import asyncio,json,socket,tempfile,time,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from validation import compat_session as s
from validation import functional_capture as f
from validation.functional_addon import FunctionalAddon
from validation.capture_session import private_write,private_json
from validation.common import ROOT
async def run():
 with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
  base=Path(raw);(base/'.auth').mkdir(mode=0o700);(base/'.auth/wechat-capture').mkdir(mode=0o700)
  d=base/'.auth/wechat-capture/current';d.mkdir(mode=0o700);identity=s.generate(d)
  proxy={'Enabled':'Yes','Server':'127.0.0.1','Port':'7897','Authenticated Proxy Enabled':'0'}
  baseline={'https_proxy':proxy,'http_proxy':dict(proxy),'pac':{'Enabled':'No','URL':'(null)'},
    'autodiscovery':'Auto Proxy Discovery: Off','review_reasons':[],'bypass_domains':['localhost']}
  plan={'version':1,'experiment':'article_functional','duration_seconds':180,'cleanup_reserve_seconds':120,
   'baseline':baseline,'mode':s.upstream_mode(baseline),'wall_deadline':time.time()+180,**identity}
  plan['active_deadline']=plan['wall_deadline']-120
  private_write(d/'plan.json',plan);private_write(d/'state.json',{'capture_disabled':False,'status':'starting'})
  with patch.object(f,'DIRECTORY',d),patch.object(s,'ROOT',base):
   master=DumpMaster(Options(server=False,confdir=str(d/'mitmproxy')),with_termlog=True,with_dumper=True)
   addon=FunctionalAddon();master.addons.add(addon);options=master.options
   try:
    class Headers:
     reads=0
     def get(self,*_):self.reads+=1;return 'appmsg_token=FAKE_TOKEN; unrelated=DO_NOT_SAVE'
     def get_all(self,*_):self.reads+=1;return []
    fields={'__biz':next(iter(f.TARGETS_ONE)),'mid':'2247498641','idx':'1','sn':'public',
      'uin':'FAKE_UIN','key':'FAKE_KEY','pass_ticket':'FAKE_TICKET','appmsg_token':'FAKE_TOKEN'}
    reqh,resph=Headers(),Headers()
    flow=SimpleNamespace(request=SimpleNamespace(url='https://mp.weixin.qq.com/s?'+urlencode(fields),method='GET',headers=reqh),
      response=SimpleNamespace(status_code=200,headers=resph))
    addon.requestheaders(flow);addon.responseheaders(flow);assert reqh.reads==resph.reads==0
    options.update(mode=[plan['mode']],listen_host='127.0.0.1',listen_port=8899,allow_hosts=[r'^mp\.weixin\.qq\.com:443$'],
      ssl_insecure=False,upstream_cert=False,certs=['mp.weixin.qq.com='+str(d/'mitmproxy/target-key-chain.pem')],
      add_upstream_certs_to_client_chain=False,flow_detail=0,termlog_verbosity='error',command_history=False,strip_ech=False)
    options.update(liumo_compat=True)
    addon.requestheaders(flow);addon.responseheaders(flow);assert reqh.reads==resph.reads==0
    private_write(d/'state.json',{'capture_disabled':False,'status':f.READY_STATUS,
       'diagnostic_control':{'proxy_response_observed':True}})
    addon.requestheaders(flow);addon.responseheaders(flow)
    assert reqh.reads==resph.reads==1 and flow.request.stream and flow.response.stream
    data=private_json(d/'candidate.json');assert 'DO_NOT_SAVE' not in json.dumps(data)
    assert (d/'candidate.json').stat().st_mode&0o777==0o600
    addon.responseheaders(flow);assert reqh.reads==resph.reads==1
    assert addon.session.summary()['saved_by_account']=={'猫笔刀':1}
    private_write(d/'state.json',{'capture_disabled':True});addon.capture_disabled()
    assert addon.passthrough_only and not options.liumo_compat
   finally:master.shutdown()
 print(json.dumps({'actual_component':True,'listener_started':False,'real_credentials':False,'candidate_count':1}))
actual=socket.socket
def local_only(family=socket.AF_INET,*args,**kwargs):
 if family in (socket.AF_INET,socket.AF_INET6):raise AssertionError('network prohibited')
 return actual(family,*args,**kwargs)
with patch.object(socket,'socket',side_effect=local_only):asyncio.run(run())
'''
        result = subprocess.run([str(capture.ROOT / '.venv-capture/bin/python'), '-c', code], cwd=capture.ROOT,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"candidate_count": 1', result.stdout)
