"""One notification boundary; only a local sender is implemented."""

import subprocess

LABELS = {
    "complete": "归档完成",
    "partial": "归档部分成功，请查看未完成原因",
    "failed": "检查或归档失败，请查看状态",
    "login_required": "需要重新登录，相关请求已停止",
}


def render_event(event, count):
    if event not in LABELS or type(count) is not int or count < 0:
        raise ValueError("invalid_notification_event")
    return {"title": "留墨", "message": f"{LABELS[event]}。涉及 {count} 篇文章。"}


def local_sender(title, message):
    script = 'on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run'
    subprocess.run(["/usr/bin/osascript", "-e", script, title, message],
                   check=True, timeout=10, capture_output=True)


def notify(event, count, sender=local_sender):
    payload = render_event(event, count)
    try:
        sender(payload["title"], payload["message"])
        return {"notification": "sent", "event": event}
    except Exception:
        # This result never mutates archive state. A future WeChat sender can
        # share this signature without adding a plugin or message queue.
        return {"notification": "failed", "event": event}
