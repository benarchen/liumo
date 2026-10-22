"""Offline artifact and ledger inspection. Never creates or updates state."""

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .rss import MVPError, canonical

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r'[0-9a-f]{24}')
DIGEST = re.compile(r'[0-9a-f]{64}')
MAX_METADATA = 1024 * 1024
MAX_LEDGER = 64 * 1024 * 1024


def safe_path(root, value):
    """Accept only descendants of an explicit root, with no symlink component."""
    root = Path(root).absolute()
    path = Path(value)
    if '..' in path.parts:
        raise MVPError('integrity_path_rejected')
    path = path if path.is_absolute() else root/path
    if not path.is_relative_to(root):
        raise MVPError('integrity_path_rejected')
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise MVPError('integrity_symlink_rejected')
    return path


def read_bytes(path, limit):
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise MVPError('integrity_size_limit')
    return data


def read_json(path, limit=MAX_METADATA):
    value = json.loads(read_bytes(path, limit))
    if not isinstance(value, dict):
        raise MVPError('integrity_invalid_json_shape')
    return value


def check_file(output, relative, digest, size=None, limit=25*1024*1024):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise MVPError('integrity_path_rejected')
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise MVPError('integrity_digest_unverifiable')
    data = read_bytes(safe_path(output, relative), limit)
    if hashlib.sha256(data).hexdigest() != digest or (size is not None and len(data) != size):
        raise MVPError('integrity_hash_mismatch')
    return data


def inspect_archive(output, *, root=None, key=None, kind=None):
    """Report integrity independently of the ledger's historical completion flag."""
    result = {'integrity_status':'unverifiable', 'reasons':[], 'checked_files':0}
    checking = 'metadata.json'
    try:
        output = Path(output).absolute()
        output = safe_path(root or Path(output).parent, output)
        meta = read_json(safe_path(output, 'metadata.json'))
        required = ('status','archive_kind','key','source_url','markdown_sha256','images')
        if any(name not in meta for name in required):
            raise MVPError('integrity_metadata_incomplete')
        if meta['status'] != 'complete' or meta.get('image_failures') or meta.get('reasons'):
            raise MVPError('integrity_snapshot_not_complete')
        if (meta['archive_kind'] not in ('rss_snapshot','manual_page_snapshot') or
                (kind is not None and meta['archive_kind'] != kind) or
                not isinstance(meta['key'],str) or not KEY.fullmatch(meta['key']) or
                (key is not None and key != meta['key'])):
            raise MVPError('integrity_identity_mismatch')
        if meta['archive_kind'] == 'rss_snapshot':
            biz = parse_qs(urlsplit(meta['source_url']).query).get('__biz',[None])[0]
            _, actual, _ = canonical(meta['source_url'], biz)
        else:
            identity = meta.get('identity', {})
            biz, mid, idx = (identity[name] for name in ('biz','mid','idx'))
            _, actual, normalized = canonical(
                'https://mp.weixin.qq.com/s?'+urlencode(
                    {'__biz':biz,'mid':mid,'idx':idx}), biz)
            if normalized != identity:
                raise MVPError('integrity_identity_mismatch')
            source = urlsplit(meta['source_url'])
            if source.scheme!='https' or source.netloc!='mp.weixin.qq.com' or source.fragment:
                raise MVPError('integrity_identity_mismatch')
            if re.fullmatch(r'/s/[A-Za-z0-9_-]{1,128}',source.path):
                if source.query:
                    raise MVPError('integrity_identity_mismatch')
            else:
                _, source_key, _ = canonical(meta['source_url'],biz)
                if source_key != actual:
                    raise MVPError('integrity_identity_mismatch')
        if actual != meta['key']:
            raise MVPError('integrity_identity_mismatch')
        if not isinstance(meta['images'],list) or len(meta['images']) > 25:
            raise MVPError('integrity_metadata_incomplete')
        checking = 'article.md'
        markdown = check_file(output,'article.md',meta['markdown_sha256'],limit=16*1024*1024).decode('utf-8')
        result['checked_files'] += 1
        if not markdown.strip():
            raise MVPError('integrity_empty_markdown')
        paths = set()
        for image in meta['images']:
            if (not isinstance(image,dict) or type(image.get('bytes')) is not int or image['bytes']<=0
                    or not isinstance(image.get('path'),str) or not image['path'].startswith('images/')):
                raise MVPError('integrity_metadata_incomplete')
            checking = str(safe_path(output,image['path']).relative_to(output))
            check_file(output,image['path'],image['sha256'],image['bytes'])
            result['checked_files'] += 1
            paths.add(image['path'])
        # Our renderer emits inline Markdown images with deterministic relative paths.
        checking = 'article.md'
        references = re.findall(r'!\[(?:\\.|[^\]])*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)',markdown)
        if set(references) != paths:
            raise MVPError('integrity_image_references_mismatch')
        result['integrity_status'] = 'intact'
    except FileNotFoundError:
        result.update(integrity_status='missing',reasons=['integrity_file_missing'])
    except MVPError as exc:
        code = str(exc)
        result.update(integrity_status='unverifiable' if code in {
            'integrity_metadata_incomplete','integrity_digest_unverifiable','integrity_snapshot_not_complete'
        } else 'corrupt',reasons=[code if code.startswith('integrity_') else 'integrity_identity_mismatch'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result.update(integrity_status='unverifiable',reasons=['integrity_metadata_or_read_failed'])
    if result['integrity_status'] != 'intact':
        result['affected_file'] = checking
    return result


def locations(scope, data_dir=None, archive_root=None):
    defaults = {'rss':('state/maobidao','archives/maobidao'),
                'manual':('state/manual','archives/manual'),
                'history':('state/history/maobidao','archives/history/maobidao')}
    if scope not in defaults:
        raise MVPError('integrity_scope_invalid')
    data, archives = defaults[scope]
    return Path(data_dir or ROOT/data).absolute(), Path(archive_root or ROOT/archives).absolute()


def read_ledger(scope, data):
    """Open SQLite read-only; do not use Store which initializes schemas/directories."""
    data = Path(data)
    name = {'rss':'state.sqlite3','manual':'index.json','history':'history.json'}[scope]
    path = safe_path(data,name)
    if not path.exists():
        return None, []
    if scope == 'rss':
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute('SELECT key,item,status,attempts,output FROM articles')]
        for row in rows:
            row['item'] = json.loads(row['item'])
        return {}, rows
    ledger = read_json(path,MAX_LEDGER)
    if ledger.get('version') != 1:
        raise MVPError('integrity_ledger_version')
    if scope == 'manual':
        rows = [{'key':key,'status':'complete','output':output}
                for key,output in ledger['articles'].items()]
    else:
        rows = [dict(row,key=key) for key,row in ledger['tasks'].items()]
    return ledger, rows


def verify_scope(scope, *, data_dir=None, archive_root=None):
    data, root = locations(scope,data_dir,archive_root)
    report = {'scope':scope,'status':'complete','at':datetime.now(timezone.utc).isoformat(),
              'entries':[],'unindexed':[],'reasons':[],'baseline_count':0}
    referenced = set()
    try:
        safe_path(root,root)
        _, rows = read_ledger(scope,data)
        for row in rows:
            key = row['key']
            if not isinstance(key,str) or not KEY.fullmatch(key):
                raise MVPError('integrity_ledger_key_invalid')
            if row['status'] in ('baseline','skipped_before_start'):
                report['baseline_count'] += 1
                continue
            entry = {'key':key,'ledger_status':row['status']}
            if not row.get('output'):
                entry.update(integrity_status='missing',reasons=['integrity_output_missing'],checked_files=0)
            else:
                try:
                    output = safe_path(root,row['output'])
                    referenced.add(str(output))
                    entry['output'] = str(output.relative_to(root))
                    entry.update(inspect_archive(output,root=root,key=key,
                        kind='manual_page_snapshot' if scope=='manual' else 'rss_snapshot'))
                except (MVPError, TypeError, ValueError):
                    entry.update(integrity_status='corrupt',reasons=['integrity_path_rejected'],checked_files=0)
            report['entries'].append(entry)
        # Exactly the supported <key>/<attempt> layout, without following symlinks.
        if root.exists():
            for article in sorted(root.iterdir()):
                if not KEY.fullmatch(article.name):
                    continue
                safe_path(root,article)
                if not article.is_dir():
                    continue
                for output in sorted(article.iterdir()):
                    safe_path(root,output)
                    if output.is_dir() and str(output) not in referenced:
                        report['unindexed'].append(str(output.relative_to(root)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error, MVPError):
        report['reasons'].append('integrity_ledger_or_inventory_unreadable')
    counts = {name:sum(x['integrity_status']==name for x in report['entries'])
              for name in ('intact','missing','corrupt','unverifiable')}
    report.update(counts=counts,checked=len(report['entries']),
                  empty=not report['entries'] and not report['unindexed'] and not report['reasons'])
    if report['reasons'] or any(counts[name] for name in ('missing','corrupt','unverifiable')):
        report['status'] = 'partial'
    if not report['entries'] and report['unindexed']:
        report['status'] = 'partial'
        report['reasons'].append('integrity_unindexed_only')
    return report


def verify(scope='all', *, data_dir=None, archive_root=None):
    if scope != 'all':
        return verify_scope(scope,data_dir=data_dir,archive_root=archive_root)
    if data_dir is not None or archive_root is not None:
        raise MVPError('integrity_all_custom_roots_rejected')
    reports = [verify_scope('rss'),verify_scope('manual')]
    history = ROOT/'state/history'
    history_archives = ROOT/'archives/history'
    try:
        names = set()
        for parent in (history,history_archives):
            safe_path(parent,parent)
            if parent.exists():
                for child in parent.iterdir():
                    safe_path(parent,child)
                    if child.is_dir():
                        names.add(child.name)
        for name in sorted(names):
            reports.append(verify_scope('history',data_dir=history/name,archive_root=history_archives/name))
        if not names:
            reports.append(verify_scope('history'))
    except (OSError,MVPError):
        reports.append({'scope':'history','status':'partial','reasons':['integrity_history_inventory_failed']})
    return {'status':'complete' if all(r['status']=='complete' for r in reports) else 'partial',
            'at':datetime.now(timezone.utc).isoformat(),'scopes':reports}
