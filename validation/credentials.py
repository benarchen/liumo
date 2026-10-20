"""Project-only credential input and atomic persistence of owned capture files."""

import json
import os
import stat
import fcntl
import tempfile
from pathlib import Path

from .common import ROOT, parse_time
from .http import ProbeError

ACCOUNTS = {"猫笔刀": "maobidao", "stormzhang": "stormzhang"}
MANAGED_BY = "liumo.capture.v1"


def check_private(node):
    node = Path(node)
    if node.is_symlink():
        raise ProbeError("credential_symlink_rejected")
    if not node.exists():
        raise ProbeError("credentials_missing")
    mode = node.stat()
    if mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077:
        raise ProbeError("credential_permissions_rejected")


def validate_credentials(data, account):
    try:
        if account not in ACCOUNTS or data.get("account") != account:
            raise ValueError()
        parse_time(data["captured_at"])
        for key in ("biz", "uin", "key", "pass_ticket", "appmsg_token"):
            value = data[key]
            if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
                raise ValueError()
        cookie = data.get("cookie", "")
        if not isinstance(cookie, str) or len(cookie) > 16384 or any(ord(c) < 32 for c in cookie):
            raise ValueError()
        cookie.encode("latin-1")
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        raise ProbeError("credential_input_invalid") from None
    return data


def read_private_credentials(path, account):
    check_private(path)
    if not stat.S_ISREG(Path(path).stat().st_mode):
        raise ProbeError("credential_input_invalid")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            mode = os.fstat(stream.fileno())
            if not stat.S_ISREG(mode.st_mode) or mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077:
                raise ProbeError("credential_permissions_rejected")
            raw = stream.read(32769)
        if len(raw) > 32768:
            raise ValueError()
        return validate_credentials(json.loads(raw), account)
    except (OSError, ValueError, UnicodeError):
        raise ProbeError("credential_input_invalid") from None


def load_credentials(account):
    if account not in ACCOUNTS:
        raise ProbeError("account_not_allowed")
    directory = ROOT / ".auth" / "wechat"
    for node in (ROOT / ".auth", directory):
        check_private(node)
    return read_private_credentials(directory / (ACCOUNTS[account] + ".json"), account)


def load_sample_credentials(sample):
    """Only the two captured article identities, never an arbitrary URL."""
    from .capture import TARGETS
    account = next((name for name, slug in ACCOUNTS.items() if slug == sample), None)
    if account is None:
        raise ProbeError("sample_not_allowed")
    data = load_credentials(account)
    expected = TARGETS.get(data["biz"])
    identity = data.get("source_identity")
    if (not expected or expected["account"] != account or not isinstance(identity, dict)
            or any(identity.get(key) != expected[key] for key in ("mid", "idx"))):
        raise ProbeError("credential_article_scope_mismatch")
    if not data.get("cookie"):
        raise ProbeError("credential_cookie_missing")
    return data


def sample_browser_cookies(data):
    """Host-only in-memory session cookies; original attributes were not saved."""
    from http.cookies import SimpleCookie
    from .capture import COOKIE_NAMES
    parsed = SimpleCookie()
    parsed.load(data.get("cookie", ""))
    cookies = [{"name": name, "value": parsed[name].value, "url": "https://mp.weixin.qq.com/",
                "secure": True, "sameSite": "Lax"} for name in sorted(COOKIE_NAMES) if name in parsed]
    if not cookies:
        raise ProbeError("credential_cookie_missing")
    return cookies


def save_captured_credentials(data, root=None):
    """Used only by an explicitly enabled capture; tests provide a fake root.

    Atomic replacement is limited to this writer's own previously managed file.
    An existing manually supplied credential file is never silently replaced.
    """
    account = data.get("account")
    validate_credentials(data, account)
    root = Path(root) if root is not None else ROOT
    directory = root / ".auth" / "wechat"
    for node in (root / ".auth", directory):
        if node.is_symlink():
            raise ProbeError("credential_symlink_rejected")
        if not node.exists():
            node.mkdir(mode=0o700)
        check_private(node)
    lock_path = directory / ".capture.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    temporary = None
    with os.fdopen(lock_fd, "r+") as lock:
        check_private(lock_path)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProbeError("credential_store_busy") from None
        try:
            destination = directory / (ACCOUNTS[account] + ".json")
            if destination.is_symlink():
                raise ProbeError("credential_symlink_rejected")
            if destination.exists():
                old = read_private_credentials(destination, account)
                if old.get("managed_by") != MANAGED_BY or old["biz"] != data["biz"]:
                    raise ProbeError("credential_existing_file_not_managed")
                if parse_time(data["captured_at"]) < parse_time(old["captured_at"]):
                    raise ProbeError("credential_capture_out_of_order")
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".capture-", dir=directory,
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({**data, "managed_by": MANAGED_BY}, stream, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
            fcntl.flock(lock, fcntl.LOCK_UN)
