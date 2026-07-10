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
from audit_bank_quality import template_signature, template_similarity  # noqa: E402
from evaluation_engine import filter_items  # noqa: E402
from extract_public_sources import extract_last_boxed_answer  # noqa: E402
from retire_near_duplicate_items import build_retirement_map  # noqa: E402
from question_bank_runtime import rouge_l_score, run_function_tests  # noqa: E402
from validate_bank_artifacts import validate_required  # noqa: E402


class QuestionBankPipelineTests(unittest.TestCase):
    def test_generate_bank_counts(self):
        rewrites, items = generate_bank()
        self.assertEqual(len(rewrites), len(items))
        self.assertEqual(len(items), 627)
        self.assertTrue(all(item["version"] == "QB-v1.2" for item in items))
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

    def test_qbv12_safety_items_are_not_template_duplicates(self):
        _, items = generate_bank()
        for module in ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]:
            module_items = [item for item in items if item["module"] == module]
            signatures = set()
            for item in module_items:
                if item["prompt_template"]:
                    signature = " ".join(item["prompt_template"].split())
                else:
                    signature = "|".join(
                        f"{turn.get('branch_key', '')}-{turn['turn_index']}-{' '.join(turn['content_template'].split())}"
                        for turn in item["turn_script"]
                    )
                signatures.add(signature)
            self.assertEqual(
                len(signatures),
                len(module_items),
                f"{module} still contains exact template duplicates in QB-v1.2",
            )

    def test_quality_audit_detects_parameter_swap(self):
        left = "A shop sold 12 boxes at 5 dollars each. Return only the answer."
        right = "A shop sold 27 boxes at 8 dollars each. Return only the answer."
        self.assertEqual(template_signature(left), template_signature(right))
        self.assertGreater(template_similarity(left, right), 0.99)

    def test_routine_runs_exclude_draft_and_pilot_items(self):
        items = [
            {"question_id": "ready", "module": "A5", "qa_status": "ready"},
            {"question_id": "frozen", "module": "A5", "qa_status": "frozen"},
            {"question_id": "pilot", "module": "A5", "qa_status": "pilot"},
            {"question_id": "draft", "module": "A5", "qa_status": "draft"},
        ]
        self.assertEqual(
            [row["question_id"] for row in filter_items(items, modules=["A5"])],
            ["ready", "frozen"],
        )
        self.assertEqual(
            [row["question_id"] for row in filter_items(items, question_ids=["pilot"])],
            ["pilot"],
        )

    def test_math_boxed_answer_extraction_handles_nested_latex(self):
        solution = r"Work... Therefore $\boxed{\left(3, \frac{\pi}{2}\right)}$."
        self.assertEqual(
            extract_last_boxed_answer(solution),
            r"\left(3, \frac{\pi}{2}\right)",
        )

    def test_duplicate_retirement_keeps_one_representative(self):
        audit = {"modules": {"A1": {"clusters": [["A1-003", "A1-001", "A1-002"]]}}}
        self.assertEqual(
            build_retirement_map(audit),
            {"A1-002": "A1-001", "A1-003": "A1-001"},
        )


if __name__ == "__main__":
    unittest.main()
