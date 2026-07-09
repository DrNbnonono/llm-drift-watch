#!/usr/bin/env python3
"""
将题库 JSONL 文件按模块分类转换为 CSV 文件。

每个模块生成一个独立的 CSV 文件，放在 QuestionBank/ 目录下。
嵌套对象展平为带点号的列名，复杂字段（turn_script、scoring_params）保留为 JSON 字符串。
"""

import csv
import json
import os
import sys
from collections import OrderedDict

# ── 配置 ──────────────────────────────────────────────
INPUT_FILE = os.path.join(
    os.path.dirname(__file__), "..",
    "final_bank_specs", "generated", "final_bank_items.jsonl"
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "QuestionBank")

# CSV 列定义（保持统一，所有模块共享同一列结构）
CSV_COLUMNS = [
    # ── 基本信息 ──
    "question_id",
    "version",
    "module",
    "subtype",
    "item_format",
    "difficulty",
    "drift_role",
    # ── 题目内容 ──
    "prompt_template",
    "turn_script",
    # ── 答案与评分 ──
    "ground_truth",
    "scoring_method",
    "scoring_params",
    # ── 约束与配额 ──
    "module_quota_tag",
    "qa_status",
    # ── 轮换策略 ──
    "rotation_replaceable",
    "rotation_priority",
    "rotation_expected_lifespan_days",
    # ── 来源溯源 ──
    "provenance_rewrite_ids",
    "provenance_source_candidate_ids",
    "provenance_transformation_summary",
    # ── 备注 ──
    "notes",
]


def flatten_item(item: dict) -> dict:
    """将一个 JSONL 条目展平为一维字典。"""
    flat = OrderedDict()

    # 基本信息
    flat["question_id"] = item.get("question_id", "")
    flat["version"] = item.get("version", "")
    flat["module"] = item.get("module", "")
    flat["subtype"] = item.get("subtype", "")
    flat["item_format"] = item.get("item_format", "")
    flat["difficulty"] = item.get("difficulty", "") or ""
    flat["drift_role"] = item.get("drift_role", "")

    # 题目内容
    flat["prompt_template"] = (item.get("prompt_template") or "").strip()

    # turn_script 序列化为 JSON
    turn_script = item.get("turn_script")
    if turn_script:
        flat["turn_script"] = json.dumps(turn_script, ensure_ascii=False)
    else:
        flat["turn_script"] = ""

    # 答案与评分
    gt = item.get("ground_truth")
    if gt is None:
        flat["ground_truth"] = ""
    else:
        flat["ground_truth"] = str(gt)

    flat["scoring_method"] = item.get("scoring_method", "")

    # scoring_params 序列化为 JSON
    sp = item.get("scoring_params")
    if sp:
        flat["scoring_params"] = json.dumps(sp, ensure_ascii=False)
    else:
        flat["scoring_params"] = ""

    # 约束与配额
    flat["module_quota_tag"] = item.get("module_quota_tag", "") or ""
    flat["qa_status"] = item.get("qa_status", "")

    # rotation_policy 展平
    rp = item.get("rotation_policy", {})
    flat["rotation_replaceable"] = rp.get("replaceable", "")
    flat["rotation_priority"] = rp.get("rotation_priority", "")
    flat["rotation_expected_lifespan_days"] = rp.get("expected_lifespan_days", "") or ""

    # provenance 展平
    prov = item.get("provenance", {})
    rw_ids = prov.get("rewrite_ids", [])
    flat["provenance_rewrite_ids"] = "; ".join(rw_ids) if rw_ids else ""
    src_ids = prov.get("source_candidate_ids", [])
    flat["provenance_source_candidate_ids"] = "; ".join(src_ids) if src_ids else ""
    flat["provenance_transformation_summary"] = prov.get("transformation_summary", "")

    # 备注
    flat["notes"] = item.get("notes", "")

    return flat


def module_description(module: str) -> str:
    """返回模块的中文描述，用于文件名。"""
    descriptions = {
        "A1": "A1_数学推理",
        "A2": "A2_代码编程",
        "A3": "A3_指令遵循",
        "A4": "A4_英语阅读",
        "A5": "A5_知识多选",
        "A6": "A6_逻辑推理",
        "B1": "B1_有害拒绝",
        "B2": "B2_越狱抵抗",
        "B3": "B3_安全边界",
        "B4": "B4_引用真实性",
        "B5": "B5_间接注入",
        "B6": "B6_多轮越狱",
        "B7": "B7_真实性边界",
        "B8": "B8_专业场景安全",
        "C1": "C1_数学边界",
        "C2": "C2_严格格式",
        "C3": "C3_思维链结构",
        "C4": "C4_一致性校验",
    }
    return descriptions.get(module, module)


def main():
    input_path = os.path.normpath(INPUT_FILE)
    output_dir = os.path.normpath(OUTPUT_DIR)

    if not os.path.isfile(input_path):
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # ── 读取所有条目并按模块分组 ──
    modules = OrderedDict()
    total = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_no} JSON parse error: {e}", file=sys.stderr)
                continue

            mod = item.get("module", "UNKNOWN")
            if mod not in modules:
                modules[mod] = []
            modules[mod].append(flatten_item(item))
            total += 1

    print(f"[INFO] total={total} items in {len(modules)} modules")

    # ── 按模块写入 CSV ──
    for mod, items in modules.items():
        desc = module_description(mod)
        filename = f"{desc}.csv"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in items:
                writer.writerow(row)

        print(f"  [OK] {mod:4s} -> {filename:40s} ({len(items)} items)")

    # ── 生成汇总文件 ──
    summary_path = os.path.join(output_dir, "_summary_all.csv")
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for mod in modules:
            for row in modules[mod]:
                writer.writerow(row)

    print(f"\n[SUMMARY] _summary_all.csv ({total} items)")
    print(f"[OUTPUT] {output_dir}")


if __name__ == "__main__":
    main()
