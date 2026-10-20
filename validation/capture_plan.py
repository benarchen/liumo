"""Generate a reviewable experiment; only the fixture command writes fake data."""

import json
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from .capture import CaptureSession, TARGETS
from .common import ROOT, new_run, timestamp, write_json
from .credentials import read_private_credentials, save_captured_credentials
from .http import ProbeError

ALLOW_HOST = r"^mp\.weixin\.qq\.com:443$"
PORT = 8899


def review_plan():
    executable = ROOT / ".venv-capture/bin/mitmdump"
    confdir = ROOT / ".auth/wechat-capture/mitmproxy"
    command = [str(executable), "--mode", "regular", "--listen-host", "127.0.0.1",
               "--listen-port", str(PORT), "--allow-hosts", ALLOW_HOST,
               "--set", "confdir=" + str(confdir), "--set", "ssl_insecure=false",
               "--set", "flow_detail=0", "--set", "termlog_verbosity=error",
               "--set", "show_ignored_hosts=false", "--set", "store_streamed_bodies=false",
               "--set", "command_history=false", "--set", "strip_ech=false",
               "-s", str(ROOT / "validation/mitm_addon.py"),
               "--set", "liumo_capture=true", "--set", "liumo_capture_seconds=600"]
    return {"at": timestamp(), "status": "prepared_not_running", "requires_explicit_authorization": True,
            "dependency_candidate": {"name": "mitmproxy", "version": "12.2.3", "installed": executable.exists()},
            "duration_seconds": 600, "listen_host": "127.0.0.1", "listen_port": PORT,
            "tls_target": "mp.weixin.qq.com:443", "targets": list(TARGETS.values()),
            "proposed_command_not_executed": command,
            "credential_output_directory": str(ROOT / ".auth/wechat"),
            "certificate_directory": str(confdir),
            "system_changes_requiring_authorization": ["temporary user certificate trust", "active service HTTPS proxy"],
            "preconditions": ["explicit user authorization", "complete readable proxy/trust baseline",
                              "exact rollback operations validated before changes", "supervisor and timed recovery ready",
                              "installed component options checked", "safe process output suppression"],
            "template_not_standalone": True,
            "single_use_driver": "capture-session --baseline PRIVATE_BASELINE_PATH",
            "restoration_helper": "capture-recover",
            "not_live_verified": ["system proxy/trust supervisor", "system recovery",
                                   "live capture", "authentication", "automatic renewal"],
            "policy": {"enable_http_proxy": False, "public_proxy": False, "save_flows": False,
                       "read_response_body": False, "forward_credentials_to_third_party": False}}


def check_proxy_options(options):
    confdir = str(ROOT / ".auth/wechat-capture/mitmproxy")
    mode = ["regular"]
    profile = bool(getattr(options, "liumo_profile_capture", False))
    diagnostic = bool(getattr(options, "liumo_diagnostic_only", False))
    ui = bool(getattr(options, "liumo_ui_diagnostic", False))
    article = bool(getattr(options, "liumo_article_diagnostic", False))
    if (profile and diagnostic) or ((ui or article) and not diagnostic) or (ui and article):
        raise ProbeError("capture_proxy_configuration_rejected")
    experiment_directory = ROOT / ".auth/wechat-capture" / ("article-diagnostic-session" if article else "ui-diagnostic-session" if ui else "diagnostic-session" if diagnostic else "profile-session" if profile else "session")
    if options.confdir == str(experiment_directory / "mitmproxy"):
        from .capture_session import runtime_plan
        plan = runtime_plan(experiment_directory)
        if ((plan.get("experiment") == "profile") != profile
                or (plan.get("experiment") in {"diagnostic", "ui_diagnostic", "article_diagnostic"}) != diagnostic
                or (plan.get("experiment") == "ui_diagnostic") != ui
                or (plan.get("experiment") == "article_diagnostic") != article):
            raise ProbeError("capture_proxy_configuration_rejected")
        mode, confdir = [plan["mode"]], options.confdir
    elif profile or diagnostic:
        raise ProbeError("capture_proxy_configuration_rejected")
    expected = {"listen_host": "127.0.0.1", "listen_port": PORT, "mode": ["regular"],
                "allow_hosts": [ALLOW_HOST], "ignore_hosts": [], "ssl_insecure": False,
                "flow_detail": 0, "termlog_verbosity": "error", "show_ignored_hosts": False,
                "store_streamed_bodies": False, "command_history": False,
                "strip_ech": False,
                "confdir": confdir}
    expected["mode"] = mode
    if any(getattr(options, name, None) != value for name, value in expected.items()):
        raise ProbeError("capture_proxy_configuration_rejected")
    if diagnostic and getattr(options, "liumo_capture_seconds", None) != 120:
        raise ProbeError("capture_proxy_configuration_rejected")
    if getattr(options, "save_stream_file", None) or getattr(options, "hardump", None):
        raise ProbeError("capture_proxy_dump_rejected")


def recovery_decision(before, applied, current):
    """Pure guard, not an OS setter; refuse to overwrite concurrent user changes."""
    if current == before:
        return {"status": "already_original", "restore": False}
    if current != applied:
        return {"status": "conflict_requires_review", "restore": False}
    return {"status": "restore_required", "restore": True}


def fixture_capture():
    base = ROOT / ".tmp/wechat-session-validation"
    base.mkdir(mode=0o700, exist_ok=True)
    output = new_run("capture-fixture")
    summary = {"at": timestamp(), "evidence": "constructed_capture_events_no_network",
               "status": "constructed_passed_live_not_verified", "live_capture": False}
    targets = {"FIXTURE_BIZ": {"account": "猫笔刀", "mid": "100", "idx": "1"}}
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        root = Path(temporary)
        session = CaptureSession(targets=targets, writer=lambda data: save_captured_credentials(data, root))
        query = {"__biz": "FIXTURE_BIZ", "mid": "100", "idx": "1", "uin": "FAKE_UIN",
                 "key": "FAKE_KEY", "pass_ticket": "FAKE_PASS"}
        result = session.observe("https://mp.weixin.qq.com/s?" + urlencode(query), "GET", 200,
                                 "unrelated_cookie=NOT_STORED", ["appmsg_token=FAKE_TOKEN; Secure; HttpOnly"])
        saved = read_private_credentials(root / ".auth/wechat/maobidao.json", "猫笔刀")
        if result != "capture_saved_not_authentication_verified" or "unrelated_cookie" in saved["cookie"]:
            raise ProbeError("fixture_capture_failed")
        session.stop()
        summary.update({"capture": session.summary(), "private_file_mode": "0600",
                        "unknown_cookie_saved": False, "fake_credentials_retained": False})
    write_json(output / "capture-fixture.json", summary)
    return {"output": str(output), **summary}
