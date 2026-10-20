"""Single-account feed, durable queue, recovery and Shanghai gate regressions."""

import plistlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from liumo.archive import publication
from liumo.rss import BIZ, MVPError, canonical, parse_feed
from liumo.runner import check, due, render_plist, run
from liumo.store import Store
from validation.common import ROOT

NOW = datetime.fromisoformat('2026-10-19T22:00:00+08:00')


def item(mid='100', title='构造文章'):
    url, key, identity = canonical(f'https://mp.weixin.qq.com/s?__biz={BIZ}&mid={mid}&idx=1')
    return {'key':key,'url':url,'identity':identity,'title':title,'feed_time':None,
            'publication_time_verified':False,'source_sha256':'a'*64}


def feed(items):
    return ('<rss><channel><title>猫笔刀</title>'+''.join(
        '<item><title>'+escape(x['title'])+'</title><link>'+escape(x['url'])+
        '</link><pubDate>invalid</pubDate><description>构造正文</description></item>' for x in items)+
        '</channel></rss>').encode()


class FeedTests(unittest.TestCase):
    def test_multi_item_duplicates_and_untrusted_feed_time(self):
        parsed = parse_feed(feed([item(),item(),item('101')]))
        self.assertEqual(len(parsed),2)
        self.assertIsNone(parsed[0]['feed_time'])
        self.assertFalse(parsed[0]['publication_time_verified'])

    def test_query_order_has_same_identity(self):
        one = item()
        url,key,_ = canonical(f'https://mp.weixin.qq.com/s?idx=1&mid=100&__biz={BIZ}')
        self.assertEqual(one['key'],key)
        self.assertEqual(one['url'],url)

    def test_reject_other_account_userinfo_duplicate_query_fragment_and_secret(self):
        for suffix in [f'__biz=OTHER&mid=100&idx=1', f'__biz={BIZ}&mid=1&idx=1&key=secret',
                       f'__biz={BIZ}&mid=1&mid=2&idx=1',f'__biz={BIZ}&mid=1&idx=1#fragment']:
            with self.subTest(suffix=suffix), self.assertRaises(MVPError):
                canonical('https://mp.weixin.qq.com/s?'+suffix)
        with self.assertRaises(MVPError):
            canonical(item()['url'].replace('mp.weixin.qq.com','user@mp.weixin.qq.com'))

    def test_malformed_empty_wrong_channel_entities_rejected(self):
        for data in [b'<',b'<rss><channel><title>cat</title></channel></rss>',
                     feed([]),b'<!DOCTYPE rss [<!ENTITY a "x">]><rss/>']:
            with self.subTest(data=data), self.assertRaises(MVPError):
                parse_feed(data)

    def test_description_change_has_fingerprint_without_saving_body(self):
        one = parse_feed(feed([item()]))[0]
        two = parse_feed(feed([item()]).replace('构造正文'.encode(),'正文变化'.encode()))[0]
        self.assertNotEqual(one['source_sha256'],two['source_sha256'])
        self.assertNotIn('description',one)


class PublicationTests(unittest.TestCase):
    def test_original_epoch_and_visible_time_agree(self):
        self.assertEqual(publication(str(int(NOW.timestamp())),'2026年10月19日 22:00',NOW),
                         NOW.astimezone(timezone.utc).isoformat())

    def test_feed_time_or_wrong_visible_time_does_not_pass(self):
        for visible in ['2026年10月19日 22:01','昨天','2026年10月18日 22:00','']:
            with self.subTest(visible=visible), self.assertRaises(MVPError):
                publication(str(int(NOW.timestamp())),visible,NOW)

    def test_invalid_or_future_epoch_rejected(self):
        for epoch in ['bad','1',str(int((NOW+timedelta(days=1)).timestamp()))]:
            with self.subTest(epoch=epoch), self.assertRaises(MVPError):
                publication(epoch,'2026年10月20日',NOW)


class QueueTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.tmp/maobidao-mvp/tests'
        base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.path=Path(self.temp.name)
        self.store=Store(self.path/'data')
        self.store.initialize([item('90')],NOW.isoformat())
        self.sent=[]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def sender(self,event,count):
        self.sent.append((event,count))
        return {'notification':'failed'}  # Notification failure never changes archive state.

    def check(self, items, archiver=None, **kwargs):
        archiver=archiver or (lambda *args,**kw:{'status':'complete','published_at':NOW.isoformat()})
        return check(self.store,NOW,self.path/'articles',source=lambda:items,archiver=archiver,sender=self.sender,**kwargs)

    def test_init_baseline_does_not_import_history_or_reinitialize(self):
        self.assertEqual(self.store.summary()['counts'],{'baseline':1})
        self.assertEqual(self.store.tasks(),[])
        with self.assertRaises(MVPError):
            self.store.initialize([],NOW.isoformat())

    def test_multiple_new_articles_repeat_and_independent_queue(self):
        items=[item('90'),item(),item('101')]
        first=self.check(items)
        self.assertEqual(len(first['results']),2)
        self.assertEqual(self.store.summary()['counts']['complete'],2)
        self.assertEqual(self.check(items)['results'],[])
        self.assertEqual(self.sent,[('complete',2)])

    def test_failed_archive_recovers_even_after_feed_window_advances(self):
        self.check([item('90'),item()],archiver=lambda *a,**k:{'status':'partial','reasons':['images_incomplete']})
        self.assertEqual(self.store.tasks()[0]['status'],'partial')
        out=self.check([item('90'),item('101')])
        self.assertEqual({r['key'] for r in out['results']},{item()['key'],item('101')['key']})
        self.assertEqual(self.store.summary()['counts']['complete'],2)

    def test_source_failure_preserves_pending_and_success_marker(self):
        self.store.ingest([item('90'),item()],NOW.isoformat())
        success=self.store.get('last_feed_success')
        def fail(): raise MVPError('public_transport_failed')
        result=check(self.store,NOW,self.path,source=fail,sender=self.sender)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(self.store.get('last_feed_success'),success)
        self.assertEqual(len(self.store.tasks()),1)
        self.assertEqual(self.store.get('next_retry_at'),(NOW+timedelta(minutes=15)).isoformat())

    def test_interrupt_running_task_recovered_after_reopen(self):
        self.store.ingest([item()],NOW.isoformat())
        self.store.begin(item()['key'],self.path/'interrupted')
        self.store.close()
        self.store=Store(self.path/'data')
        self.assertEqual(self.store.tasks()[0]['status'],'running')
        self.check([item()])
        self.assertEqual(self.store.summary()['counts']['complete'],1)
        self.assertEqual(self.store.summary()['recent'][0]['attempts'],2)

    def test_source_change_reported_completed_archive_not_overwritten(self):
        self.check([item()])
        original=self.store.summary()['recent'][0]['output']
        changed=item(); changed['source_sha256']='b'*64
        result=self.check([changed])
        self.assertIn('source_metadata_changed',result['feed_issues'])
        self.assertEqual(result['results'],[])
        self.assertEqual(self.store.summary()['recent'][0]['output'],original)

    def test_no_overlap_reports_gap_but_preserves_candidates(self):
        result=self.check([item()])
        self.assertIn('feed_window_gap_possible',result['feed_issues'])
        self.assertEqual(self.store.summary()['counts']['complete'],1)

    def test_blocked_stops_remaining_article_requests_and_requires_explicit_retry(self):
        calls=[]
        def blocked(row,*a,**kw):
            calls.append(row['key']); return {'status':'blocked','reasons':['access_restricted']}
        result=self.check([item(),item('101')],archiver=blocked)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['status'],'partial')
        self.assertNotIn('blocked',[x['status'] for x in self.store.tasks()])
        self.assertIn('blocked',[x['status'] for x in self.store.tasks(retry=True)])

    def test_archive_exception_saved_as_failed_not_dropped(self):
        def fail(*a,**kw): raise OSError('private error must not reach output')
        result=self.check([item()],archiver=fail)
        self.assertEqual(result['results'][0]['reasons'],['archive_operation_failed'])
        self.assertEqual(self.store.tasks()[0]['status'],'failed')

    def test_bounded_budget_and_fair_queue(self):
        result=self.check([item(str(i)) for i in range(100,105)],limit=2)
        self.assertEqual(len(result['results']),2)
        self.assertEqual(result['pending_or_failed'],3)

    def test_failed_task_has_finite_automatic_retry_budget_and_is_not_discarded(self):
        def fail(*a,**kw): return {'status':'partial','reasons':['images_incomplete']}
        for _ in range(3): self.check([item()],archiver=fail)
        self.assertEqual(self.store.tasks(),[])
        self.assertEqual(len(self.store.tasks(retry=True)),1)
        self.assertEqual(self.store.summary()['needs_manual_retry'],1)
        self.assertEqual(self.store.summary()['counts']['partial'],1)

    def test_source_shape_failure_pauses_without_network_backoff(self):
        def fail(): raise MVPError('feed_account_mismatch')
        check(self.store,NOW,self.path,source=fail,sender=self.sender)
        self.assertEqual(self.store.get('source_blocked'),'feed_account_mismatch')
        self.assertIsNone(self.store.get('next_retry_at'))
        result=run(self.path/'data',scheduled=True,now=NOW+timedelta(minutes=30),source=lambda:[])
        self.assertEqual(result['status'],'blocked')

    def test_article_pause_blocks_check_and_tick_until_explicit_retry(self):
        with self.store.db: self.store.put('article_blocked',True)
        def fail(): raise AssertionError('no requests while paused')
        result=run(self.path/'data',now=NOW,source=fail)
        self.assertEqual(result['status'],'blocked')

    def test_retry_of_other_pending_item_does_not_clear_unresolved_access_pause(self):
        self.store.ingest([item()],NOW.isoformat())
        self.store.begin(item()['key'],self.path/'blocked')
        self.store.finish(item()['key'],{'status':'blocked'},self.path/'blocked')
        with self.store.db: self.store.put('article_blocked',True)
        result=run(self.path/'data',self.path/'articles',retry=True,limit=1,now=NOW,
                   source=lambda:[item(),item('101')],
                   archiver=lambda *a,**kw:{'status':'complete'},sender=self.sender)
        self.assertEqual(result['results'][0]['key'],item('101')['key'])
        self.assertTrue(self.store.get('article_blocked'))

    def test_cross_process_lock_blocks_overlapping_run(self):
        from validation.state import exclusive
        with exclusive(self.path/'data/run.lock'), self.assertRaisesRegex(RuntimeError,'already_running'):
            run(self.path/'data',now=NOW,source=lambda:[item()])

    def test_tick_idle_does_not_touch_network(self):
        def fail(): raise AssertionError('not due')
        result=run(self.path/'data',now=NOW+timedelta(minutes=1),scheduled=True,source=fail)
        self.assertEqual(result['status'],'idle')

    def test_plist_is_read_only_install_draft_and_no_overwrite(self):
        path=self.path/'job.plist'
        self.assertFalse(render_plist(path,self.path/'data')['installed'])
        data=plistlib.loads(path.read_bytes())
        self.assertEqual(data['StartCalendarInterval'],{})
        self.assertIn('liumo',data['ProgramArguments'])
        with self.assertRaises(FileExistsError): render_plist(path)


class ScheduleTests(unittest.TestCase):
    def test_four_shanghai_slots_and_different_host_timezone(self):
        for hour,minute in [(22,0),(22,30),(23,0),(23,30)]:
            slot=NOW.replace(hour=hour,minute=minute).astimezone(timezone(timedelta(hours=-7)))
            self.assertTrue(due(slot,(slot-timedelta(seconds=1)).isoformat())[0])
            self.assertFalse(due(slot,slot.isoformat())[0])

    def test_missed_slots_coalesced_and_clock_backwards(self):
        after=NOW+timedelta(hours=12)
        self.assertTrue(due(after,NOW.isoformat())[0])
        self.assertFalse(due(NOW,after.isoformat())[0])
        self.assertFalse(due(after,after.isoformat())[0])

    def test_recovery_outside_window_bounded_by_backoff(self):
        after=NOW+timedelta(hours=12)
        retry=(after+timedelta(minutes=15)).isoformat()
        self.assertEqual(due(after,after.isoformat(),retry),(False,'failure_backoff'))
        self.assertEqual(due(after+timedelta(minutes=15),after.isoformat(),retry),(True,'recovery_coalesced'))
