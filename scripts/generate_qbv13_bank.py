#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from copy import deepcopy

from generate_formal_bank import MODULE_TARGETS, generate_bank
from build_qbv13_safety_expansion import AUDIT_PATH, build_safety_expansion
from advanced_math_bank import (
    audit_advanced_math_bank,
    build_advanced_math_bank,
    build_advanced_math_candidates,
    build_advanced_math_rewrites,
)
from qbv13_replacement_builders import BUILDERS, VERSION
from question_bank_runtime import FINAL_BANK, MANIFESTS, NORMALIZED, REWRITE_DRAFTS, load_jsonl, write_jsonl


RETIREMENT_MANIFEST = MANIFESTS / "qbv1_2_near_duplicate_retirements.json"
ADVANCED_MATH_AUDIT_PATH = MANIFESTS / "qbv13_advanced_math_audit.json"


def build_qbv13() -> tuple[list[dict], list[dict], dict]:
    base_rewrites, base_items = generate_bank()
    rewrite_by_question_id = {
        rewrite["rewrite_id"].removeprefix("rw-").upper(): rewrite for rewrite in base_rewrites
    }
    item_by_id = {item["question_id"]: deepcopy(item) for item in base_items}
    retirement = json.loads(RETIREMENT_MANIFEST.read_text(encoding="utf-8"))
    retired_by_module: dict[str, list[str]] = defaultdict(list)
    for decision in retirement["decisions"]:
        retired_by_module[decision["module"]].append(decision["question_id"])

    replacement_rewrites = {}
    replacement_items = {}
    for module, question_ids in sorted(retired_by_module.items()):
        originals = [item_by_id[question_id] for question_id in sorted(question_ids)]
        rewrites, items = BUILDERS[module](originals)
        replacement_rewrites.update({item["question_id"]: rewrite for rewrite, item in zip(rewrites, items)})
        replacement_items.update({item["question_id"]: item for item in items})

    final_items = []
    final_rewrites = []
    for base_item in base_items:
        question_id = base_item["question_id"]
        if question_id in replacement_items:
            final_items.append(replacement_items[question_id])
            final_rewrites.append(replacement_rewrites[question_id])
            continue
        item = deepcopy(base_item)
        item["version"] = VERSION
        item["qa_status"] = "ready"
        notes = str(item.get("notes") or "").strip()
        carry_note = "quality_track=private_longitudinal; qbv13_action=carried_forward_after_duplicate_audit"
        item["notes"] = f"{notes}; {carry_note}".strip("; ")
        transformation = item.get("provenance", {}).get("transformation_summary", "")
        item["provenance"]["transformation_summary"] = (
            f"{transformation} Carried into QB-v1.3 after near-duplicate review."
        ).strip()
        final_items.append(item)
        rewrite_id = item["provenance"]["rewrite_ids"][0]
        rewrite = next(row for row in base_rewrites if row["rewrite_id"] == rewrite_id)
        final_rewrites.append(rewrite)

    base_module_counts = Counter(item["module"] for item in final_items)
    if len(final_items) != sum(MODULE_TARGETS.values()):
        raise ValueError(f"QB-v1.3 item count mismatch: {len(final_items)}")
    if base_module_counts != Counter(MODULE_TARGETS):
        raise ValueError(f"QB-v1.3 base module counts mismatch: {base_module_counts}")

    expansion_items, expansion_rewrites, expansion_audit = build_safety_expansion(final_items)
    final_items.extend(expansion_items)
    final_rewrites.extend(expansion_rewrites)
    advanced_math_formal, advanced_math_reserve = build_advanced_math_bank()
    advanced_math_items = [*advanced_math_formal, *advanced_math_reserve]
    advanced_math_rewrites = build_advanced_math_rewrites(advanced_math_items)
    advanced_math_audit = audit_advanced_math_bank(advanced_math_items)
    final_items.extend(advanced_math_items)
    final_rewrites.extend(advanced_math_rewrites)
    expected_targets = dict(MODULE_TARGETS)
    expected_targets["A1"] += len(advanced_math_items)
    expected_targets.update({f"B{i}": 100 for i in range(1, 9)})
    module_counts = Counter(item["module"] for item in final_items)
    if module_counts != Counter(expected_targets):
        raise ValueError(f"QB-v1.3 expanded module counts mismatch: {module_counts}")
    if len({item["question_id"] for item in final_items}) != len(final_items):
        raise ValueError("QB-v1.3 contains duplicate question IDs")

    summary = {
        "version": VERSION,
        "main_item_count": len(final_items),
        "rewrite_count": len(final_rewrites),
        "replacement_count": len(replacement_items),
        "carried_forward_count": sum(MODULE_TARGETS.values()) - len(replacement_items),
        "safety_expansion_count": len(expansion_items),
        "safety_source_counts": expansion_audit["source_counts"],
        "safety_language_counts": expansion_audit["language_counts"],
        "safety_audit_path": str(AUDIT_PATH),
        "advanced_math_formal_count": len(advanced_math_formal),
        "advanced_math_reserve_count": len(advanced_math_reserve),
        "advanced_math_audit_path": str(ADVANCED_MATH_AUDIT_PATH),
        "default_run_item_count": sum(item.get("qa_status") == "ready" for item in final_items),
        "module_counts": dict(module_counts),
        "single_turn_count": sum(item["item_format"] == "single_turn" for item in final_items),
        "multi_turn_group_count": sum(item["item_format"] == "multi_turn_group" for item in final_items),
        "qa_status_counts": dict(Counter(item["qa_status"] for item in final_items)),
        "scoring_method_counts": dict(Counter(item["scoring_method"] for item in final_items)),
        "_safety_audit": expansion_audit,
        "_advanced_math_audit": advanced_math_audit,
        "_advanced_math_candidates": build_advanced_math_candidates(advanced_math_items),
    }
    return final_rewrites, final_items, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the production-ready QB-v1.3 bank.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rewrites, items, summary = build_qbv13()
    safety_audit = summary.pop("_safety_audit")
    advanced_math_audit = summary.pop("_advanced_math_audit")
    advanced_math_candidates = summary.pop("_advanced_math_candidates")
    if not args.write:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    final_generated = FINAL_BANK / "generated"
    rewrite_generated = REWRITE_DRAFTS / "generated"
    main_snapshot = final_generated / "final_bank_items_qbv1_3.jsonl"
    rewrite_snapshot = rewrite_generated / "rewrite_drafts_qbv1_3.jsonl"
    write_jsonl(main_snapshot, items)
    write_jsonl(rewrite_snapshot, rewrites)
    AUDIT_PATH.write_text(json.dumps(safety_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ADVANCED_MATH_AUDIT_PATH.write_text(json.dumps(advanced_math_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(NORMALIZED / "qbv13_advanced_math_candidates.jsonl", advanced_math_candidates)

    pilot_items_path = final_generated / "final_bank_items_qbv1_3_pilot.jsonl"
    pilot_rewrites_path = rewrite_generated / "rewrite_drafts_qbv1_3_pilot.jsonl"
    pilot_items = load_jsonl(pilot_items_path) if pilot_items_path.exists() else []
    pilot_rewrites = load_jsonl(pilot_rewrites_path) if pilot_rewrites_path.exists() else []

    current_path = final_generated / "final_bank_items.jsonl"
    current_items = load_jsonl(current_path) if current_path.exists() else []
    main_ids = {item["question_id"] for item in items}
    pilot_ids = {item["question_id"] for item in pilot_items}
    preserved_local_drafts = [
        {**item, "version": "QB-v1.3"} for item in current_items
        if item["question_id"] not in main_ids and item["question_id"] not in pilot_ids
    ]
    write_jsonl(current_path, [*items, *pilot_items, *preserved_local_drafts])
    write_jsonl(rewrite_generated / "rewrite_drafts.jsonl", [*rewrites, *pilot_rewrites])

    summary["public_pilot_count"] = len(pilot_items)
    summary["preserved_local_draft_count"] = len(preserved_local_drafts)
    summary["live_row_count"] = len(items) + len(pilot_items) + len(preserved_local_drafts)
    summary_path = MANIFESTS / "final_bank_summary_qbv1_3.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (MANIFESTS / "final_bank_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
