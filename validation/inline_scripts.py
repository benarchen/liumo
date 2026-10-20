"""Offline, bounded syntax inspection; no live HTML or capture integration."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent / 'js'
SOURCE_LIMIT = 4 * 1024 * 1024
INPUT_LIMIT = 9 * 1024 * 1024
OUTPUT_LIMIT = 8192
TIMEOUT = 10
PAIRS = ('endpoint_literal_nodes', 'endpoint_static_expressions',
         'endpoint_call_argument_candidates', 'fetch_endpoint_candidates', 'ajax_url_candidates')
COUNTS = ('scripts_total', 'scripts_parsed', 'scripts_failed', 'nodes_visited',
          'dynamic_fetch_candidates', 'dynamic_ajax_url_candidates',
          'bridge_invoke_candidates', 'dynamic_bridge_method_candidates')
FLAGS = ('script_execution', 'runtime_execution_verified', 'comment_channel_verified')
REASONS = {'analysis_complete', 'syntax_incomplete', 'input_rejected', 'source_limit',
           'node_limit', 'parser_resource_failure', 'input_limit'}


def failed(reason):
    return {'status': 'failed', 'reason': reason, **dict.fromkeys(FLAGS, False)}


def analyze_scripts(scripts, timeout=TIMEOUT):
    """Return only validated fixed counters; never return child diagnostics."""
    if (type(timeout) not in (int, float) or not 0 < timeout <= TIMEOUT
            or not isinstance(scripts, list) or len(scripts) > 128):
        return failed('input_rejected')
    size = 0
    try:
        for script in scripts:
            if (not isinstance(script, dict) or set(script) != {'source', 'source_type'}
                    or not isinstance(script['source'], str)
                    or script['source_type'] not in ('script', 'module')):
                return failed('input_rejected')
            size += len(script['source'].encode('utf-8'))
            if size > SOURCE_LIMIT:
                return failed('source_limit')
        payload = json.dumps(scripts, ensure_ascii=False).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError):
        return failed('input_rejected')
    if len(payload) > INPUT_LIMIT:
        return failed('input_limit')
    node = shutil.which('node', path='/opt/homebrew/bin:/usr/bin:/bin')
    if not node or not (DIRECTORY / 'node_modules/acorn/package.json').is_file():
        return failed('parser_unavailable')
    try:
        p = subprocess.run([node, '--max-old-space-size=256', str(DIRECTORY / 'analyze.mjs')],
                           input=payload, capture_output=True, timeout=timeout,
                           env={'PATH': '/opt/homebrew/bin:/usr/bin:/bin', 'LC_ALL': 'C'},
                           cwd=DIRECTORY)
    except subprocess.TimeoutExpired:
        return failed('parser_timeout')
    except OSError:
        return failed('parser_unavailable')
    if p.returncode not in (0, 2) or p.stderr or len(p.stdout) > OUTPUT_LIMIT:
        return failed('parser_process_failure')
    try:
        out = json.loads(p.stdout)
        if not isinstance(out, dict):
            raise ValueError()
        small = {'status', 'reason', *FLAGS}
        full = small | set(PAIRS) | set(COUNTS)
        if set(out) not in (small, full) or out['reason'] not in REASONS:
            raise ValueError()
        if any(out[k] is not False for k in FLAGS):
            raise ValueError()
        if set(out) == small:
            if out['status'] != 'failed' or p.returncode != 2:
                raise ValueError()
        else:
            if (out['status'], out['reason'], p.returncode) not in (
                    ('passed', 'analysis_complete', 0), ('partial', 'syntax_incomplete', 2)):
                raise ValueError()
            values = [out[k] for k in COUNTS]
            for k in PAIRS:
                if not isinstance(out[k], dict) or set(out[k]) != {'comment', 'article_ext'}:
                    raise ValueError()
                values.extend(out[k].values())
            if any(type(v) is not int or not 0 <= v <= 200000 for v in values):
                raise ValueError()
        return out
    except (ValueError, TypeError, KeyError):
        return failed('parser_output_rejected')


def fixture():
    return analyze_scripts([{'source_type': 'script', 'source': '''
// fetch('/mp/appmsg_comment?token=CONSTRUCTED_SECRET');
const text = '/mp/appmsg_comment';
fetch('/mp/' + 'appmsg_comment?token=CONSTRUCTED_SECRET');
$.ajax({url: '/mp/getappmsgext', data: {token: 'CONSTRUCTED_SECRET'}});
WeixinJSBridge.invoke('CONSTRUCTED_METHOD', {token: 'CONSTRUCTED_SECRET'});
'''}])


if __name__ == '__main__':
    if sys.argv[1:] == ['--fixture']:
        result = fixture()
    elif sys.argv[1:]:
        result = failed('input_rejected')
    else:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        try:
            result = (failed('input_limit') if len(raw) > INPUT_LIMIT
                      else analyze_scripts(json.loads(raw)))
        except (ValueError, UnicodeError, RecursionError):
            result = failed('input_rejected')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'passed' else 2)
