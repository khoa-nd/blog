import os
import unittest

import numpy as np
import pymupdf

from config import PDF_DIR
from highlight import find_boxes
from search import companies, maxsim, rrf


class LateInteraction(unittest.TestCase):
    def test_maxsim_takes_best_patch_per_query_token(self):
        q = np.array([[1.0, 0.0], [0.0, 1.0]])            # two query tokens
        page_a = np.array([[1.0, 0.0], [0.0, 1.0]])       # matches both tokens perfectly
        page_b = np.array([[0.7, 0.7], [0.1, 0.0]])       # one blurry patch
        vecs = np.vstack([page_a, page_b])
        scores = maxsim(q, vecs, np.array([0, 2, 4]))
        np.testing.assert_allclose(scores, [2.0, 1.4])

    def test_maxsim_handles_pages_of_different_lengths(self):
        q = np.array([[1.0, 0.0]])
        vecs = np.array([[0.2, 0.0], [0.9, 0.0], [0.5, 0.0]])
        np.testing.assert_allclose(maxsim(q, vecs, np.array([0, 1, 3])), [0.2, 0.9])


class Fusion(unittest.TestCase):
    def test_rrf_rewards_agreement(self):
        fused = rrf([[("a", 9), ("b", 8)], [("b", 5), ("c", 4)]])
        self.assertEqual(fused[0][0], "b")
        self.assertEqual({p for p, _ in fused}, {"a", "b", "c"})


class Companies(unittest.TestCase):
    def test_finds_one_or_several_banks(self):
        self.assertEqual(companies("Did JPMorganChase execute its buyback?"), {"jpmorgan_chase_2024"})
        self.assertEqual(companies("Compare Bank of America's Series B and Citigroup's Series O"),
                         {"bank_of_america_2024", "citigroup_2024"})
        self.assertEqual(companies("total assets of the bank"), set())

    def test_morgan_stanley_is_not_jpmorgan(self):
        self.assertEqual(companies("Morgan Stanley wealth management revenue"), {"morgan_stanley_2024"})


class Evidence(unittest.TestCase):
    page = pymupdf.open(os.path.join(PDF_DIR, "jpmorgan_chase_2024.pdf"))[107]

    def test_quote_found_on_page(self):
        rects, how = find_boxes(self.page, "Aggregate purchase price of common stock")
        self.assertEqual(how, "quote")
        self.assertGreaterEqual(len(rects), 1)

    def test_falls_back_to_answer_numbers(self):
        rects, how = find_boxes(self.page, "a quote that is not on this page", "It spent $18,841 million in 2024.")
        self.assertEqual(how, "numbers")
        self.assertGreaterEqual(len(rects), 1)


if __name__ == "__main__":
    unittest.main()
