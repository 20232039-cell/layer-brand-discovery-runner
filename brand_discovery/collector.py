"""Dependency-free, conservative public-page collector. Never authenticates."""
import csv
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from .schema import adapt

AGENT = 'LayerBrandEvidenceBot/0.1'
LIMIT = 2_000_000
BLOCKED = ('instagram.com', 'facebook.com', 'threads.net')

class Refused(Exception):
    pass

def canonical(url):
    p = urlsplit(url.strip())
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise Refused('invalid_url')
    host = p.hostname.lower().encode('idna').decode()
    if any(host == x or host.endswith('.' + x) for x in BLOCKED):
        raise Refused('manual_social_collection_required')
    # Queries may contain tracking or secrets. Input must be a clean public URL.
    if p.query:
        raise Refused('query_not_allowed')
    return urlunsplit(('https', host, p.path or '/', '', ''))

def public_ip(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = {a[4][0] for a in addresses}
    if not ips or any(not ipaddress.ip_address(x).is_global for x in ips):
        raise Refused('non_public_address')
    return sorted(ips)[0]

class PinnedTLS(http.client.HTTPSConnection):
    def connect(self):
        ip = public_ip(self.host)
        raw = socket.create_connection((ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)

class Fetcher:
    def __init__(self, delay=2.0):
        self.delay = max(2.0, delay)
        self.last = {}
        self.robots = {}
        self.deadline = float('inf')

    def raw(self, url):
        url = canonical(url)
        p = urlsplit(url)
        wait = self.delay - (time.monotonic() - self.last.get(p.hostname, 0))
        if wait > 60 or time.monotonic() + max(0, wait) + 15 > self.deadline:
            raise Refused('rate_or_time_budget_exceeded')
        if wait > 0:
            time.sleep(wait)
        self.last[p.hostname] = time.monotonic()
        conn = PinnedTLS(p.hostname, timeout=15, context=ssl.create_default_context())
        try:
            conn.request('GET', p.path or '/', headers={'User-Agent': AGENT, 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            body = response.read(LIMIT + 1)
            if len(body) > LIMIT:
                raise Refused('response_too_large')
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), body
        finally:
            conn.close()

    def allowed(self, url):
        p = urlsplit(url)
        origin = 'https://' + p.hostname
        if origin not in self.robots:
            status, _, body = self.raw(origin + '/robots.txt')
            rp = RobotFileParser()
            if status == 404:
                rp.parse([])
            elif status == 200:
                rp.parse(body.decode('utf-8', 'replace').splitlines())
            else:
                raise Refused('robots_unavailable')
            self.robots[origin] = rp
        rp = self.robots[origin]
        delay = rp.crawl_delay(AGENT) or rp.crawl_delay('*') or 0
        rate = rp.request_rate(AGENT) or rp.request_rate('*')
        self.delay = max(self.delay, delay, rate.seconds / rate.requests if rate else 0)
        if not rp.can_fetch(AGENT, url):
            raise Refused('robots_disallow')

    def get(self, url):
        url = canonical(url)
        for _ in range(4):
            self.allowed(url)
            status, headers, body = self.raw(url)
            if status in (301, 302, 303, 307, 308):
                new = canonical(urljoin(url, headers.get('location', '')))
                # Cross-origin redirects need human identity review; never silently follow.
                if urlsplit(new).hostname != urlsplit(url).hostname:
                    raise Refused('cross_origin_redirect')
                url = new
                continue
            if status != 200:
                raise Refused('http_' + str(status))
            if 'text/html' not in headers.get('content-type', ''):
                raise Refused('not_html')
            return url, body.decode('utf-8', 'replace')
        raise Refused('redirect_limit')

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self.jsonld = [], [], []
        self.skip = 0
        self.structured = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
            self.structured = tag == 'script' and a.get('type') == 'application/ld+json'
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
            self.structured = False
    def handle_data(self, data):
        if self.structured:
            self.jsonld.append(data)
        elif not self.skip:
            self.parts.append(data)

def extract(url, html):
    page = Page()
    page.feed(html)
    text = re.sub(r'\s+', ' ', ' '.join(page.parts))
    apparel = sorted(set(re.findall(r'상의|하의|아우터|원피스|니트|셔츠|팬츠|티셔츠|\b(?:SHIRT|PANTS|OUTER|KNIT|DRESS)\b', text, re.I)))
    emails = sorted({x[7:].split('?')[0] for x in page.links if x.startswith('mailto:') and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', x[7:].split('?')[0])})
    instagram = sorted({urljoin(url, x) for x in page.links if urlsplit(urljoin(url, x)).hostname in ('instagram.com', 'www.instagram.com')})
    platforms = [name for name, marker in [('cafe24', 'cafe24'), ('imweb', 'imweb'), ('shopify', 'cdn.shopify.com')] if marker in html.lower()]
    return {'visible_text_excerpt': text[:12000], 'apparel_terms': apparel,
            'email_links_observed': emails, 'instagram_links_observed_unvisited': instagram,
            'platform_hints': platforms, 'cart_text_observed': bool(re.search('장바구니|add to cart', text, re.I)),
            'identity_status': 'unverified', 'korean_brand_status': 'unverified',
            'apparel_primary_status': 'unverified', 'current_sale_status': 'unverified',
            'cart_function_status': 'not_tested'}

def stable_id(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def safe_cell(value):
    s = str(value)
    return "'" + s if s.lstrip().startswith(('=', '+', '-', '@')) else s

def write_csv(path, rows, fields):
    with open(str(path) + '.tmp', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: safe_cell(r.get(k, '')) for k in fields} for r in rows)
    Path(str(path) + '.tmp').replace(path)

def validate_private_root(root, code_root):
    root, code_root = Path(root).resolve(), Path(code_root).resolve()
    if root == code_root or code_root in root.parents or root in code_root.parents:
        raise Refused('data_must_be_separate_from_public_code')
    if not (root / '.private-data-root').is_file():
        raise Refused('private_root_marker_missing')
    return root

def run(root, limit=30, seconds=1800, fetcher=None):
    fetcher = fetcher or Fetcher()
    evidence_dir = root / 'evidence'
    evidence_dir.mkdir(exist_ok=True)
    checkpoint_path = root / 'checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    with (root / 'candidates.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    exclusion_file = root / 'exclusions.json'
    exclusions = json.loads(exclusion_file.read_text()) if exclusion_file.exists() else {'names': [], 'urls': []}
    normalize = lambda x: re.sub(r'[^a-z0-9가-힣]', '', x.lower())
    excluded_names = {normalize(n) for n in exclusions['names']}
    excluded_urls = {canonical(u) for u in exclusions['urls']}
    seen, processed = set(), 0
    deadline = time.monotonic() + seconds
    if isinstance(fetcher, Fetcher):
        fetcher.deadline = deadline
    for row in rows:
        ident = stable_id(row)
        source = adapt(row)
        name = source['name']
        raw_url = source['official_url']
        try:
            url = canonical(raw_url)
        except (Refused, ValueError):
            url = ''
        # Duplicate URLs are review candidates, not merged identities; multi-brand stores exist.
        duplicate = bool(url and url in seen)
        if url:
            seen.add(url)
        if ident in checkpoint:
            continue
        if processed >= limit or time.monotonic() >= deadline:
            break
        processed += 1
        result = {**source, 'candidate_id': ident, 'name': name, 'submitted_url': raw_url,
                  'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'needs_review'}
        if not url:
            result['status'] = 'invalid_or_unsupported_url'
        elif normalize(name) in excluded_names or url in excluded_urls:
            result['status'] = 'excluded_known_brand'
        elif duplicate:
            result['status'] = 'possible_duplicate_review'
        else:
            try:
                final_url, html = fetcher.get(url)
                result.update(extract(final_url, html))
                result['fetched_url'] = final_url
                result['source_sha256'] = hashlib.sha256(html.encode()).hexdigest()
            except Refused as exc:
                result['status'] = str(exc) if re.fullmatch('[a-z0-9_]+', str(exc)) else 'fetch_refused'
            except Exception:
                result['status'] = 'fetch_failed'
        atomic_json(evidence_dir / (ident + '.json'), result)
        checkpoint[ident] = result
        atomic_json(checkpoint_path, checkpoint)
    fields = ['candidate_id', 'name', 'submitted_url', 'status', 'checked_at', 'source_schema', 'source_verdict', 'identity_status', 'korean_brand_status', 'apparel_primary_status', 'current_sale_status', 'cart_function_status']
    atomic_json(checkpoint_path, checkpoint)
    output = list(checkpoint.values())
    write_csv(root / 'review_queue.csv', output, fields)
    from .xlsx import write_xlsx
    write_xlsx(root / 'review_queue.xlsx', output, fields)
    return processed
