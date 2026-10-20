"""One native comment baseline, private context and an offline comparison only."""

import hashlib
import json
import os
import time
import zlib
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, unquote_plus, urlsplit

from .capture import COOKIE_NAMES, TARGETS
from .capture_session import private_json
from .common import ROOT, SAMPLES, article_url, new_run, parse_time, timestamp, write_json
from .credentials import check_private, read_private_credentials
from .http import ProbeError, USER_AGENT

DIRECTORY = ROOT / '.auth/wechat-capture/comment-baseline-session'
BASELINE_DIRECTORY = DIRECTORY
REFRESH_DIRECTORY = DIRECTORY.parent / 'comment-refresh-session'
EXPERIMENT = 'c21_comment_baseline'
ARTICLE_DIRECTORY = ROOT / '.auth/wechat-capture/article-functional-session'
AUTHORIZATION = DIRECTORY.parent / 'comment-baseline-authorization.json'
UI_READY = ROOT / '.tmp/wechat-session-validation/comment-ui-ready.json'
READY_STATUS = 'ready_load_maobidao_comments_for_baseline'
BIZ = 'MzE5ODk2NjUwOA=='
IDENTITY = {'biz': BIZ, 'appmsgid': TARGETS[BIZ]['mid'], 'idx': TARGETS[BIZ]['idx']}
LIMIT = 1024 * 1024
QUERY_FIELDS = ('action', 'scene', 'appmsgid', 'idx', '__biz', 'comment_id', 'uin', 'key',
                'pass_ticket', 'appmsg_token', 'wxtoken', 'devicetype', 'comment_scene',
                'buffer', 'offset', 'limit', 'x5', 'f')
HEADER_FIELDS = ('User-Agent', 'Accept', 'Accept-Language', 'X-Requested-With')
PUBLIC_FAILURE_REASONS = frozenset({
    'comment_baseline_not_authorized', 'comment_baseline_not_running',
    'comment_baseline_recovery_unverified', 'comment_baseline_identity_invalid',
    'compat_UI_confirmation_required', 'compat_session_already_exists',
    'compat_previous_recovery_unverified', 'functional_previous_recovery_unverified',
    'comment_previous_recovery_unverified', 'anchor_previous_recovery_unverified',
    'compat_lifecycle_busy', 'compat_plan_invalid', 'compat_material_invalid',
    'compat_observation_phase_invalid', 'compat_observation_not_running',
    'compat_counters_invalid', 'diagnostic_control_unverified',
    'preflight_system_authorization_unavailable', 'preflight_command_unavailable',
    'preflight_query_failed', 'preflight_services_shape_unknown',
    'preflight_active_interface_unknown', 'preflight_active_service_ambiguous',
    'preflight_proxy_shape_unknown', 'preflight_pac_shape_unknown',
    'preflight_autodiscovery_shape_unknown', 'preflight_bypass_shape_unknown',
    'preflight_loopback_unavailable', 'session_baseline_not_supported',
    'session_target_bypasses_proxy', 'session_file_invalid',
    'credentials_missing', 'credential_symlink_rejected', 'credential_permissions_rejected',
    'comment_refresh_previous_unverified',
})

MATCH_CATEGORIES = ('non_GET', 'query_invalid', 'query_ambiguous', 'action_other',
                    'account_missing', 'account_other', 'article_missing', 'article_other',
                    'idx_missing', 'idx_other', 'comment_id_invalid', 'public_shape_matches')
MATCH_COUNTERS = frozenset('comment_' + phase + '_' + kind
                          for phase in ('requests', 'responses') for kind in MATCH_CATEGORIES)


def select_refresh_mode():
    """Only the independent C22 scope; no arbitrary runtime configuration."""
    global DIRECTORY, AUTHORIZATION, UI_READY, READY_STATUS, EXPERIMENT
    DIRECTORY = REFRESH_DIRECTORY
    AUTHORIZATION = DIRECTORY.parent / 'comment-refresh-authorization.json'
    UI_READY = ROOT / '.tmp/wechat-session-validation/comment-refresh-ui-ready.json'
    READY_STATUS = 'ready_user_refresh_maobidao_comments'
    EXPERIMENT = 'c22_comment_refresh'


def comment_match_category(url, method):
    """Inspect only five public query values on the single known endpoint."""
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.netloc != 'mp.weixin.qq.com' or p.path != '/mp/appmsg_comment':
            return None
        if method != 'GET':
            return 'non_GET'
        if len(url) > 32768 or p.fragment:
            return 'query_invalid'
        fields = p.query.split('&')
        if len(fields) > 60:
            return 'query_invalid'
        values = {}
        for field in fields:
            key, sep, raw = field.partition('=')
            if not sep:
                return 'query_invalid'
            key = unquote_plus(key)
            if key not in ('action', '__biz', 'appmsgid', 'idx', 'comment_id'):
                continue
            if key in values:
                return 'query_ambiguous'
            value = unquote_plus(raw)
            if len(value) > 4096 or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                return 'query_invalid'
            values[key] = value
        if values.get('action') != 'getcomment':
            return 'action_other'
        for field, expected, prefix in (('__biz', BIZ, 'account'),
                ('appmsgid', IDENTITY['appmsgid'], 'article'), ('idx', IDENTITY['idx'], 'idx')):
            if field not in values:
                return prefix + '_missing'
            if values[field] != expected:
                return prefix + '_other'
        if not values.get('comment_id', '').isdigit() or len(values['comment_id']) > 32:
            return 'comment_id_invalid'
        return 'public_shape_matches'
    except (TypeError, ValueError):
        return None


def review_plan():
    result = {'experiment': EXPERIMENT, 'requires_new_explicit_authorization': True,
            'target': 'maobidao_fixed_article_only', 'duration_seconds': 180,
            'cleanup_reserve_seconds': 120, 'max_passive_responses': 1,
            'wire_limit_bytes': LIMIT, 'decoded_limit_bytes': LIMIT,
            'full_single_Cookie_field_private': True, 'comment_content_persisted': False,
            'active_API_requests': 0, 'public_control_requests': 1,
            'automatic_replay': False, 'executed': False}
    if EXPERIMENT == 'c22_comment_refresh':
        result.update(manual_menu_refresh_once=True, fixed_comment_match_counters=True,
                      previous_system_experiments=9)
    return result


def authorized():
    proof = private_json(AUTHORIZATION)
    refresh = EXPERIMENT == 'c22_comment_refresh'
    source = BASELINE_DIRECTORY / 'state.json' if refresh else ARTICLE_DIRECTORY / 'functional-cookie-body-result.json'
    old = private_json(source)
    try:
        valid_time = parse_time(old['recovery_completed_at'] if refresh else old['at']) <= parse_time(proof['authorized_at'])
    except (KeyError, TypeError, ValueError):
        valid_time = False
    valid_source = (old.get('body_verified') is True
                   and old.get('requests_attempted') == {'body': 1, 'comments': 1}
                   and old.get('comments', {}).get('error_code') == -3)
    if refresh:
        recovery = old.get('recovery', {})
        valid_source = (old.get('status') == 'closed' and old.get('finished') is True
            and all(recovery.get(k) is True for k in ('verified', 'proxy_verified', 'process_stopped', 'keys_removed'))
            and recovery.get('trust', {}).get('verified') is True
            and old.get('capture', {}).get('matched_response_count') == 0
            and old.get('comment_baseline_observed') is False
            and proof.get('manual_menu_refresh_once') is True
            and proof.get('fixed_comment_match_counters') is True)
    if (EXPERIMENT not in ('c21_comment_baseline', 'c22_comment_refresh')
            or proof.get('experiment') != EXPERIMENT or proof.get('source') != 'explicit_user_grant'
            or proof.get('source_result_sha256') != hashlib.sha256(source.read_bytes()).hexdigest()
            or not valid_time or type(proof.get('max_passive_responses')) is not int
            or proof.get('max_passive_responses') != 1
            or proof.get('wire_limit_bytes') != LIMIT or proof.get('decoded_limit_bytes') != LIMIT
            or proof.get('full_single_Cookie_field_private') is not True
            or proof.get('duration_seconds') != 180 or proof.get('cleanup_reserve_seconds') != 120
            or not valid_source):
        raise ProbeError('comment_baseline_not_authorized')


def select_runtime():
    from . import compat_session as runtime
    runtime.DIRECTORY = DIRECTORY
    runtime.PREVIOUS = (*runtime.anchor.PREVIOUS, runtime.anchor.DIRECTORY,
                        runtime.COMPAT_DIRECTORY, ARTICLE_DIRECTORY)
    refresh = EXPERIMENT == 'c22_comment_refresh'
    if refresh:
        runtime.PREVIOUS = (*runtime.PREVIOUS, BASELINE_DIRECTORY)
    runtime.UI_READY = UI_READY
    runtime.EXPERIMENT = 'comment_refresh' if refresh else 'comment_baseline'
    runtime.ADDON = ROOT / ('validation/comment_refresh_addon.py' if refresh else 'validation/comment_addon.py')
    runtime.READY_STATUS = READY_STATUS
    runtime.WORKER_FLAG = '--comment-refresh-worker' if refresh else '--comment-baseline-worker'
    runtime.RUN_SLUG = 'comment-refresh-session' if refresh else 'comment-baseline-session'
    return runtime


def ready():
    authorized()
    state = private_json(DIRECTORY / 'state.json')
    return (state.get('status') == READY_STATUS and state.get('capture_disabled') is False
            and state.get('diagnostic_control', {}).get('proxy_response_observed') is True)


def store_baseline(data):
    check_private(DIRECTORY)
    encoded = json.dumps(data, ensure_ascii=False).encode('utf-8')
    if len(encoded) > 131072:
        raise ProbeError('comment_baseline_size_limit')
    fd = os.open(DIRECTORY / 'baseline.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def decode_body(raw, encoding):
    if len(raw) > LIMIT:
        raise ProbeError('comment_wire_size_limit')
    if encoding in ('', 'identity'):
        return raw
    try:
        if encoding in ('gzip', 'deflate'):
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            data = decoder.decompress(raw, LIMIT + 1)
            if len(data) > LIMIT:
                raise ProbeError('comment_decoded_size_limit')
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ProbeError('comment_encoded_body_invalid')
        elif encoding == 'br':
            import brotli  # Existing isolated capture environment, bounded API 1.2.0.
            decoder = brotli.Decompressor()
            data = decoder.process(raw, output_buffer_limit=LIMIT + 1)
            if len(data) > LIMIT or not decoder.can_accept_more_data() and not decoder.is_finished():
                raise ProbeError('comment_decoded_size_limit')
            if not decoder.is_finished():
                raise ProbeError('comment_encoded_body_invalid')
        else:
            raise ProbeError('comment_encoding_unsupported')
    except ProbeError:
        raise
    except Exception:
        raise ProbeError('comment_encoded_body_invalid') from None
    return data


def public_referer(value):
    try:
        p = urlsplit(value)
        if p.scheme != 'https' or p.netloc != 'mp.weixin.qq.com':
            return 'missing' if not value else 'other', ''
        if p.path in ('', '/') and not p.query:
            return 'target_root', 'https://mp.weixin.qq.com/'
        if p.path == urlsplit(SAMPLES['maobidao']).path and not p.query:
            return 'target_article', SAMPLES['maobidao']
        q = parse_qs(p.query, max_num_fields=60)
        if p.path == '/s' and all(q.get(k) == [v] for k, v in
                {'__biz': BIZ, 'mid': IDENTITY['appmsgid'], 'idx': IDENTITY['idx']}.items()):
            return 'target_article', article_url(value)
        return 'target_other', ''
    except (ValueError, ProbeError):
        return 'other', ''


class CommentBaselineSession:
    def __init__(self, writer=None, gate=None, clock=time.monotonic):
        self.writer = store_baseline if writer is None else writer
        self.gate = ready if gate is None else gate
        self.clock, self.deadline = clock, clock() + 60
        self.stopped = self.attempted = self.saved = False
        self.reason = 'waiting_for_matching_comment'
        self.response = {}
        self.buffer = bytearray()
        self.pending = None

    def matching(self, url, method, status):
        if self.stopped or self.attempted or self.clock() >= self.deadline or not self.gate():
            raise ProbeError('comment_gate_closed')
        try:
            p = urlsplit(url)
            if (len(url) > 32768 or method != 'GET' or p.scheme != 'https'
                    or p.netloc != 'mp.weixin.qq.com' or p.path != '/mp/appmsg_comment' or p.fragment):
                raise ValueError()
            fields = p.query.split('&')
            if len(fields) > 60:
                raise ValueError()
            q, raw, additional = {}, {}, set()
            for field in fields:
                key, separator, value = field.partition('=')
                if not separator:
                    raise ValueError()
                key = unquote_plus(key)
                if key in QUERY_FIELDS:
                    q.setdefault(key, []).append(unquote_plus(value))
                    raw[key] = value
                else:
                    additional.add(key)  # Unknown values are never decoded.
            for key, value in {'action': 'getcomment', '__biz': BIZ,
                               'appmsgid': IDENTITY['appmsgid'], 'idx': IDENTITY['idx']}.items():
                if q.get(key) != [value]:
                    raise ValueError()
            if any(len(v) != 1 or len(v[0]) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in v[0])
                   for k, v in q.items() if k in QUERY_FIELDS):
                raise ValueError()
            if not q.get('comment_id', [''])[0].isdigit() or len(q['comment_id'][0]) > 32:
                raise ValueError()
            data = {'query': {k: q[k][0] for k in QUERY_FIELDS if k in q}, 'query_encoded': raw,
                    'additional_query_count': len(additional)}
        except (ValueError, TypeError):
            raise ProbeError('comment_scope_not_matching') from None
        if status != 200:
            self.attempted = True
            self.response = {'http_status': status if type(status) is int else 0}
            self.reason = 'native_comment_HTTP_rejected'
            self.stop()
            raise ProbeError('comment_HTTP_rejected')
        return data

    def begin(self, data, headers, set_cookies, encoding):
        if self.attempted or self.stopped or self.clock() >= self.deadline or not self.gate():
            raise ProbeError('comment_gate_closed')
        self.attempted = True
        try:
            if set(headers) != set(HEADER_FIELDS) | {'Cookie', 'Referer'}:
                raise ValueError()
            if any(not isinstance(v, str) or len(v) > (16384 if k == 'Cookie' else 8192)
                   or any(ord(c) < 32 or ord(c) == 127 for c in v) for k, v in headers.items()):
                raise ValueError()
            if len(set_cookies) > 32 or sum(len(v) for v in set_cookies) > 32768:
                raise ValueError()
            updates = {}
            for row in set_cookies:
                if '\r' in row or '\n' in row:
                    raise ValueError()
                parsed = SimpleCookie()
                parsed.load(row)
                updates.update({k: v.value for k, v in parsed.items()})
            scope, referer = public_referer(headers['Referer'])
            self.pending = {**data, 'headers': {k: headers[k] for k in HEADER_FIELDS},
                'request_cookie': headers['Cookie'], 'referer_scope': scope, 'public_referer': referer,
                'response_cookie_updates': updates,
                'encoding': encoding if encoding in ('', 'identity', 'gzip', 'deflate', 'br') else 'unsupported'}
        except (ValueError, TypeError, CookieError):
            self.reason = 'comment_context_invalid'
            self.stop()
            raise ProbeError('comment_context_invalid') from None
        return self.stream

    def stream(self, chunk):
        if self.stopped:
            return chunk
        if self.clock() >= self.deadline or not self.gate():
            self.stop()
            return chunk
        if chunk:
            if len(self.buffer) + len(chunk) > LIMIT:
                self.reason = 'comment_wire_size_limit'
                self.stop()
            else:
                self.buffer.extend(chunk)
            return chunk
        try:
            raw = decode_body(bytes(self.buffer), self.pending['encoding'])
            payload = json.loads(raw)
            base = payload.get('base_resp', {}) if isinstance(payload, dict) else {}
            ret = base.get('ret') if isinstance(base, dict) else None
            if type(ret) is not int or not -2**31 <= ret < 2**31:
                raise ProbeError('comment_business_status_unknown')
            self.response = {'http_status': 200, 'business_code': ret, 'wire_bytes': len(self.buffer),
                             'decoded_bytes': len(raw)}
            if ret:
                raise ProbeError('native_comment_business_rejected')
            rows = payload.get('elected_comment')
            if not isinstance(rows, list) or any(not isinstance(v, dict) for v in rows):
                raise ProbeError('native_comment_shape_unknown')
            self.response['comment_items_count'] = len(rows)
            if not rows:
                raise ProbeError('native_comment_empty_not_success_baseline')
            self.writer({'version': 1, 'target': IDENTITY, 'captured_at': timestamp(),
                         **self.pending, 'response': self.response})
            self.saved = True
            self.reason = 'native_comment_success_baseline_saved'
        except ProbeError as exc:
            self.reason = exc.reason
        except (ValueError, UnicodeError, RecursionError, TypeError):
            self.reason = 'comment_response_invalid'
        except Exception:
            self.reason = 'comment_baseline_store_failed'
        finally:
            self.stop()
        return chunk

    def stop(self):
        if self.reason == 'waiting_for_matching_comment':
            self.reason = 'comment_stream_incomplete' if self.attempted else 'no_matching_comment_observed'
        self.stopped = True
        self.buffer.clear()
        self.pending = None

    def summary(self):
        return {'status': 'closed' if self.stopped or self.clock() >= self.deadline else 'open',
                'matched_response_count': int(self.attempted), 'success_baseline_saved': self.saved,
                'saved_by_account': {'猫笔刀': 1} if self.saved else {},
                'reason': self.reason, 'response': dict(self.response),
                'comment_content_persisted': False, 'active_API_requests': 0}


def compare():
    authorized()
    runtime = select_runtime()
    plan = runtime.load_plan()
    state = private_json(DIRECTORY / 'state.json')
    recovery = state.get('recovery', {})
    if (state.get('status') != 'closed' or state.get('finished') is not True
            or any(recovery.get(k) is not True for k in ('verified', 'proxy_verified', 'process_stopped', 'keys_removed'))
            or recovery.get('trust', {}).get('verified') is not True
            or any((DIRECTORY / 'mitmproxy' / name).exists() or (DIRECTORY / 'mitmproxy' / name).is_symlink()
                   for name in runtime.KEYS)):
        raise ProbeError('comment_baseline_recovery_unverified')
    record = private_json(DIRECTORY / 'baseline.json')
    captured = parse_time(record['captured_at']).timestamp()
    response = record.get('response', {})
    if (record.get('version') != 1 or record.get('target') != IDENTITY
            or not isinstance(record.get('query'), dict)
            or any(record['query'].get(k) != v for k, v in
                   {'action': 'getcomment', '__biz': BIZ, 'appmsgid': IDENTITY['appmsgid'],
                    'idx': IDENTITY['idx']}.items())
            or not plan['wall_deadline'] - 180 <= captured <= plan['active_deadline']
            or type(response.get('business_code')) is not int or response.get('business_code') != 0
            or response.get('http_status') != 200
            or any(type(response.get(k)) is not int or not 0 <= response[k] <= LIMIT
                   for k in ('wire_bytes', 'decoded_bytes', 'comment_items_count'))
            or response.get('comment_items_count', 0) < 1
            or record.get('referer_scope') not in ('missing', 'other', 'target_root', 'target_article', 'target_other')
            or type(record.get('additional_query_count')) is not int
            or not 0 <= record['additional_query_count'] <= 60):
        raise ProbeError('comment_baseline_identity_invalid')
    old = read_private_credentials(ARTICLE_DIRECTORY / 'candidate.json', '猫笔刀')
    expected = {'action': 'getcomment', 'scene': '0', 'appmsgid': IDENTITY['appmsgid'], 'idx': IDENTITY['idx'],
        '__biz': BIZ, **{k: old[k] for k in ('uin', 'key', 'pass_ticket', 'appmsg_token')},
        'wxtoken': '777', 'devicetype': 'UnifiedPCMac', 'comment_scene': '0', 'buffer': '',
        'offset': '0', 'limit': '100', 'x5': '0', 'f': 'json'}
    native = record['query']
    fields = {k: 'not_retained_in_C20' if k == 'comment_id' else 'missing_in_native' if k not in native
              else 'same' if native[k] == expected[k] else 'changed' for k in QUERY_FIELDS}
    before, after = SimpleCookie(), SimpleCookie()
    before.load(old.get('cookie', ''))
    after.load(record['request_cookie'])
    cookies = {k: 'missing_in_native' if k not in after else 'not_in_old_capture' if k not in before
               else 'same' if before[k].value == after[k].value else 'changed' for k in sorted(COOKIE_NAMES)}
    result = {'at': timestamp(), 'status': 'native_comment_baseline_compared_offline', 'query': fields,
        'known_Cookie_fields': cookies, 'additional_native_Cookie_count': len(set(after) - COOKIE_NAMES),
        'additional_query_count': record['additional_query_count'],
        'UA_matches_C20': record['headers']['User-Agent'] == USER_AGENT,
        'Accept_matches_C20': record['headers']['Accept'] == 'application/json',
        'Accept_Language_present': bool(record['headers']['Accept-Language']),
        'X_Requested_With_present': bool(record['headers']['X-Requested-With']),
        'referer_scope': record['referer_scope'],
        'known_response_Cookie_updates': {k: k in record['response_cookie_updates'] for k in sorted(COOKIE_NAMES)},
        'additional_response_Cookie_count': len(set(record['response_cookie_updates']) - COOKIE_NAMES),
        'native_response': {k: response[k] for k in ('http_status', 'business_code', 'wire_bytes', 'decoded_bytes', 'comment_items_count')},
        'API_replay_verified': False, 'minus3_cause_verified': False,
        'comment_archive_complete': False, 'network_requests': 0}
    out = new_run('comment-baseline-comparison')
    result['output'] = str(out)
    write_json(out / 'comparison-summary.json', result)
    return result


def session():
    authorized()
    return select_runtime().session()


def recover():
    return select_runtime().manual_recover()


def observe(phase):
    result = select_runtime().observe(phase)
    if EXPERIMENT == 'c22_comment_refresh':
        capture = private_json(DIRECTORY / 'capture.json')
        counters = {key: capture.get('diagnostics', {}).get(key, 0) for key in sorted(MATCH_COUNTERS)}
        if any(type(v) is not int or not 0 <= v <= 10**9 for v in counters.values()):
            raise ProbeError('compat_counters_invalid')
        result['comment_match_counters'] = counters
        from .capture_session import private_write
        private_write(DIRECTORY / (phase + '.json'), result)
    return result


def finish():
    # A completed stream is already closed; requesting cleanup must not require
    # an open capture or manufacture an after-refresh observation.
    runtime = select_runtime()
    runtime.load_plan()
    state = private_json(DIRECTORY / 'state.json')
    if state.get('status') != READY_STATUS or state.get('finished') is not False:
        raise ProbeError('comment_baseline_not_running')
    fd = os.open(DIRECTORY / 'FINISH', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    return {'status': 'cleanup_requested', 'UI_refresh_verified_by_snapshot': False}
