"""Small transactional task ledger; feed observations never discard unfinished work."""

import json
import sqlite3
from pathlib import Path

from .rss import MVPError


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(directory/'state.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS articles (
                key TEXT PRIMARY KEY, item TEXT NOT NULL, observed_at TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                reason TEXT, output TEXT, published_at TEXT);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def initialize(self, items, now):
        if self.get('start_at'):
            raise MVPError('already_initialized')
        with self.db:
            for item in items:
                item = {**item,'first_seen_at':now}
                self.db.execute('INSERT OR IGNORE INTO articles(key,item,observed_at,status) VALUES (?,?,?,?)',
                                (item['key'], json.dumps(item, ensure_ascii=False), now, 'baseline'))
            self.put('last_feed_keys', [x['key'] for x in items])
            self.put('start_at', now)
            self.put('last_feed_success', now)
            self.put('last_attempt', now)

    def ingest(self, items, now, baseline=False):
        old = set(self.get('last_feed_keys', []))
        keys = {x['key'] for x in items}
        issues = ['feed_window_gap_possible'] if old and not old.intersection(keys) else []
        added, changed = 0, []
        with self.db:
            for item in items:
                item = {**item,'first_seen_at':now}
                row = self.db.execute('SELECT item,status FROM articles WHERE key=?', (item['key'],)).fetchone()
                if row:
                    previous = json.loads(row['item'])
                    if any(previous.get(k) != item.get(k) for k in ('title','url','source_sha256')):
                        issues.append('source_metadata_changed')
                        changed.append(item['key'])
                    continue
                self.db.execute('INSERT INTO articles(key,item,observed_at,status) VALUES (?,?,?,?)',
                                (item['key'], json.dumps(item, ensure_ascii=False), now,
                                 'baseline' if baseline else 'pending'))
                added += 1
            self.put('last_feed_keys', list(keys))
            self.put('last_feed_success', now)
            self.put('feed_issues', sorted(set(issues)))
            self.put('source_changed_keys', changed)
        return {'discovered': added, 'feed_issues': sorted(set(issues)), 'feed_items': len(items)}

    def tasks(self, retry=False, limit=3):
        # Running can only remain after process interruption, under the shared lock.
        statuses = ('pending', 'running', 'partial', 'failed', 'blocked') if retry else ('pending', 'running', 'partial', 'failed')
        budget = '' if retry else ' AND attempts < 3'
        rows = self.db.execute('SELECT * FROM articles WHERE status IN (' + ','.join('?' for _ in statuses) +
                               ')'+budget+' ORDER BY attempts,observed_at,key LIMIT ?', (*statuses, limit)).fetchall()
        return [dict(row, item=json.loads(row['item'])) for row in rows]

    def begin(self, key, output):
        with self.db:
            self.db.execute("UPDATE articles SET status='running',attempts=attempts+1,output=? WHERE key=? AND status NOT IN ('complete','baseline','skipped_before_start')", (str(output), key))

    def finish(self, key, result, output):
        status = result['status']
        if status not in {'complete', 'partial', 'failed', 'blocked', 'skipped_before_start'}:
            raise MVPError('invalid_archive_result')
        with self.db:
            self.db.execute('UPDATE articles SET status=?,reason=?,output=?,published_at=? WHERE key=?',
                            (status, ','.join(result.get('reasons', [])), str(output), result.get('published_at'), key))

    def summary(self):
        counts = dict(self.db.execute('SELECT status,count(*) FROM articles GROUP BY status').fetchall())
        recent = [dict(x) for x in self.db.execute('SELECT key,status,attempts,reason,output,published_at FROM articles WHERE status != ? ORDER BY observed_at DESC LIMIT 10', ('baseline',))]
        review = self.db.execute("SELECT count(*) FROM articles WHERE status='blocked' OR (status IN ('failed','partial','running') AND attempts>=3)").fetchone()[0]
        return {'integrity_checked':False,'status_basis':'task_ledger','start_at':self.get('start_at'),'last_feed_success':self.get('last_feed_success'),
                'last_attempt':self.get('last_attempt'),'last_outcome':self.get('last_outcome'),
                'next_retry_at':self.get('next_retry_at'),'feed_issues':self.get('feed_issues', []),
                'source_changed_keys':self.get('source_changed_keys', []),
                'article_access_paused':self.get('article_blocked',False),
                'source_access_paused':self.get('source_blocked'),
                'needs_manual_retry':review,
                'counts':counts,'recent':recent,'comments_status':'not_requested',
                'background_installation':'not_managed_by_cli'}
