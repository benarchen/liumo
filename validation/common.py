"""Local artifacts and credential-safe summaries."""

from liumo.common import timestamp, parse_time, public_content_link, write_json, error_kind

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "maobidao": "https://mp.weixin.qq.com/s/ihaxygZIbs2HwXMNiMaqEg",
    "stormzhang": "https://mp.weixin.qq.com/s/4ihER5266aHuAwNzX8cDgw",
}






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




def new_run(name):
    base = ROOT / "archives" / "feasibility"
    base.mkdir(parents=True, exist_ok=True)
    path = base / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + name)
    path.mkdir(mode=0o700)
    return path
