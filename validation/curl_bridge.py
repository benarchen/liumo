"""A bounded, task-only bridge to explicitly authorized native curl commands.

Secrets and raw responses use private FIFOs, never argv, regular config files,
logs or a network listener. This module does not start curl or change systems.
"""

import json
import os
import select
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs

from .common import ROOT, timestamp, write_json
from .credentials import check_private
from .capture_session import private_json
from .http import ProbeError, WechatHTTP, profile_cookie


class CurlBridge(WechatHTTP):
    def __init__(self, directory, seconds=600, request_timeout=40):
        super().__init__(transport="curl")
        self.directory = Path(directory)
        check_private(self.directory)
        self.deadline = time.monotonic() + seconds
        self.request_timeout = request_timeout
        self.requests = 0
        self.outcomes = []

    def publish(self, **data):
        write_json(self.directory / "status.json", {"at": timestamp(), **data})

    def read(self, url, headers=None, limit=10 * 1024 * 1024):
        return self._read(url, headers, limit, redirected=False)

    def _read(self, url, headers, limit, redirected):
        if self.requests >= 46 or time.monotonic() >= self.deadline:
            raise ProbeError("bridge_budget_exhausted")
        if type(limit) is not int or not 1 <= limit <= 25 * 1024 * 1024:
            raise ProbeError("invalid_response_limit")
        config = self.curl_config(url, headers or {})
        self.requests += 1
        directory = self.directory / str(self.requests)
        directory.mkdir(mode=0o700)
        config_fifo, response_fifo = directory / "config.fifo", directory / "response.fifo"
        header_fifo = directory / "headers.fifo"
        os.mkfifo(config_fifo, 0o600)
        os.mkfifo(response_fifo, 0o600)
        os.mkfifo(header_fifo, 0o600)
        until = min(self.deadline, time.monotonic() + self.request_timeout)
        stop = threading.Event()

        def produce():
            descriptor = None
            try:
                while not stop.is_set() and time.monotonic() < until:
                    try:
                        descriptor = os.open(config_fifo, os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
                        break
                    except OSError:
                        stop.wait(.05)
                if descriptor is None:
                    return
                remaining = memoryview(config)
                while remaining and not stop.is_set() and time.monotonic() < until:
                    if select.select([], [descriptor], [], .1)[1]:
                        try:
                            remaining = remaining[os.write(descriptor, remaining):]
                        except BlockingIOError:
                            continue
            except OSError:
                pass
            finally:
                if descriptor is not None:
                    os.close(descriptor)

        descriptor = os.open(response_fifo, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        header_descriptor = os.open(header_fifo, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        producer = threading.Thread(target=produce, daemon=True)
        producer.start()
        self.publish(status="awaiting_curl", request=self.requests, config_fifo=str(config_fifo),
                     response_fifo=str(response_fifo), header_fifo=str(header_fifo),
                     receipt=str(directory / "receipt.json"), limit=limit)
        data, response_headers = bytearray(), bytearray()
        try:
            while time.monotonic() < until:
                for ready in select.select([descriptor, header_descriptor], [], [], .1)[0]:
                    target, maximum = (data, limit) if ready == descriptor else (response_headers, 65536)
                    try:
                        part = os.read(ready, min(65536, maximum + 1 - len(target)))
                    except BlockingIOError:
                        continue
                    target.extend(part)
                    if len(target) > maximum:
                        raise ProbeError("response_size_limit")
                receipt = directory / "receipt.json"
                if receipt.exists():
                    # Darwin select need not signal another readable EOF after
                    # the last FIFO writer closes. A completed curl receipt is
                    # authoritative; drain the nonblocking FIFO explicitly.
                    for source, target, maximum in ((descriptor, data, limit),
                                                     (header_descriptor, response_headers, 65536)):
                        while True:
                            try:
                                part = os.read(source, min(65536, maximum + 1 - len(target)))
                            except BlockingIOError:
                                break
                            if not part:
                                break
                            target.extend(part)
                            if len(target) > maximum:
                                raise ProbeError("response_size_limit")
                    try:
                        result = private_json(receipt)
                    except (ProbeError, ValueError, OSError):
                        raise ProbeError("bridge_receipt_invalid") from None
                    code, status = result.get("exit_code"), result.get("http_status")
                    if type(code) is not int or type(status) is not int:
                        raise ProbeError("bridge_receipt_invalid")
                    self.outcomes.append({"request": self.requests, "exit_code": code, "http_status": status,
                                          "redirect": redirect_summary(url, bytes(response_headers))})
                    if code:
                        raise ProbeError({63: "response_size_limit", 60: "tls_verification_failed"}.get(
                            code, "curl_transport_failed"), code)
                    if status != 200:
                        if status in {301, 302, 303, 307, 308} and not redirected:
                            target = canonical_sample_redirect(url, bytes(response_headers))
                            if target:
                                self.outcomes[-1]["canonical_redirect_followed"] = True
                                self.outcomes[-1]["redirect"]["location_followed"] = True
                                return self._read(target, headers, limit, redirected=True)
                        raise ProbeError("redirect_blocked" if 300 <= status < 400 else "http_rejected", status)
                    parts = urlsplit(url)
                    if parts.path == "/mp/profile_ext" and parse_qs(parts.query).get("action") == ["home"]:
                        self._profile_cookie = profile_cookie(bytes(response_headers))
                    return bytes(data)
            raise ProbeError("bridge_request_timed_out")
        finally:
            stop.set()
            os.close(descriptor)
            os.close(header_descriptor)
            producer.join(timeout=.5)
            self.publish(status="processing", request=self.requests)

def redirect_summary(url, headers):
    """Only classify known routes; never persist raw Location, queries or cookies."""
    location = next((line.split(b":", 1)[1].strip() for line in headers.split(b"\r\n")
                     if line.lower().startswith(b"location:")), None)
    if location is None:
        return None
    try:
        destination = urlsplit(urljoin(url, location.decode("latin-1")))
        known = {"/s", "/mp/wappoc_appmsgcaptcha", "/mp/verifycode", "/mp/profile_ext",
                 "/cgi-bin/readtemplate", "/mp/redirect", "/mp/auth"}
        return {"same_https_origin": destination.scheme == "https" and destination.netloc == "mp.weixin.qq.com",
                "host_class": "mp.weixin.qq.com" if destination.hostname == "mp.weixin.qq.com" else "other",
                "route": destination.path if destination.path in known else
                         ("/s/<article>" if destination.path.startswith("/s/") else "other"),
                "query_present": bool(destination.query), "location_followed": False}
    except (ValueError, UnicodeError):
        return {"route": "unrecognized", "location_followed": False}


def canonical_sample_redirect(url, headers):
    """Raw result stays in memory; only one exact known article may be followed."""
    from .common import SAMPLES
    from .capture import TARGETS
    expected = next((target | {"biz": biz} for biz, target in TARGETS.items()
                     if SAMPLES.get("maobidao" if target["account"] == "猫笔刀" else "stormzhang") == url), None)
    if expected is None:
        return None
    location = next((line.split(b":", 1)[1].strip() for line in headers.split(b"\r\n")
                     if line.lower().startswith(b"location:")), None)
    if location is None:
        return None
    try:
        target = urljoin(url, location.decode("latin-1"))
        if target == url:
            return None
        parts = urlsplit(target)
        if (parts.scheme != "https" or parts.netloc != "mp.weixin.qq.com" or parts.fragment
                or len(target) > 16384):
            return None
        query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=60)
        keys = {"__biz": "biz", "mid": "mid", "idx": "idx"}
        has_identity = any(key in query for key in keys)
        identity_matches = all(query.get(key) == [expected[value]] for key, value in keys.items())
        if has_identity and not identity_matches:
            return None
        same_short_path = parts.path == urlsplit(url).path
        canonical_long_path = parts.path == "/s" and identity_matches and len(query.get("sn", [])) == 1 and query["sn"][0]
        return target if same_short_path or canonical_long_path else None
    except (ValueError, UnicodeError):
        return None


def run_bridge(source=False, context=False):
    """Only the two sample HTTP checks; system and browser operations excluded."""
    from .sample_check import check_samples
    os.umask(0o077)
    directory = ROOT / ".tmp/wechat-session-validation/native-curl" / uuid.uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    bridge = CurlBridge(directory)
    print(json.dumps({"status_file": str(directory / "status.json"), "status": "bridge_started"}), flush=True)
    try:
        if context:
            from .profile_context import check_profile_contexts
            result = check_profile_contexts(bridge)
        elif source:
            from .mp_source import diagnose_profile
            from .common import new_run
            output = new_run("reference-source-pair")
            rows = [diagnose_profile(account, transport="native_curl_bridge", client=bridge)
                    for account in ("猫笔刀", "stormzhang")]
            result = {"output": str(output), "status": "not_verified", "results": rows,
                      "system_changes_made": False, "formal_subscription_enabled": False}
            write_json(output / "source-pair.json", result)
        else:
            result = check_samples(transport="native_curl_bridge", client=bridge)
    except Exception:
        result = {"status": "failed", "reason": "bridge_sample_execution_failed"}
    bridge.publish(status="finished", requests=bridge.requests, outcomes=bridge.outcomes, result=result)
    if result.get("output"):
        write_json(Path(result["output"]) / "transport.json", {"at": timestamp(), "requests": bridge.outcomes,
                   "no_raw_response_or_header_saved": True, "no_system_changes": True})
    return result
