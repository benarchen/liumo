"""Regression for completed history artifacts that subsequently become corrupt."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from liumo.history import import_history
from liumo.rss import ACCOUNT, BIZ, canonical
from liumo.rss_archive import archive_rss
from liumo.common import ROOT, write_json


class HistoryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'.tmp')
        self.root = Path(self.temp.name)
        url, key, identity = canonical(f'https://mp.weixin.qq.com/s?__biz={BIZ}&mid=100&idx=1')
        self.item = {'key':key, 'url':url, 'identity':identity, 'title':'构造文章',
                     'body_html':'<p>构造正文</p>', 'source_sha256':'a'*64,
                     'feed_time':'2026-10-20T22:00:00+08:00', 'first_seen_at':'2026-10-21T00:00:00+00:00'}
        self.output = self.root/'archives'/key/'original'
        archive_rss(self.item, self.output)
        self.ledger = {'version':1, 'account':ACCOUNT, 'biz':BIZ, 'sources':{'source':{
            'sha256':'a'*64, 'feed_url':None, 'path':'unused.xml'}}, 'tasks':{key:{
            'item':self.item, 'status':'complete', 'attempts':1, 'sources':['source'],
            'conflicts':[], 'output':str(self.output)}}}
        write_json(self.root/'data/history.json', self.ledger)

    def tearDown(self):
        self.temp.cleanup()

    def run_history(self, **kw):
        return import_history(ACCOUNT,'2026-10-20','2026-10-20',resume=True,
            data_dir=self.root/'data',archive_dir=self.root/'archives',
            now=datetime(2026,10,22,tzinfo=timezone.utc),**kw)

    def test_missing_markdown_complete_is_retried(self):
        (self.output/'article.md').unlink()
        archiver=Mock(wraps=archive_rss)
        result=self.run_history(retry=True,archiver=archiver)
        self.assertEqual(archiver.call_count,1)
        self.assertEqual(result['complete'],1)
        self.assertTrue((self.output/'metadata.json').is_file())
        self.assertEqual(self.run_history(retry=True,archiver=archiver)['complete'],1)
        self.assertEqual(archiver.call_count,1)

    def test_corrupt_image_complete_is_retried(self):
        image=self.output/'images/test.png';image.write_bytes(b'damaged')
        meta=json.loads((self.output/'metadata.json').read_text())
        meta['images']=[{'path':'images/test.png','sha256':hashlib.sha256(b'original').hexdigest(),'bytes':8,'index':0}]
        write_json(self.output/'metadata.json',meta)
        archiver=Mock(wraps=archive_rss)
        result=self.run_history(retry=True,archiver=archiver)
        self.assertEqual(archiver.call_count,1)
        self.assertEqual(result['complete'],1)
        self.assertEqual(image.read_bytes(),b'damaged')

    def test_no_retry_reports_damage_without_archiver(self):
        (self.output/'article.md').write_text('damaged')
        archiver=Mock(wraps=archive_rss)
        result=self.run_history(archiver=archiver)
        archiver.assert_not_called()
        self.assertEqual(result['archive_integrity_failed'],[self.item['key']])
        self.assertEqual(result['processing_status'],'partial')
        self.assertEqual(result['maturity'],'validated_rss_input')

    def test_false_complete_is_rejected_and_previous_reference_retained(self):
        (self.output/'article.md').write_text('damaged')
        result=self.run_history(retry=True,archiver=Mock(return_value={'status':'complete'}))
        self.assertEqual(result['complete'],0)
        ledger=json.loads((self.root/'data/history.json').read_text())
        row=ledger['tasks'][self.item['key']]
        self.assertEqual(row['output'],str(self.output))
        self.assertEqual(row['status'],'partial')
        self.assertEqual(row['previous_outputs'],[str(self.output)])
        self.assertEqual(self.run_history(retry=True)['complete'],1)

    def test_interruption_keeps_task_recoverable(self):
        (self.output/'article.md').write_text('damaged')
        with self.assertRaises(KeyboardInterrupt):
            self.run_history(retry=True,archiver=Mock(side_effect=KeyboardInterrupt))
        ledger=json.loads((self.root/'data/history.json').read_text())
        row=ledger['tasks'][self.item['key']]
        self.assertEqual(row['status'],'running');self.assertEqual(row['output'],str(self.output))
        self.assertEqual(self.run_history(retry=True)['complete'],1)


class HistorySelectionTests(unittest.TestCase):
    """Direct module and CLI contracts; all state is isolated."""

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.tmp')
        self.root=Path(self.temp.name)
        self.now=datetime(2026,10,22,tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, entries, name='feed.xml', account=ACCOUNT, biz=BIZ):
        from xml.sax.saxutils import escape
        rows=[]
        for mid, when, body in entries:
            url=f'https://mp.weixin.qq.com/s?__biz={biz}&mid={mid}&idx=1'
            rows.append('<item><title>构造文章</title><link>'+escape(url)+'</link><pubDate>'+escape(when)+
                        '</pubDate><description>'+escape(body)+'</description></item>')
        path=self.root/name
        path.write_text('<rss><channel><title>'+account+'</title>'+''.join(rows)+'</channel></rss>')
        return path

    def run_import(self, start='2026-10-20', end='2026-10-20', **kw):
        return import_history(ACCOUNT,start,end,data_dir=self.root/'state',archive_dir=self.root/'archives',
                              now=self.now,**kw)

    def ledger(self):
        return json.loads((self.root/'state/history.json').read_text())

    def test_inclusive_shanghai_dates_and_cross_day(self):
        p=self.source([(100,'Mon, 19 Oct 2026 16:00:00 GMT','正文'),
                       (101,'Tue, 20 Oct 2026 15:59:59 GMT','正文'),
                       (102,'Tue, 20 Oct 2026 16:00:00 GMT','正文')])
        r=self.run_import(rss_files=[p]);self.assertEqual((r['matching'],r['complete'],r['outside_range']),(2,2,1))
        self.assertEqual(r['processing_status'],'complete');self.assertFalse(r['coverage']['complete'])
        self.assertEqual(r['status'],'partial');self.assertFalse(r['original_times_verified'])

    def test_leap_date_and_invalid_ranges(self):
        from liumo.history import date_range
        from liumo.rss import MVPError
        self.assertEqual(str(date_range('2024-02-29','2024-02-29')[0]),'2024-02-29')
        for a,b in [('2026-02-29','2026-03-01'),('2026-10-21','2026-10-20'),('2026-1-01','2026-10-20'),(None,'2026-10-20')]:
            with self.subTest(a=a),self.assertRaises(MVPError):date_range(a,b)

    def test_unknown_and_future_times_are_not_archived(self):
        p=self.source([(100,'invalid','正文'),(101,'Thu, 22 Oct 2026 12:00:00 GMT','正文')])
        r=self.run_import(end='2026-10-23',rss_files=[p])
        self.assertEqual((len(r['unknown_time']),len(r['future_time']),r['complete']),(1,1,0))
        self.assertEqual(r['processing_status'],'partial');self.assertTrue(r['coverage']['future_range_pending'])

    def test_wrong_account_and_biz_do_not_persist_input(self):
        from liumo.rss import MVPError
        for p in [self.source([(100,'invalid','正文')],name='a.xml',account='other'),
                  self.source([(100,'invalid','正文')],name='b.xml',biz='MTIz')]:
            with self.subTest(p=p),self.assertRaises(MVPError):self.run_import(rss_files=[p])
            self.assertFalse((self.root/'state/history.json').exists())

    def test_all_sources_validate_before_ledger_changes(self):
        from liumo.rss import MVPError
        good=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        bad=self.root/'bad.xml';bad.write_text('<')
        with self.assertRaises(MVPError):self.run_import(rss_files=[good,bad])
        self.assertFalse((self.root/'state/history.json').exists())
        self.assertFalse((self.root/'state/sources').exists())
        self.assertFalse((self.root/'archives').exists())

    def test_cross_input_deduplication_and_changed_content_conflict(self):
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        r=self.run_import(rss_files=[p,p]);self.assertEqual((r['imported'],r['complete']),(1,1))
        changed=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','变稿')],name='changed.xml')
        r=self.run_import(rss_files=[changed]);self.assertEqual(len(r['source_conflicts']),1)
        self.assertEqual(r['results'],[]);self.assertEqual(r['processing_status'],'partial')
        self.assertEqual(next(iter(self.ledger()['tasks'].values()))['item']['body_html'],'正文')

    def test_retry_budget_and_explicit_retry(self):
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        fail=Mock(return_value={'status':'failed','reasons':['constructed_failure']})
        self.run_import(rss_files=[p],archiver=fail)
        self.run_import(resume=True,archiver=fail);r=self.run_import(resume=True,archiver=fail)
        self.assertEqual(len(r['needs_manual_retry']),1)
        self.run_import(resume=True,archiver=fail);self.assertEqual(fail.call_count,3)
        r=self.run_import(resume=True,retry=True);self.assertEqual(r['complete'],1)

    def test_resume_never_reads_feed_and_does_not_lose_window_items(self):
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        self.run_import(rss_files=[p],archiver=Mock(return_value={'status':'failed'}))
        newer=self.source([(101,'Wed, 21 Oct 2026 12:00:00 GMT','正文')],name='new.xml')
        self.run_import('2026-10-21','2026-10-21',rss_files=[newer])
        fetch=Mock(side_effect=AssertionError('feed must not be requested'))
        r=self.run_import(resume=True,fetch=fetch);fetch.assert_not_called()
        self.assertEqual(r['complete'],1);self.assertEqual(r['known_items'],2)
        self.assertTrue(all(row['status']=='complete' for row in self.ledger()['tasks'].values()))

    def test_other_range_conflicts_are_separate(self):
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        self.run_import(rss_files=[p])
        changed=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','变稿'),
                             (101,'Wed, 21 Oct 2026 12:00:00 GMT','正文')],name='changed.xml')
        r=self.run_import('2026-10-21','2026-10-21',rss_files=[changed])
        self.assertEqual(r['source_conflicts'],[])
        self.assertEqual(len(r['outside_selection_conflicts']),1)
        self.assertEqual((r['processing_status'],r['complete']),('complete',1))

    def test_limit_repeat_and_concurrent_lock(self):
        from liumo.common import exclusive
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文'),(101,'Tue, 20 Oct 2026 13:00:00 GMT','正文')])
        r=self.run_import(rss_files=[p],limit=1);self.assertEqual((r['complete'],len(r['unfinished'])),(1,1))
        r=self.run_import(resume=True,limit=1);self.assertEqual(r['complete'],2)
        self.assertEqual(self.run_import(resume=True)['results'],[])
        with exclusive(self.root/'state/run.lock'),self.assertRaisesRegex(RuntimeError,'already_running'):
            self.run_import(resume=True)

    def test_cli_processing_and_coverage_exit_contract(self):
        import subprocess,sys
        p=self.source([(100,'Tue, 20 Oct 2026 12:00:00 GMT','正文')])
        r=subprocess.run([sys.executable,'-m','liumo','history','--account',ACCOUNT,'--start','2026-10-20',
                          '--end','2026-10-20','--rss-file',str(p),'--data-dir',str(self.root/'state'),
                          '--archive-dir',str(self.root/'archives')],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);result=json.loads(r.stdout)
        self.assertEqual(result['processing_status'],'complete');self.assertFalse(result['coverage']['complete'])

    def test_source_and_input_guards(self):
        from liumo.history import account_config
        from liumo.rss import MVPError
        for options in [dict(biz='MTIz'),dict(feed_url='https://example.com/rss')]:
            with self.subTest(options=options),self.assertRaises(MVPError):account_config(ACCOUNT,**options)
        for options in [dict(limit=0),dict(limit=101),dict(resume=True,rss_files=['unused'])]:
            with self.subTest(options=options),self.assertRaises(MVPError):self.run_import(**options)
        with self.assertRaisesRegex(MVPError,'history_resume_missing'):self.run_import(resume=True)

    def test_official_emoji_image_path_is_narrowly_allowed(self):
        from liumo.rss import image_source,MVPError,public_image_url
        from urllib.parse import urlencode
        url='https://res.wx.qq.com/t/wx_fed/we-emoji/res/assets/Expression/Expression_21@2x.png'
        self.assertTrue(public_image_url(url))
        self.assertEqual(image_source('https://wechat2rss.xlab.app/img-proxy/?'+urlencode({'k':'public','u':url})),url)
        for other in [url+'?token=x',url+'#x',url.replace('https:','http:'),
                      url.replace('/Expression/','/../'),url.replace('res.wx.qq.com','other.wx.qq.com'),
                      'https://res.wx.qq.com/private.png']:
            with self.subTest(url=other),self.assertRaises(MVPError):image_source(other)
