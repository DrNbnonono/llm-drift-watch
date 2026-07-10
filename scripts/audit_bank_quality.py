#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from question_bank_runtime import FINAL_BANK, load_jsonl


NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:%|\u2030)?(?![\w])")
SPACE_RE = re.compile(r"\s+")


def item_text(item: dict) -> str:
    prompt = item.get("prompt_template")
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    return "\n".join(
        str(turn.get("content_template") or "")
        for turn in (item.get("turn_script") or [])
        if turn.get("speaker") == "user"
    )


def template_signature(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = NUMBER_RE.sub("<num>", text)
    text = re.sub(r"[`*_#>|]", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def template_similarity(left: str, right: str) -> float:
    left_sig = template_signature(left)
    right_sig = template_signature(right)
    if not left_sig or not right_sig:
        return 0.0
    return SequenceMatcher(None, left_sig, right_sig, autojunk=False).ratio()


class DisjointSet:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            nxt = self.parent[value]
            self.parent[value] = root
            value = nxt
        return root

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def audit_items(items: list[dict], similarity_threshold: float = 0.88) -> dict:
    modules: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        modules[str(item.get("module") or "unknown")].append(item)

    module_reports = {}
    all_pairs = []
    for module, module_items in sorted(modules.items()):
        ids = [str(item["question_id"]) for item in module_items]
        dsu = DisjointSet(ids)
        signatures: dict[str, list[str]] = defaultdict(list)
        for item in module_items:
            signatures[template_signature(item_text(item))].append(item["question_id"])

        exact_template_groups = [group for group in signatures.values() if len(group) > 1]
        for group in exact_template_groups:
            for question_id in group[1:]:
                dsu.union(group[0], question_id)

        for left_index, left in enumerate(module_items):
            left_text = item_text(left)
            for right in module_items[left_index + 1 :]:
                similarity = template_similarity(left_text, item_text(right))
                if similarity < similarity_threshold:
                    continue
                pair = {
                    "module": module,
                    "left": left["question_id"],
                    "right": right["question_id"],
                    "similarity": round(similarity, 4),
                }
                all_pairs.append(pair)
                dsu.union(pair["left"], pair["right"])

        components: dict[str, list[str]] = defaultdict(list)
        for question_id in ids:
            components[dsu.find(question_id)].append(question_id)
        clusters = sorted(
            (sorted(group) for group in components.values() if len(group) > 1),
            key=lambda group: (-len(group), group[0]),
        )
        module_pairs = [pair for pair in all_pairs if pair["module"] == module]
        module_reports[module] = {
            "item_count": len(module_items),
            "unique_parameter_masked_templates": len(signatures),
            "exact_parameter_swap_group_count": len(exact_template_groups),
            "near_duplicate_pair_count": len(module_pairs),
            "near_duplicate_cluster_count": len(clusters),
            "largest_cluster_size": max((len(group) for group in clusters), default=1),
            "clusters": clusters[:20],
        }

    return {
        "item_count": len(items),
        "version_counts": dict(Counter(str(item.get("version")) for item in items)),
        "similarity_threshold": similarity_threshold,
        "near_duplicate_pair_count": len(all_pairs),
        "near_duplicate_cluster_count": sum(
            report["near_duplicate_cluster_count"] for report in module_reports.values()
        ),
        "modules": module_reports,
        "top_pairs": sorted(all_pairs, key=lambda pair: -pair["similarity"])[:100],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit exact, parameter-swap and near-duplicate bank items.")
    parser.add_argument(
        "--input",
        type=Path,
        default=FINAL_BANK / "generated" / "final_bank_items.jsonl",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threshold", type=float, default=0.88)
    parser.add_argument("--active-only", action="store_true", help="Audit only ready/frozen items.")
    parser.add_argument("--fail-on-near-duplicates", action="store_true")
    args = parser.parse_args()

    items = load_jsonl(args.input)
    if args.active_only:
        items = [item for item in items if item.get("qa_status", "ready") in {"ready", "frozen"}]
    report = audit_items(items, similarity_threshold=args.threshold)
    report["active_only"] = args.active_only
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if args.fail_on_near_duplicates and report["near_duplicate_pair_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
