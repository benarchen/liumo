"""Explicit local-browser checks, never WeChat or account profiles."""

import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from liumo.archive import snapshot
from validation.common import ROOT
from test_mvp import NOW, item


@unittest.skipUnless(os.environ.get('LIUMO_BROWSER_TESTS')=='1','explicit browser opt-in required')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver=sync_playwright().start()
        cls.browser=cls.driver.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.driver.stop()

    def setUp(self):
        base=ROOT/'.tmp/maobidao-mvp/browser-tests'; base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.output=Path(self.temp.name)
        self.context=self.browser.new_context(viewport={'width':1100,'height':900},device_scale_factor=1,timezone_id='Asia/Shanghai')
        self.page=self.context.new_page()
        self.html=(ROOT/'examples/pages/mvp-article.html').read_text()

    def tearDown(self):
        self.context.close(); self.temp.cleanup()

    def take(self,html=None,start=None):
        self.page.set_content(html or self.html)
        return snapshot(self.page,item(),self.output,start_at=start)

    def test_visible_body_local_image_full_screenshot_and_footer(self):
        result=self.take(start=NOW.isoformat())
        self.assertEqual(result['status'],'complete',result)
        text=(self.output/'article.md').read_text()
        self.assertIn('构造正文开头',text); self.assertIn('构造正文结尾',text)
        self.assertNotIn('隐藏面板',text)
        self.assertEqual(len(result['images']),1)
        self.assertTrue((self.output/result['images'][0]['path']).is_file())
        self.assertEqual(result['comments_status'],'not_requested')
        self.assertGreaterEqual(result['screenshot_dimensions']['height'],result['document_dimensions']['height'])

    def test_before_boundary_saves_no_article_but_equal_is_included(self):
        result=self.take(start=(NOW+timedelta(seconds=1)).isoformat())
        self.assertEqual(result['status'],'skipped_before_start')
        self.assertFalse((self.output/'article.md').exists())
        self.assertEqual(self.take(start=NOW.isoformat())['status'],'complete')

    def test_wrong_original_identity_stops_without_body_archive(self):
        result=self.take(self.html.replace("var mid='100'","var mid='101'"))
        self.assertEqual(result['status'],'blocked')
        self.assertFalse((self.output/'article.md').exists())

    def test_hidden_body_and_access_restriction_never_pass(self):
        self.assertEqual(self.take(self.html.replace('id="js_content"','id="js_content" style="display:none"'))['status'],'blocked')
        result=self.take('<body>环境异常，请完成验证。</body>')
        self.assertIn('access_restricted',result['reasons'])

    def test_image_failure_preserves_markdown_as_partial(self):
        html=self.html.replace('data:image/png;base64,iVBOR','data:image/png;base64,INVALID!iVBOR')
        result=self.take(html)
        self.assertEqual(result['status'],'partial')
        self.assertIn('images_incomplete',result['reasons'])
        self.assertTrue((self.output/'article.md').exists())

    def test_screenshot_failure_does_not_discard_saved_body(self):
        self.page.set_content(self.html)
        with patch.object(self.page,'screenshot',side_effect=OSError('private detail')):
            result=snapshot(self.page,item(),self.output)
        self.assertEqual(result['status'],'partial')
        self.assertTrue((self.output/'article.md').exists())
        self.assertNotIn('private detail',str(result))

    def test_long_page_and_large_overlay_are_not_silent_success(self):
        html=self.html.replace('</body>','<div style="height:101000px"></div></body>')
        result=self.take(html)
        self.assertIn('single_image_size_guard',result['reasons'])
        self.assertNotEqual(result['status'],'complete')
        self.assertFalse((self.output/'article.png').exists())
        overlay='<div style="position:fixed;inset:0;background:white;z-index:999">构造遮挡</div>'
        result=self.take(self.html.replace('</body>',overlay+'</body>'))
        self.assertIn('large_overlay_requires_review',result['reasons'])
