import unittest

from score import citation_precision, hit, ndcg, number_recall, numbers, recall, token_f1, yes_no


class RetrievalMetrics(unittest.TestCase):
    gold = {"a#1": 2, "a#2": 1}

    def test_perfect_ranking_scores_one(self):
        self.assertAlmostEqual(ndcg(["a#1", "a#2", "x"], self.gold), 1.0)

    def test_order_matters_for_ndcg(self):
        self.assertLess(ndcg(["a#2", "a#1"], self.gold), 1.0)
        self.assertGreater(ndcg(["a#2", "a#1"], self.gold), ndcg(["x", "y", "a#2"], self.gold))

    def test_recall_and_hit(self):
        self.assertEqual(recall(["x", "a#2"], self.gold, k=5), 0.5)
        self.assertEqual(hit(["x", "y"], self.gold), 0.0)
        self.assertEqual(hit(["x", "a#2"], self.gold, k=2), 1.0)


class AnswerChecks(unittest.TestCase):
    def test_numbers_keep_scale_and_skip_years(self):
        self.assertEqual(numbers("In 2024 it repurchased $18.841 billion, up 12.5%."), [18.841e9, 12.5])

    def test_number_recall_across_units(self):
        gold = "repurchases of $18.841 billion"
        self.assertEqual(number_recall("They bought back $18,841 million of stock", gold), 1.0)
        self.assertEqual(number_recall("They bought back 91.7 million shares", gold), 0.0)
        self.assertIsNone(number_recall("Yes.", "Yes, it did."))

    def test_parentheses_and_commas(self):
        self.assertEqual(numbers("a loss of (1,234) and 3,000"), [1234.0, 3000.0])

    def test_yes_no(self):
        self.assertEqual(yes_no("Yes, JPMorgan executed more than half."), "yes")
        self.assertEqual(yes_no("**No** - it did not."), "no")
        self.assertIsNone(yes_no("The program was $30 billion."))

    def test_token_f1(self):
        self.assertEqual(token_f1("The capital is Paris", "Paris is the capital"), 1.0)
        self.assertEqual(token_f1("London", "Paris"), 0.0)

    def test_citation_precision(self):
        self.assertEqual(citation_precision(["a#1", "x#9"], {"a#1": 2}), 0.5)
        self.assertIsNone(citation_precision([], {"a#1": 2}))


if __name__ == "__main__":
    unittest.main()
