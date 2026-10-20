"""Offline controls: no system trust, socket listeners, accounts or WeChat."""

import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_validation import LocalTest
from validation.certificate_scope import assess, cases, classify_native, native_verify
from validation.common import ROOT


class AssessmentTests(unittest.TestCase):
    def rows(self):
        rows = []
        for profile in ("unconstrained", "exact_dns_no_ip"):
            for case in cases():
                good = case["valid_control"] if profile == "unconstrained" else case["in_scope"]
                rows.append({"validator": "fixture", "profile": profile, "case": case["id"],
                             "outcome": "accepted" if good else "rejected"})
        return rows

    def test_missing_duplicate_and_unknown_matrix_cannot_pass(self):
        rows = self.rows()
        self.assertEqual(assess(rows, "fixture", "exact_dns_no_ip")["status"], "passed_offline_matrix")
        for bad in (rows[:-1], rows + [rows[-1]]):
            self.assertEqual(assess(bad, "fixture", "exact_dns_no_ip")["status"], "not_verified")
        rows[-1]["outcome"] = "not_verified"
        self.assertEqual(assess(rows, "fixture", "exact_dns_no_ip")["status"], "not_verified")

    def test_rejected_controls_and_positive_target_do_not_imply_protection(self):
        rows = self.rows()
        self.assertEqual(assess(rows + [rows[0]], "fixture", "exact_dns_no_ip")["reason"], "baseline_control_failed")
        rows[0]["outcome"] = "rejected"
        self.assertEqual(assess(rows, "fixture", "exact_dns_no_ip")["reason"], "baseline_control_failed")
        rows = self.rows()
        for row in rows:
            if row["profile"] == "exact_dns_no_ip" and row["case"] == "target":
                row["outcome"] = "rejected"
        self.assertEqual(assess(rows, "fixture", "exact_dns_no_ip")["unexpected_cases"], ["target"])
        rows = self.rows()
        for row in rows:
            if row["profile"] == "exact_dns_no_ip" and row["case"] == "mixed_other":
                row["outcome"] = "accepted"
        self.assertEqual(assess(rows, "fixture", "exact_dns_no_ip")["unexpected_cases"], ["mixed_other"])


class NativeTests(unittest.TestCase):
    def test_explicit_files_disable_network_and_keychain_search(self):
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout=b"TrustResultValue = 4;", stderr=b""))
        self.assertEqual(native_verify(Path("root.pem"), Path("leaf.pem"), "mp.weixin.qq.com", run)["outcome"], "accepted")
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/security", "verify-cert", "-v"])
        self.assertNotIn("-q", command)
        self.assertIn("-N", command)
        self.assertIn("-L", command)
        self.assertEqual(command[command.index("-R") + 1], "offline")
        self.assertEqual(command[command.index("-r") + 1], "root.pem")
        self.assertNotIn("add-trusted-cert", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 8)

    def test_CT_unknown_and_timeout_are_not_scope_rejections_and_do_not_leak(self):
        for stderr, reason in ((b"PRIVATE signed certificate timestamps", "native_CT_diagnostic_only"),
                               (b"PRIVATE AuthorizationCreate()", "native_authorization_unavailable"),
                               (b"PRIVATE other failure", "native_nonzero_exit_unclassified")):
            run = Mock(return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=stderr))
            result = native_verify(Path("root"), Path("leaf"), "mp.weixin.qq.com", run)
            self.assertEqual(result["outcome"], "not_verified")
            self.assertEqual(result["reason"], reason)
            self.assertNotIn("PRIVATE", json.dumps(result))
        run = Mock(side_effect=subprocess.TimeoutExpired(["PRIVATE"], 8))
        self.assertEqual(native_verify(Path("root"), Path("leaf"), "mp.weixin.qq.com", run)["outcome"], "not_verified")

    def test_internal_error_precedes_CT_text_and_no_error_text_is_not_success(self):
        response = SimpleNamespace(returncode=1,
            stdout=b"PRIVATE signed certificate timestamps TrustResultValue = 0;",
            stderr=b'Cert Verify Result: No error. Error Domain=NSOSStatusErrorDomain Code=-26276 "PRIVATE"')
        result = classify_native(response)
        self.assertEqual(result["reason"], "native_security_framework_error")
        self.assertEqual(result["OSStatus_codes"], [-26276])
        self.assertEqual(result["trust_result"], 0)
        self.assertTrue(result["CT_diagnostic_present"])
        self.assertEqual(result["outcome"], "not_verified")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_real_decisions_and_conflicts_do_not_turn_tool_failures_into_passes(self):
        for trust in (1, 4):
            result = classify_native(SimpleNamespace(returncode=0,
                stdout=f"TrustResultValue = {trust}; signed certificate timestamps".encode(), stderr=b""))
            self.assertEqual(result["outcome"], "accepted")
            self.assertTrue(result["CT_diagnostic_present"])
        for trust in (3, 5, 6):
            self.assertEqual(classify_native(SimpleNamespace(returncode=1,
                stdout=f"TrustResultValue = {trust};".encode(), stderr=b""))["outcome"], "rejected")
        for content in (b"TrustResultValue = 0;", b"TrustResultValue = 7;", b"TrustResultValue = 8;",
                        b"TrustResultValue = 1; TrustResultValue = 5;", b"unrecognized PRIVATE"):
            result = classify_native(SimpleNamespace(returncode=1, stdout=content, stderr=b""))
            self.assertEqual(result["outcome"], "not_verified")
            self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(classify_native(SimpleNamespace(returncode=0, stdout=b"", stderr=b""))["outcome"], "not_verified")
        contradictory = b'Error Domain=NSOSStatusErrorDomain Code=-26276 "A" Error Domain=NSOSStatusErrorDomain Code=-26275 "B"'
        self.assertEqual(classify_native(SimpleNamespace(returncode=1, stdout=contradictory, stderr=b""))["reason"], "native_diagnostic_conflict")
        self.assertEqual(classify_native(SimpleNamespace(returncode=1, stdout=b"x" * 65537, stderr=b""))["reason"], "native_output_invalid")


class ActualOfflineTests(LocalTest):
    def test_real_TLS_constraints_negative_controls_and_private_key_cleanup(self):
        python = ROOT / ".venv-capture/bin/python"
        if not python.exists():
            self.skipTest("optional isolated cryptography not installed")
        code = r'''
import json, socket, tempfile
from pathlib import Path
from unittest.mock import patch
from cryptography import x509
from validation import certificate_scope as subject
from validation.common import ROOT
with tempfile.TemporaryDirectory(dir=ROOT/'.tmp/feasibility/tests') as raw:
 root=Path(raw)
 with patch.object(subject,'ROOT',root), patch.object(socket,'socket',side_effect=AssertionError('network prohibited')):
  result=subject.fixture(root/'output',native=False)
 report=json.loads((root/'output/certificate-scope.json').read_text())
 assert result['status']=='partial' and report['WeChat_verified'] is False
 assert report['summary']['python_memory_TLS']['exact_dns_no_ip']['status']=='passed_offline_matrix'
 assert set(report['summary']['python_memory_TLS']['dns_only']['unexpected_cases'])=={
  'subdomain','wildcard_subdomain','mixed_subdomain','ipv4','ipv6','mixed_ipv4','mixed_ipv6'}
 assert report['summary']['macOS_explicit_anchor']['exact_dns_no_ip']['status']=='not_verified'
 rejected={r['case']:r for r in report['rows'] if r['validator']=='python_memory_TLS' and r['profile']=='exact_dns_no_ip'}
 assert rejected['mixed_other']['verify_code']==47
 assert rejected['mixed_ipv4']['verify_code']==48
 assert rejected['wrong_host']['verify_code']==62
 assert rejected['expired']['verify_code']==10
 assert rejected['bad_signature']['verify_code']==7
 cert=x509.load_pem_x509_certificate((root/'output/exact_dns_no_ip-root.pem').read_bytes())
 ext=cert.extensions.get_extension_for_class(x509.NameConstraints)
 assert ext.critical and len(ext.value.excluded_subtrees)==3
 assert report['temporary_directory_removed'] and not report['private_keys_retained']
 assert not list((root/'.tmp/wechat-session-validation').iterdir())
 assert not any(b'PRIVATE KEY' in p.read_bytes() for p in (root/'output').iterdir())
 before=(root/'output/target-leaf.pem').read_bytes()
 with patch.object(subject,'ROOT',root):
  try: subject.fixture(root/'output',native=False)
  except FileExistsError: pass
  else: raise AssertionError('Existing output accepted')
 assert before==(root/'output/target-leaf.pem').read_bytes()
 with patch.object(subject,'ROOT',root),patch.object(subject,'memory_verify',side_effect=RuntimeError('synthetic failure')):
  try: subject.fixture(root/'failed',native=False)
  except RuntimeError: pass
  else: raise AssertionError('Failure swallowed')
 assert not list((root/'.tmp/wechat-session-validation').iterdir())
 assert not any(b'PRIVATE KEY' in p.read_bytes() for p in (root/'failed').iterdir())
 print(json.dumps({'status':'passed','network':False,'private_keys_retained':False}))
'''
        response = subprocess.run([str(python), "-c", code], cwd=ROOT, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(json.loads(response.stdout)["status"], "passed")
