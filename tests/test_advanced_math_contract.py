#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_engine import EvaluationRunService, filter_items  # noqa: E402
from sqlite_runtime import SQLiteStore  # noqa: E402


def make_math_item(question_id: str, tier: str) -> dict:
    return {
        "question_id": question_id,
        "version": "QB-v1.3",
        "module": "A1",
        "subtype": "graph_theory",
        "item_format": "single_turn",
        "difficulty": "hard",
        "difficulty_tier": tier,
        "drift_role": "capability",
        "prompt_template": "求图的顶点数。最后一行写答案。",
        "turn_script": None,
        "ground_truth": "7",
        "scoring_method": "numeric_em",
        "scoring_params": {},
        "module_quota_tag": "advanced_graph",
        "qa_status": "ready",
        "rotation_policy": {"replaceable": True, "rotation_priority": 1},
        "provenance": {"rewrite_ids": [], "source_candidate_ids": [], "transformation_summary": "test"},
        "notes": "test",
    }


class AdvancedMathContractTests(unittest.TestCase):
    def test_default_filter_excludes_frozen_reserve_items(self):
        items = [
            {"question_id": "A1-H001", "version": "QB-v1.3", "module": "A1", "qa_status": "ready"},
            {"question_id": "A1-R001", "version": "QB-v1.3", "module": "A1", "qa_status": "frozen"},
        ]
        self.assertEqual([item["question_id"] for item in filter_items(items)], ["A1-H001"])
        self.assertEqual(
            [item["question_id"] for item in filter_items(items, question_ids=["A1-R001"])],
            ["A1-R001"],
        )

    def test_schema_declares_backward_compatible_advanced_math_metadata(self):
        schema = json.loads((ROOT / "schema" / "final_bank_item.schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(
            properties["difficulty_tier"]["enum"],
            ["foundation", "advanced_hs", "olympiad", "undergraduate", "stretch", None],
        )
        self.assertEqual(properties["prerequisites"]["items"], {"type": "string"})
        self.assertTrue({"reasoning_profile", "discrimination_profile", "answer_contract"} <= set(properties))

    def test_difficulty_tier_is_persisted_filtered_and_faceted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = SQLiteStore(
                db_path=root / "evaluation.sqlite",
                runs_dir=root / "runs",
                bank_items_path=root / "bank.jsonl",
            )
            store.create_bank_item(make_math_item("A1-H001", "olympiad"))
            store.create_bank_item(make_math_item("A1-H002", "undergraduate"))
            result = store.list_bank_items(version="QB-v1.3", difficulty_tier="olympiad")
            self.assertEqual([item["question_id"] for item in result["items"]], ["A1-H001"])
            self.assertEqual(
                store.get_bank_facets(version="QB-v1.3", module="A1")["difficulty_tiers"],
                [{"value": "olympiad", "count": 1}, {"value": "undergraduate", "count": 1}],
            )

    def test_api_payload_normalization_preserves_advanced_math_metadata(self):
        payload = make_math_item("A1-H003", "stretch")
        payload.update(
            {
                "prerequisites": ["linear_algebra", "graph_spectrum"],
                "reasoning_profile": {"minimum_nontrivial_steps": 5},
                "discrimination_profile": {"item_family": "spectral_graph"},
                "answer_contract": {"format": "integer", "canonical_answer": "6"},
            }
        )
        normalized = EvaluationRunService._normalize_bank_payload(payload)
        self.assertEqual(normalized["difficulty_tier"], "stretch")
        self.assertEqual(normalized["prerequisites"], ["linear_algebra", "graph_spectrum"])
        self.assertEqual(normalized["answer_contract"]["format"], "integer")

    def test_item_detail_projection_exposes_advanced_math_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = SQLiteStore(
                db_path=root / "evaluation.sqlite",
                runs_dir=root / "runs",
                bank_items_path=root / "bank.jsonl",
            )
            item = make_math_item("A1-H004", "stretch")
            item.update(
                {
                    "prerequisites": ["finite_fields"],
                    "reasoning_profile": {"minimum_nontrivial_steps": 5},
                    "discrimination_profile": {"item_family": "finite_field_graph"},
                    "answer_contract": {"format": "integer", "canonical_answer": "7"},
                }
            )
            store.create_bank_item(item)
            service = object.__new__(EvaluationRunService)
            service.store = store
            service.bank_item_index = {}
            result = service.get_bank_item("A1-H004", "QB-v1.3")
            self.assertEqual(result["difficulty_tier"], "stretch")
            self.assertEqual(result["prerequisites"], ["finite_fields"])
            self.assertEqual(result["reasoning_profile"]["minimum_nontrivial_steps"], 5)
            self.assertEqual(result["answer_contract"]["canonical_answer"], "7")


if __name__ == "__main__":
    unittest.main()
