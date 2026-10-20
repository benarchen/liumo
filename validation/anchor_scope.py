"""One authorized offline user-trust experiment, without private key files."""

import fcntl
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .certificate_scope import TARGET, cases, assess, classify_native
from .capture_session import (ARTICLE_SESSION, PROFILE_SESSION, DIAGNOSTIC_SESSION,
    UI_DIAGNOSTIC_SESSION, ARTICLE_DIAGNOSTIC_SESSION, SessionWindow, private_json, private_write)
from .common import ROOT, new_run, timestamp, write_json
from .credentials import check_private
from .http import ProbeError

DIRECTORY = ROOT / '.auth/wechat-capture/anchor-scope-session'
SECURITY = '/usr/bin/security'
PREVIOUS = (ARTICLE_SESSION, PROFILE_SESSION, DIAGNOSTIC_SESSION,
            UI_DIAGNOSTIC_SESSION, ARTICLE_DIAGNOSTIC_SESSION)
CERT_NAMES = tuple(p + '-root.pem' for p in ('unconstrained', 'dns_only', 'exact_dns_no_ip')) + tuple(
    row['id'] + '-leaf.pem' for row in cases())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def previous_closed():
    for directory in PREVIOUS:
        state = private_json(directory / 'state.json')
        if (state.get('finished') is not True or state.get('recovery', {}).get('verified') is not True
                or state.get('proxy_process_stopped') is not True):
            raise ProbeError('anchor_previous_recovery_unverified')


@contextmanager
def locks():
    """Existing controllers and this recovery entry cannot overlap this worker."""
    with ExitStack() as stack:
        for directory in (*PREVIOUS, DIRECTORY):
            check_private(directory)
            path = directory / '.lifecycle.lock'
            flags = os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if directory == DIRECTORY else 0)
            descriptor = os.open(path, flags, 0o600)
            stream = stack.enter_context(os.fdopen(descriptor, 'r+'))
            check_private(path)
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ProbeError('anchor_lifecycle_busy') from None
        yield


def generate_public(directory, name):
    """Run only in the short signing child; no TLS server/private key export."""
    from .certificate_scope import _materials
    os.umask(0o077)
    _materials(directory, None, public_only=True, ca_name=name)


def material_plan(directory, name):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID
    if not re.fullmatch(r'liumo-anchor-[a-f0-9]{32}', name):
        raise ProbeError('anchor_name_invalid')
    if set(p.name for p in directory.iterdir()) != set(CERT_NAMES):
        raise ProbeError('anchor_public_materials_invalid')
    for path in directory.iterdir():
        check_private(path)
        data = path.read_bytes()
        if len(data) > 16384 or data.count(b'BEGIN CERTIFICATE') != 1 or b'PRIVATE KEY' in data:
            raise ProbeError('anchor_public_materials_invalid')
        x509.load_pem_x509_certificate(data)
    ca = x509.load_pem_x509_certificate((directory / 'exact_dns_no_ip-root.pem').read_bytes())
    if ca.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value != name:
        raise ProbeError('anchor_certificate_identity_mismatch')
    constraints = ca.extensions.get_extension_for_class(x509.NameConstraints)
    if (not constraints.critical or [n.value for n in constraints.value.permitted_subtrees] != [TARGET]
            or [str(n.value) for n in constraints.value.excluded_subtrees] !=
            ['.' + TARGET, '0.0.0.0/0', '::/0']):
        raise ProbeError('anchor_certificate_constraints_invalid')
    return {'version': 1, 'experiment': 'anchor_scope', 'ca_name': name,
            'certificate_sha256': ca.fingerprint(hashes.SHA256()).hex().upper(),
            'materials': {name: digest(directory / name) for name in CERT_NAMES}}


def load_plan():
    for path in (ROOT / '.auth', DIRECTORY.parent, DIRECTORY, DIRECTORY / 'public'):
        check_private(path)
    plan = private_json(DIRECTORY / 'plan.json')
    actual = material_plan(DIRECTORY / 'public', plan.get('ca_name', ''))
    if plan != actual:
        raise ProbeError('anchor_plan_identity_mismatch')
    return plan


class Native:
    def __init__(self, directory, plan, run=None, *, recovery_timeout=30):
        self.directory, self.plan = directory, plan
        self.keychain = str(Path.home() / 'Library/Keychains/login.keychain-db')
        self.run = subprocess.run if run is None else run
        self.recovery_timeout = recovery_timeout
        self.ca_file = self.directory / 'exact_dns_no_ip-root.pem'

    def validate(self):
        if load_plan() != self.plan:
            raise ProbeError('anchor_plan_identity_mismatch')

    def command(self, args, timeout=4):
        try:
            return self.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ProbeError('anchor_native_command_timed_out') from None
        except OSError:
            raise ProbeError('anchor_native_command_unavailable') from None

    def verify(self, case, root=None, timeout=4, include_root=False):
        if case not in cases() or root not in (None, 'unconstrained', 'exact_dns_no_ip'):
            raise ProbeError('anchor_verification_scope_invalid')
        command = [SECURITY, 'verify-cert', '-v', '-L', '-R', 'offline', '-p', 'ssl', '-n', case['host']]
        if root is None:
            command.extend(['-k', self.keychain])
        else:
            command.extend(['-N', '-r', str(self.directory / (root + '-root.pem'))])
        command.extend(['-c', str(self.directory / (case['id'] + '-leaf.pem'))])
        if include_root:
            if root is not None:
                raise ProbeError('anchor_verification_scope_invalid')
            command.extend(['-c', str(self.directory / 'exact_dns_no_ip-root.pem')])
        try:
            return classify_native(self.command(command, timeout))
        except ProbeError:
            return {'outcome': 'not_verified', 'reason': 'anchor_native_command_unavailable'}

    def present(self):
        response = self.command([SECURITY, 'find-certificate', '-c', self.plan['ca_name'], '-Z', self.keychain])
        if response.returncode == 44 and not response.stdout:
            return False
        if (response.returncode == 0 and len(response.stdout) <= 65536
                and self.plan['certificate_sha256'].encode() in response.stdout.upper()):
            return True
        raise ProbeError('anchor_certificate_presence_unknown')

    def trust(self, timeout):
        self.validate()
        response = self.command([SECURITY, 'add-trusted-cert', '-r', 'trustRoot', '-p', 'ssl', '-k',
                                 self.keychain, str(self.ca_file)], timeout)
        if response.returncode != 0:
            raise ProbeError('anchor_trust_command_rejected', response.returncode)

    def revoke(self):
        # Validate ownership again immediately before either destructive operation.
        self.validate()
        ca = str(self.ca_file)
        failures = []
        for args, allowed in (
                ([SECURITY, 'remove-trusted-cert', ca], (0,)),
                ([SECURITY, 'delete-certificate', '-Z', self.plan['certificate_sha256'], '-t', self.keychain], (0, 44))):
            try:
                if self.command(args, self.recovery_timeout).returncode not in allowed:
                    failures.append('native_nonzero_exit')
            except ProbeError as exc:
                failures.append(exc.reason)
        absent = not self.present()
        # Supply the public root as a chain certificate, never as an explicit
        # trust anchor: absence in the keychain alone cannot prove revocation.
        result = self.verify(cases()[0], include_root=True)
        return {'certificate_absent': absent, 'target_after_removal': result,
                'removal_command_issues': failures, 'verified': absent and not_trusted(result)}


def not_trusted(result):
    # SDK SecBase.h: errSecNotTrusted / errSecCreateChainFailed.
    # A prior explicit-root success establishes the target leaf itself is valid.
    return (result.get('outcome') == 'rejected' and result.get('trust_result') in (3, 5, 6)
            and result.get('OSStatus_codes') in ([-67843], [-25318]))


class Window(SessionWindow):
    def timeout(self, limit=4):
        self.check()
        available = min(self.seconds - (self.monotonic() - self.started),
                        self.wall_deadline - self.wall()) - 70
        if available <= 0:
            raise ProbeError('anchor_cleanup_reserve_reached')
        return min(limit, available)


def recover(native, state, save):
    def record():
        try:
            save(state)
        except Exception:
            state['journal_write_failed'] = True
    try:
        result = native.revoke() if state.get('trust_attempted') else {
            'verified': True, 'trust': 'unchanged'}
    except Exception:
        result = {'verified': False, 'trust': 'recovery_unverified'}
    state.update(recovery=result, recovery_completed_at=timestamp(), finished=True,
                 status='closed' if result['verified'] else 'manual_recovery_required')
    record()
    return result


def evaluate(native, state, save, window):
    """No system mutation before complete, explicit-root and untrusted controls."""
    state['controls'] = []
    for profile in ('unconstrained', 'exact_dns_no_ip'):
        for case in cases():
            row = native.verify(case, profile, window.timeout())
            state['controls'].append({'validator': 'native', 'profile': profile, 'case': case['id'], **row})
            expected = case['valid_control'] if profile == 'unconstrained' else case['in_scope']
            if row['outcome'] != ('accepted' if expected else 'rejected'):
                raise ProbeError('anchor_explicit_control_failed')
    state['explicit_control_summary'] = assess(state['controls'], 'native', 'exact_dns_no_ip')
    if state['explicit_control_summary']['status'] != 'passed_offline_matrix':
        raise ProbeError('anchor_explicit_control_failed')
    if native.present():
        raise ProbeError('anchor_CA_already_present')
    state['before'] = []
    for case in cases():
        row = native.verify(case, timeout=window.timeout())
        state['before'].append({'case': case['id'], **row})
        acceptable = not_trusted(row) if case['valid_control'] else row['outcome'] == 'rejected'
        if not acceptable:
            raise ProbeError('anchor_preinstall_not_untrusted')
    state['before_target_with_chain'] = native.verify(cases()[0], timeout=window.timeout(), include_root=True)
    if not not_trusted(state['before_target_with_chain']):
        raise ProbeError('anchor_preinstall_chain_not_untrusted')
    save(state)
    state.update(trust_attempted=True, trust_started_at=timestamp(), status='temporary_trust_requested')
    save(state)  # Never install if the write-ahead record cannot be persisted.
    native.trust(window.timeout(30))
    if not native.present():
        raise ProbeError('anchor_installed_certificate_unconfirmed')
    state['after'] = []
    for case in cases():
        row = native.verify(case, timeout=window.timeout())
        state['after'].append({'case': case['id'], **row})
        save(state)
        if row['outcome'] != ('accepted' if case['in_scope'] else 'rejected'):
            raise ProbeError('anchor_installed_scope_failed')
    state['installed_matrix_passed'] = True


def worker():
    os.umask(0o077)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    def terminate(_number, _frame):
        raise ProbeError('anchor_worker_terminated')
    signal.signal(signal.SIGTERM, terminate)
    plan = load_plan()
    with locks():
        previous_closed()
        state = {'at': timestamp(), 'status': 'checking_controls', 'finished': False,
                 'trust_attempted': False, 'installed_matrix_passed': False,
                 'network_or_proxy_used': False, 'WeChat_verified': False,
                 'certificate_sha256': plan['certificate_sha256']}
        save = lambda value: private_write(DIRECTORY / 'state.json', value)
        native = Native(DIRECTORY / 'public', plan)
        window = Window(sys.stdin.fileno(), time.time() + 120, seconds=120)
        state['duration_limit_seconds'] = 120
        try:
            save(state)
            evaluate(native, state, save, window)
            state['reason'] = 'anchor_installed_matrix_finished'
        except ProbeError as exc:
            state['reason'] = exc.reason
        except BaseException:
            state['reason'] = 'anchor_worker_failed'
        finally:
            # Once cleanup begins, another TERM must not interrupt deletion.
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            recover(native, state, save)
            state['worker_elapsed_seconds'] = round(time.monotonic() - window.started, 3)
            try:
                save(state)
            except Exception:
                pass


def session():
    """Read-only preflight first; rejected preflight does not consume fixed run."""
    if DIRECTORY.exists() or DIRECTORY.is_symlink():
        raise ProbeError('anchor_session_already_exists')
    previous_closed()
    for node in (ROOT / '.auth', DIRECTORY.parent):
        check_private(node)
    os.umask(0o077)
    base = ROOT / '.tmp/wechat-session-validation'
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base, prefix='anchor-preflight-') as raw:
        temporary = Path(raw)
        name = 'liumo-anchor-' + uuid.uuid4().hex
        # Signing child exits (and its memory-only keys cease to exist) before any trust operation.
        code = ('from pathlib import Path; from validation.anchor_scope import generate_public; '
                'import sys; generate_public(Path(sys.argv[1]), sys.argv[2])')
        result = subprocess.run([str(ROOT / '.venv-capture/bin/python'), '-c', code, str(temporary), name],
                                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=15)
        if result.returncode:
            raise ProbeError('anchor_public_signing_failed')
        plan = material_plan(temporary, name)
        control = Native(temporary, plan).verify(cases()[0], 'unconstrained')
        if control['outcome'] != 'accepted':
            output = new_run('anchor-scope-preflight')
            shutil.copytree(temporary, output / 'public')
            report = {'at': timestamp(), 'status': 'blocked', 'reason': 'anchor_explicit_preflight_failed',
                      'control': control, 'signing_child_exited': True, 'private_keys_written': False,
                      'experiment_created': False, 'system_trust_changed': False,
                      'network_or_proxy_used': False, 'WeChat_verified': False, 'plan': plan}
            write_json(output / 'preflight.json', report)
            return {'output': str(output), **{k: report[k] for k in (
                'status', 'reason', 'control', 'experiment_created', 'system_trust_changed')}}
        DIRECTORY.mkdir(mode=0o700)
        shutil.copytree(temporary, DIRECTORY / 'public')
        private_write(DIRECTORY / 'plan.json', plan)
        private_write(DIRECTORY / 'recovery-plan.json', {
            'certificate_sha256': plan['certificate_sha256'], 'only_this_user_certificate': True,
            'recommended_entry': [str(ROOT / '.venv-capture/bin/python'), '-m', 'validation', 'anchor-scope-recover'],
            'notice': '仅恢复本次新证书；不更改代理或其他信任项。'})
    child = subprocess.Popen([str(ROOT / '.venv-capture/bin/python'), '-m', 'validation.anchor_scope', '--worker'],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)
    print('主人，正在执行本次离线信任对照；如出现 macOS 用户信任提示，请由你确认。无需操作微信或按 Enter。', flush=True)
    try:
        child.wait(timeout=130)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        child.stdin.close()
        try:
            child.wait(timeout=25)
        except subprocess.TimeoutExpired:
            return {'status': 'blocked', 'reason': 'anchor_worker_cleanup_pending',
                    'private_session': str(DIRECTORY)}
    finally:
        if not child.stdin.closed:
            child.stdin.close()
    state = private_json(DIRECTORY / 'state.json') if (DIRECTORY / 'state.json').exists() else {
        'reason': 'anchor_worker_no_final_state', 'finished': False}
    output = new_run('anchor-scope-session')
    write_json(output / 'session-summary.json', state)
    shutil.copytree(DIRECTORY / 'public', output / 'public')
    complete = state.get('installed_matrix_passed') and state.get('recovery', {}).get('verified')
    return {'output': str(output), 'status': 'partial' if complete else 'blocked',
            'reason': state.get('reason'), 'installed_matrix_passed': bool(state.get('installed_matrix_passed')),
            'trust_attempted': bool(state.get('trust_attempted')),
            'recovery': state.get('recovery'), 'WeChat_verified': False}


def manual_recover():
    plan = load_plan()
    with locks():
        path = DIRECTORY / 'state.json'
        state = private_json(path) if path.exists() else {'trust_attempted': True}
        if state.get('finished') and state.get('recovery', {}).get('verified'):
            return {'status': 'already_closed_no_changes', 'recorded_recovery': state['recovery'],
                    'current_system_state_rechecked': False}
        # This entry only removes the existing experiment's trust. Allow time
        # for user authorization prompts; never reinstall or start a new run.
        result = recover(Native(DIRECTORY / 'public', plan, recovery_timeout=30), state,
                         lambda value: private_write(path, value))
        return {'status': 'recovered' if result['verified'] else 'blocked', 'recovery': result}


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    worker()
