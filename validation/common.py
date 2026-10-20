"""Local artifacts and credential-safe summaries."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "maobidao": "https://mp.weixin.qq.com/s/ihaxygZIbs2HwXMNiMaqEg",
    "stormzhang": "https://mp.weixin.qq.com/s/4ihER5266aHuAwNzX8cDgw",
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone_required")
    return result.astimezone(timezone.utc)


def article_url(value):
    """Only preserve public article identity, never session query parameters."""
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc != "mp.weixin.qq.com":
        raise ValueError("invalid_article_url")
    if parts.path.startswith("/s/") and re.fullmatch(r"[A-Za-z0-9_-]+", parts.path[3:]):
        return urlunsplit(("https", parts.netloc, parts.path, "", ""))
    query = parse_qs(parts.query)
    if parts.path == "/s" and all(query.get(k) for k in ("__biz", "mid", "idx", "sn")):
        public = {k: query[k][0] for k in ("__biz", "mid", "idx", "sn")}
        return urlunsplit(("https", parts.netloc, "/s", urlencode(public), ""))
    raise ValueError("unknown_article_identity")


def article_key(value, stable_id=None, account=None):
    if stable_id:
        if not account:
            raise ValueError("account_required")
        raw = f"{account}:{stable_id}"
    else:
        raw = article_url(value)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def public_content_link(value):
    """Remove WeChat session query fields before links enter an archive."""
    parts = urlsplit(value)
    if parts.hostname == "mp.weixin.qq.com":
        private = {"uin", "key", "pass_ticket", "appmsg_token", "wap_sid2", "wxtoken", "poc_token"}
        query = [(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
                 if key.lower() not in private]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return value


def new_run(name):
    base = ROOT / "archives" / "feasibility"
    base.mkdir(parents=True, exist_ok=True)
    path = base / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + name)
    path.mkdir(mode=0o700)
    return path


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
