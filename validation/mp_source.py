"""Credential-based list candidate; publication times remain unverified."""

import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from .common import article_key, article_url, new_run, timestamp, write_json
from .credentials import ACCOUNTS, load_credentials
from .http import ProbeError, WechatHTTP, business_ok, count


def profile_shape(payload):
    """A fixed schema summary, never raw values, unknown keys or error text."""
    def fields(value, names):
        return {name: {"present": isinstance(value, dict) and name in value,
                       "type": type(value.get(name)).__name__ if isinstance(value, dict) else "unavailable"}
                for name in names}

    result = {"payload_type": type(payload).__name__,
              "fields": fields(payload, ("ret", "base_resp", "general_msg_list", "can_msg_continue", "next_offset"))}
    if not isinstance(payload, dict):
        return result
    for name in ("ret", "can_msg_continue", "next_offset"):
        value = payload.get(name)
        if type(value) is int and -2147483648 <= value <= 2147483647:
            result["fields"][name]["integer"] = value
    response = payload.get("base_resp")
    if (isinstance(response, dict) and type(response.get("ret")) is int
            and -2147483648 <= response["ret"] <= 2147483647):
        result["base_response_code"] = response["ret"]
    listing = payload.get("general_msg_list")
    if isinstance(listing, str):
        try:
            listing = json.loads(listing)
        except ValueError:
            result["listing_json_valid"] = False
            return result
        result["listing_json_valid"] = True
    result["listing_type"] = type(listing).__name__
    if isinstance(listing, dict):
        groups = listing.get("list")
        result["groups_type"] = type(groups).__name__
        if isinstance(groups, list):
            result["group_count"] = len(groups)
            result["first_group_shapes"] = []
            for group in groups[:3]:
                shape = {"type": type(group).__name__,
                         "fields": fields(group, ("comm_msg_info", "app_msg_ext_info"))}
                if isinstance(group, dict):
                    shape["message_fields"] = fields(group.get("comm_msg_info"), ("datetime", "type"))
                    shape["article_fields"] = fields(group.get("app_msg_ext_info"),
                                                     ("title", "content_url", "multi_app_msg_item_list"))
                result["first_group_shapes"].append(shape)
    return result


def parse_profile(payload, account, biz):
    business_ok(payload)
    if "general_msg_list" not in payload:
        # Observed in both live targets: ret=0/continue=0 is insufficient.
        # Never invent an empty list or complete the scan from that response.
        raise ProbeError("source_list_missing")
    try:
        listing = payload["general_msg_list"]
        if isinstance(listing, str):
            listing = json.loads(listing)
        groups = listing["list"]
        if not isinstance(groups, list):
            raise ValueError()
        items = {}
        for group in groups:
            details = group["app_msg_ext_info"]
            if not isinstance(details, dict) or not isinstance(details.get("multi_app_msg_item_list", []), list):
                raise ValueError()
            articles = [details, *details.get("multi_app_msg_item_list", [])]
            candidate = datetime.fromtimestamp(group["comm_msg_info"]["datetime"], timezone.utc).isoformat()
            for article in articles:
                if (not isinstance(article, dict) or not isinstance(article.get("content_url"), str)
                        or not isinstance(article.get("title", ""), str)):
                    raise ValueError()
                url = article_url(article["content_url"])
                query = parse_qs(urlsplit(url).query)
                if query.get("__biz", [biz])[0] != biz:
                    raise ValueError()
                stable = ":".join(query[key][0] for key in ("mid", "idx")) if query.get("mid") and query.get("idx") else article_key(url)
                items.setdefault(stable, {"id": stable, "url": url, "account": account,
                                          "title": str(article.get("title", "")),
                                          "published_at": candidate, "time_verified": False,
                                          "candidate_time_field": "comm_msg_info.datetime"})
        more = payload["can_msg_continue"]
        if type(more) is not int or more not in (0, 1):
            raise ValueError()
        offset = count(payload["next_offset"])
        return list(items.values()), bool(more), offset
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        raise ProbeError("source_shape_changed") from None


def scan_profile(request, account, biz, max_pages=3):
    if account not in ACCOUNTS or not 1 <= max_pages <= 3:
        raise ValueError("probe_scope_exceeded")
    result = {"at": timestamp(), "account": account, "status": "not_verified", "pages": [],
              "coverage_complete": False, "publication_times_verified": False,
              "account_identity_verified": False}
    offset = 0
    for _ in range(max_pages):
        payload = None
        try:
            payload = request("list", {"offset": offset, "count": 10})
            items, more, next_offset = parse_profile(payload, account, biz)
            result["pages"].append({"cursor": str(offset), "items": items, "has_more": more})
            if not more:
                result["coverage_complete"] = True
                break
            if next_offset <= offset:
                raise ProbeError("source_cursor_stalled")
            offset = next_offset
        except ProbeError as exc:
            result["reason"] = exc.reason
            if exc.code is not None:
                result["error_code"] = exc.code
            result["pages"].append({"cursor": str(offset), "error": exc.reason})
            if payload is not None:
                result["pages"][-1]["shape"] = profile_shape(payload)
            break
    if result["pages"] and any(page.get("items") for page in result["pages"]):
        result["status"] = "list_observed_times_unverified"
    if not result["coverage_complete"] and "reason" not in result:
        result["reason"] = "source_page_limit"
    return result


def discover_profile(account, max_pages=3, transport="python"):
    if account not in ACCOUNTS or not 1 <= max_pages <= 3:
        raise ValueError("probe_scope_exceeded")
    output = new_run("mp-source")
    result = {"at": timestamp(), "status": "blocked", "evidence": "live_source_attempt",
              "requests_attempted": 0, "account": account, "coverage_complete": False}
    try:
        credential = load_credentials(account)
        client = WechatHTTP(transport=transport)

        def request(action, fields):
            result["requests_attempted"] += 1
            return client.api(action, fields, credential)

        result.update(scan_profile(request, account, credential["biz"], max_pages))
    except ProbeError as exc:
        result["reason"] = exc.reason
    write_json(output / "source.json", result)
    return {"output": str(output), **result}


def diagnose_profile(account, transport="python", client=None):
    """Exactly one first-page request; emit structure and counts, not articles."""
    if account not in ACCOUNTS:
        raise ValueError("probe_scope_exceeded")
    output = new_run("mp-diagnostic")
    result = {"at": timestamp(), "account": account, "status": "not_verified",
              "evidence": "live_source_schema_attempt", "transport": transport, "requests_attempted": 0,
              "authentication_verified": False}
    try:
        credential = load_credentials(account)
        client = client if client is not None else WechatHTTP(transport=transport)
        result["requests_attempted"] = 1
        payload = client.api("list", {"offset": 0, "count": 10}, credential)
        result["shape"] = profile_shape(payload)
        items, more, _ = parse_profile(payload, account, credential["biz"])
        result.update(status="list_shape_observed", items_observed=len(items), has_more=more)
    except ProbeError as exc:
        result["reason"] = exc.reason
        if exc.code is not None:
            result["error_code"] = exc.code
    write_json(output / "diagnostic.json", result)
    return {"output": str(output), **result}


def diagnose_profiles(transport="python"):
    """One request per target, paced, no capture or system configuration."""
    output = new_run("mp-diagnostic-pair")
    results = []
    for account in ACCOUNTS:
        if results:
            time.sleep(2)
        results.append(diagnose_profile(account, transport))
    result = {"at": timestamp(), "status": "not_verified", "evidence": "live_source_schema_attempt",
              "results": results, "requests_attempted": sum(row["requests_attempted"] for row in results),
              "authentication_verified": False, "system_changes_made": False}
    write_json(output / "diagnostic-pair.json", result)
    return {"output": str(output), **result}
