#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_qbv13_bank import build_qbv13  # noqa: E402


class QBV13AdvancedMathGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rewrites, cls.items, cls.summary = build_qbv13()

    def test_generation_includes_formal_and_reserve_math_items(self):
        formal = [item for item in self.items if item["question_id"].startswith("A1-H")]
        reserve = [item for item in self.items if item["question_id"].startswith("A1-R")]
        self.assertEqual(len(formal), 240)
        self.assertEqual(len(reserve), 160)
        self.assertEqual(Counter(item["qa_status"] for item in formal), Counter(ready=240))
        self.assertEqual(Counter(item["qa_status"] for item in reserve), Counter(frozen=160))
        self.assertEqual(self.summary["main_item_count"], 1510)
        self.assertEqual(self.summary["default_run_item_count"], 1350)
        self.assertEqual(self.summary["advanced_math_formal_count"], 240)
        self.assertEqual(self.summary["advanced_math_reserve_count"], 160)

    def test_every_generated_math_item_has_a_candidate_and_rewrite(self):
        item_ids = {item["question_id"] for item in self.items if item["question_id"].startswith("A1-H") or item["question_id"].startswith("A1-R")}
        rewrite_ids = {rewrite["rewrite_id"] for rewrite in self.rewrites}
        self.assertEqual({f"rw-{question_id.lower()}" for question_id in item_ids}, rewrite_ids & {f"rw-{question_id.lower()}" for question_id in item_ids})


if __name__ == "__main__":
    unittest.main()
