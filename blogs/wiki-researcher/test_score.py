import unittest

from score import exact_match, f1, normalize


class ScoreTest(unittest.TestCase):
    def test_articles_and_case(self):
        self.assertEqual(exact_match("The United States", ["United States"]), 1.0)

    def test_punctuation(self):
        self.assertEqual(normalize("Arthur's Magazine."), "arthurs magazine")

    def test_partial_credit(self):
        self.assertAlmostEqual(f1("President Richard Nixon", ["Richard Nixon"]), 0.8)

    def test_yes_no_is_all_or_nothing(self):
        self.assertEqual(f1("yes", ["no"]), 0.0)
        self.assertEqual(f1("no it was not", ["no"]), 0.0)
        self.assertEqual(f1("Yes", ["yes"]), 1.0)

    def test_numbers(self):
        self.assertEqual(exact_match("1,844", ["1844"]), 1.0)

    def test_best_of_several_answers(self):
        self.assertEqual(f1("NYC", ["New York City", "NYC"]), 1.0)

    def test_empty_prediction(self):
        self.assertEqual(f1("", ["Paris"]), 0.0)


if __name__ == "__main__":
    unittest.main()
