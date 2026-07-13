#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from advanced_math_bank import build_advanced_math_bank, recompute_answer  # noqa: E402


class AdvancedMathBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal, cls.reserve = build_advanced_math_bank()

    def test_exact_ids_and_difficulty_quotas(self):
        self.assertEqual([item["question_id"] for item in self.formal], [f"A1-H{index:03d}" for index in range(1, 241)])
        self.assertEqual([item["question_id"] for item in self.reserve], [f"A1-R{index:03d}" for index in range(1, 161)])
        self.assertEqual(
            Counter(item["difficulty_tier"] for item in self.formal),
            Counter(foundation=20, advanced_hs=60, olympiad=80, undergraduate=60, stretch=20),
        )
        self.assertEqual(
            Counter(item["difficulty_tier"] for item in self.reserve),
            Counter(foundation=14, advanced_hs=40, olympiad=52, undergraduate=40, stretch=14),
        )

    def test_topic_quotas_and_statuses(self):
        self.assertEqual(
            Counter(item["subtype"] for item in self.formal),
            Counter(
                advanced_algebra=30, inequality_optimization=22, number_theory=24, combinatorics=24,
                discrete_probability=28, graph_theory=24, linear_algebra=24, recurrence_generating_functions=18,
                geometry_analytic=16, algorithms_discrete_optimization=12, abstract_algebra_intro=10, information_coding=8,
            ),
        )
        self.assertTrue(all(item["qa_status"] == "ready" for item in self.formal))
        self.assertTrue(all(item["qa_status"] == "frozen" for item in self.reserve))

    def test_every_answer_contract_recomputes_and_has_discrimination_metadata(self):
        for item in [*self.formal, *self.reserve]:
            self.assertEqual(recompute_answer(item["math_blueprint"]), item["answer_contract"]["canonical_answer"], item["question_id"])
            self.assertGreaterEqual(item["reasoning_profile"]["minimum_nontrivial_steps"], 2, item["question_id"])
            self.assertTrue(item["reasoning_profile"]["common_traps"], item["question_id"])
            self.assertTrue(item["discrimination_profile"]["item_family"], item["question_id"])


if __name__ == "__main__":
    unittest.main()
