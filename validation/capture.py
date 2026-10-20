"""Finite, passive matching of the two known article responses; no networking."""

import time
from http.cookies import SimpleCookie, CookieError
from urllib.parse import parse_qs, unquote_plus, urlsplit

from .common import timestamp
from .credentials import save_captured_credentials, validate_credentials
from .http import ProbeError

# Public identifiers from the project's already saved sample-page observations.
# They are not authentication credentials. Fresh identity confirmation is still
# required before any live interface or full-archive claim.
TARGETS = {
    "MzE5ODk2NjUwOA==": {"account": "猫笔刀", "mid": "2247498641", "idx": "1"},
    "MzA4NTQwNDcyMA==": {"account": "stormzhang", "mid": "2650682490", "idx": "1"},
}
COOKIE_NAMES = {"appmsg_token", "wap_sid2", "pass_ticket", "wxtoken"}


def select_target(url, method, status, targets):
    if len(url) > 16384 or method != "GET" or status != 200:
        raise ProbeError("capture_not_matching")
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname != "mp.weixin.qq.com" or parts.port not in (None, 443)
                or parts.username is not None or parts.password is not None or parts.path != "/s" or parts.fragment):
            raise ProbeError("capture_not_matching")
        fields = parts.query.split("&")
        if len(fields) > 60:
            raise ProbeError("capture_not_matching")
        scope = {}
        for field in fields:
            key, _, value = field.partition("=")
            key = unquote_plus(key)
            if key in {"__biz", "mid", "idx"}:
                scope.setdefault(key, []).append(unquote_plus(value))
        for name in ("__biz", "mid", "idx"):
            if len(scope.get(name, [])) != 1:
                raise ProbeError("capture_not_matching")
        target = targets.get(scope["__biz"][0])
        if not target or any(scope[name][0] != target[name] for name in ("mid", "idx")):
            raise ProbeError("capture_not_matching")
        query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=60)
        return target, query
    except ValueError:
        raise ProbeError("capture_not_matching") from None


def extract_credential(target, query, request_cookie, set_cookies, captured_at=None):
    cookie_values = {}
    try:
        for header in [request_cookie, *set_cookies]:
            if not isinstance(header, str) or len(header) > 32768 or "\r" in header or "\n" in header:
                raise ProbeError("capture_cookie_invalid")
            parsed = SimpleCookie()
            parsed.load(header)
            for name in COOKIE_NAMES:
                if name in parsed:
                    cookie_values[name] = parsed[name].value
    except CookieError:
        raise ProbeError("capture_cookie_invalid") from None
    result = {"account": target["account"], "biz": query["__biz"][0],
              "captured_at": captured_at or timestamp(),
              "source_identity": {"mid": target["mid"], "idx": target["idx"]}}
    for name in ("uin", "key", "pass_ticket", "appmsg_token"):
        values = query.get(name, [])
        if len(values) > 1:
            raise ProbeError("capture_ambiguous_fields")
        result[name] = values[0] if values else (cookie_values.get(name, "") if name in COOKIE_NAMES else "")
    filtered = SimpleCookie()
    for name, value in sorted(cookie_values.items()):
        filtered[name] = value
    result["cookie"] = "; ".join(morsel.OutputString() for morsel in filtered.values())
    try:
        validate_credentials(result, target["account"])
    except ProbeError:
        raise ProbeError("capture_required_fields_missing_or_invalid") from None
    return result


class CaptureSession:
    def __init__(self, seconds=600, writer=save_captured_credentials, targets=None, clock=time.monotonic):
        if type(seconds) is not int or not 1 <= seconds <= 600:
            raise ValueError("invalid_capture_duration")
        self.clock, self.deadline = clock, clock() + seconds
        self.writer = writer
        self.targets = TARGETS if targets is None else targets
        self.saved = {}
        self.events = {}
        self.stopped = False

    def stop(self):
        self.stopped = True

    def matching(self, url, method, status):
        if self.stopped or self.clock() >= self.deadline:
            raise ProbeError("capture_window_closed")
        return select_target(url, method, status, self.targets)

    def observe(self, url, method, status, request_cookie="", set_cookies=()):
        try:
            target, query = self.matching(url, method, status)
            data = extract_credential(target, query, request_cookie, set_cookies)
            self.writer(data)
            account = target["account"]
            self.saved[account] = self.saved.get(account, 0) + 1
            reason = "capture_saved_not_authentication_verified"
        except ProbeError as exc:
            reason = exc.reason
        except Exception:
            # Framework exceptions must never print a flow or credential URL.
            reason = "capture_store_failed"
        self.events[reason] = self.events.get(reason, 0) + 1
        return reason

    def summary(self):
        return {"status": "closed" if self.stopped or self.clock() >= self.deadline else "open",
                "saved_by_account": dict(self.saved), "events": dict(self.events),
                "authentication_verified": False, "automatic_renewal_verified": False}
