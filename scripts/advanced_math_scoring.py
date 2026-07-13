#!/usr/bin/env python3

from __future__ import annotations

import ast
import math
import re
from fractions import Fraction
from typing import Any


def extract_answer_payload(text: str) -> str:
    matches = re.findall(r"答案\s*[:：]\s*(.+)", text, flags=re.I)
    if matches:
        return matches[-1].strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def parse_reduced_fraction(payload: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"(-?\d+)\s*/\s*(-?\d+)", payload.strip())
    if not match:
        return None
    numerator, denominator = (int(value) for value in match.groups())
    if denominator <= 0 or math.gcd(numerator, denominator) != 1:
        return None
    return numerator, denominator


def _parse_set(payload: str, universe: list[str] | None = None) -> list[str] | None:
    value = payload.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return None
    elements = [element.strip() for element in value[1:-1].split(",") if element.strip()]
    if len(elements) != len(set(elements)):
        return None
    if universe is not None and not set(elements) <= set(universe):
        return None
    return sorted(elements)


def _parse_matrix(payload: str) -> list[list[int]] | None:
    try:
        value = ast.literal_eval(payload.strip())
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, list) or not value or not all(isinstance(row, list) and row for row in value):
        return None
    width = len(value[0])
    if any(len(row) != width or any(not isinstance(entry, int) for entry in row) for row in value):
        return None
    return value


def score_advanced_math(text: str, params: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    answer_format = str(params.get("format") or "")
    canonical = params.get("canonical_answer")
    payload = extract_answer_payload(text)
    details: dict[str, Any] = {"format": answer_format, "payload": payload, "canonical": canonical}

    if answer_format == "integer":
        correct = bool(re.fullmatch(r"-?\d+", payload)) and int(payload) == int(canonical)
    elif answer_format == "reduced_fraction":
        predicted = parse_reduced_fraction(payload)
        expected = parse_reduced_fraction(str(canonical))
        correct = predicted is not None and expected is not None and predicted == expected
    elif answer_format == "mod_class":
        match = re.fullmatch(r"(-?\d+)\s*\(mod\s*(\d+)\)", payload, flags=re.I)
        expected = params.get("modulus")
        correct = bool(match and expected is not None and int(match.group(2)) == int(expected) and int(match.group(1)) % int(expected) == int(canonical) % int(expected))
    elif answer_format in {"finite_set", "vertex_set"}:
        predicted = _parse_set(payload, params.get("universe") if answer_format == "vertex_set" else None)
        correct = predicted is not None and predicted == sorted(str(value) for value in canonical)
    elif answer_format == "matrix":
        predicted = _parse_matrix(payload)
        correct = predicted is not None and predicted == canonical
    elif answer_format == "ordered_tuple":
        try:
            predicted = ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            predicted = None
        correct = isinstance(predicted, tuple) and list(predicted) == list(canonical)
    elif answer_format == "boolean":
        normalized = payload.lower()
        correct = normalized in {"true", "false"} and normalized == str(canonical).lower()
    else:
        details["error"] = "unsupported_answer_format"
        return 0.0, details
    details["correct"] = bool(correct)
    return (1.0 if correct else 0.0), details
