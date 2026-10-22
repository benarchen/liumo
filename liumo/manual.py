"""User-supplied WeChat articles, separate from feeds and their state."""

import base64
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from playwright.sync_api import sync_playwright

from validation.archive import (image_node_observations, render_markdown,
                                scroll_document, select_markdown_body)
from validation.common import ROOT, timestamp, write_json
from validation.state import exclusive
from .archive import publication
from .rss import MVPError, read_image

DATA = ROOT/'state/manual'
ARCHIVES = ROOT/'archives/manual'
PROFILE = ROOT/'.auth/manual-article'
PRIVATE_QUERY = {'uin', 'key', 'pass_ticket', 'wap_sid2', 'appmsg_token', 'wxtoken', 'poc_token',
                 'access_token','token','authorization'}


def identity(biz, mid, idx):
    try:
        if (not isinstance(biz, str) or len(biz)>256 or
                not base64.b64decode(biz, validate=True).isdigit() or
                not re.fullmatch(r'[0-9]{1,20}', str(mid)) or int(mid)<=0 or
                not re.fullmatch(r'[0-9]{1,3}', str(idx)) or not 1<=int(idx)<=100):
            raise ValueError
        return {'biz':biz, 'mid':str(int(mid)), 'idx':str(int(idx))}
    except (ValueError, TypeError):
        raise MVPError('manual_article_identity_invalid') from None


def article_key(value):
    return hashlib.sha256(f"{value['biz']}:{value['mid']}:{value['idx']}".encode()).hexdigest()[:24]


def normalize_url(value):
    """Public article identity only; never accept a login URL or credential query."""
    try:
        if not isinstance(value,str) or len(value)>8192 or any(ord(c)<32 for c in value):
            raise ValueError
        p=urlsplit(html.unescape(value.strip()))
        if p.scheme!='https' or p.netloc!='mp.weixin.qq.com' or p.username or p.password:
            raise ValueError
        q=parse_qs(p.query,keep_blank_values=True,strict_parsing=True)
        if any(k.lower() in PRIVATE_QUERY for k in q) or any(len(v)!=1 for v in q.values()):
            raise ValueError
        if re.fullmatch(r'/s/[A-Za-z0-9_-]{1,128}',p.path):
            return urlunsplit(('https','mp.weixin.qq.com',p.path,'','')), None
        if p.path!='/s' or not all(q.get(k) for k in ('__biz','mid','idx','sn')):
            raise ValueError
        expected=identity(q['__biz'][0],q['mid'][0],q['idx'][0])
        if not re.fullmatch(r'[0-9a-f]{32}',q['sn'][0]):
            raise ValueError
        fields={'__biz':expected['biz'],'mid':expected['mid'],'idx':expected['idx'],'sn':q['sn'][0]}
        return 'https://mp.weixin.qq.com/s?'+urlencode(fields), expected
    except (ValueError,TypeError,MVPError):
        raise MVPError('manual_public_article_url_required') from None


def capture_page(page, url):
    """Read only selected public page fields; no raw script/HTML snapshot on disk."""
    public=page.evaluate("""() => {
        const text=s=>document.querySelector(s)?.innerText.trim() || '';
        const value=(v)=>v==null?null:String(v);
        return {title:text('#activity-name'), account:text('#js_name') || text('.wx_follow_nickname'),
            biz:typeof biz==='undefined'?null:value(biz),
            mid:typeof mid!=='undefined'?value(mid):(typeof appmsgid==='undefined'?null:value(appmsgid)),
            idx:typeof idx==='undefined'?null:value(idx),
            epoch:typeof ct==='undefined'?null:value(ct),
            paid:typeof is_pay_subscribe==='undefined'?null:value(is_pay_subscribe),
            time:text('#publish_time'), time_title:document.querySelector('#publish_time')?.getAttribute('title') || ''};
    }""")
    if public['paid'] in {'1','true'}:
        raise MVPError('manual_paid_content_not_verified')
    actual=identity(public.pop('biz'),public.pop('mid'),public.pop('idx'))
    _,expected=normalize_url(url)
    if expected is not None and actual!=expected:
        raise MVPError('manual_article_identity_mismatch')
    if not public['title'] or len(public['title'])>500 or not public['account'] or len(public['account'])>500:
        raise MVPError('manual_article_fields_missing')
    body=page.locator('#js_content')
    if not body.count() or not body.is_visible() or not body.inner_text().strip():
        raise MVPError('manual_visible_body_missing')
    nodes=image_node_observations(body)
    selected=select_markdown_body(body)
    if len(selected['html'].encode())>10*1024*1024 or len(selected['retained_image_indices'])>25:
        raise MVPError('manual_body_size_limit')
    published=None
    try:
        published=publication(public['epoch'],public['time_title'] or public['time'])
    except MVPError:
        pass
    return {'title':public['title'],'account':public['account'],'identity':actual,
            'published_at':published,'publication_time_verified':published is not None,
            'body_html':selected.pop('html'),'selection':selected,'image_nodes':nodes}


def _private_directory(path):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise MVPError('manual_symlink_directory_rejected')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.chmod(0o700)


def load_page(url, *, headless=False, wait_seconds=180):
    """One normal navigation, optional human verification, no request replay."""
    _private_directory(PROFILE.parent)
    _private_directory(PROFILE)
    with sync_playwright() as driver:
        context=driver.chromium.launch_persistent_context(str(PROFILE),channel='chrome',
            headless=headless,chromium_sandbox=True,viewport={'width':1100,'height':900},
            timezone_id='Asia/Shanghai',service_workers='block',
            env={k:v for k,v in os.environ.items() if k.upper() not in
                 {'SSLKEYLOGFILE','DEBUG','PWDEBUG','CHROME_LOG_FILE'}})
        denied=0
        def route(request_route):
            nonlocal denied
            request=request_route.request
            p=urlsplit(request.url);host=p.hostname or ''
            comments=any(x in p.path.lower() for x in ('comment','getreply','getappmsgext'))
            allowed=host=='mp.weixin.qq.com' or host.endswith(('.qpic.cn','.qlogo.cn','.wx.qq.com',
                '.weixin.qq.com','.captcha.qq.com','.captcha.qcloud.com','.gtimg.com','.idqqimg.com'))
            top=request.is_navigation_request() and request.frame==page.main_frame
            if comments or (p.scheme not in {'https','data','blob','about'}) or (p.scheme=='https' and not allowed) or (top and host!='mp.weixin.qq.com'):
                denied+=1;request_route.abort()
            else:
                headers=request.headers
                if host!='mp.weixin.qq.com':
                    headers={k:v for k,v in headers.items() if k.lower() not in {'cookie','authorization'}}
                request_route.continue_(headers=headers)
        try:
            page=context.new_page()
            context.route('**/*',route)
            page.goto(url,wait_until='domcontentloaded',timeout=30000)
            deadline=time.monotonic()+(0 if headless else wait_seconds)
            prompted=False
            while True:
                if page.is_closed():
                    raise MVPError('manual_window_closed')
                p=urlsplit(page.url)
                if p.scheme!='https' or p.netloc!='mp.weixin.qq.com':
                    raise MVPError('manual_left_article_site')
                text=page.locator('body').inner_text(timeout=10000)
                if any(x in text for x in ('该内容已被发布者删除','此内容因违规无法查看','内容已删除','无权查看')):
                    raise MVPError('manual_article_unavailable')
                body=page.locator('#js_content')
                if body.count() and body.is_visible() and body.inner_text().strip():
                    break
                if time.monotonic()>=deadline:
                    raise MVPError('manual_verification_required' if ('验证' in text or 'captcha' in p.path or '环境异常' in text) else 'manual_visible_body_missing')
                if not prompted:
                    print('主人，如文章窗口要求验证，请正常完成；程序会等待，不会自动操作验证码。会话仅存于项目 .auth/manual-article/。',file=sys.stderr,flush=True)
                    prompted=True
                page.wait_for_timeout(500)
            scroll=scroll_document(page)
            payload=capture_page(page,url)
            try:
                _,final_expected=normalize_url(page.url)
            except MVPError:
                raise MVPError('manual_unexpected_article_destination') from None
            if final_expected and final_expected!=payload['identity']:
                raise MVPError('manual_article_identity_mismatch')
            payload.update(scroll=scroll,blocked_requests=denied)
            return payload
        finally:
            context.close()


def _artifact(root, relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise MVPError('manual_index_path_rejected')
    result=Path(root)/p
    if (not result.resolve().is_relative_to(Path(root).resolve()) or
            any((Path(root)/Path(*p.parts[:i])).is_symlink() for i in range(len(p.parts)+1))):
        raise MVPError('manual_index_path_rejected')
    return result


def _cached(root, relative):
    if not isinstance(relative,str):
        return None
    try:
        output=_artifact(root,relative)
        meta_path=output/'metadata.json'
        if meta_path.is_symlink() or meta_path.stat().st_size>1024*1024:
            return None
        result=json.loads(meta_path.read_text())
        if result['status']!='complete':
            return None
        md=output/'article.md'
        if md.is_symlink() or hashlib.sha256(md.read_bytes()).hexdigest()!=result['markdown_sha256']:
            return None
        for im in result['images']:
            p=_artifact(output,im['path'])
            if p.stat().st_size!=im['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=im['sha256']:
                return None
        return {**result,'output':str(output)}
    except (OSError,ValueError,KeyError,TypeError,MVPError):
        return None


def save_article(url, *, refresh=False, headless=False, wait_seconds=180,
                 data_dir=DATA, archive_root=ARCHIVES, loader=None, image_fetch=read_image):
    url,expected=normalize_url(url)
    if type(wait_seconds) is not int or not 0<=wait_seconds<=300:
        raise MVPError('manual_wait_out_of_range')
    data_dir,archive_root=Path(data_dir),Path(archive_root)
    _private_directory(data_dir);_private_directory(archive_root)
    with exclusive(data_dir/'run.lock'):
        state_path=data_dir/'index.json'
        try:
            if state_path.is_symlink() or (state_path.exists() and state_path.stat().st_size>4*1024*1024):
                raise ValueError
            state=json.loads(state_path.read_text()) if state_path.exists() else {'version':1,'articles':{},'aliases':{}}
            if state.get('version')!=1 or not isinstance(state.get('articles'),dict) or not isinstance(state.get('aliases'),dict):
                raise ValueError
        except (OSError,ValueError,AttributeError):
            raise MVPError('manual_index_invalid') from None
        known=article_key(expected) if expected else state['aliases'].get(url)
        previous=_cached(archive_root,state['articles'].get(known))
        if previous and previous.get('key')!=known:
            previous=None
        if previous and not refresh:
            return {**previous,'reused':True}
        request_key=hashlib.sha256(url.encode()).hexdigest()[:24]
        relative=f"{request_key}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        output=_artifact(archive_root,relative)
        output.mkdir(parents=True,exist_ok=False,mode=0o700)
        result={'status':'failed','archive_kind':'manual_page_snapshot','source_url':url,
                'started_at':timestamp(),'comments_status':'not_requested','screenshot':{'status':'deferred'},
                'reused':False,'reasons':[]}
        try:
            payload=(loader or load_page)(url,headless=headless,wait_seconds=wait_seconds)
            actual=identity(**payload['identity'])
            if expected and expected!=actual:
                raise MVPError('manual_article_identity_mismatch')
            key=article_key(actual)
            previous=_cached(archive_root,state['articles'].get(key))
            if previous and previous.get('key')!=key:
                previous=None
            state['aliases'][url]=key
            if previous and not refresh:
                result.update(status='duplicate',key=key,existing_output=previous['output'])
                write_json(state_path,state)
                return {**previous,'reused':True,'alias_attempt':str(output)}
            result.update({k:v for k,v in payload.items() if k not in {'body_html','image_nodes','identity'}})
            result.update(identity=actual,key=key)
            selected=payload['selection']
            result.update(render_markdown(payload['body_html'],payload['title'],url,output,
                lambda image:image_fetch(image,limit=25*1024*1024),payload['image_nodes'],selected['retained_image_indices']))
            for failure in result['image_failures']:
                failure.pop('source_host',None)
            path=output/'article.md'
            heading,_,body=path.read_text().partition('\n')
            provenance=(f'\n> 保存类型：用户指定链接的原文正文快照。\n> 公众号：{payload["account"]}\n'
                        f'> 原文链接：{url}\n> 保存时间：{result["started_at"]}\n'
                        '> 评论未读取，原页截图暂缓。\n')
            path.write_text(heading+'\n'+provenance+'\n'+body.lstrip())
            result['markdown_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            if not payload['scroll']['bottom_reached']:
                result['reasons'].append('manual_page_bottom_not_reached')
            if result['image_failures']:
                result['reasons'].append('manual_images_incomplete')
            if previous:
                result.update(previous_output=previous['output'],body_changed=previous['body_sha256']!=result['body_sha256'])
            result['status']='partial' if result['reasons'] else 'complete'
            if result['status']=='complete':
                state['articles'][key]=relative
            write_json(state_path,state)
        except MVPError as exc:
            result['status']='blocked';result['reasons'].append(str(exc))
        except Exception as exc:
            result['status']='partial' if (output/'article.md').is_file() else 'failed'
            result['reasons'].append('manual_operation_'+type(exc).__name__)
        finally:
            result['finished_at']=timestamp()
            write_json(output/'metadata.json',result)
        return {**result,'output':str(output)}
