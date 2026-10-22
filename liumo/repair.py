"""Explicit single-key repair; preserve all snapshots and publish only verified output."""

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from bs4 import BeautifulSoup

from .common import write_json
from .common import exclusive
from .integrity import (KEY, check_file, inspect_archive, locations, read_json,
                        read_ledger, safe_path)
from .rss import ACCOUNT, BIZ, MVPError, canonical, read_image
from .rss_archive import archive_rss


def cached_images(item, previous, root, fallback=read_image):
    """Reuse verified images only when the saved HTML fingerprint proves index mapping."""
    cache = {}
    try:
        previous = safe_path(root,previous)
        meta = read_json(safe_path(previous,'metadata.json'))
        if (meta.get('key') != item['key'] or meta.get('archive_kind') != 'rss_snapshot' or
                meta.get('rss_body_sha256') != hashlib.sha256(item['body_html'].encode()).hexdigest()):
            raise MVPError('repair_image_mapping_unverified')
        soup = BeautifulSoup(item['body_html'],'html.parser')
        for tag in soup.select('script,style,iframe,object,embed'):
            tag.decompose()
        tags = soup.select('img')
        for image in meta.get('images',[]):
            try:
                index = image['index']
                if type(index) is not int or not 0 <= index < len(tags):
                    continue
                source = tags[index].get('data-src') or tags[index].get('src')
                if source:
                    cache[urljoin(item['url'],source)] = check_file(previous,image['path'],
                        image['sha256'],image['bytes'])
            except (OSError,KeyError,TypeError,ValueError,MVPError):
                continue
    except (OSError,KeyError,TypeError,ValueError,MVPError):
        pass
    def fetch(url, limit=25*1024*1024):
        if url in cache:
            if len(cache[url]) > limit:
                raise MVPError('response_size_limit')
            return cache[url]
        return fallback(url,limit=limit)
    return fetch


def repair(scope, key, *, data_dir=None, archive_root=None, archiver=archive_rss,
           image_fetch=read_image, loader=None, headless=False, wait_seconds=180):
    if not isinstance(key,str) or not KEY.fullmatch(key):
        raise MVPError('repair_key_invalid')
    data, root = locations(scope,data_dir,archive_root)
    safe_path(data,data);safe_path(root,root)
    if scope == 'manual':
        # save_article owns the same lock and validates identity before publishing its index.
        from .manual import save_article
        safe_path(data,'index.json')
        if not (data/'index.json').is_file():
            raise MVPError('repair_key_not_found')
        return save_article(None,data_dir=data,archive_root=root,loader=loader,image_fetch=image_fetch,
            headless=headless,wait_seconds=wait_seconds,repair_key=key)
    name = 'state.sqlite3' if scope=='rss' else 'history.json'
    if not safe_path(data,name).is_file():
        raise MVPError('repair_key_not_found')
    safe_path(data,'run.lock')
    safe_path(data,name+'.tmp')
    with exclusive(data/'run.lock'):
        ledger, rows = read_ledger(scope,data)
        row = next((r for r in rows if r['key']==key),None)
        if row is None or row['status'] in ('baseline','skipped_before_start'):
            raise MVPError('repair_key_not_archived')
        previous = safe_path(root,row['output']) if row.get('output') else None
        if previous and inspect_archive(previous,root=root,key=key,kind='rss_snapshot')['integrity_status']=='intact':
            return {'status':'complete','key':key,'reused':True,'output':str(previous)}
        item = row.get('item',{})
        biz = BIZ if scope=='rss' else ledger['biz']
        _, item_key, identity = canonical(item.get('url'),biz)
        if item_key!=key or item.get('key')!=key or item.get('identity')!=identity:
            raise MVPError('repair_source_identity_mismatch')
        if not isinstance(item.get('body_html'),str) or not item['body_html'].strip():
            return {'status':'unrecoverable','key':key,'reasons':['repair_source_unavailable']}
        if scope=='history' and row.get('conflicts'):
            return {'status':'unrecoverable','key':key,'reasons':['repair_source_conflict']}
        now = datetime.now(timezone.utc)
        attempt = now.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:12]
        output = safe_path(root,Path(key)/attempt)
        receipt_path = safe_path(data,Path('repair-attempts')/(attempt+'.json'))
        receipt_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        receipt = {'status':'running','scope':scope,'key':key,'previous_output':str(previous) if previous else None,
                   'output':str(output),'started_at':now.isoformat()}
        old_body_digest = None
        try:
            old_meta = read_json(safe_path(previous,'metadata.json')) if previous else {}
            if old_meta.get('key') == key:
                old_body_digest = old_meta.get('rss_body_sha256')
        except (OSError,ValueError,TypeError,MVPError):
            pass
        write_json(receipt_path,receipt)
        kwargs = {'account':ACCOUNT if scope=='rss' else ledger['account'],'biz':biz,
                  'image_fetch':cached_images(item,previous,root,image_fetch) if previous else image_fetch}
        if scope=='history':
            try:
                origin = ledger['sources'][row['sources'][0]]
                kwargs['feed_source'] = origin.get('feed_url') or origin['path']
                old = read_json(safe_path(previous,'metadata.json')) if previous else {}
                if old.get('history_selection'):
                    kwargs['history_selection'] = old['history_selection']
            except (OSError,ValueError,TypeError,KeyError,MVPError):
                # History provenance in the retained ledger remains available even if metadata was lost.
                kwargs['feed_source'] = 'retained_history_ledger'
        try:
            result = archiver(item,output,**kwargs)
            receipt['body_changed'] = (old_body_digest != result.get('rss_body_sha256')
                                       if old_body_digest is not None else None)
            integrity = inspect_archive(output,root=root,key=key,kind='rss_snapshot')
            if result.get('status')=='complete' and integrity['integrity_status']=='intact':
                if scope=='rss':
                    # Existing schema only; lock excludes the running scheduler.
                    with closing(sqlite3.connect((data/'state.sqlite3').as_uri()+'?mode=rw',uri=True)) as db:
                        with db:
                            db.execute('UPDATE articles SET status=?,attempts=attempts+1,reason=?,output=? WHERE key=?',
                                ('complete','',str(output),key))
                else:
                    task = ledger['tasks'][key]
                    task.setdefault('previous_outputs',[]).append(task.get('output'))
                    task.update(status='complete',attempts=task['attempts']+1,output=str(output),reasons=[])
                    write_json(data/'history.json',ledger)
                receipt.update(status='complete',integrity=integrity)
            else:
                receipt.update(status='partial',reasons=['repair_output_not_complete'],integrity=integrity)
        except Exception:
            receipt.update(status='failed',reasons=['repair_operation_failed'])
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_json(receipt_path,receipt)
        return receipt
