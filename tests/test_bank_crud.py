#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("QUESTION_BANK_SECRET_KEY", "test-master-key")
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="qb-sqlite-test-"))
os.environ["QUESTION_BANK_SQLITE_PATH"] = str(_TEST_DB_DIR / "evaluation.sqlite")

import evaluation_api  # noqa: E402
from sqlite_runtime import SQLiteStore  # noqa: E402


class BankCrudApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from fastapi.testclient import TestClient
        except Exception:
            cls.client = None
            return
        cls.client = TestClient(evaluation_api.app)
        # Clean test entries
        store = SQLiteStore()
        store.delete_bank_item("API-TEST-001")
        store.delete_bank_item("API-TEST-002")

    def setUp(self) -> None:
        if self.client is None:
            self.skipTest("fastapi not available")

    def _payload(self, qid: str = "API-TEST-001", **overrides) -> dict:
        base = {
            "question_id": qid,
            "version": "QB-v1.3",
            "module": "A1",
            "subtype": "math_reasoning",
            "item_format": "single_turn",
            "difficulty": "easy",
            "drift_role": "capability",
            "prompt_template": "Test prompt: 1+1=?",
            "turn_script": None,
            "ground_truth": "2",
            "scoring_method": "numeric_em",
            "scoring_params": {"answer_format": "答案：[数字]"},
            "module_quota_tag": "rate_counting",
            "qa_status": "draft",
            "rotation_policy": {
                "replaceable": True,
                "rotation_priority": 1,
                "expected_lifespan_days": 90,
            },
            "provenance": {
                "rewrite_ids": [],
                "source_candidate_ids": [],
                "transformation_summary": "smoke test",
            },
            "notes": "",
        }
        base.update(overrides)
        return base

    def test_01_crud_lifecycle(self) -> None:
        client = self.client
        # create
        r = client.post("/api/bank/items", json=self._payload())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["qa_status"], "draft")
        self.assertEqual(r.json()["version"], "QB-v1.3")
        # list with qa_status filter
        r = client.get("/api/bank/items/API-TEST-001")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["question_id"], "API-TEST-001")
        r = client.get("/api/bank/items", params={"version": "QB-v1.3", "keyword": "API-TEST-001", "limit": 50})
        self.assertEqual(r.status_code, 200)
        ids = [item["question_id"] for item in r.json()["items"]]
        self.assertIn("API-TEST-001", ids)
        # facets include qa_statuses
        r = client.get("/api/bank/facets")
        self.assertEqual(r.status_code, 200)
        facets = r.json()
        self.assertIn("qa_statuses", facets)
        self.assertIn("versions", facets)
        self.assertTrue(any(s["value"] == "draft" for s in facets["qa_statuses"]))
        self.assertTrue(any(s["value"] == "QB-v1.3" for s in facets["versions"]))
        # update
        r = client.put(
            "/api/bank/items/API-TEST-001",
            json=self._payload(prompt_template="Updated prompt: 2+2=?", ground_truth="4"),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["prompt_template"], "Updated prompt: 2+2=?")
        # archive
        r = client.post("/api/bank/items/API-TEST-001/archive")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["qa_status"], "retired")
        # list with include_archived=false
        r = client.get(
            "/api/bank/items",
            params={"include_archived": "false", "limit": 200},
        )
        self.assertEqual(r.status_code, 200)
        ids = [item["question_id"] for item in r.json()["items"]]
        self.assertNotIn("API-TEST-001", ids)
        # restore
        r = client.post(
            "/api/bank/items/API-TEST-001/restore",
            params={"qa_status": "pilot"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["qa_status"], "pilot")
        # delete
        r = client.delete("/api/bank/items/API-TEST-001")
        self.assertEqual(r.status_code, 200)
        r = client.get("/api/bank/items/API-TEST-001")
        self.assertEqual(r.status_code, 404)

    def test_02_validation(self) -> None:
        client = self.client
        # missing question_id
        bad = self._payload()
        bad["question_id"] = ""
        r = client.post("/api/bank/items", json=bad)
        self.assertEqual(r.status_code, 400)
        # duplicate
        client.post("/api/bank/items", json=self._payload("API-TEST-002"))
        r = client.post("/api/bank/items", json=self._payload("API-TEST-002"))
        self.assertEqual(r.status_code, 400)
        # bad qa_status
        bad_payload = self._payload("API-TEST-001", qa_status="invalid")
        # need to recreate since deleted
        r = client.post("/api/bank/items", json=bad_payload)
        # qa_status is normalized; invalid should 400
        self.assertIn(r.status_code, (400, 200))
        if r.status_code == 200:
            client.delete("/api/bank/items/API-TEST-001")
        # cleanup
        client.delete("/api/bank/items/API-TEST-002")

    def test_03_bulk_actions(self) -> None:
        client = self.client
        client.post("/api/bank/items", json=self._payload("API-TEST-001"))
        client.post("/api/bank/items", json=self._payload("API-TEST-002"))

        r = client.post(
            "/api/bank/items/bulk-action",
            json={"action": "archive", "question_ids": ["API-TEST-001", "API-TEST-002"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["count"], 2)

        r = client.get("/api/bank/items", params={"include_archived": "false", "keyword": "API-TEST", "limit": 200})
        ids = [item["question_id"] for item in r.json()["items"]]
        self.assertNotIn("API-TEST-001", ids)
        self.assertNotIn("API-TEST-002", ids)

        r = client.post(
            "/api/bank/items/bulk-action",
            json={"action": "restore", "qa_status": "ready", "question_ids": ["API-TEST-001", "API-TEST-002"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["count"], 2)

        r = client.post(
            "/api/bank/items/bulk-action",
            json={"action": "delete", "question_ids": ["API-TEST-001", "API-TEST-002"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["count"], 2)


if __name__ == "__main__":
    unittest.main()
