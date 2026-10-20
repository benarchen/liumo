"""One normal homepage-context check per account; no credential persistence."""

import json
import time
from http.cookies import SimpleCookie
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .archive import BLOCK_MARKERS
from .capture import TARGETS
from .common import new_run, timestamp, write_json
from .credentials import load_credentials
from .http import ProbeError
from .http_archive import literal
from .mp_source import profile_shape, parse_profile

ENDPOINT = "https://mp.weixin.qq.com/mp/profile_ext"


def check_profile_context(account, client):
    result = {"account": account, "status": "not_verified", "at": timestamp(),
              "requests_attempted": {"home": 0, "list": 0}, "context_identity_verified": False,
              "new_credentials_saved": False, "publication_times_verified": False,
              "evidence": "live_profile_context_attempt"}
    try:
        credential = load_credentials(account)
        target = TARGETS.get(credential["biz"])
        if not target or target["account"] != account:
            raise ProbeError("credential_article_scope_mismatch")
        cookies = SimpleCookie()
        cookies.load(credential.get("cookie", ""))
        if "wxtokenkey" not in cookies:
            cookies["wxtokenkey"] = "777"  # Protocol compatibility, not authentication.
        base = {"__biz": credential["biz"], "scene": "124", "uin": credential["uin"],
                "key": credential["key"], "pass_ticket": credential["pass_ticket"]}
        headers = {"Accept": "text/html", "Accept-Encoding": "identity",
                   "Cookie": "; ".join(item.OutputString() for item in cookies.values())}
        result["requests_attempted"]["home"] = 1
        data = client.read(ENDPOINT + "?" + urlencode({"action": "home", **base}), headers)
        sid = client.take_profile_cookie()
        page = BeautifulSoup(data.decode("utf-8"), "html.parser")
        if any(marker in page.get_text(" ", strip=True) for marker in BLOCK_MARKERS):
            raise ProbeError("access_restricted")
        scripts = "\n".join(tag.get_text() for tag in page.select("script"))
        observed_biz = literal(scripts, "biz") or literal(scripts, "__biz")
        token = literal(scripts, "poc_token")
        result.update(homepage_identity_observed=observed_biz is not None,
                      homepage_token_observed=bool(token), homepage_session_cookie_observed=bool(sid))
        if observed_biz != credential["biz"]:
            raise ProbeError("profile_identity_unverified")
        result["context_identity_verified"] = True
        if not token or not sid:
            raise ProbeError("profile_session_fields_missing")
        cookies["poc_sid"] = sid
        params = {"action": "getmsg", **base, "offset": 0, "count": 10, "f": "json", "is_ok": "1",
                  "x5": "0", "appmsg_token": credential["appmsg_token"], "poc_token": token}
        headers.update(Accept="application/json,text/plain,*/*", Referer=ENDPOINT + "?" + urlencode(
            {"action": "home", "__biz": credential["biz"], "scene": "124"}),
            Cookie="; ".join(item.OutputString() for item in cookies.values()))
        result["requests_attempted"]["list"] = 1
        time.sleep(2)
        payload = json.loads(client.read(ENDPOINT + "?" + urlencode(params), headers))
        result["shape"] = profile_shape(payload)
        items, more, _ = parse_profile(payload, account, credential["biz"])
        result.update(status="list_shape_observed", items_observed=len(items), has_more=more)
    except ProbeError as exc:
        result["reason"] = exc.reason
        if exc.code is not None:
            result["error_code"] = exc.code
    except (UnicodeError, ValueError):
        result["reason"] = "profile_response_unusable"
    return result


def check_profile_contexts(client):
    output = new_run("profile-context-pair")
    rows = []
    for account in ("猫笔刀", "stormzhang"):
        if rows:
            time.sleep(2)
        rows.append(check_profile_context(account, client))
        write_json(output / "contexts.json", {"at": timestamp(), "status": "not_verified", "results": rows,
                   "system_changes_made": False, "new_credentials_saved": False})
    return {"output": str(output), "status": "not_verified", "results": rows,
            "system_changes_made": False, "new_credentials_saved": False}
