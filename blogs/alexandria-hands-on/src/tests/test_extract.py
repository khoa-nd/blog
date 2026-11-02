import unittest

from alexandria.extract import book_from_html, clean_title, links, review_from_html
from tests.util import FIXTURES


def page(name):
    return (FIXTURES / f"{name}.html").read_text()


class ExtractTest(unittest.TestCase):
    def test_publisher_book_from_jsonld(self):
        b = book_from_html(page("prh_book"))
        self.assertEqual((b["title"], b["authors"], b["isbn13"], b["pages"]), ("The Peace", ["Romeo Dallaire"], "9780345814418", 264))
        self.assertEqual(b["published"], "2026-10-20")
        self.assertTrue(b["description"])            # taken from the page when the Book record has none

    def test_store_book_merges_page_data(self):
        b = book_from_html(page("tiki_product"))
        self.assertEqual(b["isbn13"], "9781108430494")  # only in the embedded product data
        self.assertEqual((b["currency"], b["rating_count"], b["pages"]), ("VND", 2, 319))

    def test_isbn_from_page_text_when_the_record_has_none(self):
        b = book_from_html(page("fahasa_product"))
        self.assertEqual((b["title"], b["authors"], b["isbn13"]), ("The Kite Runner", ["Khaled Hosseini"], "9781526604736"))

    def test_page_without_book_data_needs_the_model(self):
        self.assertIsNone(book_from_html(page("nhanam_product")))   # Step 10 turns on model extraction for these

    def test_store_titles_lose_sales_words(self):
        self.assertEqual(clean_title("Sách ngoại văn: Project Hail Mary"), "Project Hail Mary")
        self.assertEqual(clean_title("Túp lều bác Tôm (205.000đ)"), "Túp lều bác Tôm")

    def test_review_headline(self):
        r = review_from_html(page("guardian_review"))
        self.assertEqual(r["book_title"], "The Rise and Fall of the Artificial State")
        self.assertEqual(r["book_author"], "Jill Lepore")
        self.assertEqual(r["published"], "2026-08-19")

    def test_non_book_page_is_rejected(self):
        self.assertIsNone(book_from_html(page("guardian_review")))
        self.assertIsNone(book_from_html("<html><head><title>Cart</title></head></html>"))

    def test_links_follow_the_site_pattern(self):
        found = links(page("fahasa_list"), "https://www.fahasa.com/foreigncategory.html", r"https://www\.fahasa\.com/[a-z0-9-]+\.html")
        self.assertTrue(all(u.startswith("https://www.fahasa.com/") for u in found))
        self.assertEqual(len(found), len(set(found)))
        rel = links('<a href="/books/12/x-y">a</a><a href="/about">b</a>', "https://p.com/new/", r"/books/\d+/[a-z0-9-]+")
        self.assertEqual(rel, ["https://p.com/books/12/x-y"])


if __name__ == "__main__":
    unittest.main()
