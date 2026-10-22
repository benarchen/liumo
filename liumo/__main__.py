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
    parser = argparse.ArgumentParser(description='留墨：RSS 自动追更与按公众号、日期导入历史。')
    sub = parser.add_subparsers(dest='command', required=True)
    manual = sub.add_parser('save', help='立即归档任意微信公众号文章链接，不等待 RSS。')
    manual.add_argument('url', help='微信公众号公开文章的 HTTPS 短链或长链。')
    manual.add_argument('--refresh', action='store_true', help='重新读取并保留新快照，不覆盖旧结果。')
    manual.add_argument('--headless', action='store_true', help='不显示浏览器，遇验证立即报告。')
    manual.add_argument('--wait-seconds', type=int, metavar='0..300', default=180,
                        help='有界面时等待正常验证的秒数，默认 180。')
    history = sub.add_parser('history', help='按上海日期范围显式保存 RSS 历史快照。')
    history.add_argument('--account', required=True, help='公众号名称，首个预置为猫笔刀。')
    history.add_argument('--biz', help='其他公众号必填的公开 __biz 身份。')
    history.add_argument('--start', required=True, help='起始日期 YYYY-MM-DD，包含当天。')
    history.add_argument('--end', required=True, help='结束日期 YYYY-MM-DD，包含当天。')
    source = history.add_mutually_exclusive_group()
    source.add_argument('--feed-url', help='公开 Wechat2RSS XML 地址。猫笔刀可省略。')
    source.add_argument('--rss-file', type=Path, action='append', default=[], help='本地 RSS XML，可重复传入。')
    source.add_argument('--resume', action='store_true', help='只用已保存的本地输入续跑，不请求 RSS。')
    history.add_argument('--retry', action='store_true', help='显式重试已达到 3 次的失败任务。')
    history.add_argument('--limit', type=int, choices=range(1, 101), default=20, help='本次最多处理篇数，默认 20。')
    history.add_argument('--data-dir', type=Path, help='历史任务本机状态目录。')
    history.add_argument('--archive-dir', type=Path, help='历史快照输出目录。')
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
        if args.command == 'save':
            from .manual import save_article
            result = save_article(args.url, refresh=args.refresh, headless=args.headless,
                                  wait_seconds=args.wait_seconds)
        elif args.command == 'history':
            from .history import import_history
            result = import_history(args.account, args.start, args.end, biz=args.biz,
                                    feed_url=args.feed_url, rss_files=args.rss_file,
                                    resume=args.resume, retry=args.retry, limit=args.limit,
                                    data_dir=args.data_dir, archive_dir=args.archive_dir)
        elif args.command == 'source':
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
