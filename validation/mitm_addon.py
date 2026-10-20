"""Optional mitmproxy adapter. Importing this file never starts capture."""

# mitmdump loads -s files independently of the project's module search path.
import sys
import asyncio
import time
from pathlib import Path
from urllib.parse import urlsplit

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation.capture import CaptureSession
from validation.capture_plan import check_proxy_options
from validation.http import ProbeError


class WechatCaptureAddon:
    def __init__(self):
        self.session = None
        self.runtime_directory = None
        self.monitor_task = None
        self.wall_deadline = None
        self.passthrough_only = False
        self.diagnostics = {}
        self.last_publication = None

    def load(self, loader):
        loader.add_option("liumo_capture", bool, False, "Explicitly enable an already authorized capture experiment.")
        loader.add_option("liumo_capture_seconds", int, 600, "Capture window, 1 to 600 seconds.")
        loader.add_option("liumo_profile_capture", bool, False, "Use the separately authorized profile-only experiment.")
        loader.add_option("liumo_diagnostic_only", bool, False, "Credential-free 120 second experiment; separate authorization required.")
        loader.add_option("liumo_ui_diagnostic", bool, False, "Separate single diagnostic operated by the Agent, no credentials.")
        loader.add_option("liumo_article_diagnostic", bool, False, "Separate single article-page diagnostic, no credentials.")

    def configure(self, updated):
        from mitmproxy import ctx
        if not ctx.options.liumo_capture:
            if self.session:
                self.session.stop()
            return
        try:
            check_proxy_options(ctx.options)
        except ProbeError:
            if self.session:
                self.session.stop()
            raise
        if self.session is None:
            profile = bool(getattr(ctx.options, "liumo_profile_capture", False))
            diagnostic = bool(getattr(ctx.options, "liumo_diagnostic_only", False))
            ui = bool(getattr(ctx.options, "liumo_ui_diagnostic", False))
            article = bool(getattr(ctx.options, "liumo_article_diagnostic", False))
            from validation.capture_plan import ROOT
            directory = ROOT / ".auth/wechat-capture" / ("article-diagnostic-session" if article else "ui-diagnostic-session" if ui else "diagnostic-session" if diagnostic else "profile-session" if profile else "session")
            if diagnostic:
                from validation.transport_diagnostic import DiagnosticSession
                self.session = DiagnosticSession(ctx.options.liumo_capture_seconds)
            elif profile:
                from validation.profile_capture import ProfileCaptureSession
                self.session = ProfileCaptureSession(directory / "requests", ctx.options.liumo_capture_seconds)
            else:
                self.session = CaptureSession(ctx.options.liumo_capture_seconds)
            if ctx.options.confdir == str(directory / "mitmproxy"):
                self.runtime_directory = directory
                from validation.capture_session import runtime_plan
                self.wall_deadline = runtime_plan(directory)["wall_deadline"]

    def publish(self, running=True):
        if self.runtime_directory:
            from validation.capture_session import private_write
            data = {"running": running, "passthrough_only": self.passthrough_only,
                    "diagnostics": dict(self.diagnostics), **self.session.summary()}
            if data != self.last_publication:
                private_write(self.runtime_directory / "capture.json", data)
                self.last_publication = data

    def tls_failure(self, side, data):
        if self.session and self.session.summary()["status"] == "open":
            key = "tls_" + side + "_failures_seen"
            self.diagnostics[key] = self.diagnostics.get(key, 0) + 1
            sni = getattr(getattr(data, "conn", None), "sni", None)
            scope = "unknown"
            if (isinstance(sni, str) and 0 < len(sni) <= 253 and sni.isascii()
                    and not any(ord(char) < 33 or ord(char) == 127 for char in sni)):
                scope = "target" if sni.rstrip(".").lower() == "mp.weixin.qq.com" else "other"
            key = "tls_" + side + "_failures_" + scope
            self.diagnostics[key] = self.diagnostics.get(key, 0) + 1
            if scope == "target":
                from validation.transport_diagnostic import tls_error_category
                category = tls_error_category(getattr(getattr(data, "conn", None), "error", None))
                key = "tls_" + side + "_target_reason_" + category
                self.diagnostics[key] = self.diagnostics.get(key, 0) + 1

    def tls_failed_client(self, data):
        self.tls_failure("client", data)

    def tls_failed_server(self, data):
        self.tls_failure("server", data)

    def observe_target_http(self, url, phase):
        # Classifications only: no arbitrary path, query, hostname or error.
        try:
            parts = urlsplit(url)
            if parts.hostname != "mp.weixin.qq.com":
                return
            from validation.transport_diagnostic import CONTROL_URL
            if url == CONTROL_URL:
                key = "control_target_" + phase + "_seen"
                self.diagnostics[key] = self.diagnostics.get(key, 0) + 1
                return
            category = ("profile_path" if parts.path == "/mp/profile_ext" else
                        "article_like" if parts.path == "/s" or parts.path.startswith("/s/") else
                        "other_target_path")
            for key in ("target_host_" + phase + "_seen", category + "_" + phase + "_seen"):
                self.diagnostics[key] = self.diagnostics.get(key, 0) + 1
        except ValueError:
            pass

    def capture_disabled(self):
        if self.runtime_directory:
            from validation.capture_session import private_json
            disabled = private_json(self.runtime_directory / "state.json").get("capture_disabled")
            if disabled or time.time() >= self.wall_deadline or self.session.summary()["status"] == "closed":
                self.session.stop()
                if not self.passthrough_only:
                    from mitmproxy import ctx
                    # No new TLS interception after expiry, even if OS recovery
                    # fails. Existing flows finish without collecting headers.
                    self.passthrough_only = True
                    ctx.options.update(liumo_capture=False, allow_hosts=[r"(?!)"])

    def running(self):
        if self.runtime_directory:
            self.publish()
            self.monitor_task = asyncio.create_task(self.monitor())

    async def monitor(self):
        from mitmproxy import ctx
        while True:
            self.capture_disabled()
            self.publish()
            if (self.runtime_directory / "STOP").exists():
                self.session.stop()
                self.publish(False)
                ctx.master.shutdown()
                return
            await asyncio.sleep(0.2)

    def requestheaders(self, flow):
        # Never retain HTTP request bodies, including other paths on this host.
        if self.session is not None:
            flow.request.stream = True
            self.capture_disabled()
            if self.session.summary()["status"] == "open":
                self.observe_target_http(flow.request.url, "requests")
                self.publish()

    def responseheaders(self, flow):
        # Authentication comes only from headers; article/comment bodies stream
        # through untouched and are never read by this addon.
        if self.session is None:
            return
        flow.response.stream = True
        self.capture_disabled()
        if self.session.stopped:
            return
        self.observe_target_http(flow.request.url, "responses")
        try:
            self.session.matching(flow.request.url, flow.request.method, flow.response.status_code)
        except ProbeError:
            self.publish()
            return
        from validation.profile_capture import ProfileCaptureSession
        if isinstance(self.session, ProfileCaptureSession):
            # Only retrieve the named request headers after public-scope match.
            from validation.profile_capture import HEADER_FIELDS
            headers = {key: flow.request.headers.get(key, '') for key in HEADER_FIELDS | {'Cookie'}}
            self.session.observe(flow.request.url, flow.request.method, flow.response.status_code,
                                 headers, flow.response.headers.get_all("set-cookie"))
        else:
            self.session.observe(flow.request.url, flow.request.method, flow.response.status_code,
                                 flow.request.headers.get("cookie", ""),
                                 flow.response.headers.get_all("set-cookie"))
        self.publish()

    def done(self):
        if self.session:
            self.session.stop()
            self.publish(False)
        if self.monitor_task:
            self.monitor_task.cancel()


addons = [WechatCaptureAddon()]
