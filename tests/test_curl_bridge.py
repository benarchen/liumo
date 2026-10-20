"""Real local FIFOs and numeric receipts; no network or real credentials."""

import json
import stat
import threading
import time
import os
from unittest.mock import patch

from test_validation import LocalTest
from validation.capture_session import private_write
from validation.curl_bridge import CurlBridge, redirect_summary, canonical_sample_redirect
from validation.common import SAMPLES
from validation.http import ProbeError


class CurlBridgeTests(LocalTest):
    def test_only_one_known_sample_https_identity_can_redirect(self):
        origin = SAMPLES['maobidao']
        def headers(value):
            return b'Location: ' + value.encode() + b'\r\n'
        self.assertEqual(canonical_sample_redirect(origin, headers(origin + '?scene=1')), origin + '?scene=1')
        canonical = 'https://mp.weixin.qq.com/s?__biz=MzE5ODk2NjUwOA%3D%3D&mid=2247498641&idx=1&sn=public'
        self.assertEqual(canonical_sample_redirect(origin, headers(canonical)), canonical)
        for target in (origin, origin.replace('https:', 'http:') + '?scene=1',
                       'https://evil.test/s/x', 'https://user@mp.weixin.qq.com/s/x',
                       'https://mp.weixin.qq.com:444/s/x', SAMPLES['stormzhang'],
                       '/mp/wappoc_appmsgcaptcha?key=private-key', '/s/other?scene=1',
                       origin + '?mid=other', canonical + '&mid=2247498641', canonical + '#fragment'):
            self.assertIsNone(canonical_sample_redirect(origin, headers(target)))
        self.assertIsNone(canonical_sample_redirect('https://mp.weixin.qq.com/mp/profile_ext', headers(origin)))

    def fake_curl(self, body=b'private-response', code=0, status=200):
        captured = []
        def run():
            end = time.monotonic() + 3
            while time.monotonic() < end:
                path = self.path / 'status.json'
                if path.exists():
                    state = json.loads(path.read_text())
                    if state['status'] == 'awaiting_curl':
                        break
                time.sleep(.01)
            else:
                return
            with open(state['config_fifo'], 'rb') as stream:
                captured.append(stream.read())
            with open(state['header_fifo'], 'wb') as stream:
                stream.write(b'HTTP/1.1 200 OK\r\nSet-Cookie: key=private-key\r\n\r\n')
            with open(state['response_fifo'], 'wb') as stream:
                stream.write(body)
            from pathlib import Path
            private_write(Path(state['receipt']), {'exit_code': code, 'http_status': status})
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, captured

    def test_actual_fifos_no_secret_or_raw_response_in_regular_files(self):
        bridge = CurlBridge(self.path, request_timeout=3)
        thread, captured = self.fake_curl()
        data = bridge.read('https://mp.weixin.qq.com/s?key=private-key', {'Cookie': 'appmsg_token=private-token'})
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(data, b'private-response')
        self.assertIn(b'private-key', captured[0])
        for path in self.path.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'private-', path.read_bytes())
            if stat.S_ISFIFO(path.stat().st_mode):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_redirect_classification_never_includes_location_query_cookie_or_unknown_host(self):
        result = redirect_summary('https://mp.weixin.qq.com/s/x', b'HTTP/1.1 302\r\nLocation: /mp/wappoc_appmsgcaptcha?key=private-key\r\nSet-Cookie: private-token\r\n\r\n')
        self.assertEqual(result['route'], '/mp/wappoc_appmsgcaptcha')
        self.assertTrue(result['same_https_origin'])
        self.assertFalse(result['location_followed'])
        self.assertNotIn('private-', json.dumps(result))
        result = redirect_summary('https://mp.weixin.qq.com/s/x', b'Location: https://private-account.invalid/private-key')
        self.assertEqual(result['host_class'], 'other')
        self.assertEqual(result['route'], 'other')
        self.assertNotIn('private-', json.dumps(result))

    def test_no_consumer_timeout_and_budget_terminate_without_network(self):
        bridge = CurlBridge(self.path, request_timeout=.15)
        with self.assertRaisesRegex(ProbeError, '^bridge_request_timed_out$'):
            bridge.read('https://mp.weixin.qq.com/s')
        bridge.requests = 46
        with self.assertRaisesRegex(ProbeError, '^bridge_budget_exhausted$'):
            bridge.read('https://mp.weixin.qq.com/s')

    def test_unapproved_target_rejected_before_creating_fifos(self):
        bridge = CurlBridge(self.path)
        with self.assertRaisesRegex(ProbeError, 'target_not_allowed'):
            bridge.read('https://untrusted.test/s?key=private-key')
        self.assertEqual(list(self.path.iterdir()), [])

    def test_transient_nonblocking_read_race_does_not_drop_request(self):
        bridge = CurlBridge(self.path, request_timeout=3)
        thread, _ = self.fake_curl()
        read = os.read
        calls = [0]
        def read_once(fd, size):
            calls[0] += 1
            if calls[0] == 1:
                raise BlockingIOError()
            return read(fd, size)
        with patch('validation.curl_bridge.os.read', side_effect=read_once):
            self.assertEqual(bridge.read('https://mp.weixin.qq.com/s'), b'private-response')
        thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_nonzero_curl_and_redirect_cannot_accept_body(self):
        for code, status, reason in ((60, 0, 'tls_verification_failed'), (0, 302, 'redirect_blocked'),
                                     (18, 200, 'curl_transport_failed'), (0, 'bad', 'bridge_receipt_invalid')):
            folder = self.path / (str(code) + '-' + str(status))
            folder.mkdir(mode=0o700)
            bridge = CurlBridge(folder, request_timeout=3)
            original = self.path
            self.path = folder
            try:
                thread, _ = self.fake_curl(code=code, status=status)
                with self.assertRaisesRegex(ProbeError, reason):
                    bridge.read('https://mp.weixin.qq.com/s')
                thread.join(2)
                self.assertFalse(thread.is_alive())
            finally:
                self.path = original
