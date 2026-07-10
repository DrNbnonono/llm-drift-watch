from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_engine import filter_items  # noqa: E402
from sqlite_runtime import SQLiteStore  # noqa: E402


def bank_item(version: str, prompt: str, *, question_id: str = "A1-001") -> dict:
    return {
        "question_id": question_id,
        "version": version,
        "module": "A1",
        "subtype": "arithmetic",
        "item_format": "single_turn",
        "prompt_template": prompt,
        "turn_script": None,
        "ground_truth": "2",
        "scoring_method": "exact_match",
        "scoring_params": {},
        "qa_status": "ready",
        "rotation_policy": {"replaceable": True, "rotation_priority": 1},
        "provenance": {
            "rewrite_ids": [],
            "source_candidate_ids": [],
            "transformation_summary": "test",
        },
    }


class VersionedBankStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        generated = self.root / "final_bank_specs" / "generated"
        generated.mkdir(parents=True)
        self.live_path = generated / "final_bank_items.jsonl"
        snapshots = {
            "final_bank_items_qbv1_0.jsonl": [bank_item("QB-v1.0", "old prompt")],
            "final_bank_items_qbv1_1.jsonl": [bank_item("QB-v1.1", "v1.1 prompt")],
            "final_bank_items_qbv1_2.jsonl": [bank_item("QB-v1.2", "v1.2 prompt")],
            "final_bank_items_qbv1_3.jsonl": [bank_item("QB-v1.3", "snapshot prompt")],
            "final_bank_items_qbv1_3_pilot.jsonl": [
                bank_item("QB-v1.3-pilot", "pilot prompt", question_id="GPQA-001")
            ],
            "final_bank_items.jsonl": [bank_item("QB-v1.3", "live prompt")],
        }
        for name, rows in snapshots.items():
            (generated / name).write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
        config = self.root / "providers.json"
        config.write_text('{"providers": [], "models": []}', encoding="utf-8")
        self.store = SQLiteStore(
            db_path=self.root / "evaluation.sqlite",
            legacy_config_path=config,
            runs_dir=self.root / "runs",
            bank_items_path=self.live_path,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_bootstrap_keeps_same_question_id_in_every_version(self) -> None:
        rows = self.store.get_all_bank_items()
        matching = [row for row in rows if row["question_id"] == "A1-001"]
        self.assertEqual(
            {row["version"] for row in matching},
            {"QB-v1.0", "QB-v1.1", "QB-v1.2", "QB-v1.3"},
        )
        self.assertEqual(
            self.store.get_bank_item("A1-001", version="QB-v1.3")["prompt_template"],
            "live prompt",
        )

    def test_bank_versions_describe_runnable_and_editable_snapshots(self) -> None:
        versions = {row["version"]: row for row in self.store.list_bank_versions()}
        self.assertEqual(versions["QB-v1.0"]["item_count"], 1)
        self.assertTrue(versions["QB-v1.0"]["is_runnable"])
        self.assertFalse(versions["QB-v1.0"]["is_editable"])
        self.assertTrue(versions["QB-v1.3"]["is_editable"])
        self.assertTrue(versions["QB-v1.3-pilot"]["is_editable"])

    def test_legacy_lookup_defaults_to_current_version_and_old_versions_are_read_only(self) -> None:
        self.assertEqual(self.store.get_bank_item("A1-001")["version"], "QB-v1.3")
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.store.update_bank_item(
                "A1-001", bank_item("QB-v1.0", "changed"), version="QB-v1.0"
            )

    def test_facets_are_scoped_to_selected_version_and_module(self) -> None:
        self.store.create_bank_item(
            bank_item("QB-v1.3", "second subtype", question_id="A1-002")
            | {"subtype": "geometry"}
        )
        self.store.create_bank_item(
            bank_item("QB-v1.3", "other module", question_id="A2-001")
            | {"module": "A2", "subtype": "coding"}
        )

        facets = self.store.get_bank_facets(version="QB-v1.3", module="A1")

        self.assertEqual(facets["total"], 2)
        self.assertEqual(
            {(row["value"], row["count"]) for row in facets["subtypes"]},
            {("arithmetic", 1), ("geometry", 1)},
        )
        self.assertEqual(
            facets["modules"],
            [{"value": "A1", "count": 2}, {"value": "A2", "count": 1}],
        )

    def test_run_item_round_trips_immutable_bank_snapshot(self) -> None:
        snapshot = self.store.get_bank_item("A1-001", version="QB-v1.3")
        row = {
            "run_id": "run-1",
            "question_id": "A1-001",
            "module": "A1",
            "item_format": "single_turn",
            "score_method": "exact_match",
            "primary_score": 1.0,
            "status": "ok",
            "response": {"text": "2"},
            "bank_version": "QB-v1.3",
            "bank_item_snapshot": snapshot,
            "bank_item_content_hash": "sha256:test",
            "snapshot_origin": "captured",
        }
        self.store.upsert_run({
            "run_id": "run-1",
            "bank_version": "QB-v1.3",
            "status": "completed",
            "execution_status": "completed",
        })
        self.store.upsert_run_item(row)
        actual = self.store.list_run_items("run-1")[0]
        self.assertEqual(actual["bank_version"], "QB-v1.3")
        self.assertEqual(actual["bank_item_snapshot"]["prompt_template"], "live prompt")
        self.assertEqual(actual["bank_item_content_hash"], "sha256:test")
        self.assertEqual(actual["snapshot_origin"], "captured")


class VersionFilterTests(unittest.TestCase):
    def test_filter_items_selects_version_before_other_filters(self) -> None:
        items = [
            bank_item("QB-v1.2", "old", question_id="A1-001"),
            bank_item("QB-v1.3", "current", question_id="A1-001"),
            bank_item("QB-v1.3", "other module", question_id="A2-001") | {"module": "A2"},
        ]
        actual = filter_items(
            items,
            bank_version="QB-v1.3",
            modules=["A1"],
            question_ids=["A1-001"],
        )
        self.assertEqual([(row["version"], row["question_id"]) for row in actual], [("QB-v1.3", "A1-001")])


if __name__ == "__main__":
    unittest.main()
