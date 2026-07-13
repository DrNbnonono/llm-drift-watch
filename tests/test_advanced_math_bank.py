#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from advanced_math_bank import audit_advanced_math_bank, build_advanced_math_bank, recompute_answer  # noqa: E402


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

    def test_audit_rejects_more_than_three_numeric_reskins(self):
        base = self.formal[0]
        copies = []
        for index in range(4):
            item = {**base, "question_id": f"A1-X{index:03d}", "prompt_template": f"求多项式 x²+{index}x+1 在 x={index + 2} 时的值。"}
            copies.append(item)
        audit = audit_advanced_math_bank(copies)
        self.assertFalse(audit["passed"])
        self.assertEqual(audit["violations"][0]["rule"], "parameter_reskin_limit")

    def test_source_seed_catalog_prevents_template_farming(self):
        items = [*self.formal, *self.reserve]
        audit = audit_advanced_math_bank(items)
        self.assertTrue(audit["passed"], audit["violations"])
        self.assertGreaterEqual(audit["source_catalog_count"], 12)
        self.assertGreaterEqual(audit["distinct_source_seed_count"], 200)
        self.assertLessEqual(audit["max_items_per_source_seed"], 2)
        self.assertLessEqual(audit["max_items_per_prompt_cluster"], 2)


if __name__ == "__main__":
    unittest.main()
