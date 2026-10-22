"""Read-only static checks and explicit test layers using the standard library."""
import argparse
import ast
import json
import os
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = {'test_mvp.py', 'test_mvp_rss_archive.py', 'test_manual.py',
           'test_history.py', 'test_integrity.py', 'test_engineering.py'}
BROWSER = {'test_mvp_browser.py', 'test_manual_browser.py'}


def python_files(root):
    return sorted(p for name in ('liumo', 'validation', 'tests', 'tools')
                  for p in (root/name).rglob('*.py') if 'node_modules' not in p.parts)


def syntax_errors(root):
    failures = []
    for path in python_files(root):
        try:
            compile(path.read_bytes(), str(path), 'exec')
        except (SyntaxError, UnicodeError) as exc:
            failures.append(f'{path.relative_to(root)}:{getattr(exc,"lineno",0)}:invalid_python')
    return failures


def boundary_errors(root):
    failures = []
    for path in sorted((root/'liumo').rglob('*.py')):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modules = [node.module or '']
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                if name in ('__import__', 'import_module') and isinstance(node.args[0].value, str):
                    modules = [node.args[0].value]
            if any(m == 'validation' or m.startswith('validation.') for m in modules):
                failures.append(f'{path.relative_to(root)}:{node.lineno}:experiment_import')
    return failures


def headings(path):
    result = set()
    counts = {}
    fenced = False
    for line in path.read_text().splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
        if not fenced and re.match(r'^#{1,6} ', line):
            title = re.sub(r'^#+\s+', '', line).strip().lower()
            slug = re.sub(r'[^\w\-\s]', '', title).replace(' ', '-')
            index = counts.get(slug, 0)
            result.add(slug + (f'-{index}' if index else ''))
            counts[slug] = index + 1
    return result


def document_errors(root):
    files = sorted(set(root.glob('*.md')) | {
        p for name in ('docs', 'goals', 'goal') for p in (root/name).rglob('*.md')})
    failures = []
    for path in files:
        text = path.read_text()
        fence = None
        visible = []
        for line in text.splitlines():
            match = re.match(r'^\s*(`{3,}|~{3,})', line)
            if match:
                mark = match[1][0]
                fence = None if fence == mark else mark if fence is None else fence
            elif fence is None:
                visible.append(line)
        if fence:
            failures.append(f'{path.relative_to(root)}:unclosed_fence')
        for target in re.findall(r'\]\((<[^>\n]+>|(?:[^()\n]|\([^()\n]*\))+)\)', '\n'.join(visible)):
            target = target.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            name, _, anchor = unquote(target).partition('#')
            name = re.sub(r':\d+$', '', name)
            linked = (Path(name) if name.startswith('/') else path.parent/name) if name else path
            if not linked.exists():
                failures.append(f'{path.relative_to(root)}:missing_link:{name}')
            elif anchor and linked.suffix == '.md' and anchor not in headings(linked):
                failures.append(f'{path.relative_to(root)}:missing_anchor:{anchor}')
    roadmap = root/'ROADMAP.md'
    if roadmap.exists():
        text = roadmap.read_text()
        for section in ('最近完成', '最近验证'):
            if '## '+section+'\n' not in text:
                failures.append(f'ROADMAP.md:missing_section:{section}')
                continue
            part = text.split('## '+section+'\n', 1)[1].split('\n## ', 1)[0]
            rows = re.findall(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d)', part, re.M)
            if len(rows) > 20 or rows != sorted(rows, reverse=True):
                failures.append(f'ROADMAP.md:record_order_or_limit:{section}')
    return failures


def test_groups(root):
    files = {p.name for p in (root/'tests').glob('test_*.py')}
    return {'product': sorted(files & PRODUCT), 'browser': sorted(files & BROWSER),
            'legacy': sorted(files - PRODUCT - BROWSER)}


class LayerResult(unittest.TextTestResult):
    """Report actual per-layer results, including errors during class setup."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layers = {name: {'run': 0, 'passed': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
                       for name in ('product', 'browser', 'legacy')}

    def record(self, test, field):
        module = test.id().split('.')[0]+'.py'
        name = 'product' if module in PRODUCT else 'browser' if module in BROWSER else 'legacy'
        self.layers[name][field] += 1

    def startTest(self, test):
        self.record(test, 'run')
        super().startTest(test)

    def addSuccess(self, test):
        self.record(test, 'passed')
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.record(test, 'failures')
        super().addFailure(test, err)

    def addError(self, test, err):
        self.record(test, 'errors')
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.record(test, 'skipped')
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.record(test, 'failures' if issubclass(err[0], test.failureException) else 'errors')
        super().addSubTest(test, subtest, err)


def main(argv=None):
    parser = argparse.ArgumentParser(description='留墨只读静态检查与分层测试。')
    parser.add_argument('--suite', choices=('product', 'browser', 'legacy', 'all'), default='product')
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--list', action='store_true', help='仅显示分组和收集数，不执行测试。')
    args = parser.parse_args(argv)
    failures = syntax_errors(ROOT)
    if not failures:
        failures += boundary_errors(ROOT)
    failures += document_errors(ROOT)
    if failures:
        print(json.dumps({'status': 'failed', 'static_errors': failures}, ensure_ascii=False))
        return 2
    if args.static_only:
        print(json.dumps({'status': 'complete', 'checks': ['syntax', 'runtime_import_boundary', 'documents']}))
        return 0
    groups = test_groups(ROOT)
    if args.suite in ('browser', 'legacy', 'all'):
        os.environ['LIUMO_BROWSER_TESTS'] = '1'
    sys.path.insert(0, str(ROOT/'tests'))
    selected = [p for name, paths in groups.items() if args.suite in (name, 'all') for p in paths]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.discover(str(ROOT/'tests'), pattern=p) for p in selected)
    collected = suite.countTestCases()
    if args.list:
        print(json.dumps({'groups': groups, 'selected': args.suite, 'collected': collected}, ensure_ascii=False))
        return 0
    result = unittest.TextTestRunner(verbosity=2, resultclass=LayerResult).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped) - len(result.expectedFailures)
    summary = {'suite': args.suite, 'collected': collected, 'run': result.testsRun, 'passed': passed,
               'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
               'expected_failures': len(result.expectedFailures), 'layers': result.layers}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if result.wasSuccessful() and result.testsRun == collected and not result.skipped else 2


if __name__ == '__main__':
    raise SystemExit(main())
