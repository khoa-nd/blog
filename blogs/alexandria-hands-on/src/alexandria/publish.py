"""Stage 4: store today's recommendation at night, publish it as a page on the blog at 07:00."""
import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote_plus

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psycopg.types.json import Jsonb

from .discover import norm

TEMPLATES = Path(__file__).resolve().parent / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")[:60] or "book"


def create(conn, gateway, day, facet, exploration, best, runner_ups):
    work = best["work"]
    wrote = gateway.run("write", {"profile": "", "facet": facet["name"],
                                  "book": {"title": work["title"], "authors": work["authors"], "year": work["year"],
                                           "description": (work["description"] or "")[:800]},
                                  "digest_sentences": [s["text"] for s in best["digest"]["sentences"]]})
    digest = {**best["digest"], "intro": wrote["intro"]}
    return conn.execute(
        "insert into recommendation (date, work_id, facet_slug, exploration, judge, digest, why, runner_ups) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (date) do nothing returning id",
        (day, work["id"], facet["slug"], exploration, Jsonb(best["parts"]), Jsonb(digest), wrote["why_you"],
         runner_ups)).fetchone()


def find_links(conn, work):
    """Pages where the book was found, then search links on every tracked store (including link-only ones)."""
    out = []
    for e in conn.execute("select e.url, e.price, e.currency, s.name from edition e join tracked_site s on s.id = e.site_id "
                          "where e.work_id = %s order by s.name", (work["id"],)).fetchall():
        price = f"{e['price']:,.0f} {e['currency']}" if e["price"] and e["currency"] == "VND" else (
            f"{e['price']:.2f} {e['currency']}" if e["price"] else "")
        out.append({"label": e["name"], "url": e["url"], "note": price})
    have = {o["label"] for o in out}
    query = quote_plus(f"{work['title']} {(work['authors'] or [''])[0]}".strip())
    for s in conn.execute("select name, search_template from tracked_site where search_template is not null "
                          "and kind in ('bookstore', 'publisher') order by name").fetchall():
        if s["name"] not in have:
            out.append({"label": s["name"], "url": s["search_template"].replace("{q}", query), "note": "search"})
    return out


def vietnamese_editions(conn, work):
    """Vietnamese-language works by the same author: a likely translation, labeled as such."""
    if work["language"] == "vi" or not work["authors"]:
        return []
    surname = norm(work["authors"][0]).split()[-1:]
    rows = conn.execute("select w.title, w.authors, (select url from edition where work_id = w.id limit 1) as url "
                        "from work w where w.language = 'vi' and cardinality(w.authors) > 0").fetchall()
    return [r for r in rows if surname and norm(r["authors"][0]).split()[-1:] == surname][:2]


def write_shared(out_dir, cfg):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.js").write_text("window.ALEXANDRIA = " + json.dumps(
        {"url": cfg["supabase_url"], "anonKey": cfg["anon_key"]}) + ";\n")
    for name in ("alexandria.css", "console.html"):
        shutil.copyfile(TEMPLATES / name, out_dir / name)


def publish(conn, day, blog_dir, cfg):
    """Render today's pick if it is ready, mark it published, and rebuild the index. Returns the page path or None."""
    out_dir = Path(blog_dir) / "blogs" / "alexandria"
    write_shared(out_dir, cfg)
    rec = conn.execute("select r.*, w.title, w.authors, w.year, w.pages, w.language, w.description, f.name as facet_name "
                       "from recommendation r join work w on w.id = r.work_id "
                       "left join taste_facet f on f.slug = r.facet_slug where r.date = %s", (day,)).fetchone()
    page = None
    if rec and rec["status"] == "ready":
        page = f"picks/{day.isoformat()}-{slugify(rec['title'])}.html"
        work = {"id": rec["work_id"], "title": rec["title"], "authors": rec["authors"], "language": rec["language"]}
        html = env.get_template("pick.html").render(
            rec=rec, digest=rec["digest"], links=find_links(conn, work), vn=vietnamese_editions(conn, work),
            design_url=cfg["design_url"])
        (out_dir / "picks").mkdir(exist_ok=True)
        (out_dir / page).write_text(html)
        conn.execute("update recommendation set status = 'published', page_path = %s, published_at = now() where id = %s",
                     (page, rec["id"]))
    picks = conn.execute("select r.date, r.page_path, r.exploration, w.title, w.authors, f.name as facet_name "
                         "from recommendation r join work w on w.id = r.work_id left join taste_facet f on f.slug = r.facet_slug "
                         "where r.status = 'published' order by r.date desc").fetchall()
    (out_dir / "index.html").write_text(env.get_template("index.html").render(picks=picks, design_url=cfg["design_url"]))
    return page
