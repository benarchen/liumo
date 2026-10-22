"""Manual links are independent of subscriptions, accounts, and existing archives."""

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from liumo.manual import article_key, identity, normalize_url, save_article
from liumo.rss import MVPError
from validation.common import ROOT
from validation.state import exclusive

BIZ=base64.b64encode(b'3075446573').decode()
SHORT='https://mp.weixin.qq.com/s/public_example'
LONG='https://mp.weixin.qq.com/s?'+urlencode({'__biz':BIZ,'mid':'100','idx':'1','sn':'a'*32})
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')


def payload(biz=BIZ, text='构造正文'):
    return {'title':'另一个公众号文章','account':'任意构造号','identity':identity(biz,'100','1'),
            'published_at':None,'publication_time_verified':False,'body_html':f'<p>{text}</p><img src="https://mmbiz.qpic.cn/example.png">',
            'selection':{'retained_image_indices':[0],'pruned_counts':{}},'image_nodes':[],
            'scroll':{'bottom_reached':True},'blocked_requests':0}


class ManualTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.tmp')
        self.root=Path(self.temp.name)
        self.loader=Mock(return_value=payload())
        self.images=Mock(return_value=PNG)

    def tearDown(self):
        self.temp.cleanup()

    def save(self,url=SHORT,**kwargs):
        return save_article(url,data_dir=self.root/'state',archive_root=self.root/'archive',
                            loader=self.loader,image_fetch=self.images,**kwargs)

    def test_public_short_long_share_tracking_and_html_ampersand(self):
        self.assertEqual(normalize_url(SHORT+'?scene=1#wechat_redirect'),(SHORT,None))
        normalized,expected=normalize_url(LONG.replace('&','&amp;')+'&scene=2#rd')
        self.assertEqual(normalized,LONG);self.assertEqual(expected,identity(BIZ,100,1))

    def test_invalid_urls_and_credential_fields_make_no_requests(self):
        for url in ['http://mp.weixin.qq.com/s/x','https://evil.test/s/x','https://mp.weixin.qq.com.evil.test/s/x',
                    'https://user@mp.weixin.qq.com/s/x','https://mp.weixin.qq.com/mp/profile_ext',
                    SHORT+'?key=secret',SHORT+'?access_token=secret',LONG+'&mid=101',SHORT+'\n']:
            with self.subTest(url=url),self.assertRaises(MVPError):self.save(url)
        self.loader.assert_not_called();self.images.assert_not_called()
        self.assertFalse((self.root/'state').exists())

    def test_any_account_body_image_metadata_and_no_follow_state(self):
        result=self.save();self.assertEqual(result['status'],'complete',result)
        output=Path(result['output']);text=(output/'article.md').read_text()
        self.assertIn('构造正文',text);self.assertIn('任意构造号',text)
        self.assertEqual(result['identity']['biz'],BIZ)
        self.assertIn(result['images'][0]['path'],text)
        self.assertEqual(hashlib.sha256((output/result['images'][0]['path']).read_bytes()).hexdigest(),result['images'][0]['sha256'])
        self.assertEqual(result['comments_status'],'not_requested');self.assertEqual(result['screenshot']['status'],'deferred')
        self.assertNotIn('body_html',json.loads((output/'metadata.json').read_text()))
        self.assertFalse((self.root/'state/state.sqlite3').exists())

    def test_repeated_link_reuses_verified_copy_without_browser(self):
        first=self.save();second=self.save()
        self.assertTrue(second['reused']);self.assertEqual(first['output'],second['output'])
        self.assertEqual(self.loader.call_count,1);self.assertEqual(self.images.call_count,1)

    def test_short_to_long_identity_dedup_and_unknown_alias(self):
        first=self.save();second=self.save(LONG)
        self.assertEqual(first['output'],second['output']);self.assertEqual(self.loader.call_count,1)
        third=self.save(SHORT+'2')
        self.assertEqual(third['output'],first['output']);self.assertEqual(self.images.call_count,1)
        index=json.loads((self.root/'state/index.json').read_text());self.assertEqual(index['aliases'][SHORT+'2'],first['key'])

    def test_explicit_long_identity_mismatch_stops_before_images(self):
        self.loader.return_value=payload(base64.b64encode(b'888888').decode())
        result=self.save(LONG);self.assertEqual(result['status'],'blocked')
        self.assertIn('manual_article_identity_mismatch',result['reasons']);self.images.assert_not_called()
        self.assertFalse((Path(result['output'])/'article.md').exists())

    def test_verification_or_paid_refusal_never_saves_article(self):
        for reason in ('manual_verification_required','manual_paid_content_not_verified'):
            self.loader.side_effect=MVPError(reason);result=self.save()
            self.assertEqual(result['status'],'blocked');self.assertFalse((Path(result['output'])/'article.md').exists())
        self.images.assert_not_called()

    def test_partial_images_and_retry_preserve_old_attempt(self):
        self.images.side_effect=OSError('private upstream detail');first=self.save()
        self.assertEqual(first['status'],'partial');self.assertNotIn('private upstream detail',json.dumps(first))
        self.images.side_effect=None;second=self.save()
        self.assertEqual(second['status'],'complete');self.assertNotEqual(first['output'],second['output'])
        self.assertTrue((Path(first['output'])/'article.md').exists())

    def test_refresh_keeps_old_snapshot_and_reports_body_change(self):
        first=self.save();old=Path(first['output'],'article.md').read_bytes()
        self.loader.return_value=payload(text='新的构造正文');second=self.save(refresh=True)
        self.assertEqual(second['status'],'complete');self.assertTrue(second['body_changed'])
        self.assertEqual(Path(first['output'],'article.md').read_bytes(),old)

    def test_damaged_copy_is_not_reused_as_complete(self):
        first=self.save();Path(first['output'],'article.md').write_text('damaged')
        second=self.save();self.assertFalse(second['reused']);self.assertEqual(self.loader.call_count,2)
        self.assertNotEqual(first['output'],second['output'])

    def test_damaged_image_or_wrong_cached_identity_is_not_reused(self):
        first=self.save()
        Path(first['output'],first['images'][0]['path']).write_bytes(b'damaged')
        second=self.save();self.assertFalse(second['reused'])
        meta=Path(second['output'],'metadata.json');record=json.loads(meta.read_text())
        record['key']='wrong';meta.write_text(json.dumps(record))
        third=self.save();self.assertFalse(third['reused']);self.assertEqual(self.loader.call_count,3)

    def test_poisoned_index_path_never_reads_or_writes_outside_archive(self):
        first=self.save();index_path=self.root/'state/index.json'
        state=json.loads(index_path.read_text());state['articles'][first['key']]='../../outside'
        index_path.write_text(json.dumps(state))
        second=self.save();self.assertFalse(second['reused']);self.assertEqual(second['status'],'complete')
        self.assertFalse((self.root/'outside').exists())

    def test_symlink_output_parent_is_refused_before_browser(self):
        target=self.root/'other';target.mkdir();archive=self.root/'archive';archive.mkdir()
        key=hashlib.sha256(SHORT.encode()).hexdigest()[:24]
        (archive/key).symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(MVPError,'manual_index_path_rejected'):self.save()
        self.loader.assert_not_called();self.assertEqual(list(target.iterdir()),[])

    def test_wait_budget_invalid_before_any_state_or_network(self):
        for wait in (-1,301,True,'180'):
            with self.assertRaisesRegex(MVPError,'manual_wait_out_of_range'):self.save(wait_seconds=wait)
        self.loader.assert_not_called();self.assertFalse((self.root/'state').exists())

    def test_bottom_not_reached_stays_partial(self):
        self.loader.return_value['scroll']['bottom_reached']=False
        result=self.save();self.assertEqual(result['status'],'partial')
        self.assertIn('manual_page_bottom_not_reached',result['reasons'])

    def test_overlap_lock_and_invalid_state_stop_before_browser(self):
        with exclusive(self.root/'state/run.lock'),self.assertRaisesRegex(RuntimeError,'already_running'):
            self.save()
        (self.root/'state/index.json').write_text('invalid')
        with self.assertRaisesRegex(MVPError,'manual_index_invalid'):self.save()
        self.loader.assert_not_called()

    def test_cli_invalid_url_and_help_do_not_open_browser(self):
        help_result=subprocess.run([sys.executable,'-m','liumo','save','--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(help_result.returncode,0);self.assertIn('--refresh',help_result.stdout)
        result=subprocess.run([sys.executable,'-m','liumo','save','https://evil.test/s/x'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertEqual(json.loads(result.stdout)['reason'],'manual_public_article_url_required')
