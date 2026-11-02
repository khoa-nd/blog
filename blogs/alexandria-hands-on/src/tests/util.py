"""Test helpers: a fresh database per test module on the local pgserver."""
import atexit
from pathlib import Path

import pgserver
import psycopg
import yaml

from alexandria import db

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def fresh_db(name):
    server = pgserver.get_server(str(ROOT / ".pgdata"), cleanup_mode=None)
    base = server.get_uri()
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"drop database if exists {name} with (force)")
        admin.execute(f"create database {name}")
    url = base.replace("/postgres?", f"/{name}?")
    conn = db.connect(url)
    atexit.register(conn.close)
    db.init_schema(conn)
    return conn


def seed(conn, owner_key="test-owner-key"):
    seeds = yaml.safe_load((ROOT / "config" / "seeds.yaml").read_text())
    for f in seeds["facets"]:
        conn.execute("insert into taste_facet (slug, name, priority, keywords) values (%s,%s,%s,%s)",
                     (f["slug"], f["name"], f["priority"], f["keywords"]))
    for s in seeds["sites"]:
        conn.execute("insert into tracked_site (name, url, kind, language, watch, link_pattern, search_template, mode) "
                     "values (%s,%s,%s,%s,%s,%s,%s,%s)",
                     (s["name"], s["url"], s["kind"], s["language"], s.get("watch", []), s.get("link_pattern"),
                      s.get("search_template"), s.get("mode", "crawl")))
    conn.execute("insert into app_owner (id, key_hash) values (1, encode(sha256(convert_to(%s, 'UTF8')), 'hex'))", (owner_key,))
    return owner_key


def site(conn, name):
    return conn.execute("select * from tracked_site where name = %s", (name,)).fetchone()
