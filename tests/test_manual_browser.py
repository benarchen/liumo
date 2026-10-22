"""Local browser rendering only, never a real account or WeChat request."""

import os
import html
import re
import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

from liumo.manual import capture_page, save_article
from liumo.rss import MVPError
from liumo.common import ROOT
from test_manual import BIZ, LONG, SHORT, PNG


@unittest.skipUnless(os.environ.get('LIUMO_BROWSER_TESTS')=='1','explicit browser opt-in required')
class ManualBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver=sync_playwright().start()
        cls.browser=cls.driver.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.driver.stop()

    def setUp(self):
        self.page=self.browser.new_page()
        self.html=f'''<html><body><h1 id="activity-name">构造文章</h1><span id="js_name">任意构造号</span>
        <div id="js_content"><p>正文开头</p><div style="display:none">隐藏面板</div><p>正文结尾</p></div>
        <script>var biz='{BIZ}';var mid='100';var idx='1';var is_pay_subscribe='0';</script></body></html>'''

    def tearDown(self):
        self.page.close()

    def test_any_account_readable_body_hidden_content_filtered(self):
        self.page.set_content(self.html);result=capture_page(self.page,SHORT)
        self.assertEqual(result['account'],'任意构造号');self.assertEqual(result['identity']['biz'],BIZ)
        self.assertIn('正文结尾',result['body_html']);self.assertNotIn('隐藏面板',result['body_html'])
        self.assertFalse(result['publication_time_verified'])

    def test_request_identity_is_not_used_as_response_identity(self):
        self.page.set_content(self.html.replace("var mid='100'","var mid='999'"))
        with self.assertRaisesRegex(MVPError,'manual_article_identity_mismatch'):capture_page(self.page,LONG)

    def test_paid_article_and_hidden_body_do_not_pass(self):
        self.page.set_content(self.html.replace("is_pay_subscribe='0'","is_pay_subscribe='1'"))
        with self.assertRaisesRegex(MVPError,'manual_paid_content_not_verified'):capture_page(self.page,SHORT)
        self.page.set_content(self.html.replace('id="js_content"','id="js_content" style="display:none"'))
        with self.assertRaisesRegex(MVPError,'manual_visible_body_missing'):capture_page(self.page,SHORT)

    def test_browser_capture_to_markdown_and_offline_local_images(self):
        self.page.set_content(self.html.replace('</div>\n        <script>',
            '<img src="https://mmbiz.qpic.cn/example.png"></div>\n        <script>'))
        captured=capture_page(self.page,SHORT)
        captured['scroll']={'bottom_reached':True}
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as temporary:
            root=Path(temporary)
            result=save_article(SHORT,data_dir=root/'state',archive_root=root/'archive',
                loader=lambda *a,**kw:captured,image_fetch=lambda *a,**kw:PNG)
            self.assertEqual(result['status'],'complete',result)
            output=Path(result['output']);md=(output/'article.md').read_text()
            paths=re.findall(r'!\[[^\]]*\]\((images/[^)]+)\)',md)
            self.assertEqual(len(paths),1)
            preview=output/'offline-test.html'
            preview.write_text('<meta charset="utf-8"><pre>'+html.escape(md)+'</pre>'+''.join(
                '<img src="'+html.escape(path,quote=True)+'">' for path in paths))
            self.page.route('http://**/*',lambda route:route.abort())
            self.page.route('https://**/*',lambda route:route.abort())
            self.page.goto(preview.as_uri())
            self.assertIn('正文结尾',self.page.locator('pre').inner_text())
            self.assertTrue(self.page.locator('img').evaluate('(el)=>el.complete && el.naturalWidth>0'))
