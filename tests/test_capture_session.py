"""Constructed system operations; only files/locks/pipes are real here."""

import copy
import os
import unittest
from unittest.mock import patch

from test_validation import LocalTest
from validation.capture_session import (APPLIED, TARGET_HOST, SessionWindow,
    lifecycle_lock, private_json, private_write, recover, setup, upstream_mode, validate_sources)
from validation.http import ProbeError


def baseline():
    proxy = {"Enabled": "Yes", "Server": "127.0.0.1", "Port": "7897", "Authenticated Proxy Enabled": "0"}
    return {"active_service": "Wi-Fi", "interface": "en0", "https_proxy": proxy,
            "http_proxy": dict(proxy), "pac": {"Enabled": "No", "URL": "(null)"},
            "autodiscovery": "Auto Proxy Discovery: Off", "bypass_domains": ["localhost", "*.local"],
            "review_reasons": []}


class FakeNative:
    def __init__(self):
        self.plan = {"baseline": baseline()}
        self.current = copy.deepcopy(self.plan["baseline"])
        self.trusted, self.broad_trust = False, False
        self.events = []

    def snapshot(self):
        return copy.deepcopy(self.current)

    def proxy(self):
        return dict(self.current["https_proxy"])

    def prepare_ca(self):
        self.events.append("prepare")
        return "FAKE_CERT_FINGERPRINT"

    def certificate_present(self, fingerprint):
        return self.trusted

    def trust(self):
        self.events.append("trust")
        self.trusted = True

    def verify(self, host):
        return self.trusted and (self.broad_trust or host == TARGET_HOST)

    def untrust(self, fingerprint):
        self.events.append("untrust")
        self.trusted = False

    def set_proxy(self, value):
        self.events.append("apply" if value == APPLIED else "restore")
        self.current["https_proxy"] = dict(value)


class LifecycleTests(unittest.TestCase):
    def test_upstream_preserves_existing_loopback_and_rejects_scope_expansion(self):
        self.assertEqual(upstream_mode(baseline()), "upstream:http://127.0.0.1:7897")
        for key, value in [("Server", "outside.example"), ("Port", "8899"), ("Authenticated Proxy Enabled", "1"), ("Enabled", "No")]:
            data = baseline()
            data["https_proxy"][key] = value
            with self.assertRaises(ProbeError):
                upstream_mode(data)
        data = baseline()
        data["bypass_domains"] = ["*.weixin.qq.com"]
        with self.assertRaisesRegex(ProbeError, "bypasses"):
            upstream_mode(data)

    def test_roundtrip_before_ready_and_restore_before_trust_removal(self):
        native, journal, saved = FakeNative(), {}, []
        save = lambda value: saved.append(copy.deepcopy(value))
        setup(native, journal, save, lambda: None, lambda: object())
        self.assertEqual(native.events, ["prepare", "trust", "apply", "restore", "apply"])
        self.assertTrue(journal["trust_scope_verified"] and journal["proxy_roundtrip_verified"])
        self.assertTrue(any(x.get("proxy_attempted") and x["status"] == "proxy_roundtrip_trial" for x in saved))
        result = recover(native, journal, save)
        self.assertTrue(result["verified"])
        self.assertEqual(native.events[-2:], ["restore", "untrust"])
        self.assertTrue(journal["capture_disabled"])
        self.assertEqual(native.current, native.plan["baseline"])

    def test_broad_certificate_trust_aborts_before_any_proxy_change(self):
        native, journal = FakeNative(), {}
        native.broad_trust = True
        with self.assertRaisesRegex(ProbeError, "hostname_trust_scope_failed"):
            setup(native, journal, lambda _: None, lambda: None, lambda: self.fail("proxy started"))
        result = recover(native, journal, lambda _: None)
        self.assertTrue(result["verified"])
        self.assertNotIn("apply", native.events)
        self.assertFalse(native.trusted)

    def test_existing_configuration_change_aborts_before_CA(self):
        native = FakeNative()
        native.current["http_proxy"]["Port"] = "7898"
        with self.assertRaisesRegex(ProbeError, "changed_since_preflight"):
            setup(native, {}, lambda _: None, lambda: None, lambda: None)
        self.assertEqual(native.events, [])

    def test_proxy_start_failure_still_removes_our_trust(self):
        native, journal = FakeNative(), {}
        def failed():
            raise ProbeError("session_proxy_start_failed")
        with self.assertRaises(ProbeError):
            setup(native, journal, lambda _: None, lambda: None, failed)
        self.assertTrue(recover(native, journal, lambda _: None)["verified"])
        self.assertFalse(native.trusted)

    def test_partial_proxy_mutation_is_in_journal_and_recovered(self):
        native, journal = FakeNative(), {}
        original = native.set_proxy
        def failed(value):
            original(value)
            if value == APPLIED:
                raise ProbeError("session_proxy_readback_failed")
        native.set_proxy = failed
        with self.assertRaises(ProbeError):
            setup(native, journal, lambda _: None, lambda: None, lambda: object())
        self.assertTrue(journal["proxy_attempted"])
        native.set_proxy = original
        self.assertTrue(recover(native, journal, lambda _: None)["verified"])

    def test_parent_cancel_after_trust_is_cleaned_without_proxy(self):
        native, journal = FakeNative(), {}
        def checkpoint():
            if native.trusted:
                raise ProbeError("session_parent_closed_or_cancelled")
        with self.assertRaises(ProbeError):
            setup(native, journal, lambda _: None, checkpoint, lambda: self.fail("proxy started"))
        self.assertTrue(recover(native, journal, lambda _: None)["verified"])

    def test_external_change_is_preserved_without_false_restoration_claim(self):
        native = FakeNative()
        native.current["https_proxy"]["Port"] = "9000"
        journal = {"proxy_attempted": True}
        result = recover(native, journal, lambda _: None)
        self.assertEqual(result["proxy"], "external_change_preserved")
        self.assertFalse(result["verified"])
        self.assertTrue(result["safe_to_stop_proxy"])
        self.assertEqual(native.events, [])

    def test_same_endpoint_modified_by_user_or_read_failure_keeps_listener(self):
        native = FakeNative()
        native.current["https_proxy"] = {**APPLIED, "Authenticated Proxy Enabled": "1"}
        self.assertFalse(recover(native, {"proxy_attempted": True}, lambda _: None)["safe_to_stop_proxy"])
        native.proxy = lambda: (_ for _ in ()).throw(RuntimeError("PRIVATE_PARAMETER"))
        result = recover(native, {"proxy_attempted": True}, lambda _: None)
        self.assertEqual(result["proxy"], "recovery_failed")
        self.assertNotIn("PRIVATE", str(result))
        self.assertFalse(result["safe_to_stop_proxy"])

    def test_failed_journal_write_cannot_prevent_native_cleanup(self):
        native = FakeNative()
        native.current["https_proxy"] = dict(APPLIED)
        native.trusted = True
        journal = {"proxy_attempted": True, "trust_attempted": True, "ca_fingerprint": "FAKE"}
        def failed(_):
            raise OSError("disk full")
        result = recover(native, journal, failed)
        self.assertTrue(result["verified"])
        self.assertTrue(journal["journal_write_failed"])
        self.assertEqual(native.events, ["restore", "untrust"])


class WindowTests(unittest.TestCase):
    def test_real_parent_pipe_EOF_and_both_deadlines(self):
        reader, writer = os.pipe()
        try:
            now, wall = [0], [0]
            window = SessionWindow(reader, 600, monotonic=lambda: now[0], wall=lambda: wall[0])
            window.check()
            now[0] = 600
            with self.assertRaisesRegex(ProbeError, "expired"):
                window.check()
            now[0] = 0
            wall[0] = 600
            with self.assertRaisesRegex(ProbeError, "expired"):
                window.check()
            wall[0] = 0
            os.close(writer)
            writer = None
            with self.assertRaisesRegex(ProbeError, "parent_closed"):
                window.check()
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)


class PrivateSessionTests(LocalTest):
    def test_lock_prevents_concurrent_recovery_and_private_state_is_atomic(self):
        with patch("validation.capture_session.SESSION", self.path):
            with lifecycle_lock():
                with self.assertRaisesRegex(ProbeError, "still_owns"):
                    with lifecycle_lock():
                        self.fail("concurrent recovery")
        path = self.path / "state.json"
        private_write(path, {"finished": False})
        self.assertEqual(private_json(path), {"finished": False})
        with patch("validation.capture_session.os.replace", side_effect=OSError("write interrupted")):
            with self.assertRaises(OSError):
                private_write(path, {"finished": True})
        self.assertFalse(private_json(path)["finished"])

    def test_private_reader_rejects_symlinks_and_non_regular_files(self):
        target = self.path / "target.json"
        private_write(target, {"fake": True})
        alias = self.path / "alias.json"
        alias.symlink_to(target)
        with self.assertRaisesRegex(ProbeError, "symlink"):
            private_json(alias)
        with self.assertRaisesRegex(ProbeError, "file_invalid"):
            private_json(self.path)


class PostCaptureTests(unittest.TestCase):
    def test_no_probe_until_restore_and_only_captured_account_uses_bounded_list(self):
        def forbidden(*args, **kwargs):
            self.fail("probe before recovery")
        self.assertEqual(validate_sources({"capture": {"saved_by_account": {"猫笔刀": 1}}}, forbidden), [])
        commands = []
        def invoke(command, **kwargs):
            from types import SimpleNamespace
            commands.append(command)
            self.assertEqual(kwargs["timeout"], 120)
            return SimpleNamespace(returncode=2, stdout='{"account":"猫笔刀","status":"list_observed_times_unverified"}')
        state = {"capture": {"saved_by_account": {"猫笔刀": 1}}, "recovery": {"verified": True}, "proxy_process_stopped": True}
        with patch("builtins.print"):
            result = validate_sources(state, invoke)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][-2:], ["--max-pages", "3"])
        self.assertIn("mp-discover", commands[0])
        self.assertNotIn("key", str(commands[0]))
        self.assertEqual(result[0]["status"], "list_observed_times_unverified")
