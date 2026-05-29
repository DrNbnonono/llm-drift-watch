#!/usr/bin/env python3

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NORMALIZED = ROOT / "normalized"
RAW = ROOT / "raw_sources"


def curl_json(url: str) -> dict:
    result = subprocess.run(
        ["curl", "-L", "-s", "--max-time", "60", url],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_truthfulqa() -> tuple[str, int]:
    src = RAW / "truthfulqa" / "TruthfulQA.csv"
    rows = []
    with src.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            rows.append(
                {
                    "candidate_id": f"truthfulqa-{idx}",
                    "source_name": "TruthfulQA",
                    "source_dataset": "truthfulqa/truthful_qa",
                    "source_split": "generation",
                    "source_url": "https://github.com/sylinrl/TruthfulQA",
                    "original_id": str(idx),
                    "module_candidates": ["B4"],
                    "task_family": "truthfulness_qa",
                    "category": row.get("Category"),
                    "prompt": row.get("Question"),
                    "turns": None,
                    "options": None,
                    "answer": row.get("Best Answer"),
                    "scoring_method": "judge_or_reference_match",
                    "scoring_params": {
                        "best_incorrect_answer": row.get("Best Incorrect Answer"),
                        "correct_answers": row.get("Correct Answers"),
                        "incorrect_answers": row.get("Incorrect Answers"),
                        "type": row.get("Type"),
                    },
                    "anti_contamination_source": row.get("Source"),
                    "source_metadata": {
                        "type": row.get("Type"),
                        "source": row.get("Source"),
                        "best_incorrect_answer": row.get("Best Incorrect Answer"),
                    },
                    "direct_reuse_allowed": False,
                    "rewrite_guidance": "Keep the misconception or false-premise pattern, but rewrite the surface question and supporting reference style into the project's B4 template.",
                    "notes": "Best used to derive trap-premise and factual reliability items, not as a direct hidden test set.",
                }
            )
    out = NORMALIZED / "truthfulqa_candidates.jsonl"
    write_jsonl(out, rows)
    return str(out), len(rows)


def build_jbb_harmful() -> tuple[str, int]:
    payload = curl_json(
        "https://datasets-server.huggingface.co/rows?dataset=JailbreakBench%2FJBB-Behaviors&config=behaviors&split=harmful&offset=0&length=100"
    )
    rows = []
    for wrapper in payload["rows"]:
        row = wrapper["row"]
        original_id = str(row["Index"])
        rows.append(
            {
                "candidate_id": f"jbb-harmful-{original_id}",
                "source_name": "JailbreakBench",
                "source_dataset": "JailbreakBench/JBB-Behaviors",
                "source_split": "harmful",
                "source_url": "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors",
                "original_id": original_id,
                "module_candidates": ["B1", "B2"],
                "task_family": "harmful_behavior_goal",
                "category": row.get("Category"),
                "prompt": row.get("Goal"),
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "wildguard_or_strongreject",
                "scoring_params": {
                    "behavior": row.get("Behavior"),
                    "target_prefix": row.get("Target"),
                },
                "anti_contamination_source": row.get("Source"),
                "source_metadata": {
                    "behavior": row.get("Behavior"),
                    "target_prefix": row.get("Target"),
                    "source": row.get("Source"),
                },
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Use the harmful behavior intent and category only; rewrite direct requests and jailbreak wrappers into the project's own B1 and B2 templates.",
                "notes": "Full harmful behavior base set for B1 and B2 candidate generation.",
            }
        )
    out = NORMALIZED / "jbb_harmful_candidates.jsonl"
    write_jsonl(out, rows)
    return str(out), len(rows)


def build_or_bench_seed() -> tuple[str, int]:
    payload = curl_json(
        "https://datasets-server.huggingface.co/rows?dataset=bench-llm%2For-bench&config=or-bench-hard-1k&split=train&offset=0&length=100"
    )
    rows = []
    for idx, wrapper in enumerate(payload["rows"]):
        row = wrapper["row"]
        rows.append(
            {
                "candidate_id": f"or-bench-hard-{idx}",
                "source_name": "OR-Bench",
                "source_dataset": "bench-llm/or-bench",
                "source_split": "or-bench-hard-1k/train",
                "source_url": "https://huggingface.co/datasets/bench-llm/or-bench",
                "original_id": str(idx),
                "module_candidates": ["B3"],
                "task_family": "over_refusal_benign_boundary",
                "category": row.get("category"),
                "prompt": row.get("prompt"),
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "refusal_detection",
                "scoring_params": {},
                "anti_contamination_source": "OR-Bench hard set",
                "source_metadata": {
                    "seed_subset": True,
                    "num_rows_total": payload.get("num_rows_total"),
                },
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Keep the benign-but-sensitive boundary pattern, but rewrite scenario, actors, and wording into the project's B3 scenario families.",
                "notes": "Seed subset only in this environment; intended for B3 over-refusal design.",
            }
        )
    out = NORMALIZED / "or_bench_hard_candidates.jsonl"
    write_jsonl(out, rows)
    return str(out), len(rows)


def build_livecodebench_seed() -> tuple[str, int]:
    payload = curl_json(
        "https://datasets-server.huggingface.co/rows?dataset=livecodebench%2Ftest_generation&config=default&split=test&offset=0&length=100"
    )
    rows = []
    for wrapper in payload["rows"]:
        row = wrapper["row"]
        original_id = f"{row.get('question_id')}-{row.get('test_id')}"
        rows.append(
            {
                "candidate_id": f"lcb-testgen-{original_id}",
                "source_name": "LiveCodeBench",
                "source_dataset": "livecodebench/test_generation",
                "source_split": "test",
                "source_url": "https://huggingface.co/datasets/livecodebench/test_generation",
                "original_id": original_id,
                "module_candidates": ["A2"],
                "task_family": "code_test_generation",
                "category": row.get("difficulty"),
                "prompt": row.get("question_content"),
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "exec_or_exact_match",
                "scoring_params": {
                    "question_title": row.get("question_title"),
                    "question_id": row.get("question_id"),
                    "contest_id": row.get("contest_id"),
                    "function_name": row.get("function_name"),
                    "starter_code": row.get("starter_code"),
                    "test": row.get("test"),
                },
                "anti_contamination_source": str(row.get("contest_date")),
                "source_metadata": {
                    "question_title": row.get("question_title"),
                    "contest_id": row.get("contest_id"),
                    "contest_date": row.get("contest_date"),
                    "test_id": row.get("test_id"),
                    "seed_subset": True,
                    "num_rows_total": payload.get("num_rows_total"),
                },
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Use the problem type and dynamic contest freshness signal, but rewrite into the project's A2 task templates with private hidden tests.",
                "notes": "Seed subset from LiveCodeBench test_generation for A2 code-oriented candidate work.",
            }
        )
    out = NORMALIZED / "livecodebench_test_generation_candidates.jsonl"
    write_jsonl(out, rows)
    return str(out), len(rows)


def main() -> None:
    summary = {}
    builders = {
        "truthfulqa": build_truthfulqa,
        "jbb_harmful": build_jbb_harmful,
        "or_bench_seed": build_or_bench_seed,
        "livecodebench_seed": build_livecodebench_seed,
    }
    for key, builder in builders.items():
        path, count = builder()
        summary[key] = {"path": path, "count": count}
        print(f"[ok] {key}: {count} -> {path}")
    summary_path = NORMALIZED / "curated_build_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] summary -> {summary_path}")


if __name__ == "__main__":
    main()
