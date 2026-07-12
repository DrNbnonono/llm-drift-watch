from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_engine import EvaluationRunService, aggregate_scores  # noqa: E402
from sqlite_runtime import SQLiteStore  # noqa: E402


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        config = root / "providers.json"
        config.write_text('{"providers": [], "models": []}', encoding="utf-8")
        self.store = SQLiteStore(
            db_path=root / "evaluation.sqlite",
            legacy_config_path=config,
            runs_dir=root / "runs",
            bank_items_path=root / "final_bank_items.jsonl",
        )
        self.store.upsert_run({"run_id": "run-1", "status": "completed", "bank_version": "QB-v1.3"})
        self.row = {
            "run_id": "run-1", "attempt_run_id": "run-1", "source_run_id": "run-1",
            "provider_id": "answer", "model_alias": "answer-model", "question_id": "B1-001",
            "module": "B1", "item_format": "single_turn", "score_method": "strongreject_score",
            "primary_score": 0.2, "status": "ok", "response": {"text": "answer"}, "score_details": {},
            "bank_version": "QB-v1.3", "bank_item_snapshot": {
                "question_id": "B1-001", "module": "B1", "item_format": "single_turn",
                "scoring_method": "strongreject_score", "review_policy": {"mode": "judge", "confidence_threshold": 0.7},
            },
        }
        self.store.upsert_run_item(self.row)
        self.service = object.__new__(EvaluationRunService)
        self.service.store = self.store

    def tearDown(self):
        self.temp.cleanup()

    def test_manual_review_overrides_judge_without_overwriting_rule_score(self):
        self.store.add_judge_assessment({
            "run_id": "run-1", "question_id": "B1-001", "attempt_run_id": "run-1",
            "status": "ok", "score": 0.6, "verdict": "partial", "criteria": [], "confidence": 0.9,
        })
        judged = self.service._attach_review_scores(self.row)
        self.assertEqual(judged["effective_score"], 0.6)
        self.assertEqual(judged["score_source"], "judge")
        self.assertEqual(judged["review_status"], "pending")  # 0.4 disagreement

        self.store.add_manual_review({
            "run_id": "run-1", "question_id": "B1-001", "attempt_run_id": "run-1",
            "reviewer": "Alice", "score": 0.8, "verdict": "pass", "confirmed": True,
        })
        reviewed = self.service._attach_review_scores(self.row)
        self.assertEqual(reviewed["rule_score"], 0.2)
        self.assertEqual(reviewed["judge_score"], 0.6)
        self.assertEqual(reviewed["manual_score"], 0.8)
        self.assertEqual(reviewed["effective_score"], 0.8)
        self.assertEqual(reviewed["score_source"], "manual")
        self.assertEqual(reviewed["review_status"], "reviewed")

    def test_manual_review_requires_note_and_uses_exact_verdict_thresholds(self):
        with self.assertRaisesRegex(ValueError, "note is required"):
            self.service.submit_manual_review("run-1", "B1-001", {"reviewer": "Alice", "score": 1, "note": ""})
        partial = self.service.submit_manual_review(
            "run-1", "B1-001", {"reviewer": "Alice", "score": 0.8, "note": "部分满足评分约束"}
        )
        self.assertEqual(partial["review"]["verdict"], "partial")
        passed = self.service.submit_manual_review(
            "run-1", "B1-001", {"reviewer": "Alice", "score": 1, "note": "答案完全正确"}
        )
        self.assertEqual(passed["review"]["verdict"], "pass")

    def test_pending_review_is_excluded_from_aggregate(self):
        summary = aggregate_scores([
            {"module": "B1", "status": "ok", "primary_score": 0.0, "effective_score": 0.0, "review_status": "pending"},
            {"module": "B1", "status": "ok", "primary_score": 1.0, "effective_score": 1.0, "review_status": "complete"},
        ])
        self.assertEqual(summary["module_scores"]["B1"], 1.0)

    def test_review_thread_messages_are_append_only(self):
        thread = self.store.create_review_thread({"run_id": "run-1", "question_id": "B1-001", "attempt_run_id": "run-1", "title": "Follow-up"})
        self.store.add_review_message(thread["thread_id"], "user", "Why?")
        self.store.add_review_message(thread["thread_id"], "assistant", "Because.")
        loaded = self.store.get_review_thread(thread["thread_id"])
        self.assertEqual([row["role"] for row in loaded["messages"]], ["user", "assistant"])
        self.assertEqual(self.store.list_run_items("run-1")[0]["response"]["text"], "answer")

    def test_judge_has_enough_output_budget_for_complete_json(self):
        class JudgeProvider:
            model = SimpleNamespace(model_alias="judge-model")

            def __init__(self):
                self.max_tokens = None

            def complete_messages(self, messages, max_tokens):
                self.max_tokens = max_tokens
                return {"content": [{"type": "text", "text": '{"score":0.8,"verdict":"pass","criteria":[],"rationale":"ok","confidence":0.9}'}]}

            @staticmethod
            def extract_text(raw):
                return raw["content"][0]["text"]

            @staticmethod
            def sanitize_response(raw):
                return {"text": raw["content"][0]["text"]}

        judge = JudgeProvider()
        self.service.registry = SimpleNamespace(resolve_connection=lambda connection_id: judge)

        result = self.service.judge_run_item("run-1", "B1-001", attempt_run_id="run-1", judge_connection_id="judge-connection")

        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(judge.max_tokens, 1400)

    def test_retry_inherits_judge_connection(self):
        self.service.get_run = lambda run_id: {
            "provider_id": "answer", "model_alias": "answer-model", "connection_id": "answer-connection",
            "bank_version": "QB-v1.3", "config": {"modules": None, "timeout": 60, "limit_per_module": 1, "judge_connection_id": "judge-connection"},
        }
        self.service.get_items = lambda run_id, status=None: {"items": [{"question_id": "B1-001"}]}
        self.service.create_run = Mock(return_value={"run_id": "retry-1"})

        self.service.retry_failed_items("run-1", concurrency_limit=2)

        self.assertEqual(self.service.create_run.call_args.kwargs["judge_connection_id"], "judge-connection")


if __name__ == "__main__":
    unittest.main()
