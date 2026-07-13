#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_advanced_math_source_cards import build_source_cards  # noqa: E402


class AdvancedMathSourceCardTests(unittest.TestCase):
    def test_every_card_has_a_real_problem_answer_solution_and_traceable_license(self):
        formal, reserve = build_source_cards()
        self.assertEqual(len(formal), 240)
        self.assertEqual(len(reserve), 160)
        cards = [*formal, *reserve]
        self.assertEqual(len({card["card_id"] for card in cards}), 400)
        self.assertEqual(len({card["source_item"]["original_id"] for card in cards}), 400)
        for card in cards:
            self.assertTrue(card["source_item"]["prompt"].strip())
            self.assertTrue(card["source_item"]["answer"].strip())
            self.assertTrue(card["source_item"]["reference_solution"].strip())
            self.assertTrue(card["source"]["url"].startswith("https://"))
            self.assertEqual(card["formalization"]["direct_public_reuse"], False)
            self.assertTrue(card["knowledge_taxonomy"]["evidence"])


if __name__ == "__main__":
    unittest.main()
