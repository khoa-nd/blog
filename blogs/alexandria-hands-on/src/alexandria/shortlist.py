"""Stage 2: pick today's taste facet with Thompson sampling, then shortlist books for it."""
import datetime as dt
import math
import re

from psycopg.types.json import Jsonb

PRIOR_MEAN, PRIOR_WEIGHT = 3.8, 50          # Bayesian average: 50 virtual ratings of 3.8 stars
WILDCARD_WEEKDAY = 3                        # Thursday: one exploration day a week


def prior(priority):
    """Starting Beta(alpha, beta) for a facet: priority 1.0 → Beta(5, 1), priority 0.4 → Beta(2.6, 3.4)."""
    return 1 + 4 * priority, 1 + 4 * (1 - priority)


def facets(conn):
    return conn.execute("select * from taste_facet where status = 'active' order by priority desc, slug").fetchall()


def profile_text(conn):
    row = conn.execute("select text from profile_version where approved_at is not null order by id desc limit 1").fetchone()
    lines = [f"- {f['name']} (priority {f['priority']:.2f})" for f in facets(conn)]
    head = row["text"] + "\n" if row else ""
    return head + "Taste facets, most important first:\n" + "\n".join(lines)


def pick_facet(conn, day, rng):
    """Sample each facet's Beta posterior; the highest draw gets today's slot. Thursday is a wildcard."""
    active = facets(conn)
    state = {r["facet_slug"]: r for r in conn.execute("select * from bandit_state").fetchall()}
    draws = []
    for f in active:
        a, b = (state[f["slug"]]["alpha"], state[f["slug"]]["beta"]) if f["slug"] in state else prior(f["priority"])
        draws.append((rng.betavariate(a, b), f))
    draws.sort(key=lambda d: -d[0])
    if day.weekday() == WILDCARD_WEEKDAY and len(draws) > 3:
        return rng.choice([f for _, f in draws[3:]]), True, draws
    return draws[0][1], False, draws


def keyword_hits(facet, text):
    hits = 0
    for kw in facet["keywords"]:
        hits += len(re.findall(r"\b" + re.escape(kw.lower()) + r"\b", text))
    return hits


def eligible(conn):
    """Works not yet recommended, whose authors were not recommended in the last 30 days."""
    return conn.execute("""
        select w.*, max(e.published) as published,
               (array_agg(e.rating order by e.rating_count desc nulls last))[1] as rating,
               max(e.rating_count) as rating_count,
               bool_or(e.language = 'vi') as sold_in_vn
        from work w join edition e on e.work_id = w.id
        where not exists (select 1 from recommendation r where r.work_id = w.id)
          and not exists (select 1 from recommendation r join work rw on rw.id = r.work_id
                          where r.date > current_date - 30 and rw.authors && w.authors and cardinality(w.authors) > 0)
        group by w.id""").fetchall()


def cheap_score(facet, work, day):
    text = f"{work['title']} {work['title']} {work['description'] or ''}".lower()
    published = work["published"]
    recent = bool(published) and (day - published).days <= 365
    if facet["slug"] == "new-releases":
        taste = 1.0 if recent else 0.0
    else:
        taste = 1 - math.exp(-keyword_hits(facet, text) / 3)
    if work["rating"] and work["rating_count"]:
        n = work["rating_count"]
        bayes = (PRIOR_WEIGHT * PRIOR_MEAN + n * work["rating"]) / (PRIOR_WEIGHT + n)
        quality = max(0.0, min(1.0, (bayes - 3) / 2))
    else:
        quality = 0.4                                   # unknown: neutral, not zero
    prize = 0.15 if "pulitzer" in text else 0.0
    parts = {"taste": round(taste, 3), "quality": round(quality, 3), "fresh": 1.0 if recent else 0.0,
             "vn": 1.0 if work["sold_in_vn"] else 0.0, "prize": prize}
    score = 0.55 * taste + 0.25 * quality + 0.1 * parts["fresh"] + 0.1 * parts["vn"] + prize
    return round(score, 4), parts


def run(conn, gateway, day, rng, keep=5, judge_top=20, skip=()):
    """Returns (facet, exploration, shortlist). The shortlist is ranked, best first. skip: facet slugs already tried."""
    pool = eligible(conn)
    facet, exploration, draws = pick_facet(conn, day, rng)
    order = [f for f in [facet] + [f for _, f in draws if f["slug"] != facet["slug"]] if f["slug"] not in skip]
    for f in order:                                      # fall back to the next facet if this one has no books
        scored = [(w, *cheap_score(f, w, day)) for w in pool]
        scored = [s for s in scored if s[2]["taste"] > 0]
        if scored:
            facet = f
            break
    else:
        return facet, exploration, []
    exploration = exploration and facet is order[0]
    scored.sort(key=lambda s: -s[1])
    top = scored[:judge_top]
    judged = gateway.run("judge", {
        "profile": profile_text(conn), "facet": facet["name"],
        "books": [{"id": w["id"], "title": w["title"], "authors": w["authors"], "year": w["year"],
                   "description": (w["description"] or "")[:700]} for w, _, _ in top]})
    by_id = {s["id"]: s for s in judged["scores"]}
    ranked = []
    for w, cheap, parts in top:
        j = by_id.get(w["id"])
        judge = (0.6 * j["fit"] + 0.2 * j["depth"] + 0.2 * j["readability"]) / 10 if j else 0.0
        ranked.append({"work": w, "score": round(0.5 * cheap + 0.5 * judge, 4),
                       "parts": {**parts, "cheap": cheap, "judge": round(judge, 3), "reason": j["reason"] if j else ""}})
    ranked.sort(key=lambda r: -r["score"])
    for i, r in enumerate(ranked[:keep]):
        conn.execute("insert into candidate (run_date, work_id, facet_slug, score, parts, rank) values (%s,%s,%s,%s,%s,%s) "
                     "on conflict (run_date, work_id) do update set score = excluded.score, parts = excluded.parts, rank = excluded.rank",
                     (day, r["work"]["id"], facet["slug"], r["score"], Jsonb(r["parts"]), i + 1))
    return facet, exploration, ranked[:keep]
