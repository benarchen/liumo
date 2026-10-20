"""Constructed header events only; no installed proxy, TLS trust or OS changes."""

import copy
import fcntl
import json
import stat
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from test_validation import LocalTest
from validation.capture import CaptureSession, extract_credential, select_target
from validation.common import ROOT
from validation.capture_plan import ALLOW_HOST, PORT, check_proxy_options, recovery_decision, review_plan
from validation.credentials import read_private_credentials, save_captured_credentials
from validation.http import ProbeError
from validation.mitm_addon import WechatCaptureAddon


TARGET = {"account": "猫笔刀", "mid": "100", "idx": "1"}
TARGET_MAP = {"FIXTURE_BIZ": TARGET}


def query(**changes):
    return {"__biz": "FIXTURE_BIZ", "mid": "100", "idx": "1", "uin": "SENSITIVE_UIN",
            "key": "SENSITIVE_KEY", "pass_ticket": "PASS_+/=", **changes}


def url(**changes):
    return "https://mp.weixin.qq.com/s?" + urlencode(query(**changes))


def data(at="2026-10-17T10:00:00+08:00"):
    _, raw = select_target(url(), "GET", 200, TARGET_MAP)
    return extract_credential(TARGET, raw, "unrelated=DO_NOT_KEEP; wap_sid2=sid",
                              ["appmsg_token=TOKEN; Path=/; Secure; HttpOnly"], at)


class MatchingTests(unittest.TestCase):
    def test_exact_article_method_tls_and_account_scope(self):
        self.assertEqual(select_target(url(), "GET", 200, TARGET_MAP)[0], TARGET)
        for address, method, code in [(url(__biz="OTHER"), "GET", 200), (url(mid="101"), "GET", 200),
                                      (url(idx="2"), "GET", 200), (url(), "POST", 200),
                                      (url(), "GET", 302), (url().replace("https:", "http:"), "GET", 200),
                                      (url().replace("mp.weixin.qq.com", "mp.weixin.qq.com.evil.test"), "GET", 200)]:
            with self.subTest(address=address[:40], method=method, code=code):
                with self.assertRaisesRegex(ProbeError, "not_matching"):
                    select_target(address, method, code, TARGET_MAP)

    def test_duplicate_scope_and_credential_fields_rejected(self):
        with self.assertRaises(ProbeError):
            select_target(url() + "&__biz=OTHER", "GET", 200, TARGET_MAP)
        _, raw = select_target(url() + "&key=SECOND", "GET", 200, TARGET_MAP)
        with self.assertRaisesRegex(ProbeError, "ambiguous"):
            extract_credential(TARGET, raw, "appmsg_token=TOKEN", [])

    def test_response_cookie_wins_and_unrelated_cookie_is_discarded(self):
        _, raw = select_target(url(), "GET", 200, TARGET_MAP)
        result = extract_credential(TARGET, raw, "appmsg_token=OLD; unrelated=DO_NOT_KEEP",
                                    ["appmsg_token=NEW; HttpOnly", "wap_sid2=sid; Secure"])
        self.assertEqual(result["appmsg_token"], "NEW")
        self.assertEqual(result["pass_ticket"], "PASS_+/=")
        self.assertIn("wap_sid2=sid", result["cookie"])
        self.assertNotIn("DO_NOT_KEEP", json.dumps(result))

    def test_missing_fields_or_header_injection_never_produce_credentials(self):
        _, raw = select_target(url(), "GET", 200, TARGET_MAP)
        with self.assertRaisesRegex(ProbeError, "missing_or_invalid"):
            extract_credential(TARGET, raw, "", [])
        with self.assertRaisesRegex(ProbeError, "cookie_invalid"):
            extract_credential(TARGET, raw, "appmsg_token=A\nprivate-key", [])

    def test_closed_window_stops_and_failure_summary_does_not_leak(self):
        clock = [10]
        captured = []
        session = CaptureSession(seconds=2, targets=TARGET_MAP, writer=captured.append, clock=lambda: clock[0])
        session.observe(url(), "GET", 200, "appmsg_token=TOKEN")
        clock[0] = 12
        self.assertEqual(session.observe(url(), "GET", 200, "appmsg_token=TOKEN"), "capture_window_closed")
        self.assertEqual(len(captured), 1)
        self.assertEqual(session.summary()["status"], "closed")
        summary = json.dumps(session.summary())
        for value in ["SENSITIVE", "TOKEN", "PASS_", "http"]:
            self.assertNotIn(value, summary)
        self.assertFalse(session.summary()["authentication_verified"])

    def test_store_exception_cannot_print_url_or_secret(self):
        def broken(_):
            raise RuntimeError(url())
        session = CaptureSession(targets=TARGET_MAP, writer=broken)
        self.assertEqual(session.observe(url(), "GET", 200, "appmsg_token=TOKEN"), "capture_store_failed")
        self.assertNotIn("SENSITIVE", json.dumps(session.summary()))

    def test_unmatched_flow_never_calls_writer(self):
        session = CaptureSession(targets=TARGET_MAP, writer=lambda _: self.fail("out-of-scope write"))
        with patch("validation.capture.parse_qs", side_effect=AssertionError("out-of-scope credential decode")):
            self.assertEqual(session.observe(url(__biz="OTHER"), "GET", 200), "capture_not_matching")


class PrivateWriterTests(LocalTest):
    def test_atomic_owned_rotation_permissions_and_reader_compatibility(self):
        save_captured_credentials(data(), self.path)
        path = self.path / ".auth/wechat/maobidao.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        newer = {**data("2026-10-17T10:01:00+08:00"), "key": "NEW_KEY"}
        save_captured_credentials(newer, self.path)
        self.assertEqual(read_private_credentials(path, "猫笔刀")["key"], "NEW_KEY")
        self.assertEqual(list(path.parent.glob(".capture-*")), [])
        with self.assertRaisesRegex(ProbeError, "out_of_order"):
            save_captured_credentials(data(), self.path)
        self.assertEqual(read_private_credentials(path, "猫笔刀")["key"], "NEW_KEY")

    def test_existing_manual_input_not_overwritten(self):
        save_captured_credentials(data(), self.path)
        path = self.path / ".auth/wechat/maobidao.json"
        manual = json.loads(path.read_text())
        manual.pop("managed_by")
        path.write_text(json.dumps(manual))
        before = path.read_bytes()
        with self.assertRaisesRegex(ProbeError, "not_managed"):
            save_captured_credentials(data(), self.path)
        self.assertEqual(path.read_bytes(), before)

    def test_directory_symlink_and_wide_permissions_rejected(self):
        foreign = self.path / "foreign"
        foreign.mkdir()
        (self.path / ".auth").symlink_to(foreign)
        with self.assertRaisesRegex(ProbeError, "symlink"):
            save_captured_credentials(data(), self.path)
        self.assertEqual(list(foreign.iterdir()), [])

    def test_busy_writer_never_truncates_current_file(self):
        save_captured_credentials(data(), self.path)
        path = self.path / ".auth/wechat/maobidao.json"
        before = path.read_bytes()
        with (path.parent / ".capture.lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ProbeError, "store_busy"):
                save_captured_credentials(data("2026-10-17T10:01:00+08:00"), self.path)
        self.assertEqual(path.read_bytes(), before)

    def test_interrupted_write_keeps_old_file(self):
        save_captured_credentials(data(), self.path)
        path = self.path / ".auth/wechat/maobidao.json"
        before = path.read_bytes()
        with patch("validation.credentials.os.replace", side_effect=OSError("SENSITIVE_KEY")):
            with self.assertRaises(OSError):
                save_captured_credentials(data("2026-10-17T10:01:00+08:00"), self.path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob(".capture-*")), [])


class AdapterTests(unittest.TestCase):
    def test_standalone_loader_has_project_imports_without_starting_capture(self):
        result = subprocess.run([sys.executable, "-I", str(ROOT / "validation/mitm_addon.py")],
                                cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"")

    def test_configuration_change_stops_an_existing_session(self):
        options = ReviewPlanTests().options()
        options.liumo_capture, options.liumo_capture_seconds = True, 600
        addon = WechatCaptureAddon()
        with patch.dict(sys.modules, {"mitmproxy": SimpleNamespace(ctx=SimpleNamespace(options=options))}):
            addon.configure(set())
            options.flow_detail = 1
            with self.assertRaises(ProbeError):
                addon.configure({"flow_detail"})
        self.assertTrue(addon.session.stopped)

    def flow(self, address=None):
        # Access to a response body or an unexpected header fails immediately.
        class Headers:
            def get(self, key, default):
                if key != "cookie":
                    raise AssertionError("unneeded request header")
                return "appmsg_token=TOKEN"

            def get_all(self, key):
                if key != "set-cookie":
                    raise AssertionError("unneeded response header")
                return []
        return SimpleNamespace(request=SimpleNamespace(url=address or url(), method="GET", headers=Headers(), stream=False),
                               response=SimpleNamespace(status_code=200, headers=Headers(), stream=False))

    def test_adapter_off_by_default_does_not_touch_flow(self):
        addon = WechatCaptureAddon()
        flow = self.flow()
        addon.requestheaders(flow)
        addon.responseheaders(flow)
        self.assertFalse(flow.request.stream)
        self.assertFalse(flow.response.stream)

    def test_target_header_events_only_and_stop(self):
        addon = WechatCaptureAddon()
        collected = []
        addon.session = CaptureSession(targets=TARGET_MAP, writer=collected.append)
        flow = self.flow()
        addon.requestheaders(flow)
        addon.responseheaders(flow)
        self.assertEqual(len(collected), 1)
        self.assertTrue(flow.request.stream and flow.response.stream)
        addon.done()
        addon.responseheaders(flow)
        self.assertEqual(len(collected), 1)


class ReviewPlanTests(unittest.TestCase):
    def options(self):
        return SimpleNamespace(listen_host="127.0.0.1", listen_port=PORT, mode=["regular"],
                               allow_hosts=[ALLOW_HOST], ignore_hosts=[], ssl_insecure=False,
                               flow_detail=0, termlog_verbosity="error", show_ignored_hosts=False,
                               store_streamed_bodies=False, command_history=False, strip_ech=False,
                               confdir=str(ROOT / ".auth/wechat-capture/mitmproxy"), save_stream_file=None, hardump="")

    def test_review_plan_does_not_execute_commands_or_claim_approval(self):
        result = review_plan()
        self.assertEqual(result["status"], "prepared_not_running")
        self.assertTrue(result["requires_explicit_authorization"])
        self.assertFalse(result["policy"]["enable_http_proxy"])
        self.assertEqual(len(result["targets"]), 2)

    def test_unsafe_configuration_or_flow_dump_rejected(self):
        options = self.options()
        check_proxy_options(options)
        for key, value in [("listen_host", "0.0.0.0"), ("ssl_insecure", True),
                           ("flow_detail", 1), ("allow_hosts", []), ("save_stream_file", "dump")]:
            changed = copy.copy(options)
            setattr(changed, key, value)
            with self.assertRaises(ProbeError):
                check_proxy_options(changed)

    def test_concurrent_proxy_change_blocks_blind_restore(self):
        before = {"enabled": False, "server": "", "port": 0}
        applied = {"enabled": True, "server": "127.0.0.1", "port": PORT}
        external = {"enabled": True, "server": "user-proxy", "port": 9000}
        self.assertTrue(recovery_decision(before, applied, applied)["restore"])
        self.assertFalse(recovery_decision(before, applied, before)["restore"])
        self.assertEqual(recovery_decision(before, applied, external)["status"], "conflict_requires_review")
