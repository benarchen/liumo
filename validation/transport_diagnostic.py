"""Credential-free, bounded proxy control; no system settings are changed here."""

import os
import re
import subprocess
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from .capture import CaptureSession
from .credentials import check_private
from .http import ProbeError

DURATION = 120
CONTROL_URL = 'https://mp.weixin.qq.com/robots.txt?liumo_feasibility_control=1'
TLS_REASONS = ('certificate_alert', 'certificate_verification', 'protocol_error',
               'connection_closed', 'ambiguous', 'other', 'unavailable')
OBSERVATION_COUNTERS = frozenset(
    [prefix + '_' + phase + '_seen'
     for prefix in ('control_target', 'target_host', 'profile_path', 'article_like', 'other_target_path')
     for phase in ('requests', 'responses')]
    + ['tls_' + side + '_failures_' + scope
       for side in ('client', 'server') for scope in ('seen', 'target', 'other', 'unknown')]
    + ['tls_' + side + '_target_reason_' + reason
       for side in ('client', 'server') for reason in TLS_REASONS])


def tls_error_category(error):
    """Classify component messages in memory; never return text or infer pinning."""
    if not isinstance(error, str) or not error or len(error) > 4096:
        return 'unavailable'
    message = error.lower()
    markers = {
        'certificate_alert': ('unknown ca', 'bad certificate', 'certificate unknown'),
        'certificate_verification': ('certificate verify failed',),
        'protocol_error': ('unsupported protocol', 'wrong version number',
                           'cannot agree on a tls version'),
        'connection_closed': ('connection closed', 'disconnected during the handshake'),
    }
    matched = [category for category, values in markers.items()
               if any(value in message for value in values)]
    return matched[0] if len(matched) == 1 else 'ambiguous' if matched else 'other'


def observation_snapshot(directory, phase, clock=time.time):
    """Read a bounded live counter sample; caller must separately prove UI action."""
    from .capture_session import private_json
    if phase not in ('before_refresh', 'after_refresh'):
        raise ProbeError('diagnostic_observation_phase_invalid')
    directory = Path(directory)
    check_private(directory)
    plan = private_json(directory / 'plan.json')
    state = private_json(directory / 'state.json')
    capture = private_json(directory / 'capture.json')
    if not all(isinstance(value, dict) for value in (plan, state, capture)):
        raise ProbeError('diagnostic_observation_state_invalid')
    if plan.get('experiment') not in ('diagnostic', 'ui_diagnostic', 'article_diagnostic') or plan.get('duration_seconds') != DURATION:
        raise ProbeError('diagnostic_observation_experiment_invalid')
    now, deadline = clock(), plan.get('wall_deadline')
    if (type(now) not in (int, float) or type(deadline) not in (int, float)
            or not math.isfinite(now) or not math.isfinite(deadline)
            or not deadline - DURATION <= now < deadline):
        raise ProbeError('diagnostic_observation_window_closed')
    ready = ('ready_refresh_maobidao_article_for_diagnostics' if plan['experiment'] == 'article_diagnostic'
             else 'ready_refresh_maobidao_for_diagnostics')
    if (state.get('status') != ready
            or state.get('finished') is not False or state.get('capture_disabled') is not False
            or capture.get('running') is not True or capture.get('status') != 'open'
            or capture.get('passthrough_only') is not False):
        raise ProbeError('diagnostic_observation_not_running')
    counters = capture.get('diagnostics')
    control = state.get('diagnostic_control')
    if not isinstance(counters, dict) or not isinstance(control, dict):
        raise ProbeError('diagnostic_observation_state_invalid')
    selected = {key: counters.get(key, 0) for key in sorted(OBSERVATION_COUNTERS)}
    if any(type(value) is not int or not 0 <= value <= 1000000000 for value in selected.values()):
        raise ProbeError('diagnostic_observation_counters_invalid')
    if not control_verified(control, selected) or control.get('proxy_response_observed') is not True:
        raise ProbeError('diagnostic_observation_control_unverified')
    try:
        at = datetime.fromtimestamp(now, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        raise ProbeError('diagnostic_observation_window_closed') from None
    return {'phase': phase, 'at': at,
            'seconds_remaining': round(deadline - now, 3), 'counters': selected,
            'UI_refresh_verified_by_snapshot': False}


class DiagnosticSession(CaptureSession):
    def __init__(self, seconds=DURATION):
        if seconds != DURATION:
            raise ProbeError('diagnostic_duration_invalid')
        super().__init__(seconds=seconds, targets={})

    def matching(self, *_args):
        raise ProbeError('diagnostic_credentials_disabled')

    def observe(self, *_args, **_kwargs):
        raise ProbeError('diagnostic_credentials_disabled')


def control_probe(directory, run=subprocess.run):
    directory = Path(directory)
    check_private(directory)
    certificate = directory / 'mitmproxy/mitmproxy-ca-cert.pem'
    check_private(certificate.parent)
    if not certificate.is_file() or certificate.is_symlink():
        raise ProbeError('diagnostic_control_certificate_missing')
    command = ['/usr/bin/curl', '--disable', '--silent', '--globoff', '--no-netrc',
               '--proxy', 'http://127.0.0.1:8899', '--noproxy', '', '--proto', '=https',
               '--no-location', '--no-insecure', '--cacert', str(certificate),
               '--connect-timeout', '8', '--max-time', '20', '--max-filesize', '65536',
               '--user-agent', 'liumo-feasibility-control', '--output', os.devnull,
               '--write-out', '%{http_code}', '--url', CONTROL_URL]
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                                          'SSLKEYLOGFILE', 'MITMPROXY_SSLKEYLOGFILE',
                                          'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}}
    result = {'status': 'not_verified', 'request_attempted': False, 'cookies_or_tokens_sent': False,
              'proxy_response_observed': False, 'account_access_verified': False}
    try:
        result['request_attempted'] = True
        response = run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       text=True, timeout=25, env=environment)
        result['curl_exit_code'] = response.returncode
        output = response.stdout.strip()
        if re.fullmatch(r'[1-5][0-9]{2}', output):
            result['http_status'] = int(output)
        if response.returncode == 0 and 'http_status' in result:
            result['status'] = 'https_response_observed'
        else:
            result['reason'] = 'diagnostic_control_transport_or_status_failed'
    except (OSError, subprocess.TimeoutExpired):
        result['reason'] = 'diagnostic_control_transport_failed'
    return result


def control_verified(result, counters):
    return (result.get('status') == 'https_response_observed'
            and counters.get('control_target_requests_seen', 0) > 0
            and counters.get('control_target_responses_seen', 0) > 0)
