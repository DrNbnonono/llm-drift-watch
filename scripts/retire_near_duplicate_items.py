#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from question_bank_runtime import FINAL_BANK, MANIFESTS, load_jsonl, write_jsonl


DEFAULT_AUDIT = MANIFESTS / "qbv1_2_near_duplicate_audit.json"
DEFAULT_BANK = FINAL_BANK / "generated" / "final_bank_items.jsonl"


def build_retirement_map(audit: dict) -> dict[str, str]:
    retirement_map = {}
    for module_report in audit.get("modules", {}).values():
        for cluster in module_report.get("clusters", []):
            if len(cluster) < 2:
                continue
            retained = sorted(cluster)[0]
            for question_id in sorted(cluster)[1:]:
                retirement_map.setdefault(question_id, retained)
    return retirement_map


def retire_items(items: list[dict], retirement_map: dict[str, str]) -> tuple[list[dict], list[dict]]:
    decisions = []
    updated = []
    for item in items:
        question_id = str(item.get("question_id"))
        retained_peer = retirement_map.get(question_id)
        if not retained_peer or item.get("version") != "QB-v1.2":
            updated.append(item)
            continue
        new_item = dict(item)
        previous_status = new_item.get("qa_status", "ready")
        new_item["qa_status"] = "retired"
        notes = str(new_item.get("notes") or "").strip()
        marker = (
            "quality_retired=near_duplicate_cluster; "
            f"retained_peer={retained_peer}; audit=qbv1_2_near_duplicate_audit"
        )
        if marker not in notes:
            new_item["notes"] = f"{notes}; {marker}".strip("; ")
        rotation = dict(new_item.get("rotation_policy") or {})
        rotation["rotation_priority"] = max(3, int(rotation.get("rotation_priority") or 0))
        new_item["rotation_policy"] = rotation
        decisions.append(
            {
                "question_id": question_id,
                "module": new_item.get("module"),
                "previous_status": previous_status,
                "new_status": "retired",
                "retained_peer": retained_peer,
            }
        )
        updated.append(new_item)
    return updated, decisions


def main() -> None:
    parser = argparse.ArgumentParser(description="Retire duplicate-cluster members while retaining one representative.")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    retirement_map = build_retirement_map(audit)
    updated, decisions = retire_items(load_jsonl(args.bank), retirement_map)
    summary = {
        "audit": str(args.audit),
        "bank": str(args.bank),
        "retired_count": len(decisions),
        "retired_by_module": dict(Counter(row["module"] for row in decisions)),
        "decisions": decisions,
    }
    if args.write:
        write_jsonl(args.bank, updated)
        decision_path = MANIFESTS / "qbv1_2_near_duplicate_retirements.json"
        decision_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(decision_path)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
