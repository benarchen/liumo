"""Bounded, non-executing inspection of the one fixed article; no networking."""

import re
import time
import zlib
from email.message import Message
from email.policy import HTTP
from html.parser import HTMLParser
from urllib.parse import unquote_plus, urlsplit

from .capture import TARGETS
from .common import SAMPLES, timestamp
from .http import ProbeError

LIMIT = 4 * 1024 * 1024
BIZ = 'MzE5ODk2NjUwOA=='
EXPECTED = TARGETS[BIZ]
TITLE = '上个月最值的一笔消费'
MARKERS = ('cgiDataNew', 'appmsg_comment', 'getcomment', 'getcommentreply',
           'elected_comment', 'WeixinJSBridge', 'getappmsgext', 'comment_id')
FAILURE_REASONS = frozenset(('html_wire_size_limit', 'html_decoded_size_limit',
    'html_encoded_body_invalid', 'html_encoding_unsupported', 'html_decoder_unavailable',
    'html_text_encoding_invalid', 'html_identity_ambiguous', 'html_access_restricted',
    'html_body_missing', 'html_identity_unverified', 'html_paid_content_unverified',
    'html_script_count_limit', 'html_structure_incomplete', 'html_summary_size_limit'))
VOID = frozenset(('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                  'link', 'meta', 'param', 'source', 'track', 'wbr'))


def response_metadata(status, content_type, encoding, content_type_count=1):
    """Fixed categories only; no arbitrary header/parameter strings escape."""
    out = {'http_status': status if type(status) is int and 100 <= status <= 599 else 0,
           'media': 'malformed', 'charset': 'unknown', 'parameter_count': 0,
           'content_type_count': content_type_count if type(content_type_count) is int and 0 <= content_type_count <= 32 else 33,
           'content_encoding': encoding if encoding in ('', 'identity', 'gzip', 'deflate', 'br') else 'unsupported',
           'accepted': False}
    if content_type_count != 1 or type(content_type_count) is not int:
        out['media'] = 'missing' if content_type_count == 0 else 'ambiguous'
        return out
    if not isinstance(content_type, str) or len(content_type) > 8192 or any(ord(c) < 32 or ord(c) > 126 for c in content_type):
        return out
    if not content_type.strip():
        out['media'] = 'missing'
        return out
    try:
        message = Message(policy=HTTP)
        message['Content-Type'] = content_type
        field = message['Content-Type']
        if field.defects or len(field.params) > 16:
            return out
        media = message.get_content_type()
        out['media'] = {'text/html': 'html', 'application/xhtml+xml': 'xhtml',
                        'application/json': 'json'}.get(media, 'other')
        out['parameter_count'] = len(field.params)
        charset = field.params.get('charset')
        out['charset'] = ('absent' if charset is None else 'utf8' if charset.lower() == 'utf-8'
                          else 'utf8_alias' if charset.lower() in ('utf8', 'utf_8') else 'non_utf8')
        out['accepted'] = (out['http_status'] == 200 and out['media'] == 'html'
                           and out['charset'] in ('absent', 'utf8', 'utf8_alias')
                           and out['content_encoding'] != 'unsupported')
    except Exception:
        out.update(media='malformed', charset='unknown', accepted=False)
    return out


def is_target(url, method):
    if method != 'GET' or not isinstance(url, str) or len(url) > 32768:
        return False
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.netloc != 'mp.weixin.qq.com' or p.fragment:
            return False
        if p.path == urlsplit(SAMPLES['maobidao']).path:
            return True
        if p.path != '/s' or len(p.query.split('&')) > 60:
            return False
        scope = {}
        for part in p.query.split('&'):
            key, _, value = part.partition('=')
            key = unquote_plus(key)
            if key in ('__biz', 'mid', 'idx'):
                if key in scope:
                    return False
                scope[key] = unquote_plus(value)
        return scope == {'__biz': BIZ, 'mid': EXPECTED['mid'], 'idx': EXPECTED['idx']}
    except ValueError:
        return False


def declaration_metadata(status, values, encoding):
    """Recovery policy: one declaration or exactly two fully equal meanings."""
    count = len(values)
    out = response_metadata(status, '', encoding, count)
    out.update(declarations=[], relation='count_rejected')
    if count not in (1, 2):
        return out
    rows = [response_metadata(status, value, encoding) for value in values]
    out['declarations'] = rows
    if count == 1:
        return {**rows[0], 'declarations': rows, 'relation': 'single'}
    if not all(row['accepted'] for row in rows):
        out['relation'] = 'unacceptable_declaration'
        return out
    signatures = []
    for value in values:
        message = Message(policy=HTTP)
        message['Content-Type'] = value
        params = dict(message['Content-Type'].params)
        if 'charset' in params:
            params['charset'] = 'utf-8'  # Each declaration already passed the UTF-8 gate.
        signatures.append((message.get_content_type(), tuple(sorted(params.items()))))
    if signatures[0] != signatures[1]:
        out['relation'] = 'conflicting_declarations'
        return out
    return {**rows[0], 'content_type_count': 2, 'declarations': rows, 'relation': 'equivalent_declarations'}


def decode_body(raw, encoding):
    if len(raw) > LIMIT:
        raise ProbeError('html_wire_size_limit')
    try:
        if encoding in ('', 'identity'):
            return raw
        if encoding in ('gzip', 'deflate'):
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            data = decoder.decompress(raw, LIMIT + 1)
            if len(data) > LIMIT:
                raise ProbeError('html_decoded_size_limit')
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ProbeError('html_encoded_body_invalid')
        elif encoding == 'br':
            import brotli  # Already installed in the isolated capture environment.
            decoder = brotli.Decompressor()
            data = decoder.process(raw, output_buffer_limit=LIMIT + 1)
            if len(data) > LIMIT or not decoder.can_accept_more_data() and not decoder.is_finished():
                raise ProbeError('html_decoded_size_limit')
            if not decoder.is_finished():
                raise ProbeError('html_encoded_body_invalid')
        else:
            raise ProbeError('html_encoding_unsupported')
    except ProbeError:
        raise
    except ImportError:
        raise ProbeError('html_decoder_unavailable') from None
    except Exception:
        raise ProbeError('html_encoded_body_invalid') from None
    return data


def public_script(value):
    """Conservative public Tencent static paths only; never echo rejected input."""
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        return None
    try:
        p = urlsplit('https:'+value if value.startswith('//') else value)
        if (p.scheme != 'https' or p.netloc not in ('res.wx.qq.com', 'res2.wx.qq.com')
                or not p.path.startswith(('/mmbizwap/', '/a/wx_fed/', '/t/wx_fed/'))
                or not re.fullmatch(r'/[A-Za-z0-9_./-]{1,1024}\.js', p.path)
                or any(part in ('.', '..', '') for part in p.path[1:].split('/'))):
            return None
        return 'https://'+p.netloc+p.path
    except ValueError:
        return None


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.scripts, self.sources, self.visible = [], [], [], []
        self.fields = {key: [] for key in ('activity-name', 'js_name', 'js_content')}
        self.nodes = {key: 0 for key in self.fields}
        self.body_image = False
        self.ambiguous = False

    def handle_starttag(self, tag, attrs):
        keys = [key for key, _ in attrs]
        if len(keys) != len(set(keys)):
            self.ambiguous = True
        values = dict(attrs)
        node = values.get('id')
        if node in self.fields:
            self.nodes[node] += 1
        if tag == 'script':
            self.scripts.append('')
            if 'src' in values:
                self.sources.append(values['src'])
        if tag == 'img' and any(n == 'js_content' for _, n in self.stack):
            self.body_image |= bool(values.get('src') or values.get('data-src'))
        if tag not in VOID:
            self.stack.append((tag, node))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == 'script':
            self.scripts[-1] += data
            return
        if any(tag in ('style', 'noscript') for tag, _ in self.stack):
            return
        self.visible.append(data)
        for _, node in self.stack:
            if node in self.fields:
                self.fields[node].append(data)


def literals(scripts, names):
    found = set()
    for name in names:
        pattern = (r'(?:^|[;{},\n])\s*(?:(?:var|let|const)\s+)?[\'\"]?'+re.escape(name)
                   +r'[\'\"]?\s*(?:=|:)\s*(?:[\'\"]([A-Za-z0-9+/=_-]+)[\'\"]|(\d+)\b)')
        for script in scripts:
            found.update(a or b for a, b in re.findall(pattern, script))
    return found


def analyze(raw):
    if len(raw) > LIMIT:
        raise ProbeError('html_decoded_size_limit')
    try:
        html = raw.decode('utf-8-sig', errors='strict')
    except UnicodeError:
        raise ProbeError('html_text_encoding_invalid') from None
    parser = ArticleParser()
    parser.feed(html)
    parser.close()
    if parser.ambiguous:
        raise ProbeError('html_identity_ambiguous')
    if parser.stack:
        raise ProbeError('html_structure_incomplete')
    if not parser.nodes['js_content'] or not (''.join(parser.fields['js_content']).strip() or parser.body_image):
        restricted = any(word in ''.join(parser.visible) for word in ('环境异常', '访问过于频繁', '完成验证', '验证码'))
        raise ProbeError('html_access_restricted' if restricted else 'html_body_missing')
    if parser.ambiguous or any(count != 1 for count in parser.nodes.values()):
        raise ProbeError('html_identity_ambiguous')
    if (' '.join(''.join(parser.fields['activity-name']).split()) != TITLE
            or ''.join(parser.fields['js_name']).strip() != '猫笔刀'
            or any(literals(parser.scripts, names) != {expected} for names, expected in (
                (('biz',), BIZ), (('mid', 'appmsgid'), EXPECTED['mid']), (('idx',), EXPECTED['idx'])))):
        raise ProbeError('html_identity_unverified')
    paid = literals(parser.scripts, ('is_pay_subscribe',))
    if paid and paid != {'0'}:
        raise ProbeError('html_paid_content_unverified')
    sources, rejected, removed = set(), 0, 0
    if len(parser.sources) > 128:
        raise ProbeError('html_script_count_limit')
    for value in parser.sources:
        source = public_script(value)
        if source is None:
            rejected += 1
        else:
            sources.add(source)
            p = urlsplit(value)
            removed += int(bool(p.query or p.fragment))
    scripts = '\n'.join(parser.scripts)
    counts = {key: scripts.count(key) for key in MARKERS}
    has_clues = bool(sources or any(counts.values()))
    return {'status': 'partial' if rejected or not has_clues else 'static_clues_observed',
            'reason': 'html_script_source_rejected' if rejected else 'html_static_clues_observed' if has_clues else 'html_no_static_clues',
            'body_identity_verified': True, 'decoded_bytes': len(raw),
            'inline_marker_counts': counts, 'public_script_sources': sorted(sources),
            'script_elements_count': len(parser.scripts), 'external_script_elements_count': len(parser.sources),
            'rejected_script_sources_count': rejected, 'stripped_query_or_fragment_count': removed,
            'script_execution': False, 'script_fetch_requests': 0,
            'comment_channel_verified': False, 'comment_baseline_verified': False,
            'raw_HTML_persisted': False, 'comment_content_persisted': False}


class StaticSession:
    def __init__(self, writer, gate, clock=time.monotonic, header_diagnostics=False, equivalent_duplicates=False,
                 inline_analysis=False):
        self.writer, self.gate, self.clock = writer, gate, clock
        self.deadline = clock()+60
        self.stopped = self.attempted = self.saved = False
        self.buffer = bytearray()
        self.reason = 'html_waiting_for_target'
        self.result = {}
        self.header_diagnostics = header_diagnostics
        self.equivalent_duplicates = equivalent_duplicates
        self.inline_analysis = inline_analysis
        self.metadata = {}

    def stop(self):
        self.stopped = True
        self.buffer.clear()
        if self.reason == 'html_waiting_for_target':
            self.reason = 'html_stream_incomplete' if self.attempted else 'html_no_target_observed'

    def available(self):
        if self.stopped:
            return False
        if self.clock() >= self.deadline or not self.gate():
            self.reason = 'html_gate_closed'
            self.stop()
            return False
        return True

    def begin(self, status, content_type, encoding, content_type_count=1, content_types=None):
        if not self.available() or self.attempted:
            raise ProbeError('html_gate_closed')
        self.attempted = True
        self.reason = 'html_waiting_for_target'
        if self.header_diagnostics:
            values = [content_type] if content_types is None and content_type_count == 1 else content_types
            self.metadata = (declaration_metadata(status, values, encoding)
                             if self.equivalent_duplicates and isinstance(values, list) else
                             response_metadata(status, content_type, encoding, content_type_count))
            if self.metadata['accepted']:
                self.encoding = encoding
                return self.stream
            self.reason = ('html_HTTP_rejected' if self.metadata['http_status'] != 200 else
                           'html_encoding_unsupported' if self.metadata['content_encoding'] == 'unsupported' else
                           'html_content_type_rejected')
            self.stop()
            raise ProbeError(self.reason)
        if status != 200:
            self.reason = 'html_HTTP_rejected'
        elif not re.fullmatch(r'text/html(?:\s*;\s*charset\s*=\s*[\'\"]?utf-8[\'\"]?)?\s*', content_type, re.I):
            self.reason = 'html_content_type_rejected'
        elif encoding not in ('', 'identity', 'gzip', 'deflate', 'br'):
            self.reason = 'html_encoding_unsupported'
        else:
            self.encoding = encoding
            return self.stream
        self.stop()
        raise ProbeError(self.reason)

    def stream(self, chunk):
        if not self.available():
            return chunk
        if chunk:
            if len(self.buffer)+len(chunk) > LIMIT:
                self.reason = 'html_wire_size_limit'
                self.stop()
            else:
                self.buffer.extend(chunk)
            return chunk
        try:
            wire_bytes = len(self.buffer)
            decoded = decode_body(bytes(self.buffer), self.encoding)
            if self.inline_analysis:
                from .html_inline import analyze as analyze_inline
                remaining = self.deadline - self.clock() - 1
                if remaining <= 0:
                    self.reason = 'html_inline_budget_closed'
                    return chunk
                result = analyze_inline(decoded, remaining_seconds=remaining)
                if not self.available():
                    return chunk  # No write after analysis consumes the active window.
            else:
                result = analyze(decoded)
            self.writer({'version': 1, 'at': timestamp(), 'wire_bytes': wire_bytes, **result,
                         **({'response_metadata': dict(self.metadata)} if self.header_diagnostics else {})})
            self.result, self.saved = result, True
            self.reason = result['reason']
        except ProbeError as exc:
            self.reason = exc.reason if exc.reason in FAILURE_REASONS else 'html_analysis_or_store_failed'
        except Exception:
            self.reason = 'html_analysis_or_store_failed'
        finally:
            self.stop()
        return chunk

    def summary(self):
        if not self.stopped and self.clock() >= self.deadline:
            self.reason = 'html_gate_closed'
            self.stop()
        return {'status': 'closed' if self.stopped else 'open',
                'matched_response_count': int(self.attempted), 'static_summary_saved': self.saved,
                'reason': self.reason, 'body_identity_verified': self.result.get('body_identity_verified', False),
                'saved_by_account': {}, 'active_API_requests': 0,
                'raw_HTML_persisted': False, 'credentials_collected': False,
                'comment_baseline_verified': False,
                **({'response_metadata': dict(self.metadata)} if self.header_diagnostics else {})}
