"""Stage 1: crawl the tracked sites and turn product pages into works, editions and review pages."""
import re
import unicodedata

from psycopg.types.json import Jsonb

from . import extract
from .gateway import GatewayError


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def work_key(book):
    if book.get("isbn13"):
        return "isbn:" + book["isbn13"]
    return "t:" + norm(book["title"]) + "|" + norm((book.get("authors") or [""])[0])


def check_modes(conn, crawler):
    """Give every new site a mode from its robots.txt. Sites set to link-only by hand stay link-only."""
    decided = []
    for site in conn.execute("select * from tracked_site where mode = 'pending'").fetchall():
        mode, reason = crawler.mode_for(site)
        conn.execute("update tracked_site set mode = %s, mode_reason = %s where id = %s", (mode, reason, site["id"]))
        decided.append((site["name"], mode, reason))
    return decided


def save_book(conn, site, url, book):
    existing = None
    if book.get("isbn13"):
        existing = conn.execute("select work_id from edition where isbn13 = %s limit 1", (book["isbn13"],)).fetchone()
    year = int(book["published"][:4]) if book.get("published") and book["published"][:4].isdigit() else None
    if existing:
        work_id = existing["work_id"]
    else:
        work_id = conn.execute(
            "insert into work (key, title, authors, language, year, pages, description) values (%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (key) do update set description = coalesce(nullif(work.description, ''), excluded.description) "
            "returning id",
            (work_key(book), book["title"][:300], book.get("authors") or [], site["language"], year, book.get("pages"),
             (book.get("description") or "")[:4000])).fetchone()["id"]
    conn.execute(
        "insert into edition (work_id, site_id, url, isbn13, language, price, currency, rating, rating_count, published) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (url) do update set price = excluded.price, "
        "rating = excluded.rating, rating_count = excluded.rating_count, fetched_at = now()",
        (work_id, site["id"], url, book.get("isbn13") or None, site["language"], book.get("price"), book.get("currency"),
         book.get("rating"), book.get("rating_count"), book.get("published")))
    return work_id


def run(conn, crawler, gateway=None, cap=8, refetch_days=14, use_llm=False):
    """Crawl every site in crawl mode. cap = new product pages per site per run."""
    totals = {}
    sites = conn.execute("select * from tracked_site where mode = 'crawl' and cardinality(watch) > 0 order by id").fetchall()
    for site in sites:
        stats = {"listing_pages": 0, "fetched": 0, "books": 0, "reviews": 0, "skipped": 0}
        for watch_url in site["watch"]:
            status, html = crawler.get(site, watch_url, revalidate=False)
            if not html:
                stats["skipped"] += 1
                continue
            stats["listing_pages"] += 1
            fresh = conn.execute(
                "select url from page_cache where site_id = %s and fetched_at > now() - make_interval(days => %s)",
                (site["id"], refetch_days)).fetchall()
            recent = {r["url"] for r in fresh}
            todo = [u for u in extract.links(html, watch_url, site["link_pattern"]) if u not in recent and u != watch_url]
            todo.sort(key=len, reverse=True)       # long product slugs before short category slugs
            for url in todo[:cap]:
                status, page = crawler.get(site, url)
                stats["fetched"] += 1
                if not page:
                    continue
                if site["kind"] == "review":
                    review = extract.review_from_html(page)
                    if review:
                        conn.execute(
                            "insert into review_page (url, site_id, headline, description, published) values (%s,%s,%s,%s,%s) "
                            "on conflict (url) do nothing",
                            (url, site["id"], review["headline"], review["description"], review["published"]))
                        stats["reviews"] += 1
                    continue
                book = extract.book_from_html(page)
                if not book and use_llm and gateway:
                    book = llm_extract(gateway, url, page)
                conn.execute("update page_cache set is_book = %s where url = %s", (book is not None, url))
                if book:
                    save_book(conn, site, url, book)
                    stats["books"] += 1
        health = "ok" if stats["listing_pages"] else "listing unreachable"
        conn.execute("update tracked_site set last_crawl_at = now(), health = %s where id = %s", (health, site["id"]))
        totals[site["name"]] = stats
    return totals


def llm_extract(gateway, url, html):
    """Last resort for pages without structured data: a small model reads the visible text."""
    text = extract.text_of(html)[:6000]
    try:
        out = gateway.run("extract", {"url": url, "text": text})
    except GatewayError:
        return None
    if not out["is_book"] or not out["title"]:
        return None
    return {"title": out["title"], "authors": out["authors"], "isbn13": out["isbn13"], "pages": None, "published": None,
            "description": out["description"], "price": out["price"] or None, "currency": out["currency"] or None,
            "rating": None, "rating_count": None}
