"""Narrow profile header capture and one immediate list probe per account."""

import json
import time
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, unquote_plus, urlencode, urlsplit

from .capture import TARGETS
from .common import parse_time, timestamp
from .credentials import ACCOUNTS, check_private
from .http import ProbeError, WechatHTTP
from .mp_source import parse_profile, profile_shape

ENDPOINT = 'https://mp.weixin.qq.com/mp/profile_ext'
QUERY_FIELDS = {'action', '__biz', 'uin', 'key', 'pass_ticket', 'appmsg_token', 'poc_token',
                'scene', 'subscene', 'offset', 'count', 'f', 'is_ok', 'x5', 'lang',
                'devicetype', 'version', 'nettype', 'wx_header', 'ascene'}
COOKIE_FIELDS = {'uin', 'key', 'pass_ticket', 'appmsg_token', 'wap_sid2', 'wxtoken',
                 'wxtokenkey', 'poc_sid', 'poc_token'}
HEADER_FIELDS = {'User-Agent', 'Accept', 'Accept-Language', 'Accept-Encoding', 'Origin', 'Referer'}


def safe_value(value, maximum=4096):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ProbeError('profile_capture_field_invalid')
    return value


def select_profile(url, method, status, targets=TARGETS):
    if not isinstance(url, str) or len(url) > 16384 or method != 'GET' or status != 200:
        raise ProbeError('profile_capture_not_matching')
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.netloc != 'mp.weixin.qq.com'
                or parts.path != '/mp/profile_ext' or parts.fragment):
            raise ProbeError('profile_capture_not_matching')
        # Match public scope before parsing any private query or headers.
        scope = {}
        fields = parts.query.split('&')
        if len(fields) > 60:
            raise ProbeError('profile_capture_not_matching')
        for field in fields:
            key, _, value = field.partition('=')
            key = unquote_plus(key)
            if key in {'action', '__biz'}:
                scope.setdefault(key, []).append(unquote_plus(value))
        if (len(scope.get('action', [])) != 1 or len(scope.get('__biz', [])) != 1
                or scope['action'][0] not in {'home', 'getmsg'} or scope['__biz'][0] not in targets):
            raise ProbeError('profile_capture_not_matching')
        return targets[scope['__biz'][0]], parse_qs(parts.query, keep_blank_values=True, max_num_fields=60)
    except ValueError:
        raise ProbeError('profile_capture_not_matching') from None


def filtered_referer(value, biz):
    safe_value(value, 16384)
    parts = urlsplit(value)
    if parts.scheme != 'https' or parts.netloc != 'mp.weixin.qq.com' or parts.path != '/mp/profile_ext':
        raise ProbeError('profile_capture_referer_rejected')
    query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=60)
    if query.get('__biz') != [biz] or query.get('action') != ['home']:
        raise ProbeError('profile_capture_referer_rejected')
    if any(len(values) != 1 for key, values in query.items() if key in QUERY_FIELDS):
        raise ProbeError('profile_capture_ambiguous_fields')
    return ENDPOINT + '?' + urlencode({key: safe_value(values[0]) for key, values in query.items()
                                      if key in QUERY_FIELDS})


def extract_profile(target, query, headers, set_cookies=()):
    if any(len(values) != 1 for key, values in query.items() if key in QUERY_FIELDS):
        raise ProbeError('profile_capture_ambiguous_fields')
    selected = {key: safe_value(values[0]) for key, values in query.items() if key in QUERY_FIELDS}
    selected_headers = {}
    for name in HEADER_FIELDS:
        value = headers.get(name, '')
        if not value:
            continue
        if name == 'Referer':
            value = filtered_referer(value, selected['__biz'])
        elif name == 'Origin' and value != 'https://mp.weixin.qq.com':
            raise ProbeError('profile_capture_origin_rejected')
        selected_headers[name] = safe_value(value, 16384 if name == 'Referer' else 4096)
    if 'User-Agent' not in selected_headers:
        raise ProbeError('profile_capture_user_agent_missing')
    cookie_values = {}
    try:
        for text in [headers.get('Cookie', ''), *set_cookies]:
            parsed = SimpleCookie()
            parsed.load(safe_value(text, 32768))
            for key in COOKIE_FIELDS:
                if key in parsed:
                    cookie_values[key] = safe_value(parsed[key].value)
    except CookieError:
        raise ProbeError('profile_capture_cookie_invalid') from None
    if not any(selected.get(key) or cookie_values.get(key) for key in ('key', 'pass_ticket', 'appmsg_token')):
        raise ProbeError('profile_capture_session_fields_missing')
    cookie = SimpleCookie()
    for key, value in sorted(cookie_values.items()):
        cookie[key] = value
    if cookie:
        selected_headers['Cookie'] = '; '.join(item.OutputString() for item in cookie.values())
    if selected['action'] == 'getmsg':
        if selected.get('offset') != '0':
            raise ProbeError('profile_capture_first_page_required')
        if not selected.get('count', '').isdigit() or not 1 <= int(selected['count']) <= 10:
            raise ProbeError('profile_capture_count_outside_scope')
    return {'version': 1, 'account': target['account'], 'biz': selected['__biz'],
            'action': selected['action'], 'captured_at': timestamp(), 'query': selected,
            'headers': selected_headers,
            'omitted_query_fields': sum(len(values) for key, values in query.items() if key not in QUERY_FIELDS),
            'raw_request_saved': False, 'authentication_verified': False}


class ProfileCaptureSession:
    def __init__(self, directory, seconds=600, targets=TARGETS, clock=time.monotonic):
        if type(seconds) is not int or not 1 <= seconds <= 600:
            raise ValueError('invalid_capture_duration')
        self.directory, self.targets, self.clock = directory, targets, clock
        check_private(directory)
        self.deadline, self.stopped = clock() + seconds, False
        self.saved, self.events, self.seen = {}, {}, set()

    def stop(self):
        self.stopped = True

    def matching(self, url, method, status):
        if self.stopped or self.clock() >= self.deadline:
            raise ProbeError('profile_capture_window_closed')
        return select_profile(url, method, status, self.targets)

    def observe(self, url, method, status, headers, set_cookies=()):
        try:
            target, query = self.matching(url, method, status)
            key = (target['account'], query['action'][0])
            if key in self.seen:
                raise ProbeError('profile_capture_already_saved')
            data = extract_profile(target, query, headers, set_cookies)
            from .capture_session import private_write
            path = self.directory / (ACCOUNTS[target['account']] + '-' + data['action'] + '.json')
            if path.exists() or path.is_symlink():
                raise ProbeError('profile_capture_existing_file')
            private_write(path, data)
            self.seen.add(key)
            self.saved.setdefault(target['account'], []).append(data['action'])
            reason = 'profile_capture_saved_not_authentication_verified'
        except ProbeError as exc:
            reason = exc.reason
        except Exception:
            reason = 'profile_capture_store_failed'
        self.events[reason] = self.events.get(reason, 0) + 1
        return reason

    def summary(self):
        return {'status': 'closed' if self.stopped or self.clock() >= self.deadline else 'open',
                'saved_actions_by_account': dict(self.saved), 'events': dict(self.events),
                'authentication_verified': False, 'automatic_renewal_verified': False}


def probe_profile_snapshot(data, client=None, now=None):
    """One request only; parse metadata/counts without saving article contents."""
    result = {'at': timestamp(), 'status': 'not_verified', 'requests_attempted': 0,
              'authentication_verified': False, 'publication_times_verified': False,
              'account_identity_verified': False, 'evidence': 'live_captured_profile_probe'}
    try:
        account, biz = data['account'], data['biz']
        if account not in ACCOUNTS or TARGETS.get(biz, {}).get('account') != account:
            raise ProbeError('profile_probe_scope_rejected')
        result['account'] = account
        age = ((parse_time(now or timestamp()) - parse_time(data['captured_at'])).total_seconds())
        if not 0 <= age <= 30:
            raise ProbeError('profile_probe_capture_too_old')
        query, headers = data['query'], data['headers']
        if (not isinstance(query, dict) or set(query) - QUERY_FIELDS or not isinstance(headers, dict)
                or set(headers) - (HEADER_FIELDS | {'Cookie'})):
            raise ProbeError('profile_probe_fields_rejected')
        _, checked = select_profile(ENDPOINT + '?' + urlencode(query), 'GET', 200)
        normalized = extract_profile(TARGETS[biz], checked, headers)
        if normalized['action'] != 'getmsg' or normalized['biz'] != biz or data['action'] != 'getmsg':
            raise ProbeError('profile_probe_scope_rejected')
        omitted = data.get('omitted_query_fields', 0)
        if type(omitted) is not int or not 0 <= omitted <= 60:
            raise ProbeError('profile_probe_fields_rejected')
        result['omitted_query_fields'] = omitted
        result['request_reconstruction'] = 'allowlisted_fields_not_raw_request_replay'
        client = client if client is not None else WechatHTTP(transport='curl')
        result['requests_attempted'] = 1
        payload = json.loads(client.read(ENDPOINT + '?' + urlencode(normalized['query']), normalized['headers']))
        result['shape'] = profile_shape(payload)
        items, more, _ = parse_profile(payload, account, biz)
        identified = sum(parse_qs(urlsplit(item['url']).query).get('__biz') == [biz] for item in items)
        result.update(status='list_shape_observed', items_observed=len(items), has_more=more,
                      explicitly_identified_items=identified,
                      account_identity_verified=bool(items) and identified == len(items))
    except ProbeError as exc:
        result['reason'] = exc.reason
        if exc.code is not None:
            result['error_code'] = exc.code
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        result['reason'] = 'profile_probe_input_or_response_invalid'
    return result
