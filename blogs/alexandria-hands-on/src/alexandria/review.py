"""Stage 3: gather evidence for the top books, write a digest, and drop every sentence it can't back."""
import re

from .discover import norm
from .gateway import GatewayError

STOP = set("about after again also because been before being between book books both could does doing during each "
           "from have having into itself more most other over same should some such than that their them then there "
           "these they this those through under very what when where which while will with would your readers reader".split())


def words(text):
    return {w for w in re.findall(r"[a-zà-ỹ]{4,}", (text or "").lower()) if w not in STOP}


def gather(conn, work):
    """Ratings from store pages, critics' reviews that name the book, and the publisher's description."""
    rows = []
    for e in conn.execute("select e.*, s.name as site from edition e left join tracked_site s on s.id = e.site_id "
                          "where e.work_id = %s and e.rating is not null and e.rating_count > 0", (work["id"],)).fetchall():
        rows.append(("rating", e["site"] or "store", e["url"], e["rating"], e["rating_count"],
                     f"{e['rating']:.1f} out of 5 from {e['rating_count']} ratings on {e['site']}"))
    title = norm(work["title"])
    if len(title) >= 6:
        for r in conn.execute("select rp.*, s.name as site from review_page rp join tracked_site s on s.id = rp.site_id").fetchall():
            if title in norm(r["headline"]):
                rows.append(("review", r["site"], r["url"], None, None, f"{r['headline']}. {r['description'] or ''}"))
    publisher = conn.execute("select e.url, s.name as site from edition e left join tracked_site s on s.id = e.site_id "
                             "where e.work_id = %s order by (e.language = 'en') desc, e.id limit 1", (work["id"],)).fetchone()
    if work["description"] and publisher:
        rows.append(("publisher", publisher["site"] or "publisher", publisher["url"], None, None, work["description"][:800]))
    evidence = []
    for kind, source, url, rating, count, excerpt in rows:
        row = conn.execute(
            "insert into evidence (work_id, kind, source_name, url, rating, rating_count, excerpt) values (%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (work_id, kind, url) do update set rating = excluded.rating, rating_count = excluded.rating_count, "
            "excerpt = excluded.excerpt, fetched_at = now() returning id",
            (work["id"], kind, source, url, rating, count, excerpt)).fetchone()
        evidence.append({"id": row["id"], "kind": kind, "source": source, "url": url, "excerpt": excerpt})
    return evidence


def validate(digest, evidence, work):
    """Keep a sentence only if it cites real evidence and shares at least one content word with it."""
    by_id = {e["id"]: e for e in evidence}
    ignore = words(work["title"]) | {w for a in work["authors"] for w in words(a)}
    kept, dropped = [], []
    for s in digest["sentences"]:
        cited = [by_id[i] for i in s["evidence_ids"] if i in by_id]
        support = words(s["text"]) - ignore
        backed = cited and support & set().union(*(words(e["excerpt"]) for e in cited))
        (kept if backed else dropped).append({**s, "sources": [{"source": e["source"], "url": e["url"]} for e in cited]})
    return {**digest, "sentences": kept, "dropped": len(dropped)}


def run(conn, gateway, shortlist, top=3, min_sentences=2):
    """Returns (best, runner_ups). best = {"work", "score", "digest", "evidence"} or None."""
    reviewed = []
    for item in shortlist[:top]:
        work = item["work"]
        evidence = gather(conn, work)
        if not evidence:
            continue
        try:
            digest = gateway.run("digest", {"book": {"title": work["title"], "authors": work["authors"],
                                                     "description": (work["description"] or "")[:800]},
                                            "evidence": [{k: e[k] for k in ("id", "kind", "source", "excerpt")} for e in evidence]})
        except GatewayError:
            continue
        digest = validate(digest, evidence, work)
        if len(digest["sentences"]) < min_sentences:
            continue
        bonus = 0.05 * min(len(digest["sentences"]), 4) + (0.1 if any(e["kind"] == "review" for e in evidence) else 0)
        reviewed.append({**item, "final": round(item["score"] + bonus, 4), "digest": digest, "evidence": evidence})
    reviewed.sort(key=lambda r: -r["final"])
    if not reviewed:
        return None, []
    return reviewed[0], [r["work"]["id"] for r in reviewed[1:]]
