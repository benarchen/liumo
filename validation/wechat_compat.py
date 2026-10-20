"""Offline component preparation only; no system/WeChat/network operations."""

import asyncio
import ipaddress
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from .certificate_scope import TARGET, cases, memory_verify
from .common import ROOT, new_run, timestamp, write_json
from .credentials import check_private
from .http import ProbeError

RESTORE_STEPS = (
    ('disable_interception_and_save', 5), ('read_proxy', 5),
    ('restore_proxy', 30), ('read_back_proxy', 5),
    ('remove_user_trust', 30), ('delete_this_certificate', 30),
    ('read_back_certificate', 5), ('verify_revocation', 5),
    ('stop_process_and_delete_owned_keys', 5),
)


def review_plan():
    reserve = sum(seconds for _, seconds in RESTORE_STEPS)
    return {'status': 'prepared_not_running', 'system_runtime_implemented': True,
        'system_experiment_authorized': True, 'duration_seconds_proposed': 180,
        'cleanup_reserve_seconds': reserve, 'active_budget_seconds': 180 - reserve,
        'cleanup_steps': [{'step': name, 'seconds': seconds} for name, seconds in RESTORE_STEPS],
        'target_host': TARGET, 'sample': 'maobidao', 'max_UI_refreshes': 1,
        'candidate_leaf_SAN': [TARGET], 'ssl_insecure': False,
        'certificate_profile': 'permit target DNS, exclude subdomains and all IPv4/IPv6',
        'new_system_scope': ['one new user SSL constrained CA, no old -s policy string',
            'fresh local 0600 CA and target-leaf key files; remove after process stops',
            'temporary current-service HTTPS proxy, exact original-value recovery',
            '180-second window proposed, with 120 seconds reserved for cleanup'],
        'collect_credentials': False, 'read_response_body': False,
        'system_or_network_operations_executed': False,
        'not_verified': ['installed proxy CA and fixed leaf in actual WeChat',
            'real restoration within proposed time', 'source and full screenshot functionality']}


def operation_budget(started_monotonic, deadline_wall, now_monotonic, now_wall, operation_seconds):
    """Pure scheduling check for the proposal; never runs an operation."""
    import math
    values = (started_monotonic, deadline_wall, now_monotonic, now_wall, operation_seconds)
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError('compat_budget_invalid')
    if not 0 < operation_seconds <= 30 or now_monotonic < started_monotonic:
        raise ValueError('compat_budget_invalid')
    remaining = min(180 - (now_monotonic - started_monotonic), deadline_wall - now_wall)
    return remaining >= sum(seconds for _, seconds in RESTORE_STEPS) + operation_seconds


def _write_new(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)


def prepare_store(directory):
    """Create a private test store; no existing directory is ever overwritten."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    directory = Path(directory)
    check_private(directory.parent)
    directory.mkdir(mode=0o700)
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'liumo-compat-' + uuid.uuid4().hex)])
    common = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(ca_key.public_key()).not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(minutes=20))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False))
    permitted = [x509.DNSName(TARGET)]
    excluded = [x509.DNSName('.' + TARGET), x509.IPAddress(ipaddress.ip_network('0.0.0.0/0')),
                x509.IPAddress(ipaddress.ip_network('::/0'))]
    root = (common.serial_number(x509.random_serial_number())
        .add_extension(x509.NameConstraints(permitted, excluded), True).sign(ca_key, hashes.SHA256()))
    control = common.serial_number(x509.random_serial_number()).sign(ca_key, hashes.SHA256())
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, TARGET)]))
        .issuer_name(name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(minutes=20))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(TARGET)]), False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
        .sign(ca_key, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    private = lambda key: key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    _write_new(directory / 'mitmproxy-ca.pem', private(ca_key) + root.public_bytes(pem))
    _write_new(directory / 'mitmproxy-ca-cert.pem', root.public_bytes(pem))
    _write_new(directory / 'unconstrained-root.pem', control.public_bytes(pem))
    _write_new(directory / 'target-key-chain.pem', private(leaf_key) + leaf.public_bytes(pem) + root.public_bytes(pem))
    _write_new(directory / 'target-leaf.pem', leaf.public_bytes(pem))
    return {'root': directory / 'mitmproxy-ca-cert.pem', 'control': directory / 'unconstrained-root.pem',
            'ca_bundle': directory / 'mitmproxy-ca.pem', 'target_bundle': directory / 'target-key-chain.pem',
            'target_leaf': directory / 'target-leaf.pem'}


async def _component_selection(directory, material, output):
    from cryptography import x509
    from mitmproxy.certs import CertStore
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from cryptography.hazmat.primitives import hashes
    # A master is configured, never run. No listener or network task is started.
    with CertStore.umask_secret():
        options = Options(confdir=str(directory), server=False)
        master = DumpMaster(options, with_termlog=False, with_dumper=False)
        try:
            tls = master.addons.get('tlsconfig')
            tls.configure({'confdir'})
            upstream = tls.certstore.get_cert('*.weixin.qq.com', [x509.DNSName('*.weixin.qq.com')]).cert
            context = SimpleNamespace(client=SimpleNamespace(sni=TARGET, sockname=('127.0.0.1', 10000)),
                server=SimpleNamespace(certificate_list=[upstream], address=('192.0.2.1', 443)))
            default = tls.get_cert(context)
            default_path = output / 'component-default-leaf.pem'
            _write_new(default_path, default.cert.to_pem())
            baseline = {name: memory_verify(material[name], default_path, material['ca_bundle'], TARGET)
                        for name in ('control', 'root')}
            options.update(upstream_cert=False, certs=[TARGET + '=' + str(material['target_bundle'])])
            tls.configure({'certs'})
            selected = tls.get_cert(context)
            selected_path = output / 'component-fixed-leaf.pem'
            _write_new(selected_path, selected.cert.to_pem())
            expected = x509.load_pem_x509_certificate(material['target_leaf'].read_bytes())
            exact = selected.cert._cert.fingerprint(hashes.SHA256()) == expected.fingerprint(hashes.SHA256())
            sans = selected.cert._cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            selected_sans = sans.get_values_for_type(x509.DNSName)
            fixed = memory_verify(material['root'], selected_path, material['target_bundle'], TARGET)
            wrong = memory_verify(material['root'], selected_path, material['target_bundle'], 'other.invalid')
            root_matches = tls.certstore.default_ca.to_pem() == material['root'].read_bytes()
            return {'upstream_wildcard_and_server_IP_context': True,
                'default_selection_TLS': baseline, 'fixed_selection_TLS': fixed, 'wrong_host_TLS': wrong,
                'fixed_certificate_selected': exact, 'fixed_SAN': selected_sans,
                'configured_CA_preserved': root_matches, 'ssl_insecure': options.ssl_insecure,
                'upstream_cert': options.upstream_cert, 'master_run_called': False,
                'passed': baseline['control']['outcome'] == 'accepted' and baseline['root']['outcome'] == 'rejected'
                    and exact and selected_sans == [TARGET] and len(sans) == 1 and root_matches
                    and fixed['outcome'] == 'accepted' and wrong['outcome'] == 'rejected'
                    and options.ssl_insecure is False}
        finally:
            master.shutdown()


def fixture(output=None):
    from importlib.metadata import version
    from cryptography import x509
    from mitmproxy.certs import CertStore
    if output is None:
        output = new_run('wechat-compat-offline')
    else:
        output = Path(output)
        output.mkdir(mode=0o700)
    base = ROOT / '.tmp/wechat-session-validation'
    base.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=base, prefix='wechat-compat-') as raw:
        private = Path(raw)
        directory = private / 'store'
        material = prepare_store(directory)
        expected_root = material['root'].read_bytes()
        check_private(material['ca_bundle'])
        with CertStore.umask_secret():
            store = CertStore.from_store(directory, 'mitmproxy', 2048)
        if store.default_ca.to_pem() != expected_root:
            raise ProbeError('compat_CA_fallback_rejected')
        for name in ('root', 'control', 'target_leaf'):
            _write_new(output / (name + '.pem'), material[name].read_bytes())
        for case in cases():
            if case['id'] in ('expired', 'bad_signature'):
                continue  # These controls belong to C15; component uses its own validity/signing.
            names = [x509.DNSName(name) for name in case['dns']]
            names += [x509.IPAddress(ipaddress.ip_address(name)) for name in case['ips']]
            entry = store.get_cert(case['dns'][0] if case['dns'] else case['host'], names)
            leaf = output / (case['id'] + '-leaf.pem')
            _write_new(leaf, entry.cert.to_pem())
            for profile in ('control', 'root'):
                result = memory_verify(material[profile], leaf, material['ca_bundle'], case['host'])
                expected = case['valid_control'] if profile == 'control' else case['in_scope']
                rows.append({'case': case['id'], 'profile': profile, 'expected_accept': expected, **result})
        selection = asyncio.run(_component_selection(directory, material, output))
        if material['root'].read_bytes() != expected_root:
            raise ProbeError('compat_CA_fallback_rejected')
        # Every artifact is public; key bundles are confined to the temporary store.
        assert not any(b'PRIVATE KEY' in p.read_bytes() for p in output.iterdir())
    matrix_passed = len(rows) == 30 and all(row['outcome'] == (
        'accepted' if row['expected_accept'] else 'rejected') for row in rows)
    offline_passed = matrix_passed and selection['passed']
    report = {'at': timestamp(), 'status': 'partial' if offline_passed else 'failed',
        'evidence': 'real_installed_component_synthetic_certificates_and_context_real_memory_TLS',
        'versions': {'mitmproxy': version('mitmproxy'), 'cryptography': version('cryptography')},
        'matrix_rows': rows, 'matrix_passed': matrix_passed, 'component_selection': selection,
        'offline_checks_passed': offline_passed,
        'temporary_directory_removed': not private.exists(), 'private_keys_retained': False,
        'system_trust_changed': False, 'proxy_or_listener_started': False,
        'network_requests_made': False, 'WeChat_verified': False, 'plan': review_plan()}
    write_json(output / 'compatibility.json', report)
    return {'output': str(output), 'status': report['status'], 'offline_checks_passed': report['offline_checks_passed'],
            'system_trust_changed': False, 'WeChat_verified': False}
