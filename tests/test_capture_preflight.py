"""Constructed macOS query output; never calls system setters."""

import json
import stat
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_validation import LocalTest
from validation.capture_preflight import (NETWORKSETUP, active_service, collect_baseline,
                                          parse_proxy, query, save_baseline)
from validation.http import ProbeError

SERVICES = "An asterisk (*) denotes that a network service is disabled.\nWi-Fi\n*Disabled\n"
ORDER = "(1) Wi-Fi\n(Hardware Port: Wi-Fi, Device: en0)\n"
PROXY = "Enabled: No\nServer: \nPort: 0\nAuthenticated Proxy Enabled: 0\n"


class BaselineTests(unittest.TestCase):
    def runner(self, changes=None):
        output = {"-listallnetworkservices": SERVICES, "-listnetworkserviceorder": ORDER,
                  "-getsecurewebproxy": PROXY, "-getwebproxy": PROXY,
                  "-getautoproxyurl": "URL: (null)\nEnabled: No\n",
                  "-getproxyautodiscovery": "Auto Proxy Discovery: Off\n",
                  "-getproxybypassdomains": "localhost\n*.local\n", "-n": "interface: en0\n"}
        output.update(changes or {})
        def run(command):
            self.assertIn(command[0], [NETWORKSETUP, "/sbin/route"])
            self.assertFalse(any(str(x).startswith("-set") for x in command))
            return output[command[1]]
        return run

    def test_authorization_error_is_failure_even_with_zero_exit(self):
        with patch("validation.capture_preflight.subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout="AuthorizationCreate() failed: -60008\nPRIVATE", stderr="")):
            with self.assertRaisesRegex(ProbeError, "authorization_unavailable") as error:
                query([NETWORKSETUP, "-listallnetworkservices"])
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_query_timeout_or_stderr_has_no_original_error_text(self):
        with patch("validation.capture_preflight.subprocess.run", side_effect=subprocess.TimeoutExpired("PRIVATE", 10)):
            with self.assertRaisesRegex(ProbeError, "command_unavailable"):
                query([NETWORKSETUP, "-listallnetworkservices"])
        with patch("validation.capture_preflight.subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=PROXY, stderr="PRIVATE")):
            with self.assertRaisesRegex(ProbeError, "query_failed"):
                query([NETWORKSETUP, "-getsecurewebproxy", "Wi-Fi"])

    def test_proxy_fields_must_be_complete_and_unambiguous(self):
        self.assertEqual(parse_proxy(PROXY)["Port"], "0")
        for value in [PROXY.replace("Port: 0\n", ""), PROXY + "Port: 1\n",
                      PROXY.replace("Enabled: No", "Enabled: Unknown"), PROXY + "New: x\n"]:
            with self.assertRaises(ProbeError):
                parse_proxy(value)

    def test_only_unambiguous_active_service_is_accepted(self):
        self.assertEqual(active_service(SERVICES, ORDER, "interface: en0\n"), ("Wi-Fi", "en0"))
        for order, route in [(ORDER, "interface: utun9\n"),
                             (ORDER + ORDER, "interface: en0\n"),
                             ("(1) Wi-Fi\n(*) Disabled\n(Hardware Port: Wi-Fi, Device: en0)\n", "interface: en0\n")]:
            with self.assertRaises(ProbeError):
                active_service(SERVICES, order, route)

    def test_complete_read_only_baseline_is_not_recovery_validation(self):
        result = collect_baseline(run=self.runner(), port_check=lambda: None)
        self.assertFalse(result["recovery_verified"])
        self.assertFalse(result["system_changes_made"])
        self.assertEqual(result["review_reasons"], [])
        self.assertEqual(result["https_proxy"], result["http_proxy"])

    def test_pac_and_authenticated_proxy_are_visible_conflicts(self):
        result = collect_baseline(run=self.runner({
            "-getsecurewebproxy": PROXY.replace("Proxy Enabled: 0", "Proxy Enabled: 1"),
            "-getautoproxyurl": "URL: https://private.example/pac?secret=VALUE\nEnabled: Yes\n"}),
            port_check=lambda: None)
        self.assertEqual(len(result["review_reasons"]), 2)
        self.assertFalse(result["recovery_verified"])

    def test_loopback_unavailable_does_not_become_ready(self):
        def unavailable():
            raise ProbeError("preflight_loopback_unavailable")
        with self.assertRaisesRegex(ProbeError, "loopback_unavailable"):
            collect_baseline(run=self.runner(), port_check=unavailable)


class PrivateBaselineTests(LocalTest):
    def test_baseline_private_mode_no_overwrite_and_no_symlink(self):
        data = {"at": "2026-10-17T10:00:00+08:00", "pac": "PRIVATE_VALUE"}
        destination = save_baseline(data, self.path)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(destination.parent.stat().st_mode), 0o700)
        self.assertEqual(json.loads(destination.read_text()), data)
        with self.assertRaises(FileExistsError):
            save_baseline(data, self.path)
        other = self.path / "other"
        other.mkdir()
        (other / ".auth").symlink_to(destination.parent)
        with self.assertRaisesRegex(ProbeError, "symlink"):
            save_baseline(data, other)
