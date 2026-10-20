"""Small CLI; no implicit history import, login or system changes."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from validation.common import ROOT, timestamp
from validation.state import exclusive
from .rss_archive import archive_rss
from .rss import FEED, MVPError, discover
from .runner import ARCHIVES, DATA, render_plist, run
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='留墨：猫笔刀单号 RSS 归档。')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'check', 'retry', 'tick', 'status', 'source', 'sample', 'page-sample', 'plist'):
        cmd = sub.add_parser(name)
        if name in ('init', 'check', 'retry', 'tick', 'status', 'plist'):
            cmd.add_argument('--data-dir', type=Path, default=DATA)
        if name in ('check', 'retry', 'tick'):
            cmd.add_argument('--limit', type=int, choices=range(1, 6), default=3)
        if name == 'page-sample':
            cmd.add_argument('--headed', action='store_true')
            cmd.add_argument('--wait-readable', action='store_true')
        if name == 'plist':
            cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'source':
            items = discover()
            result = {'status':'complete','feed':FEED,'items':[{k:v for k,v in x.items() if k!='body_html'} for x in items],
                      'original_times_verified':False}
        elif args.command in ('sample','page-sample'):
            item = {**discover()[0],'first_seen_at':timestamp()}
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            output = ROOT/'archives/mvp-samples'/stamp
            if args.command == 'page-sample':
                from .archive import archive_article
                saved=archive_article(item,output,headed=args.headed,wait_readable=args.wait_readable)
            else:
                saved=archive_rss(item,output)
            result = {'output':str(output),'technical_sample_only':True,**saved}
        elif args.command == 'plist':
            result = render_plist(args.output, args.data_dir)
        elif args.command in ('init', 'status'):
            if args.command == 'status' and not (args.data_dir/'state.sqlite3').is_file():
                print(json.dumps({'status':'not_initialized','comments_status':'not_requested'}, ensure_ascii=False))
                return 2
            with exclusive(args.data_dir/'run.lock'):
                store = Store(args.data_dir)
                try:
                    if args.command == 'init':
                        if store.get('start_at'):
                            raise MVPError('already_initialized')
                        items = discover()  # Observe before setting the activation time.
                        store.initialize(items, timestamp())
                    result = {'status':'complete' if store.get('start_at') else 'not_initialized', **store.summary()}
                finally:
                    store.close()
        else:
            result = run(args.data_dir, ARCHIVES, scheduled=args.command=='tick',
                         retry=args.command=='retry', limit=args.limit)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, MVPError) or (isinstance(exc, RuntimeError) and str(exc)=='already_running') else 'operation_' + type(exc).__name__
        result = {'status':'failed','reason':reason}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') in ('complete','idle') else 2


if __name__ == '__main__':
    raise SystemExit(main())
