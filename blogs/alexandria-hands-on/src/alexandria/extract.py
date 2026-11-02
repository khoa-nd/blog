"""Pull books and reviews out of HTML: schema.org JSON-LD first, then embedded page data, then Open Graph."""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ISBN13 = re.compile(r"\b97[89]\d{10}\b")
NO_AUTHOR = re.compile(r"^(nhi[eề]u t[aá]c gi[aả]|various|many authors|nhiều tác giả)$", re.I)
REVIEW_HEADLINE = re.compile(r"^(?P<title>.+?) by (?P<author>.+?) review\b", re.I)


def links(html, base, pattern):
    """Absolute URLs on the page whose path matches the site's link pattern, in page order."""
    seen, out = set(), []
    for href in re.findall(r'href="([^"#?]+)', html):
        url = urljoin(base, href)
        if re.search(pattern, url) and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def text_of(html_fragment):
    return BeautifulSoup(html_fragment or "", "html.parser").get_text(" ", strip=True)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _jsonld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            yield from _walk(json.loads(script.string or script.get_text()))
        except ValueError:
            continue


def _types(node):
    t = node.get("@type", [])
    return set(t if isinstance(t, list) else [t])


def _names(value):
    if isinstance(value, str):
        return [n.strip() for n in re.split(r",| and ", value) if n.strip()]
    if isinstance(value, dict):
        return _names(value.get("name", ""))
    if isinstance(value, list):
        return [n for v in value for n in _names(v)]
    return []


def _isbn(*values):
    for value in values:
        match = ISBN13.search(re.sub(r"[-\s]", "", str(value or "")))
        if match:
            return match.group(0)
    return ""


def _from_jsonld(soup):
    for node in _jsonld(soup):
        types = _types(node)
        if not types & {"Book", "Product"} or not node.get("name"):
            continue
        examples = [e for e in _walk(node.get("workExample", [])) if isinstance(e, dict)]
        offers = node.get("offers") or {}
        offers = offers[0] if isinstance(offers, list) and offers else offers
        rating = node.get("aggregateRating") or {}
        book = {"title": node["name"], "authors": _names(node.get("author")),
                "isbn13": _isbn(node.get("isbn"), node.get("gtin13"), *[e.get("isbn") for e in examples]),
                "pages": node.get("numberOfPages"),
                "published": node.get("datePublished") or next((e["datePublished"] for e in examples if e.get("datePublished")), None),
                "description": text_of(node.get("description")),
                "price": offers.get("price") if isinstance(offers, dict) else None,
                "currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
                "rating": rating.get("ratingValue"), "rating_count": rating.get("ratingCount") or rating.get("reviewCount")}
        if "Book" in types or book["isbn13"]:
            return book
    return None


def _from_next_data(html):
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    nodes = [n for n in _walk(data) if "name" in n and "price" in n and ("authors" in n or "rating_average" in n)]
    nodes.sort(key=lambda n: ("specifications" not in n, -len(n)))  # the full product record first
    for node in nodes[:1]:
        specs = {a.get("code"): a.get("value") for group in node.get("specifications") or []
                 for a in group.get("attributes", []) if isinstance(a, dict)}
        return {"title": node["name"], "authors": _names(node.get("authors")),
                "isbn13": _isbn(specs.get("isbn13"), specs.get("isbn")),
                "pages": int(specs["number_of_page"]) if str(specs.get("number_of_page", "")).isdigit() else None,
                "published": (specs.get("publication_date") or "")[:10] or None,
                "description": text_of(node.get("description") or node.get("short_description")),
                "price": node.get("price"), "currency": "VND",
                "rating": node.get("rating_average") or None, "rating_count": node.get("review_count") or None}
    return None


def _from_open_graph(soup):
    og = {m.get("property"): m.get("content") for m in soup.find_all("meta") if m.get("property")}
    if og.get("og:type") not in ("product", "book", "books.book"):
        return None
    title = re.split(r"\s+[|:]\s+", og.get("og:title") or "")[0].strip()
    title = re.sub(r"^Mua\s+", "", title)
    isbn = _isbn(og.get("og:title"), og.get("book:isbn"), og.get("books:isbn"))
    if not title or not isbn:
        return None
    return {"title": title, "authors": [], "isbn13": isbn, "pages": None, "published": None,
            "description": og.get("og:description") or "", "price": og.get("og:price:amount") or og.get("product:price:amount"),
            "currency": og.get("og:price:currency") or og.get("product:price:currency"), "rating": None, "rating_count": None}


def clean_title(title):
    """Store titles carry sales words: 'Mua ', 'Sách ngoại văn: ', a price in brackets."""
    title = re.sub(r"^[\s\-–•]+", "", title.strip())
    title = re.sub(r"^(Mua\s+|Sách ngoại văn:\s*|Sách\s+)", "", title)
    title = re.sub(r"\s+[-–]\s+Sách\b.*$", "", title)
    return re.sub(r"\s*\(\s*[\d.,]+\s*(đ|vnd)?\s*\)\s*$", "", title, flags=re.I).strip(" -–")


def book_from_html(html):
    """The book a product page sells, or None when the page is not about one book."""
    soup = BeautifulSoup(html, "html.parser")
    found = [b for b in (_from_jsonld(soup), _from_next_data(html), _from_open_graph(soup)) if b]
    book = dict(found[0]) if found else None
    for other in found[1:]:          # fill gaps from the other sources on the same page
        for key, value in other.items():
            if book.get(key) in (None, "", []) and value not in (None, "", []):
                book[key] = value
    if not book:
        return None
    book["title"] = clean_title(book["title"])
    book["authors"] = [a for a in book["authors"] if not NO_AUTHOR.match(a.strip())]
    if not book["isbn13"]:                      # some stores print the ISBN only in the page body
        found = set(ISBN13.findall(soup.get_text(" ")))
        book["isbn13"] = found.pop() if len(found) == 1 else ""
    if not book["title"] or not (book["isbn13"] or book["authors"]):
        return None
    if not book["description"]:
        meta = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"})
        book["description"] = (meta.get("content") or "").strip() if meta else ""
    for key in ("price", "rating"):
        try:
            book[key] = float(book[key]) if book[key] not in (None, "") else None
        except (TypeError, ValueError):
            book[key] = None
    try:
        book["rating_count"] = int(book["rating_count"]) if book["rating_count"] else None
        book["pages"] = int(book["pages"]) if book["pages"] else None
    except (TypeError, ValueError):
        book["rating_count"] = book["pages"] = None
    book["published"] = (book["published"] or "")[:10] or None
    return book


def review_from_html(html):
    """A critic's review page: headline, the book's title and author as the headline names them, standfirst."""
    soup = BeautifulSoup(html, "html.parser")
    for node in _jsonld(soup):
        if _types(node) & {"NewsArticle", "Review", "Article"} and node.get("headline"):
            headline = node["headline"].strip()
            match = REVIEW_HEADLINE.match(headline)
            og = {m.get("property"): m.get("content") for m in soup.find_all("meta") if m.get("property")}
            return {"headline": headline, "book_title": match.group("title").strip() if match else None,
                    "book_author": match.group("author").strip() if match else None,
                    "description": og.get("og:description") or "",
                    "published": (node.get("datePublished") or "")[:10] or None}
    return None
