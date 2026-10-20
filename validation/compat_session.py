"""Fixed C16/C17/C21/C22/C24 modes. Independent worker and scoped recovery."""

import fcntl
import hashlib
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

from . import anchor_scope as anchor
from .capture_preflight import collect_baseline, NETWORKSETUP, parse_proxy
from .capture_session import (APPLIED, SessionWindow, private_json, private_write,
                              same_configuration, upstream_mode, verify_diagnostic_control)
from .certificate_scope import TARGET, cases, classify_native
from .common import ROOT, new_run, timestamp, write_json
from .credentials import check_private
from .http import ProbeError
from .wechat_compat import prepare_store, operation_budget

DIRECTORY = ROOT / '.auth/wechat-capture/wechat-compat-session'
COMPAT_DIRECTORY = DIRECTORY
PREVIOUS = (*anchor.PREVIOUS, anchor.DIRECTORY)
UI_READY = ROOT / '.tmp/wechat-session-validation/compat-ui-ready.json'
EXPERIMENT = 'wechat_compat'
ADDON = ROOT / 'validation/compat_addon.py'
READY_STATUS = 'ready_refresh_maobidao_article_for_compatibility'
WORKER_FLAG = '--worker'
RUN_SLUG = 'wechat-compat-session'
KEYS = ('mitmproxy-ca.pem', 'target-key-chain.pem')
PUBLIC = ('mitmproxy-ca-cert.pem', 'unconstrained-root.pem', 'target-leaf.pem')


def previous_closed():
    anchor.previous_closed()
    state = private_json(anchor.DIRECTORY / 'state.json')
    if not state.get('finished') or state.get('recovery', {}).get('verified') is not True:
        raise ProbeError('compat_previous_recovery_unverified')
    if EXPERIMENT in ('article_functional', 'comment_baseline', 'comment_refresh', 'article_static'):
        state = private_json(COMPAT_DIRECTORY / 'state.json')
        if (state.get('finished') is not True or state.get('status') != 'closed'
                or state.get('recovery', {}).get('verified') is not True
                or state.get('recovery', {}).get('process_stopped') is not True):
            raise ProbeError('functional_previous_recovery_unverified')
    if EXPERIMENT in ('comment_baseline', 'comment_refresh', 'article_static'):
        from .comment_baseline import ARTICLE_DIRECTORY
        state = private_json(ARTICLE_DIRECTORY / 'state.json')
        if (state.get('finished') is not True or state.get('status') != 'closed'
                or state.get('recovery', {}).get('verified') is not True
                or state.get('recovery', {}).get('process_stopped') is not True):
            raise ProbeError('comment_previous_recovery_unverified')
    if EXPERIMENT in ('comment_refresh', 'article_static'):
        from .comment_baseline import BASELINE_DIRECTORY
        state = private_json(BASELINE_DIRECTORY / 'state.json')
        recovery = state.get('recovery', {})
        if (state.get('finished') is not True or state.get('status') != 'closed'
                or any(recovery.get(k) is not True for k in ('verified', 'proxy_verified', 'process_stopped', 'keys_removed'))
                or recovery.get('trust', {}).get('verified') is not True):
            raise ProbeError('comment_refresh_previous_unverified')
    if EXPERIMENT == 'article_static':
        from .html_static_session import authorized
        authorized()  # Bound C22 closure is also required before any preflight.


@contextmanager
def locks():
    with ExitStack() as stack:
        for directory in (*PREVIOUS, DIRECTORY):
            check_private(directory)
            path = directory / '.lifecycle.lock'
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if directory == DIRECTORY else 0), 0o600)
            stream = stack.enter_context(os.fdopen(fd, 'r+'))
            check_private(path)
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ProbeError('compat_lifecycle_busy') from None
        yield


def digest(path):
    check_private(path)
    if not path.is_file():
        raise ProbeError('compat_material_invalid')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_plan(directory):
    """Only fixed public identities and private-key hashes enter this journal."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID
    store = directory / 'mitmproxy'
    ca = x509.load_pem_x509_certificate((store / PUBLIC[0]).read_bytes())
    nc = ca.extensions.get_extension_for_class(x509.NameConstraints)
    if (not nc.critical or [n.value for n in nc.value.permitted_subtrees] != [TARGET]
            or [str(n.value) for n in nc.value.excluded_subtrees] != ['.' + TARGET, '0.0.0.0/0', '::/0']):
        raise ProbeError('compat_constraints_invalid')
    name = ca.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    import re
    if not re.fullmatch(r'liumo-compat-[a-f0-9]{32}', name):
        raise ProbeError('compat_identity_invalid')
    paths = ['mitmproxy/' + n for n in PUBLIC] + ['probes/' + c['id'] + '-leaf.pem' for c in cases()]
    return {'ca_name': name, 'certificate_sha256': ca.fingerprint(hashes.SHA256()).hex().upper(),
            'materials': {p: digest(directory / p) for p in paths}}


def generate(directory):
    """Fresh CA and leaf keys; only public probe certificates, never real traffic."""
    import ipaddress
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    material = prepare_store(directory / 'mitmproxy')
    ca = x509.load_pem_x509_certificate(material['root'].read_bytes())
    leaf = x509.load_pem_x509_certificate(material['target_leaf'].read_bytes())
    key = serialization.load_pem_private_key(material['ca_bundle'].read_bytes(), password=None)
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    probes = directory / 'probes'
    probes.mkdir(mode=0o700)
    now = datetime.now(timezone.utc)
    for case in cases():
        expired = case['id'] == 'expired'
        cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, TARGET)]))
            .issuer_name(ca.subject).public_key(leaf.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2) if expired else now - timedelta(minutes=1))
            .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(minutes=20))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in case['dns']] +
                [x509.IPAddress(ipaddress.ip_address(n)) for n in case['ips']]), False)
            .sign(wrong if case['id'] == 'bad_signature' else key, hashes.SHA256()))
        path = probes / (case['id'] + '-leaf.pem')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(cert.public_bytes(serialization.Encoding.PEM))
    return {**material_plan(directory), 'keys': {n: digest(directory / 'mitmproxy' / n) for n in KEYS}}


def load_plan():
    for node in (ROOT / '.auth', DIRECTORY.parent, DIRECTORY, DIRECTORY / 'mitmproxy', DIRECTORY / 'probes'):
        check_private(node)
    plan = private_json(DIRECTORY / 'plan.json')
    identity = material_plan(DIRECTORY)
    if (plan.get('experiment') != EXPERIMENT or plan.get('version') != 1
            or plan.get('duration_seconds') != 180 or plan.get('cleanup_reserve_seconds') != 120
            or plan.get('mode') != upstream_mode(plan['baseline'])
            or any(plan.get(k) != v for k, v in identity.items())
            or set(plan.get('keys', {})) != set(KEYS)
            or any(not isinstance(v, str) or len(v) != 64 for v in plan['keys'].values())
            or type(plan.get('wall_deadline')) not in (int, float) or not math.isfinite(plan['wall_deadline'])
            or plan.get('active_deadline') != plan['wall_deadline'] - 120):
        raise ProbeError('compat_plan_invalid')
    return plan


class Native(anchor.Native):
    def __init__(self, directory, plan, run=None):
        super().__init__(directory, plan, run, recovery_timeout=30)
        self.ca_file = directory / 'mitmproxy' / PUBLIC[0]

    def validate(self):
        if load_plan() != self.plan:
            raise ProbeError('compat_plan_invalid')

    def query(self, args):
        result = self.command(args, 5)
        raw = result.stdout + result.stderr
        if b'AuthorizationCreate()' in raw or b'not authorized' in raw.lower():
            raise ProbeError('preflight_system_authorization_unavailable')
        if result.returncode or len(raw) > 65536 or result.stderr.strip():
            raise ProbeError('preflight_query_failed')
        try:
            return result.stdout.decode('utf-8')
        except UnicodeError:
            raise ProbeError('preflight_query_failed') from None

    def snapshot(self):
        return collect_baseline(run=self.query, port_check=None)

    def proxy(self):
        return parse_proxy(self.query([NETWORKSETUP, '-getsecurewebproxy', self.plan['baseline']['active_service']]))

    def set_proxy(self, value):
        if value not in (APPLIED, self.plan['baseline']['https_proxy']):
            raise ProbeError('compat_proxy_scope_invalid')
        if value['Enabled'] != 'Yes' or value['Authenticated Proxy Enabled'] != '0':
            raise ProbeError('compat_proxy_scope_invalid')
        response = self.command([NETWORKSETUP, '-setsecurewebproxy', self.plan['baseline']['active_service'],
                                 value['Server'], value['Port'], 'off'], 30)
        if response.returncode or response.stdout.strip() or response.stderr.strip():
            raise ProbeError('compat_proxy_write_unverified')

    def verify(self, case, root=None, timeout=4, include_root=False):
        if case not in cases() or root not in (None, 'unconstrained', 'exact_dns_no_ip') or (include_root and root):
            raise ProbeError('compat_verify_scope_invalid')
        args = [anchor.SECURITY, 'verify-cert', '-v', '-L', '-R', 'offline', '-p', 'ssl', '-n', case['host']]
        if root:
            cert = self.directory / 'mitmproxy' / ('unconstrained-root.pem' if root == 'unconstrained' else PUBLIC[0])
            args.extend(['-N', '-r', str(cert)])
        else:
            args.extend(['-k', self.keychain])
        args.extend(['-c', str(self.directory / 'probes' / (case['id'] + '-leaf.pem'))])
        if include_root:
            args.extend(['-c', str(self.ca_file)])
        try:
            return classify_native(self.command(args, timeout))
        except ProbeError:
            return {'outcome': 'not_verified', 'reason': 'compat_native_verify_unavailable'}


class Window(SessionWindow):
    def __init__(self, parent_fd, deadline, **kwargs):
        super().__init__(parent_fd, deadline, seconds=180, **kwargs)

    def guard(self, seconds=5):
        self.check()
        if not operation_budget(self.started, self.wall_deadline, self.monotonic(), self.wall(), seconds):
            raise ProbeError('compat_cleanup_reserve_reached')
        return seconds

    def timeout(self, limit=4):
        return self.guard(limit)


def proxy_command(plan):
    return [str(ROOT / '.venv-capture/bin/python'), str(ROOT / '.venv-capture/bin/mitmdump'),
        '--mode', plan['mode'], '--listen-host', '127.0.0.1', '--listen-port', '8899',
        '--allow-hosts', r'^mp\.weixin\.qq\.com:443$', '--set', 'confdir=' + str(DIRECTORY / 'mitmproxy'),
        '--set', 'ssl_insecure=false', '--set', 'upstream_cert=false', '--set',
        'certs=' + TARGET + '=' + str(DIRECTORY / 'mitmproxy/target-key-chain.pem'),
        '--set', 'add_upstream_certs_to_client_chain=false', '--set', 'flow_detail=0',
        '--set', 'termlog_verbosity=error', '--set', 'command_history=false', '--set', 'strip_ech=false',
        '--set', 'liumo_compat=true', '-s', str(ADDON)]


def delete_keys(plan):
    removed = []
    for name in KEYS:
        path = DIRECTORY / 'mitmproxy' / name
        if not path.exists() and not path.is_symlink():
            removed.append(name)
        elif digest(path) == plan['keys'][name]:
            path.unlink()
            removed.append(name)
    return len(removed) == len(KEYS)


def stop_inline_group(pid, process=None):
    """C28 only: stop the owned proxy session and its one inherited Node child."""
    if type(pid) is not int or pid <= 1:
        return False
    if process is not None and process.poll() is not None:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            pass
        return False  # Reaped parent: do not signal an unidentifiable/reused group.
    try:
        if os.getpgid(pid) != pid:
            return False
        os.killpg(pid, signal.SIGTERM)
        if process is not None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        until = time.monotonic() + 2
        while time.monotonic() < until:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(.05)
        os.killpg(pid, signal.SIGKILL)
        if process is not None:
            process.wait(timeout=1)
        until = time.monotonic() + 1
        while time.monotonic() < until:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(.05)
    except ProcessLookupError:
        # A missing parent does not prove its inherited group is absent.
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            pass
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def stop_process(process, plan, state):
    inline = WORKER_FLAG == '--html-inline-worker'
    if process is not None:
        if inline:
            return stop_inline_group(process.pid, process)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        return process.poll() is not None
    pid = state.get('proxy_pid')
    if pid is None:
        return not state.get('proxy_start_attempted')
    if type(pid) is not int or pid <= 1:
        return False
    result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'uid=', '-o', 'command='],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=2)
    if result.returncode == 1 and not result.stdout.strip():
        if inline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return True
            return False
        return True
    # Never signal a reused PID or an unidentifiable process.
    expected = (str(os.getuid()) + ' ' + ' '.join(proxy_command(plan))).encode()
    if result.returncode or b' '.join(result.stdout.split()) != expected:
        return False
    if inline:
        return stop_inline_group(pid)
    os.kill(pid, signal.SIGTERM)
    until = time.monotonic() + 1
    while time.monotonic() < until:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(.05)
    return False


def recover(native, state, save, process=None):
    """Every stage runs even if a previous stage or journal write failed."""
    def record():
        try:
            save(state)
        except Exception:
            state['journal_write_failed'] = True
    state.update(capture_disabled=True, status='recovering')
    record()
    result = {'proxy_verified': not state.get('proxy_attempted'), 'safe_to_stop': not state.get('proxy_attempted')}
    try:
        if state.get('proxy_attempted'):
            current = native.proxy()
            if current == APPLIED:
                native.set_proxy(native.plan['baseline']['https_proxy'])
                current = native.proxy()
            result['proxy_verified'] = current == native.plan['baseline']['https_proxy']
            result['safe_to_stop'] = not (current.get('Enabled') == 'Yes' and current.get('Server') == '127.0.0.1'
                                           and current.get('Port') == '8899')
    except Exception:
        result.update(proxy_verified=False, safe_to_stop=False)
    try:
        result['trust'] = native.revoke() if state.get('trust_attempted') else {'verified': True, 'unchanged': True}
    except Exception:
        result['trust'] = {'verified': False}
    try:
        result['process_stopped'] = bool(result['safe_to_stop'] and stop_process(process, native.plan, state))
    except Exception:
        result['process_stopped'] = False
    try:
        result['keys_removed'] = bool(result['process_stopped'] and delete_keys(native.plan))
    except Exception:
        result['keys_removed'] = False
    result['verified'] = bool(result['proxy_verified'] and result['trust']['verified'] and
                              result['process_stopped'] and result['keys_removed'])
    state.update(recovery=result, finished=True, recovery_completed_at=timestamp(),
                 status='closed' if result['verified'] else 'manual_recovery_required')
    record()
    return result


def evaluate(native, state, save, window, start_proxy):
    # Reuse the proven C15 34 explicit, 17 preinstall, 17 installed scope gates.
    window.guard(5)
    if not same_configuration(native.plan['baseline'], native.snapshot()):
        raise ProbeError('compat_configuration_changed')
    anchor.evaluate(native, state, save, window)
    window.guard(5)
    for name in KEYS:
        if digest(DIRECTORY / 'mitmproxy' / name) != native.plan['keys'][name]:
            raise ProbeError('compat_key_identity_changed')
    state['proxy_start_attempted'] = True
    save(state)
    process = start_proxy()
    state['proxy_pid'] = process.pid
    save(state)
    until = time.monotonic() + 3
    while not (DIRECTORY / 'capture.json').exists():
        window.guard(5)
        if process.poll() is not None or time.monotonic() >= until:
            raise ProbeError('compat_proxy_not_ready')
        time.sleep(.1)
    window.guard(30)
    state.update(proxy_attempted=True)
    save(state)
    native.set_proxy(APPLIED)
    window.guard(5)
    if native.proxy() != APPLIED:
        raise ProbeError('compat_proxy_readback_failed')
    window.guard(28)
    state.update(status='diagnostic_control_pending')
    save(state)
    verify_diagnostic_control(DIRECTORY, state, save, lambda: window.guard(1), native.plan['active_deadline'])
    window.guard(8)
    state.update(status=READY_STATUS)
    save(state)
    while not (DIRECTORY / 'FINISH').exists():
        window.guard(5)
        if process.poll() is not None or native.proxy() != APPLIED:
            raise ProbeError('compat_proxy_stopped_or_changed')
        time.sleep(.2)
    state['reason'] = 'compat_observation_finished'


def worker():
    os.umask(0o077)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    def terminate(_signum, _frame):
        raise ProbeError('compat_worker_cancelled')
    signal.signal(signal.SIGTERM, terminate)
    with locks():
        plan = load_plan()
        state = {'status': 'starting', 'finished': False, 'capture_disabled': False,
                 'at': timestamp(), 'credentials_collected': False}
        save = lambda value: private_write(DIRECTORY / 'state.json', value)
        native = Native(DIRECTORY, plan)
        window = Window(sys.stdin.fileno(), plan['wall_deadline'])
        process = None
        def start_proxy():
            nonlocal process
            clean = {k: v for k, v in os.environ.items() if k.upper() not in {
                'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSLKEYLOGFILE', 'MITMPROXY_SSLKEYLOGFILE'}}
            process = subprocess.Popen(proxy_command(plan), cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean, start_new_session=True)
            return process
        try:
            save(state)
            evaluate(native, state, save, window, start_proxy)
        except ProbeError as exc:
            state['reason'] = exc.reason
        except BaseException:
            state['reason'] = 'compat_worker_failed'
        finally:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            recover(native, state, save, process)
            state['worker_elapsed_seconds'] = round(time.monotonic() - window.started, 3)
            state['within_total_window'] = window.monotonic() - window.started <= 180 and window.wall() <= plan['wall_deadline']
            try:
                if (DIRECTORY / 'capture.json').exists():
                    state['capture'] = private_json(DIRECTORY / 'capture.json')
                    if EXPERIMENT == 'article_functional':
                        state['credentials_collected'] = state['capture'].get('saved_by_account', {}).get('猫笔刀') == 1
                    elif EXPERIMENT in ('comment_baseline', 'comment_refresh'):
                        state['comment_baseline_observed'] = state['capture'].get('success_baseline_saved') is True
                    elif EXPERIMENT == 'article_static':
                        state['static_summary_saved'] = state['capture'].get('static_summary_saved') is True
                save(state)
            except Exception:
                pass


def session():
    if DIRECTORY.exists() or DIRECTORY.is_symlink():
        raise ProbeError('compat_session_already_exists')
    previous_closed()
    for node in (ROOT / '.auth', DIRECTORY.parent):
        check_private(node)
    # Read-only failure here leaves no CA, listener, or consumed one-use directory.
    baseline = collect_baseline()
    mode = upstream_mode(baseline)
    ready = private_json(UI_READY)
    if (ready.get('target') != 'maobidao_fixed_article' or type(ready.get('at')) not in (int, float)
            or not 0 <= time.time() - ready['at'] <= 300):
        raise ProbeError('compat_UI_confirmation_required')
    os.umask(0o077)
    base = ROOT / '.tmp/wechat-session-validation'
    with tempfile.TemporaryDirectory(dir=base, prefix='compat-preflight-') as raw:
        temporary = Path(raw)
        identity = generate(temporary)
        control = Native(temporary, identity).verify(cases()[0], 'unconstrained')
        if control['outcome'] != 'accepted':
            output = new_run('wechat-compat-preflight')
            write_json(output / 'preflight.json', {'at': timestamp(), 'status': 'blocked', 'control': control,
                'experiment_created': False, 'system_trust_changed': False, 'WeChat_verified': False})
            return {'status': 'blocked', 'reason': 'compat_explicit_preflight_failed', 'output': str(output)}
        DIRECTORY.mkdir(mode=0o700)
        # Files generated by this invocation only. Rename stays on the same project volume.
        for name in ('mitmproxy', 'probes'):
            (temporary / name).rename(DIRECTORY / name)
    now = time.time()
    plan = {'version': 1, 'experiment': EXPERIMENT, 'baseline': baseline, 'mode': mode,
            'duration_seconds': 180, 'cleanup_reserve_seconds': 120,
            'wall_deadline': now + 180, 'active_deadline': now + 60, **identity}
    private_write(DIRECTORY / 'plan.json', plan)
    child = subprocess.Popen([str(ROOT / '.venv-capture/bin/python'), '-m', 'validation.compat_session', WORKER_FLAG],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)
    print('主人，单次明确刷新对照已启动；如有 macOS 认证请完成，暂勿刷新。控制通过时会提示点击文章标题右侧的圆形刷新箭头一次。'
          if EXPERIMENT in ('comment_refresh', 'article_static') else
          '主人，单次评论基线实验已启动；如有 macOS 认证请完成，暂勿刷新。Agent 将在控制通过后刷新并滚动至留言区。'
          if EXPERIMENT == 'comment_baseline' else
          '主人，单次文章实验已启动；如有 macOS 认证请完成，暂勿刷新。Agent 将在控制通过后刷新一次。', flush=True)
    last = None
    try:
        while child.poll() is None:
            if (DIRECTORY / 'state.json').exists():
                state = private_json(DIRECTORY / 'state.json')
                status = state.get('status')
                if status != last:
                    print(status, flush=True)
                    if EXPERIMENT in ('comment_refresh', 'article_static') and status == READY_STATUS:
                        print('主人，控制已通过。请点击固定猫笔刀文章标题右侧的圆形刷新箭头一次，随后保持文章前置，回复「已刷新」；不要再次刷新。', flush=True)
                    last = status
            if time.time() > plan['wall_deadline'] + 5:
                break
            time.sleep(.2)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        child.stdin.close()  # Independent worker detects EOF and performs recovery.
    if child.poll() is None:
        return {'status': 'blocked', 'reason': 'compat_cleanup_pending', 'private_session': str(DIRECTORY)}
    state = private_json(DIRECTORY / 'state.json')
    output = new_run(RUN_SLUG)
    write_json(output / 'session-summary.json', state)
    return {'status': 'partial' if state.get('recovery', {}).get('verified') else 'blocked',
            'output': str(output), 'reason': state.get('reason'), 'recovery': state.get('recovery'),
            'WeChat_verified': False}


def manual_recover():
    plan = load_plan()
    with locks():
        path = DIRECTORY / 'state.json'
        state = private_json(path) if path.exists() else {'trust_attempted': True, 'proxy_attempted': True,
                                                        'proxy_start_attempted': True}
        if state.get('finished') and state.get('recovery', {}).get('verified'):
            return {'status': 'already_closed_no_changes', 'current_system_state_rechecked': False}
        result = recover(Native(DIRECTORY, plan), state, lambda value: private_write(path, value))
        return {'status': 'recovered' if result['verified'] else 'blocked', 'recovery': result}


def observe(phase):
    from .transport_diagnostic import OBSERVATION_COUNTERS, control_verified
    if phase not in ('before_refresh', 'after_refresh'):
        raise ProbeError('compat_observation_phase_invalid')
    plan = load_plan()
    state, capture = (private_json(DIRECTORY / n) for n in ('state.json', 'capture.json'))
    remaining = plan['active_deadline'] - time.time()
    if (not 0 < remaining <= 60 or state.get('status') != READY_STATUS
            or state.get('finished') is not False or state.get('capture_disabled') is not False
            or capture.get('running') is not True or capture.get('status') != 'open'
            or capture.get('passthrough_only') is not False):
        raise ProbeError('compat_observation_not_running')
    counters = {k: capture.get('diagnostics', {}).get(k, 0) for k in sorted(OBSERVATION_COUNTERS)}
    if any(type(v) is not int or not 0 <= v <= 10**9 for v in counters.values()):
        raise ProbeError('compat_counters_invalid')
    if not control_verified(state.get('diagnostic_control', {}), counters):
        raise ProbeError('diagnostic_control_unverified')
    result = {'phase': phase, 'at': timestamp(), 'seconds_remaining': round(remaining, 3), 'counters': counters,
              'UI_refresh_verified_by_snapshot': False}
    private_write(DIRECTORY / (phase + '.json'), result)
    return result


def finish():
    observe('after_refresh')
    fd = os.open(DIRECTORY / 'FINISH', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    return {'status': 'cleanup_requested'}


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--functional-worker']:
    # -m runs this file as __main__; make the addon selector bind this instance.
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .functional_capture import select_runtime
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--comment-baseline-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .comment_baseline import authorized, select_runtime
    authorized()
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--comment-refresh-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .comment_baseline import authorized, select_refresh_mode, select_runtime
    select_refresh_mode()
    authorized()
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--html-static-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .html_static_session import authorized, select_runtime
    authorized()
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--html-static-metadata-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .html_static_session import authorized, select_metadata_mode, select_runtime
    select_metadata_mode()
    authorized()
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--html-static-duplicates-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .html_static_session import authorized, select_duplicate_mode, select_runtime
    select_duplicate_mode()
    authorized()
    select_runtime()
    worker()
elif __name__ == '__main__' and sys.argv[1:] == ['--html-inline-worker']:
    sys.modules['validation.compat_session'] = sys.modules[__name__]
    from .html_static_session import authorized, select_inline_mode, select_runtime
    select_inline_mode()
    authorized()
    select_runtime()
    worker()
