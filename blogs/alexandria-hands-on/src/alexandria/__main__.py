"""Command line: python -m alexandria <command>. Run with no command for the list."""
import argparse
import datetime as dt
import json
import os
import random
import secrets
import sys
import traceback

import yaml
from pathlib import Path

from . import db, discover, learn, publish, review, shortlist
from .crawl import Crawler
from .gateway import Gateway


def cfg_from_env():
    return {"supabase_url": os.environ.get("SUPABASE_URL", ""), "anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
            "design_url": "https://nguyendangkhoa.info/blogs/autonomous-book-curator-system-design.html"}


def cmd_dev_db(args):
    import pgserver
    server = pgserver.get_server(".pgdata", cleanup_mode=None)
    print(f"export DATABASE_URL='{server.get_uri()}'")


def cmd_db_init(args, conn):
    db.init_schema(conn)
    print("schema ready")


def cmd_owner_key(args, conn):
    key = secrets.token_urlsafe(24)
    conn.execute("insert into app_owner (id, key_hash) values (1, encode(sha256(convert_to(%s, 'UTF8')), 'hex')) "
                 "on conflict (id) do update set key_hash = excluded.key_hash", (key,))
    print("Owner key (shown once; paste it into the console page):\n" + key)


def cmd_seed(args, conn):
    seeds = yaml.safe_load(Path("config/seeds.yaml").read_text())
    for f in seeds["facets"]:
        conn.execute("insert into taste_facet (slug, name, priority, keywords) values (%s,%s,%s,%s) on conflict (slug) do nothing",
                     (f["slug"], f["name"], f["priority"], f["keywords"]))
        conn.execute("insert into taste_event (facet_slug, kind, payload, source) select %s, 'add', '{}', 'seed' "
                     "where not exists (select 1 from taste_event where facet_slug = %s)", (f["slug"], f["slug"]))
    for s in seeds["sites"]:
        conn.execute("insert into tracked_site (name, url, kind, language, watch, link_pattern, search_template, mode, mode_reason, delay_s) "
                     "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (url) do nothing",
                     (s["name"], s["url"], s["kind"], s["language"], s.get("watch", []), s.get("link_pattern"),
                      s.get("search_template"), s.get("mode", "pending"),
                      "set by hand in seeds.yaml" if s.get("mode") else None, s.get("delay_s", 10)))
    learn.bandit(conn)
    print(f"seeded {len(seeds['facets'])} facets and {len(seeds['sites'])} sites")


def cmd_sites(args, conn):
    for name, mode, reason in discover.check_modes(conn, Crawler(conn)):
        print(f"{name:22s} {mode:10s} {reason}")
    for s in conn.execute("select name, mode, mode_reason from tracked_site order by name").fetchall():
        print(f"  {s['name']:22s} {s['mode']:10s} {s['mode_reason'] or ''}")


def cmd_discover(args, conn):
    crawler = Crawler(conn)
    discover.check_modes(conn, crawler)
    gateway = Gateway(conn, fake=args.fake)
    totals = discover.run(conn, crawler, gateway, cap=args.cap, use_llm=args.llm)
    db.log(conn, "discover", "discover", "ok", **totals)
    print(json.dumps(totals, indent=1))


def nightly(conn, day, fake=False, crawl=True, seed=None):
    """00:00 ICT: learn from yesterday, crawl, shortlist, review, store today's pick."""
    rng = random.Random(seed if seed is not None else day.toordinal())
    gateway = Gateway(conn, fake=fake, rng=rng)
    weekly = day.weekday() == 6
    if db.paused(conn):
        db.log(conn, "nightly", "all", "paused")
        return None
    db.log(conn, "nightly", "learn", "ok", **learn.run(conn, gateway, weekly=weekly))
    if crawl:
        crawler = Crawler(conn)
        discover.check_modes(conn, crawler)
        db.log(conn, "nightly", "discover", "ok", **discover.run(conn, crawler, gateway, cap=25 if weekly else 8,
                                                                 use_llm=not fake))
    if conn.execute("select 1 from recommendation where date = %s", (day,)).fetchone():
        db.log(conn, "nightly", "pick", "exists", date=str(day))
        return None
    tried, best = [], None
    for _ in range(4):                      # if no book survives the review check, try the next facet
        facet, exploration, top = shortlist.run(conn, gateway, day, rng, skip=tried)
        db.log(conn, "nightly", "shortlist", "ok" if top else "empty", facet=facet["slug"], exploration=exploration,
               candidates=[t["work"]["title"] for t in top])
        if not top:
            return None
        best, runner_ups = review.run(conn, gateway, top)
        if best:
            break
        db.log(conn, "nightly", "review", "nothing survived", facet=facet["slug"])
        tried.append(facet["slug"])
    if not best:
        return None
    rec = publish.create(conn, gateway, day, facet, exploration, best, runner_ups)
    db.log(conn, "nightly", "pick", "ok", date=str(day), title=best["work"]["title"], facet=facet["slug"],
           dropped_sentences=best["digest"]["dropped"])
    return {"rec_id": rec["id"] if rec else None, "title": best["work"]["title"], "facet": facet["slug"],
            "exploration": exploration, "sentences": len(best["digest"]["sentences"]), "dropped": best["digest"]["dropped"]}


def cmd_nightly(args, conn):
    day = dt.date.fromisoformat(args.date) if args.date else db.today_ict()
    print(json.dumps(nightly(conn, day, fake=args.fake, crawl=not args.no_crawl), indent=1, default=str))


def cmd_publish(args, conn):
    day = dt.date.fromisoformat(args.date) if args.date else db.today_ict()
    if db.paused(conn):
        print("paused")
        return
    page = publish.publish(conn, day, args.blog_dir, cfg_from_env())
    db.log(conn, "publish", "publish", "ok" if page else "nothing ready", page=page, date=str(day))
    print(page or "nothing to publish today")


def cmd_learn(args, conn):
    print(json.dumps(learn.run(conn, Gateway(conn, fake=args.fake), weekly=args.weekly), indent=1, default=str))


def cmd_status(args, conn):
    q = lambda sql: conn.execute(sql).fetchone()
    print("works", q("select count(*) n from work")["n"], "| editions", q("select count(*) n from edition")["n"],
          "| reviews", q("select count(*) n from review_page")["n"], "| picks", q("select count(*) n from recommendation")["n"])
    print("spend today $%.4f | last 7 days $%.4f" % (q("select coalesce(sum(cost_usd),0) s from llm_call where at >= date_trunc('day', now())")["s"],
                                                   q("select coalesce(sum(cost_usd),0) s from llm_call where at > now() - interval '7 days'")["s"]))
    for r in conn.execute("select at, command, stage, status, detail from run_log order by at desc limit 8").fetchall():
        print(f"  {r['at']:%Y-%m-%d %H:%M} {r['command']:8s} {r['stage']:10s} {r['status']:16s} {json.dumps(r['detail'])[:90]}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m alexandria")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("dev-db", help="start a local Postgres for development (pgserver)")
    sub.add_parser("db-init", help="create or update tables and functions")
    sub.add_parser("owner-key", help="create (or rotate) the owner key")
    sub.add_parser("seed", help="load config/seeds.yaml")
    sub.add_parser("sites", help="decide crawl or link-only for new sites from robots.txt")
    d = sub.add_parser("discover", help="crawl tracked sites")
    d.add_argument("--cap", type=int, default=8, help="new product pages per site")
    d.add_argument("--llm", action="store_true", help="use the extract model for pages without structured data")
    d.add_argument("--fake", action="store_true")
    n = sub.add_parser("nightly", help="00:00 ICT run: learn, crawl, shortlist, review, store the pick")
    n.add_argument("--date"), n.add_argument("--fake", action="store_true"), n.add_argument("--no-crawl", action="store_true")
    pub = sub.add_parser("publish", help="07:00 ICT run: render today's page into the blog checkout")
    pub.add_argument("--date"), pub.add_argument("--blog-dir", default=os.environ.get("BLOG_DIR", "blog"))
    l = sub.add_parser("learn", help="rewards, bandit, parse notes (part of nightly)")
    l.add_argument("--fake", action="store_true"), l.add_argument("--weekly", action="store_true")
    sub.add_parser("status", help="counts, spend and the last runs")
    args = p.parse_args(argv)
    if args.command == "dev-db":
        return cmd_dev_db(args)
    conn = db.connect()
    try:
        globals()["cmd_" + args.command.replace("-", "_")](args, conn)
    except Exception as e:
        traceback.print_exc()
        try:
            db.log(conn, args.command, "error", "failed", error=f"{type(e).__name__}: {e}"[:500])
        except Exception:
            pass  # e.g. db-init failed before run_log existed
        sys.exit(1)


if __name__ == "__main__":
    main()
