"""Read-only macOS proxy baseline; no CA, proxy process or OS setters."""

import json
import os
import re
import socket
import subprocess
from pathlib import Path

from .common import ROOT, new_run, timestamp, write_json
from .credentials import check_private
from .http import ProbeError

NETWORKSETUP = "/usr/sbin/networksetup"
PROXY_FIELDS = {"Enabled", "Server", "Port", "Authenticated Proxy Enabled"}


def query(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                timeout=10, env={**os.environ, "LC_ALL": "C", "LANG": "C"})
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise ProbeError("preflight_command_unavailable") from None
    combined = result.stdout + result.stderr
    if "AuthorizationCreate()" in combined or "not authorized" in combined.lower():
        raise ProbeError("preflight_system_authorization_unavailable")
    if result.returncode or len(combined) > 65536 or result.stderr.strip():
        raise ProbeError("preflight_query_failed")
    return result.stdout


def parse_proxy(text):
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator or key not in PROXY_FIELDS or key in values:
            raise ProbeError("preflight_proxy_shape_unknown")
        values[key] = value.strip()
    if (set(values) != PROXY_FIELDS or values["Enabled"] not in {"Yes", "No"}
            or values["Authenticated Proxy Enabled"] not in {"0", "1"}
            or not values["Port"].isdigit() or not 0 <= int(values["Port"]) <= 65535):
        raise ProbeError("preflight_proxy_shape_unknown")
    return values


def parse_pac(text):
    lines = text.splitlines()
    if (len(lines) != 2 or not lines[0].startswith("URL:")
            or lines[1] not in {"Enabled: Yes", "Enabled: No"}):
        raise ProbeError("preflight_pac_shape_unknown")
    return {"URL": lines[0][4:].strip(), "Enabled": lines[1][9:]}


def active_service(services, order, route):
    if not services.startswith("An asterisk (*) denotes that a network service is disabled."):
        raise ProbeError("preflight_services_shape_unknown")
    interfaces = re.findall(r"^\s*interface:\s*(\S+)\s*$", route, re.MULTILINE)
    if len(interfaces) != 1:
        raise ProbeError("preflight_active_interface_unknown")
    interface = interfaces[0]
    allowed = {line for line in services.splitlines()[1:] if line and not line.startswith("*")}
    matches = []
    service = None
    for line in order.splitlines():
        match = re.fullmatch(r"\((\d+|\*)\) (.+)", line)
        if match:
            service = match[2] if match[1] != "*" else None
        if re.search(r"Device: " + re.escape(interface) + r"\)$", line) and service in allowed:
            matches.append(service)
    if len(matches) != 1:
        raise ProbeError("preflight_active_service_ambiguous")
    return matches[0], interface


def port_available():
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", 8899))
        except OSError:
            raise ProbeError("preflight_loopback_unavailable") from None


def collect_baseline(run=query, port_check=port_available):
    services = run([NETWORKSETUP, "-listallnetworkservices"])
    service, interface = active_service(services, run([NETWORKSETUP, "-listnetworkserviceorder"]),
                                        run(["/sbin/route", "-n", "get", "default"]))
    proxy = parse_proxy(run([NETWORKSETUP, "-getsecurewebproxy", service]))
    http_proxy = parse_proxy(run([NETWORKSETUP, "-getwebproxy", service]))
    pac = parse_pac(run([NETWORKSETUP, "-getautoproxyurl", service]))
    auto = run([NETWORKSETUP, "-getproxyautodiscovery", service]).strip()
    if auto not in {"Auto Proxy Discovery: On", "Auto Proxy Discovery: Off"}:
        raise ProbeError("preflight_autodiscovery_shape_unknown")
    bypass = run([NETWORKSETUP, "-getproxybypassdomains", service]).splitlines()
    if not bypass:
        raise ProbeError("preflight_bypass_shape_unknown")
    if port_check is not None:
        port_check()
    reasons = []
    if proxy["Authenticated Proxy Enabled"] != "0":
        reasons.append("authenticated_proxy_requires_unavailable_restore_secret")
    if pac["Enabled"] == "Yes" or auto.endswith(": On"):
        reasons.append("PAC_or_autodiscovery_conflict_requires_review")
    if proxy["Server"] == "127.0.0.1" and proxy["Port"] == "8899":
        reasons.append("existing_proxy_uses_proposed_endpoint")
    return {"at": timestamp(), "active_service": service, "interface": interface,
            "https_proxy": proxy, "http_proxy": http_proxy, "pac": pac,
            "autodiscovery": auto, "bypass_domains": bypass,
            "loopback_bind_checked": port_check is not None, "review_reasons": reasons,
            "recovery_verified": False, "system_changes_made": False}


def save_baseline(data, root=ROOT):
    directory = Path(root) / ".auth/wechat-capture/baselines"
    for node in (Path(root) / ".auth", directory.parent, directory):
        if node.is_symlink():
            raise ProbeError("credential_symlink_rejected")
        if not node.exists():
            node.mkdir(mode=0o700)
        check_private(node)
    name = re.sub(r"[^0-9]", "", data["at"]) + "-proxy.json"
    destination = directory / name
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return destination


def preflight():
    output = new_run("capture-preflight")
    result = {"at": timestamp(), "status": "blocked", "system_changes_made": False,
              "capture_started": False, "recovery_verified": False}
    try:
        data = collect_baseline()
        path = save_baseline(data)
        result.update({"status": "baseline_saved_review_required", "private_baseline": str(path),
                       "review_reasons": data["review_reasons"], "loopback_bind_checked": True})
    except ProbeError as exc:
        result["reason"] = exc.reason
    except Exception:
        result["reason"] = "preflight_failed"
    write_json(output / "preflight.json", result)
    return {"output": str(output), **result}
