#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evaluation_api import app, service as api_service  # noqa: E402
from evaluation_engine import EvaluationRunService, make_run_id, score_item  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from provider_runtime import ProviderRegistry  # noqa: E402
from question_bank_runtime import write_jsonl  # noqa: E402


class EvaluationSystemTests(unittest.TestCase):
    def _ensure_mock_model(self):
        registry = ProviderRegistry()
        if "mock_echo" not in registry.models:
            registry.create_model(
                {
                    "model_alias": "mock_echo",
                    "provider_id": "mock_local",
                    "display_name": "Mock Echo",
                    "model_name": "mock-echo",
                    "default_timeout": 2,
                    "default_max_tokens": 128,
                    "supports_multi_turn": True,
                    "enabled": True,
                }
            )
        api_service.registry.reload()

    def test_provider_registry_lists_mock_and_minimax(self):
        registry = ProviderRegistry()
        providers = {row["provider_id"]: row for row in registry.list_providers()}
        self.assertIn("minimax_anthropic", providers)
        self.assertIn("mock_local", providers)
        self.assertTrue(providers["mock_local"]["configured"])

    def test_mock_run_completes(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        meta = service.get_run(run_id)
        self.assertEqual(meta["execution_status"], "completed")
        items = service.get_items(run_id)["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "ok")

    def test_canonical_summary_prefers_retry_success(self):
        service = EvaluationRunService()
        root_id = f"test-{make_run_id()}"
        child_id = f"test-{make_run_id()}"
        root_dir = ROOT / "manifests" / "evaluation_runs" / root_id
        child_dir = ROOT / "manifests" / "evaluation_runs" / child_id
        root_dir.mkdir(parents=True, exist_ok=True)
        child_dir.mkdir(parents=True, exist_ok=True)

        root_meta = {
            "run_id": root_id,
            "provider_id": "mock_local",
            "model_alias": "mock_echo",
            "model_name": "mock-echo",
            "base_url": "mock://local",
            "started_at": "2026-05-28T00:00:00Z",
            "finished_at": "2026-05-28T00:01:00Z",
            "bank_version": "QB-v1.0",
            "status": "completed",
            "execution_status": "completed",
            "run_kind": "base",
            "parent_run_id": None,
            "retry_policy": None,
            "config": {"modules": ["C2"], "timeout": 2, "concurrency_limit": 1},
            "progress": {"items_total": 1, "items_completed": 1, "items_failed": 0, "items_inflight": 0},
            "totals": {"items_total": 1, "items_completed": 0, "items_failed": 1},
            "summary_metrics": {},
            "report_path": None,
            "canonical_summary_path": None,
        }
        child_meta = {
            **root_meta,
            "run_id": child_id,
            "parent_run_id": root_id,
            "run_kind": "retry",
            "started_at": "2026-05-28T00:02:00Z",
            "finished_at": "2026-05-28T00:03:00Z",
            "totals": {"items_total": 1, "items_completed": 1, "items_failed": 0},
        }
        (root_dir / "evaluation_run.json").write_text(json.dumps(root_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (child_dir / "evaluation_run.json").write_text(json.dumps(child_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        write_jsonl(
            root_dir / "item_scores.jsonl",
            [
                {
                    "run_id": root_id,
                    "attempt_run_id": root_id,
                    "source_run_id": root_id,
                    "provider_id": "mock_local",
                    "model_alias": "mock_echo",
                    "question_id": "C2-001",
                    "module": "C2",
                    "item_format": "single_turn",
                    "score_method": "rule",
                    "primary_score": None,
                    "aux_score": None,
                    "status": "failed",
                    "response": None,
                    "score_details": {},
                    "error": "timeout",
                    "failure_type": "read_timeout",
                    "latency_ms": 100,
                    "is_retry_attempt": False,
                    "canonical_selected": False,
                }
            ],
        )
        write_jsonl(
            child_dir / "item_scores.jsonl",
            [
                {
                    "run_id": child_id,
                    "attempt_run_id": child_id,
                    "source_run_id": root_id,
                    "provider_id": "mock_local",
                    "model_alias": "mock_echo",
                    "question_id": "C2-001",
                    "module": "C2",
                    "item_format": "single_turn",
                    "score_method": "rule",
                    "primary_score": 1.0,
                    "aux_score": None,
                    "status": "ok",
                    "response": {"mode": "single_turn", "text": "42"},
                    "score_details": {"number_only": True},
                    "error": None,
                    "failure_type": None,
                    "latency_ms": 50,
                    "is_retry_attempt": True,
                    "canonical_selected": False,
                }
            ],
        )

        summary = service.get_canonical_summary(child_id)
        items = service.get_canonical_items(child_id)
        self.assertEqual(summary["module_scores"]["C2"], 1.0)
        self.assertEqual(items[0]["status"], "ok")

    def test_api_providers_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/providers")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("providers", payload)
        self.assertIn("models", payload)

    def test_api_accepts_module_filters_alias(self):
        self._ensure_mock_model()
        client = TestClient(app)
        response = client.post(
            "/api/runs",
            json={
                "provider_id": "mock_local",
                "model_alias": "mock_echo",
                "module_filters": ["C2"],
                "smoke": True,
                "max_items": 1,
                "concurrency_limit": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["config"]["modules"], ["C2"])

    def test_items_endpoint_includes_bank_item(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        client = TestClient(app)
        response = client.get(f"/api/runs/{run_id}/items")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("bank_item", payload["items"][0])
        self.assertEqual(payload["items"][0]["bank_item"]["question_id"], payload["items"][0]["question_id"])

    def test_consistency_bundle_scores_semantic_equivalence(self):
        item = {
            "question_id": "C4-test",
            "module": "C4",
            "scoring_method": "consistency_bundle",
            "ground_truth": "Canberra",
            "scoring_params": {"accepted_answers": ["Canberra", "堪培拉"]},
        }
        response_payload = {
            "turn_results": [
                {"text": "澳大利亚的首都是堪培拉（Canberra）。"},
                {"text": "行政首都是 Canberra。"},
                {"text": "联邦政府所在地是堪培拉。"},
            ]
        }
        score, details = score_item(item, response_payload)
        self.assertEqual(score, 1.0)
        self.assertEqual(details["consistency"], 1.0)
        self.assertEqual(details["accuracy"], 1.0)

    def test_items_endpoint_paginates(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        client = TestClient(app)
        response = client.get(f"/api/runs/{run_id}/items?limit=5&offset=0")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["limit"], 5)
        self.assertLessEqual(len(payload["items"]), 5)
        self.assertGreaterEqual(payload["total"], len(payload["items"]))

    def test_report_payload_generates_when_report_path_missing(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        payload = service.get_report_payload(run_id)
        self.assertEqual(payload["run_id"], run_id)
        self.assertIn("report_path", payload)
        self.assertTrue(payload["report_path"].endswith("report.md"))
        self.assertIn("content", payload)
        self.assertIn("dashboard", payload)
        self.assertIn("modules", payload["dashboard"])
        self.assertIn("scores", payload["dashboard"])

    def test_delete_run_removes_run_dir_and_records(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        run_dir = ROOT / "manifests" / "evaluation_runs" / run_id
        self.assertTrue(run_dir.exists())
        result = service.delete_run(run_id)
        self.assertIn(run_id, result["deleted_run_ids"])
        self.assertFalse(run_dir.exists())
        with self.assertRaises(FileNotFoundError):
            service.get_run(run_id)

    def test_bulk_delete_runs_endpoint(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run_ids = []
        for _ in range(2):
          run = service.create_run(
              provider_id="mock_local",
              model_alias="mock_echo",
              modules=["C2"],
              smoke=True,
              timeout=2,
              concurrency_limit=1,
          )
          run_ids.append(run["run_id"])
        deadline = time.time() + 10
        while time.time() < deadline:
            if all(service.get_run(run_id)["execution_status"] == "completed" for run_id in run_ids):
                break
            time.sleep(0.1)
        client = TestClient(app)
        response = client.post("/api/runs/bulk-delete", json={"run_ids": run_ids})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload["deleted_run_ids"]), set(run_ids))

    def test_registry_create_provider_and_model(self):
        registry = ProviderRegistry()
        provider_id = "test_openai_provider"
        model_alias = "test_openai_model"
        if provider_id in registry.providers:
            registry.delete_provider(provider_id)
        if model_alias in registry.models:
            registry.delete_model(model_alias)
        provider = registry.create_provider(
            {
                "provider_id": provider_id,
                "display_name": "Test OpenAI Provider",
                "protocol": "openai_compatible",
                "base_url": "https://example.com/v1",
                "auth_scheme": "bearer",
                "auth_env": "OPENAI_API_KEY",
                "headers_template": {},
                "model_lookup_mode": "list_contains",
                "enabled": True,
            }
        )
        model = registry.create_model(
            {
                "model_alias": model_alias,
                "provider_id": provider_id,
                "display_name": "Test Model",
                "model_name": "gpt-test",
                "default_timeout": 30,
                "default_max_tokens": 256,
                "supports_multi_turn": True,
                "enabled": True,
            }
        )
        self.assertEqual(provider["provider_id"], provider_id)
        self.assertEqual(model["model_alias"], model_alias)
        registry.delete_model(model_alias)
        registry.delete_provider(provider_id)

    def test_legacy_run_meta_and_item_are_normalized(self):
        service = EvaluationRunService()
        run_id = f"test-{make_run_id()}"
        run_dir = ROOT / "manifests" / "evaluation_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        legacy_meta = {
            "run_id": run_id,
            "started_at": "2026-05-28T00:00:00Z",
            "finished_at": "2026-05-28T00:01:00Z",
            "model_name": "MiniMax-M2.7",
            "base_url": "https://api.minimaxi.com/anthropic/v1",
            "bank_version": "QB-v1.0",
            "status": "completed",
            "config": {"modules": ["A1"], "timeout": 45},
            "totals": {"items_total": 1, "items_completed": 1, "items_failed": 0},
            "summary_metrics": {"module_scores": {"A1": 1.0}},
        }
        (run_dir / "evaluation_run.json").write_text(json.dumps(legacy_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        write_jsonl(
            run_dir / "item_scores.jsonl",
            [
                {
                    "run_id": run_id,
                    "question_id": "A1-001",
                    "module": "A1",
                    "item_format": "single_turn",
                    "score_method": "numeric_em",
                    "primary_score": 1.0,
                    "aux_score": None,
                    "status": "ok",
                    "response": {"mode": "single_turn", "text": "答案：36"},
                    "score_details": {"predicted": "36", "gold": "36"},
                    "error": None,
                }
            ],
        )
        meta = service.get_run(run_id)
        items = service.get_items(run_id, include_bank=True)["items"]
        self.assertEqual(meta["provider_id"], "minimax_anthropic")
        self.assertEqual(meta["model_alias"], "minimax_m2_7")
        self.assertEqual(items[0]["provider_id"], "minimax_anthropic")
        self.assertIn("bank_item", items[0])

    def test_timeline_endpoint_returns_steps(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        run_id = run["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            meta = service.get_run(run_id)
            if meta["execution_status"] == "completed":
                break
            time.sleep(0.1)
        client = TestClient(app)
        response = client.get(f"/api/runs/{run_id}/timeline/C2-001")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question_id"], "C2-001")
        self.assertTrue(len(payload["timeline"]) >= 1)

    def test_bank_items_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/bank/items?module=A1&limit=5")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertLessEqual(len(payload["items"]), 5)
        self.assertGreaterEqual(payload["total"], len(payload["items"]))

    def test_bank_facets_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/bank/facets")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("modules", payload)
        self.assertIn("subtypes", payload)
        self.assertIn("item_formats", payload)
        self.assertGreater(payload["total"], 0)

    def test_system_paths_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/system/paths")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("providers_config_path", payload)
        self.assertIn("bank_items_path", payload)
        self.assertIn("evaluation_runs_root", payload)

    def test_run_meta_includes_artifact_paths(self):
        self._ensure_mock_model()
        service = EvaluationRunService()
        run = service.create_run(
            provider_id="mock_local",
            model_alias="mock_echo",
            modules=["C2"],
            smoke=True,
            timeout=2,
            concurrency_limit=1,
        )
        meta = service.get_run(run["run_id"])
        self.assertIn("run_dir", meta)
        self.assertIn("item_scores_path", meta)
        self.assertIn("summary_path", meta)
        self.assertIn("canonical_ready", meta)

    def test_run_count_semantics_are_normalized(self):
        service = EvaluationRunService()
        run_id = f"test-{make_run_id()}"
        run_dir = ROOT / "manifests" / "evaluation_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        legacy_meta = {
            "run_id": run_id,
            "started_at": "2026-05-30T00:00:00Z",
            "finished_at": "2026-05-30T00:01:00Z",
            "model_name": "MiniMax-M2.7",
            "base_url": "https://api.minimaxi.com/anthropic/v1",
            "bank_version": "QB-v1.0",
            "status": "completed",
            "config": {"modules": ["C2"], "timeout": 45},
            "totals": {"items_total": 2, "items_completed": 1, "items_failed": 1},
            "summary_metrics": {"module_scores": {"C2": 1.0}},
        }
        (run_dir / "evaluation_run.json").write_text(json.dumps(legacy_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        meta = service.get_run(run_id)
        self.assertEqual(meta["progress"]["items_processed"], 2)
        self.assertEqual(meta["progress"]["items_completed"], 2)
        self.assertEqual(meta["progress"]["items_succeeded"], 1)
        self.assertEqual(meta["progress"]["items_failed"], 1)
        self.assertEqual(meta["totals"]["items_processed"], 2)
        self.assertEqual(meta["totals"]["items_completed"], 2)
        self.assertEqual(meta["totals"]["items_succeeded"], 1)
        self.assertEqual(meta["totals"]["items_failed"], 1)


if __name__ == "__main__":
    unittest.main()
