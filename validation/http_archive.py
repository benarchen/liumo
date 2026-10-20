"""HTTP body/images and an independent comment snapshot, never a fake screenshot."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from .archive import BLOCK_MARKERS, render_markdown
from .comments import collect_comments
from .common import ROOT, SAMPLES, article_url, new_run, timestamp, write_json
from .credentials import load_credentials, load_sample_credentials
from .http import ProbeError, WechatHTTP

SAMPLE_ACCOUNTS = {"maobidao": "猫笔刀", "stormzhang": "stormzhang"}


def literal(scripts, name):
    # Only literal assignments/fields; no eval, JS execution or guessed decoding.
    key = re.escape(name)
    match = re.search(r"\b" + key + r"\s*(?:=|:)\s*['\"]([A-Za-z0-9+/=_-]+)['\"]", scripts)
    if match:
        return match[1]
    match = re.search(r"\b" + key + r"\s*=\s*(\d+)\b", scripts)
    if match:
        return match[1]
    return None


def parse_article(html, url, account):
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#js_content")
    if body is None or not (body.get_text(strip=True) or body.select_one("img[src], img[data-src]")):
        restricted = any(marker in soup.get_text(" ", strip=True) for marker in BLOCK_MARKERS)
        raise ProbeError("access_restricted" if restricted else "body_template_not_supported")
    scripts = "\n".join(tag.get_text() for tag in soup.select("script"))
    if literal(scripts, "is_pay_subscribe") == "1":
        raise ProbeError("paid_content_not_verified")
    title = soup.select_one("#activity-name, h1")
    if title is None or not title.get_text(strip=True):
        raise ProbeError("title_missing")
    name = soup.select_one("#js_name, .wx_follow_nickname")
    name = name.get_text(" ", strip=True) if name else ""
    query = parse_qs(urlsplit(url).query)
    identity = {"biz": query.get("__biz", [literal(scripts, "biz")])[0],
                "appmsgid": query.get("mid", [literal(scripts, "mid") or literal(scripts, "appmsgid")])[0],
                "idx": query.get("idx", [literal(scripts, "idx")])[0],
                "comment_id": literal(scripts, "comment_id")}
    epoch = literal(scripts, "ct")
    try:
        candidate = datetime.fromtimestamp(int(epoch), timezone.utc).isoformat() if epoch else None
    except (ValueError, OverflowError, OSError):
        candidate = None
    for node in list(body.select("script, style, noscript, iframe, object, embed, [hidden]")):
        if node.parent is not None:
            node.decompose()
    for node in list(body.select("[style]")):
        if node.parent is not None and re.search(r"(?:^|;)\s*display\s*:\s*none\b", node.get("style", ""), re.I):
            node.decompose()
    return {"title": title.get_text(" ", strip=True), "account": name,
            "account_identity_verified": name == account, "identity": identity,
            "published_at_candidate": candidate, "publication_time_verified": False,
            "body": str(body), "body_visibility_verified": False}


def save_http_article(html, url, account, output, image_fetch, comment_request=None,
                      credential_biz=None, evidence="live_http", expected_identity=None):
    """Write one new run, preserve partial results, return only a safe summary."""
    result = {"started_at": timestamp(), "url": article_url(url), "evidence": evidence,
              "status": "failed", "reasons": [], "screenshot": {"status": "not_attempted"},
              "comments": {"status": "unknown"}}
    try:
        parsed = parse_article(html, url, account)
        if expected_identity and any(parsed["identity"].get(key) != value for key, value in expected_identity.items()):
            raise ProbeError("credential_article_scope_mismatch")
        result.update({key: value for key, value in parsed.items() if key != "body"})
        if evidence != "live_credentialed_http":
            result["html_sha256"] = hashlib.sha256(html.encode()).hexdigest()
        result.update(render_markdown(parsed["body"], parsed["title"], url, output, image_fetch))
        result["status"] = "partial"
        result["reasons"].extend(["original_page_screenshot_not_verified", "publication_time_not_verified",
                                  "static_body_visibility_not_verified"])
        if not parsed["account_identity_verified"]:
            result["reasons"].append("account_identity_unverified")
        if result["image_failures"]:
            result["reasons"].append("images_incomplete")
        identity = parsed["identity"]
        if comment_request is None:
            result["comments"] = {"status": "blocked", "reason": "credentials_missing"}
        elif not parsed["account_identity_verified"] or not identity["biz"] or identity["biz"] != credential_biz:
            result["comments"] = {"status": "blocked", "reason": "credential_article_scope_mismatch"}
        elif any(not identity[key] or identity[key] == "0" for key in ("appmsgid", "idx", "comment_id")):
            result["comments"] = {"status": "unknown", "reason": "article_identity_missing"}
        else:
            snapshot = collect_comments(comment_request, identity)
            write_json(Path(output) / "comments.json", snapshot)
            result["comments"] = {key: value for key, value in snapshot.items() if key != "items"}
            result["comments"]["saved_comments"] = len(snapshot["items"])
            result["comments"]["path"] = "comments.json"
        if result["comments"]["status"] not in {"loaded", "none"}:
            result["reasons"].append("comments_" + result["comments"]["status"])
    except ProbeError as exc:
        result["reasons"].append(exc.reason)
        result["status"] = "blocked" if exc.reason in {"access_restricted", "paid_content_not_verified"} else "failed"
    finally:
        result["finished_at"] = timestamp()
        write_json(Path(output) / "http-metadata.json", result)
    return {"output": str(output), **result}


def archive_http(sample, credentialed=False, transport="python", client=None):
    output = new_run("http-article")
    url, account = SAMPLES[sample], SAMPLE_ACCOUNTS[sample]
    credential, credential_reason = None, None
    counts = {"body": 0, "images": 0, "comment_api": 0}
    try:
        if credentialed:
            credential = load_sample_credentials(sample)
        client = client if client is not None else WechatHTTP(transport=transport)
        counts["body"] += 1
        html = client.read(url, {"Cookie": credential["cookie"]} if credentialed else None).decode("utf-8")
    except (ProbeError, UnicodeError) as exc:
        result = {"status": "blocked", "reason": exc.reason if isinstance(exc, ProbeError) else "html_encoding_invalid",
                  "at": timestamp(), "evidence": "live_credentialed_http" if credentialed else "live_http_attempt",
                  "requests_attempted": counts, "transport": transport}
        if isinstance(exc, ProbeError) and exc.code is not None:
            result["error_code"] = exc.code
        write_json(output / "http-metadata.json", result)
        return {"output": str(output), **result}
    if not credentialed:
        try:
            credential = load_credentials(account)
        except ProbeError as exc:
            credential_reason = exc.reason

    def image_fetch(image):
        if counts["images"] >= 10:
            raise ProbeError("sample_image_budget_exhausted")
        counts["images"] += 1
        return client.read(image, limit=25 * 1024 * 1024)

    def comment_request(action, fields):
        if counts["comment_api"] >= 12:
            raise ProbeError("sample_api_budget_exhausted")
        counts["comment_api"] += 1
        return client.api(action, fields, credential)

    expected = ({"biz": credential["biz"], "appmsgid": credential["source_identity"]["mid"],
                 "idx": credential["source_identity"]["idx"]} if credentialed else None)
    result = save_http_article(html, url, account, output, image_fetch,
                               comment_request if credential else None,
                               credential["biz"] if credential else None,
                               evidence="live_credentialed_http" if credentialed else "live_http",
                               expected_identity=expected)
    result.update(requests_attempted=counts, transport=transport, credentialed=credentialed)
    if credential_reason:
        result["credential_input"] = credential_reason
    write_json(output / "http-metadata.json", {key: value for key, value in result.items() if key != "output"})
    return result


def fixture_http():
    output = new_run("http-fixture")
    html = (ROOT / "examples/pages/http-article.html").read_text()
    pages = json.loads((ROOT / "examples/comment-pages.json").read_text())

    def request(action, fields):
        if action == "comments":
            return pages["comments"][fields["buffer"]]
        return pages["replies"][str(fields["max_reply_id"])].copy()

    def reject_external_image(_):
        raise ProbeError("fixture_external_image_rejected")

    result = save_http_article(html, SAMPLES["maobidao"], "猫笔刀", output,
                               reject_external_image,
                               request, "FIXTURE_BIZ", "constructed_http_input_no_live_requests")
    return result
