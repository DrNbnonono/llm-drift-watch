from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_engine import calculate_estimated_cost, summarize_item_billing, classify_grid_state, combine_billing_summaries  # noqa: E402
from provider_runtime import normalize_billing_usage  # noqa: E402
from sqlite_runtime import SQLiteStore  # noqa: E402
from evaluation_engine import EvaluationRunService  # noqa: E402
from types import SimpleNamespace
from unittest.mock import Mock


class BillingTests(unittest.TestCase):
    def test_grid_state_uses_effective_score_and_pending_state(self):
        self.assertEqual(classify_grid_state(None), "unprocessed")
        self.assertEqual(classify_grid_state({"status": "failed"}), "failed")
        self.assertEqual(classify_grid_state({"status": "ok", "effective_score": None}), "pending_score")
        self.assertEqual(classify_grid_state({"status": "ok", "effective_score": 1}), "correct")
        self.assertEqual(classify_grid_state({"status": "ok", "effective_score": 0.8}), "incorrect")
    def test_anthropic_usage_is_normalized_without_double_counting(self):
        usage = normalize_billing_usage("anthropic_compatible", {
            "input_tokens": 100,
            "cache_read_input_tokens": 40,
            "cache_creation_input_tokens": 10,
            "output_tokens": 50,
        })
        self.assertEqual(usage, {
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "cache_creation_tokens": 10,
            "output_tokens": 50,
            "reasoning_tokens": 0,
            "usage_complete": True,
        })

    def test_openai_cached_and_reasoning_tokens_are_subsets(self):
        usage = normalize_billing_usage("openai_compatible", {
            "prompt_tokens": 100,
            "completion_tokens": 60,
            "prompt_tokens_details": {"cached_tokens": 25},
            "completion_tokens_details": {"reasoning_tokens": 20},
        })
        self.assertEqual(usage["input_tokens"], 75)
        self.assertEqual(usage["cached_input_tokens"], 25)
        self.assertEqual(usage["output_tokens"], 60)
        self.assertEqual(usage["reasoning_tokens"], 20)

    def test_cost_uses_price_snapshot_and_subtracts_reasoning_from_output(self):
        cost = calculate_estimated_cost(
            {"input_tokens": 100, "cached_input_tokens": 20, "cache_creation_tokens": 0,
             "output_tokens": 50, "reasoning_tokens": 10, "usage_complete": True},
            {"currency": "USD", "input_per_million": 2, "cached_input_per_million": 1,
             "cache_creation_per_million": 3, "output_per_million": 4, "reasoning_per_million": 6},
        )
        self.assertEqual(cost["currency"], "USD")
        self.assertAlmostEqual(cost["amount"], (100 * 2 + 20 * 1 + 40 * 4 + 10 * 6) / 1_000_000)
        self.assertTrue(cost["complete"])

    def test_missing_price_is_unknown_not_zero(self):
        cost = calculate_estimated_cost({"input_tokens": 10, "usage_complete": True}, {})
        self.assertIsNone(cost["amount"])
        self.assertFalse(cost["complete"])

    def test_multiturn_item_usage_is_aggregated(self):
        summary = summarize_item_billing({
            "turn_results": [
                {"billing_usage": {"input_tokens": 10, "output_tokens": 5, "usage_complete": True}},
                {"billing_usage": {"input_tokens": 20, "output_tokens": 8, "usage_complete": True}},
            ]
        }, {"currency": "USD", "input_per_million": 1, "output_per_million": 2})
        self.assertEqual(summary["token_usage"]["input_tokens"], 30)
        self.assertEqual(summary["token_usage"]["output_tokens"], 13)

    def test_answer_and_judge_billing_are_combined(self):
        combined = combine_billing_summaries([
            {"token_usage": {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100, "usage_complete": True}, "estimated_cost": {"amount": 0.1, "known_amount": 0.1, "currency": "USD", "complete": True}},
            {"token_usage": {"input_tokens": 15, "output_tokens": 5, "total_tokens": 20, "usage_complete": True}, "estimated_cost": {"amount": 0.02, "known_amount": 0.02, "currency": "USD", "complete": True}},
        ])
        self.assertEqual(combined["token_usage"]["total_tokens"], 120)
        self.assertAlmostEqual(combined["estimated_cost"]["amount"], 0.12)


class BatchStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        config = root / "providers.json"
        config.write_text('{"providers": [], "models": []}', encoding="utf-8")
        self.store = SQLiteStore(root / "evaluation.sqlite", config, root / "runs", root / "bank.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_batch_and_child_runs_round_trip(self):
        self.store.create_evaluation_batch({
            "batch_id": "batch-1", "status": "running", "bank_version": "QB-v1.3",
            "config": {"modules": ["A1"]}, "created_at": "2026-07-12T00:00:00Z",
        })
        self.store.upsert_run({"run_id": "run-a", "status": "running", "bank_version": "QB-v1.3"})
        self.store.upsert_run({"run_id": "run-b", "status": "running", "bank_version": "QB-v1.3"})
        self.store.add_batch_run("batch-1", "run-a", "conn-a", 0)
        self.store.add_batch_run("batch-1", "run-b", "conn-b", 1)
        loaded = self.store.get_evaluation_batch("batch-1")
        self.assertEqual([row["run_id"] for row in loaded["runs"]], ["run-a", "run-b"])
        self.assertEqual(self.store.list_evaluation_batches()[0]["batch_id"], "batch-1")
        self.assertEqual(self.store.list_batches_for_run("run-a")[0]["batch_id"], "batch-1")

    def test_service_creates_one_deferred_child_run_per_connection(self):
        service = object.__new__(EvaluationRunService)
        service.store = self.store
        service.registry = SimpleNamespace(model_connections={
            "conn-a": {"connection_id": "conn-a"}, "conn-b": {"connection_id": "conn-b"},
        })
        run_ids = iter(["run-a", "run-b"])
        def create_run(**kwargs):
            run_id = next(run_ids)
            self.store.upsert_run({"run_id": run_id, "status": "queued", "bank_version": "QB-v1.3"})
            return {"run_id": run_id}
        service.create_run = Mock(side_effect=create_run)
        service._start_batch_scheduler = Mock()
        batch = service.create_evaluation_batch(
            model_connection_ids=["conn-a", "conn-b"], bank_version="QB-v1.3",
            modules=["A1"], smoke=True, timeout=30, max_items=2, limit_per_module=1,
            concurrency_limit=2, max_active_models=1, judge_connection_id=None,
        )
        self.assertEqual([row["run_id"] for row in batch["runs"]], ["run-a", "run-b"])
        self.assertTrue(service.create_run.call_args_list[0].kwargs["defer_start"])
        service._start_batch_scheduler.assert_called_once_with(batch["batch_id"])


if __name__ == "__main__":
    unittest.main()
