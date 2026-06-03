#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NORMALIZED = ROOT / "normalized"
MANIFESTS = ROOT / "manifests"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def logic_rows() -> tuple[list[dict], list[dict]]:
    bbh_rows = []
    zebra_rows = []
    bbh_seeds = [
        ("BBH", "multi_step_rules", "从规则示例中归纳变换函数，再推断目标实例输出。"),
        ("BBEH", "symbolic_rewrite", "根据一组符号改写规则，计算最终字符串或数字。"),
        ("BBH", "tracking_shuffled_objects", "在长文本中追踪多个对象的状态与位置变化。"),
        ("BBEH", "boolean_reasoning", "综合真假条件与排除关系，求唯一满足对象。"),
        ("BBH", "dyck_like_brackets", "根据嵌套结构与局部规则，判断最终合法性或补全结果。"),
        ("BBEH", "causal_chains", "从多步因果链中推断最终结果。"),
        ("BBH", "disambiguation_qa", "从交织描述中选出唯一正确指代。"),
        ("BBEH", "induction_lists", "从多例子归纳列表运算规则。"),
        ("BBH", "date_reasoning", "在删减日历或非标准周期下进行纪年推断。"),
        ("BBEH", "operators", "自定义运算符系统下计算目标表达式。"),
        ("BBH", "word_sorting", "按隐藏规则而非字典序排序词项。"),
        ("BBEH", "penguins_in_a_table", "从表格和叙述中完成关系推断。"),
    ]
    for idx, (source_name, category, prompt) in enumerate(bbh_seeds, start=1):
        bbh_rows.append(
            {
                "candidate_id": f"bbh-bbeh-{idx:03d}",
                "source_name": source_name,
                "source_dataset": "BIG-Bench Hard / BBEH curated",
                "source_split": "curated",
                "source_url": "https://github.com/suzgunmirac/BIG-Bench-Hard",
                "original_id": str(idx),
                "module_candidates": ["A6"],
                "task_family": "logic_reasoning",
                "category": category,
                "prompt": prompt,
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "exact_match_or_numeric",
                "scoring_params": {"curated": True, "module_target": "A6"},
                "anti_contamination_source": "benchmark-inspired-only",
                "source_metadata": {"benchmark_family": source_name, "reasoning_axis": category},
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Retain the reasoning pattern only; rewrite entities, surface forms, and answer format into A6 formal tasks.",
                "notes": "Curated QB-v1.1 logic pool inspired by BIG-Bench Hard / BBEH styles.",
            }
        )
    zebra_planbench_seeds = [
        ("ZebraLogic", "constraint_satisfaction", "多实体、多位置约束满足，输出唯一排列。"),
        ("ZebraLogic", "relative_position", "根据相对左右/上下关系推断最终顺序。"),
        ("PlanBench", "stateful_simulation", "执行动作序列并计算最终世界状态。"),
        ("PlanBench", "goal_reachability", "判断给定动作集是否可达目标状态。"),
        ("ZebraLogic", "grid_reasoning", "在离散网格中根据约束选择唯一落点。"),
        ("PlanBench", "resource_planning", "资源受限时执行动作并推导最终资源分布。"),
        ("ZebraLogic", "matching", "根据多重属性匹配人物、地点和时间。"),
        ("PlanBench", "action_side_effects", "动作带副作用时跟踪状态变化。"),
        ("ZebraLogic", "puzzle_layout", "在拼图/棋盘布局中找满足条件的组合。"),
        ("PlanBench", "temporal_dependencies", "带前置条件与时序依赖的规划推断。"),
        ("ZebraLogic", "spatial_rotation", "旋转或翻转约束下确定最终朝向。"),
        ("PlanBench", "machine_control", "机器操作命令和模式切换状态模拟。"),
    ]
    for idx, (source_name, category, prompt) in enumerate(zebra_planbench_seeds, start=1):
        zebra_rows.append(
            {
                "candidate_id": f"zebra-plan-{idx:03d}",
                "source_name": source_name,
                "source_dataset": "ZebraLogic / PlanBench curated",
                "source_split": "curated",
                "source_url": "https://github.com/karthikv792/LLMs-Planning/ (PlanBench references)",
                "original_id": str(idx),
                "module_candidates": ["A6"],
                "task_family": "logic_reasoning",
                "category": category,
                "prompt": prompt,
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "exact_match_or_numeric",
                "scoring_params": {"curated": True, "module_target": "A6"},
                "anti_contamination_source": "benchmark-inspired-only",
                "source_metadata": {"benchmark_family": source_name, "reasoning_axis": category},
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Retain state/constraint structure only; rewrite into private A6 simulations, geometry, and long-context relation tasks.",
                "notes": "Curated QB-v1.1 logic pool inspired by Zebra-style puzzles and PlanBench state-transition tasks.",
            }
        )
    return bbh_rows, zebra_rows


def coding_rows() -> tuple[list[dict], list[dict]]:
    apps_rows = []
    bigcode_rows = []
    apps_seeds = [
        ("APPS", "constrained_program_synthesis", "多重约束程序编写，输入输出格式明确，隐藏边界较多。"),
        ("APPS", "stateful_data_processing", "日志、流水、状态机类数据处理。"),
        ("APPS", "matrix_transform", "二维/三维数组在复杂规则下变换。"),
        ("APPS", "string_simulation", "字符级别规则迭代与压缩/还原。"),
        ("APPS", "inventory_reconciliation", "库存/票务/资源流水结算。"),
        ("APPS", "window_aggregation", "多窗口、多阈值聚合计算。"),
        ("APPS", "combinational_search", "在多个约束下构造满足条件的程序输出。"),
        ("APPS", "parsing_normalization", "异构文本解析与规范化。"),
        ("LiveCodeBench", "contest_style_synthesis", "更贴近真实竞赛/实时编程叙述风格。"),
        ("LiveCodeBench", "execution_validated_coding", "以执行验证为主的真实题型结构。"),
        ("APPS", "queue_stack_machine", "基于命令序列的结构化状态模拟。"),
        ("LiveCodeBench", "data_pipeline_task", "近工程风格的数据流水处理。"),
    ]
    for idx, (source_name, category, prompt) in enumerate(apps_seeds, start=1):
        apps_rows.append(
            {
                "candidate_id": f"apps-live-{idx:03d}",
                "source_name": source_name,
                "source_dataset": "APPS / LiveCodeBench curated",
                "source_split": "curated",
                "source_url": "https://github.com/hendrycks/apps",
                "original_id": str(idx),
                "module_candidates": ["A2"],
                "task_family": "hard_coding",
                "category": category,
                "prompt": prompt,
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "exec",
                "scoring_params": {"curated": True, "module_target": "A2"},
                "anti_contamination_source": "benchmark-inspired-only",
                "source_metadata": {"benchmark_family": source_name, "coding_axis": category},
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Preserve task difficulty and validation style, but rewrite problem statement, examples, and hidden tests into private A2 tasks.",
                "notes": "Curated QB-v1.1 high-difficulty coding pool inspired by APPS and LiveCodeBench.",
            }
        )
    bigcode_seeds = [
        ("BigCodeBench", "long_code_comprehension", "阅读较长代码并复现最终输出。"),
        ("BigCodeBench", "multi_helper_pipeline", "理解多 helper 函数组合后的行为。"),
        ("EvalPlus", "strict_hidden_tests", "简单题面但边界严格，执行验证更苛刻。"),
        ("HumanEval+", "robust_exec", "函数级实现但隐藏测试覆盖更深。"),
        ("SWE-bench Lite", "bug_fix_and_patch_reasoning", "单文件/单函数逻辑修复。"),
        ("SWE-bench Lite", "regression_patch", "修复 bug 同时避免破坏已有行为。"),
        ("BigCodeBench", "config_driven_processing", "长代码中的配置、状态、数据流联合推断。"),
        ("EvalPlus", "edge_case_repair", "修复实现并覆盖边界输入。"),
        ("BigCodeBench", "code_result_reproduction", "复现复杂脚本执行结果。"),
        ("SWE-bench Lite", "targeted_patch", "不做全仓库，只保留 patch 推理模式。"),
        ("HumanEval+", "boundary_sensitive_function", "函数实现对边界和空输入敏感。"),
        ("BigCodeBench", "large_context_coding", "中长代码阅读、摘要和输出复现结合。"),
    ]
    for idx, (source_name, category, prompt) in enumerate(bigcode_seeds, start=1):
        bigcode_rows.append(
            {
                "candidate_id": f"bigcode-eval-{idx:03d}",
                "source_name": source_name,
                "source_dataset": "BigCodeBench / EvalPlus / SWE-bench Lite curated",
                "source_split": "curated",
                "source_url": "https://github.com/bigcode-project/bigcodebench",
                "original_id": str(idx),
                "module_candidates": ["A2"],
                "task_family": "hard_coding",
                "category": category,
                "prompt": prompt,
                "turns": None,
                "options": None,
                "answer": None,
                "scoring_method": "exec_or_exact_match",
                "scoring_params": {"curated": True, "module_target": "A2"},
                "anti_contamination_source": "benchmark-inspired-only",
                "source_metadata": {"benchmark_family": source_name, "coding_axis": category},
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Retain long-code reading, patch reasoning, or hidden-test rigor; rewrite concrete code and task surface into QB-v1.1 A2 items.",
                "notes": "Curated QB-v1.1 high-difficulty coding pool inspired by BigCodeBench, EvalPlus, HumanEval+, and SWE-bench Lite.",
            }
        )
    return apps_rows, bigcode_rows


def upsert_extraction_summary(entries: list[dict]) -> None:
    path = NORMALIZED / "extraction_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_key = {row["source_key"]: row for row in payload}
    for entry in entries:
        by_key[entry["source_key"]] = entry
    merged = list(by_key.values())
    merged.sort(key=lambda row: row["source_key"])
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_source_registry(entries: list[dict]) -> None:
    path = MANIFESTS / "source_registry.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_name = {row["source_name"]: row for row in rows}
    for entry in entries:
        by_name[entry["source_name"]] = entry
    fieldnames = list(rows[0].keys())
    merged = [by_name[name] for name in sorted(by_name)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)


def main() -> None:
    bbh_rows, zebra_rows = logic_rows()
    apps_rows, bigcode_rows = coding_rows()
    outputs = [
        ("bbh_bbeh_logic_curated", "benchmark-curated/bbh-bbeh-logic", "curated", NORMALIZED / "bbh_bbeh_logic_candidates.jsonl", bbh_rows),
        ("zebra_planbench_logic_curated", "benchmark-curated/zebra-planbench-logic", "curated", NORMALIZED / "zebra_planbench_logic_candidates.jsonl", zebra_rows),
        ("apps_livecodebench_coding_curated", "benchmark-curated/apps-livecodebench-coding", "curated", NORMALIZED / "apps_livecodebench_coding_candidates.jsonl", apps_rows),
        ("bigcode_evalplus_swebench_curated", "benchmark-curated/bigcode-evalplus-swebench", "curated", NORMALIZED / "bigcode_evalplus_swebench_candidates.jsonl", bigcode_rows),
    ]
    summary_entries = []
    registry_entries = []
    for source_key, dataset, split, out_path, rows in outputs:
        write_jsonl(out_path, rows)
        summary_entries.append(
            {
                "source_key": source_key,
                "dataset": dataset,
                "split": split,
                "output_file": str(out_path),
                "count": len(rows),
            }
        )
    registry_entries.extend(
        [
            {
                "source_name": "BIG-Bench Hard / BBEH",
                "source_dataset": "benchmark-curated/bbh-bbeh-logic",
                "source_url": "https://github.com/suzgunmirac/BIG-Bench-Hard",
                "local_path": str(NORMALIZED / "bbh_bbeh_logic_candidates.jsonl"),
                "module_candidates": "A6",
                "status": "curated_method_snapshot",
                "notes": "Curated logic-reasoning source pool for QB-v1.1, inspired by BIG-Bench Hard and BBEH task styles.",
            },
            {
                "source_name": "ZebraLogic / PlanBench",
                "source_dataset": "benchmark-curated/zebra-planbench-logic",
                "source_url": "https://github.com/karthikv792/LLMs-Planning/",
                "local_path": str(NORMALIZED / "zebra_planbench_logic_candidates.jsonl"),
                "module_candidates": "A6",
                "status": "curated_method_snapshot",
                "notes": "Curated logic and state-tracking source pool for QB-v1.1, inspired by Zebra-style constraints and PlanBench planning/state tasks.",
            },
            {
                "source_name": "APPS / LiveCodeBench",
                "source_dataset": "benchmark-curated/apps-livecodebench-coding",
                "source_url": "https://github.com/hendrycks/apps",
                "local_path": str(NORMALIZED / "apps_livecodebench_coding_candidates.jsonl"),
                "module_candidates": "A2",
                "status": "curated_method_snapshot",
                "notes": "Curated high-difficulty coding source pool for QB-v1.1 synthesis and stateful data processing, inspired by APPS and LiveCodeBench.",
            },
            {
                "source_name": "BigCodeBench / EvalPlus / SWE-bench Lite",
                "source_dataset": "benchmark-curated/bigcode-evalplus-swebench",
                "source_url": "https://github.com/bigcode-project/bigcodebench",
                "local_path": str(NORMALIZED / "bigcode_evalplus_swebench_candidates.jsonl"),
                "module_candidates": "A2",
                "status": "curated_method_snapshot",
                "notes": "Curated high-difficulty coding source pool for QB-v1.1 long-code comprehension and patch reasoning, inspired by BigCodeBench, EvalPlus, HumanEval+, and SWE-bench Lite.",
            },
        ]
    )
    upsert_extraction_summary(summary_entries)
    upsert_source_registry(registry_entries)
    summary_path = NORMALIZED / "qbv11_candidate_build_summary.json"
    summary_path.write_text(json.dumps(summary_entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "sources_added": len(summary_entries), "summary_path": str(summary_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
