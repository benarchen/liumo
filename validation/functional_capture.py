"""C17: first candidate for the one fixed article, with no legacy overwrites."""

import json
import os
import subprocess

from .capture import CaptureSession, TARGETS, extract_credential
from .capture_session import private_json
from .common import ROOT, article_url
from .credentials import check_private
from .http import ProbeError

DIRECTORY = ROOT / '.auth/wechat-capture/article-functional-session'
UI_READY = ROOT / '.tmp/wechat-session-validation/functional-ui-ready.json'
READY_STATUS = 'ready_refresh_maobidao_article_for_functional_capture'
TARGETS_ONE = {key: value for key, value in TARGETS.items() if value['account'] == '猫笔刀'}


def select_runtime():
    """CLI and worker are isolated processes, like the existing diagnostic modes."""
    from . import compat_session as runtime
    runtime.DIRECTORY = DIRECTORY
    runtime.PREVIOUS = (*runtime.anchor.PREVIOUS, runtime.anchor.DIRECTORY, runtime.COMPAT_DIRECTORY)
    runtime.UI_READY = UI_READY
    runtime.EXPERIMENT = 'article_functional'
    runtime.ADDON = ROOT / 'validation/functional_addon.py'
    runtime.READY_STATUS = READY_STATUS
    runtime.WORKER_FLAG = '--functional-worker'
    runtime.RUN_SLUG = 'article-functional-session'
    return runtime


def gate():
    state = private_json(DIRECTORY / 'state.json')
    return (state.get('status') == READY_STATUS and state.get('capture_disabled') is False
            and state.get('diagnostic_control', {}).get('proxy_response_observed') is True)


def store_candidate(data):
    check_private(DIRECTORY)
    destination = DIRECTORY / 'candidate.json'
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


class ArticleCandidateSession(CaptureSession):
    def __init__(self, writer=None, ready=None, **kwargs):
        super().__init__(seconds=120, targets=TARGETS_ONE,
                         writer=store_candidate if writer is None else writer, **kwargs)
        self.ready = gate if ready is None else ready
        self.attempted = False

    def matching(self, url, method, status):
        if self.attempted or not self.ready():
            raise ProbeError('functional_capture_gate_closed')
        return super().matching(url, method, status)

    def observe(self, url, method, status, request_cookie='', set_cookies=()):
        try:
            target, query = self.matching(url, method, status)
            self.attempted = True  # A malformed first candidate is not retried.
            data = extract_credential(target, query, request_cookie, set_cookies)
            data['public_article_url'] = article_url(url)
            self.writer(data)
            self.saved['猫笔刀'] = 1
            reason = 'functional_candidate_saved_not_verified'
        except ProbeError as exc:
            reason = exc.reason
        except Exception:
            reason = 'functional_candidate_store_or_public_identity_failed'
        self.events[reason] = self.events.get(reason, 0) + 1
        return reason

    def summary(self):
        return {**super().summary(), 'first_target_response_observed': self.attempted}


def session():
    runtime = select_runtime()
    result = runtime.session()
    if result.get('recovery', {}).get('verified') is True:
        # The main environment already has the HTML parser. No new dependency.
        try:
            process = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'validation.functional_check'],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=45, close_fds=True)
            if len(process.stdout) <= 32768:
                value = json.loads(process.stdout)
                if isinstance(value, dict):
                    # The child exports only this fixed projection.
                    result['functional_check'] = {key: value.get(key) for key in
                        ('status', 'reason', 'output', 'body_verified', 'comments', 'requests_attempted')}
        except (OSError, subprocess.TimeoutExpired, ValueError):
            result['functional_check'] = {'status': 'not_verified', 'reason': 'functional_child_unavailable'}
    return result


def recover():
    return select_runtime().manual_recover()


def observe(phase):
    return select_runtime().observe(phase)


def finish():
    return select_runtime().finish()
