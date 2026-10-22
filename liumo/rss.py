"""One public RSS source. Feed times never decide original publication time."""

import hashlib
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

ACCOUNT = "猫笔刀"
BIZ = "MzE5ODk2NjUwOA=="
FEED = "https://wechat2rss.xlab.app/feed/33d986064f59be5263de2ca822fb3e0bdd59eb81.xml"


class MVPError(Exception):
    """Only fixed, locally defined reason codes may reach ordinary output."""


def image_source(url):
    """Use the explicit Tencent image URL carried by the feed's public proxy URL.

    This is a deterministic source selection, never a failure-triggered retry.
    No proxy token, browser cookie or WeChat account credential is needed.
    """
    p=urlsplit(url)
    if p.hostname=='wechat2rss.xlab.app' and p.path=='/img-proxy/':
        q=parse_qs(p.query)
        if p.scheme!='https' or p.netloc!='wechat2rss.xlab.app' or set(q)!={'k','u'} or any(len(v)!=1 for v in q.values()):
            raise MVPError('image_proxy_url_rejected')
        url=q['u'][0]
        p=urlsplit(url)
    if (p.scheme!='https' or p.username or p.password or p.port not in (None,443) or p.fragment
            or not (p.hostname or '').endswith(('.qpic.cn','.qlogo.cn'))):
        raise MVPError('image_source_rejected')
    return url


def read_image(url, limit=25*1024*1024):
    return read_public(image_source(url),limit)


def canonical(url, biz=BIZ):
    try:
        p = urlsplit(url)
        q = parse_qs(p.query, strict_parsing=True)
        if (p.scheme != 'https' or p.netloc != 'mp.weixin.qq.com' or p.path != '/s'
                or p.fragment or set(q) - {'__biz', 'mid', 'idx', 'sn'}
                or any(len(v) != 1 for v in q.values()) or q.get('__biz') != [biz]
                or not q.get('mid', [''])[0].isdigit() or not q.get('idx', [''])[0].isdigit()
                or int(q['mid'][0]) <= 0 or not 1 <= int(q['idx'][0]) <= 100):
            raise ValueError
        if 'sn' in q and (len(q['sn'][0]) != 32 or any(c not in '0123456789abcdef' for c in q['sn'][0])):
            raise ValueError
        fields = {k: q[k][0] for k in ('__biz', 'mid', 'idx', 'sn') if k in q}
        fields['mid'], fields['idx'] = str(int(fields['mid'])), str(int(fields['idx']))
        identity = {'biz': biz, 'mid': fields['mid'], 'idx': fields['idx']}
        key = hashlib.sha256(f"{biz}:{identity['mid']}:{identity['idx']}".encode()).hexdigest()[:24]
        return urlunsplit(('https', 'mp.weixin.qq.com', '/s', urlencode(fields), '')), key, identity
    except (ValueError, TypeError, AttributeError):
        raise MVPError('invalid_target_article_url') from None


def public_feed_url(url):
    """Only credential-free public Wechat2RSS feed paths, never management APIs."""
    return bool(re.fullmatch(r'https://wechat2rss\.xlab\.app/feed/(?:[0-9a-f]{40}|[0-9]+)\.xml', url))


def read_public(url, limit=4 * 1024 * 1024):
    """Native curl, verified HTTPS, no credentials/config/redirects/retries."""
    p = urlsplit(url)
    host = p.hostname or ''
    proxy_image = False
    if host == 'wechat2rss.xlab.app' and p.path == '/img-proxy/':
        query = parse_qs(p.query)
        upstream = urlsplit(query.get('u',[''])[0])
        proxy_image = (set(query) == {'k','u'} and all(len(v)==1 for v in query.values())
                       and upstream.scheme=='https' and not upstream.username and not upstream.password
                       and upstream.port in (None,443) and not upstream.fragment
                       and (upstream.hostname or '').endswith(('.qpic.cn','.qlogo.cn')))
    if (p.scheme != 'https' or p.username or p.password or p.port not in (None, 443)
            or p.fragment or not (public_feed_url(url) or proxy_image or host.endswith(('.qpic.cn', '.qlogo.cn')))):
        raise MVPError('public_fetch_target_rejected')
    env = {k: v for k, v in os.environ.items() if k.upper() not in
           {'SSLKEYLOGFILE', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}}
    try:
        r = subprocess.run(['/usr/bin/curl', '--disable', '--silent', '--globoff', '--no-netrc',
                            '--proto', '=https', '--no-location', '--no-insecure',
                            '--connect-timeout', '10', '--max-time', '30', '--max-filesize', str(limit),
                            '--write-out', '\n%{http_code}', '--url', url],
                           capture_output=True, timeout=35, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise MVPError('public_transport_failed') from None
    if r.returncode:
        raise MVPError({60: 'tls_verification_failed', 63: 'response_size_limit'}.get(r.returncode, 'public_transport_failed'))
    data, sep, status = r.stdout.rpartition(b'\n')
    if sep and status.isdigit() and int(status) >= 500:
        raise MVPError('public_service_unavailable')
    if not sep or status != b'200':
        raise MVPError('public_http_rejected')
    if len(data) > limit:
        raise MVPError('response_size_limit')
    return data


def parse_feed(data, account=ACCOUNT, biz=BIZ, max_bytes=4 * 1024 * 1024, max_items=200):
    if len(data) > max_bytes or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise MVPError('feed_size_or_entities_rejected')
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise MVPError('feed_xml_invalid') from None
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None or (channel.findtext('title') or '').strip() != account:
        raise MVPError('feed_account_mismatch')
    items, seen = [], {}
    nodes = channel.findall('item')
    if not 1 <= len(nodes) <= max_items:
        raise MVPError('feed_empty_or_item_limit')
    for node in nodes:
        url, key, identity = canonical((node.findtext('link') or '').strip(), biz)
        title = (node.findtext('title') or '').strip()
        if not title or len(title) > 500:
            raise MVPError('feed_title_invalid')
        try:
            dt = parsedate_to_datetime(node.findtext('pubDate') or '')
            feed_time = dt.isoformat() if dt.tzinfo else None
        except (TypeError, ValueError, OverflowError):
            feed_time = None
        content = node.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or node.findtext('description') or ''
        soup = BeautifulSoup(content,'html.parser')
        for tag in list(soup.select('script,style,iframe,object,embed,noscript,form,input,button,textarea,[hidden]')):
            if tag.parent is not None:
                tag.decompose()
        for tag in list(soup.select('[style]')):
            if tag.parent is not None and any(value in tag.get('style','').replace(' ','').lower() for value in ('display:none','visibility:hidden')):
                tag.decompose()
        body_html = str(soup)
        fingerprint = hashlib.sha256((title+'\n'+body_html).encode()).hexdigest()
        signature = (url, fingerprint, feed_time)
        if key in seen and seen[key] != signature:
            raise MVPError('feed_duplicate_conflict')
        if key not in seen:
            items.append({'key': key, 'url': url, 'identity': identity, 'title': title,
                          'source_sha256':fingerprint,'body_html':body_html,
                          'feed_time': feed_time, 'publication_time_verified': False})
            seen[key] = signature
    return items


def discover():
    return parse_feed(read_public(FEED))
