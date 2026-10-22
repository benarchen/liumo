"""Product file, time, public-link and process-lock utilities."""
import json
import os
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone_required")
    return result.astimezone(timezone.utc)


def public_content_link(value):
    """Remove WeChat session query fields before links enter an archive."""
    parts = urlsplit(value)
    if parts.hostname == "mp.weixin.qq.com":
        private = {"uin", "key", "pass_ticket", "appmsg_token", "wap_sid2", "wxtoken", "poc_token"}
        query = [(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
                 if key.lower() not in private]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return value


def write_json(path, data):
    """Atomic local update; callers use a process lock for shared state."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def error_kind(error):
    # Exception strings may contain response URLs or headers. Never persist them.
    name = type(error).__name__
    return "timeout" if "Timeout" in name else name


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("already_running") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
