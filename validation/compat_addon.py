"""Credential-free C16 adapter; never inspect cookies, tokens or response bodies."""

import sys
import time
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from validation.mitm_addon import WechatCaptureAddon
from validation.http import ProbeError


def validate_options(options, plan, directory):
    from validation.certificate_scope import TARGET
    expected = {'confdir': str(directory / 'mitmproxy'), 'listen_host': '127.0.0.1', 'listen_port': 8899,
        'ssl_insecure': False, 'upstream_cert': False, 'add_upstream_certs_to_client_chain': False,
        'flow_detail': 0, 'termlog_verbosity': 'error', 'command_history': False, 'strip_ech': False,
        'save_stream_file': None, 'store_streamed_bodies': False}
    if (any(getattr(options, k, object()) != v for k, v in expected.items())
            or list(options.mode) != [plan['mode']]
            or list(options.allow_hosts) != [r'^mp\.weixin\.qq\.com:443$']
            or list(options.certs) != [TARGET + '=' + str(directory / 'mitmproxy/target-key-chain.pem')]):
        raise ProbeError('compat_proxy_options_rejected')


class CompatibilityAddon(WechatCaptureAddon):
    def select_runtime(self):
        pass

    def make_session(self):
        from validation.transport_diagnostic import DiagnosticSession
        return DiagnosticSession()

    def load(self, loader):
        loader.add_option('liumo_compat', bool, False, 'Enable the one authorized C16 diagnostic.')

    def disable(self):
        from mitmproxy import ctx
        if self.session:
            self.session.stop()
        if not self.passthrough_only:
            self.passthrough_only = True
            ctx.options.update(liumo_compat=False, allow_hosts=[r'(?!)'])

    def configure(self, updated):
        from mitmproxy import ctx
        self.select_runtime()
        if not ctx.options.liumo_compat:
            if self.session:
                self.session.stop()
            return
        try:
            from validation.compat_session import DIRECTORY, load_plan, digest, KEYS
            plan = load_plan()
            validate_options(ctx.options, plan, DIRECTORY)
            if any(digest(DIRECTORY / 'mitmproxy' / n) != plan['keys'][n] for n in KEYS):
                raise ProbeError('compat_key_identity_changed')
            if self.session is None:
                self.session = self.make_session()
                self.runtime_directory = DIRECTORY
                self.wall_deadline = plan['active_deadline']
            self.capture_disabled()
        except Exception:
            self.disable()
            raise ProbeError('compat_addon_configuration_rejected') from None

    def capture_disabled(self):
        if self.runtime_directory:
            from validation.capture_session import private_json
            try:
                disabled = private_json(self.runtime_directory / 'state.json').get('capture_disabled') is not False
                expired = time.time() >= self.wall_deadline or self.session.summary()['status'] == 'closed'
            except Exception:
                disabled, expired = True, True
            if disabled or expired:
                self.disable()

    def publish(self, running=True):
        try:
            super().publish(running)
        except Exception:
            self.disable()  # A broken journal cannot leave observation running.


addons = [CompatibilityAddon()]
