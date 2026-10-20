"""Synthetic certificate constraints; no trust installation, sockets or WeChat."""

import ipaddress
import os
import re
import ssl
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import ROOT, new_run, timestamp, write_json

TARGET = "mp.weixin.qq.com"
PROFILES = ("unconstrained", "dns_only", "exact_dns_no_ip")


def cases():
    rows = [
        ("target", TARGET, [TARGET], [], True),
        ("uppercase_target", TARGET.upper(), [TARGET.upper()], [], True),
        ("other", "other.invalid", ["other.invalid"], [], False),
        ("subdomain", "a." + TARGET, ["a." + TARGET], [], False),
        ("suffix", TARGET + ".evil.invalid", [TARGET + ".evil.invalid"], [], False),
        ("prefix", "not" + TARGET, ["not" + TARGET], [], False),
        ("wildcard_parent", TARGET, ["*.weixin.qq.com"], [], False),
        ("wildcard_subdomain", "a." + TARGET, ["*." + TARGET], [], False),
        ("mixed_other", TARGET, [TARGET, "other.invalid"], [], False),
        ("mixed_subdomain", TARGET, [TARGET, "a." + TARGET], [], False),
        ("ipv4", "192.0.2.1", [], ["192.0.2.1"], False),
        ("ipv6", "2001:db8::1", [], ["2001:db8::1"], False),
        ("mixed_ipv4", TARGET, [TARGET], ["192.0.2.1"], False),
        ("mixed_ipv6", TARGET, [TARGET], ["2001:db8::1"], False),
        ("wrong_host", TARGET, ["other.invalid"], [], False),
        ("expired", TARGET, [TARGET], [], False),
        ("bad_signature", TARGET, [TARGET], [], False),
    ]
    return [dict(id=name, host=host, dns=dns, ips=ips, in_scope=scope,
                 valid_control=name not in {"wrong_host", "expired", "bad_signature"})
            for name, host, dns, ips, scope in rows]


def _materials(output, private, *, public_only=False, ca_name="liumo offline fixture CA"):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ca_name)])
    def builder(subject, key, ca, expired=False):
        return (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=2) if expired else now - timedelta(minutes=1) if public_only else now - timedelta(days=1))
                .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(minutes=20) if public_only else now + timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca else None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                    key_encipherment=not ca, data_encipherment=False, key_agreement=False,
                    key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False))
    roots = {}
    for profile in PROFILES:
        cert = builder(issuer, ca_key, True)
        if profile != "unconstrained":
            excluded = ([x509.DNSName("." + TARGET), x509.IPAddress(ipaddress.ip_network("0.0.0.0/0")),
                         x509.IPAddress(ipaddress.ip_network("::/0"))] if profile == "exact_dns_no_ip" else None)
            cert = cert.add_extension(x509.NameConstraints([x509.DNSName(TARGET)], excluded), critical=True)
        path = output / (profile + "-root.pem")
        path.write_bytes(cert.sign(ca_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
        roots[profile] = path
    key_path = None
    if not public_only:
        key_path = private / "server-key.pem"
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                  serialization.NoEncryption()))
    leaves = {}
    for case in cases():
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, TARGET)])
        cert = builder(subject, server_key, False, expired=case["id"] == "expired")
        names = [x509.DNSName(name) for name in case["dns"]]
        names += [x509.IPAddress(ipaddress.ip_address(name)) for name in case["ips"]]
        cert = cert.add_extension(x509.SubjectAlternativeName(names), critical=False)
        cert = cert.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        leaf = output / (case["id"] + "-leaf.pem")
        leaf.write_bytes(cert.sign(wrong_key if case["id"] == "bad_signature" else ca_key,
                                   hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
        leaves[case["id"]] = leaf
    return roots, leaves, key_path


def memory_verify(root, leaf, key, host):
    """Real TLS client/server handshake over BIO bytes, with an explicit root."""
    client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_context.load_verify_locations(cafile=str(root))
    client_context.hostname_checks_common_name = False
    client_context.verify_flags |= ssl.VERIFY_X509_STRICT
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(str(leaf), str(key))
    assert client_context.verify_mode == ssl.CERT_REQUIRED and client_context.check_hostname
    assert client_context.keylog_filename is None and server_context.keylog_filename is None
    ci, co, si, so = (ssl.MemoryBIO() for _ in range(4))
    client = client_context.wrap_bio(ci, co, server_hostname=host)
    server = server_context.wrap_bio(si, so, server_side=True)
    complete = [False, False]
    try:
        for _ in range(64):
            progressed = False
            for i, peer in enumerate((client, server)):
                if not complete[i]:
                    try:
                        peer.do_handshake()
                        complete[i] = True
                        progressed = True
                    except ssl.SSLWantReadError:
                        pass
            for source, destination in ((co, si), (so, ci)):
                if source.pending:
                    destination.write(source.read())
                    progressed = True
            if all(complete):
                return {"outcome": "accepted", "TLS_version": client.version()}
            if not progressed:
                break
    except ssl.SSLCertVerificationError as exc:
        return {"outcome": "rejected", "verify_code": exc.verify_code,
                "reason": {47: "permitted_subtree", 48: "excluded_subtree", 62: "hostname_mismatch",
                           64: "IP_mismatch", 10: "expired", 7: "signature_invalid"}.get(
                               exc.verify_code, "certificate_verification")}
    except ssl.SSLError:
        return {"outcome": "not_verified", "reason": "TLS_error"}
    return {"outcome": "not_verified", "reason": "handshake_incomplete"}


def classify_native(response):
    """Keep fixed numeric diagnostics; CT text alone is not a failure cause."""
    if response.returncode < 0:
        return {"outcome": "not_verified", "reason": "native_tool_terminated"}
    message = (response.stdout + response.stderr).lower()
    if len(message) > 65536:
        return {"outcome": "not_verified", "reason": "native_output_invalid"}
    codes = sorted(set(int(value) for value in re.findall(
        rb'error domain=nsosstatuserrordomain code=(-?\d{1,10})(?=\s|["}])', message)))
    values = sorted(set(int(value) for value in re.findall(rb'\btrustresultvalue\s*=\s*(\d{1,2})\s*;', message)))
    result = {"outcome": "not_verified", "exit_code": response.returncode,
              "CT_diagnostic_present": b"signed certificate timestamps" in message,
              "OSStatus_codes": codes}
    if (len(codes) > 1 or len(values) > 1 or any(not -(2**31) <= code < 2**31 for code in codes)
            or any(value > 7 for value in values)):
        return {**result, "reason": "native_diagnostic_conflict"}
    trust = values[0] if values else None
    if trust is not None:
        result["trust_result"] = trust
    if -26276 in codes:
        return {**result, "reason": "native_security_framework_error"}
    if trust == 0:
        return {**result, "reason": "native_evaluation_invalid"}
    if response.returncode == 0:
        if codes or trust not in (1, 4):
            return {**result, "reason": "native_success_unconfirmed"}
        return {**result, "outcome": "accepted"}
    if trust in (3, 5, 6):
        return {**result, "outcome": "rejected", "reason": "native_trust_rejected"}
    reason = ("native_authorization_unavailable" if b"authorizationcreate" in message else
              "native_CT_diagnostic_only" if result["CT_diagnostic_present"] else
              "native_nonzero_exit_unclassified")
    return {**result, "reason": reason}


def native_verify(root, leaf, host, run=subprocess.run):
    """Verbose diagnostics only; verification policy and offline guards unchanged."""
    command = ["/usr/bin/security", "verify-cert", "-v", "-N", "-L", "-R", "offline",
               "-p", "ssl", "-n", host, "-r", str(root), "-c", str(leaf)]
    try:
        response = run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return {"outcome": "not_verified", "reason": "native_tool_unavailable"}
    return classify_native(response)


def assess(rows, validator, profile):
    selected = [row for row in rows if row["validator"] == validator and row["profile"] == profile]
    catalog = {case["id"]: case for case in cases()}
    if len(selected) != len(catalog) or {row["case"] for row in selected} != set(catalog):
        return {"status": "not_verified", "reason": "matrix_incomplete"}
    if any(row["outcome"] not in {"accepted", "rejected"} for row in selected):
        return {"status": "not_verified", "reason": "validator_unavailable"}
    controls = [row for row in rows if row["validator"] == validator and row["profile"] == "unconstrained"]
    baseline = {row["case"]: row for row in controls}
    if len(controls) != len(catalog) or set(baseline) != set(catalog):
        return {"status": "not_verified", "reason": "baseline_control_failed"}
    for name, case in catalog.items():
        expected = "accepted" if case["valid_control"] else "rejected"
        actual = baseline.get(name, {}).get("outcome")
        if actual != expected:
            return {"status": "not_verified", "reason": "baseline_control_failed"}
    failures = [row["case"] for row in selected
                if (row["outcome"] == "accepted") != catalog[row["case"]]["in_scope"]]
    return {"status": "scope_not_preserved" if failures else "passed_offline_matrix",
            "unexpected_cases": failures, "WeChat_verified": False}


def fixture(output=None, native=True):
    # Import only when using the optional, already installed isolated dependency.
    import cryptography
    if output is None:
        output = new_run("certificate-scope-offline")
    else:
        output = Path(output)
        output.mkdir(mode=0o700)  # Reject every existing directory or symlink.
    temporary_base = ROOT / ".tmp/wechat-session-validation"
    temporary_base.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=temporary_base, prefix="certificate-scope-") as raw:
        private = Path(raw)
        roots, leaves, key = _materials(output, private)
        native_gate = native_verify(roots["unconstrained"], leaves["target"], TARGET) if native else {
            "outcome": "not_verified", "reason": "native_not_requested"}
        for profile in PROFILES:
            for case in cases():
                for validator in ("python_memory_TLS", "macOS_explicit_anchor"):
                    result = (memory_verify(roots[profile], leaves[case["id"]], key, case["host"])
                              if validator == "python_memory_TLS" else
                              native_verify(roots[profile], leaves[case["id"]], case["host"])
                              if native_gate["outcome"] == "accepted" else
                              {"outcome": "not_verified", "reason": "native_positive_control_unavailable"})
                    rows.append({"validator": validator, "profile": profile, "case": case["id"], **result})
    summary = {validator: {profile: assess(rows, validator, profile) for profile in PROFILES[1:]}
               for validator in ("python_memory_TLS", "macOS_explicit_anchor")}
    report = {"at": timestamp(), "evidence": "synthetic_certificates_real_offline_verifiers",
              "status": "partial", "offline_evaluation_completed": True, "python_SSL": ssl.OPENSSL_VERSION,
              "cryptography": cryptography.__version__, "constraints_on": "explicit_trust_anchor_root",
              "certificates_shared_across_profiles": True, "native_positive_control": native_gate,
              "native_diagnostic_mode": "verbose_same_policy_no_CT_bypass",
              "native_keychain_search": False, "network_or_listener_used": False, "system_trust_changed": False,
              "private_keys_retained": False, "temporary_directory_removed": not private.exists(),
              "WeChat_verified": False, "live_experiment_started": False,
              "profiles": {"unconstrained": "Positive and negative controls only",
                  "dns_only": "Permit DNS subtree mp.weixin.qq.com; no IP restriction",
                  "exact_dns_no_ip": "Permit target DNS subtree, exclude its subdomains and all IPv4/IPv6"},
              "cases": cases(), "rows": rows, "summary": summary}
    write_json(output / "certificate-scope.json", report)
    return {"output": str(output), "status": report["status"], "summary": summary,
            "WeChat_verified": False, "system_trust_changed": False}
