import json
import random
import tempfile
import unittest

import yaml

from alexandria.gateway import Gateway, GatewayError
from tests.util import fresh_db

ROUTES = {
    "models": {"broken": {"provider": "test", "price": [1, 1]}, "sloppy": {"provider": "test", "price": [1, 1]},
               "paid": {"provider": "test", "price": [1000000, 1000000]}, "free": {"provider": "fake", "price": [0, 0]},
               "fake": {"provider": "fake", "price": [0, 0]}},
    "tasks": {"write": {"model": "broken", "fallback": ["free"]}, "judge": {"model": "sloppy", "fallback": []},
              "digest": {"model": "paid", "fallback": ["free"]}, "reflect": {"model": "broken", "fallback": []}},
    "budget": {"usd_per_day": 0.5},
    "shadow": {"judge": {"model": "free", "share": 1.0}},
}
BOOK = {"profile": "", "facet": "physics", "book": {"title": "T", "description": "D"}, "digest_sentences": []}


class TestGateway(Gateway):
    replies = []

    def provider(self, model, task, spec, prompt, data):
        if model["provider"] != "test":
            return super().provider(model, task, spec, prompt, data)
        if model is self.models["broken"]:
            raise RuntimeError("HTTP 503")
        return self.replies.pop(0), 100, 50


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = fresh_db("alx_test_gateway")
        cls.routes = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        yaml.safe_dump(ROUTES, cls.routes)
        cls.routes.close()

    def setUp(self):
        self.conn.execute("delete from llm_call")

    def gw(self):
        return TestGateway(self.conn, routes=self.routes.name, rng=random.Random(0))

    def test_fake_answers_match_every_schema(self):
        gw = Gateway(self.conn, fake=True)
        out = gw.run("judge", {"profile": "", "facet": "x", "books": [{"id": 1, "title": "A"}]})
        self.assertEqual(out["scores"][0]["id"], 1)

    def test_falls_back_when_a_provider_fails(self):
        self.assertIn("why_you", self.gw().run("write", BOOK))
        row = self.conn.execute("select ok, error from llm_call where model = 'broken' order by id desc").fetchone()
        self.assertFalse(row["ok"])
        self.assertIn("503", row["error"])

    def test_repairs_invalid_json_once(self):
        TestGateway.replies = ["not json", json.dumps({"scores": []})]
        self.assertEqual(self.gw().run("judge", {"profile": "", "facet": "x", "books": []}), {"scores": []})

    def test_shadow_call_is_logged(self):
        TestGateway.replies = [json.dumps({"scores": []})]
        self.gw().run("judge", {"profile": "", "facet": "x", "books": []})
        self.assertTrue(self.conn.execute("select 1 from llm_call where shadow and task = 'judge'").fetchone())

    def test_budget_switches_to_free_models(self):
        self.conn.execute("insert into llm_call (task, provider, model, ok, cost_usd) values ('x', 'test', 'paid', true, 5)")
        out = self.gw().run("digest", {"book": {"title": "T"}, "evidence": [{"id": 1, "kind": "rating", "source": "S", "excerpt": "4.5 stars"}]})
        self.assertEqual(out["sentences"][0]["evidence_ids"], [1])
        self.assertFalse(self.conn.execute("select 1 from llm_call where model = 'paid' and task = 'digest'").fetchone())

    def test_error_when_every_route_fails(self):
        with self.assertRaises(GatewayError):
            self.gw().run("reflect", {"facets": [], "week": []})


if __name__ == "__main__":
    unittest.main()
