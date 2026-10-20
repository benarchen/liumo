"""Original browser page, visible Markdown and local images; comments are excluded."""

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from validation.archive import (BLOCK_MARKERS, image_node_observations, png_size,
                                render_markdown, scroll_document, select_markdown_body)
from validation.common import ROOT, timestamp, write_json
from validation.http_archive import literal
from .rss import ACCOUNT, BIZ, MVPError, read_public

SHANGHAI = ZoneInfo('Asia/Shanghai')


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


def inspect_article(page, item):
    body = page.locator('#js_content')
    if not body.count() or not body.is_visible() or not body.inner_text().strip():
        text = page.locator('body').inner_text(timeout=10000)
        raise MVPError('access_restricted' if any(x in text for x in BLOCK_MARKERS) else 'visible_body_missing')
    public = page.evaluate(r"""() => {
        const text = s => document.querySelector(s)?.innerText.trim() || '';
        return {account:text('#js_name'),title:text('#activity-name'),
            time:text('#publish_time'),time_title:document.querySelector('#publish_time')?.getAttribute('title') || '',
            scripts:[...document.scripts].filter(s=>!s.src).map(s=>s.textContent).join('\n')};
    }""")
    scripts = public.pop('scripts')  # In memory only; return no raw HTML/JS.
    identity = {k: literal(scripts, k) for k in ('biz', 'mid', 'idx')}
    if not identity['mid']:
        identity['mid'] = literal(scripts, 'appmsgid')
    if public['account'] != ACCOUNT or identity != item['identity'] or identity['biz'] != BIZ:
        raise MVPError('original_article_identity_mismatch')
    if literal(scripts, 'is_pay_subscribe') == '1':
        raise MVPError('paid_content_not_verified')
    if not public['title'] or public['title'] != item['title']:
        raise MVPError('original_title_changed_or_unverified')
    public['published_at'] = publication(literal(scripts, 'ct'), public['time_title'] or public['time'])
    public.update(identity=identity, identity_verified=True, publication_time_verified=True)
    return public


def snapshot(page, item, output, start_at=None, image_fetch=read_public):
    """Caller navigates normally. No layout mutation or comment expansion."""
    output = Path(output)
    result = {'source_url': item['url'], 'key': item['key'], 'started_at': timestamp(),
              'status': 'failed', 'reasons': [], 'comments_status': 'not_requested'}
    try:
        public = inspect_article(page, item)
        result.update(public)
        if start_at and datetime.fromisoformat(public['published_at']) < datetime.fromisoformat(start_at):
            result['status'] = 'skipped_before_start'
            return result
        result['status'] = 'partial'
        body = page.locator('#js_content')
        result['scroll'] = scroll_document(page)
        nodes = image_node_observations(body)
        selected = select_markdown_body(body)
        if len(selected['retained_image_indices']) > 25:
            raise MVPError('body_image_budget_exceeded')
        result['markdown_selection'] = {k: v for k, v in selected.items() if k != 'html'}
        result.update(render_markdown(selected['html'], public['title'], item['url'], output,
                                       lambda url: image_fetch(url, limit=25 * 1024 * 1024), nodes,
                                       selected['retained_image_indices']))
        ignored = {x['index'] for x in result['ignored_image_nodes']}
        unloaded = [n['index'] for n in nodes if n['index'] in selected['retained_image_indices']
                    and n['index'] not in ignored and (not n['complete'] or not n['natural_width'])]
        result['unloaded_body_images'] = unloaded
        if not result['scroll']['bottom_reached']:
            result['reasons'].append('page_bottom_not_reached')
        if result['image_failures'] or unloaded:
            result['reasons'].append('images_incomplete')
        page.evaluate('window.scrollTo(0,0)')
        page.wait_for_timeout(250)
        dims = page.evaluate('({width:document.documentElement.clientWidth,height:document.documentElement.scrollHeight})')
        result['document_dimensions'] = dims
        result['snapshot_at'] = timestamp()
        # Large modal/fixed layers can obscure article text in a full-page capture.
        overlays = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e=>{
            let s=getComputedStyle(e),r=e.getBoundingClientRect();
            return ['fixed','sticky'].includes(s.position) && s.visibility!=='hidden' &&
                   s.display!=='none' && Number(s.opacity)!==0 &&
                   r.width>innerWidth*0.5 && r.height>innerHeight*0.35;
        }).length""")
        if overlays:
            result['reasons'].append('large_overlay_requires_review')
        if dims['height'] > 100000 or dims['width'] * dims['height'] > 100_000_000:
            result['reasons'].append('single_image_size_guard')
        else:
            page.screenshot(path=str(output / 'article.png'), full_page=True, timeout=30000)
            width, height = png_size(output / 'article.png')
            result['screenshot_dimensions'] = {'width': width, 'height': height}
            after = page.evaluate('document.documentElement.scrollHeight')
            if width < dims['width'] or height < max(dims['height'], after):
                result['reasons'].append('screenshot_dimensions_mismatch')
            result['screenshot_sha256'] = hashlib.sha256((output/'article.png').read_bytes()).hexdigest()
        result['status'] = 'complete' if not result['reasons'] else 'partial'
    except MVPError as exc:
        result['status'] = 'blocked'
        result['reasons'].append(str(exc))
    except Exception as exc:
        result['reasons'].append('page_operation_' + type(exc).__name__)
    finally:
        result['finished_at'] = timestamp()
        write_json(output / 'metadata.json', result)
    return result


def archive_article(item, output, start_at=None, headed=False, wait_readable=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        if wait_readable and not headed:
            raise MVPError('wait_requires_headed_browser')
        with sync_playwright() as driver:
            profile = ROOT / '.auth' / 'article'
            if profile.is_symlink() or profile.parent.is_symlink():
                raise MVPError('symlink_profile_rejected')
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            profile.chmod(0o700)
            context = driver.chromium.launch_persistent_context(str(profile), channel='chrome',
                headless=not headed, chromium_sandbox=True, viewport={'width':1100,'height':900},
                device_scale_factor=1, timezone_id='Asia/Shanghai', service_workers='block',
                env={k:v for k,v in os.environ.items() if k.upper() not in
                     {'SSLKEYLOGFILE','DEBUG','PWDEBUG','CHROME_LOG_FILE'}})
            try:
                def route(request_route):
                    from urllib.parse import urlsplit
                    p = urlsplit(request_route.request.url)
                    if any(x in p.path.lower() for x in ('comment', 'getreply', 'getappmsgext')):
                        request_route.abort()
                    elif p.scheme not in ('https', 'data', 'blob', 'about'):
                        request_route.abort()
                    else:
                        request_route.continue_()
                context.route('**/*', route)
                page = context.new_page()
                response = page.goto(item['url'], wait_until='domcontentloaded', timeout=30000)
                if response is None or response.status != 200:
                    raise MVPError('article_http_rejected')
                from urllib.parse import urlsplit
                if urlsplit(page.url).hostname != 'mp.weixin.qq.com':
                    raise MVPError('left_original_article_site')
                page.wait_for_timeout(1500)
                if wait_readable:
                    print('主人，项目文章窗口已打开；如出现验证，请正常完成。程序最多等待 300 秒，无需终端操作。', flush=True)
                    deadline = time.monotonic()+300
                    while time.monotonic()<deadline and not page.is_closed():
                        body = page.locator('#js_content')
                        if body.count() and body.is_visible() and body.inner_text().strip():
                            break
                        page.wait_for_timeout(500)
                    if page.is_closed():
                        raise MVPError('article_window_closed')
                return snapshot(page, item, output, start_at)
            finally:
                context.close()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, MVPError) else 'browser_' + type(exc).__name__
        result = {'status':'blocked','reasons':[reason],'source_url':item['url'],
                  'comments_status':'not_requested','finished_at':timestamp()}
        write_json(output/'metadata.json', result)
        return result
