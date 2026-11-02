import unittest

import httpx

from alexandria.crawl import Crawler
from tests.util import fresh_db, seed, site


def transport(robots_status=200, robots="User-agent: *\nDisallow: /search/\n", pages=None, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(robots_status, text=robots)
        body = (pages or {}).get(request.url.path)
        if body is None:
            return httpx.Response(404, text="nope")
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, text=body, headers={"etag": '"v1"'})
    return httpx.Client(transport=httpx.MockTransport(handler))


class CrawlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = fresh_db("alx_test_crawl")
        seed(cls.conn)

    def site(self, watch=("https://www.penguinrandomhouse.com/books/new-releases/",)):
        return {**site(self.conn, "Penguin Random House"), "watch": list(watch)}

    def test_forbidden_robots_means_link_only(self):
        c = Crawler(self.conn, client=transport(robots_status=403), sleep=lambda s: None)
        self.assertEqual(c.mode_for(self.site())[0], "link-only")

    def test_disallowed_watch_page_means_link_only(self):
        c = Crawler(self.conn, client=transport(), sleep=lambda s: None)
        mode, reason = c.mode_for(self.site(["https://www.penguinrandomhouse.com/search/x"]))
        self.assertEqual(mode, "link-only")
        self.assertIn("disallows", reason)

    def test_allowed_site_means_crawl(self):
        c = Crawler(self.conn, client=transport(), sleep=lambda s: None)
        self.assertEqual(c.mode_for(self.site())[0], "crawl")

    def test_waits_between_requests_and_honors_crawl_delay(self):
        waits, now = [], [0.0]
        c = Crawler(self.conn, client=transport(robots="User-agent: *\nCrawl-delay: 20\n", pages={"/a": "A", "/b": "B"}),
                    sleep=lambda s: waits.append(s), clock=lambda: now[0])
        s = self.site()
        c.get(s, "https://www.penguinrandomhouse.com/a")
        c.get(s, "https://www.penguinrandomhouse.com/b")
        self.assertEqual(waits, [20.0])               # max(site delay 10, crawl-delay 20)

    def test_revalidates_with_etag(self):
        seen = []
        c = Crawler(self.conn, client=transport(pages={"/c": "C"}, seen=seen), sleep=lambda s: None)
        s = self.site()
        self.assertEqual(c.get(s, "https://www.penguinrandomhouse.com/c"), (200, "C"))
        self.assertEqual(c.get(s, "https://www.penguinrandomhouse.com/c"), (304, None))
        self.assertEqual(seen[-1].headers.get("if-none-match"), '"v1"')

    def test_never_fetches_disallowed_pages(self):
        seen = []
        c = Crawler(self.conn, client=transport(seen=seen), sleep=lambda s: None)
        self.assertEqual(c.get(self.site(), "https://www.penguinrandomhouse.com/search/q"), (0, None))
        self.assertFalse(any(r.url.path.startswith("/search") for r in seen))


if __name__ == "__main__":
    unittest.main()
