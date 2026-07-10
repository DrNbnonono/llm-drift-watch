#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:  # pragma: no cover - optional dependency for fuller local extraction
    load_dataset = None

try:
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - optional dependency for direct parquet extraction
    pq = None


ROOT = Path(__file__).resolve().parent.parent
ROWS_API = "https://datasets-server.huggingface.co/rows"
CNN_DAILYMAIL_DIR = ROOT / "raw_sources" / "cnn-dailymail"
HOTPOTQA_DIR = ROOT / "raw_sources" / "hotpotqa"


def fetch_json(url: str, retries: int = 5, sleep_s: float = 2.0):
    last_error = None
    for attempt in range(retries):
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-L",
                    "-s",
                    "--fail",
                    "--max-time",
                    "180",
                    "-H",
                    "User-Agent: question-bank-workspace/0.2",
                    url,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries - 1:
                time.sleep(sleep_s * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def download_file(url: str, target: Path, max_time_s: int = 1800) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return
    partial_path = target.with_name(target.name + ".part")
    subprocess.run(
        [
            "curl",
            "-L",
            "-s",
            "--fail",
            "--show-error",
            "--continue-at",
            "-",
            "--max-time",
            str(max_time_s),
            "-o",
            str(partial_path),
            url,
        ],
        check=True,
    )
    partial_path.replace(target)


def iter_hf_rows(dataset: str, config: str, split: str, page_size: int = 100, row_limit: int | None = None):
    offset = 0
    total_seen = 0
    try:
        while True:
            length = page_size
            if row_limit is not None:
                remaining = row_limit - total_seen
                if remaining <= 0:
                    break
                length = min(length, remaining)
            params = {
                "dataset": dataset,
                "config": config,
                "split": split,
                "offset": offset,
                "length": length,
            }
            url = f"{ROWS_API}?{urllib.parse.urlencode(params)}"
            payload = fetch_json(url)
            rows = payload.get("rows", [])
            if not rows:
                break
            for wrapper in rows:
                row = dict(wrapper["row"])
                row["_hf_row_idx"] = wrapper.get("row_idx", offset + total_seen)
                yield row
                total_seen += 1
            offset += len(rows)
            if len(rows) < length:
                break
        return
    except Exception:
        if load_dataset is None:
            raise

    ds = load_dataset(dataset, config, split=split)
    for idx, row in enumerate(ds):
        if row_limit is not None and idx >= row_limit:
            break
        item = dict(row)
        item["_hf_row_idx"] = idx
        yield item


def iter_parquet_rows(url: str, cache_path: Path, row_limit: int | None = None):
    if pq is None:
        raise RuntimeError("pyarrow is required for parquet-backed extraction")
    download_file(url, cache_path, max_time_s=600)
    parquet_file = pq.ParquetFile(cache_path)
    seen = 0
    for batch in parquet_file.iter_batches(batch_size=512):
        rows = batch.to_pylist()
        for row in rows:
            if row_limit is not None and seen >= row_limit:
                return
            row["_hf_row_idx"] = seen
            yield row
            seen += 1


def iter_csv_rows(path: Path, row_limit: int | None = None):
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if row_limit is not None and idx >= row_limit:
                break
            item = dict(row)
            item["_csv_row_idx"] = idx
            yield item


def iter_jsonl_rows(path: Path, row_limit: int | None = None):
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if row_limit is not None and idx >= row_limit:
                break
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            item["_jsonl_row_idx"] = idx
            yield item


def extract_final_numeric_answer(answer_text: str | None) -> str | None:
    if not answer_text:
        return None
    match = re.search(r"####\s*([^\n]+)", answer_text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(-?\d[\d,]*(?:\.\d+)?)\s*$", answer_text.strip())
    if match:
        return match.group(1).replace(",", "")
    return None


def extract_last_boxed_answer(solution: str | None) -> str | None:
    if not solution:
        return None
    marker_index = solution.rfind("\\boxed{")
    if marker_index < 0:
        return None
    start = marker_index + len("\\boxed{")
    depth = 1
    for index in range(start, len(solution)):
        char = solution[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return solution[start:index].strip()
    return None


def has_derived_prompt(record: dict) -> bool:
    prompt = record.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return True
    turns = record.get("turns")
    if isinstance(turns, list):
        return any(isinstance(turn, str) and turn.strip() for turn in turns)
    return False


def json_fallback(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def normalize_ifeval(row: dict) -> dict:
    original_id = str(row["key"])
    return {
        "candidate_id": f"ifeval-{original_id}",
        "source_name": "IFEval",
        "source_dataset": "google/IFEval",
        "source_split": "train",
        "source_url": "https://huggingface.co/datasets/google/IFEval",
        "original_id": original_id,
        "module_candidates": ["A3", "C2", "C3"],
        "task_family": "instruction_following",
        "category": "verifiable_constraints",
        "prompt": row.get("prompt"),
        "turns": None,
        "options": None,
        "answer": None,
        "scoring_method": "rule",
        "scoring_params": {
            "instruction_id_list": row.get("instruction_id_list", []),
            "kwargs": row.get("kwargs", []),
        },
        "anti_contamination_source": "Public benchmark reference; must be rewritten before entering final bank.",
        "source_metadata": {
            "instruction_id_list": row.get("instruction_id_list", []),
            "kwargs": row.get("kwargs", []),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Keep the constraint pattern, but rewrite the task surface form, entities, and formatting demands into the project's private prompt style.",
        "notes": "Best suited for A3 strict/partial scoring and C2/C3 drift probes.",
    }


def normalize_mmlu_pro(row: dict) -> dict:
    original_id = str(row["question_id"])
    return {
        "candidate_id": f"mmlu-pro-{original_id}",
        "source_name": "MMLU-Pro",
        "source_dataset": "TIGER-Lab/MMLU-Pro",
        "source_split": "test",
        "source_url": "https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro",
        "original_id": original_id,
        "module_candidates": ["A5"],
        "task_family": "knowledge_mcq",
        "category": row.get("category"),
        "prompt": row.get("question"),
        "turns": None,
        "options": row.get("options"),
        "answer": row.get("answer"),
        "scoring_method": "em",
        "scoring_params": {
            "answer_index": row.get("answer_index"),
            "option_count": len(row.get("options", [])),
        },
        "anti_contamination_source": row.get("src"),
        "source_metadata": {
            "src": row.get("src"),
            "answer_index": row.get("answer_index"),
            "cot_content_present": bool(row.get("cot_content")),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Retain the knowledge point and difficulty band, but rebuild options, distractors, and prompt framing; prefer 6-8 options and add project-specific reasoning format requirements.",
        "notes": "Use as a topic and difficulty pool, not as a direct evaluation set.",
    }


def normalize_jbb_harmful(row: dict) -> dict:
    original_id = str(row["Index"])
    return {
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
        "rewrite_guidance": "Use the harmful behavior intent and category only; rewrite direct requests and attack wrappers into the project's own B1/B2 template system.",
        "notes": "Good base for fixed harmful behavior set and for mapping to attack templates.",
    }


def normalize_livebench_instruction(row: dict) -> dict:
    original_id = str(row["question_id"])
    turns = row.get("turns") or []
    return {
        "candidate_id": f"livebench-inst-{original_id}",
        "source_name": "LiveBench-Instruction",
        "source_dataset": "livebench/instruction_following",
        "source_split": "test",
        "source_url": "https://huggingface.co/datasets/livebench/instruction_following",
        "original_id": original_id,
        "module_candidates": ["A3", "C2"],
        "task_family": "dynamic_instruction_following",
        "category": row.get("category"),
        "prompt": turns[0] if turns else None,
        "turns": turns,
        "options": None,
        "answer": None,
        "scoring_method": "rule",
        "scoring_params": {
            "task": row.get("task"),
            "instruction_id_list": row.get("instruction_id_list", []),
            "kwargs": row.get("kwargs", []),
        },
        "anti_contamination_source": row.get("citation") or row.get("release_date"),
        "source_metadata": {
            "task": row.get("task"),
            "task_prompt": row.get("task_prompt"),
            "instruction_id_list": row.get("instruction_id_list", []),
            "kwargs": row.get("kwargs", []),
            "release_date": row.get("release_date"),
            "livebench_release_date": row.get("livebench_release_date"),
            "citation": row.get("citation"),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Retain the constraint composition and freshness signal, but replace the source passage and exact surface form; use the release metadata to prioritize recent material in quarterly rotation.",
        "notes": "Useful for private reformulations of dynamic instruction-following probes.",
    }


def normalize_gsm8k(row: dict) -> dict:
    row_idx = int(row.get("_hf_row_idx", 0))
    original_id = f"train-{row_idx:05d}"
    answer_text = row.get("answer")
    final_answer = extract_final_numeric_answer(answer_text)
    return {
        "candidate_id": f"gsm8k-{original_id}",
        "source_name": "GSM8K",
        "source_dataset": "openai/gsm8k",
        "source_split": "main/train",
        "source_url": "https://huggingface.co/datasets/openai/gsm8k",
        "original_id": original_id,
        "module_candidates": ["A1"],
        "task_family": "math_reasoning",
        "category": "grade_school_math_word_problem",
        "prompt": row.get("question"),
        "turns": None,
        "options": None,
        "answer": final_answer,
        "scoring_method": "numeric_em",
        "scoring_params": {
            "reference_solution": answer_text,
        },
        "anti_contamination_source": "Public benchmark reference; retain only problem archetypes for rewritten private math items.",
        "source_metadata": {
            "hf_row_idx": row_idx,
            "reference_solution": answer_text,
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Keep the arithmetic/combinatorial structure, but rewrite the scenario, values, distractor details, and output format into the project's private A1 template.",
        "notes": "Broad open math reasoning pool for A1; harder filtering is still needed before using items as C1-style boundary probes.",
    }


def stable_mcq(question: str, correct: str, incorrect: list[str]) -> tuple[list[str], str]:
    """Return a reproducibly shuffled option list and its answer letter."""
    options = [correct, *incorrect]
    seed = int(hashlib.sha256(question.encode("utf-8")).hexdigest()[:16], 16)
    random.Random(seed).shuffle(options)
    answer_index = options.index(correct)
    if answer_index >= 10:
        raise ValueError("Multiple-choice normalizer supports at most 10 options")
    return options, chr(ord("A") + answer_index)


def normalize_gpqa_diamond(row: dict) -> dict:
    question = str(row.get("Question") or "").strip()
    correct = str(row.get("Correct Answer") or "").strip()
    incorrect = [
        str(row.get(f"Incorrect Answer {idx}") or "").strip()
        for idx in range(1, 4)
    ]
    options, answer = stable_mcq(question, correct, incorrect)
    original_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": f"gpqa-diamond-{original_id}",
        "source_name": "GPQA Diamond",
        "source_dataset": "openai/simple-evals:gpqa_diamond",
        "source_split": "diamond",
        "source_url": "https://github.com/idavidrein/gpqa",
        "original_id": original_id,
        "module_candidates": ["A5"],
        "task_family": "graduate_science_mcq",
        "category": row.get("High-level domain") or row.get("Subdomain"),
        "prompt": question,
        "turns": None,
        "options": options,
        "answer": answer,
        "scoring_method": "em",
        "scoring_params": {
            "answer_index": options.index(correct),
            "option_count": len(options),
        },
        "anti_contamination_source": "Public benchmark; use only in the public calibration track.",
        "source_metadata": {
            "subdomain": row.get("Subdomain"),
            "writer_accuracy": row.get("Writer's Difficulty Estimate"),
            "non_expert_accuracy": row.get("Non-Expert Validator Accuracy"),
            "expert_accuracy": row.get("Expert Validator Accuracy"),
        },
        "direct_reuse_allowed": True,
        "rewrite_guidance": "Direct reuse is limited to the explicitly labelled public calibration track; private monitoring items must use a different knowledge point and fresh distractors.",
        "notes": "Official GPQA Diamond item distributed through OpenAI simple-evals; deterministic option order is fixed by question hash.",
    }


def normalize_simpleqa(row: dict) -> dict:
    question = str(row.get("problem") or row.get("question") or "").strip()
    answer = str(row.get("answer") or row.get("target") or "").strip()
    original_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": f"simpleqa-{original_id}",
        "source_name": "SimpleQA",
        "source_dataset": "openai/simple-evals:simple_qa_test_set",
        "source_split": "test",
        "source_url": "https://github.com/openai/simple-evals",
        "original_id": original_id,
        "module_candidates": ["A5", "B4"],
        "task_family": "short_form_factuality",
        "category": row.get("topic") or "factuality",
        "prompt": question,
        "turns": None,
        "options": None,
        "answer": answer,
        "scoring_method": "reference_match",
        "scoring_params": {"accepted_answers": [answer]},
        "anti_contamination_source": "Public benchmark; use only in the public calibration track.",
        "source_metadata": {"metadata": row.get("metadata")},
        "direct_reuse_allowed": True,
        "rewrite_guidance": "Keep direct items in the public calibration track. For the private track, replace the fact, evidence source and answer aliases.",
        "notes": "SimpleQA requires semantic grading in its official protocol; exact/reference matching is only suitable after manual alias review.",
    }


def normalize_math500(row: dict) -> dict:
    question = str(row.get("Question") or row.get("problem") or "").strip()
    reference_solution = str(row.get("Answer") or row.get("answer") or "").strip()
    answer = extract_last_boxed_answer(reference_solution)
    original_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": f"math500-{original_id}",
        "source_name": "MATH-500",
        "source_dataset": "openai/simple-evals:math_500_test",
        "source_split": "test",
        "source_url": "https://github.com/hendrycks/math",
        "original_id": original_id,
        "module_candidates": ["A1", "C1"],
        "task_family": "competition_math",
        "category": row.get("Subject") or row.get("type") or "competition_math",
        "prompt": question,
        "turns": None,
        "options": None,
        "answer": answer,
        "scoring_method": "math_equivalence",
        "scoring_params": {
            "reference_answer": answer,
            "reference_solution": reference_solution,
        },
        "anti_contamination_source": "Public benchmark; use only in the public calibration track.",
        "source_metadata": {
            "level": row.get("Level") or row.get("level"),
            "reference_solution": reference_solution,
        },
        "direct_reuse_allowed": True,
        "rewrite_guidance": "Use direct items only for public calibration. Private probes must change the mathematical construction, not merely the constants.",
        "notes": "Symbolic equivalence support is required before promotion from candidate to runnable pilot.",
    }


def normalize_supergpqa(row: dict) -> dict:
    question = str(row.get("question") or "").strip()
    correct = str(row.get("answer") or "").strip()
    raw_options = [str(option).strip() for option in (row.get("options") or [])]
    answer_letter = str(row.get("answer_letter") or "").strip().upper()
    if answer_letter and answer_letter.isalpha():
        answer = answer_letter
        options = raw_options
    else:
        incorrect = [option for option in raw_options if option != correct]
        options, answer = stable_mcq(question, correct, incorrect)
    original_id = str(row.get("uuid") or hashlib.sha256(question.encode("utf-8")).hexdigest()[:16])
    return {
        "candidate_id": f"supergpqa-{original_id}",
        "source_name": "SuperGPQA",
        "source_dataset": "m-a-p/SuperGPQA",
        "source_split": "train",
        "source_url": "https://huggingface.co/datasets/m-a-p/SuperGPQA",
        "original_id": original_id,
        "module_candidates": ["A5"],
        "task_family": "graduate_multidiscipline_mcq",
        "category": row.get("discipline"),
        "prompt": question,
        "turns": None,
        "options": options,
        "answer": answer,
        "scoring_method": "em",
        "scoring_params": {"option_count": len(options)},
        "anti_contamination_source": "Public composite benchmark; preserve original-source attribution and license constraints.",
        "source_metadata": {
            "discipline": row.get("discipline"),
            "field": row.get("field"),
            "subfield": row.get("subfield"),
            "difficulty": row.get("difficulty"),
            "is_calculation": row.get("is_calculation"),
        },
        "direct_reuse_allowed": True,
        "rewrite_guidance": "Direct reuse is restricted to public calibration; private monitoring items must change the tested knowledge and distractor set.",
        "notes": "ODC-BY composite dataset; downstream users must also respect licenses of referenced source datasets.",
    }


def normalize_sorrybench(row: dict) -> dict:
    question_id = str(row["question_id"])
    prompt_style = row.get("prompt_style") or "base"
    original_id = f"{question_id}-{prompt_style}"
    turns = [turn for turn in (row.get("turns") or []) if isinstance(turn, str) and turn.strip()]
    return {
        "candidate_id": f"sorrybench-{original_id}",
        "source_name": "SORRY-Bench",
        "source_dataset": "AIM-Harvard/sorrybench",
        "source_split": "train",
        "source_url": "https://huggingface.co/datasets/AIM-Harvard/sorrybench",
        "original_id": original_id,
        "module_candidates": ["B1"],
        "task_family": "harmful_request_refusal",
        "category": row.get("category"),
        "prompt": turns[0] if turns else None,
        "turns": turns,
        "options": None,
        "answer": None,
        "scoring_method": "wildguard_refusal",
        "scoring_params": {
            "prompt_style": prompt_style,
            "base_question_id": question_id,
        },
        "anti_contamination_source": "Mirror of the public SORRY-Bench release because the official 202406 dataset is gated.",
        "source_metadata": {
            "question_id": row.get("question_id"),
            "prompt_style": prompt_style,
            "turn_count": len(turns),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Use the harmful topic taxonomy and mutation style only; rewrite direct asks into the project's own B1 wording templates and balanced topic buckets.",
        "notes": "The base prompts support B1 topic balancing; non-base prompt styles can later inform B2-style mutation templates, but this candidate file is registered for B1.",
    }


def normalize_squad(row: dict) -> dict:
    answers = row.get("answers") or {}
    answer_texts = answers.get("text") or []
    answer_starts = answers.get("answer_start") or []
    prompt = f"Context:\n{row.get('context', '')}\n\nQuestion: {row.get('question', '')}"
    return {
        "candidate_id": f"squad-{row['id']}",
        "source_name": "SQuAD",
        "source_dataset": "rajpurkar/squad",
        "source_split": "validation",
        "source_url": "https://huggingface.co/datasets/rajpurkar/squad",
        "original_id": str(row["id"]),
        "module_candidates": ["A4"],
        "task_family": "reading_comprehension_span_qa",
        "category": row.get("title"),
        "prompt": prompt,
        "turns": None,
        "options": None,
        "answer": answer_texts[0] if answer_texts else None,
        "scoring_method": "span_em_f1",
        "scoring_params": {
            "all_answers": answer_texts,
            "answer_starts": answer_starts,
        },
        "anti_contamination_source": row.get("title"),
        "source_metadata": {
            "title": row.get("title"),
            "question": row.get("question"),
            "context": row.get("context"),
            "answer_count": len(answer_texts),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Retain the passage-question relation, but replace the article text, entities, and answer span surface form using private source passages for A4 reading comprehension items.",
        "notes": "Open reading-comprehension pool for A4 span-answer tasks.",
    }


def ensure_hotpotqa_asset() -> Path:
    path = HOTPOTQA_DIR / "hotpot_dev_distractor_v1.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                json.load(f)
            return path
        except json.JSONDecodeError:
            path.unlink()
    download_file(
        "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
        path,
        max_time_s=1800,
    )
    return path


def iter_hotpotqa_validation_rows(row_limit: int | None = None):
    if load_dataset is not None:
        ds = load_dataset("hotpotqa/hotpot_qa", "distractor", split="validation")
        for idx, row in enumerate(ds):
            if row_limit is not None and idx >= row_limit:
                break
            yield dict(row)
        return
    path = ensure_hotpotqa_asset()
    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    for idx, row in enumerate(rows):
        if row_limit is not None and idx >= row_limit:
            break
        yield row


def format_hotpot_context(context: dict | list | None) -> str:
    if not context:
        return ""
    blocks = []
    if isinstance(context, dict):
        titles = context.get("title") or []
        sentences = context.get("sentences") or []
        for title, sentence_list in zip(titles, sentences):
            joined = " ".join(sentence_list or [])
            blocks.append(f"[{title}]\n{joined}")
    else:
        for item in context:
            if not isinstance(item, list) or len(item) != 2:
                continue
            title, sentence_list = item
            joined = " ".join(sentence_list or [])
            blocks.append(f"[{title}]\n{joined}")
    return "\n\n".join(blocks)


def normalize_hotpotqa(row: dict) -> dict:
    prompt = f"Context:\n{format_hotpot_context(row.get('context'))}\n\nQuestion: {row.get('question', '')}"
    supporting_facts = row.get("supporting_facts") or {}
    original_id = str(row.get("_id") or row.get("id"))
    if isinstance(supporting_facts, list) and supporting_facts and all(
        isinstance(item, list) and len(item) == 2 for item in supporting_facts
    ):
        supporting_titles = [item[0] for item in supporting_facts]
        supporting_sent_ids = [item[1] for item in supporting_facts]
    elif isinstance(supporting_facts, list) and len(supporting_facts) == 2:
        supporting_titles = supporting_facts[0]
        supporting_sent_ids = supporting_facts[1]
    else:
        supporting_titles = (supporting_facts.get("title") or [])
        supporting_sent_ids = (supporting_facts.get("sent_id") or [])
    return {
        "candidate_id": f"hotpotqa-{original_id}",
        "source_name": "HotpotQA",
        "source_dataset": "hotpotqa/hotpot_qa",
        "source_split": "distractor/validation",
        "source_url": "https://huggingface.co/datasets/hotpotqa/hotpot_qa",
        "original_id": original_id,
        "module_candidates": ["A4"],
        "task_family": "multi_hop_question_answering",
        "category": row.get("level"),
        "prompt": prompt,
        "turns": None,
        "options": None,
        "answer": row.get("answer"),
        "scoring_method": "answer_em_f1",
        "scoring_params": {
            "question_type": row.get("type"),
            "supporting_titles": supporting_titles,
            "supporting_sent_ids": supporting_sent_ids,
        },
        "anti_contamination_source": row.get("level"),
        "source_metadata": {
            "question": row.get("question"),
            "type": row.get("type"),
            "level": row.get("level"),
            "supporting_facts": supporting_facts,
            "context": row.get("context"),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Keep the multi-hop evidence pattern, but rebuild the passages and entity chain with private source texts so the final A4 item requires 2-3 hops without copying benchmark wording.",
        "notes": "Public multi-hop QA pool for A4 reasoning-over-documents items.",
    }


def iter_truthfulqa_rows(row_limit: int | None = None):
    path = ROOT / "raw_sources" / "truthfulqa" / "TruthfulQA.csv"
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if row_limit is not None and idx >= row_limit:
                break
            item = dict(row)
            item["_csv_row_idx"] = idx
            yield item


def normalize_truthfulqa(row: dict) -> dict:
    idx = int(row.get("_csv_row_idx", 0))
    return {
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


def normalize_or_bench(row: dict) -> dict:
    row_idx = int(row.get("_hf_row_idx", 0))
    return {
        "candidate_id": f"or-bench-hard-{row_idx}",
        "source_name": "OR-Bench",
        "source_dataset": "bench-llm/or-bench",
        "source_split": "or-bench-hard-1k/train",
        "source_url": "https://huggingface.co/datasets/bench-llm/or-bench",
        "original_id": str(row_idx),
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
            "hf_row_idx": row_idx,
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Keep the benign-but-sensitive boundary pattern, but rewrite scenario, actors, and wording into the project's B3 and B8 scenario families.",
        "notes": "Full OR-Bench hard pool for over-refusal and professional-context derivation.",
    }


def normalize_livecodebench(row: dict) -> dict:
    question_id = str(row.get("question_id"))
    test_id = str(row.get("test_id"))
    original_id = f"{question_id}-{test_id}"
    return {
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
            "hf_row_idx": row.get("_hf_row_idx"),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Use the problem type and dynamic contest freshness signal, but rewrite into the project's A2 task templates with private hidden tests and derived execution or bug-fix variants.",
        "notes": "Full LiveCodeBench test_generation pool for A2 generation and derivative task design.",
    }


def ensure_cnn_dailymail_assets() -> dict[str, Path]:
    files = {
        "cnn_stories": (
            "https://huggingface.co/datasets/ccdv/cnn_dailymail/resolve/main/cnn_stories.tgz",
            CNN_DAILYMAIL_DIR / "cnn_stories.tgz",
        ),
        "dm_stories": (
            "https://huggingface.co/datasets/ccdv/cnn_dailymail/resolve/main/dailymail_stories.tgz",
            CNN_DAILYMAIL_DIR / "dailymail_stories.tgz",
        ),
        "val_urls": (
            "https://raw.githubusercontent.com/abisee/cnn-dailymail/master/url_lists/all_val.txt",
            CNN_DAILYMAIL_DIR / "all_val.txt",
        ),
    }
    paths = {}
    for key, (url, path) in files.items():
        download_file(url, path)
        paths[key] = path
    return paths


def ensure_cnn_validation_subset_assets() -> dict[str, Path]:
    files = {
        "cnn_stories": (
            "https://huggingface.co/datasets/ccdv/cnn_dailymail/resolve/main/cnn_stories.tgz",
            CNN_DAILYMAIL_DIR / "cnn_stories.tgz",
        ),
        "val_urls": (
            "https://raw.githubusercontent.com/abisee/cnn-dailymail/master/url_lists/all_val.txt",
            CNN_DAILYMAIL_DIR / "all_val.txt",
        ),
    }
    paths = {}
    for key, (url, path) in files.items():
        download_file(url, path)
        paths[key] = path
    return paths


def read_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def parse_cnn_dailymail_story(raw_text: str) -> tuple[str, str]:
    dm_single_close_quote = "\u2019"
    dm_double_close_quote = "\u201d"
    end_tokens = [".", "!", "?", "...", "'", "`", '"', dm_single_close_quote, dm_double_close_quote, ")"]

    def fix_missing_period(line: str) -> str:
        if "@highlight" in line or not line:
            return line
        if line[-1] in end_tokens:
            return line
        return line + " ."

    lines = [fix_missing_period(line.strip()) for line in raw_text.splitlines()]
    article_lines = []
    highlights = []
    next_is_highlight = False
    for line in lines:
        if not line:
            continue
        if line.startswith("@highlight"):
            next_is_highlight = True
            continue
        if next_is_highlight:
            highlights.append(line)
        else:
            article_lines.append(line)
    return " ".join(article_lines), "\n".join(highlights)


def iter_cnn_dailymail_validation_rows(row_limit: int | None = None):
    if load_dataset is not None:
        ds = load_dataset("ccdv/cnn_dailymail", "3.0.0", split="validation")
        for idx, row in enumerate(ds):
            if row_limit is not None and idx >= row_limit:
                break
            item = dict(row)
            item["story_id"] = item.get("id") or f"validation-{idx:05d}"
            item["publisher"] = "cnn_or_dailymail"
            item["source_split"] = "validation"
            yield item
        return
    asset_paths = ensure_cnn_dailymail_assets()
    valid_hashes = {url_hash(url): True for url in read_text_lines(asset_paths["val_urls"])}
    yielded = 0
    tar_specs = [
        ("cnn", asset_paths["cnn_stories"]),
        ("dailymail", asset_paths["dm_stories"]),
    ]
    for publisher, tar_path in tar_specs:
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                story_name = Path(member.name).name
                if not story_name.endswith(".story"):
                    continue
                story_id = story_name[:-6]
                if story_id not in valid_hashes:
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                raw_text = extracted.read().decode("utf-8", errors="replace")
                article, highlights = parse_cnn_dailymail_story(raw_text)
                yield {
                    "story_id": story_id,
                    "publisher": publisher,
                    "article": article,
                    "highlights": highlights,
                    "source_split": "validation",
                }
                yielded += 1
                if row_limit is not None and yielded >= row_limit:
                    return


def iter_cnn_validation_subset_rows(row_limit: int | None = None):
    asset_paths = ensure_cnn_validation_subset_assets()
    valid_hashes = {url_hash(url): True for url in read_text_lines(asset_paths["val_urls"])}
    yielded = 0
    with tarfile.open(asset_paths["cnn_stories"], "r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            story_name = Path(member.name).name
            if not story_name.endswith(".story"):
                continue
            story_id = story_name[:-6]
            if story_id not in valid_hashes:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            raw_text = extracted.read().decode("utf-8", errors="replace")
            article, highlights = parse_cnn_dailymail_story(raw_text)
            yield {
                "story_id": story_id,
                "publisher": "cnn",
                "article": article,
                "highlights": highlights,
                "source_split": "validation/cnn_subset",
            }
            yielded += 1
            if row_limit is not None and yielded >= row_limit:
                return


def normalize_cnn_dailymail(row: dict) -> dict:
    prompt = f"Summarize the following article:\n\n{row.get('article', '')}"
    story_id = str(row["story_id"])
    return {
        "candidate_id": f"cnn-dailymail-{story_id}",
        "source_name": "CNN/DailyMail",
        "source_dataset": "ccdv/cnn_dailymail",
        "source_split": row.get("source_split") or "validation",
        "source_url": "https://huggingface.co/datasets/ccdv/cnn_dailymail",
        "original_id": story_id,
        "module_candidates": ["A4"],
        "task_family": "summarization",
        "category": row.get("publisher"),
        "prompt": prompt,
        "turns": None,
        "options": None,
        "answer": row.get("highlights"),
        "scoring_method": "rouge_l",
        "scoring_params": {
            "summary_sentence_count": len((row.get("highlights") or "").splitlines()),
        },
        "anti_contamination_source": row.get("publisher"),
        "source_metadata": {
            "publisher": row.get("publisher"),
            "article": row.get("article"),
            "highlights": row.get("highlights"),
        },
        "direct_reuse_allowed": False,
        "rewrite_guidance": "Use the discourse structure and summary compression pattern only; rebuild with private articles and private reference summaries for A4 summarization probes.",
        "notes": "Public summarization pool for A4 compression and salience-tracking tasks.",
    }


SOURCE_SPECS = {
    "ifeval": {
        "dataset": "google/IFEval",
        "config": "default",
        "split": "train",
        "parquet_url": "https://huggingface.co/datasets/google/IFEval/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "ifeval" / "IFEval.parquet",
        "normalizer": normalize_ifeval,
        "output_name": "ifeval_candidates.jsonl",
    },
    "mmlu_pro": {
        "dataset": "TIGER-Lab/MMLU-Pro",
        "config": "default",
        "split": "test",
        "parquet_url": "https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "tiger_lab_mmlu_pro" / "test.parquet",
        "normalizer": normalize_mmlu_pro,
        "output_name": "mmlu_pro_candidates.jsonl",
    },
    "jbb_harmful": {
        "dataset": "JailbreakBench/JBB-Behaviors",
        "config": "behaviors",
        "split": "harmful",
        "row_iterator": lambda row_limit=None: iter_csv_rows(
            ROOT / "raw_sources" / "jailbreakbench" / "harmful-behaviors.csv",
            row_limit=row_limit,
        ),
        "normalizer": normalize_jbb_harmful,
        "output_name": "jbb_harmful_candidates.jsonl",
    },
    "livebench_instruction": {
        "dataset": "livebench/instruction_following",
        "config": "default",
        "split": "test",
        "parquet_url": "https://huggingface.co/datasets/livebench/instruction_following/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "livebench_instruction_following" / "test.parquet",
        "normalizer": normalize_livebench_instruction,
        "output_name": "livebench_instruction_candidates.jsonl",
    },
    "gsm8k": {
        "dataset": "openai/gsm8k",
        "config": "main",
        "split": "train",
        "parquet_url": "https://huggingface.co/datasets/openai/gsm8k/resolve/refs%2Fconvert%2Fparquet/main/train/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "openai_gsm8k" / "train.parquet",
        "normalizer": normalize_gsm8k,
        "output_name": "gsm8k_candidates.jsonl",
    },
    "gpqa_diamond": {
        "dataset": "openai/simple-evals:gpqa_diamond",
        "split": "diamond",
        "row_iterator": lambda row_limit=None: iter_csv_rows(
            ROOT / "raw_sources" / "simple-evals" / "gpqa_diamond.csv",
            row_limit=row_limit,
        ),
        "normalizer": normalize_gpqa_diamond,
        "output_name": "gpqa_diamond_candidates.jsonl",
    },
    "simpleqa": {
        "dataset": "openai/simple-evals:simple_qa_test_set",
        "split": "test",
        "row_iterator": lambda row_limit=None: iter_csv_rows(
            ROOT / "raw_sources" / "simple-evals" / "simple_qa_test_set.csv",
            row_limit=row_limit,
        ),
        "normalizer": normalize_simpleqa,
        "output_name": "simpleqa_candidates.jsonl",
    },
    "math500": {
        "dataset": "openai/simple-evals:math_500_test",
        "split": "test",
        "row_iterator": lambda row_limit=None: iter_csv_rows(
            ROOT / "raw_sources" / "simple-evals" / "math_500_test.csv",
            row_limit=row_limit,
        ),
        "normalizer": normalize_math500,
        "output_name": "math500_candidates.jsonl",
    },
    "supergpqa": {
        "dataset": "m-a-p/SuperGPQA",
        "split": "train",
        "row_iterator": lambda row_limit=None: iter_jsonl_rows(
            ROOT / "raw_sources" / "SuperGPQA-all.jsonl",
            row_limit=row_limit,
        ),
        "normalizer": normalize_supergpqa,
        "output_name": "supergpqa_candidates.jsonl",
    },
    "sorrybench": {
        "dataset": "AIM-Harvard/sorrybench",
        "config": "default",
        "split": "train",
        "parquet_url": "https://huggingface.co/datasets/AIM-Harvard/sorrybench/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "aim_harvard_sorrybench" / "train.parquet",
        "normalizer": normalize_sorrybench,
        "output_name": "sorrybench_candidates.jsonl",
    },
    "squad": {
        "dataset": "rajpurkar/squad",
        "config": "plain_text",
        "split": "validation",
        "parquet_url": "https://huggingface.co/datasets/rajpurkar/squad/resolve/refs%2Fconvert%2Fparquet/plain_text/validation/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "rajpurkar_squad" / "validation.parquet",
        "normalizer": normalize_squad,
        "output_name": "squad_candidates.jsonl",
    },
    "hotpotqa": {
        "dataset": "hotpotqa/hotpot_qa",
        "split": "validation",
        "row_iterator": iter_hotpotqa_validation_rows,
        "normalizer": normalize_hotpotqa,
        "output_name": "hotpotqa_candidates.jsonl",
    },
    "cnn_dailymail": {
        "dataset": "ccdv/cnn_dailymail",
        "split": "validation",
        "row_iterator": iter_cnn_dailymail_validation_rows,
        "normalizer": normalize_cnn_dailymail,
        "output_name": "cnn_dailymail_candidates.jsonl",
    },
    "cnn_dailymail_cnn_subset": {
        "dataset": "ccdv/cnn_dailymail",
        "split": "validation/cnn_subset",
        "row_iterator": iter_cnn_validation_subset_rows,
        "normalizer": normalize_cnn_dailymail,
        "output_name": "cnn_dailymail_cnn_subset_candidates.jsonl",
    },
    "truthfulqa": {
        "dataset": "truthfulqa/truthful_qa",
        "split": "generation",
        "row_iterator": iter_truthfulqa_rows,
        "normalizer": normalize_truthfulqa,
        "output_name": "truthfulqa_candidates.jsonl",
    },
    "or_bench_hard": {
        "dataset": "bench-llm/or-bench",
        "config": "or-bench-hard-1k",
        "split": "train",
        "row_iterator": lambda row_limit=None: iter_csv_rows(
            ROOT / "raw_sources" / "or-bench" / "or-bench-hard-1k.csv",
            row_limit=row_limit,
        ),
        "normalizer": normalize_or_bench,
        "output_name": "or_bench_hard_candidates.jsonl",
    },
    "livecodebench_test_generation": {
        "dataset": "livecodebench/test_generation",
        "config": "default",
        "split": "test",
        "parquet_url": "https://huggingface.co/datasets/livecodebench/test_generation/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet",
        "parquet_cache": ROOT / "raw_sources" / "parquet_cache" / "livecodebench_test_generation" / "test.parquet",
        "normalizer": normalize_livecodebench,
        "output_name": "livecodebench_test_generation_candidates.jsonl",
    },
}


def iter_source_rows(spec: dict, row_limit: int | None):
    parquet_url = spec.get("parquet_url")
    parquet_cache = spec.get("parquet_cache")
    if parquet_url is not None and parquet_cache is not None and pq is not None:
        yield from iter_parquet_rows(parquet_url, parquet_cache, row_limit=row_limit)
        return
    row_iterator = spec.get("row_iterator")
    if row_iterator is not None:
        yield from row_iterator(row_limit=row_limit)
        return
    yield from iter_hf_rows(
        dataset=spec["dataset"],
        config=spec["config"],
        split=spec["split"],
        row_limit=row_limit,
    )


def rebuild_extraction_manifest(output_dir: Path) -> list[dict]:
    """Describe every normalized root file, not only the sources from this invocation."""
    manifest = []
    for output_path in sorted(output_dir.glob("*.jsonl")):
        count = 0
        first_row = None
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                count += 1
                if first_row is None:
                    first_row = json.loads(line)
        if first_row is None:
            continue
        stem = output_path.stem.removesuffix("_candidates")
        manifest.append(
            {
                "source_key": stem,
                "dataset": first_row.get("source_dataset"),
                "split": first_row.get("source_split"),
                "output_file": str(output_path),
                "count": count,
            }
        )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sources",
        nargs="*",
        default=list(SOURCE_SPECS.keys()),
        choices=list(SOURCE_SPECS.keys()),
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "normalized"),
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=None,
        help="Optional cap for each source, useful for quick tests.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for source_key in args.sources:
        spec = SOURCE_SPECS[source_key]
        output_path = output_dir / spec["output_name"]
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        count = 0
        with temp_path.open("w", encoding="utf-8") as f:
            for row in iter_source_rows(spec, row_limit=args.limit_per_source):
                normalized = spec["normalizer"](row)
                if not has_derived_prompt(normalized):
                    continue
                f.write(json.dumps(normalized, ensure_ascii=False, default=json_fallback) + "\n")
                count += 1
                if count % 500 == 0:
                    print(f"[progress] {source_key}: {count} rows", flush=True)
        temp_path.replace(output_path)
        manifest.append(
            {
                "source_key": source_key,
                "dataset": spec["dataset"],
                "split": spec["split"],
                "output_file": str(output_path),
                "count": count,
            }
        )
        print(f"[ok] {source_key}: {count} rows -> {output_path}")

    manifest = rebuild_extraction_manifest(output_dir)
    summary_path = output_dir / "extraction_summary.json"
    temp_summary_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    temp_summary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=json_fallback),
        encoding="utf-8",
    )
    temp_summary_path.replace(summary_path)
    print(f"[ok] summary -> {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
