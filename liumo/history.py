"""Explicit RSS history import with a separate, resumable local ledger."""

import base64
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from .common import ROOT, write_json
from .common import exclusive
from .rss import ACCOUNT, BIZ, FEED, MVPError, parse_feed, public_feed_url, read_public
from .rss_archive import archive_rss

MAX_BYTES = 32 * 1024 * 1024
MAX_ITEMS = 10000
SHANGHAI = ZoneInfo('Asia/Shanghai')


def date_range(start, end):
    try:
        if not all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) for value in (start, end)):
            raise ValueError
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last:
            raise ValueError
        return first, last
    except (ValueError, TypeError):
        raise MVPError('invalid_history_date_range') from None


def account_config(account, biz=None, feed_url=None):
    if not account or account.strip() != account or len(account) > 100 or any(ord(c) < 32 for c in account):
        raise MVPError('invalid_history_account')
    if account == ACCOUNT:
        if biz not in (None, BIZ):
            raise MVPError('history_account_biz_mismatch')
        biz = BIZ
    try:
        # WeChat biz is a base64 encoding of the numeric public account identity.
        if not biz or len(biz) > 100 or not base64.b64decode(biz, validate=True).decode('ascii').isdigit():
            raise ValueError
    except (ValueError, UnicodeError):
        raise MVPError('invalid_history_biz') from None
    if feed_url is not None and not public_feed_url(feed_url):
        raise MVPError('history_feed_url_rejected')
    slug = 'maobidao' if biz == BIZ else hashlib.sha256(biz.encode()).hexdigest()[:16]
    return {'account':account, 'biz':biz, 'slug':slug,
            'feed_url':feed_url or (FEED if account == ACCOUNT else None)}


def _feed_time(item):
    try:
        value = datetime.fromisoformat(item['feed_time'])
        return value.astimezone(SHANGHAI) if value.tzinfo else None
    except (TypeError, ValueError, KeyError, OverflowError):
        return None


def _signature(item):
    return tuple(item.get(k) for k in ('url', 'source_sha256', 'feed_time'))


def verify_archive(output, *, root=None, key=None):
    from .integrity import inspect_archive
    return bool(output) and inspect_archive(output,root=root,key=key,kind='rss_snapshot')['integrity_status']=='intact'


def import_history(account, start, end, *, biz=None, feed_url=None, rss_files=(),
                   resume=False, retry=False, limit=20, data_dir=None, archive_dir=None,
                   now=None, fetch=read_public, archiver=archive_rss):
    first, last = date_range(start, end)
    config = account_config(account, biz, feed_url)
    if not 1 <= limit <= 100 or len(rss_files) > 100 or (resume and (rss_files or feed_url)):
        raise MVPError('invalid_history_input')
    if not resume and not rss_files and not config['feed_url']:
        raise MVPError('history_source_required')
    now = now or datetime.now(timezone.utc)
    now_shanghai = now.astimezone(SHANGHAI)
    data = Path(data_dir) if data_dir else ROOT/'state/history'/config['slug']
    archive_root = Path(archive_dir) if archive_dir else ROOT/'archives/history'/config['slug']
    with exclusive(data/'run.lock'):
        path = data/'history.json'
        if path.exists():
            ledger = json.loads(path.read_text())
            if (ledger.get('version'), ledger.get('account'), ledger.get('biz')) != (1, account, config['biz']):
                raise MVPError('history_ledger_identity_mismatch')
        else:
            if resume:
                raise MVPError('history_resume_missing')
            ledger = {'version':1, 'account':account, 'biz':config['biz'], 'tasks':{}, 'sources':{}}
        # Validate every source before changing the ledger or downloading images.
        sources = []
        for source in rss_files:
            try:
                with Path(source).open('rb') as stream:
                    raw = stream.read(MAX_BYTES+1)
            except OSError:
                raise MVPError('history_source_read_failed') from None
            sources.append((raw, None))
        if not rss_files and not resume:
            sources.append((fetch(config['feed_url'], limit=MAX_BYTES), config['feed_url']))
        parsed = [(raw, url, parse_feed(raw, account, config['biz'], MAX_BYTES, MAX_ITEMS))
                  for raw, url in sources]
        imported = 0
        for raw, url, items in parsed:
            digest = hashlib.sha256(raw).hexdigest()
            snapshot = data/'sources'/(digest+'.xml')
            snapshot.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not snapshot.exists():
                with snapshot.open('xb') as stream:
                    stream.write(raw)
            elif hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
                raise MVPError('history_source_integrity_failed')
            source = {'sha256':digest, 'path':str(snapshot.resolve()), 'feed_url':url,
                      'observed_at':now.isoformat(), 'items':len(items)}
            ledger['sources'].setdefault(digest, source)
            for item in items:
                row = ledger['tasks'].get(item['key'])
                if row is None:
                    row = {'item':{**item, 'first_seen_at':now.isoformat()},
                           'status':'pending', 'attempts':0, 'sources':[], 'conflicts':[]}
                    ledger['tasks'][item['key']] = row
                    imported += 1
                elif _signature(row['item']) != _signature(item):
                    if digest not in row['conflicts']:
                        row['conflicts'].append(digest)
                if digest not in row['sources']:
                    row['sources'].append(digest)
        write_json(path, ledger)  # Persist input before the first archive attempt.
        matching, unknown, future, outside = [], [], [], 0
        for key, row in ledger['tasks'].items():
            value = _feed_time(row['item'])
            if value is None:
                unknown.append(key)
            elif not first <= value.date() <= last:
                outside += 1
            elif value > now_shanghai:
                future.append(key)
            else:
                matching.append(key)
        results = []
        damaged = {key for key in matching if ledger['tasks'][key]['status']=='complete'
                   and not verify_archive(ledger['tasks'][key].get('output'),root=archive_root,key=key)}
        candidates = [key for key in matching if (ledger['tasks'][key]['status'] != 'complete' or (retry and key in damaged))
                      and not ledger['tasks'][key]['conflicts']
                      and (retry or ledger['tasks'][key]['attempts'] < 3)]
        candidates.sort(key=lambda key:(ledger['tasks'][key]['attempts'],
                                       ledger['tasks'][key]['item']['feed_time'], key))
        for key in candidates[:limit]:
            row = ledger['tasks'][key]
            from .integrity import KEY, safe_path
            if not isinstance(key,str) or not KEY.fullmatch(key):
                raise MVPError('history_key_invalid')
            output = safe_path(archive_root,Path(key)/(now.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:12]))
            previous = row.get('output')
            if previous:
                row.setdefault('previous_outputs',[])
                if previous not in row['previous_outputs']:
                    row['previous_outputs'].append(previous)
            row.update(status='running', attempts=row['attempts']+1)
            row['attempt_output'] = str(output.resolve())
            write_json(path, ledger)
            origin = ledger['sources'][row['sources'][0]]
            selection = {'start':start, 'end':end, 'timezone':'Asia/Shanghai',
                         'date_basis':'rss_pubDate_unverified', 'source_sha256':origin['sha256']}
            try:
                options = {}
                if previous:
                    from .repair import cached_images
                    options['image_fetch'] = cached_images(row['item'],previous,archive_root)
                result = archiver(row['item'], output, account=account, biz=config['biz'],
                                  feed_source=origin['feed_url'] or origin['path'], history_selection=selection,**options)
                if result.get('status')=='complete' and not verify_archive(output,root=archive_root,key=key):
                    result = {'status':'partial','reasons':['history_post_write_integrity_failed']}
                if result.get('status') not in ('complete', 'partial', 'failed', 'blocked'):
                    raise MVPError('invalid_archive_result')
            except Exception:
                result = {'status':'failed', 'reasons':['history_archive_operation_failed']}
            row.update(status=result['status'], reasons=result.get('reasons', []))
            if row['status']=='complete' or not previous:
                row['output']=str(output.resolve())
            write_json(path, ledger)
            results.append({'key':key, 'status':row['status'], 'output':str(output.resolve()), 'reasons':row['reasons']})
            if row['status'] == 'blocked':
                break
        complete = [key for key in matching if ledger['tasks'][key]['status'] == 'complete']
        corrupt = [key for key in complete if not verify_archive(ledger['tasks'][key].get('output'),root=archive_root,key=key)]
        conflicts = [key for key in matching if ledger['tasks'][key]['conflicts']]
        outside_conflicts = [key for key, row in ledger['tasks'].items()
                             if row['conflicts'] and key not in matching]
        times = [_feed_time(row['item']) for row in ledger['tasks'].values()]
        times = [value for value in times if value is not None]
        unfinished = [key for key in matching if ledger['tasks'][key]['status'] != 'complete']
        report = {'status':'partial', 'maturity':'validated_rss_input', 'account':account, 'biz':config['biz'],
                  'request':{'start':start, 'end':end, 'timezone':'Asia/Shanghai', 'inclusive':True},
                  'date_basis':'rss_pubDate_unverified', 'original_times_verified':False,
                  'coverage':{'complete':False, 'reason':'source_inventory_not_verified',
                              'future_range_pending':last > now_shanghai.date(),
                              'earliest_feed_time':min(times).isoformat() if times else None,
                              'latest_feed_time':max(times).isoformat() if times else None},
                  'processing_status':'complete' if not (unfinished or unknown or future or conflicts or corrupt) else 'partial',
                  'imported':imported, 'source_snapshots':len(ledger['sources']),
                  'known_items':len(ledger['tasks']), 'matching':len(matching), 'outside_range':outside,
                  'complete':len(complete)-len(corrupt), 'unfinished':unfinished,
                  'unknown_time':unknown, 'future_time':future, 'source_conflicts':conflicts,
                  'outside_selection_conflicts':outside_conflicts,
                  'archive_integrity_failed':corrupt, 'results':results,
                  'needs_manual_retry':[key for key in unfinished if ledger['tasks'][key]['attempts'] >= 3],
                  'ledger':str(path.resolve()), 'at':now.isoformat()}
        report_path = data/'reports'/(now.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:12]+'.json')
        report['report_path'] = str(report_path.resolve())
        write_json(report_path, report)
        write_json(data/'last-report.json', report)
        return report
