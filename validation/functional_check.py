"""After C17 recovery only: at most one body GET and one comments GET."""

import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, urlsplit

from .capture import TARGETS
from .capture_session import private_json, private_write, upstream_mode
from .certificate_scope import cases
from .comments import collect_comments
from .common import ROOT, SAMPLES, new_run, parse_time, timestamp, write_json
from .credentials import check_private, read_private_credentials
from .functional_capture import DIRECTORY, TARGETS_ONE
from .http import ProbeError, WechatHTTP
from .http_archive import parse_article

EXPECTED = next(iter(TARGETS_ONE.values()))
BIZ = next(iter(TARGETS_ONE))
RESPONSE_LIMIT = 2 * 1024 * 1024
BOUNDED_BODY_LIMIT = 10 * 1024 * 1024
CURL_WRITE_OUT = ('\nLIUMO_CURL_V1:%{http_code}:%{http_connect}:%{ssl_verify_result}:'
                  '%{time_connect}:%{time_appconnect}:%{size_download}')


def curl_observation(response, limit=RESPONSE_LIMIT):
    """Return only bounded numeric telemetry and fixed message categories."""
    if type(limit) is not int or limit not in (RESPONSE_LIMIT, BOUNDED_BODY_LIMIT):
        raise ProbeError('functional_response_budget_invalid')
    raw = getattr(response, 'stderr', b'')
    category = 'unavailable'
    if isinstance(raw, bytes) and 0 < len(raw) <= 8192:
        message = raw.lower()
        patterns = {'size_limit_message': (b'exceeded the maximum allowed file size', b'maximum file size exceeded'),
                    'connection_reset_message': (b'connection reset by peer',),
                    'proxy_tunnel_message': (b'proxy connect aborted', b'connect tunnel failed'),
                    'tls_read_message': (b'sslread()', b'ssl_read', b'schannel'),
                    'connection_closed_message': (b'connection closed', b'empty reply')}
        matched = [k for k, values in patterns.items() if any(v in message for v in values)]
        category = matched[0] if len(matched) == 1 else 'ambiguous' if matched else 'other'
    observed = {'curl_exit_code': response.returncode, 'error_category': category, 'metadata_valid': False}
    body, separator, tail = response.stdout.rpartition(b'\n')
    match = re.fullmatch(rb'LIUMO_CURL_V1:([0-5][0-9]{2}):([0-5][0-9]{2}):(-?[0-9]{1,8}):'
                         rb'([0-9]{1,3}\.[0-9]{1,6}):([0-9]{1,3}\.[0-9]{1,6}):([0-9]{1,9}(?:\.0+)?)', tail)
    if separator and match:
        http, connect, verify, tcp, tls, size = match.groups()
        tcp, tls, size = float(tcp), float(tls), int(float(size))
        if tcp <= 60 and tls <= 60 and size <= limit:
            observed.update(metadata_valid=True, http_status=int(http), proxy_connect_status=int(connect),
                certificate_verify_result=int(verify), tcp_connect_seconds=tcp, tls_connect_seconds=tls,
                downloaded_bytes=size, download_limit_reached=size == limit)
    return body if observed['metadata_valid'] else b'', observed


@contextmanager
def once(observation=False, bounded_body=False, cookie_body=False):
    check_private(DIRECTORY)
    path = DIRECTORY / '.functional.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as stream:
        check_private(path)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProbeError('functional_check_busy') from None
        marker = DIRECTORY / (trial_name(observation, bounded_body, cookie_body) + '-attempt.json')
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as attempt:
            json.dump({'at': timestamp(), 'body': 0, 'comments': 0}, attempt)
            attempt.flush()
            os.fsync(attempt.fileno())
        yield


def recovered_plan():
    for path in (ROOT / '.auth', DIRECTORY.parent, DIRECTORY, DIRECTORY / 'mitmproxy', DIRECTORY / 'probes'):
        check_private(path)
    plan, state = (private_json(DIRECTORY / n) for n in ('plan.json', 'state.json'))
    recovery = state.get('recovery', {})
    if (plan.get('experiment') != 'article_functional' or plan.get('version') != 1
            or plan.get('duration_seconds') != 180 or plan.get('cleanup_reserve_seconds') != 120
            or plan.get('mode') != upstream_mode(plan['baseline'])
            or state.get('finished') is not True or state.get('status') != 'closed'
            or recovery.get('verified') is not True or recovery.get('proxy_verified') is not True
            or recovery.get('trust', {}).get('verified') is not True
            or recovery.get('process_stopped') is not True or recovery.get('keys_removed') is not True):
        raise ProbeError('functional_recovery_unverified')
    if any((DIRECTORY / 'mitmproxy' / n).exists() or (DIRECTORY / 'mitmproxy' / n).is_symlink()
           for n in ('mitmproxy-ca.pem', 'target-key-chain.pem')):
        raise ProbeError('functional_keys_still_present')
    paths = ['mitmproxy/' + n for n in ('mitmproxy-ca-cert.pem', 'unconstrained-root.pem', 'target-leaf.pem')]
    paths += ['probes/' + c['id'] + '-leaf.pem' for c in cases()]
    if set(plan.get('materials', {})) != set(paths):
        raise ProbeError('functional_material_identity_invalid')
    for name in paths:
        path = DIRECTORY / name
        check_private(path)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != plan['materials'][name]:
            raise ProbeError('functional_material_identity_invalid')
    return plan


def candidate(plan):
    data = read_private_credentials(DIRECTORY / 'candidate.json', '猫笔刀')
    identity = data.get('source_identity')
    if (data['biz'] != BIZ or not isinstance(identity, dict)
            or any(identity.get(k) != EXPECTED[k] for k in ('mid', 'idx'))):
        raise ProbeError('functional_candidate_scope_invalid')
    url = data.get('public_article_url')
    try:
        parts = urlsplit(url)
        query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=4, strict_parsing=True)
        if (parts.scheme != 'https' or parts.netloc != 'mp.weixin.qq.com' or parts.path != '/s' or parts.fragment
                or set(query) != {'__biz', 'mid', 'idx', 'sn'} or any(len(v) != 1 for v in query.values())
                or query['__biz'] != [BIZ] or query['mid'] != [EXPECTED['mid']] or query['idx'] != [EXPECTED['idx']]
                or re.fullmatch(r'[A-Za-z0-9_-]{1,128}', query['sn'][0]) is None):
            raise ValueError()
        captured = parse_time(data['captured_at']).timestamp()
        # Bind to this trial's active capture window. Recovery can take longer
        # than ten minutes; local elapsed age is not server expiry evidence.
        if not plan['wall_deadline'] - 185 <= captured <= min(plan['wall_deadline'] - 120, time.time()):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ProbeError('functional_candidate_public_identity_invalid') from None
    return data


class LimitedHTTP:
    def __init__(self, baseline, record, run=None, body_limit=RESPONSE_LIMIT):
        if type(body_limit) is not int or body_limit not in (RESPONSE_LIMIT, BOUNDED_BODY_LIMIT):
            raise ProbeError('functional_response_budget_invalid')
        self.body_limit = body_limit
        # upstream_mode proves a pre-existing local, unauthenticated upstream.
        self.upstream = upstream_mode(baseline).removeprefix('upstream:')
        self.record = record
        self.run = subprocess.run if run is None else run
        self.attempts = {'body': 0, 'comments': 0}
        self.observations = {}

    def read(self, kind, url, headers):
        if kind not in self.attempts or self.attempts[kind]:
            raise ProbeError('functional_request_budget_exhausted')
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.netloc != 'mp.weixin.qq.com' or parts.fragment
                or parts.path != ('/s' if kind == 'body' else '/mp/appmsg_comment')):
            raise ProbeError('functional_request_scope_invalid')
        query = parse_qs(parts.query)
        if (query.get('__biz') != [BIZ]
                or query.get('mid' if kind == 'body' else 'appmsgid') != [EXPECTED['mid']]
                or query.get('idx') != [EXPECTED['idx']]
                or (kind == 'comments' and query.get('action') != ['getcomment'])):
            raise ProbeError('functional_request_scope_invalid')
        self.attempts[kind] = 1
        self.record(dict(self.attempts))  # Failure here prevents the request.
        config = WechatHTTP.curl_config(url, headers)
        limit = self.body_limit if kind == 'body' else RESPONSE_LIMIT
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--globoff', '--no-netrc',
            '--proxy', self.upstream, '--noproxy', '', '--proto', '=https', '--no-location', '--no-insecure',
            '--connect-timeout', '8', '--max-time', '18', '--max-filesize', str(limit),
            '--write-out', CURL_WRITE_OUT, '--config', '-']
        env = {k: v for k, v in os.environ.items() if k.upper() not in {
            'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSLKEYLOGFILE', 'MITMPROXY_SSLKEYLOGFILE',
            'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}}
        try:
            response = self.run(argv, input=config, stdin=None, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=20, env=env, close_fds=True)
        except (OSError, subprocess.TimeoutExpired):
            self.observations[kind] = {'metadata_valid': False, 'error_category': 'process_unavailable_or_timed_out'}
            raise ProbeError('functional_transport_failed') from None
        body, self.observations[kind] = curl_observation(response, limit)
        if response.returncode:
            raise ProbeError('functional_tls_or_transport_failed', response.returncode)
        observed = self.observations[kind]
        if not observed['metadata_valid'] or observed['http_status'] == 0:
            raise ProbeError('functional_http_status_unknown')
        code = observed['http_status']
        if code != 200:
            raise ProbeError('redirect_blocked' if 300 <= code < 400 else 'http_rejected', code)
        if len(body) > limit:
            raise ProbeError('response_size_limit')
        return body


def body_request(data):
    """Pinned reference's authenticated body path; API tokens stay in APIs."""
    try:
        cookies = SimpleCookie()
        cookies.load(data.get('cookie', ''))
        ticket, session = data['pass_ticket'], cookies['wap_sid2'].value
        if any(not isinstance(value, str) or not value or len(value) > 4096 or
               any(ord(char) < 33 or ord(char) > 126 or char in ';,"\\' for char in value)
               for value in (ticket, session)):
            raise ValueError()
    except (CookieError, KeyError, ValueError, TypeError):
        raise ProbeError('functional_body_cookie_missing_or_invalid') from None
    return data['public_article_url'], {'Cookie': f'pass_ticket={ticket};wap_sid2={session}'}


def verify(data, client, output):
    result = {'status': 'blocked', 'body_verified': False,
              'comments': {'status': 'not_attempted'}, 'full_archive_verified': False}
    try:
        url, headers = body_request(data)
        raw = client.read('body', url, headers)
        html = raw.decode('utf-8')
        # The public short URL has no identity query to mask a mismatching HTML.
        parsed = parse_article(html, SAMPLES['maobidao'], '猫笔刀')
        expected = {'biz': BIZ, 'appmsgid': EXPECTED['mid'], 'idx': EXPECTED['idx']}
        if (not parsed['account_identity_verified'] or parsed['title'] != '上个月最值的一笔消费'
                or any(parsed['identity'].get(k) != value for k, value in expected.items())):
            raise ProbeError('functional_response_identity_unverified')
        result.update(body_verified=True, status='partial', body_bytes=len(raw),
                      reason='full_original_screenshot_and_images_not_verified')
        identity = parsed['identity']
        if not identity.get('comment_id') or identity['comment_id'] == '0':
            result['comments'] = {'status': 'unknown', 'reason': 'article_comment_identity_missing'}
        else:
            def request(action, values):
                if action != 'comments':
                    raise ProbeError('functional_request_budget_exhausted')
                endpoint, headers = WechatHTTP.api_request('comments', values, data)
                try:
                    payload = json.loads(client.read('comments', endpoint, headers))
                except (ValueError, UnicodeError):
                    raise ProbeError('response_not_json') from None
                if not isinstance(payload, dict):
                    raise ProbeError('response_shape_changed')
                return payload
            snapshot = collect_comments(request, identity, max_pages=1, max_reply_pages=1)
            # C16 and the user's fixed-sample screenshots show comments. An
            # empty API view cannot establish that the original page has none.
            if snapshot['status'] == 'none':
                snapshot.update(status='unknown', snapshot_finished=False, api_reported_empty=True)
                snapshot['reasons'].append('api_empty_conflicts_with_known_sample_comments')
            write_json(output / 'comments.json', snapshot)
            result['comments'] = {k: v for k, v in snapshot.items() if k != 'items'}
            result['comments']['saved_comments'] = len(snapshot['items'])
    except ProbeError as exc:
        result['reason'] = exc.reason
        if type(exc.code) is int:
            result['error_code'] = exc.code
    except UnicodeError:
        result['reason'] = 'html_encoding_invalid'
    result['requests_attempted'] = dict(client.attempts)
    result['transport_observations'] = dict(getattr(client, 'observations', {}))
    return result


def observation_plan():
    return {'experiment': 'c18_functional_observation', 'requires_new_explicit_authorization': True,
        'target': 'maobidao_fixed_article_C17_candidate_only', 'new_capture': False,
        'system_settings_changed': False, 'max_body_requests': 1, 'max_comment_requests': 1,
        'comment_request_only_after_body_identity_verified': True, 'max_seconds_per_request': 20,
        'routing': 'original_local_upstream_only', 'redirects_or_retries': False,
        'original_C17_marker_preserved': True, 'executed': False}


def observation_authorized():
    proof = private_json(DIRECTORY / 'functional-observation-authorization.json')
    old = private_json(DIRECTORY / 'functional-result.json')
    try:
        valid_time = parse_time(old['at']) <= parse_time(proof['authorized_at'])
    except (KeyError, TypeError, ValueError):
        valid_time = False
    if (proof.get('experiment') != 'c18_functional_observation' or proof.get('source') != 'explicit_user_grant'
            or proof.get('max_body_requests') != 1 or proof.get('max_comment_requests') != 1
            or proof.get('same_candidate_only') is not True or not valid_time
            or old.get('reason') != 'functional_tls_or_transport_failed' or old.get('error_code') != 56
            or old.get('requests_attempted') != {'body': 1, 'comments': 0}):
        raise ProbeError('functional_observation_not_authorized')


def trial_name(observation=False, bounded_body=False, cookie_body=False):
    if sum((observation, bounded_body, cookie_body)) > 1:
        raise ProbeError('functional_mode_not_allowed')
    return ('functional-cookie-body' if cookie_body else 'functional-bounded-body' if bounded_body else
            'functional-observation' if observation else 'functional')


def bounded_body_plan():
    return {**observation_plan(), 'experiment': 'c19_bounded_body',
            'body_response_limit_bytes': BOUNDED_BODY_LIMIT,
            'comment_response_limit_bytes': RESPONSE_LIMIT,
            'only_request_change': 'body_response_limit_2MiB_to_10MiB',
            'original_C18_marker_preserved': True}


def bounded_body_authorized():
    proof = private_json(DIRECTORY / 'functional-bounded-body-authorization.json')
    old_path = DIRECTORY / 'functional-observation-result.json'
    old = private_json(old_path)
    body = old.get('transport_observations', {}).get('body', {})
    try:
        valid_time = parse_time(old['at']) <= parse_time(proof['authorized_at'])
    except (KeyError, TypeError, ValueError):
        valid_time = False
    if (proof.get('experiment') != 'c19_bounded_body' or proof.get('source') != 'explicit_user_grant'
            or proof.get('max_body_requests') != 1 or proof.get('max_comment_requests') != 1
            or proof.get('same_candidate_only') is not True or not valid_time
            or proof.get('body_response_limit_bytes') != BOUNDED_BODY_LIMIT
            or proof.get('comment_response_limit_bytes') != RESPONSE_LIMIT
            or proof.get('source_result_sha256') != hashlib.sha256(old_path.read_bytes()).hexdigest()
            or old.get('requests_attempted') != {'body': 1, 'comments': 0}
            or old.get('body_verified') is not False or old.get('error_code') != 56
            or old.get('reason') != 'functional_tls_or_transport_failed'
            or body.get('http_status') != 200 or body.get('proxy_connect_status') != 200
            or body.get('downloaded_bytes') != RESPONSE_LIMIT):
        raise ProbeError('functional_bounded_body_not_authorized')


def cookie_body_plan():
    return {**bounded_body_plan(), 'experiment': 'c20_cookie_body',
            'only_request_change': 'body_public_article_URL_and_pass_ticket_wap_sid2_Cookie',
            'original_C19_marker_preserved': True}


def cookie_body_authorized():
    proof = private_json(DIRECTORY / 'functional-cookie-body-authorization.json')
    source = DIRECTORY / 'functional-bounded-body-result.json'
    old = private_json(source)
    body = old.get('transport_observations', {}).get('body', {})
    try:
        valid_time = parse_time(old['at']) <= parse_time(proof['authorized_at'])
    except (KeyError, TypeError, ValueError):
        valid_time = False
    if (proof.get('experiment') != 'c20_cookie_body' or proof.get('source') != 'explicit_user_grant'
            or proof.get('max_body_requests') != 1 or proof.get('max_comment_requests') != 1
            or proof.get('same_candidate_only') is not True or not valid_time
            or proof.get('body_response_limit_bytes') != BOUNDED_BODY_LIMIT
            or proof.get('comment_response_limit_bytes') != RESPONSE_LIMIT
            or proof.get('source_result_sha256') != hashlib.sha256(source.read_bytes()).hexdigest()
            or old.get('requests_attempted') != {'body': 1, 'comments': 0}
            or old.get('body_verified') is not False or old.get('reason') != 'redirect_blocked'
            or old.get('error_code') != 302 or body.get('http_status') != 302
            or body.get('curl_exit_code') != 0 or body.get('proxy_connect_status') != 200):
        raise ProbeError('functional_cookie_body_not_authorized')


def check(observation=False, bounded_body=False, cookie_body=False):
    name = trial_name(observation, bounded_body, cookie_body)
    if cookie_body:
        cookie_body_authorized()
    if bounded_body:
        bounded_body_authorized()
    if observation:
        observation_authorized()  # Never touch credentials without a new grant.
    with once(observation=observation, bounded_body=bounded_body, cookie_body=cookie_body):
        plan = recovered_plan()
        output = new_run('article-' + name if observation or bounded_body or cookie_body else 'article-functional-check')
        result = {'status': 'blocked', 'body_verified': False, 'comments': {'status': 'not_attempted'},
                  'requests_attempted': {'body': 0, 'comments': 0}, 'output': str(output)}
        try:
            data = candidate(plan)
            def record(counts):
                private_write(DIRECTORY / (name + '-attempt.json'), {'at': timestamp(), **counts})
            client = LimitedHTTP(plan['baseline'], record,
                body_limit=BOUNDED_BODY_LIMIT if bounded_body or cookie_body else RESPONSE_LIMIT)
            result.update(verify(data, client, output))
        except ProbeError as exc:
            result['reason'] = exc.reason
        result['at'] = timestamp()
        write_json(output / 'functional-summary.json', result)
        private_write(DIRECTORY / (name + '-result.json'), result)
        return result


def main():
    try:
        if sys.argv[1:] == ['--observation-plan']:
            result = observation_plan()
        elif sys.argv[1:] == ['--bounded-body-plan']:
            result = bounded_body_plan()
        elif sys.argv[1:] == ['--bounded-body-once']:
            result = check(bounded_body=True)
        elif sys.argv[1:] == ['--cookie-body-plan']:
            result = cookie_body_plan()
        elif sys.argv[1:] == ['--cookie-body-once']:
            result = check(cookie_body=True)
        elif sys.argv[1:] in ([], ['--observation-once']):
            result = check(observation=bool(sys.argv[1:]))
        else:
            raise ProbeError('functional_mode_not_allowed')
    except ProbeError as exc:
        result = {'status': 'blocked', 'reason': exc.reason}
    except FileExistsError:
        result = {'status': 'blocked', 'reason': 'functional_check_already_attempted'}
    except Exception:
        result = {'status': 'not_verified', 'reason': 'functional_check_failed'}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('body_verified') or result.get('executed') is False else 2


if __name__ == '__main__':
    raise SystemExit(main())
