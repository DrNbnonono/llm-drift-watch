#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from question_bank_runtime import FINAL_BANK, NORMALIZED, REWRITE_DRAFTS, load_jsonl


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"


def validate_required(path: Path, required: list[str]) -> tuple[int, list[str]]:
    missing = []
    rows = load_jsonl(path)
    for idx, row in enumerate(rows, start=1):
        for field in required:
            if field not in row:
                missing.append(f"{path.name}:{idx}:{field}")
    return len(rows), missing


def main() -> None:
    summaries = []
    candidate_required = [
        "candidate_id",
        "source_name",
        "source_dataset",
        "source_url",
        "original_id",
        "module_candidates",
        "task_family",
        "scoring_method",
        "direct_reuse_allowed",
        "rewrite_guidance",
    ]
    rewrite_required = [
        "rewrite_id",
        "source_candidate_ids",
        "target_module",
        "target_subtype",
        "rewrite_strategies",
        "draft_status",
        "scoring_method",
        "direct_public_reuse",
        "contamination_risk",
    ]
    final_required = [
        "question_id",
        "version",
        "module",
        "subtype",
        "item_format",
        "scoring_method",
        "qa_status",
        "rotation_policy",
        "provenance",
    ]
    failures = []
    for path in sorted(NORMALIZED.glob("*.jsonl")):
        rows, missing = validate_required(path, candidate_required)
        summaries.append({"path": str(path), "rows": rows, "missing": len(missing)})
        failures.extend(missing)
    for path in sorted((REWRITE_DRAFTS / "generated").glob("*.jsonl")):
        rows, missing = validate_required(path, rewrite_required)
        summaries.append({"path": str(path), "rows": rows, "missing": len(missing)})
        failures.extend(missing)
    for path in sorted((FINAL_BANK / "generated").glob("*.jsonl")):
        rows, missing = validate_required(path, final_required)
        summaries.append({"path": str(path), "rows": rows, "missing": len(missing)})
        failures.extend(missing)
    print(json.dumps({"ok": not failures, "files": summaries, "failures": failures[:50]}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
