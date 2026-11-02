import datetime as dt
import random
import unittest

from alexandria import review, shortlist


def work(**kw):
    base = {"id": 1, "title": "The Making of the Atomic Bomb", "description": "A history of nuclear physics and the physicists.",
            "authors": ["Richard Rhodes"], "published": dt.date(1986, 1, 1), "rating": None, "rating_count": None,
            "sold_in_vn": False, "year": 1986}
    return {**base, **kw}


PHYSICS = {"slug": "physics-history", "keywords": ["physics", "physicist", "nuclear", "atomic"], "priority": 1.0}
NEW = {"slug": "new-releases", "keywords": [], "priority": 0.4}


class ScoringTest(unittest.TestCase):
    def test_priors_follow_priority(self):
        self.assertEqual(shortlist.prior(1.0), (5.0, 1.0))
        a, b = shortlist.prior(0.4)
        self.assertAlmostEqual(a / (a + b), 0.4 * 4 / 6 + 1 / 6)

    def test_many_ratings_beat_a_few_perfect_ones(self):
        few = shortlist.cheap_score(PHYSICS, work(rating=5.0, rating_count=3), dt.date(2026, 11, 2))[1]["quality"]
        many = shortlist.cheap_score(PHYSICS, work(rating=4.4, rating_count=40000), dt.date(2026, 11, 2))[1]["quality"]
        self.assertGreater(many, few)

    def test_new_releases_go_by_date(self):
        day = dt.date(2026, 11, 2)
        self.assertEqual(shortlist.cheap_score(NEW, work(published=dt.date(2026, 10, 20)), day)[1]["taste"], 1.0)
        self.assertEqual(shortlist.cheap_score(NEW, work(), day)[1]["taste"], 0.0)

    def test_off_topic_book_has_no_taste_match(self):
        score = shortlist.cheap_score(PHYSICS, work(title="Cooking at Home", description="Recipes."), dt.date(2026, 11, 2))
        self.assertEqual(score[1]["taste"], 0.0)

    def test_validator_drops_unbacked_sentences(self):
        evidence = [{"id": 7, "source": "Guardian", "url": "u", "excerpt": "A gripping account of the Manhattan Project scientists"}]
        digest = {"sentences": [{"text": "Critics call it a gripping account.", "evidence_ids": [7]},
                                {"text": "Critics call it a gripping account.", "evidence_ids": [99]},
                                {"text": "It won three Oscars.", "evidence_ids": [7]}],
                  "who_for": "", "math_level": "light", "red_flags": []}
        out = review.validate(digest, evidence, work())
        self.assertEqual([s["text"] for s in out["sentences"]], ["Critics call it a gripping account."])
        self.assertEqual(out["dropped"], 2)


if __name__ == "__main__":
    unittest.main()
