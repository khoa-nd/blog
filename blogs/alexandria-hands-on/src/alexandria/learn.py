"""Stage 5 and the loop: reactions become rewards, rewards update the facet bandit, notes become proposals."""
from psycopg.types.json import Jsonb

from .gateway import GatewayError
from .shortlist import facets, prior

REWARD = {"finished": 1.0, "want": 0.6, "not": 0.0}
COMMENT_WEIGHT = 0.2


def parse_comments(conn, gateway):
    n = 0
    for r in conn.execute("select x.id, x.comment, w.title from reaction x join recommendation rc on rc.id = x.rec_id "
                          "join work w on w.id = rc.work_id where x.kind = 'comment' and x.parsed is null").fetchall():
        try:
            parsed = gateway.run("parse_comment", {"comment": r["comment"] or "", "book_title": r["title"]})
        except GatewayError:
            continue
        conn.execute("update reaction set parsed = %s where id = %s", (Jsonb(parsed), r["id"]))
        if parsed["taste_suggestion"].strip():
            conn.execute("insert into proposal (kind, payload, reason) values ('taste_text', %s, %s)",
                         (Jsonb({"text": parsed["taste_suggestion"]}), f"from a comment on {r['title']}"))
        n += 1
    return n


def parse_taste_notes(conn, gateway):
    """Free-text taste notes (console or comments) become concrete facet changes for me to approve."""
    current = [{"slug": f["slug"], "name": f["name"], "priority": f["priority"]} for f in facets(conn)]
    n = 0
    for p in conn.execute("select * from proposal where kind = 'taste_text' and status = 'pending'").fetchall():
        try:
            change = gateway.run("parse_taste", {"text": p["payload"]["text"], "facets": current})
        except GatewayError:
            continue
        change["priority"] = max(0.0, min(1.0, change["priority"]))
        conn.execute("insert into proposal (kind, payload, reason) values ('taste_change', %s, %s)",
                     (Jsonb(change), f"{p['reason']}: \"{p['payload']['text'][:200]}\""))
        conn.execute("update proposal set status = 'parsed', decided_at = now() where id = %s", (p["id"],))
        n += 1
    return n


def rewards(conn):
    """Strongest signal wins (Finished > the latest of Want it / Not for me); comments nudge it. Silence is not a signal."""
    n = 0
    for rec in conn.execute("select distinct rec_id from reaction").fetchall():
        rows = conn.execute("select * from reaction where rec_id = %s order by at", (rec["rec_id"],)).fetchall()
        kinds = [r["kind"] for r in rows if r["kind"] != "comment"]
        sentiments = [r["parsed"]["sentiment"] for r in rows if r["kind"] == "comment" and r["parsed"]]
        if "finished" in kinds:
            base = REWARD["finished"]
        elif kinds:
            base = REWARD[kinds[-1]]
        elif sentiments:
            base = 0.5
        else:
            continue
        nudge = COMMENT_WEIGHT * (sum(sentiments) / len(sentiments)) if sentiments else 0.0
        value = max(0.0, min(1.0, base + nudge))
        conn.execute("insert into reward (rec_id, value, parts) values (%s,%s,%s) on conflict (rec_id) do update "
                     "set value = excluded.value, parts = excluded.parts, updated_at = now()",
                     (rec["rec_id"], value, Jsonb({"base": base, "nudge": round(nudge, 3), "signals": kinds})))
        n += 1
    return n


def bandit(conn):
    """Recompute each facet's Beta posterior from its prior and every reward so far (idempotent)."""
    totals = {r["facet_slug"]: r for r in conn.execute(
        "select rc.facet_slug, sum(rw.value) as s, count(*) as n from reward rw join recommendation rc on rc.id = rw.rec_id "
        "where not rc.exploration group by rc.facet_slug").fetchall()}
    for f in facets(conn):
        a, b = prior(f["priority"])
        t = totals.get(f["slug"])
        if t:
            a, b = a + float(t["s"]), b + float(t["n"]) - float(t["s"])
        conn.execute("insert into bandit_state (facet_slug, alpha, beta) values (%s,%s,%s) on conflict (facet_slug) "
                     "do update set alpha = excluded.alpha, beta = excluded.beta, updated_at = now()", (f["slug"], a, b))


def reflect(conn, gateway):
    week = conn.execute("select w.title, rc.facet_slug as facet, x.kind, x.comment from reaction x "
                        "join recommendation rc on rc.id = x.rec_id join work w on w.id = rc.work_id "
                        "where x.at > now() - interval '7 days' order by x.at").fetchall()
    if len(week) < 3:
        return None                                      # too little to say anything
    out = gateway.run("reflect", {"facets": [{"slug": f["slug"], "name": f["name"], "priority": f["priority"]}
                                              for f in facets(conn)], "week": [dict(r) for r in week]})
    conn.execute("insert into proposal (kind, payload, reason) values ('profile', %s, 'weekly reflection')",
                 (Jsonb({"text": out["profile_text"]}),))
    known = {f["slug"]: f for f in facets(conn)}
    for c in out["changes"]:
        if c["slug"] in known:
            f = known[c["slug"]]
            conn.execute("insert into proposal (kind, payload, reason) values ('taste_change', %s, %s)",
                         (Jsonb({"slug": f["slug"], "name": f["name"], "priority": max(0.0, min(1.0, c["priority"])),
                                 "keywords": [], "status": f["status"]}), c["reason"]))
    return out


def run(conn, gateway, weekly=False):
    result = {"comments": parse_comments(conn, gateway), "taste_notes": parse_taste_notes(conn, gateway),
              "rewards": rewards(conn)}
    bandit(conn)
    if weekly:
        result["reflection"] = bool(reflect(conn, gateway))
    return result
