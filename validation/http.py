"""Small, direct HTTPS transport. No environment proxies or redirects."""

import json
import ssl
import subprocess
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

# Protocol compatibility value from the researched Mac article request format;
# this header provides no authentication and is not evidence of a live session.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 "
              "Safari/537.36 MicroMessenger/6.8.0(0x16080000) NetType/WIFI "
              "MiniProgramEnv/Mac MacWechat/WECHAT/WeChatBrowser XWEB/1191")
LIST_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 WAE/1.0")


class ProbeError(Exception):
    def __init__(self, reason, code=None):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def allowed_target(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return (parts.scheme == "https" and not parts.username and not parts.password
                and parts.port in (None, 443) and not parts.fragment
                and (host == "mp.weixin.qq.com" or host.endswith((".qpic.cn", ".qlogo.cn"))))
    except ValueError:
        return False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WechatHTTP:
    def __init__(self, transport="python"):
        if transport not in {"python", "curl"}:
            raise ValueError("invalid_transport")
        self.transport = transport
        self._profile_cookie = None
        self.opener = None
        if transport == "python":
            # Python 3.14's default client policy, without its optional
            # SSLKEYLOGFILE environment hook: credentials must not be keylogged.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
            context.load_default_certs()
            self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
        self.last_api_request = None

    def read(self, url, headers=None, limit=10 * 1024 * 1024):
        if not allowed_target(url):
            raise ProbeError("target_not_allowed")
        request_headers = {"User-Agent": USER_AGENT, "Referer": "https://mp.weixin.qq.com/"}
        request_headers.update(headers or {})
        # Authentication is never attached to an image/CDN request.
        if urlsplit(url).hostname != "mp.weixin.qq.com" and any(
                key.lower() in {"cookie", "authorization"} for key in request_headers):
            raise ProbeError("credential_target_not_allowed")
        if self.transport == "curl":
            return self._curl_read(url, request_headers, limit)
        try:
            with self.opener.open(Request(url, headers=request_headers), timeout=20) as response:
                if response.status != 200:
                    raise ProbeError("http_rejected", response.status)
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ProbeError("response_size_limit")
                parts = urlsplit(url)
                if parts.hostname == "mp.weixin.qq.com" and parts.path == "/mp/profile_ext" and parse_qs(parts.query).get("action") == ["home"]:
                    fields = response.headers.get_all("Set-Cookie", [])
                    self._profile_cookie = profile_cookie(b"\r\n".join(
                        b"Set-Cookie: " + value.encode("latin-1") for value in fields))
                return data
        except HTTPError as exc:
            reason = "redirect_blocked" if 300 <= exc.code < 400 else "http_rejected"
            raise ProbeError(reason, exc.code) from None
        except (URLError, OSError, TimeoutError):
            raise ProbeError("transport_failed") from None

    def take_profile_cookie(self):
        cookie, self._profile_cookie = self._profile_cookie, None
        return cookie

    @staticmethod
    def curl_config(url, headers):
        """Private in-memory configuration; never write or log its return value."""
        if not allowed_target(url):
            raise ProbeError("target_not_allowed")
        if urlsplit(url).hostname != "mp.weixin.qq.com" and any(
                key.lower() in {"cookie", "authorization"} for key in headers):
            raise ProbeError("credential_target_not_allowed")
        headers = {"User-Agent": USER_AGENT, "Referer": "https://mp.weixin.qq.com/", **headers}
        def quoted(value):
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ProbeError("invalid_request_headers")
            return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

        config = "url = " + quoted(url) + "\n"
        for key, value in headers.items():
            if (not isinstance(key, str) or not key.isascii() or not key.replace("-", "").isalnum()
                    or not isinstance(value, str)):
                raise ProbeError("invalid_request_headers")
            config += "header = " + quoted(key + ": " + value) + "\n"
        return config.encode()

    @staticmethod
    def _curl_read(url, headers, limit):
        """Explicit native HTTPS transport; secrets go only through stdin.

        curl >= 8.4 bounds unknown-length transfers with --max-filesize. The
        current Mac's system curl is 8.7.1. No config file, redirects or retry.
        """
        if type(limit) is not int or not 1 <= limit <= 25 * 1024 * 1024:
            raise ProbeError("invalid_response_limit")
        config = WechatHTTP.curl_config(url, headers)
        command = ["/usr/bin/curl", "--disable", "--silent", "--globoff", "--no-netrc",
                   "--proxy", "", "--noproxy", "*", "--proto", "=https",
                   "--no-location", "--no-insecure", "--connect-timeout", "10", "--max-time", "20",
                   "--max-filesize", str(limit), "--write-out", "\n%{http_code}", "--config", "-"]
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in {"SSLKEYLOGFILE", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR",
                                               "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
        try:
            response = subprocess.run(command, input=config, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, timeout=25, env=environment, close_fds=True)
        except (OSError, subprocess.TimeoutExpired):
            raise ProbeError("curl_transport_failed") from None
        if response.returncode:
            reason = {63: "response_size_limit", 60: "tls_verification_failed"}.get(
                response.returncode, "curl_transport_failed")
            raise ProbeError(reason, response.returncode)
        data, separator, status = response.stdout.rpartition(b"\n")
        if not separator or len(status) != 3 or not status.isdigit():
            raise ProbeError("curl_status_missing")
        code = int(status)
        if code != 200:
            raise ProbeError("redirect_blocked" if 300 <= code < 400 else "http_rejected", code)
        if len(data) > limit:
            raise ProbeError("response_size_limit")
        return data

    @staticmethod
    def api_request(action, fields, credential):
        allowed_fields = {
            "list": {"offset", "count"},
            "comments": {"comment_id", "appmsgid", "idx", "buffer", "offset", "comment_scene", "limit"},
            "replies": {"comment_id", "appmsgid", "idx", "content_id", "max_reply_id", "buffer", "limit"},
        }
        if action not in allowed_fields or not set(fields) <= allowed_fields[action]:
            raise ProbeError("invalid_request_fields")
        if any(type(value) not in (str, int) or len(str(value)) > 8192 for value in fields.values()):
            raise ProbeError("invalid_request_fields")
        if action == "list":
            path = "/mp/profile_ext"
            params = {"action": "getmsg", "is_ok": "1", "scene": "124", "f": "json",
                      "__biz": credential["biz"], "uin": credential["uin"],
                      "key": credential["key"], "pass_ticket": credential["pass_ticket"], **fields}
        elif action in {"comments", "replies"}:
            path = "/mp/appmsg_comment"
            params = {"action": "getcomment" if action == "comments" else "getcommentreply",
                      "__biz": credential["biz"], "uin": credential["uin"],
                      "key": credential["key"], "pass_ticket": credential["pass_ticket"],
                      "appmsg_token": credential["appmsg_token"], "scene": "0", "x5": "0",
                      "wxtoken": "777", "devicetype": "UnifiedPCMac", "f": "json", **fields}
        else:
            raise ProbeError("unknown_action")
        headers = {"Accept": "application/json"}
        if action == "list":
            # Fixed reference's reader-credential list path: query credentials,
            # explicit server headers, no injected article-reading Cookie.
            headers.update({"User-Agent": LIST_USER_AGENT, "Origin": "https://mp.weixin.qq.com",
                            "Accept-Encoding": "identity", "Accept": "*/*"})
        elif credential.get("cookie"):
            headers["Cookie"] = credential["cookie"]
        return "https://mp.weixin.qq.com" + path + "?" + urlencode(params), headers

    def api(self, action, fields, credential):
        url, headers = self.api_request(action, fields, credential)
        if self.last_api_request is not None:
            time.sleep(max(0, 2 - (time.monotonic() - self.last_api_request)))
        self.last_api_request = time.monotonic()
        data = self.read(url, headers)
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError):
            raise ProbeError("response_not_json") from None
        if not isinstance(payload, dict):
            raise ProbeError("response_shape_changed")
        return payload


def business_ok(payload):
    if not isinstance(payload, dict):
        raise ProbeError("response_shape_changed")
    response = payload.get("base_resp")
    code = response.get("ret") if isinstance(response, dict) else payload.get("ret")
    if type(code) is not int:
        raise ProbeError("business_status_missing")
    if code:
        raise ProbeError("business_rejected", code)


def count(value):
    if type(value) is not int or not 0 <= value <= 100000:
        raise ProbeError("response_shape_changed")
    return value


def profile_cookie(headers):
    """Select one normal homepage cookie in memory; never log the headers."""
    from http.cookies import SimpleCookie, CookieError
    for line in headers.split(b"\r\n"):
        if not line.lower().startswith(b"set-cookie:"):
            continue
        try:
            parsed = SimpleCookie()
            parsed.load(line.split(b":", 1)[1].strip().decode("latin-1"))
            if "poc_sid" in parsed:
                value = parsed["poc_sid"].value
                if value and len(value) <= 4096 and not any(ord(c) < 32 for c in value):
                    return value
        except (CookieError, UnicodeError):
            continue
    return None
