"""Offline constructed capacity comparison; never reads accounts or real HTML."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .common import ROOT


def constructed_scripts(size):
    prefix = 'fetch("/mp/appmsg_comment?token=CONSTRUCTED_SECRET");\n'
    rows = []
    for i in range(55):
        length = size // 55 + int(i < size % 55)
        count, pad = divmod(length - len(prefix), 2)
        rows.append({'source': prefix + '0;' * count + ' ' * pad, 'source_type': 'script'})
    return rows


def compare():
    node = shutil.which('node', path='/opt/homebrew/bin:/usr/bin:/bin')
    if not node:
        return {'status': 'failed', 'reason': 'capacity_environment_unavailable'}
    source = (ROOT/'validation/js/analyze.mjs').read_text()
    # Experimental copies only. The runtime source and its 200000 guard stay unchanged.
    if 'const NODE_LIMIT = 200000;' not in source or "from 'acorn'" not in source:
        return {'status': 'failed', 'reason': 'capacity_source_changed'}
    source = source.replace("from 'acorn'", 'from ' + json.dumps(str(ROOT/'validation/js/node_modules/acorn/dist/acorn.mjs')))
    base = ROOT/'.tmp/wechat-session-validation'
    base.mkdir(exist_ok=True, parents=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=base, prefix='parser-capacity-') as directory:
        for size in (3493944, 4194304):
            scripts = constructed_scripts(size)
            payload = json.dumps(scripts).encode()
            assert sum(len(r['source'].encode()) for r in scripts) == size
            for cap in (200000, 8388608):
                path = Path(directory)/('capacity-'+str(cap)+'.mjs')
                path.write_text(source.replace('const NODE_LIMIT = 200000;', 'const NODE_LIMIT = '+str(cap)+';'))
                start = time.monotonic()
                process = subprocess.Popen([node, '--max-old-space-size=256', str(path)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin','LC_ALL':'C'}, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(payload, timeout=10)
                    output = json.loads(stdout) if len(stdout) <= 8192 else {}
                    status, reason = output.get('status'), output.get('reason')
                    if process.returncode != (0 if status == 'passed' else 2):
                        status, reason = 'failed', 'capacity_process_failed'
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    stdout, stderr, output = b'', b'', {}
                    status, reason = 'failed', 'capacity_timeout'
                except (ValueError, UnicodeError):
                    stdout, stderr, output = b'', b'', {}
                    status, reason = 'failed', 'capacity_output_invalid'
                rows.append({'source_bytes':size,'script_count':55,'node_limit':cap,
                    'status':status if status in ('passed','partial','failed') else 'failed',
                    'reason':reason if reason in ('analysis_complete','node_limit','capacity_timeout',
                        'capacity_output_invalid','parser_resource_failure','syntax_incomplete') else 'capacity_process_failed',
                    'exit_code':process.returncode,'elapsed_seconds':round(time.monotonic()-start,3),
                    'peak_RSS_bytes_macos':None,
                    'nodes_visited':output.get('nodes_visited'),
                    'scripts_parsed':output.get('scripts_parsed'),
                    'fetch_comment_candidates':output.get('fetch_endpoint_candidates',{}).get('comment'),
                    'stdout_has_constructed_secret':b'CONSTRUCTED_SECRET' in stdout,
                    'stderr_has_constructed_secret':b'CONSTRUCTED_SECRET' in stderr})
    return {'status':'comparison_recorded','evidence':'constructed_JS_only',
            'runtime_source_modified':False,'network_requests':0,'system_settings_changed':False,
            'parent_timeout_seconds':10,'Node_old_space_MiB':256,'results':rows,
            'peak_RSS_measured':False,
            'real_WeChat_capacity_verified':False}


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
