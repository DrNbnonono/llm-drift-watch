#!/usr/bin/env python3
"""Build traceable source cards before any advanced-mathematics rewrite.

The cards deliberately retain the source problem, reference answer, and full
solution.  They are candidates only: formal QB items must link to a card and
must be independently rewritten rather than copied verbatim.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from question_bank_runtime import NORMALIZED, write_jsonl


MATH500_PATH = NORMALIZED / "math500_candidates.jsonl"
OUTPUT_PATH = NORMALIZED / "qbv13_advanced_math_source_cards.jsonl"
SOURCE_URL = "https://github.com/hendrycks/math"


def _load_math500() -> list[dict[str, Any]]:
    return [json.loads(line) for line in MATH500_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _taxonomy(prompt: str, solution: str) -> tuple[str, str]:
    text = f"{prompt}\n{solution}".lower()
    rules = (
        ("graph_theory", (" graph", "vertex", "vertices", " edge", "tree", "path", "coloring", "bipartite")),
        ("discrete_probability", ("probability", "random", "coin", "dice", "expected value", "distribution")),
        ("linear_algebra", ("matrix", "determinant", "eigen", "vector", "linear transformation")),
        ("number_theory", ("prime", "integer", "divis", "modulo", "remainder", "gcd", "congruen")),
        ("combinatorics", ("permutation", "combination", "arrange", "subset", "choose", "how many ways", "binomial")),
        ("abstract_algebra_intro", (" group", "ring", " field", "homomorphism", "coset")),
        ("recurrence_generating_functions", ("sequence", "recurrence", "generating function", "series")),
        ("geometry_analytic", ("triangle", "circle", "angle", "polygon", "coordinate", "rectangle", "radius")),
        ("inequality_optimization", ("inequality", "minimum", "maximum", "minimize", "maximize", "least value", "greatest value")),
    )
    for domain, markers in rules:
        evidence = [marker.strip() for marker in markers if marker in text]
        if evidence:
            return domain, ", ".join(evidence[:3])
    return "advanced_algebra", "algebraic expression or equation"


def _rank_key(candidate: dict[str, Any]) -> tuple[int, str]:
    solution = str((candidate.get("source_metadata") or {}).get("reference_solution") or "")
    digest = hashlib.sha256(str(candidate["candidate_id"]).encode("utf-8")).hexdigest()
    # Longer worked solutions generally retain a nontrivial proof mechanism.
    return (-len(solution), digest)


def _to_card(candidate: dict[str, Any], pool: str, index: int) -> dict[str, Any]:
    source_metadata = dict(candidate.get("source_metadata") or {})
    solution = str(source_metadata.get("reference_solution") or candidate.get("answer") or "")
    domain, evidence = _taxonomy(str(candidate["prompt"]), solution)
    return {
        "card_id": f"A1-S{'H' if pool == 'formal' else 'R'}{index:03d}",
        "pool": pool,
        "source": {
            "name": "MATH-500 / Hendrycks MATH",
            "dataset": candidate["source_dataset"],
            "split": candidate["source_split"],
            "url": SOURCE_URL,
            "license_note": "The dataset repository is MIT-licensed; this card retains provenance and formal QB items must not copy the source wording.",
        },
        "source_item": {
            "candidate_id": candidate["candidate_id"],
            "original_id": candidate["original_id"],
            "prompt": candidate["prompt"],
            "answer": str(candidate["answer"]),
            "reference_solution": solution,
        },
        "knowledge_taxonomy": {
            "domain": domain,
            "evidence": evidence,
            "mechanism_status": "requires human source-card review before formal rewrite",
        },
        "item_shape": {
            "source_task_family": candidate["task_family"],
            "answer_mode": "symbolic_or_numeric",
            "requires_derivation": True,
        },
        "formalization": {
            "direct_public_reuse": False,
            "rewrite_required": True,
            "required_changes": ["change mathematical construction", "recompute answer independently", "preserve only the audited proof mechanism"],
            "status": "source_card_ready",
        },
    }


def build_source_cards() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = sorted(_load_math500(), key=_rank_key)
    if len(candidates) < 400:
        raise ValueError("MATH-500 candidate snapshot must contain at least 400 source problems")
    formal = [_to_card(candidate, "formal", index) for index, candidate in enumerate(candidates[:240], start=1)]
    reserve = [_to_card(candidate, "reserve", index) for index, candidate in enumerate(candidates[240:400], start=1)]
    return formal, reserve


def main() -> None:
    formal, reserve = build_source_cards()
    write_jsonl(OUTPUT_PATH, [*formal, *reserve])
    print(json.dumps({"output": str(OUTPUT_PATH), "formal": len(formal), "reserve": len(reserve)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
