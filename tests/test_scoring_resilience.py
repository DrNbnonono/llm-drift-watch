from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_engine import score_item  # noqa: E402
from question_bank_runtime import evaluate_constraint_set  # noqa: E402


class ScoringResilienceTests(unittest.TestCase):
    def test_invalid_xml_is_a_zero_score_not_a_run_failure(self):
        score, details = evaluate_constraint_set("not xml", {"constraints": [{"type": "xml_shape", "root": "task"}]})
        self.assertEqual(score, 0.0)
        self.assertFalse(details["constraints"][0]["passed"])

    def test_reference_match_without_reference_defers_to_judge(self):
        item = {"scoring_method": "reference_match", "scoring_params": {}, "ground_truth": None}
        score, details = score_item(item, {"text": "candidate answer"})
        self.assertEqual(score, 0.0)
        self.assertTrue(details["reference_missing"])


if __name__ == "__main__":
    unittest.main()
