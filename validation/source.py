"""Read-only WeRead list probe based on a pinned reference, without fallbacks."""

import base64
import hashlib
import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from .common import ROOT, SAMPLES, error_kind, new_run, timestamp, write_json

REFERENCE_COMMIT = "d94db01372105bc479db81a0ac91829dac7f43e4"
BASE = "https://weread.qq.com"
# Public sample identities already recorded in validation/capture.py; no session data.
TARGET_BIZ = {"猫笔刀": "MzE5ODk2NjUwOA==", "stormzhang": "MzA4NTQwNDcyMA=="}
SOURCE_REASONS = {"invalid_response", "source_rejected", "source_shape_changed",
                  "missing_source_identity", "source_repeated_article", "source_http_rejected",
                  "source_response_too_large"}


def review_plan():
    """No filesystem session access, browser launch, or network request."""
    targets = [{"account": name, "biz": biz,
                "book_id": "MP_WXS_" + base64.b64decode(biz, validate=True).decode("ascii"),
                "sample_url": SAMPLES["maobidao" if name == "猫笔刀" else name],
                "mapping_basis": "existing_public_sample_identity",
                "live_identity_verified": False} for name, biz in TARGET_BIZ.items()]
    return {"status": "planned", "live_requests": 0, "credentials_read": False,
            "targets": targets, "endpoint": BASE + "/web/mp/articles",
            "method": "GET", "query_fields": ["bookId", "offset"],
            "headers": ["Accept", "Accept-Language", "User-Agent", "Origin", "Referer"],
            "credential_origin": "project_isolated_weread_profile",
            "credential_destination": BASE, "cross_origin_cookies": False,
            "max_pages_per_account": 3, "max_list_response_bytes": 2 * 1024 * 1024,
            "pagination_candidate": "top_level_group_count_not_live_verified",
            "alternative_source_commit": "2bde705a8346844fab6c4ec53b43708497881594",
            "reference_commit": REFERENCE_COMMIT, "comments_requested": False,
            "required_next_evidence": ["account_identity", "multiple_articles", "real_pagination",
                                       "canonical_article_links", "publication_times", "coverage_range"]}


def validate_target(book_id, account, max_pages):
    expected = {item["account"]: item["book_id"] for item in review_plan()["targets"]}
    if account not in expected or book_id != expected[account]:
        raise ValueError("source_target_mismatch")
    if type(max_pages) is not int or not 1 <= max_pages <= 3:
        raise ValueError("probe_scope_exceeded")


def profile_path(site):
    if site not in {"weread", "article"}:
        raise ValueError("invalid_site")
    root = ROOT / ".auth"
    if root.is_symlink():
        raise ValueError("symlink_auth_directory")
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    path = root / site
    if path.is_symlink():
        raise ValueError("symlink_profile")
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)
    return path


def session_stamp(context):
    """Only compare owned WeRead authentication cookies in memory; never persist this stamp."""
    values = {row["name"]: row["value"] for row in context.cookies(BASE)
              if row.get("name") in {"wr_skey", "wr_vid"}}
    if not values.get("wr_skey") or not values.get("wr_vid"):
        return None
    return hashlib.sha256((values["wr_skey"] + "\0" + values["wr_vid"]).encode()).digest()


def wait_for_session(context, page, initial, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.is_closed():
            return "session_window_closed"
        current = session_stamp(context)
        if current is not None and current != initial:
            return "session_cookie_updated"
        page.wait_for_timeout(500)
    return "session_wait_timeout"


def login(site, sample="maobidao", auto_wait=False):
    if auto_wait and site != "weread":
        raise ValueError("auto_wait_requires_weread")
    path = profile_path(site)
    url = BASE + "/" if site == "weread" else SAMPLES[sample]
    print(f"登录对象：{'微信读书' if site == 'weread' else '用户提供的微信文章页面'}。")
    print(f"会话只保存在本机 {path}。凭证随站点请求发往对应腾讯域名，不导出 Cookie 或 token。")
    print("请在专用窗口完成正常扫码或人工验证，不需要将凭证或二维码发到对话。")
    with sync_playwright() as driver:
        context = driver.chromium.launch_persistent_context(
            str(path), channel="chrome", headless=False, chromium_sandbox=True,
        )
        try:
            page = context.new_page()
            initial = session_stamp(context) if auto_wait else None
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if auto_wait:
                print("已打开项目专用微信读书窗口，请正常扫码；程序最多等待 300 秒并自动结束，无需按 Enter。", flush=True)
                # Only known sign-in controls; never inspect books or account information.
                for label in ("登录", "微信登录"):
                    control = page.get_by_text(label, exact=True)
                    if control.count() == 1 and control.is_visible():
                        control.click(timeout=5000)
                        break
                reason = wait_for_session(context, page, initial)
                return {"profile": str(path), "session_saved": True, "authentication_verified": False,
                        "session_cookie_updated": reason == "session_cookie_updated", "reason": reason,
                        "status": "session_updated" if reason == "session_cookie_updated" else "partial"}
            else:
                input("完成后回到此终端按 Enter 保存并关闭专用窗口：")
        finally:
            context.close()
    return {"profile": str(path), "session_saved": True, "authentication_verified": False}


def parse_weread(payload, book_id, account):
    if not isinstance(payload, dict):
        raise ValueError("invalid_response")
    code = payload.get("errCode", payload.get("errcode", 0))
    if not (code is None or type(code) is int and code == 0 or type(code) is str and code == "0"):
        raise ValueError("source_rejected")
    if not isinstance(payload.get("reviews"), list):
        raise ValueError("source_shape_changed")
    items = []
    for group in payload["reviews"]:
        if not isinstance(group, dict) or not isinstance(group.get("subReviews"), list) or not group["subReviews"]:
            raise ValueError("source_shape_changed")
        for child in group["subReviews"]:
            if not isinstance(child, dict):
                raise ValueError("source_shape_changed")
            review = child.get("review") or {}
            if not isinstance(review, dict):
                raise ValueError("source_shape_changed")
            info = review.get("mpInfo") or {}
            if not isinstance(info, dict) or not isinstance(info.get("title"), str) or not info["title"].strip():
                raise ValueError("source_shape_changed")
            identity = review.get("reviewId") or child.get("reviewId")
            if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_~./+=-]{1,256}", identity):
                raise ValueError("missing_source_identity")
            original = info.get("originalId")
            if original is not None and (not isinstance(original, str)
                    or not re.fullmatch(r"[A-Za-z0-9_~./+=-]{1,256}", original)):
                raise ValueError("missing_source_identity")
            raw_time = info.get("time") or review.get("createTime") or group.get("createTime")
            try:
                if type(raw_time) not in (int, str) or not re.fullmatch(r"\d{1,12}", str(raw_time)):
                    raise ValueError()
                candidate = datetime.fromtimestamp(int(raw_time), timezone.utc).isoformat()
            except (ValueError, TypeError, OverflowError, OSError):
                candidate = None
            # originalId is a source token, not necessarily a public article shortlink.
            items.append({"account": account, "id": identity, "original_id": original,
                          "url": None, "url_verified": False,
                          "title": str(info.get("title", "")), "published_at": candidate,
                          "candidate_time_field": "mpInfo.time" if info.get("time") else "createTime",
                          "time_verified": False, "book_id": book_id})
    return items, len(payload["reviews"])


def scan_weread(fetch, book_id, account, max_pages=3):
    """Bounded scan; fetch is the only I/O boundary. Never infers publication coverage."""
    if type(max_pages) is not int or not 1 <= max_pages <= 3:
        raise ValueError("probe_scope_exceeded")
    result = {"pages": [], "coverage_complete": False, "source_terminal_observed": False,
              "publication_times_verified": False, "account_identity_verified": False,
              "status": "not_verified"}
    seen, offset = set(), 0
    for _ in range(max_pages):
        payload = None
        try:
            payload = fetch(offset)
            items, count = parse_weread(payload, book_id, account)
            ids = [item["id"] for item in items]
            if len(set(ids)) != len(ids) or seen.intersection(ids):
                raise ValueError("source_repeated_article")
            # clearAll is reported by one reference, not an authoritative coverage guarantee.
            terminal = payload.get("clearAll")
            if "clearAll" in payload and (type(terminal) is not int or terminal not in (0, 1)):
                raise ValueError("source_shape_changed")
            result["pages"].append({"cursor": str(offset), "items": items,
                                    "has_more": count > 0 and terminal != 1})
            seen.update(ids)
            if count == 0 or terminal == 1:
                result["source_terminal_observed"] = True
                break
            offset += count
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in SOURCE_REASONS else None
            result["reason"] = reason or "source_rejected_or_shape_changed"
            if isinstance(payload, dict):
                code = payload.get("errCode", payload.get("errcode"))
                if type(code) in (int, str) and re.fullmatch(r"-?\d{1,12}", str(code)):
                    result["business_code"] = int(code)
            break
    if "reason" not in result:
        result["reason"] = ("source_identity_links_and_times_unverified" if result["source_terminal_observed"]
                            else "sample_page_limit_not_complete_coverage")
    if result["pages"]:
        result["status"] = "list_observed_times_unverified"
    return result


def discover(book_id, account, max_pages=3):
    validate_target(book_id, account, max_pages)
    profile = profile_path("weread")
    output = new_run("source")
    result = {"at": timestamp(), "evidence": "live_source_attempt", "reference_commit": REFERENCE_COMMIT,
              "endpoint": BASE + "/web/mp/articles", "account": account, "book_id": book_id,
              "pages": [], "coverage_complete": False, "publication_times_verified": False,
              "account_identity_verified": False,
              "status": "not_verified"}
    try:
        with sync_playwright() as driver:
            context = driver.chromium.launch_persistent_context(
                str(profile), channel="chrome", headless=True, chromium_sandbox=True,
            )
            try:
                # Only the named public-account list is read; never enumerate the bookshelf.
                page = context.pages[0] if context.pages else context.new_page()
                user_agent = page.evaluate("navigator.userAgent")
                def fetch(offset):
                    if offset:
                        time.sleep(2)
                    response = context.request.get(result["endpoint"], params={"bookId": book_id, "offset": offset},
                                                   headers={"Accept": "application/json, text/plain, */*",
                                                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                                                            "User-Agent": user_agent,
                                                            "Origin": BASE, "Referer": BASE + "/"},
                                                   max_redirects=0, timeout=30000)
                    if response.status != 200:
                        result["http_status"] = response.status
                        raise ValueError("source_http_rejected")
                    result["http_status"] = 200
                    if len(response.body()) > 2 * 1024 * 1024:
                        raise ValueError("source_response_too_large")
                    return response.json()
                result.update(scan_weread(fetch, book_id, account, max_pages))
            finally:
                context.close()
    except Exception as exc:
        result["reason"] = "environment_or_browser_" + error_kind(exc)
    # Never save raw response headers, arbitrary payload fields or exception strings.
    write_json(output / "source.json", result)
    return {"output": str(output), **result}
