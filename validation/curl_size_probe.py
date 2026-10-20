"""Constructed HTTP over local Unix IPC; no TLS, external host or credentials."""

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .common import ROOT, new_run, timestamp, write_json

LIMIT = 2 * 1024 * 1024
CASES = ('small', 'known_too_large', 'chunked_too_large', 'chunked_exact', 'chunked_interrupted')
EXPECTED = {'small': (0, 2), 'known_too_large': (63, 0),
            'chunked_too_large': (63, LIMIT), 'chunked_exact': (0, LIMIT),
            'chunked_interrupted': (18, 20)}


def send_fixture(conn, name):
    if name == 'small':
        conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
    elif name == 'known_too_large':
        conn.sendall(('HTTP/1.1 200 OK\r\nContent-Length: ' + str(LIMIT + 1) +
                      '\r\nConnection: close\r\n\r\n').encode())
        conn.sendall(b'x' * (LIMIT + 1))
    else:
        conn.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n')
        size = LIMIT + 1 if name == 'chunked_too_large' else LIMIT if name == 'chunked_exact' else 20
        while size:
            length = min(size, 16384)
            conn.sendall(f'{length:x}\r\n'.encode() + b'x' * length + b'\r\n')
            size -= length
        if name != 'chunked_interrupted':
            conn.sendall(b'0\r\n\r\n')


def run_case(name, directory):
    path = str(directory / 's')
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(path)
        listener.listen(1)
        listener.settimeout(5)
    except OSError as exc:
        listener.close()
        return {'case': name, 'status': 'unix_IPC_unavailable', 'errno': exc.errno}
    peer_errors = []

    def serve():
        try:
            with listener.accept()[0] as conn:
                conn.settimeout(5)
                request = b''
                while b'\r\n\r\n' not in request and len(request) < 8192:
                    part = conn.recv(1024)
                    if not part:
                        return
                    request += part
                send_fixture(conn, name)
        except OSError as exc:
            peer_errors.append(exc.errno)
        finally:
            listener.close()

    thread = threading.Thread(target=serve)
    thread.start()
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY')}
    try:
        completed = subprocess.run([
            '/usr/bin/curl', '--disable', '--silent', '--show-error', '--no-netrc',
            '--unix-socket', path, '--proxy', '', '--noproxy', '*', '--max-time', '3',
            '--max-filesize', str(LIMIT), '--output', '/dev/null',
            '--write-out', '\nLIUMO_SIZE:%{http_code}:%{size_download}',
            'http://localhost/constructed'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=4, env=env, close_fds=True)
        match = re.fullmatch(rb'\nLIUMO_SIZE:([0-5][0-9]{2}):([0-9]{1,8})', completed.stdout)
        if not match:
            return {'case': name, 'status': 'numeric_metadata_unavailable', 'curl_exit_code': completed.returncode}
        http, size = map(int, match.groups())
        raw = completed.stderr.lower()
        category = ('size_limit_message' if b'maximum' in raw and b'file size' in raw
                    else 'other' if raw else 'none')
        return {'case': name, 'status': 'observed', 'curl_exit_code': completed.returncode,
                'http_status': http, 'downloaded_bytes': size, 'error_category': category,
                'matches_upstream_expected': http == 200 and (completed.returncode, size) == EXPECTED[name],
                'fixture_peer_errno': peer_errors}
    except (OSError, subprocess.TimeoutExpired):
        return {'case': name, 'status': 'native_process_unavailable_or_timed_out'}
    finally:
        thread.join(timeout=6)


def probe():
    results = []
    try:
        version = subprocess.check_output(['/usr/bin/curl', '--disable', '--version'],
            timeout=3, stderr=subprocess.DEVNULL, text=True).splitlines()[0][:512]
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError, IndexError):
        version = 'unavailable'
    temporary = ROOT / '.tmp/wechat-session-validation'
    temporary.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        with tempfile.TemporaryDirectory(dir=temporary, prefix='cs-') as raw:
            row = run_case(name, Path(raw))
        results.append(row)
        if row['status'] != 'observed':
            break
    return {'status': 'observed' if len(results) == len(CASES) and
            all(row['status'] == 'observed' for row in results) else 'not_verified',
            'at': timestamp(), 'evidence_level': 'constructed_HTTP_native_curl_local_Unix_IPC',
            'curl_version': version,
            'limit_bytes': LIMIT, 'TLS_tested': False, 'external_requests': 0,
            'credentials_read': False, 'system_settings_changed': False,
            'all_cases_match_upstream_expected': len(results) == len(CASES) and
            all(row.get('matches_upstream_expected') for row in results),
            'not_attempted_cases': list(CASES[len(results):]), 'results': results}


def main():
    import json
    if sys.argv[1:]:
        print(json.dumps({'status': 'not_verified', 'reason': 'fixed_probe_accepts_no_arguments'}))
        return 2
    result = probe()
    output = new_run('curl-size-offline')
    result['output'] = str(output)
    write_json(output / 'size-summary.json', result)
    print(json.dumps(result))
    return 0 if result['status'] == 'observed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
