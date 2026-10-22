"""Offline audit and explicit repair safety, real renderer with constructed inputs."""

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from liumo.integrity import inspect_archive, verify, verify_scope, read_ledger
from liumo.repair import repair
from liumo.manual import save_article
from liumo.rss import ACCOUNT, BIZ, MVPError, canonical
from liumo.rss_archive import archive_rss
from liumo.store import Store
from liumo.common import ROOT, write_json
from liumo.common import exclusive
from test_manual import PNG, SHORT, payload

NOW='2026-10-22T00:00:00+00:00'


@contextmanager
def database(path):
    connection=sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def files(root):
    return {str(p.relative_to(root)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.tmp/p1-p2-remediation/g1/tests';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.root=Path(self.temp.name)
        self.data=self.root/'data';self.archives=self.root/'archives'
        url,key,identity=canonical(f'https://mp.weixin.qq.com/s?__biz={BIZ}&mid=101&idx=1')
        self.item={'url':url,'key':key,'identity':identity,'title':'构造正文',
            'first_seen_at':NOW,'feed_time':NOW,'source_sha256':'a'*64,
            'body_html':'<p>测试</p><img src="https://mmbiz.qpic.cn/one.png"><img src="https://mmbiz.qpic.cn/one.png">'}
        self.key=key;self.output=self.archives/key/'original'
        self.fetch=Mock(return_value=PNG)
        self.meta=archive_rss(self.item,self.output,image_fetch=self.fetch)
        self.assertEqual(self.meta['status'],'complete')
        self.store=Store(self.data)
        self.store.initialize([],NOW);self.store.ingest([self.item],NOW)
        self.store.begin(key,self.output);self.store.finish(key,self.meta,self.output)
        self.store.close()

    def tearDown(self):
        self.temp.cleanup()

    def audit(self):
        return verify_scope('rss',data_dir=self.data,archive_root=self.archives)

    def fix(self, **kw):
        return repair('rss',self.key,data_dir=self.data,archive_root=self.archives,**kw)

    def metadata(self, **kw):
        value={**self.meta,**kw};write_json(self.output/'metadata.json',value)

    def test_readonly_healthy_with_duplicate_image_references(self):
        before=files(self.root)
        with patch('liumo.rss.read_public',side_effect=AssertionError('network')):
            result=self.audit()
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(result['counts']['intact'],1)
        self.assertEqual(before,files(self.root))
        self.assertEqual(result['entries'][0]['ledger_status'],'complete')
        self.assertEqual(result['entries'][0]['checked_files'],3)

    def test_empty_does_not_create_data_or_archive_directories(self):
        root=self.root/'absent'
        report=verify_scope('manual',data_dir=root/'data',archive_root=root/'archive')
        self.assertTrue(report['empty']);self.assertEqual(report['checked'],0)
        self.assertEqual(report['status'],'complete');self.assertFalse(root.exists())

    def test_missing_markdown_has_file_reason_and_does_not_change_ledger(self):
        (self.output/'article.md').unlink();before=files(self.data)
        result=self.audit()['entries'][0]
        self.assertEqual(result['integrity_status'],'missing')
        self.assertEqual(result['affected_file'],'article.md')
        self.assertEqual(before,files(self.data))

    def test_missing_and_damaged_images_cannot_pass(self):
        image=self.output/self.meta['images'][0]['path']
        image.write_bytes(b'bad')
        self.assertEqual(self.audit()['counts']['corrupt'],1)
        image.unlink();self.assertEqual(self.audit()['counts']['missing'],1)

    def test_corrupt_metadata_unknown_fields_kind_and_identity(self):
        for update in ({'key':'0'*24},{'archive_kind':'other'},{'source_url':'https://invalid.test'},
                       {'images':{}},{'markdown_sha256':None}):
            with self.subTest(update=update):
                self.metadata(**update)
                self.assertNotEqual(self.audit()['entries'][0]['integrity_status'],'intact')
        (self.output/'metadata.json').write_text('{bad')
        self.assertEqual(self.audit()['counts']['unverifiable'],1)
        self.metadata();meta=deepcopy(self.meta);del meta['images'];write_json(self.output/'metadata.json',meta)
        self.assertEqual(self.audit()['counts']['unverifiable'],1)

    def test_metadata_size_and_unsafe_image_paths_rejected(self):
        (self.output/'metadata.json').write_bytes(b' '*(1024*1024+1))
        self.assertEqual(self.audit()['counts']['corrupt'],1)
        outside=self.root/'sensitive';outside.write_text('private')
        for relative in ('../sensitive',str(outside),'images/../../sensitive'):
            self.metadata(images=[{'path':relative,'sha256':hashlib.sha256(b'private').hexdigest(),'bytes':7}])
            result=self.audit()
            self.assertNotEqual(result['counts']['intact'],1)
            self.assertNotIn('private',json.dumps(result))

    def test_symlink_metadata_and_output_rejected_without_following(self):
        meta=self.output/'metadata.json';meta.unlink();meta.symlink_to(self.root/'outside')
        self.assertEqual(self.audit()['counts']['corrupt'],1)
        other=self.archives/('f'*24);other.symlink_to(self.root,target_is_directory=True)
        self.assertEqual(self.audit()['status'],'partial')

    def test_external_ledger_output_rejected(self):
        with database(self.data/'state.sqlite3') as db:
            db.execute('UPDATE articles SET output=?',(str(self.root/'external'),))
        self.assertEqual(self.audit()['counts']['corrupt'],1)
        with self.assertRaises(MVPError):self.fix()

    def test_image_references_must_match_manifest(self):
        md=self.output/'article.md';md.write_text(md.read_text()+'\n![missing](images/missing.png)')
        self.metadata(markdown_sha256=hashlib.sha256(md.read_bytes()).hexdigest())
        self.assertEqual(self.audit()['counts']['corrupt'],1)

    def test_unindexed_attempts_reported_without_import(self):
        extra=self.archives/self.key/'orphan';extra.mkdir()
        before=files(self.root);result=self.audit()
        self.assertEqual(result['unindexed'],[f'{self.key}/orphan'])
        self.assertEqual(before,files(self.root))

    def test_bad_ledger_not_reported_empty(self):
        report=verify_scope('history',data_dir=self.data,archive_root=self.archives)
        self.assertEqual(report['status'],'partial')  # Unindexed snapshots with no history ledger.
        (self.data/'history.json').write_text('[]')
        report=verify_scope('history',data_dir=self.data,archive_root=self.archives)
        self.assertEqual(report['status'],'partial');self.assertFalse(report['empty'])

    def test_repair_reuses_verified_images_keeps_old_and_is_idempotent(self):
        (self.output/'article.md').write_text('damaged');old=files(self.output)
        fetch=Mock(side_effect=AssertionError('network must not be used'))
        result=self.fix(image_fetch=fetch)
        self.assertEqual(result['status'],'complete',result)
        self.assertNotEqual(result['output'],str(self.output))
        self.assertEqual(old,files(self.output));fetch.assert_not_called()
        self.assertEqual(self.audit()['counts']['intact'],1)
        before=files(self.archives)
        again=self.fix(image_fetch=fetch)
        self.assertTrue(again['reused']);self.assertEqual(before,files(self.archives))
        with database(self.data/'state.sqlite3') as db:
            self.assertEqual(db.execute('SELECT attempts FROM articles').fetchone()[0],2)
            self.assertEqual(json.loads(db.execute("SELECT value FROM meta WHERE key='start_at'").fetchone()[0]),NOW)

    def test_bad_image_refetched_but_old_snapshot_kept(self):
        image=self.output/self.meta['images'][0]['path'];image.write_bytes(b'bad')
        fetch=Mock(return_value=PNG);result=self.fix(image_fetch=fetch)
        self.assertEqual(result['status'],'complete');self.assertTrue(fetch.called)
        self.assertEqual(image.read_bytes(),b'bad')

    def test_cache_mapping_requires_matching_html_fingerprint(self):
        (self.output/'article.md').write_text('bad');self.metadata(rss_body_sha256='0'*64)
        fetch=Mock(return_value=PNG);self.assertEqual(self.fix(image_fetch=fetch)['status'],'complete')
        self.assertTrue(fetch.called)

    def test_failed_repair_does_not_advance_index_and_recovery_succeeds(self):
        (self.output/'article.md').write_text('bad')
        before=(self.data/'state.sqlite3').read_bytes()
        result=self.fix(archiver=Mock(side_effect=OSError('private error')))
        self.assertEqual(result['status'],'failed');self.assertNotIn('private error',json.dumps(result))
        self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())
        self.assertEqual(self.fix()['status'],'complete')

    def test_fake_complete_and_network_failure_never_publish(self):
        (self.output/'article.md').write_text('bad')
        before=(self.data/'state.sqlite3').read_bytes()
        result=self.fix(archiver=Mock(return_value={'status':'complete'}))
        self.assertEqual(result['status'],'partial');self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())
        self.metadata(rss_body_sha256='0'*64)
        result=self.fix(image_fetch=Mock(side_effect=MVPError('public_transport_failed')))
        self.assertEqual(result['status'],'partial');self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())

    def test_interrupt_and_overlap_leave_index_retryable(self):
        (self.output/'article.md').write_text('bad');before=(self.data/'state.sqlite3').read_bytes()
        with self.assertRaises(KeyboardInterrupt):self.fix(archiver=Mock(side_effect=KeyboardInterrupt))
        self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())
        with exclusive(self.data/'run.lock'),self.assertRaisesRegex(RuntimeError,'already_running'):
            self.fix()
        self.assertEqual(self.fix()['status'],'complete')

    def test_missing_input_never_creates_empty_body(self):
        (self.output/'article.md').write_text('bad')
        item={**self.item,'body_html':''}
        with database(self.data/'state.sqlite3') as db:
            db.execute('UPDATE articles SET item=?',(json.dumps(item),))
        self.assertEqual(self.fix()['status'],'unrecoverable')
        self.assertFalse((self.data/'repair-attempts').exists())

    def test_key_scope_and_source_identity_guard(self):
        for key in ('../bad','', '0'*24):
            with self.assertRaises(MVPError):
                repair('rss',key,data_dir=self.data,archive_root=self.archives)
        with self.assertRaises(MVPError):verify('all',data_dir=self.data)
        (self.output/'article.md').write_text('bad')
        with database(self.data/'state.sqlite3') as db:
            db.execute('UPDATE articles SET item=?',(json.dumps({**self.item,'key':'0'*24}),))
        with self.assertRaises(MVPError):self.fix()

    def test_manual_audit_repair_identity_and_scope_isolation(self):
        manual_data=self.root/'manual-data';manual_root=self.root/'manual-archives'
        loader=Mock(return_value=payload())
        saved=save_article(SHORT,data_dir=manual_data,archive_root=manual_root,loader=loader,image_fetch=self.fetch)
        before=files(self.data)
        Path(saved['output'],'article.md').write_text('damaged')
        self.assertEqual(verify_scope('manual',data_dir=manual_data,archive_root=manual_root)['counts']['corrupt'],1)
        result=repair('manual',saved['key'],data_dir=manual_data,archive_root=manual_root,loader=loader,image_fetch=self.fetch)
        self.assertEqual(result['status'],'complete',result);self.assertNotEqual(saved['output'],result['output'])
        again=repair('manual',saved['key'],data_dir=manual_data,archive_root=manual_root,loader=loader,image_fetch=self.fetch)
        self.assertTrue(again['reused']);self.assertEqual(loader.call_count,2)
        self.assertEqual(before,files(self.data))
        Path(result['output'],'article.md').write_text('damaged')
        index=(manual_data/'index.json').read_bytes()
        bad=payload();bad['identity']['mid']='102'
        failed=repair('manual',saved['key'],data_dir=manual_data,archive_root=manual_root,
                      loader=Mock(return_value=bad),image_fetch=self.fetch)
        self.assertEqual(failed['status'],'blocked');self.assertEqual(index,(manual_data/'index.json').read_bytes())

    def test_history_repair_preserves_ledger_fields_and_previous_output(self):
        history=self.root/'history'
        ledger={'version':1,'account':ACCOUNT,'biz':BIZ,'sources':{},'tasks':{self.key:{
            'status':'complete','attempts':1,'item':self.item,'output':str(self.output),'conflicts':[]}}}
        write_json(history/'history.json',ledger)
        (self.output/'article.md').write_text('bad')
        result=repair('history',self.key,data_dir=history,archive_root=self.archives)
        self.assertEqual(result['status'],'complete',result)
        current=json.loads((history/'history.json').read_text())
        self.assertEqual(current['tasks'][self.key]['previous_outputs'],[str(self.output)])
        self.assertEqual(verify_scope('history',data_dir=history,archive_root=self.archives)['counts']['intact'],1)

    def test_cli_exit_codes_and_history_maturity_help(self):
        def cli(*args):
            return subprocess.run([sys.executable,'-m','liumo',*args],cwd=ROOT,capture_output=True,text=True)
        args=('verify','--scope','rss','--data-dir',str(self.data),'--archive-dir',str(self.archives))
        self.assertEqual(cli(*args).returncode,0)
        (self.output/'article.md').write_text('bad');self.assertEqual(cli(*args).returncode,2)
        self.assertIn('给定 RSS 输入',cli('--help').stdout)
        self.assertIn('不代表来源或全年完整',cli('history','--help').stdout)
        self.assertEqual(cli('repair','--scope','rss').returncode,2)

    def test_failed_write_and_publication_do_not_publish_complete(self):
        (self.output/'article.md').write_text('bad');before=(self.data/'state.sqlite3').read_bytes()
        original=Path.write_text
        def fail_markdown(path,*args,**kwargs):
            if path.name=='article.md' and path.parent!=self.output:
                raise OSError('disk full')
            return original(path,*args,**kwargs)
        with patch.object(Path,'write_text',fail_markdown):
            result=self.fix()
        self.assertNotEqual(result['status'],'complete');self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())
        with patch('liumo.repair.write_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.fix()
        self.assertEqual(before,(self.data/'state.sqlite3').read_bytes())
        self.assertEqual(self.fix()['status'],'complete')

    def test_healthy_repair_does_not_fetch_or_write(self):
        before=files(self.root);fetch=Mock(side_effect=AssertionError('unexpected'))
        result=self.fix(image_fetch=fetch)
        self.assertTrue(result['reused']);fetch.assert_not_called()
        # Existing lock contents are not rewritten, and archive/ledger bytes stay unchanged.
        self.assertEqual(before,{k:v for k,v in files(self.root).items() if k!='data/run.lock'})

    def test_ledger_symlink_and_temp_symlink_block_reads_writes(self):
        target=self.root/'other';target.write_text('unchanged')
        (self.data/'state.sqlite3.tmp').symlink_to(target)
        with self.assertRaises(MVPError):self.fix()
        self.assertEqual(target.read_text(),'unchanged')
        empty=self.root/'symlink-state';empty.mkdir()
        (empty/'index.json').symlink_to(target)
        result=verify_scope('manual',data_dir=empty,archive_root=self.archives)
        self.assertEqual(result['status'],'partial')

    def test_manual_failed_metadata_write_keeps_previous_index(self):
        data=self.root/'manual-data';root=self.root/'manual-archive'
        loader=Mock(return_value=payload())
        saved=save_article(SHORT,data_dir=data,archive_root=root,loader=loader,image_fetch=self.fetch)
        Path(saved['output'],'article.md').write_text('bad')
        before=(data/'index.json').read_bytes()
        original=write_json
        def failed(path,value):
            if Path(path).name=='metadata.json':raise OSError('disk full')
            original(path,value)
        with patch('liumo.manual.write_json',side_effect=failed),self.assertRaises(OSError):
            repair('manual',saved['key'],data_dir=data,archive_root=root,loader=loader,image_fetch=self.fetch)
        self.assertEqual(before,(data/'index.json').read_bytes())

    def test_all_scopes_enumerates_history_without_creating_files(self):
        fake=self.root/'all-root'
        data=fake/'state/history/other';data.mkdir(parents=True)
        write_json(data/'history.json',{'version':1,'account':'other','biz':BIZ,'tasks':{},'sources':{}})
        before=files(fake)
        with patch('liumo.integrity.ROOT',fake):
            result=verify()
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual([r['scope'] for r in result['scopes']],['rss','manual','history'])
        self.assertEqual(before,files(fake))

    def test_all_scopes_includes_history_archives_without_ledger(self):
        fake=self.root/'orphan-root'
        output=fake/'archives/history/other'/self.key/'orphan';output.mkdir(parents=True)
        with patch('liumo.integrity.ROOT',fake):result=verify()
        self.assertEqual(result['status'],'partial')
        history=next(r for r in result['scopes'] if r['scope']=='history')
        self.assertEqual(history['unindexed'],[f'{self.key}/orphan'])
        self.assertFalse((fake/'state').exists())

    def test_changed_retained_content_reports_change_and_preserves_old(self):
        (self.output/'article.md').write_text('damaged');before=files(self.output)
        changed={**self.item,'body_html':'<p>不同内容</p>'}
        with database(self.data/'state.sqlite3') as db:
            db.execute('UPDATE articles SET item=?',(json.dumps(changed),))
        result=self.fix()
        self.assertEqual(result['status'],'complete');self.assertTrue(result['body_changed'])
        self.assertEqual(before,files(self.output))

    def test_manual_source_url_and_inconsistent_complete_metadata_rejected(self):
        data=self.root/'manual-data';root=self.root/'manual-archive'
        saved=save_article(SHORT,data_dir=data,archive_root=root,loader=Mock(return_value=payload()),image_fetch=self.fetch)
        output=Path(saved['output']);meta=json.loads((output/'metadata.json').read_text())
        for update in ({'source_url':'https://elsewhere.test/article'},
                       {'source_url':SHORT+'?key=private'},
                       {'reasons':['incomplete']},{'image_failures':[{'index':0}]}):
            with self.subTest(update=update):
                write_json(output/'metadata.json',{**meta,**update})
                report=verify_scope('manual',data_dir=data,archive_root=root)
                self.assertEqual(report['status'],'partial')
                self.assertEqual(report['counts']['intact'],0)
