"""One authorized terminal experiment; independent worker owns all mutations.

The worker checks its parent's pipe and both wall/monotonic deadlines. This is
not an installed service and cannot protect against its own SIGKILL or power
loss. A separate recovery entry reads only this experiment's private journal.
"""

import fcntl
import hashlib
from contextlib import contextmanager
import fnmatch
import json
import math
import os
import select
import signal
import stat
import ssl
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .capture_preflight import NETWORKSETUP, collect_baseline, parse_proxy, query
from .common import ROOT, timestamp, new_run, write_json
from .credentials import check_private
from .http import ProbeError

SESSION = ROOT / ".auth/wechat-capture/session"
ARTICLE_SESSION = SESSION
PROFILE_SESSION = ROOT / ".auth/wechat-capture/profile-session"
DIAGNOSTIC_SESSION = ROOT / ".auth/wechat-capture/diagnostic-session"
UI_DIAGNOSTIC_SESSION = ROOT / ".auth/wechat-capture/ui-diagnostic-session"
ARTICLE_DIAGNOSTIC_SESSION = ROOT / ".auth/wechat-capture/article-diagnostic-session"
DIAGNOSTIC_MODES = {"diagnostic", "ui_diagnostic", "article_diagnostic"}
SECURITY = "/usr/bin/security"
TARGET_HOST = "mp.weixin.qq.com"
OTHER_HOST = "liumo-scope-check.invalid"
APPLIED = {"Enabled": "Yes", "Server": "127.0.0.1", "Port": "8899", "Authenticated Proxy Enabled": "0"}


def private_json(path):
    path = Path(path)
    check_private(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ProbeError("session_file_invalid")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, encoding="utf-8") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077):
            raise ProbeError("session_file_invalid")
        value = stream.read(131073)
    if len(value) > 131072:
        raise ProbeError("session_file_invalid")
    return json.loads(value)


def private_write(path, data):
    check_private(path.parent)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class SessionWindow:
    def __init__(self, parent_fd, wall_deadline, monotonic=time.monotonic, wall=time.time, seconds=600):
        self.parent_fd, self.wall_deadline = parent_fd, wall_deadline
        self.seconds = seconds
        self.monotonic, self.wall = monotonic, wall
        self.started = monotonic()

    def check(self):
        if self.monotonic() - self.started >= self.seconds or self.wall() >= self.wall_deadline:
            raise ProbeError("session_window_expired")
        if select.select([self.parent_fd], [], [], 0)[0]:
            os.read(self.parent_fd, 64)
            raise ProbeError("session_parent_closed_or_cancelled")


def upstream_mode(baseline):
    proxy = baseline["https_proxy"]
    if (proxy["Enabled"] != "Yes" or proxy["Server"] not in {"127.0.0.1", "localhost"}
            or proxy["Authenticated Proxy Enabled"] != "0" or baseline["http_proxy"] != proxy
            or not 1 <= int(proxy["Port"]) <= 65535 or proxy["Port"] == "8899"
            or baseline["pac"]["Enabled"] != "No" or baseline["autodiscovery"] != "Auto Proxy Discovery: Off"
            or baseline["review_reasons"]):
        raise ProbeError("session_baseline_not_supported")
    if any(fnmatch.fnmatch(TARGET_HOST, item) for item in baseline["bypass_domains"]):
        raise ProbeError("session_target_bypasses_proxy")
    return "upstream:http://" + proxy["Server"] + ":" + proxy["Port"]


def runtime_plan(directory=None):
    directory = SESSION if directory is None else Path(directory)
    for node in (ROOT / ".auth", directory.parent, directory):
        check_private(node)
    plan = private_json(directory / "plan.json")
    experiment = plan.get("experiment", "article")
    if (plan.get("version") != 1 or plan["mode"] != upstream_mode(plan["baseline"])
            or experiment not in {"article", "profile", *DIAGNOSTIC_MODES}
            or plan.get("duration_seconds", 600) != (120 if experiment in DIAGNOSTIC_MODES else 600)
            or type(plan.get("wall_deadline")) not in (int, float) or not math.isfinite(plan["wall_deadline"])):
        raise ProbeError("session_plan_invalid")
    return plan


def recovery_entry(plan):
    return {"profile": "profile-capture-recover", "diagnostic": "transport-diagnostic-recover",
            "ui_diagnostic": "ui-transport-diagnostic-recover",
            "article_diagnostic": "article-transport-diagnostic-recover"}.get(
        plan.get("experiment"), "capture-recover")


def same_configuration(first, second):
    keys = ("active_service", "interface", "https_proxy", "http_proxy", "pac", "autodiscovery", "bypass_domains")
    return all(first[key] == second[key] for key in keys)


class Native:
    def __init__(self, plan, directory=None):
        self.plan, self.directory = plan, SESSION if directory is None else directory
        self.service = plan["baseline"]["active_service"]
        self.keychain = str(Path.home() / "Library/Keychains/login.keychain-db")

    def command(self, args, allowed=(0,), timeout=30):
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise ProbeError("session_native_command_failed") from None
        if result.returncode not in allowed:
            raise ProbeError("session_native_command_rejected", result.returncode)
        return result.returncode

    def snapshot(self):
        return collect_baseline(port_check=None)

    def proxy(self):
        return parse_proxy(query([NETWORKSETUP, "-getsecurewebproxy", self.service]))

    def set_proxy(self, value):
        # This experiment supports an already enabled, unauthenticated proxy.
        if value["Enabled"] != "Yes" or value["Authenticated Proxy Enabled"] != "0":
            raise ProbeError("session_restore_shape_unsupported")
        self.command([NETWORKSETUP, "-setsecurewebproxy", self.service, value["Server"], value["Port"], "off"])
        if self.proxy() != value:
            raise ProbeError("session_proxy_readback_failed")

    def prepare_ca(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from mitmproxy.certs import CertStore
        confdir = self.directory / "mitmproxy"
        confdir.mkdir(mode=0o700)
        CertStore.create_store(confdir, "mitmproxy", 2048, organization="liumo experiment", cn=self.plan["ca_name"])
        store = CertStore.from_store(confdir, "mitmproxy", 2048)
        probe = store.get_cert(TARGET_HOST, [x509.DNSName(TARGET_HOST), x509.DNSName(OTHER_HOST)])
        (self.directory / "scope-probe.pem").write_bytes(probe.cert.to_pem())
        fingerprint = store.default_ca._cert.fingerprint(hashes.SHA256()).hex().upper()
        original = self.plan["baseline"]["https_proxy"]
        private_write(self.directory / "recovery-plan.json", {
            "at": timestamp(), "certificate_sha256": fingerprint,
            "recommended_entry": [str(ROOT / ".venv/bin/python"), "-m", "validation",
                                  recovery_entry(self.plan)],
            "only_restore_proxy_if_current_equals": APPLIED,
            "restore_proxy_argv": [NETWORKSETUP, "-setsecurewebproxy", self.service, original["Server"], original["Port"], "off"],
            "remove_only_this_user_trust_argv": [SECURITY, "remove-trusted-cert", str(confdir / "mitmproxy-ca-cert.pem")],
            "delete_only_this_new_certificate_argv": [SECURITY, "delete-certificate", "-Z", fingerprint, "-t", self.keychain],
            "notice": "优先使用恢复入口；独立命令须先核对当前状态，不覆盖并行修改。"})
        return fingerprint

    def verify(self, host):
        return self.command([SECURITY, "verify-cert", "-q", "-L", "-p", "ssl", "-n", host,
                             "-c", str(self.directory / "scope-probe.pem"),
                             "-c", str(self.directory / "mitmproxy/mitmproxy-ca-cert.pem")], allowed=tuple(range(256))) == 0

    def trust(self):
        ca = str(self.directory / "mitmproxy/mitmproxy-ca-cert.pem")
        self.command([SECURITY, "add-trusted-cert", "-r", "trustRoot", "-p", "ssl", "-s", TARGET_HOST,
                      "-k", self.keychain, ca], timeout=45)

    def certificate_present(self, fingerprint):
        result = subprocess.run([SECURITY, "find-certificate", "-c", self.plan["ca_name"], "-Z", self.keychain],
                                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10)
        if result.returncode == 44 and not result.stdout:
            return False
        if result.returncode == 0 and fingerprint in result.stdout:
            return True
        raise ProbeError("session_certificate_baseline_unknown")

    def untrust(self, fingerprint):
        ca = str(self.directory / "mitmproxy/mitmproxy-ca-cert.pem")
        check_private(Path(ca))
        certificate = Path(ca).read_text()
        if len(certificate) > 16384 or hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest().upper() != fingerprint:
            raise ProbeError("session_certificate_identity_mismatch")
        # Deleting our uniquely generated certificate with -t also removes its
        # user trust settings; attempt explicit revocation first for clarity.
        try:
            self.command([SECURITY, "remove-trusted-cert", ca])
        except ProbeError:
            pass
        self.command([SECURITY, "delete-certificate", "-Z", fingerprint, "-t", self.keychain], allowed=(0, 44))
        if self.verify(TARGET_HOST) or self.certificate_present(fingerprint):
            raise ProbeError("session_trust_revoke_unverified")


def recover(native, journal, save):
    """Compare current values, restore only our endpoint; never overwrite others."""
    result = {"proxy": "unchanged", "trust": "unchanged", "safe_to_stop_proxy": True}
    def record():
        try:
            save(journal)
        except Exception:
            journal["journal_write_failed"] = True
    journal["capture_disabled"] = True
    record()
    try:
        if journal.get("proxy_attempted"):
            current = native.proxy()
            original = native.plan["baseline"]["https_proxy"]
            if current == APPLIED:
                native.set_proxy(original)
                result["proxy"] = "restored_and_read_back"
            elif current == original:
                result["proxy"] = "already_original"
            else:
                result["proxy"] = "external_change_preserved"
                result["safe_to_stop_proxy"] = not (current["Enabled"] == "Yes" and
                    current["Server"] == APPLIED["Server"] and current["Port"] == APPLIED["Port"])
    except Exception:
        result.update(proxy="recovery_failed", safe_to_stop_proxy=False)
    # If routing is still ours, keep the listener alive; disable collection now.
    try:
        if journal.get("trust_attempted"):
            native.untrust(journal["ca_fingerprint"])
            result["trust"] = "revoked_and_checked"
    except Exception:
        result["trust"] = "revoke_failed"
    result["verified"] = result["proxy"] in {"unchanged", "restored_and_read_back", "already_original"} and result["trust"] in {"unchanged", "revoked_and_checked"}
    journal["recovery"] = result
    journal["finished"] = True
    journal["status"] = "restored" if result["verified"] else "manual_recovery_required"
    record()
    return result


def setup(native, journal, save, checkpoint, start_proxy):
    original = native.plan["baseline"]
    if not same_configuration(original, native.snapshot()):
        raise ProbeError("session_configuration_changed_since_preflight")
    journal["ca_fingerprint"] = native.prepare_ca()
    save(journal)
    if (native.certificate_present(journal["ca_fingerprint"]) or native.verify(TARGET_HOST)
            or native.verify(OTHER_HOST)):
        raise ProbeError("session_CA_unexpectedly_trusted_before_experiment")
    checkpoint()
    journal.update(trust_attempted=True, status="certificate_trust_requested")
    save(journal)
    native.trust()
    if not native.verify(TARGET_HOST) or native.verify(OTHER_HOST):
        raise ProbeError("session_hostname_trust_scope_failed")
    journal["trust_scope_verified"] = True
    save(journal)
    checkpoint()
    proxy = start_proxy()
    checkpoint()
    journal.update(proxy_attempted=True, status="proxy_roundtrip_trial")
    save(journal)
    native.set_proxy(APPLIED)
    native.set_proxy(original["https_proxy"])
    if not same_configuration(original, native.snapshot()):
        raise ProbeError("session_roundtrip_not_exact")
    journal["proxy_roundtrip_verified"] = True
    save(journal)
    checkpoint()
    native.set_proxy(APPLIED)
    journal["status"] = ("diagnostic_control_pending" if native.plan.get("experiment") in DIAGNOSTIC_MODES else
                         "ready_open_two_samples_in_mac_wechat")
    save(journal)
    return proxy


def _worker():
    os.umask(0o077)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    def terminate(_number, _frame):
        raise ProbeError("session_worker_terminated")
    signal.signal(signal.SIGTERM, terminate)
    plan = runtime_plan()
    journal = {"at": timestamp(), "status": "starting", "capture_disabled": False, "finished": False}
    save = lambda data: private_write(SESSION / "state.json", data)
    native = Native(plan)
    process = None
    checkpoint = SessionWindow(sys.stdin.fileno(), plan["wall_deadline"], seconds=plan.get("duration_seconds", 600)).check
    def start_proxy():
        nonlocal process
        from .capture_plan import review_plan
        command = review_plan()["proposed_command_not_executed"]
        command[command.index("--mode") + 1] = plan["mode"]
        command = ["confdir=" + str(SESSION / "mitmproxy") if arg.startswith("confdir=") else arg for arg in command]
        if plan.get("experiment") == "profile":
            command.extend(["--set", "liumo_profile_capture=true"])
        if plan.get("experiment") in DIAGNOSTIC_MODES:
            command = ["liumo_capture_seconds=120" if arg == "liumo_capture_seconds=600" else arg for arg in command]
            command.extend(["--set", "liumo_diagnostic_only=true"])
            if plan.get("experiment") == "ui_diagnostic":
                command.extend(["--set", "liumo_ui_diagnostic=true"])
            if plan.get("experiment") == "article_diagnostic":
                command.extend(["--set", "liumo_article_diagnostic=true"])
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in {"SSLKEYLOGFILE", "MITMPROXY_SSLKEYLOGFILE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, close_fds=True, env=environment)
        until = time.monotonic() + 12
        while time.monotonic() < until:
            checkpoint()
            if process.poll() is not None:
                raise ProbeError("session_proxy_start_failed")
            if (SESSION / "capture.json").exists() and private_json(SESSION / "capture.json").get("running"):
                import socket
                try:
                    with socket.create_connection(("127.0.0.1", 8899), timeout=0.5):
                        return process
                except OSError:
                    pass
            time.sleep(0.2)
        raise ProbeError("session_proxy_not_ready")
    save(journal)
    try:
        setup(native, journal, save, checkpoint, start_proxy)
        if plan.get("experiment") in DIAGNOSTIC_MODES:
            verify_diagnostic_control(SESSION, journal, save, checkpoint, plan["wall_deadline"])
            journal["status"] = ("ready_refresh_maobidao_article_for_diagnostics"
                                 if plan.get("experiment") == "article_diagnostic"
                                 else "ready_refresh_maobidao_for_diagnostics")
            save(journal)
        if plan.get("experiment") == "profile":
            journal["status"] = "ready_open_two_profiles_in_mac_wechat"
            save(journal)
        last_proxy_check = time.monotonic()
        while True:
            checkpoint()
            if process.poll() is not None:
                raise ProbeError("session_proxy_exited")
            if time.monotonic() - last_proxy_check >= 5:
                if native.proxy() != APPLIED:
                    raise ProbeError("session_proxy_changed_during_capture")
                last_proxy_check = time.monotonic()
            capture = private_json(SESSION / "capture.json")
            journal["capture"] = capture
            save(journal)
            if plan.get("experiment") in DIAGNOSTIC_MODES:
                time.sleep(0.5)
                continue
            if plan.get("experiment") == "profile":
                probe_new_profiles(SESSION, journal, checkpoint, plan["wall_deadline"])
                save(journal)
                if len(journal.get("profile_probe_results", {})) == 2:
                    journal["reason"] = "two_profile_probes_finished_not_full_acceptance"
                    break
                if any(capture.get("events", {}).get(reason) for reason in
                       {"profile_capture_store_failed", "profile_capture_existing_file"}):
                    raise ProbeError("session_profile_storage_refused")
                time.sleep(0.5)
                continue
            fatal = {"capture_store_failed", "credential_existing_file_not_managed", "credential_permissions_rejected",
                     "credential_symlink_rejected", "credential_store_busy", "credential_capture_out_of_order"}
            if any(capture.get("events", {}).get(reason) for reason in fatal):
                raise ProbeError("session_credential_storage_refused")
            if all(capture.get("saved_by_account", {}).get(name, 0) for name in ("猫笔刀", "stormzhang")):
                journal["reason"] = "two_credentials_saved_authentication_unverified"
                break
            time.sleep(0.5)
    except ProbeError as exc:
        journal["reason"] = exc.reason
        if exc.code is not None:
            journal["error_code"] = exc.code
    except BaseException:
        journal["reason"] = "session_failed"
    finally:
        recovery = recover(native, journal, save)
        if recovery["safe_to_stop_proxy"]:
            try:
                (SESSION / "STOP").touch(mode=0o600, exist_ok=True)
            except OSError:
                pass
            if process is not None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        journal["proxy_process_stopped"] = process is None or process.poll() is not None
        try:
            if (SESSION / "capture.json").exists():
                journal["capture"] = private_json(SESSION / "capture.json")
            save(journal)
        except Exception:
            pass  # A failed journal must never prevent system cleanup.


def session(baseline_path, profile=False, diagnostic=False, ui=False, article_control=False):
    """Invoked by the user in a normal terminal; no shell command interpolation."""
    if not sys.stdin.isatty():
        raise ProbeError("session_requires_normal_terminal")
    if (profile and diagnostic) or ((ui or article_control) and not diagnostic) or (ui and article_control):
        raise ProbeError("session_experiment_conflict")
    baseline_path = Path(baseline_path)
    if baseline_path.parent != SESSION.parent / "baselines":
        raise ProbeError("session_baseline_path_rejected")
    baseline = private_json(baseline_path)
    mode = upstream_mode(baseline)
    if not same_configuration(baseline, collect_baseline()):
        raise ProbeError("session_configuration_changed_since_preflight")
    for node in (ROOT / ".auth", SESSION.parent):
        check_private(node)
    SESSION.mkdir(mode=0o700)  # One use only; never overwrite a prior experiment.
    duration = 120 if diagnostic else 600
    plan = {"version": 1, "baseline": baseline, "mode": mode,
            "wall_deadline": time.time() + duration, "ca_name": "liumo-" + uuid.uuid4().hex}
    if diagnostic:
        plan.update(experiment="article_diagnostic" if article_control else "ui_diagnostic" if ui else "diagnostic", duration_seconds=120)
    if profile:
        plan["experiment"] = "profile"
        (SESSION / "requests").mkdir(mode=0o700)
    private_write(SESSION / "plan.json", plan)
    worker_python = ROOT / ".venv-capture/bin/python"
    child = subprocess.Popen([str(worker_python), "-m", "validation.capture_session",
                              "--article-diagnostic-worker" if article_control else "--ui-diagnostic-worker" if ui else "--diagnostic-worker" if diagnostic else "--profile-worker" if profile else "--worker"], cwd=ROOT,
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, close_fds=True)
    printed = None
    announced = set()
    try:
        while child.poll() is None:
            state = private_json(SESSION / "state.json") if (SESSION / "state.json").exists() else {"status": "starting"}
            if state["status"] != printed:
                messages = {"starting": "正在核对配置与准备本次证书。", "certificate_trust_requested": "正在请求本次限定主机的证书信任；系统认证请由你完成。",
                    "proxy_roundtrip_trial": "正在验证代理设置能否准确恢复。", "ready_open_two_samples_in_mac_wechat": "采集就绪，请在 Mac 微信中正常打开下面两篇样本。最多 10 分钟，Ctrl+C 可停止并恢复。",
                    "ready_open_two_profiles_in_mac_wechat": "采集就绪，请在 Mac 微信中分别正常打开猫笔刀、stormzhang 的公众号主页和文章列表。无需手抄参数或按 Enter；最多 10 分钟，Ctrl+C 可停止并恢复。",
                    "diagnostic_control_pending": "正在核对一次无凭证控制请求；请先不要刷新页面。",
                    "ready_refresh_maobidao_article_for_diagnostics": "控制请求与代理观测均通过。等待 Agent 对猫笔刀固定样本文章记录前后取样并刷新一次；请保持终端运行，不需人工刷新。总窗口最多 2 分钟。",
                    "ready_refresh_maobidao_for_diagnostics": "控制请求与代理观测均通过。请只在 Mac 微信刷新猫笔刀主页一次，终端保持运行；无需复制链接、参数或按 Enter。诊断窗口总计最多 2 分钟。",
                    "restored": "本次代理改动与证书信任恢复检查通过。", "manual_recovery_required": "自动恢复未通过，请保持窗口并使用恢复入口，结果尚未完成。"}
                if profile and state["status"] == "ready_open_two_samples_in_mac_wechat":
                    messages[state["status"]] = messages["ready_open_two_profiles_in_mac_wechat"]
                if ui and state["status"] == "ready_refresh_maobidao_for_diagnostics":
                    messages[state["status"]] = "控制请求与代理观测均通过。等待 Agent 记录前后样本并刷新右侧猫笔刀主页；请保持终端运行，不需人工刷新。总窗口最多 2 分钟。"
                print("主人，" + messages.get(state["status"], "正在处理实验状态。"), flush=True)
                if not profile and state["status"] == "ready_open_two_samples_in_mac_wechat":
                    from .common import SAMPLES
                    for address in SAMPLES.values():
                        print(address, flush=True)
                if state["status"] == "manual_recovery_required":
                    print("cd " + str(ROOT) + " && .venv/bin/python -m validation " +
                          recovery_entry(plan), flush=True)
                printed = state["status"]
            if profile:
                for account, row in state.get("profile_probe_results", {}).items():
                    if account not in announced and row.get("reason") != "profile_probe_started":
                        print("主人，公众号“" + account + "”的一次即时核对已结束；状态为 " + row['status'] + "。", flush=True)
                        announced.add(account)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        child.stdin.close()  # EOF also triggers recovery when the terminal dies.
    try:
        child.wait(timeout=75)
    except subprocess.TimeoutExpired:
        return {"status": "blocked", "reason": "session_cleanup_still_pending", "private_session": str(SESSION)}
    state = private_json(SESSION / "state.json") if (SESSION / "state.json").exists() else {"status": "failed"}
    output = new_run("article-transport-diagnostic-session" if article_control else "ui-transport-diagnostic-session" if ui else "transport-diagnostic-session" if diagnostic else "profile-capture-session" if profile else "capture-session")
    write_json(output / "session-summary.json", state)
    source_results = []
    if not (profile or diagnostic) and state.get("recovery", {}).get("verified") and state.get("proxy_process_stopped"):
        source_results = validate_sources(state)
        write_json(output / "source-probes.json", {"at": timestamp(), "results": source_results})
    return {"output": str(output), "status": "partial" if state.get("recovery", {}).get("verified") else "blocked",
            "reason": state.get("reason", "session_no_result"), "recovery": state.get("recovery"),
            "source_probe_results": [{"account": item["account"], "status": item.get("status", "failed")} for item in source_results],
            "profile_probe_results": list(state.get("profile_probe_results", {}).values()),
            "diagnostic_control": state.get("diagnostic_control"),
            "authentication_verified": False}


def verify_diagnostic_control(directory, journal, save, checkpoint, deadline, probe=None):
    from .transport_diagnostic import control_probe, control_verified
    checkpoint()
    if time.time() + 28 >= deadline:
        raise ProbeError("session_window_expired")
    result = (control_probe if probe is None else probe)(directory)
    checkpoint()
    until = time.monotonic() + 2
    while True:
        counters = private_json(directory / "capture.json").get("diagnostics", {})
        if control_verified(result, counters) or time.monotonic() >= until or result.get("status") != "https_response_observed":
            break
        checkpoint()
        time.sleep(0.1)
    result["proxy_response_observed"] = control_verified(result, counters)
    journal["diagnostic_control"] = {**result, "counters_at_control_end": counters}
    save(journal)
    if not result["proxy_response_observed"]:
        raise ProbeError("diagnostic_control_unverified")


def probe_new_profiles(directory, journal, checkpoint, deadline, probe=None):
    """Each account is marked before its only probe; no replay after refusal."""
    from .credentials import ACCOUNTS
    from .profile_capture import probe_profile_snapshot
    probe = probe_profile_snapshot if probe is None else probe
    results = journal.setdefault("profile_probe_results", {})
    for account, slug in ACCOUNTS.items():
        path = directory / "requests" / (slug + "-getmsg.json")
        if account in results or not path.exists():
            continue
        checkpoint()
        if time.time() + 30 >= deadline:
            raise ProbeError("session_window_expired")
        results[account] = {"account": account, "status": "not_verified", "reason": "profile_probe_started"}
        private_write(directory / "state.json", journal)
        data = private_json(path)
        if data.get("account") != account:
            raise ProbeError("session_profile_input_scope_mismatch")
        time.sleep(2)
        checkpoint()
        results[account] = probe(data)


def select_profile_experiment():
    global SESSION
    SESSION = PROFILE_SESSION


def profile_session():
    """One newly authorized experiment, fresh baseline, old run preserved."""
    if not sys.stdin.isatty():
        raise ProbeError("session_requires_normal_terminal")
    if PROFILE_SESSION.exists() or PROFILE_SESSION.is_symlink():
        raise ProbeError("session_profile_already_exists")
    previous = private_json(ARTICLE_SESSION / "state.json")
    if not previous.get("recovery", {}).get("verified") or not previous.get("proxy_process_stopped"):
        raise ProbeError("session_previous_recovery_unverified")
    # Do not mutate or create an experiment until current preflight succeeds.
    baseline = collect_baseline()
    upstream_mode(baseline)
    from .capture_preflight import save_baseline
    path = save_baseline(baseline)
    select_profile_experiment()
    return session(path, profile=True)


def profile_manual_recover():
    select_profile_experiment()
    return manual_recover()


def select_diagnostic_experiment():
    global SESSION
    SESSION = DIAGNOSTIC_SESSION


def diagnostic_session():
    """Use only after explicit authorization for this new single experiment."""
    if not sys.stdin.isatty():
        raise ProbeError("session_requires_normal_terminal")
    if DIAGNOSTIC_SESSION.exists() or DIAGNOSTIC_SESSION.is_symlink():
        raise ProbeError("session_diagnostic_already_exists")
    for directory in (ARTICLE_SESSION, PROFILE_SESSION):
        state = private_json(directory / "state.json")
        if not state.get("recovery", {}).get("verified") or not state.get("proxy_process_stopped"):
            raise ProbeError("session_previous_recovery_unverified")
    baseline = collect_baseline()
    upstream_mode(baseline)
    from .capture_preflight import save_baseline
    path = save_baseline(baseline)
    select_diagnostic_experiment()
    return session(path, diagnostic=True)


def diagnostic_manual_recover():
    select_diagnostic_experiment()
    return manual_recover()


def select_ui_diagnostic_experiment():
    global SESSION
    SESSION = UI_DIAGNOSTIC_SESSION


def ui_diagnostic_session():
    """New single experiment only; never reuse the three completed directories."""
    if not sys.stdin.isatty():
        raise ProbeError("session_requires_normal_terminal")
    if UI_DIAGNOSTIC_SESSION.exists() or UI_DIAGNOSTIC_SESSION.is_symlink():
        raise ProbeError("session_ui_diagnostic_already_exists")
    for directory in (ARTICLE_SESSION, PROFILE_SESSION, DIAGNOSTIC_SESSION):
        state = private_json(directory / "state.json")
        if not state.get("recovery", {}).get("verified") or not state.get("proxy_process_stopped"):
            raise ProbeError("session_previous_recovery_unverified")
    baseline = collect_baseline()
    upstream_mode(baseline)
    from .capture_preflight import save_baseline
    path = save_baseline(baseline)
    select_ui_diagnostic_experiment()
    return session(path, diagnostic=True, ui=True)


def ui_diagnostic_manual_recover():
    select_ui_diagnostic_experiment()
    return manual_recover()


def select_article_diagnostic_experiment():
    global SESSION
    SESSION = ARTICLE_DIAGNOSTIC_SESSION


def article_diagnostic_session():
    """One article-page control; preserve all four completed experiments."""
    if not sys.stdin.isatty():
        raise ProbeError("session_requires_normal_terminal")
    if ARTICLE_DIAGNOSTIC_SESSION.exists() or ARTICLE_DIAGNOSTIC_SESSION.is_symlink():
        raise ProbeError("session_article_diagnostic_already_exists")
    for directory in (ARTICLE_SESSION, PROFILE_SESSION, DIAGNOSTIC_SESSION, UI_DIAGNOSTIC_SESSION):
        state = private_json(directory / "state.json")
        if not state.get("recovery", {}).get("verified") or not state.get("proxy_process_stopped"):
            raise ProbeError("session_previous_recovery_unverified")
    baseline = collect_baseline()
    upstream_mode(baseline)
    from .capture_preflight import save_baseline
    path = save_baseline(baseline)
    select_article_diagnostic_experiment()
    return session(path, diagnostic=True, article_control=True)


def article_diagnostic_manual_recover():
    select_article_diagnostic_experiment()
    return manual_recover()


def validate_sources(state, run=subprocess.run):
    """At most one bounded list probe per captured account, after restoration.

    The existing CLI reads private credentials itself; no secrets in argv. No
    anonymous body re-request or history-body download is performed here.
    """
    if not state.get("recovery", {}).get("verified") or not state.get("proxy_process_stopped"):
        return []
    results = []
    captured = state.get("capture", {}).get("saved_by_account", {})
    for account in ("猫笔刀", "stormzhang"):
        if not captured.get(account):
            continue
        print("主人，配置已恢复，正在核对公众号“" + account + "”的有限多篇列表。", flush=True)
        try:
            result = run([str(ROOT / ".venv/bin/python"), "-m", "validation", "mp-discover", "--account", account,
                          "--max-pages", "3"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, timeout=120)
            data = json.loads(result.stdout)
            if result.returncode not in (0, 2) or not isinstance(data, dict) or data.get("account") != account:
                raise ValueError()
            results.append({"account": account, **data})
        except KeyboardInterrupt:
            results.append({"account": account, "status": "cancelled"})
            break
        except Exception:
            results.append({"account": account, "status": "failed", "reason": "source_probe_no_valid_result"})
    return results


@contextmanager
def lifecycle_lock():
    check_private(SESSION)
    descriptor = os.open(SESSION / ".lifecycle.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as stream:
        check_private(SESSION / ".lifecycle.lock")
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProbeError("session_worker_still_owns_recovery") from None
        yield


def worker():
    runtime_plan()
    with lifecycle_lock():
        _worker()


def _manual_recover():
    plan = runtime_plan()
    journal = private_json(SESSION / "state.json")
    if journal.get("recovery", {}).get("verified") and journal.get("proxy_process_stopped"):
        return {"status": "already_closed_no_changes", "recorded_recovery": journal["recovery"],
                "current_system_state_rechecked": False}
    result = recover(Native(plan), journal, lambda data: private_write(SESSION / "state.json", data))
    if result["safe_to_stop_proxy"]:
        (SESSION / "STOP").touch(mode=0o600, exist_ok=True)
    return {"status": "recovered" if result["verified"] else "blocked", "recovery": result}


def manual_recover():
    runtime_plan()
    with lifecycle_lock():
        return _manual_recover()


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    worker()
elif __name__ == "__main__" and sys.argv[1:] == ["--profile-worker"]:
    select_profile_experiment()
    if runtime_plan().get("experiment") != "profile":
        raise ProbeError("session_plan_invalid")
    worker()
elif __name__ == "__main__" and sys.argv[1:] == ["--diagnostic-worker"]:
    select_diagnostic_experiment()
    if runtime_plan().get("experiment") != "diagnostic":
        raise ProbeError("session_plan_invalid")
    worker()
elif __name__ == "__main__" and sys.argv[1:] == ["--ui-diagnostic-worker"]:
    select_ui_diagnostic_experiment()
    if runtime_plan().get("experiment") != "ui_diagnostic":
        raise ProbeError("session_plan_invalid")
    worker()
elif __name__ == "__main__" and sys.argv[1:] == ["--article-diagnostic-worker"]:
    select_article_diagnostic_experiment()
    if runtime_plan().get("experiment") != "article_diagnostic":
        raise ProbeError("session_plan_invalid")
    worker()
