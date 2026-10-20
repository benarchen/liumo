"""Fixed-identity HTML to bounded JS syntax counters; source remains in memory."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

from . import html_static as h, inline_scripts as js
from .http import ProbeError

CLASSIC = {'', 'text/javascript', 'application/javascript', 'text/ecmascript', 'application/ecmascript'}
DATA = {'application/json', 'application/ld+json', 'importmap', 'speculationrules'}
SOURCE_REASONS = ('accepted_public', 'invalid_shape', 'relative_source', 'non_https',
                  'unknown_host', 'authority_rejected', 'known_host_path_rejected')


def source_shape(value):
    if h.public_script(value) is not None:
        return 'accepted_public'
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        return 'invalid_shape'
    try:
        p = urlsplit('https:' + value if value.startswith('//') else value)
        if not p.scheme:
            return 'relative_source'
        if p.scheme != 'https':
            return 'non_https'
        if p.hostname not in ('res.wx.qq.com', 'res2.wx.qq.com'):
            return 'unknown_host'
        if p.netloc not in ('res.wx.qq.com', 'res2.wx.qq.com'):
            return 'authority_rejected'
        return 'known_host_path_rejected'
    except ValueError:
        return 'invalid_shape'


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.rows, self.current = [], None

    def handle_starttag(self, tag, attrs):
        if tag != 'script':
            return
        if len(self.rows) >= 128:
            raise ProbeError('html_script_count_limit')
        values = dict(attrs)
        row = {'external': 'src' in values, 'source': '', 'type': values.get('type') or '',
               'src': values.get('src') or '', 'nomodule': 'nomodule' in values}
        self.rows.append(row)
        self.current = row

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == 'script':
            self.current = None

    def handle_endtag(self, tag):
        if tag == 'script':
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current['source'] += data


def analyze(raw, remaining_seconds=10):
    # All existing independent identity/access/encoding guards run before Node can start.
    result = h.analyze(raw)
    parser = ScriptParser()
    parser.feed(raw.decode('utf-8-sig', errors='strict'))
    parser.close()
    coverage = dict.fromkeys(('classic', 'module', 'data', 'unknown_type', 'external', 'nomodule'), 0)
    shapes = dict.fromkeys(SOURCE_REASONS, 0)
    scripts = []
    try:
        for row in parser.rows:
            coverage['nomodule'] += int(row['nomodule'])
            if row['external']:
                coverage['external'] += 1
                shapes[source_shape(row['src'])] += 1
                continue
            kind = row['type'].strip().lower()
            if kind in CLASSIC or kind == 'module':
                category = 'module' if kind == 'module' else 'classic'
                coverage[category] += 1
                scripts.append({'source': row['source'], 'source_type': 'module' if kind == 'module' else 'script'})
            else:
                coverage['data' if kind in DATA else 'unknown_type'] += 1
        output = js.analyze_scripts(scripts, timeout=min(10, remaining_seconds))
    finally:
        parser.rows.clear()
        parser.current = None
        scripts.clear()
    all_inline = output['status'] == 'passed' and not coverage['unknown_type']
    # External code was not fetched even when its public source is allowed.
    complete = all_inline and coverage['external'] == 0 and coverage['data'] == 0
    return {**result, 'status': 'inline_syntax_observed' if complete else 'partial',
            'reason': 'html_inline_syntax_observed' if complete else 'html_inline_coverage_partial',
            'inline_syntax': output, 'script_coverage': coverage,
            'external_source_shapes': shapes, 'all_supported_inline_scripts_parsed': all_inline,
            'all_page_scripts_analyzed': complete, 'source_text_persisted': False}
