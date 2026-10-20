"""Default-off C21 adapter; matching response bytes pass through unchanged."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation.compat_addon import CompatibilityAddon
from validation.comment_baseline import HEADER_FIELDS, CommentBaselineSession, select_runtime
from validation.http import ProbeError


class CommentBaselineAddon(CompatibilityAddon):
    def select_runtime(self):
        select_runtime()

    def make_session(self):
        return CommentBaselineSession()

    def responseheaders(self, flow):
        if self.session is None:
            return
        flow.response.stream = True
        self.capture_disabled()
        if self.session.stopped:
            return
        self.observe_target_http(flow.request.url, 'responses')
        try:
            data = self.session.matching(flow.request.url, flow.request.method, flow.response.status_code)
        except ProbeError:
            self.publish()
            return
        try:
            headers = {key: flow.request.headers.get(key, '') for key in (*HEADER_FIELDS, 'Cookie', 'Referer')}
            callback = self.session.begin(data, headers, flow.response.headers.get_all('set-cookie'),
                                          flow.response.headers.get('content-encoding', '').strip().lower())
            flow.metadata['liumo_comment_baseline'] = True
            def stream(chunk):
                try:
                    return callback(chunk)
                except Exception:
                    self.session.reason = 'comment_stream_unavailable'
                    self.session.stop()
                    return chunk
                finally:
                    self.capture_disabled()
                    self.publish()
            flow.response.stream = stream
        except Exception:
            self.session.reason = 'comment_context_invalid'
            self.session.stop()
        self.publish()

    def error(self, flow):
        if self.session and not self.session.stopped and flow.metadata.get('liumo_comment_baseline'):
            self.session.reason = 'comment_stream_incomplete'
            self.session.stop()
            self.publish()


addons = [CommentBaselineAddon()]
