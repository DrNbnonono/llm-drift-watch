#!/usr/bin/env python3
"""One-shot seed of module/subtype/quota_tag dictionaries from existing data sources.

Reads:
  * ``QuestionBank/*.csv`` (preferred for module display_name + parent_group)
  * ``final_bank_specs/generated/final_bank_items.jsonl`` (subtype / quota_tag occurrence)

Writes into the SQLite bank_items DB at ``manifests/evaluation.sqlite`` (or whatever
``QUESTION_BANK_SQLITE_PATH`` points to). Idempotent: running twice is safe.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Hard-coded mapping of the 18 known module codes. Update here if new modules
# are introduced (or call upsert_dict from the new system-settings UI later).
MODULE_SEED: list[dict] = [
    {"code": "A1", "display_name": "数学推理", "parent_group": "capability", "sort_order": 1, "color_token": "mod-A1", "description": "基础算术 / 应用题"},
    {"code": "A2", "display_name": "代码编程", "parent_group": "capability", "sort_order": 2, "color_token": "mod-A2", "description": "代码生成 / 调试"},
    {"code": "A3", "display_name": "指令遵循", "parent_group": "capability", "sort_order": 3, "color_token": "mod-A3", "description": "格式 / 角色 / 多步指令"},
    {"code": "A4", "display_name": "英语阅读", "parent_group": "capability", "sort_order": 4, "color_token": "mod-A4", "description": "英文阅读理解"},
    {"code": "A5", "display_name": "知识多选", "parent_group": "capability", "sort_order": 5, "color_token": "mod-A5", "description": "知识题 (MCQ)"},
    {"code": "A6", "display_name": "逻辑推理", "parent_group": "capability", "sort_order": 6, "color_token": "mod-A6", "description": "演绎 / 归纳"},
    {"code": "B1", "display_name": "有害拒绝", "parent_group": "safety", "sort_order": 11, "color_token": "mod-B1", "description": "明确有害请求拒绝"},
    {"code": "B2", "display_name": "越狱抵抗", "parent_group": "safety", "sort_order": 12, "color_token": "mod-B2", "description": "Jailbreak 对抗"},
    {"code": "B3", "display_name": "安全边界", "parent_group": "safety", "sort_order": 13, "color_token": "mod-B3", "description": "灰区请求处理"},
    {"code": "B4", "display_name": "引用真实性", "parent_group": "safety", "sort_order": 14, "color_token": "mod-B4", "description": "引用 / 来源核实"},
    {"code": "B5", "display_name": "间接注入", "parent_group": "safety", "sort_order": 15, "color_token": "mod-B5", "description": "Indirect prompt injection"},
    {"code": "B6", "display_name": "多轮越狱", "parent_group": "safety", "sort_order": 16, "color_token": "mod-B6", "description": "多轮 jailbreak 演化"},
    {"code": "B7", "display_name": "真实性边界", "parent_group": "safety", "sort_order": 17, "color_token": "mod-B7", "description": "事实性边界"},
    {"code": "B8", "display_name": "专业场景安全", "parent_group": "safety", "sort_order": 18, "color_token": "mod-B8", "description": "专业领域安全"},
    {"code": "C1", "display_name": "数学边界", "parent_group": "probe", "sort_order": 21, "color_token": "mod-C1", "description": "数学对抗 / 探针"},
    {"code": "C2", "display_name": "严格格式", "parent_group": "probe", "sort_order": 22, "color_token": "mod-C2", "description": "强约束格式"},
    {"code": "C3", "display_name": "思维链结构", "parent_group": "probe", "sort_order": 23, "color_token": "mod-C3", "description": "CoT 结构探针"},
    {"code": "C4", "display_name": "一致性校验", "parent_group": "probe", "sort_order": 24, "color_token": "mod-C4", "description": "答案一致性"},
]


def _humanize_subtype(code: str) -> str:
    return re.sub(r"[_\-]+", " ", code).strip().title() or code


def _humanize_quota_tag(code: str) -> str:
    return re.sub(r"[_\-]+", " ", code).strip().title() or code


def collect_from_jsonl(jsonl_path: Path) -> tuple[set[tuple[str, str]], set[tuple[str, str | None]]]:
    """Return ((subtype, module_code), (quota_tag, module_code_or_None)) seen in items."""
    subtypes: set[tuple[str, str]] = set()
    quota_tags: set[tuple[str, str | None]] = set()
    if not jsonl_path.exists():
        return subtypes, quota_tags
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            module = item.get("module") or ""
            subtype = item.get("subtype") or ""
            if subtype and module:
                subtypes.add((subtype, module))
            quota_tag = item.get("module_quota_tag") or ""
            if quota_tag:
                quota_tags.add((quota_tag, module or None))
    return subtypes, quota_tags


def collect_from_csv_dir(csv_dir: Path) -> tuple[set[tuple[str, str]], set[tuple[str, str | None]]]:
    """Scan QuestionBank/*.csv for subtype / quota_tag / module associations."""
    subtypes: set[tuple[str, str]] = set()
    quota_tags: set[tuple[str, str | None]] = set()
    if not csv_dir.exists():
        return subtypes, quota_tags
    for csv_path in sorted(csv_dir.glob("*.csv")):
        if csv_path.name.startswith("_"):
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                module = (row.get("module") or "").strip()
                subtype = (row.get("subtype") or "").strip()
                quota = (row.get("module_quota_tag") or "").strip()
                if subtype and module:
                    subtypes.add((subtype, module))
                if quota:
                    quota_tags.add((quota, module or None))
    return subtypes, quota_tags


def main() -> int:
    from sqlite_runtime import SQLiteStore

    db_path = os.environ.get("QUESTION_BANK_SQLITE_PATH")
    store = SQLiteStore(db_path) if db_path else SQLiteStore()
    print(f"[seed] using db: {store.db_path}")

    print(f"[seed] upserting {len(MODULE_SEED)} modules")
    store.bulk_upsert_dict("module", MODULE_SEED)

    jsonl_path = ROOT / "final_bank_specs" / "generated" / "final_bank_items.jsonl"
    csv_dir = ROOT / "QuestionBank"

    subtypes_csv, quotas_csv = collect_from_csv_dir(csv_dir)
    subtypes_jsonl, quotas_jsonl = collect_from_jsonl(jsonl_path)
    all_subtypes = subtypes_csv | subtypes_jsonl
    all_quotas = quotas_csv | quotas_jsonl

    print(f"[seed] upserting {len(all_subtypes)} subtype rows")
    subtype_rows = [
        {
            "code": code,
            "module_code": module,
            "display_name": _humanize_subtype(code),
            "description": "",
            "sort_order": 0,
            "is_active": 1,
        }
        for code, module in sorted(all_subtypes)
    ]
    store.bulk_upsert_dict("subtype", subtype_rows)

    print(f"[seed] upserting {len(all_quotas)} quota_tag rows")
    quota_rows = [
        {
            "code": code,
            "module_code": module,
            "display_name": _humanize_quota_tag(code),
            "description": "",
            "sort_order": 0,
            "is_active": 1,
        }
        for code, module in sorted(all_quotas)
    ]
    store.bulk_upsert_dict("quota_tag", quota_rows)

    modules = store.list_dict("module")
    subtypes = store.list_dict("subtype")
    quotas = store.list_dict("quota_tag")
    print(f"[seed] DONE. modules={len(modules)} subtypes={len(subtypes)} quota_tags={len(quotas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
