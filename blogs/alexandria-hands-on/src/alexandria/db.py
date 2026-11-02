"""Database connection, schema setup and the run log."""
import datetime as dt
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
ICT = dt.timezone(dt.timedelta(hours=7))


def connect(url=None):
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (Supabase: Project Settings → Database → Connection string)")
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def init_schema(conn):
    conn.execute((ROOT / "db" / "schema.sql").read_text())


def today_ict():
    return dt.datetime.now(ICT).date()


def log(conn, command, stage, status, **detail):
    conn.execute("insert into run_log (command, stage, status, detail) values (%s, %s, %s, %s)",
                 (command, stage, status, Jsonb(detail)))


def paused(conn):
    row = conn.execute("select value from control where key = 'paused'").fetchone()
    return bool(row) and row["value"] == "true"
