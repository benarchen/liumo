"""First elected-comment snapshot, bounded pagination and reply ID merging."""

from .common import timestamp
from .http import ProbeError, business_ok, count

PUBLIC_FIELDS = ("content", "nick_name", "create_time", "identity_type", "identity_name",
                 "like_num", "reply_like_num", "author_like_status", "logo_url", "multi_info")


def public_item(raw, identity):
    if not isinstance(raw, dict) or type(raw.get(identity)) not in (str, int) or not str(raw[identity]):
        raise ProbeError("comment_identity_missing")
    if not isinstance(raw.get("content"), str):
        raise ProbeError("response_shape_changed")
    return {identity: str(raw[identity]), **{key: raw[key] for key in PUBLIC_FIELDS if key in raw}}


def merge_items(target, rows, identity, reasons):
    if not isinstance(rows, list):
        raise ProbeError("response_shape_changed")
    for raw in rows:
        item = public_item(raw, identity)
        key = item[identity]
        if key in target and target[key]["content"] != item["content"]:
            reasons.append("content_changed_during_snapshot")
        target.setdefault(key, item)


def collect_comments(request, identity, max_pages=3, max_reply_pages=3):
    """request(action, fields) returns JSON; no exception strings or raw payloads saved.

    Continuation of replies beyond one fetch is a proposed protocol path, tested
    on constructed data only. Counts/cursors must agree before reporting loaded.
    """
    if not 1 <= max_pages <= 10 or not 1 <= max_reply_pages <= 10:
        raise ValueError("invalid_page_limit")
    if any(not identity.get(key) for key in ("comment_id", "appmsgid", "idx")):
        raise ValueError("article_identity_missing")
    result = {"started_at": timestamp(), "status": "unknown", "scope": "elected_comments",
              "original_page_verified": False, "items": [], "pages": 0, "reply_pages": 0,
              "reasons": [], "snapshot_finished": False}
    reasons, comments, originals = result["reasons"], {}, {}
    total, cursor, cursors, terminal = None, "", set(), False
    fields = {"comment_id": identity["comment_id"], "appmsgid": identity["appmsgid"], "idx": identity["idx"]}
    try:
        for _ in range(max_pages):
            cursors.add(cursor)
            payload = request("comments", {**fields, "buffer": cursor, "offset": 0,
                                           "comment_scene": 0, "limit": 100})
            business_ok(payload)
            result["pages"] += 1
            observed_total = count(payload.get("elected_comment_total_cnt"))
            if total is not None and total != observed_total:
                reasons.append("comment_total_changed")
            total = observed_total if total is None else total
            rows = payload.get("elected_comment")
            if not isinstance(rows, list):
                raise ProbeError("response_shape_changed")
            for raw in rows:
                merge_items(comments, [raw], "content_id", reasons)
                originals.setdefault(str(raw["content_id"]), raw)
            if payload.get("friend_comment") or payload.get("my_comment"):
                reasons.append("additional_comment_sections_not_captured")
            if type(payload.get("enabled")) is not int or payload["enabled"] not in (0, 1):
                raise ProbeError("comment_access_state_unknown")
            if payload.get("enabled") == 0:
                reasons.append("comments_not_enabled")
                result["status"] = "inaccessible"
                break
            more = payload.get("continue_flag")
            if type(more) not in (bool, int) or more not in (True, False, 0, 1):
                raise ProbeError("continuation_missing")
            if not more:
                terminal = True
                break
            next_cursor = payload.get("buffer")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in cursors:
                raise ProbeError("comment_cursor_stalled")
            cursor = next_cursor
        if not terminal and result["status"] != "inaccessible":
            reasons.append("comment_page_limit")
        if total is not None and len(comments) != total:
            reasons.append("comment_count_mismatch")
    except ProbeError as exc:
        reasons.append(exc.reason)
        if exc.code is not None:
            result["error_code"] = exc.code
        if exc.reason == "http_rejected" and exc.code in (401, 403):
            result["status"] = "inaccessible"

    # Retain inline replies even if a later comment page failed; do not make
    # further authenticated requests after any failure or access refusal.
    for key, item in comments.items():
        replies = {}
        expected = None
        item["replies"] = []
        try:
            embedded = originals[key].get("reply_new")
            if not isinstance(embedded, dict):
                raise ProbeError("reply_extent_unknown")
            expected = count(embedded.get("reply_total_cnt"))
            merge_items(replies, embedded.get("reply_list"), "reply_id", reasons)
            reply_cursor = embedded.get("max_reply_id")
            seen, buffer = set(), ""
            for _ in range(max_reply_pages):
                if len(replies) >= expected or reasons:
                    break
                if type(reply_cursor) not in (int, str):
                    raise ProbeError("reply_cursor_missing")
                marker = (str(reply_cursor), buffer)
                if marker in seen:
                    raise ProbeError("reply_cursor_stalled")
                seen.add(marker)
                payload = request("replies", {**fields, "content_id": key, "limit": 100,
                                               "max_reply_id": reply_cursor, "buffer": buffer})
                business_ok(payload)
                result["reply_pages"] += 1
                reply_group = payload.get("reply_list")
                if not isinstance(reply_group, dict):
                    raise ProbeError("response_shape_changed")
                merge_items(replies, reply_group.get("reply_list"), "reply_id", reasons)
                reply_cursor = reply_group.get("max_reply_id")
                buffer = payload.get("buffer", "")
                if not isinstance(buffer, str):
                    raise ProbeError("response_shape_changed")
        except ProbeError as exc:
            reasons.append(exc.reason)
            if exc.code is not None:
                result["error_code"] = exc.code
        finally:
            if expected is not None:
                item["expected_reply_count"] = expected
                if len(replies) != expected:
                    reasons.append("reply_count_mismatch")
            item["replies"] = list(replies.values())
    result["items"] = list(comments.values())
    result["expected_comment_count"] = total
    result["reasons"] = sorted(set(reasons))
    if result["status"] != "inaccessible":
        result["status"] = ("partial" if comments else "failed") if reasons else ("loaded" if comments else "none")
    result["finished_at"] = timestamp()
    result["snapshot_finished"] = not reasons and terminal
    return result
