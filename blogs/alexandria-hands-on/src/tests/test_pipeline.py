"""End to end, offline: books in the database → nightly (fake model) → published page → reactions → learning."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from alexandria import discover, learn, publish
from alexandria.__main__ import nightly
from alexandria.extract import book_from_html
from tests.util import FIXTURES, fresh_db, seed, site

BOOKS = [
    ("The Making of the Atomic Bomb", "Richard Rhodes", "A Pulitzer Prize winning history of nuclear physics, the physicists of the Manhattan Project and the atomic age.", 4.4, 9000),
    ("Fermat's Last Theorem", "Simon Singh", "The story of a mathematical riddle: a theorem that defeated mathematicians for 350 years, and its proof.", 4.3, 6000),
    ("Hidden Figures", "Margot Lee Shetterly", "The mathematicians whose calculations sent astronauts to space; a story of science and mathematics.", 4.1, 3000),
    ("The Code Breaker", "Walter Isaacson", "Jennifer Doudna, gene editing and the future of the human race: a story of science and discovery.", 4.2, 5000),
    ("Thinking in Systems", "Donella Meadows", "A primer on systems thinking.", 4.2, 2000),
]


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = fresh_db("alx_test_pipeline")
        cls.key = seed(cls.conn)
        tiki, prh = site(cls.conn, "Tiki"), site(cls.conn, "Penguin Random House")
        discover.save_book(cls.conn, prh, "https://www.penguinrandomhouse.com/books/239736/the-peace",
                           book_from_html((FIXTURES / "prh_book.html").read_text()))
        for i, (title, author, desc, rating, count) in enumerate(BOOKS):
            discover.save_book(cls.conn, tiki if i % 2 else prh, f"https://example.test/{i}",
                               {"title": title, "authors": [author], "isbn13": f"978000000000{i}", "description": desc,
                                "pages": 300, "published": "2012-05-01", "price": 300000.0, "currency": "VND",
                                "rating": rating, "rating_count": count})
        guardian = site(cls.conn, "The Guardian books")
        cls.conn.execute("insert into review_page (url, site_id, headline, description) values (%s, %s, %s, %s)",
                         ("https://www.theguardian.com/books/review-atomic", guardian["id"],
                          "The Making of the Atomic Bomb by Richard Rhodes review – the physicists who changed the world",
                          "A gripping, monumental history of nuclear physics and the people behind it"))
        learn.bandit(cls.conn)
        cls.day = dt.date(2026, 11, 2)                  # a Monday: no wildcard, no weekly reflection
        cls.result = nightly(cls.conn, cls.day, fake=True, crawl=False, seed=1)
        cls.blog = tempfile.mkdtemp()
        cls.page = publish.publish(cls.conn, cls.day, cls.blog, {"supabase_url": "https://x.supabase.co", "anon_key": "anon",
                                                                 "design_url": "https://example.test/design"})

    def test_nightly_stores_one_pick_with_a_backed_digest(self):
        self.assertIsNotNone(self.result)
        rec = self.conn.execute("select * from recommendation where date = %s", (self.day,)).fetchone()
        self.assertGreaterEqual(len(rec["digest"]["sentences"]), 2)
        self.assertTrue(all(s["sources"] for s in rec["digest"]["sentences"]))

    def test_page_is_published_with_reaction_buttons(self):
        html = (Path(self.blog) / "blogs/alexandria" / self.page).read_text()
        self.assertIn(self.result["title"], html)
        self.assertIn('data-kind="finished"', html)
        for name in ("index.html", "console.html", "config.js", "alexandria.css"):
            self.assertTrue((Path(self.blog) / "blogs/alexandria" / name).exists(), name)
        self.assertIn("x.supabase.co", (Path(self.blog) / "blogs/alexandria/config.js").read_text())

    def test_link_only_stores_get_search_links_not_crawls(self):
        html = (Path(self.blog) / "blogs/alexandria" / self.page).read_text()
        self.assertIn("amazon.com/s?k=", html)
        self.assertIn("shopee.vn/search?keyword=", html)

    def test_reactions_become_rewards_and_move_the_bandit(self):
        rec = self.conn.execute("select id, facet_slug from recommendation where date = %s", (self.day,)).fetchone()
        before = self.conn.execute("select alpha from bandit_state where facet_slug = %s", (rec["facet_slug"],)).fetchone()["alpha"]
        self.conn.execute("select alx_react(%s, %s, 'want', null)", (self.key, rec["id"]))
        self.conn.execute("select alx_react(%s, %s, 'comment', 'Loved the story, great pick')", (self.key, rec["id"]))
        learn.run(self.conn, __import__("alexandria.gateway", fromlist=["Gateway"]).Gateway(self.conn, fake=True))
        reward = self.conn.execute("select value from reward where rec_id = %s", (rec["id"],)).fetchone()["value"]
        self.assertAlmostEqual(reward, 0.6 + 0.2 * 0.6, places=5)
        after = self.conn.execute("select alpha from bandit_state where facet_slug = %s", (rec["facet_slug"],)).fetchone()["alpha"]
        self.assertAlmostEqual(after - before, reward, places=4)

    def test_next_night_picks_a_different_book_and_pause_stops_everything(self):
        nxt = nightly(self.conn, self.day + dt.timedelta(days=1), fake=True, crawl=False, seed=2)
        self.assertIsNotNone(nxt)
        self.assertNotEqual(nxt["title"], self.result["title"])
        self.conn.execute("insert into control (key, value) values ('paused', 'true') on conflict (key) do update set value = 'true'")
        try:
            self.assertIsNone(nightly(self.conn, self.day + dt.timedelta(days=2), fake=True, crawl=False))
        finally:
            self.conn.execute("update control set value = 'false' where key = 'paused'")


if __name__ == "__main__":
    unittest.main()
