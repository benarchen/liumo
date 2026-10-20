"""C24 fixed scope, fresh authorization and existing finite system controller."""

import hashlib
import json
import os
import time

from .common import ROOT, parse_time
from .capture_session import private_json
from .credentials import check_private
from .html_static import LIMIT, StaticSession, analyze, response_metadata, declaration_metadata
from .http import ProbeError

DIRECTORY = ROOT / '.auth/wechat-capture/article-static-session'
STATIC_DIRECTORY = DIRECTORY
METADATA_DIRECTORY = DIRECTORY.parent / 'article-static-metadata-session'
DUPLICATE_DIRECTORY = DIRECTORY.parent / 'article-static-duplicates-session'
INLINE_DIRECTORY = DIRECTORY.parent / 'article-inline-session'
AUTHORIZATION = DIRECTORY.parent / 'article-static-authorization.json'
UI_READY = ROOT / '.tmp/wechat-session-validation/article-static-ui-ready.json'
PREVIOUS_REFRESH = DIRECTORY.parent / 'comment-refresh-session'
READY_STATUS = 'ready_user_refresh_maobidao_for_static_inspection'
EXPERIMENT = 'article_static'


def select_metadata_mode():
    global DIRECTORY, AUTHORIZATION, UI_READY, READY_STATUS, EXPERIMENT
    DIRECTORY = METADATA_DIRECTORY
    AUTHORIZATION = DIRECTORY.parent / 'article-static-metadata-authorization.json'
    UI_READY = ROOT / '.tmp/wechat-session-validation/article-static-metadata-ui-ready.json'
    READY_STATUS = 'ready_user_refresh_maobidao_for_static_metadata'
    EXPERIMENT = 'article_static_metadata'


def select_duplicate_mode():
    global DIRECTORY, AUTHORIZATION, UI_READY, READY_STATUS, EXPERIMENT
    DIRECTORY = DUPLICATE_DIRECTORY
    AUTHORIZATION = DIRECTORY.parent / 'article-static-duplicates-authorization.json'
    UI_READY = ROOT / '.tmp/wechat-session-validation/article-static-duplicates-ui-ready.json'
    READY_STATUS = 'ready_user_refresh_maobidao_for_static_duplicates'
    EXPERIMENT = 'article_static_duplicates'


def select_inline_mode():
    global DIRECTORY, AUTHORIZATION, UI_READY, READY_STATUS, EXPERIMENT
    DIRECTORY = INLINE_DIRECTORY
    AUTHORIZATION = DIRECTORY.parent / 'article-inline-authorization.json'
    UI_READY = ROOT / '.tmp/wechat-session-validation/article-inline-ui-ready.json'
    READY_STATUS = 'ready_user_refresh_maobidao_for_inline_analysis'
    EXPERIMENT = 'article_inline'


def review_plan():
    result = {'status': 'plan_only', 'experiment': EXPERIMENT,
            'private_session': str(DIRECTORY), 'authorization': str(AUTHORIZATION),
            'previous_system_experiments': 10, 'target': 'maobidao_fixed_article',
            'duration_seconds': 180, 'cleanup_reserve_seconds': 120,
            'max_passive_responses': 1, 'wire_limit_bytes': LIMIT, 'decoded_limit_bytes': LIMIT,
            'manual_circular_arrow_refresh_once': True, 'strict_UTF8': True,
            'raw_HTML_persisted': False, 'Cookie_headers_read': False,
            'script_execution': False, 'automatic_script_fetch': False,
            'active_API_requests': 0, 'public_control_requests': 1,
            'requires_fresh_authorization_bound_to_closed_C22': True, 'executed': False}
    if EXPERIMENT in ('article_static_metadata', 'article_static_duplicates'):
        result.update(previous_system_experiments=11, fixed_response_metadata=True,
                      requires_fresh_authorization_bound_to_closed_C22=False,
                      requires_fresh_authorization_bound_to_closed_C24=True)
    if EXPERIMENT == 'article_static_duplicates':
        result.update(previous_system_experiments=12, equivalent_duplicate_Content_Type_only=True,
                      requires_fresh_authorization_bound_to_closed_C24=False,
                      requires_fresh_authorization_bound_to_closed_C25=True)
    if EXPERIMENT == 'article_inline':
        result.update(previous_system_experiments=13, fixed_response_metadata=True,
                      equivalent_duplicate_Content_Type_only=True,
                      requires_fresh_authorization_bound_to_closed_C22=False,
                      requires_fresh_authorization_bound_to_closed_C26=True,
                      inline_JS_AST_in_memory=True, script_text_persisted=False,
                      parser_timeout_seconds=10, max_script_elements=128,
                      external_source_fixed_shape_counts=True, stop_owned_proxy_group_with_Node_child=True)
    return result


def authorized():
    try:
        proof = private_json(AUTHORIZATION)
        inline = EXPERIMENT == 'article_inline'
        duplicate = EXPERIMENT == 'article_static_duplicates'
        metadata = EXPERIMENT in ('article_static_metadata', 'article_static_duplicates')
        source = (DUPLICATE_DIRECTORY if inline else METADATA_DIRECTORY if duplicate else STATIC_DIRECTORY if metadata else PREVIOUS_REFRESH) / 'state.json'
        old = private_json(source)
        recovery = old.get('recovery', {})
        same = proof.get('source_result_sha256') == hashlib.sha256(source.read_bytes()).hexdigest()
        valid_time = parse_time(old['recovery_completed_at']) <= parse_time(proof['authorized_at'])
        required = {'experiment': EXPERIMENT, 'source': 'explicit_user_grant',
                    'duration_seconds': 180, 'cleanup_reserve_seconds': 120,
                    'max_passive_responses': 1, 'wire_limit_bytes': LIMIT, 'decoded_limit_bytes': LIMIT,
                    'manual_circular_arrow_refresh_once': True,
                    'in_memory_article_HTML_inspection': True,
                    'sanitized_public_script_sources_only': True,
                    'Cookie_headers_read': False, 'raw_HTML_persisted': False}
        if metadata:
            required['fixed_response_metadata'] = True
            if (old.get('capture', {}).get('reason') != 'html_content_type_rejected'
                    or old.get('capture', {}).get('matched_response_count') != 1
                    or old.get('static_summary_saved') is not False):
                raise ValueError()
        if duplicate:
            required['equivalent_duplicate_Content_Type_only'] = True
            observed = old.get('capture', {}).get('response_metadata', {})
            if (observed.get('http_status') != 200 or observed.get('content_type_count') != 2
                    or observed.get('media') != 'ambiguous' or observed.get('accepted') is not False):
                raise ValueError()
        if inline:
            required.update(fixed_response_metadata=True, equivalent_duplicate_Content_Type_only=True,
                            inline_JS_AST_in_memory=True, script_text_persisted=False,
                            parser_timeout_seconds=10, max_script_elements=128,
                            external_source_fixed_shape_counts=True, stop_owned_proxy_group_with_Node_child=True)
            capture = old.get('capture', {})
            if (old.get('static_summary_saved') is not True or capture.get('body_identity_verified') is not True
                    or capture.get('matched_response_count') != 1):
                raise ValueError()
        if (any(type(proof.get(k)) is not type(v) or proof[k] != v for k, v in required.items())
                or not same or not valid_time or old.get('status') != 'closed' or old.get('finished') is not True
                or any(recovery.get(k) is not True for k in ('verified', 'proxy_verified', 'process_stopped', 'keys_removed'))
                or recovery.get('trust', {}).get('verified') is not True):
            raise ValueError()
    except (OSError, ProbeError, ValueError, TypeError, KeyError, AttributeError):
        raise ProbeError('html_static_not_authorized') from None


def select_runtime():
    from . import compat_session as runtime
    from .comment_baseline import ARTICLE_DIRECTORY, BASELINE_DIRECTORY
    runtime.DIRECTORY = DIRECTORY
    runtime.PREVIOUS = (*runtime.anchor.PREVIOUS, runtime.anchor.DIRECTORY, runtime.COMPAT_DIRECTORY,
                        ARTICLE_DIRECTORY, BASELINE_DIRECTORY, PREVIOUS_REFRESH)
    duplicate = EXPERIMENT == 'article_static_duplicates'
    metadata = EXPERIMENT in ('article_static_metadata', 'article_static_duplicates')
    inline = EXPERIMENT == 'article_inline'
    if metadata or inline:
        runtime.PREVIOUS = (*runtime.PREVIOUS, STATIC_DIRECTORY)
    if duplicate or inline:
        runtime.PREVIOUS = (*runtime.PREVIOUS, METADATA_DIRECTORY)
    if inline:
        runtime.PREVIOUS = (*runtime.PREVIOUS, DUPLICATE_DIRECTORY)
    runtime.UI_READY = UI_READY
    runtime.EXPERIMENT = 'article_static'
    runtime.ADDON = ROOT / ('validation/html_inline_addon.py' if inline else 'validation/html_static_duplicates_addon.py' if duplicate else
                            'validation/html_static_metadata_addon.py' if metadata else 'validation/html_static_addon.py')
    runtime.READY_STATUS = READY_STATUS
    runtime.WORKER_FLAG = '--html-inline-worker' if inline else '--html-static-duplicates-worker' if duplicate else '--html-static-metadata-worker' if metadata else '--html-static-worker'
    runtime.RUN_SLUG = 'article-inline-session' if inline else 'article-static-duplicates-session' if duplicate else 'article-static-metadata-session' if metadata else 'article-static-session'
    return runtime


def ready():
    authorized()
    state = private_json(DIRECTORY / 'state.json')
    in_window = (time.time() < private_json(DIRECTORY / 'plan.json')['active_deadline']
                 if EXPERIMENT == 'article_inline' else True)
    return (in_window and state.get('status') == READY_STATUS and state.get('capture_disabled') is False
            and state.get('diagnostic_control', {}).get('proxy_response_observed') is True)


def store_summary(data):
    check_private(DIRECTORY)
    raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
    if len(raw) > 262144:
        raise ProbeError('html_summary_size_limit')
    fd = os.open(DIRECTORY / 'static-summary.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def make_session():
    inline = EXPERIMENT == 'article_inline'
    result = StaticSession(store_summary, ready,
        header_diagnostics=EXPERIMENT in ('article_static_metadata', 'article_static_duplicates') or inline,
        equivalent_duplicates=EXPERIMENT == 'article_static_duplicates' or inline,
        inline_analysis=inline)
    if inline:
        remaining = max(0, min(60, private_json(DIRECTORY / 'plan.json')['active_deadline'] - time.time()))
        result.deadline = result.clock() + remaining
    return result


def fixture():
    if EXPERIMENT == 'article_inline':
        from .html_inline import analyze as analyze_inline
        raw = (ROOT / 'examples/pages/article-static.html').read_bytes()
        return {**analyze_inline(raw), 'evidence': 'constructed_HTML_with_JS_no_network',
                'system_settings_changed': False}
    path = ROOT / 'examples/pages/article-static.html'
    with path.open('rb') as stream:
        raw = stream.read(LIMIT+1)
    metadata = ({'response_metadata': response_metadata(200, 'Text/HTML; Charset="utf-8"; fixture=constructed', '')}
                if EXPERIMENT in ('article_static_metadata', 'article_static_duplicates') else {})
    if EXPERIMENT == 'article_static_duplicates':
        metadata = {'response_metadata': declaration_metadata(200,
            ['text/html; charset=utf-8; fixture=constructed', 'Text/HTML; fixture="constructed"; charset="UTF-8"'], '')}
    return {**analyze(raw), **metadata, 'evidence': 'constructed_HTML_no_network', 'system_settings_changed': False}


def session():
    authorized()
    return select_runtime().session()


def recover():
    return select_runtime().manual_recover()


def observe(phase):
    return select_runtime().observe(phase)


def finish():
    runtime = select_runtime()
    runtime.load_plan()
    state = private_json(DIRECTORY / 'state.json')
    if state.get('status') != READY_STATUS or state.get('finished') is not False:
        raise ProbeError('html_static_not_running')
    fd = os.open(DIRECTORY / 'FINISH', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    return {'status': 'cleanup_requested', 'UI_refresh_verified_by_snapshot': False}
