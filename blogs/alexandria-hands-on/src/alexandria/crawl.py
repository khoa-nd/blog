"""A polite fetcher: reads robots.txt first, waits between requests, says who it is."""
import hashlib
import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

UA_NAME = "AlexandriaBot"
UA = f"{UA_NAME}/0.1 (+https://nguyendangkhoa.info/blogs/autonomous-book-curator-hands-on.html)"


def origin(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class Crawler:
    def __init__(self, conn, client=None, sleep=time.sleep, clock=time.monotonic):
        self.conn, self.sleep, self.clock = conn, sleep, clock
        self.client = client or httpx.Client(headers={"User-Agent": UA, "Accept-Language": "en,vi;q=0.8"},
                                             follow_redirects=True, timeout=30)
        self.robots_cache, self.last_hit = {}, {}

    # ---------- robots.txt ----------
    def robots(self, url):
        """Return (parser or None, status). None means: do not crawl this host."""
        host = origin(url)
        if host not in self.robots_cache:
            try:
                r = self.client.get(host + "/robots.txt")
                status = r.status_code
            except httpx.HTTPError:
                self.robots_cache[host] = (None, 0)
                return self.robots_cache[host]
            parser = urllib.robotparser.RobotFileParser()
            if status in (401, 403):
                parser = None                      # the site refuses bots outright
            elif status >= 500:
                parser = None                      # unknown rules: stay away this run
            elif status >= 400:
                parser.parse([])                   # no robots.txt: everything allowed
            else:
                parser.parse(r.text.splitlines())
            self.robots_cache[host] = (parser, status)
        return self.robots_cache[host]

    def allowed(self, url):
        parser, _ = self.robots(url)
        return parser is not None and parser.can_fetch(UA_NAME, url)

    def mode_for(self, site):
        """Decide crawl or link-only for a newly added site."""
        parser, status = self.robots(site["url"])
        if parser is None:
            return "link-only", f"robots.txt answered {status or 'nothing'} to a bot request"
        blocked = [u for u in site["watch"] if not parser.can_fetch(UA_NAME, u)]
        if blocked:
            return "link-only", f"robots.txt disallows {blocked[0]}"
        return "crawl", "robots.txt allows the watched pages"

    def delay_for(self, site):
        parser, _ = self.robots(site["url"])
        crawl_delay = parser.crawl_delay(UA_NAME) if parser else None
        return max(site.get("delay_s") or 10, float(crawl_delay or 0))

    # ---------- fetching ----------
    def get(self, site, url, revalidate=True):
        """Fetch one page. Returns (status, html). html is None when unchanged, refused or failed."""
        if not self.allowed(url):
            return 0, None
        host = origin(url)
        wait = self.delay_for(site) - (self.clock() - self.last_hit.get(host, -1e9))
        if wait > 0:
            self.sleep(wait)
        cached = self.conn.execute("select etag from page_cache where url = %s", (url,)).fetchone()
        headers = {"If-None-Match": cached["etag"]} if (revalidate and cached and cached["etag"]) else {}
        try:
            r = self.client.get(url, headers=headers)
        except httpx.HTTPError:
            self.last_hit[host] = self.clock()
            return 0, None
        self.last_hit[host] = self.clock()
        html = r.text if r.status_code == 200 else None
        self.conn.execute(
            "insert into page_cache (url, site_id, status, etag, content_hash, fetched_at) values (%s,%s,%s,%s,%s, now()) "
            "on conflict (url) do update set status = excluded.status, etag = coalesce(excluded.etag, page_cache.etag), "
            "content_hash = coalesce(excluded.content_hash, page_cache.content_hash), fetched_at = now()",
            (url, site["id"], r.status_code, r.headers.get("etag"),
             hashlib.sha256(html.encode()).hexdigest() if html else None))
        return r.status_code, html
