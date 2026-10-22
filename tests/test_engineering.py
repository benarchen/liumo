"""Runtime boundaries, quality failure exits and compatibility contracts."""
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

from liumo.common import ROOT
from liumo.rss import MVPError
from tools.check import boundary_errors, document_errors, syntax_errors, test_groups


class EngineeringTests(unittest.TestCase):
    def test_core_imports_and_help_without_optional_or_legacy_modules(self):
        code='''import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in ('validation','playwright','mitmproxy'):
   raise ImportError('optional dependency blocked for test')
sys.meta_path.insert(0,Block())
import liumo.__main__, liumo.manual, liumo.history, liumo.integrity
assert not any(x.split('.')[0] in ('validation','playwright','mitmproxy') for x in sys.modules)
sys.argv=['liumo','--help']
liumo.__main__.main()
'''
        r=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('history',r.stdout)

    def test_missing_browser_dependency_has_actionable_fixed_reason(self):
        from liumo.browser import sync_playwright
        import builtins
        original=builtins.__import__
        def block(name,*args,**kwargs):
            if name.startswith('playwright'):raise ImportError('blocked')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',block),self.assertRaisesRegex(MVPError,'browser_dependency_missing_install_requirements_browser'):
            sync_playwright()

    def test_quality_detects_syntax_static_and_dynamic_boundary_failures(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as tmp:
            root=Path(tmp);(root/'liumo').mkdir();p=root/'liumo/bad.py'
            p.write_text('invalid python (')
            self.assertTrue(syntax_errors(root))
            for source in ['from validation.common import ROOT','import validation',
                           "__import__('validation.state')", "importlib.import_module('validation.archive')"]:
                p.write_text(source)
                self.assertTrue(boundary_errors(root))
            p.write_text('from .common import ROOT');self.assertEqual(boundary_errors(root),[])

    def test_quality_detects_broken_links_anchors_and_fences(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as tmp:
            root=Path(tmp);p=root/'README.md'
            for text in ['[missing](missing.md)','[anchor](#missing)','```python\npass\n']:
                p.write_text(text);self.assertTrue(document_errors(root))
            p.write_text('# Present\n\n[anchor](#present)\n');self.assertEqual(document_errors(root),[])
            linked=root/'file(1).md';linked.write_text('# Target\n')
            p.write_text('[file](<file(1).md>)\n[line](file(1).md:1)\n')
            self.assertEqual(document_errors(root),[])

    def test_quality_failure_exit_and_groups_cover_full_discovery(self):
        from tools import check
        with patch.object(check,'syntax_errors',return_value=['constructed_syntax_failure']),\
             patch.object(check,'document_errors',return_value=[]), redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(['--static-only']),2)
        groups=test_groups(ROOT)
        files={p.name for p in (ROOT/'tests').glob('test_*.py')}
        self.assertEqual(set().union(*(set(g) for g in groups.values())),files)
        self.assertEqual(sum(map(len,groups.values())),len(files))

    def test_product_boundary_static_check(self):
        self.assertEqual(boundary_errors(ROOT),[])

    def test_layer_report_counts_subtest_failures_and_skips(self):
        from tools.check import LayerResult
        class Cases(unittest.TestCase):
            def test_ok(self):
                pass
            def test_bad(self):
                with self.subTest(case='constructed_failure'):
                    self.fail('constructed_failure')
            def test_skip(self):
                self.skipTest('constructed_skip')
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=LayerResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.layers['product'],{'run':3,'passed':1,'failures':1,'errors':0,'skipped':1})
