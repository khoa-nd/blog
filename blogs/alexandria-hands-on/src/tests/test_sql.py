"""The public API surface: anonymous visitors can call the alx_* functions and nothing else."""
import unittest

import psycopg

from tests.util import fresh_db, seed


class SqlSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = fresh_db("alx_test_sql")
        cls.key = seed(cls.conn)
        work = cls.conn.execute("insert into work (key, title) values ('k', 'A Book') returning id").fetchone()["id"]
        cls.rec = cls.conn.execute("insert into recommendation (date, work_id, facet_slug, digest, why) "
                                   "values (current_date, %s, 'physics-history', '{}', 'why') returning id", (work,)).fetchone()["id"]

    def as_anon(self, sql, params=()):
        with self.conn.transaction():
            self.conn.execute("set local role anon")
            return self.conn.execute(sql, params).fetchone()

    def test_tables_are_closed(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.as_anon("select * from reaction")

    def test_console_needs_the_key(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.as_anon("select alx_console_state('wrong')")
        state = self.as_anon("select alx_console_state(%s) as s", (self.key,))["s"]
        self.assertGreaterEqual(len(state["facets"]), 9)

    def test_owner_and_visitor_reactions_are_kept_apart(self):
        self.assertEqual(self.as_anon("select alx_react(%s, %s, 'want', null) as w", (self.key, self.rec))["w"], "owner")
        self.assertEqual(self.as_anon("select alx_react('', %s, 'not', null) as w", (self.rec,))["w"], "visitor")
        self.assertEqual(self.conn.execute("select count(*) n from reaction where rec_id = %s", (self.rec,)).fetchone()["n"], 1)
        self.assertEqual(self.conn.execute("select count(*) n from visitor_reaction").fetchone()["n"], 1)

    def test_key_check_is_not_public(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.as_anon("select alx_is_owner('x')")

    def test_console_edits_are_recorded_as_events(self):
        self.as_anon("select alx_set_facet(%s, 'chemistry-history', 'History of chemistry', 0.6, array['chemistry'], 'active')", (self.key,))
        event = self.conn.execute("select * from taste_event where facet_slug = 'chemistry-history'").fetchone()
        self.assertEqual((event["kind"], event["source"]), ("add", "console"))

    def test_approving_a_taste_change_applies_it(self):
        pid = self.conn.execute("insert into proposal (kind, payload) values ('taste_change', "
                                "'{\"slug\": \"philosophy\", \"name\": \"Philosophy\", \"priority\": 0.8, \"keywords\": [], \"status\": \"active\"}') "
                                "returning id").fetchone()["id"]
        self.as_anon("select alx_decide_proposal(%s, %s, true)", (self.key, pid))
        f = self.conn.execute("select priority, keywords from taste_facet where slug = 'philosophy'").fetchone()
        self.assertAlmostEqual(f["priority"], 0.8, places=5)
        self.assertIn("philosophy", f["keywords"])     # empty keyword list keeps the old keywords


if __name__ == "__main__":
    unittest.main()
