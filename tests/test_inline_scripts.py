"""Constructed code only; actual Acorn parses but never executes input."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from validation import inline_scripts as a
from validation.common import ROOT


def scripts(source, kind='script'):
    return [{'source': source, 'source_type': kind}]


class InlineScriptTests(unittest.TestCase):
    def test_comments_plain_strings_and_call_candidates_are_distinct(self):
        out = a.analyze_scripts(scripts('''
// fetch('/mp/appmsg_comment');
/* $.ajax({url:'/mp/getappmsgext'}); */
const s='/mp/appmsg_comment';
fetch('/mp/appmsg_comment?token=PRIVATE_SECRET');
'''))
        self.assertEqual(out['status'], 'passed')
        self.assertEqual(out['endpoint_literal_nodes'], {'comment': 2, 'article_ext': 0})
        self.assertEqual(out['fetch_endpoint_candidates']['comment'], 1)
        self.assertEqual(out['endpoint_call_argument_candidates']['comment'], 1)
        self.assertFalse(out['runtime_execution_verified'])
        self.assertNotIn('PRIVATE_SECRET', json.dumps(out))

    def test_escaped_concat_template_and_absolute_urls(self):
        out = a.analyze_scripts(scripts(r'''
fetch('/mp/\u0061ppmsg_comment');
fetch('/mp/' + 'appmsg_comment');
fetch(`/mp/appmsg_comment`);
fetch('https://mp.weixin.qq.com/mp/appmsg_comment?token=SECRET');
fetch('https://other.invalid/mp/appmsg_comment');
fetch('https://SECRET@mp.weixin.qq.com/mp/appmsg_comment');
'''))
        self.assertEqual(out['status'], 'passed')
        self.assertEqual(out['fetch_endpoint_candidates']['comment'], 4)
        self.assertEqual(out['endpoint_static_expressions']['comment'], 2)
        self.assertNotIn('SECRET', json.dumps(out))

    def test_dynamic_values_stay_unknown_and_modern_module_syntax(self):
        out = a.analyze_scripts(scripts('''
import anything from 'PRIVATE_MODULE';
await fetch(url); fetch(`/mp/${path}`);
const value = anything?.x ?? 1n;
WeixinJSBridge['invoke'](method, {token: 'PRIVATE_TOKEN'});
''', 'module'))
        self.assertEqual(out['status'], 'passed')
        self.assertEqual(out['dynamic_fetch_candidates'], 2)
        self.assertEqual(out['bridge_invoke_candidates'], 1)
        self.assertEqual(out['dynamic_bridge_method_candidates'], 1)
        self.assertNotIn('PRIVATE', json.dumps(out))

    def test_ajax_spread_duplicate_and_computed_keys_are_uncertain(self):
        out = a.analyze_scripts(scripts('''
$.ajax({url:'/mp/getappmsgext'});
ajax({url:'/mp/appmsg_comment', ...anything});
$.ajax({url:'/mp/appmsg_comment',url:dynamic});
$.ajax({[key]:'/mp/appmsg_comment'});
$.ajax(options);
'''))
        self.assertEqual(out['ajax_url_candidates'], {'comment': 0, 'article_ext': 1})
        self.assertEqual(out['dynamic_ajax_url_candidates'], 4)

    def test_input_is_not_executed_and_names_are_never_returned(self):
        out = a.analyze_scripts(scripts('''
process.exit(93); throw new Error('PRIVATE_SECRET');
eval('PRIVATE_SOURCE'); WeixinJSBridge.invoke('PRIVATE_METHOD', {PRIVATE_KEY: 1});
'''))
        self.assertEqual(out['status'], 'passed')
        self.assertEqual(out['bridge_invoke_candidates'], 1)
        self.assertFalse(out['script_execution'])
        self.assertNotIn('PRIVATE', json.dumps(out))

    def test_syntax_failure_is_partial_with_no_exception_source(self):
        out = a.analyze_scripts(scripts('const PRIVATE_TOKEN = ;') + scripts('fetch("/mp/appmsg_comment");'))
        self.assertEqual(out['status'], 'partial')
        self.assertEqual(out['scripts_failed'], 1)
        self.assertEqual(out['scripts_parsed'], 1)
        self.assertEqual(out['fetch_endpoint_candidates']['comment'], 1)
        self.assertNotIn('PRIVATE', json.dumps(out))

    def test_invalid_schema_script_count_utf8_and_source_limit(self):
        for value in (None, {}, [None], scripts('x', 'PRIVATE_KIND'),
                      [{'source': '', 'source_type': 'script', 'PRIVATE_KEY': 1}],
                      scripts('') * 129, scripts('\ud800')):
            self.assertEqual(a.analyze_scripts(value)['status'], 'failed')
        with patch.object(a, 'SOURCE_LIMIT', 8):
            self.assertEqual(a.analyze_scripts(scripts('123456789'))['reason'], 'source_limit')
        with patch.object(a, 'INPUT_LIMIT', 1):
            self.assertEqual(a.analyze_scripts(scripts(''))['reason'], 'input_limit')
        self.assertEqual(a.analyze_scripts([])['status'], 'passed')

    def test_actual_node_limit_and_parser_stack_failure_are_fixed(self):
        out = a.analyze_scripts(scripts('0;' * 100001))
        self.assertEqual(out['reason'], 'node_limit')
        out = a.analyze_scripts(scripts('(' * 10000 + 'PRIVATE_TOKEN' + ')' * 10000))
        self.assertEqual(out['reason'], 'parser_resource_failure')
        self.assertNotIn('PRIVATE', json.dumps(out))

    def test_child_timeout_unavailable_and_abnormal_exit(self):
        with patch.object(a.shutil, 'which', return_value=None):
            self.assertEqual(a.analyze_scripts([])['reason'], 'parser_unavailable')
        with patch.object(a.subprocess, 'run', side_effect=OSError('PRIVATE_SECRET')):
            self.assertNotIn('PRIVATE', json.dumps(a.analyze_scripts([])))
        with patch.object(a.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE', 10)):
            self.assertEqual(a.analyze_scripts([])['reason'], 'parser_timeout')
        for rc, out, err in ((93, b'PRIVATE', b''), (0, b'PRIVATE', b''),
                             (0, b'{}', b'PRIVATE'), (0, b'X' * (a.OUTPUT_LIMIT+1), b'')):
            with patch.object(a.subprocess, 'run', return_value=subprocess.CompletedProcess([], rc, out, err)):
                result = a.analyze_scripts([])
            self.assertEqual(result['status'], 'failed')
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_output_schema_does_not_accept_extra_fields_or_true_execution(self):
        valid = a.fixture()
        for name, value in (('PRIVATE_KEY', 'PRIVATE_SECRET'), ('script_execution', True),
                            ('scripts_total', True), ('reason', 'PRIVATE_SECRET')):
            bad = {**valid, name: value}
            p = subprocess.CompletedProcess([], 0, json.dumps(bad).encode(), b'')
            with patch.object(a.subprocess, 'run', return_value=p):
                out = a.analyze_scripts([])
            self.assertEqual(out['reason'], 'parser_output_rejected')
            self.assertNotIn('PRIVATE', json.dumps(out))

    def test_node_entry_rejects_malformed_json_and_unknown_schema(self):
        node = a.shutil.which('node', path='/opt/homebrew/bin:/usr/bin:/bin')
        for data in (b'{PRIVATE_SECRET', b'[{"source":"PRIVATE_SECRET"}]', b'\xff'):
            p = subprocess.run([node, str(a.DIRECTORY/'analyze.mjs')], input=data,
                               capture_output=True, timeout=10,
                               env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin'})
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)['status'], 'failed')
            self.assertNotIn(b'PRIVATE', p.stdout + p.stderr)

    def test_fixture_cli_is_offline_and_filters_bad_stdin(self):
        for args, data, rc in ((['--fixture'], None, 0), ([], b'{PRIVATE_SECRET', 2),
                               (['--PRIVATE_SECRET'], None, 2)):
            p = subprocess.run([sys.executable, '-m', 'validation.inline_scripts', *args],
                               input=data, capture_output=True, timeout=10, cwd=ROOT)
            self.assertEqual(p.returncode, rc)
            self.assertNotIn(b'PRIVATE', p.stdout + p.stderr)
            self.assertFalse(json.loads(p.stdout)['comment_channel_verified'])


if __name__ == '__main__':
    unittest.main()
