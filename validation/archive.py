"""Conservative page snapshot probe. Unknown comment state is never complete."""

import base64
import os
import hashlib
import re
import struct
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify
from playwright.sync_api import sync_playwright

from .common import SAMPLES, article_url, error_kind, new_run, timestamp, write_json, public_content_link
from .http import ProbeError

COMMENT_SELECTOR = "#js_cmt_area, #js_comment_area, .rich_media_comment, [data-liumo-comments]"
EXPAND = re.compile(r"^(展开(?:全部|更多)?(?:回复|留言|评论)|查看(?:全部|更多|\d+条)?回复|更多留言|加载更多)$")
BLOCK_MARKERS = ("环境异常", "访问过于频繁", "完成验证", "该内容已被发布者删除", "此内容因违规无法查看")


def comment_status(text, visible, items=0, failed_requests=0, pending=0):
    if re.search(r"请在微信|登录后.*(?:留言|评论)|无权|权限不足", text):
        return "inaccessible"
    if failed_requests or re.search(r"加载失败|网络异常|请求失败", text):
        return "failed"
    if not visible:
        return "unknown"
    if pending:
        return "incomplete"
    if re.search(r"暂无(?:留言|评论)|尚无(?:留言|评论)|留言已关闭|评论已关闭", text):
        return "none" if items == 0 else "unknown"
    return "loaded" if items > 0 else "unknown"


def png_size(path):
    data = Path(path).read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid_png")
    return struct.unpack(">II", data[16:24])


def image_extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("unsupported_image")


def render_markdown(html, title, base_url, output, fetch, image_nodes=(), image_indices=None):
    """Convert only the body; a failed image remains an explicit local marker."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, iframe, object, embed"):
        tag.decompose()
    heading = soup.find("h1")
    if (heading and heading.get_text(" ", strip=True) == title.strip()
            and not any(str(text).strip() for text in heading.find_all_previous(string=True))):
        heading.decompose()
    images, failures, ignored = [], [], []
    observed = {node["index"]: node for node in image_nodes}
    image_dir = Path(output) / "images"
    image_dir.mkdir(exist_ok=True)
    tags = soup.select("img")
    if image_indices is not None and (len(image_indices) != len(tags)
            or len(set(image_indices)) != len(image_indices)
            or any(type(index) is not int or index < 0 for index in image_indices)):
        raise ValueError("body_image_mapping_mismatch")
    for position, tag in enumerate(tags):
        index = image_indices[position] if image_indices is not None else position
        source = tag.get("data-src") or tag.get("src") or ""
        node = observed.get(index, {})
        # Observed on the real sample: an unpopulated, hidden footer avatar,
        # not a missing article illustration. Unknown nodes remain failures.
        if (tag.get("id") == node.get("id") == "js_tail_panel_account_avatar"
                and not source and node.get("has_source") is False
                and node.get("visible") is False
                and all(node.get(key) == 0 for key in
                        ("natural_width", "natural_height", "rendered_width", "rendered_height"))):
            ignored.append({"index": index, "id": node["id"], "reason": "observed_hidden_empty_account_avatar"})
            tag.decompose()
            continue
        url = urljoin(base_url, source)
        try:
            if not source:
                raise ValueError("missing_image_source")
            if source.startswith("data:image/") and ";base64," in source:
                data = base64.b64decode(source.split(",", 1)[1], validate=True)
            else:
                if urlsplit(url).scheme not in {"https", "http"}:
                    raise ValueError("unsupported_image_url")
                data = fetch(url)
            if not data or len(data) > 25 * 1024 * 1024:
                raise ValueError("image_size_limit")
            digest = hashlib.sha256(data).hexdigest()
            relative = "images/" + digest[:24] + image_extension(data)
            destination = Path(output) / relative
            if not destination.exists():
                destination.write_bytes(data)
            tag["src"] = relative
            for attribute in ("srcset", "data-src", "data-original"):
                tag.attrs.pop(attribute, None)
            images.append({"index": index, "path": relative, "sha256": digest, "bytes": len(data)})
        except Exception as exc:
            known = {"missing_image_source", "unsupported_image", "unsupported_image_url", "image_size_limit", "image_http_error", "unverified_image_host"}
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in known else error_kind(exc)
            failures.append({"index": index, "reason": reason, "source_host": urlsplit(url).hostname if source else None})
            tag.replace_with(soup.new_string(f"[配图 {index + 1} 下载失败]"))
    for tag in soup.select("a[href]"):
        link = urljoin(base_url, tag["href"])
        tag["href"] = public_content_link(link) if urlsplit(link).scheme in {"https", "http"} else "#"
    content = markdownify(str(soup), heading_style="ATX", strip=["video", "audio"])
    (Path(output) / "article.md").write_text(f"# {title}\n\n{content.strip()}\n", encoding="utf-8")
    return {"images": images, "image_failures": failures, "ignored_image_nodes": ignored,
            "body_sha256": hashlib.sha256(content.encode()).hexdigest()}


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


def visible_comments(page):
    regions = page.locator(COMMENT_SELECTOR)
    return [regions.nth(i) for i in range(regions.count()) if regions.nth(i).is_visible()]


def inspect_comments(page, network_failures, expansion_limit=20):
    if network_failures:
        return {"status": "failed", "reason": "comment_request_failed_no_retry", "expanded": 0,
                "failed_comment_requests": len(network_failures), "request_failures": network_failures}
    clicks = 0
    for _ in range(expansion_limit):
        if network_failures:
            break
        regions = visible_comments(page)
        controls = [control for region in regions for control in region.get_by_text(EXPAND).all()
                    if control.is_visible()]
        if not controls:
            break
        try:
            controls[0].click(timeout=1500)
            page.wait_for_timeout(400)
            clicks += 1
        except Exception:
            return {"status": "failed", "expanded": clicks, "reason": "expand_failed"}
    regions = visible_comments(page)
    text = "\n".join(region.inner_text() for region in regions)
    items = sum(sum(node.is_visible() for node in region.locator(".js_comment_item, .comment_item, [data-liumo-comment]").all())
                for region in regions)
    pending = sum(sum(control.is_visible() for control in region.get_by_text(EXPAND).all()) for region in regions)
    status = comment_status(text, bool(regions), items, len(network_failures), pending)
    return {"status": status, "visible_regions": len(regions), "visible_item_nodes": items,
            "expanded": clicks, "remaining_controls": pending,
            "failed_comment_requests": len(network_failures),
            "request_failures": network_failures,
            "scope": "visible_and_loadable_at_snapshot", "selector_validation": "sample_required"}


def watch_comment_requests(page):
    failures = []
    def failure(reason, url, status=None, code=None):
        parsed = urlsplit(url)
        record = {"reason": reason, "host": parsed.hostname, "path": parsed.path}
        if status is not None:
            record["http_status"] = status
        if code is not None:
            try:
                record["business_code"] = int(code)
            except (TypeError, ValueError):
                record["business_code"] = "non_numeric_rejection"
        failures.append(record)

    def response_check(response):
        path = urlsplit(response.url).path.lower()
        if not any(key in path for key in ("comment", "reply", "appmsg_comment")):
            return
        if response.status >= 400:
            failure("http_rejected", response.url, response.status)
        elif "json" in response.headers.get("content-type", ""):
            try:
                payload = response.json()
                code = payload.get("base_resp", {}).get("ret") or payload.get("errcode", 0)
                if code not in (0, "0", None):
                    failure("business_rejected", response.url, response.status, code)
            except Exception:
                failure("invalid_comment_response", response.url, response.status)

    def request_check(request):
        path = urlsplit(request.url).path.lower()
        if any(key in path for key in ("comment", "reply", "appmsg_comment")):
            failure("network_failure", request.url)

    page.on("response", response_check)
    page.on("requestfailed", request_check)

    def detach():
        page.remove_listener("response", response_check)
        page.remove_listener("requestfailed", request_check)
    return failures, detach


def await_manual_readiness():
    print("请在专用窗口正常打开目标文章。若需要验证，请由您手动完成；程序不会自动处理验证码。")
    print("确认已能阅读文章后回到此终端按 Enter 开始取证；无法访问或不希望继续时输入 q。")
    try:
        return input("就绪后按 Enter，或输入 q 取消：").strip() == ""
    except (EOFError, KeyboardInterrupt):
        return False


def public_page_observations(page):
    """Only visible article metadata and comment-region structure, no session data."""
    return page.evaluate("""() => {
        const visible = el => !!el && el.getClientRects().length > 0;
        const text = selector => {
            const el = document.querySelector(selector);
            return visible(el) ? (el.innerText || '').trim().slice(0, 200) : '';
        };
        const publish = document.querySelector('#publish_time');
        const epoch = typeof ct !== 'undefined' && /^\\d{10}$/.test(String(ct)) ? String(ct) : null;
        return {
            browser_time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            browser_language: navigator.language,
            account_name: text('#js_name'),
            author: text('#js_author_name'),
            publication_time_text: text('#publish_time'),
            publication_time_title: visible(publish) ? (publish.getAttribute('title') || '').slice(0, 100) : '',
            publication_epoch_candidate: epoch,
            article_identity_candidates: {
                biz: typeof biz === 'string' && /^[A-Za-z0-9+/=]+$/.test(biz) ? biz : null,
                mid: typeof mid !== 'undefined' && /^\\d+$/.test(String(mid)) ? String(mid) : null,
                idx: typeof idx !== 'undefined' && /^\\d+$/.test(String(idx)) ? String(idx) : null
            },
            comment_region_candidates: Array.from(document.querySelectorAll('[id]'))
                .filter(el => /comment|cmt|reply/i.test(el.id))
                .slice(0, 60).map(el => ({
                    id: el.id.slice(0, 120), tag: el.tagName.toLowerCase(), visible: visible(el),
                    visible_text_excerpt: visible(el) ? (el.innerText || '').trim().slice(0, 500) : ''
                }))
        };
    }""")


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


def snapshot_page(page, output, fixture=False, network_failures=None):
    output = Path(output)
    metadata = {"started_at": timestamp(), "evidence": "constructed_browser_page" if fixture else "live_page",
                "status": "failed", "comments": {"status": "unknown"}, "reasons": []}
    detach = None
    if network_failures is None:
        network_failures, detach = watch_comment_requests(page)
    try:
        text = page.locator("body").inner_text(timeout=10000)
        selector = "[data-liumo-body]" if fixture else "#js_content"
        body = page.locator(selector)
        if not body.count() or not body.inner_text().strip():
            metadata["reasons"] = ["access_restricted" if any(marker in text for marker in BLOCK_MARKERS) else "body_not_found"]
            metadata["status"] = "blocked" if "access_restricted" in metadata["reasons"] else "failed"
            return metadata
        metadata["status"] = "partial"
        metadata["title"] = page.locator("h1").first.inner_text() if page.locator("h1").count() else page.title()
        metadata["scroll"] = scroll_document(page)
        metadata["comments"] = inspect_comments(page, network_failures)
        # Expansion can increase the document height; check the new bottom too.
        metadata["scroll_after_expansion"] = scroll_document(page)
        image_nodes = image_node_observations(body)
        if not fixture:
            observations = public_page_observations(page)
            observations["body_image_nodes"] = image_nodes
            write_json(output / "page-observation.json", observations)
            metadata["page_observations"] = "page-observation.json"
            metadata["publication_time_candidates"] = {
                key: observations.get(key) for key in
                ("publication_time_text", "publication_time_title", "publication_epoch_candidate")
            }
            (output / "body-source.txt").write_text(body.inner_text(), encoding="utf-8")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(250)
        images = body.locator("img")
        metadata["body_images"] = images.count()
        selected = select_markdown_body(body)
        html = selected["html"]
        metadata["markdown_selection"] = {key: value for key, value in selected.items() if key != "html"}
        if not BeautifulSoup(html, "html.parser").get_text(strip=True):
            metadata["reasons"].append("visible_body_text_empty")
            return metadata

        def fetch(url):
            host = urlsplit(url).hostname or ""
            allowed = host == "mp.weixin.qq.com" or host.endswith((".qpic.cn", ".qlogo.cn"))
            if not allowed and not (fixture and host in {"127.0.0.1", "localhost"}):
                raise ValueError("unverified_image_host")
            response = page.context.request.get(url, timeout=20000, max_redirects=0)
            if response.status != 200:
                raise ValueError("image_http_error")
            return response.body()

        metadata.update(render_markdown(html, metadata["title"], page.url, output, fetch, image_nodes,
                                        selected["retained_image_indices"]))
        ignored = {node["index"] for node in metadata["ignored_image_nodes"]}
        metadata["unloaded_body_images"] = sum(
            node["index"] in selected["retained_image_indices"] and node["index"] not in ignored
            and (not node["complete"] or node["natural_width"] == 0)
            for node in image_nodes)
        metadata["snapshot_at"] = timestamp()
        dimensions = page.evaluate("({width:document.documentElement.clientWidth,height:document.documentElement.scrollHeight})")
        metadata["document_dimensions"] = dimensions
        if dimensions["height"] > 100000 or dimensions["width"] * dimensions["height"] > 100_000_000:
            metadata["reasons"].append("single_image_size_guard_not_proven_browser_limit")
        else:
            try:
                page.screenshot(path=str(output / "article.png"), full_page=True, timeout=30000)
                width, height = png_size(output / "article.png")
                after = page.evaluate("document.documentElement.scrollHeight")
                metadata["screenshot_dimensions"] = {"width": width, "height": height}
                if height < dimensions["height"] or height < after or width < dimensions["width"]:
                    metadata["reasons"].append("screenshot_dimensions_mismatch")
            except Exception as exc:
                metadata["reasons"].append("screenshot_" + error_kind(exc))
        if metadata["comments"]["status"] not in {"none", "loaded"}:
            metadata["reasons"].append("comments_" + metadata["comments"]["status"])
        if not metadata["scroll"]["bottom_reached"] or not metadata["scroll_after_expansion"]["bottom_reached"]:
            metadata["reasons"].append("bottom_not_reached")
        if metadata["image_failures"] or metadata["unloaded_body_images"]:
            metadata["reasons"].append("images_incomplete")
        # A live sample still needs original-source metadata and visual review.
        # Presence of visible comments cannot prove hidden replies were expanded.
        if not fixture:
            metadata["reasons"].extend(["publication_time_not_verified", "live_comment_selectors_not_validated", "visual_review_required"])
        metadata["status"] = "complete" if not metadata["reasons"] else "partial"
        return metadata
    except Exception as exc:
        metadata["reasons"].append(error_kind(exc))
        return metadata
    finally:
        if detach:
            detach()
        metadata["finished_at"] = timestamp()
        write_json(output / "metadata.json", metadata)


def credential_page_matches(page, credential):
    observed = public_page_observations(page)["article_identity_candidates"]
    expected = {"biz": credential["biz"], "mid": credential["source_identity"]["mid"],
                "idx": credential["source_identity"]["idx"]}
    return all(observed.get(key) == value for key, value in expected.items())


def archive(url, fixture=False, profile=None, headed=False, interactive=False, credential_sample=None):
    if interactive and (fixture or not headed):
        raise ValueError("interactive_requires_live_headed_page")
    output = new_run("fixture" if fixture else "article")
    try:
        credential = None
        if credential_sample is not None:
            from .credentials import load_sample_credentials, sample_browser_cookies
            if (fixture or profile or interactive or credential_sample not in SAMPLES
                    or article_url(url) != SAMPLES[credential_sample]):
                raise ProbeError("credential_article_scope_mismatch")
            credential = load_sample_credentials(credential_sample)
        with sync_playwright() as driver:
            options = {"channel": "chrome", "headless": not headed, "chromium_sandbox": True,
                       "viewport": {"width": 1100, "height": 900}, "device_scale_factor": 1}
            if credential:
                options["env"] = {key: value for key, value in os.environ.items()
                                  if key.upper() not in {"SSLKEYLOGFILE", "DEBUG", "PWDEBUG", "CHROME_LOG_FILE"}}
            browser = None
            if profile:
                context = driver.chromium.launch_persistent_context(str(profile), **options)
            else:
                viewport = options.pop("viewport")
                scale = options.pop("device_scale_factor")
                browser = driver.chromium.launch(**options)
                context = browser.new_context(viewport=viewport, device_scale_factor=scale)
            if credential:
                context.add_cookies(sample_browser_cookies(credential))
            page = context.new_page()
            network_failures, detach = watch_comment_requests(page)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                ready = not interactive or await_manual_readiness()
                if not ready:
                    metadata = {"status": "failed", "evidence": "user_cancelled_attempt",
                                "reasons": ["manual_capture_cancelled"], "finished_at": timestamp()}
                elif not fixture and urlsplit(page.url).hostname != "mp.weixin.qq.com":
                    metadata = {"status": "blocked", "evidence": "live_page_navigation",
                                "reasons": ["left_article_site"], "finished_at": timestamp()}
                elif credential and not credential_page_matches(page, credential):
                    metadata = {"status": "blocked", "evidence": "live_credentialed_page",
                                "reasons": ["page_identity_unverified"], "finished_at": timestamp()}
                else:
                    metadata = snapshot_page(page, output, fixture, network_failures)
                    if not fixture:
                        try:
                            metadata["resolved_source_url"] = article_url(page.url)
                            if metadata["resolved_source_url"] != article_url(url):
                                metadata.setdefault("reasons", []).append("redirect_identity_not_verified")
                                if metadata.get("status") == "complete":
                                    metadata["status"] = "partial"
                        except ValueError:
                            metadata["resolved_source_url"] = None
                metadata["manual_readiness_confirmed"] = interactive and ready
            finally:
                detach()
                context.close()
                if browser:
                    browser.close()
    except ProbeError as exc:
        metadata = {"status": "blocked", "reasons": [exc.reason], "finished_at": timestamp(),
                    "evidence": "credential_scope_check"}
    except Exception as exc:
        metadata = {"status": "failed", "reasons": ["browser_or_navigation_" + error_kind(exc)],
                    "finished_at": timestamp(), "evidence": "environment_attempt"}
        write_json(output / "metadata.json", metadata)
    if not fixture:
        metadata["source_url"] = article_url(url)
        metadata["publication_time"] = None
        metadata["account_identity"] = "unverified"
        if credential_sample:
            metadata["credentialed"] = True
            metadata["cookie_attributes"] = "host_only_secure_session_Lax_reconstructed_original_attributes_unknown"
    write_json(output / "metadata.json", metadata)
    return {"output": str(output), **metadata}
