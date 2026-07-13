#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from advanced_math_scoring import score_advanced_math  # noqa: E402
from evaluation_engine import score_item  # noqa: E402


class AdvancedMathScoringTests(unittest.TestCase):
    def test_reduced_fraction_requires_coprime_numerator_and_denominator(self):
        params = {"format": "reduced_fraction", "canonical_answer": "17/42"}
        self.assertEqual(score_advanced_math("推理。\n答案：17/42", params)[0], 1.0)
        self.assertEqual(score_advanced_math("答案：34/84", params)[0], 0.0)

    def test_vertex_set_is_order_insensitive_but_validated(self):
        params = {
            "format": "vertex_set",
            "canonical_answer": ["a", "c", "f"],
            "universe": ["a", "b", "c", "d", "e", "f"],
        }
        self.assertEqual(score_advanced_math("答案：{f,a,c}", params)[0], 1.0)
        self.assertEqual(score_advanced_math("答案：{a,c,x}", params)[0], 0.0)

    def test_matrix_requires_exact_shape_and_entries(self):
        params = {"format": "matrix", "canonical_answer": [[1, 0], [-2, 3]]}
        self.assertEqual(score_advanced_math("答案：[[1,0],[-2,3]]", params)[0], 1.0)
        self.assertEqual(score_advanced_math("答案：[[1,0,-2,3]]", params)[0], 0.0)

    def test_unsupported_format_is_a_score_not_a_run_failure(self):
        score, details = score_advanced_math("答案：7", {"format": "radical", "canonical_answer": "sqrt(2)"})
        self.assertEqual(score, 0.0)
        self.assertEqual(details["error"], "unsupported_answer_format")

    def test_evaluation_engine_dispatches_advanced_math_contract(self):
        item = {
            "scoring_method": "advanced_math",
            "ground_truth": "17/42",
            "scoring_params": {"format": "reduced_fraction", "canonical_answer": "17/42"},
        }
        score, details = score_item(item, {"text": "答案：17/42"})
        self.assertEqual(score, 1.0)
        self.assertTrue(details["correct"])


if __name__ == "__main__":
    unittest.main()
