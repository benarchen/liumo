"""Default-off C24 adapter; no request headers or unmatched bodies inspected."""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation import html_static_session as runtime
from validation.compat_addon import CompatibilityAddon
from validation.html_static import is_target
from validation.http import ProbeError


class HtmlStaticAddon(CompatibilityAddon):
    def select_runtime(self):
        runtime.select_runtime()

    def make_session(self):
        runtime.authorized()
        return runtime.make_session()

    def request_cleanup(self):
        if self.runtime_directory and self.session and self.session.stopped:
            try:
                runtime.finish()
            except Exception:
                pass  # Existing independent deadline recovery remains mandatory.

    def responseheaders(self, flow):
        if self.session is None:
            return
        flow.response.stream = True
        self.capture_disabled()
        if self.session.stopped:
            return
        self.observe_target_http(flow.request.url, 'responses')
        if not is_target(flow.request.url, flow.request.method):
            self.publish()
            return
        try:
            extra = ({'content_type_count': len(flow.response.headers.get_all('content-type'))}
                     if self.session.header_diagnostics else {})
            if self.session.equivalent_duplicates:
                extra['content_types'] = flow.response.headers.get_all('content-type')
            callback = self.session.begin(flow.response.status_code,
                flow.response.headers.get('content-type', ''),
                flow.response.headers.get('content-encoding', '').strip().lower(), **extra)
            flow.metadata['liumo_html_static'] = True
            def stream(chunk):
                try:
                    return callback(chunk)
                except Exception:
                    self.session.reason = 'html_stream_unavailable'
                    self.session.stop()
                    return chunk
                finally:
                    self.request_cleanup()
                    self.capture_disabled()
                    self.publish()
            flow.response.stream = stream
        except ProbeError:
            pass
        except Exception:
            self.session.reason = 'html_response_metadata_invalid'
            self.session.stop()
        self.request_cleanup()
        self.publish()

    def error(self, flow):
        if self.session and not self.session.stopped and flow.metadata.get('liumo_html_static'):
            self.session.reason = 'html_stream_incomplete'
            self.session.stop()
            self.request_cleanup()
            self.publish()


addons = [HtmlStaticAddon()]
