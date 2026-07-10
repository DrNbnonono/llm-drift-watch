#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict, deque

from question_bank_runtime import FINAL_BANK, NORMALIZED, REWRITE_DRAFTS, load_jsonl, write_jsonl


PILOT_VERSION = "QB-v1.3-pilot"
GPQA_PREFIX = "A5-GPQA-"


def balanced_gpqa_sample(candidates: list[dict], count: int) -> list[dict]:
    buckets: dict[str, deque[dict]] = defaultdict(deque)
    for row in sorted(candidates, key=lambda item: item["candidate_id"]):
        buckets[str(row.get("category") or "Other")].append(row)
    categories = sorted(buckets)
    picked = []
    while len(picked) < count and categories:
        next_categories = []
        for category in categories:
            if not buckets[category]:
                continue
            picked.append(buckets[category].popleft())
            if buckets[category]:
                next_categories.append(category)
            if len(picked) >= count:
                break
        categories = next_categories
    if len(picked) != count:
        raise ValueError(f"Requested {count} GPQA items but only selected {len(picked)}")
    return picked


def format_mcq_prompt(row: dict) -> str:
    option_lines = [f"{chr(ord('A') + idx)}. {option}" for idx, option in enumerate(row["options"])]
    return (
        f"{row['prompt']}\n\n"
        + "\n".join(option_lines)
        + "\n\n请分析后作答，最后一行严格输出 `答案：X`，其中 X 是选项字母。"
    )


def build_gpqa_pilot(count: int = 30) -> tuple[list[dict], list[dict]]:
    rows = balanced_gpqa_sample(load_jsonl(NORMALIZED / "gpqa_diamond_candidates.jsonl"), count)
    rewrites = []
    items = []
    for index, row in enumerate(rows, start=1):
        question_id = f"{GPQA_PREFIX}{index:03d}"
        rewrite_id = f"rw-{question_id.lower()}"
        prompt = format_mcq_prompt(row)
        scoring_params = {
            "options": row["options"],
            "answer_index": row["scoring_params"]["answer_index"],
            "public_calibration_track": True,
            "response_max_tokens": 1024,
        }
        rewrites.append(
            {
                "rewrite_id": rewrite_id,
                "source_candidate_ids": [row["candidate_id"]],
                "source_names": [row["source_name"]],
                "target_module": "A5",
                "target_subtype": "gpqa_diamond_public_calibration",
                "item_format": "single_turn",
                "rewrite_strategies": ["format_standardization", "deterministic_option_order"],
                "draft_prompt": prompt,
                "draft_turns": None,
                "draft_answer": row["answer"],
                "draft_options": row["options"],
                "scoring_method": "em",
                "scoring_params": scoring_params,
                "draft_status": "accepted",
                "direct_public_reuse": True,
                "contamination_risk": "high",
                "similarity_controls": {
                    "lexical_overlap_max": 1.0,
                    "preserve_answer_type_only": False,
                    "notes": "Public calibration track; excluded from routine longitudinal runs.",
                },
                "review_notes": "Pilot item for calibrating difficulty and scoring. Never mix into private drift estimates.",
            }
        )
        items.append(
            {
                "question_id": question_id,
                "version": PILOT_VERSION,
                "module": "A5",
                "subtype": "gpqa_diamond_public_calibration",
                "item_format": "single_turn",
                "difficulty": "hard",
                "drift_role": "capability",
                "prompt_template": prompt,
                "turn_script": None,
                "ground_truth": row["answer"],
                "scoring_method": "em",
                "scoring_params": scoring_params,
                "module_quota_tag": f"public_calibration/{row.get('category') or 'other'}",
                "qa_status": "pilot",
                "rotation_policy": {
                    "replaceable": True,
                    "rotation_priority": 3,
                    "expected_lifespan_days": None,
                },
                "provenance": {
                    "rewrite_ids": [rewrite_id],
                    "source_candidate_ids": [row["candidate_id"]],
                    "transformation_summary": "Direct GPQA Diamond reuse in the isolated public calibration track with deterministic option ordering.",
                },
                "notes": "PUBLIC_CALIBRATION_ONLY; contamination_risk=high; excluded from routine runs unless selected by question_id.",
            }
        )
    return rewrites, items


def replace_prefixed(rows: list[dict], replacements: list[dict], *, id_field: str, prefix: str) -> list[dict]:
    kept = [row for row in rows if not str(row.get(id_field) or "").startswith(prefix)]
    return kept + replacements


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated public benchmark pilot items.")
    parser.add_argument("--gpqa-count", type=int, default=30)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rewrites, items = build_gpqa_pilot(args.gpqa_count)
    if not args.write:
        print({"version": PILOT_VERSION, "gpqa_items": len(items)})
        return

    final_path = FINAL_BANK / "generated" / "final_bank_items.jsonl"
    rewrite_path = REWRITE_DRAFTS / "generated" / "rewrite_drafts.jsonl"
    merged_items = replace_prefixed(
        load_jsonl(final_path), items, id_field="question_id", prefix=GPQA_PREFIX
    )
    merged_rewrites = replace_prefixed(
        load_jsonl(rewrite_path),
        rewrites,
        id_field="rewrite_id",
        prefix=f"rw-{GPQA_PREFIX.lower()}",
    )
    write_jsonl(final_path, merged_items)
    write_jsonl(rewrite_path, merged_rewrites)
    write_jsonl(FINAL_BANK / "generated" / "final_bank_items_qbv1_3_pilot.jsonl", items)
    write_jsonl(REWRITE_DRAFTS / "generated" / "rewrite_drafts_qbv1_3_pilot.jsonl", rewrites)
    print({"final_items": len(merged_items), "pilot_items": len(items), "pilot_version": PILOT_VERSION})


if __name__ == "__main__":
    main()
