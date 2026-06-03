#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from generate_formal_bank import generate_bank  # noqa: E402
from question_bank_runtime import rouge_l_score, run_function_tests  # noqa: E402
from validate_bank_artifacts import validate_required  # noqa: E402


class QuestionBankPipelineTests(unittest.TestCase):
    def test_generate_bank_counts(self):
        rewrites, items = generate_bank()
        self.assertEqual(len(rewrites), len(items))
        self.assertEqual(len(items), 627)
        modules = {}
        for item in items:
            modules[item["module"]] = modules.get(item["module"], 0) + 1
        self.assertEqual(modules["A1"], 50)
        self.assertEqual(modules["A2"], 50)
        self.assertEqual(modules["A6"], 50)
        self.assertEqual(modules["B8"], 66)
        self.assertEqual(modules["C4"], 10)

    def test_exec_scoring_harness(self):
        code = "def sum_even(nums):\n    return sum(n for n in nums if n % 2 == 0)"
        passed, total, _ = run_function_tests(code, [{"harness": "print(sum_even([1,2,3,4]))", "expected": "6"}])
        self.assertEqual((passed, total), (1, 1))

    def test_rouge_l_basic(self):
        self.assertGreater(rouge_l_score("alpha beta gamma", "alpha gamma"), 0.6)


if __name__ == "__main__":
    unittest.main()
