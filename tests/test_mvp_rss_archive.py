"""RSS-only product path: local content and images, never an original-page browser."""

import base64
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from liumo.rss import MVPError, image_source, parse_feed
from liumo.rss_archive import archive_rss
from liumo.runner import run
from liumo.store import Store
from test_mvp import NOW, feed, item
from validation.common import ROOT

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nKsAAAAASUVORK5CYII=')


class RSSArchiveTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.tmp/maobidao-mvp/rss-tests';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.path=Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def sample(self):
        return {**item(),'first_seen_at':NOW.isoformat(),
                'body_html':'<p>构造 RSS 正文开头。</p><img src="https://mmbiz.qpic.cn/test.png"><p>构造结尾。</p>'}

    def test_complete_rss_snapshot_has_explicit_provenance_and_offline_image(self):
        result=archive_rss(self.sample(),self.path/'out',NOW.isoformat(),lambda *a,**kw:PNG)
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(result['archive_kind'],'rss_snapshot')
        self.assertFalse(result['publication_time_verified'])
        self.assertEqual(result['screenshot']['status'],'deferred')
        text=(self.path/'out/article.md').read_text()
        self.assertIn('RSS 内容快照',text);self.assertIn('原文发布时间待核实',text)
        self.assertIn('构造结尾',text)
        for image in result['images']: self.assertEqual((self.path/'out'/image['path']).read_bytes(),PNG)
        self.assertNotIn('https://mmbiz.qpic.cn/test.png',text)

    def test_first_seen_boundary_and_untrusted_old_feed_time(self):
        sample={**self.sample(),'feed_time':'2000-01-01T00:00:00+00:00'}
        self.assertEqual(archive_rss(sample,self.path/'equal',NOW.isoformat(),lambda *a,**k:PNG)['status'],'complete')
        self.assertEqual(archive_rss(sample,self.path/'before',(NOW+timedelta(seconds=1)).isoformat())['status'],'skipped_before_start')
        self.assertFalse((self.path/'before/article.md').exists())

    def test_missing_body_and_first_seen_fail_without_original_fallback(self):
        for index,sample in enumerate([{**self.sample(),'body_html':''},{**self.sample(),'first_seen_at':None}]):
            result=archive_rss(sample,self.path/str(index))
            self.assertEqual(result['status'],'failed')
            self.assertFalse((self.path/str(index)/'article.md').exists())

    def test_image_failure_keeps_partial_markdown_and_fixed_reason(self):
        def fail(*a,**kw): raise MVPError('public_http_rejected')
        result=archive_rss(self.sample(),self.path/'partial',image_fetch=fail)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['image_transport_reasons'],['public_http_rejected'])
        self.assertTrue((self.path/'partial/article.md').is_file())

    def test_image_source_uses_explicit_tencent_upstream_without_proxy_token(self):
        upstream='https://mmbiz.qpic.cn/path/0?wx_fmt=png'
        proxy='https://wechat2rss.xlab.app/img-proxy/?'+urlencode({'k':'public','u':upstream})
        self.assertEqual(image_source(proxy),upstream)
        for bad in ['http://mmbiz.qpic.cn/x','https://localhost/x','https://user@mmbiz.qpic.cn/x',
                    'https://wechat2rss.xlab.app/img-proxy/?'+urlencode({'k':'public','u':'https://127.0.0.1/x'})]:
            with self.subTest(url=bad),self.assertRaises(MVPError): image_source(bad)

    def test_encoded_content_preferred_and_scripts_forms_hidden_removed(self):
        data=feed([item()]).replace(b'<rss>',b'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/">')
        content='<p>完整正文</p><script>secret_script()</script><form>隐藏操作</form><div hidden>隐藏内容</div>'
        data=data.replace(b'</item>',('<content:encoded><![CDATA['+content+']]></content:encoded></item>').encode())
        parsed=parse_feed(data)[0]
        self.assertIn('完整正文',parsed['body_html'])
        self.assertNotIn('构造正文',parsed['body_html'])
        self.assertNotIn('secret_script',parsed['body_html'])
        self.assertNotIn('隐藏',parsed['body_html'])

    def test_real_runner_default_archiver_is_rss_only_and_repeat_does_not_overwrite(self):
        store=Store(self.path/'data');store.initialize([item('90')],NOW.isoformat());store.close()
        candidate={**self.sample(),'body_html':'<p>本地完整闭环。</p>'}
        with patch('liumo.archive.sync_playwright',side_effect=AssertionError('no browser')):
            first=run(self.path/'data',self.path/'articles',now=NOW,source=lambda:[item('90'),candidate],
                      sender=lambda *a:{'notification':'not_sent_test'})
            second=run(self.path/'data',self.path/'articles',now=NOW,source=lambda:[item('90'),candidate],
                       sender=lambda *a:{'notification':'not_sent_test'})
        self.assertEqual(first['results'][0]['status'],'complete')
        self.assertEqual(second['results'],[])
        path=Path(first['results'][0]['output'])
        self.assertTrue((path/'article.md').is_file())
        self.assertEqual(json.loads((path/'metadata.json').read_text())['archive_kind'],'rss_snapshot')

    def test_partial_retry_uses_preserved_first_seen_and_new_attempt_path(self):
        store=Store(self.path/'data');store.initialize([item('90')],NOW.isoformat());store.close()
        candidate=self.sample()
        def partial(row,out,**kw):
            return archive_rss(row,out,image_fetch=lambda *a,**k: (_ for _ in ()).throw(MVPError('public_transport_failed')))
        first=run(self.path/'data',self.path/'articles',now=NOW,source=lambda:[item('90'),candidate],
                  archiver=partial,sender=lambda *a:{})
        def complete(row,out,**kw): return archive_rss(row,out,image_fetch=lambda *a,**k:PNG)
        second=run(self.path/'data',self.path/'articles',now=NOW+timedelta(minutes=30),source=lambda:[item('90')],
                   archiver=complete,sender=lambda *a:{})
        self.assertEqual(first['results'][0]['status'],'partial')
        self.assertEqual(second['results'][0]['status'],'complete')
        self.assertNotEqual(first['results'][0]['output'],second['results'][0]['output'])
        meta=json.loads((Path(second['results'][0]['output'])/'metadata.json').read_text())
        self.assertEqual(meta['first_seen_at'],NOW.isoformat())
