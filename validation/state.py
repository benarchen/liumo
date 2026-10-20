"""Incremental discovery with an independent pending archive queue."""

import fcntl
from contextlib import contextmanager
from pathlib import Path

from .common import article_key, article_url, parse_time, timestamp


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


def empty_state():
    return {"last_complete_check": None, "tasks": {}}


def ingest(state, pages, start_at, checked_at=None):
    """pages: validated list pages, ending in has_more=False; error pages stop a scan.

    Keep valid discoveries even if another page fails. Never advance the complete
    check marker unless all pages and publication boundaries are understood.
    Raw source times must be verified by callers before use here.
    """
    boundary = parse_time(start_at)
    issues, found, terminal, cursors = [], [], False, set()
    if not pages:
        issues.append("no_pages")
    for page in pages:
        if terminal:
            issues.append("page_after_terminal")
            break
        if page.get("error"):
            issues.append("page_failed")
            break
        cursor = str(page.get("cursor", ""))
        if cursor in cursors:
            issues.append("repeated_cursor")
            break
        cursors.add(cursor)
        if not isinstance(page.get("items"), list) or not isinstance(page.get("has_more"), bool):
            issues.append("invalid_page")
            break
        for item in page["items"]:
            try:
                if item.get("time_verified") is not True:
                    raise ValueError("unverified_publication_time")
                published = parse_time(item["published_at"])
                url = article_url(item["url"])
                key = article_key(url, item.get("id"), item.get("account"))
                if published < boundary:
                    continue
                existing = state["tasks"].get(key)
                if existing:
                    if existing["published_at"] != published.isoformat():
                        issues.append("identity_or_time_changed")
                    continue
                state["tasks"][key] = {
                    "url": url, "account": item["account"], "title": item.get("title", ""),
                    "published_at": published.isoformat(), "status": "pending", "attempts": 0,
                }
                found.append(key)
            except (KeyError, TypeError, ValueError):
                issues.append("invalid_or_unverified_item")
        terminal = page["has_more"] is False
    if not terminal:
        issues.append("coverage_incomplete")
    if terminal and not issues:
        state["last_complete_check"] = checked_at or timestamp()
    return {"found": found, "issues": sorted(set(issues)), "complete_scan": terminal and not issues}


def pending(state):
    return [key for key, task in state["tasks"].items() if task["status"] != "complete"]


def archive_result(state, key, result):
    if result not in {"complete", "partial", "failed"}:
        raise ValueError("invalid_archive_result")
    task = state["tasks"][key]
    if task["status"] == "complete":
        raise ValueError("completed_archive_is_immutable")
    task["attempts"] += 1
    task["status"] = result
