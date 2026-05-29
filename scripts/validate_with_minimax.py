#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NORMALIZED = ROOT / "normalized"
REPORT_DEFAULT = ROOT / "manifests" / "minimax_validation_report.json"
MODEL_ID = "MiniMax-M2.7"
BASE_URL = "https://api.minimaxi.com/anthropic/v1"


def curl_json(method: str, url: str, api_key: str, body: dict | None = None) -> tuple[int, dict]:
    cmd = [
        "curl",
        "-s",
        "-L",
        "--max-time",
        "40",
        "-X",
        method,
        url,
        "-H",
        "Content-Type: application/json",
        "-H",
        f"X-Api-Key: {api_key}",
    ]
    if body is not None:
        cmd.extend(["--data", json.dumps(body, ensure_ascii=False)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return result.returncode, {"curl_error": result.stderr.strip() or result.stdout.strip()}
    try:
        return 0, json.loads(result.stdout)
    except json.JSONDecodeError:
        return 0, {"raw": result.stdout[:1000]}


def derive_prompt(record: dict) -> str | None:
    prompt = record.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    turns = record.get("turns")
    if isinstance(turns, list):
        for item in turns:
            if isinstance(item, str) and item.strip():
                return item
    return None


def build_validation_prompt(prompt: str) -> str:
    excerpt = prompt[:2000]
    return (
        "You are validating whether a dataset record can be sent to the model API.\n"
        "Do not fully solve the task.\n"
        "After reading the task text, reply with exactly: OK\n\n"
        "Task text:\n"
        f"{excerpt}"
    )


def validate_local_file(path: Path) -> dict:
    required = {
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
    }
    total = 0
    missing_required = 0
    missing_prompt = 0
    samples = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)
            if not required.issubset(record):
                missing_required += 1
            prompt = derive_prompt(record)
            if not prompt:
                missing_prompt += 1
            if len(samples) < 3:
                samples.append(record)
    return {
        "file": str(path),
        "total_rows": total,
        "missing_required_rows": missing_required,
        "missing_prompt_rows": missing_prompt,
        "sample_records": samples,
    }


def remote_validate_record(record: dict, api_key: str) -> dict:
    prompt = derive_prompt(record)
    if not prompt:
        return {
            "candidate_id": record.get("candidate_id"),
            "ok": False,
            "error": "missing prompt",
        }
    payload = {
        "model": MODEL_ID,
        "max_tokens": 8,
        "messages": [
            {
                "role": "user",
                "content": build_validation_prompt(prompt),
            }
        ],
    }
    status, data = curl_json("POST", f"{BASE_URL}/messages", api_key, payload)
    blocks = data.get("content", []) if isinstance(data, dict) else []
    text_blocks = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return {
        "candidate_id": record.get("candidate_id"),
        "ok": status == 0 and isinstance(data, dict) and data.get("model") == MODEL_ID,
        "status": status,
        "response_model": data.get("model") if isinstance(data, dict) else None,
        "stop_reason": data.get("stop_reason") if isinstance(data, dict) else None,
        "usage": data.get("usage") if isinstance(data, dict) else None,
        "base_resp": data.get("base_resp") if isinstance(data, dict) else None,
        "text_preview": "\n".join(text_blocks)[:200],
        "error": data.get("curl_error") if isinstance(data, dict) else None,
    }


def load_first_n_records(path: Path, n: int) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= n:
                break
    return rows


def load_shortest_prompt_records(path: Path, n: int, scan_limit: int = 50) -> list[dict]:
    candidates = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx >= scan_limit:
                break
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            prompt = derive_prompt(record)
            if prompt:
                candidates.append((len(prompt), record))
    candidates.sort(key=lambda x: x[0])
    return [record for _, record in candidates[:n]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-file", type=int, default=1)
    parser.add_argument("--report", default=str(REPORT_DEFAULT))
    args = parser.parse_args()

    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("MINIMAX_API_KEY is required")

    model_status, model_data = curl_json("GET", f"{BASE_URL}/models/{MODEL_ID}", api_key)

    files = sorted(NORMALIZED.glob("*.jsonl"))
    report = {
        "model_check": {
            "ok": model_status == 0 and isinstance(model_data, dict) and model_data.get("id") == MODEL_ID,
            "status": model_status,
            "response": model_data,
        },
        "files": [],
    }

    for path in files:
        local_result = validate_local_file(path)
        remote_results = []
        for record in load_shortest_prompt_records(path, args.samples_per_file):
            remote_results.append(remote_validate_record(record, api_key))
        report["files"].append(
            {
                "file": local_result["file"],
                "total_rows": local_result["total_rows"],
                "missing_required_rows": local_result["missing_required_rows"],
                "missing_prompt_rows": local_result["missing_prompt_rows"],
                "remote_validation": remote_results,
            }
        )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
