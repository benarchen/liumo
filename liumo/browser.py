"""Browser observations and publication checks; driver loaded only on request."""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .rss import MVPError

SHANGHAI = ZoneInfo('Asia/Shanghai')
BLOCK_MARKERS = ("环境异常", "访问过于频繁", "完成验证", "该内容已被发布者删除", "此内容因违规无法查看")

def sync_playwright():
    try:
        from playwright.sync_api import sync_playwright as start
    except ImportError:
        raise MVPError('browser_dependency_missing_install_requirements_browser') from None
    return start()


def publication(epoch, visible, now=None):
    """Cross-check original epoch with the rendered calendar date/minute."""
    try:
        when = datetime.fromtimestamp(int(epoch), timezone.utc)
        now = now or datetime.now(timezone.utc)
        if not 946684800 <= int(epoch) <= int(now.timestamp()) + 300:
            raise ValueError
        local = when.astimezone(SHANGHAI)
        match = re.search(r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})(?:日)?(?:\s+(\d{1,2}):(\d{2}))?', visible)
        if not match or tuple(map(int, match.groups()[:3])) != (local.year, local.month, local.day):
            raise ValueError
        if match[4] and (int(match[4]), int(match[5])) != (local.hour, local.minute):
            raise ValueError
        return when.isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        raise MVPError('original_publication_time_unverified') from None


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


def scroll_document(page, limit=100):
    """Bounded scrolling to the real bottom; do not modify the page layout."""
    stable = 0
    for step in range(limit):
        before = page.evaluate("({y:scrollY,h:document.documentElement.scrollHeight,v:innerHeight})")
        page.evaluate("window.scrollBy(0, Math.max(300, innerHeight * 0.8))")
        page.wait_for_timeout(180)
        after = page.evaluate("({y:scrollY,h:document.documentElement.scrollHeight,v:innerHeight})")
        at_bottom = after["y"] + after["v"] >= after["h"] - 3
        stable = stable + 1 if at_bottom and before["h"] == after["h"] else 0
        if stable >= 3:
            return {"bottom_reached": True, "steps": step + 1, "height": after["h"]}
    return {"bottom_reached": False, "steps": limit, "height": after["h"]}


def image_node_observations(body):
    return body.locator("img").evaluate_all("""images => images.map((el, index) => {
        const source = el.getAttribute('data-src') || el.getAttribute('src') || '';
        let host = null;
        try { host = source ? new URL(source, location.href).hostname : null; } catch (_) {}
        const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
        return {index, source_host: host, has_source: !!source,
            complete: el.complete, natural_width: el.naturalWidth, natural_height: el.naturalHeight,
            visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
            rendered_width: rect.width, rendered_height: rect.height,
            parent_tag: el.parentElement ? el.parentElement.tagName.toLowerCase() : null,
            id: el.id.slice(0, 100), alt: (el.getAttribute('alt') || '').slice(0, 100)};
    })""")


def select_markdown_body(body):
    """Filter a detached clone by computed visibility; never alter screenshot DOM."""
    return body.evaluate("""root => {
        const clone = root.cloneNode(true), images = Array.from(root.querySelectorAll('img'));
        const indices = new Map(images.map((el, index) => [el, index]));
        const retained = [], counts = {display_none: 0, hidden_text: 0, hidden_image: 0, non_body_tag: 0};
        function visit(source, target) {
            const style = getComputedStyle(source);
            if (style.display === 'none') {
                counts.display_none++; target.replaceChildren(); target.remove(); return;
            }
            if (/^(SCRIPT|STYLE|IFRAME|OBJECT|EMBED)$/.test(source.tagName)) {
                counts.non_body_tag++; target.remove(); return;
            }
            const hidden = style.visibility === 'hidden' || style.visibility === 'collapse';
            if (source.tagName === 'IMG') {
                if (hidden) { counts.hidden_image++; target.remove(); return; }
                retained.push(indices.get(source));
            }
            const originals = Array.from(source.childNodes), copies = Array.from(target.childNodes);
            originals.forEach((child, i) => {
                if (child.nodeType === Node.ELEMENT_NODE) visit(child, copies[i]);
                else if (hidden && child.nodeType === Node.TEXT_NODE) {
                    counts.hidden_text++; copies[i].remove();
                }
            });
        }
        visit(root, clone);
        return {html: clone.innerHTML, retained_image_indices: retained, pruned_counts: counts};
    }""")
