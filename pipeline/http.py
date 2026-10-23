"""Polite HTTP client with robots checks and an auditable response archive."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = 'JapanCityAtlas/1.0 (university educational research)'


class Client:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.robots = {}
        self.last = {}

    def allowed(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            r = self.session.get(origin + '/robots.txt', timeout=(15, 90))
            if r.status_code == 404:
                text = ''
            else:
                r.raise_for_status()
                text = r.text
            (self.directory / (parts.netloc + '.robots.txt')).write_text(text, encoding='utf-8')
            parser = RobotFileParser()
            parser.parse(text.splitlines())
            self.robots[origin] = (parser, text)
        parser, text = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise PermissionError('robots.txt disallows ' + url)
        # RobotFileParser does not implement wildcard rules. Honor generic
        # wildcard Disallow directives too (used by GeoNames).
        generic = False
        target = parts.path + ('?' + parts.query if parts.query else '')
        for line in text.splitlines():
            key, sep, value = line.partition(':')
            value = value.split('#', 1)[0].strip()
            if key.strip().lower() == 'user-agent':
                generic = value == '*'
            elif generic and key.strip().lower() == 'disallow' and '*' in value:
                pattern = re.escape(value).replace(r'\*', '.*').replace(r'\$', '$')
                if re.match(pattern, target):
                    raise PermissionError('robots.txt wildcard disallows ' + url)
        return origin, max(1, parser.crawl_delay(USER_AGENT) or 0)

    def get(self, url, label):
        for _ in range(6):
            origin, delay = self.allowed(url)
            time.sleep(max(0, delay - (time.monotonic() - self.last.get(origin, 0))))
            r = self.session.get(url, timeout=(15, 90), allow_redirects=False)
            self.last[origin] = time.monotonic()
            if r.is_redirect:
                url = urljoin(url, r.headers['Location'])
                continue
            r.raise_for_status()
            body = r.content
            (self.directory / label).write_bytes(body)
            meta = {'url': r.url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
            (self.directory / (label + '.meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')
            return body, meta
        raise RuntimeError('Too many redirects')
