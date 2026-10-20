"""A bounded check and a lightweight Beijing-time gate; no background installation."""

import plistlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from validation.common import ROOT, timestamp, write_json
from validation.notify import notify
from validation.schedule import latest_slot, next_slot
from validation.state import exclusive
from .rss_archive import archive_rss as archive_article
from .rss import MVPError, discover
from .store import Store

DATA = ROOT/'state/maobidao'
ARCHIVES = ROOT/'archives/maobidao'


def due(now, last_attempt, retry_at=None):
    if last_attempt is None:
        return True, 'initial_check'
    last = datetime.fromisoformat(last_attempt)
    if now < last:
        return False, 'clock_moved_backwards'
    if retry_at:
        return (True, 'recovery_coalesced') if now >= datetime.fromisoformat(retry_at) else (False, 'failure_backoff')
    return (True, 'scheduled_or_missed_coalesced') if latest_slot(now) > last else (False, 'not_due')


def check(store, now, archive_root=ARCHIVES, source=discover, archiver=archive_article, retry=False,
          limit=3, sender=notify):
    if not store.get('start_at'):
        raise MVPError('initialize_first')
    with store.db:
        store.put('last_attempt', now.isoformat())
    try:
        items = source()
        report = store.ingest(items, now.isoformat())
    except Exception as exc:
        reason = str(exc) if isinstance(exc, MVPError) else 'source_operation_failed'
        with store.db:
            failures = store.get('network_failures', 0) + 1
            store.put('network_failures', failures)
            transient = reason in {'public_transport_failed','public_service_unavailable'}
            store.put('source_blocked', None if transient else reason)
            store.put('next_retry_at', (now+timedelta(minutes=min(360, 15*2**min(failures-1, 5)))).isoformat() if transient else None)
            store.put('last_outcome', {'status':'failed','reason':reason})
        report = {'status':'failed','reason':reason,'feed_read':False}
        report['notification'] = sender('failed', 0)
        return report
    with store.db:
        store.put('network_failures', 0)
        store.put('next_retry_at', None)
        store.put('source_blocked', None)
    results = []
    for row in store.tasks(retry=retry, limit=limit):
        output = Path(archive_root)/row['key']/(now.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
        store.begin(row['key'], output)
        try:
            result = archiver(row['item'], output, start_at=store.get('start_at'))
        except Exception:
            result = {'status':'failed','reasons':['archive_operation_failed']}
        store.finish(row['key'], result, output)
        results.append({'key':row['key'],'status':result['status'],'output':str(output),
                        'reasons':result.get('reasons', [])})
        if result['status'] == 'blocked':
            break  # Do not probe more article pages after an access/identity refusal.
    unfinished = any(r['status'] not in ('complete','skipped_before_start') for r in results)
    outstanding = store.db.execute("SELECT count(*) FROM articles WHERE status IN ('pending','running','partial','failed','blocked')").fetchone()[0]
    report.update(status='partial' if unfinished or outstanding or report['feed_issues'] else 'complete',
                  results=results, pending_or_failed=outstanding, feed_read=True)
    complete = sum(r['status']=='complete' for r in results)
    if results or report['status'] != 'complete':
        report['notification'] = sender('partial' if report['status']=='partial' else 'complete', complete)
    else:
        report['notification'] = {'notification':'not_needed','event':'no_new_articles'}
    with store.db:
        store.put('last_outcome', {k:report[k] for k in ('status','feed_items','discovered','pending_or_failed')})
    return report


def run(data=DATA, archive_root=ARCHIVES, scheduled=False, retry=False, now=None, **kwargs):
    now = now or datetime.now(timezone.utc)
    with exclusive(Path(data)/'run.lock'):
        store = Store(data)
        try:
            if not store.get('start_at'):
                raise MVPError('initialize_first')
            if scheduled:
                should, reason = due(now, store.get('last_attempt'), store.get('next_retry_at'))
                if not should:
                    return {'status':'idle','reason':reason,'next_slot':next_slot(now).isoformat()}
            if not retry and (store.get('article_blocked') or store.get('source_blocked')):
                return {'status':'blocked','reason':'access_or_source_requires_review'}
            result = check(store, now, archive_root, retry=retry, **kwargs)
            with store.db:
                blocked = any(r['status']=='blocked' for r in result.get('results', []))
                if blocked:
                    store.put('article_blocked', True)
                elif retry:
                    remaining = store.db.execute("SELECT count(*) FROM articles WHERE status='blocked'").fetchone()[0]
                    store.put('article_blocked', bool(remaining))
            write_json(Path(data)/'last-run.json', {'at':timestamp(), **result})
            return result
        finally:
            store.close()


def render_plist(output, data=DATA):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {'Label':'local.liumo.maobidao',
               'ProgramArguments':[str(ROOT/'.venv/bin/python'),'-m','liumo','tick','--data-dir',str(Path(data).resolve())],
               'WorkingDirectory':str(ROOT),'RunAtLoad':True,'StartCalendarInterval':{},
               'StandardOutPath':str(Path(data).resolve()/'scheduler.log'),
               'StandardErrorPath':str(Path(data).resolve()/'scheduler-error.log')}
    with output.open('xb') as stream:
        stream.write(plistlib.dumps(payload, sort_keys=False))
    return {'path':str(output),'installed':False,'timezone':'Asia/Shanghai'}
