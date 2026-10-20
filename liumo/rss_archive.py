"""Archive only the content provided by the public feed, with explicit provenance."""

import hashlib
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from validation.archive import render_markdown
from validation.common import timestamp, write_json
from .rss import ACCOUNT, FEED, MVPError, canonical, read_image


def archive_rss(item, output, start_at=None, image_fetch=read_image):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    result={'status':'failed','archive_kind':'rss_snapshot','account':ACCOUNT,
            'source_url':item['url'],'feed_source':FEED,'title':item['title'],'key':item['key'],
            'first_seen_at':item.get('first_seen_at'),'feed_time_candidate':item.get('feed_time'),
            'original_publication_time':None,'publication_time_verified':False,
            'body_completeness':'as_provided_by_feed_unverified_against_original',
            'screenshot':{'status':'deferred'},'comments_status':'not_requested',
            'started_at':timestamp(),'reasons':[]}
    try:
        _,key,identity=canonical(item['url'])
        if key!=item['key'] or identity!=item['identity']:
            raise MVPError('rss_article_identity_mismatch')
        if not item.get('first_seen_at'):
            raise MVPError('first_seen_missing')
        if start_at and datetime.fromisoformat(item['first_seen_at'])<datetime.fromisoformat(start_at):
            result['status']='skipped_before_start'
            return result
        html=item.get('body_html','')
        soup=BeautifulSoup(html,'html.parser')
        if not soup.get_text(strip=True):
            raise MVPError('rss_body_missing')
        if len(soup.select('img'))>25:
            raise MVPError('body_image_budget_exceeded')
        # No browser, account profile, original page request or executed HTML/JS.
        result['status']='partial'
        failures=[]
        def fetch(url):
            try:
                return image_fetch(url,limit=25*1024*1024)
            except MVPError as exc:
                failures.append(str(exc))
                raise
        result.update(render_markdown(html,item['title'],item['url'],output,fetch))
        result['image_transport_reasons']=failures
        path=output/'article.md'
        markdown=path.read_text()
        heading,_,body=markdown.partition('\n')
        provenance=(f'\n> 保存类型：RSS 内容快照。原文发布时间待核实；原页截图暂缓。\n'
                    f'> 原文链接：{item["url"]}\n'
                    f'> 首次发现时间：{item["first_seen_at"]}\n')
        path.write_text(heading+'\n'+provenance+'\n'+body.lstrip(),encoding='utf-8')
        result['markdown_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result['rss_body_sha256']=hashlib.sha256(html.encode()).hexdigest()
        if result['image_failures']:
            result['reasons'].append('images_incomplete')
        result['status']='complete' if not result['reasons'] else 'partial'
    except MVPError as exc:
        result['reasons'].append(str(exc))
    except Exception as exc:
        result['reasons'].append('rss_archive_'+type(exc).__name__)
    finally:
        result['finished_at']=timestamp()
        write_json(output/'metadata.json',result)
    return result
