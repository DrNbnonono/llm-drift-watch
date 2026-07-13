#!/usr/bin/env python3

from __future__ import annotations

import heapq
import math
import random
from collections import Counter
from fractions import Fraction
from typing import Any


VERSION = "QB-v1.3"

TOPIC_QUOTAS = {
    "advanced_algebra": 30,
    "inequality_optimization": 22,
    "number_theory": 24,
    "combinatorics": 24,
    "discrete_probability": 28,
    "graph_theory": 24,
    "linear_algebra": 24,
    "recurrence_generating_functions": 18,
    "geometry_analytic": 16,
    "algorithms_discrete_optimization": 12,
    "abstract_algebra_intro": 10,
    "information_coding": 8,
}

RESERVE_TOPIC_QUOTAS = {
    "advanced_algebra": 20,
    "inequality_optimization": 14,
    "number_theory": 16,
    "combinatorics": 16,
    "discrete_probability": 19,
    "graph_theory": 16,
    "linear_algebra": 16,
    "recurrence_generating_functions": 12,
    "geometry_analytic": 11,
    "algorithms_discrete_optimization": 8,
    "abstract_algebra_intro": 7,
    "information_coding": 5,
}

FORMAL_TIERS = {"foundation": 20, "advanced_hs": 60, "olympiad": 80, "undergraduate": 60, "stretch": 20}
RESERVE_TIERS = {"foundation": 14, "advanced_hs": 40, "olympiad": 52, "undergraduate": 40, "stretch": 14}

FRAMINGS = (
    "请完整推导；最后一行严格写作 `答案：[结果]`。",
    "不得借助数值近似。写出关键论证后，在末行给出 `答案：[结果]`。",
    "请先识别可用的不变量或结构，再在最后一行写 `答案：[结果]`。",
    "需要说明关键分支或边界；最终输出格式为 `答案：[结果]`。",
    "请给出可核查的中间关系式，最后一行仅保留 `答案：[结果]`。",
    "注意不要把相关性误当独立性；最后一行写 `答案：[结果]`。",
)


def _tier_stream(quotas: dict[str, int], seed: int) -> list[str]:
    values = [tier for tier, count in quotas.items() for _ in range(count)]
    random.Random(seed).shuffle(values)
    return values


def _tier_steps(tier: str) -> int:
    return {"foundation": 2, "advanced_hs": 3, "olympiad": 3, "undergraduate": 4, "stretch": 5}[tier]


def _det3(matrix: list[list[int]]) -> int:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _shortest_path(edges: list[tuple[str, str, int]], start: str, target: str) -> int:
    graph: dict[str, list[tuple[str, int]]] = {}
    for left, right, weight in edges:
        graph.setdefault(left, []).append((right, weight))
        graph.setdefault(right, []).append((left, weight))
    queue = [(0, start)]
    distances = {start: 0}
    while queue:
        distance, node = heapq.heappop(queue)
        if node == target:
            return distance
        if distance != distances[node]:
            continue
        for child, weight in graph[node]:
            proposal = distance + weight
            if proposal < distances.get(child, 10**9):
                distances[child] = proposal
                heapq.heappush(queue, (proposal, child))
    raise ValueError("disconnected graph")


def recompute_answer(blueprint: dict[str, Any]) -> str:
    family = blueprint["family"]
    values = blueprint["values"]
    if family == "polynomial_value":
        answer = sum(coefficient * values["x"] ** power for power, coefficient in enumerate(values["coefficients"]))
    elif family == "quadratic_extremum":
        answer = Fraction(4 * values["a"] * values["c"] - values["b"] ** 2, 4 * values["a"])
    elif family == "crt":
        answer = next(number for number in range(1, math.prod(values["moduli"]) + 1) if all(number % modulus == residue for modulus, residue in zip(values["moduli"], values["residues"])))
    elif family == "modular_power":
        answer = pow(values["base"], values["exponent"], values["modulus"])
    elif family == "linear_diophantine_count":
        answer = sum(1 for x in range(values["total"] // values["a"] + 1) if (values["total"] - values["a"] * x) >= 0 and (values["total"] - values["a"] * x) % values["b"] == 0)
    elif family == "binomial_count":
        answer = math.comb(values["n"], values["k"])
    elif family == "derangement":
        answer = round(math.factorial(values["n"]) * sum(Fraction((-1) ** index, math.factorial(index)) for index in range(values["n"] + 1)))
    elif family == "restricted_binary":
        answer = math.comb(values["n"] - values["ones"] + 1, values["ones"])
    elif family == "hypergeometric_probability":
        answer = Fraction(math.comb(values["good"], values["draw_good"]) * math.comb(values["bad"], values["draw"] - values["draw_good"]), math.comb(values["good"] + values["bad"], values["draw"]))
    elif family == "conditional_coin_probability":
        answer = Fraction(values["favorable"], values["conditioned"])
    elif family == "expected_without_replacement":
        answer = Fraction(values["draw"] * values["good"], values["total"])
    elif family == "graph_shortest_path":
        answer = _shortest_path([tuple(edge) for edge in values["edges"]], values["start"], values["target"])
    elif family == "tree_count":
        answer = values["n"] ** (values["n"] - 2)
    elif family == "bipartite_edges":
        answer = values["left"] * values["right"]
    elif family == "matrix_determinant":
        answer = _det3(values["matrix"])
    elif family == "vandermonde_det":
        points = values["points"]
        answer = math.prod(points[right] - points[left] for left in range(len(points)) for right in range(left + 1, len(points)))
    elif family == "linear_recurrence":
        current, following = values["initial"]
        for _ in range(2, values["index"]):
            current, following = following, values["p"] * following + values["q"] * current
        answer = current if values["index"] == 1 else following
    elif family == "binomial_coefficient":
        answer = math.comb(values["n"], values["k"])
    elif family == "shoelace_area_twice":
        points = values["points"]
        answer = abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[index][1] * points[(index + 1) % len(points)][0] for index in range(len(points))))
    elif family == "vector_dot":
        answer = sum(left * right for left, right in zip(values["left"], values["right"]))
    elif family == "knapsack_value":
        capacity = values["capacity"]
        dp = [0] * (capacity + 1)
        for weight, value in values["items"]:
            for current in range(capacity, weight - 1, -1):
                dp[current] = max(dp[current], dp[current - weight] + value)
        answer = dp[capacity]
    elif family == "max_flow_cut":
        answer = sum(values["cut_capacities"])
    elif family == "unit_group_size":
        answer = sum(math.gcd(number, values["modulus"]) == 1 for number in range(1, values["modulus"] + 1))
    elif family == "polynomial_roots_mod_prime":
        answer = sum((number * number + values["b"] * number + values["c"]) % values["prime"] == 0 for number in range(values["prime"]))
    elif family == "hamming_ball_size":
        answer = sum(math.comb(values["length"], index) for index in range(values["radius"] + 1))
    elif family == "huffman_weighted_length":
        answer = sum(weight * length for weight, length in values["symbols"])
    else:
        raise ValueError(f"unknown math blueprint family: {family}")
    if isinstance(answer, Fraction):
        return str(answer.numerator) if answer.denominator == 1 else f"{answer.numerator}/{answer.denominator}"
    return str(answer)


def _family_blueprint(subtype: str, ordinal: int) -> tuple[dict[str, Any], str, list[str], str, list[str]]:
    n = ordinal + 4
    if subtype == "advanced_algebra":
        if ordinal % 3 == 0:
            coefficients = [ordinal - 7, 2 * ordinal + 3, -ordinal - 2, 1]
            x = ordinal % 7 - 3
            return ({"family": "polynomial_value", "values": {"coefficients": coefficients, "x": x}}, f"设 P(x)={coefficients[3]}x^3+({coefficients[2]})x^2+({coefficients[1]})x+({coefficients[0]})。求 P({x})。", ["polynomial_evaluation", "signed_arithmetic"], "polynomial_structure", ["sign_error", "coefficient_order"])
        a, b, c = n, 2 * n - 3, n * n + 5
        return ({"family": "quadratic_extremum", "values": {"a": a, "b": b, "c": c}}, f"在实数范围内，二次函数 f(x)={a}x²+({b})x+({c}) 的最小值是多少？结果化为最简分数。", ["quadratic_completion", "rational_arithmetic"], "quadratic_optimization", ["vertex_sign", "not_reducing_fraction"])
    if subtype == "inequality_optimization":
        a, b, c = n + 2, -2 * n, n * n + 3
        return ({"family": "quadratic_extremum", "values": {"a": a, "b": b, "c": c}}, f"设 x 为实数。求 {a}x²-({2*n})x+{c} 的全局最小值，并将答案写成最简分数。", ["convex_quadratic", "completing_square"], "convex_optimization", ["wrong_extremum", "integer_rounding"])
    if subtype == "number_theory":
        variant = ordinal % 3
        if variant == 0:
            moduli = [5, 7, 9]
            residues = [(ordinal + 1) % 5, (ordinal + 2) % 7, (ordinal + 4) % 9]
            return ({"family": "crt", "values": {"moduli": moduli, "residues": residues}}, f"求满足 x≡{residues[0]} (mod 5)、x≡{residues[1]} (mod 7)、x≡{residues[2]} (mod 9) 的最小正整数 x。", ["chinese_remainder_theorem", "modular_arithmetic"], "crt_system", ["wrong_modulus_product", "nonminimal_solution"])
        if variant == 1:
            modulus = [97, 101, 103][ordinal % 3]
            return ({"family": "modular_power", "values": {"base": 7 + ordinal % 11, "exponent": 37 + ordinal, "modulus": modulus}}, f"计算 ({7 + ordinal % 11})^({37 + ordinal}) 在模 {modulus} 下的最小非负剩余。", ["fast_exponentiation", "fermat_little_theorem"], "modular_exponentiation", ["overflow_reasoning", "wrong_reduction"])
        return ({"family": "linear_diophantine_count", "values": {"a": 4 + ordinal % 5, "b": 7 + ordinal % 6, "total": 90 + 3 * ordinal}}, f"求非负整数解 (x,y) 的个数：{4 + ordinal % 5}x+{7 + ordinal % 6}y={90 + 3 * ordinal}。", ["linear_diophantine_equation", "congruence"], "diophantine_count", ["negative_solution", "missed_congruence_class"])
    if subtype == "combinatorics":
        variant = ordinal % 3
        if variant == 0:
            return ({"family": "derangement", "values": {"n": 5 + ordinal % 5}}, f"将 {5 + ordinal % 5} 个不同对象随机放入对应的 {5 + ordinal % 5} 个位置。恰好没有对象处于原位置的排列数是多少？", ["inclusion_exclusion", "derangement"], "permutation_inclusion_exclusion", ["missing_alternating_sign", "using_n_factorial"])
        if variant == 1:
            return ({"family": "restricted_binary", "values": {"n": 12 + ordinal % 8, "ones": 3 + ordinal % 4}}, f"长度为 {12 + ordinal % 8} 的二进制串恰有 {3 + ordinal % 4} 个 1，且任意两个 1 不相邻。这样的串有多少个？", ["gap_method", "binomial_coefficient"], "nonadjacent_selection", ["off_by_one_gap", "ignoring_adjacency"])
        return ({"family": "binomial_count", "values": {"n": 14 + ordinal % 10, "k": 4 + ordinal % 5}}, f"从 {14 + ordinal % 10} 个互异元素中选出 {4 + ordinal % 5} 个组成子集，子集数是多少？", ["combinations"], "finite_set_count", ["permutation_vs_combination"])
    if subtype == "discrete_probability":
        variant = ordinal % 3
        if variant == 0:
            good, bad, draw = 7 + ordinal % 5, 9 + ordinal % 6, 4
            take = 2
            return ({"family": "hypergeometric_probability", "values": {"good": good, "bad": bad, "draw": draw, "draw_good": take}}, f"袋中有 {good} 个红球和 {bad} 个蓝球，不放回抽取 {draw} 个。恰好抽到 {take} 个红球的概率是多少？化为最简分数。", ["hypergeometric_distribution", "combinations"], "dependent_sampling_probability", ["using_binomial_model", "not_reducing_fraction"])
        if variant == 1:
            total, good, draw = 20 + ordinal % 9, 6 + ordinal % 7, 5
            return ({"family": "expected_without_replacement", "values": {"total": total, "good": good, "draw": draw}}, f"共有 {total} 个对象，其中 {good} 个带有性质 P。不放回随机抽取 {draw} 个，带有性质 P 的对象数量的期望是多少？化为最简分数。", ["linearity_of_expectation", "hypergeometric_expectation"], "expectation_without_replacement", ["assuming_independence", "integer_rounding"])
        favorable, conditioned = 3 + ordinal % 7, 11 + ordinal % 9
        return ({"family": "conditional_coin_probability", "values": {"favorable": favorable, "conditioned": conditioned}}, f"一个有限概率空间在事件 B 已发生时共有 {conditioned} 个等可能条件结果，其中 {favorable} 个同时满足事件 A。求 P(A|B)，写成最简分数。", ["conditional_probability"], "conditional_sample_space", ["wrong_denominator", "unreduced_fraction"])
    if subtype == "graph_theory":
        variant = ordinal % 3
        if variant == 0:
            edges = [["s", "a", 2 + ordinal % 3], ["s", "b", 5], ["a", "b", 1 + ordinal % 2], ["a", "t", 7], ["b", "t", 2 + ordinal % 4]]
            return ({"family": "graph_shortest_path", "values": {"edges": edges, "start": "s", "target": "t"}}, f"无向加权图的边为 {edges}（三元组为端点与权重）。求从 s 到 t 的最短路长度。", ["dijkstra", "path_relaxation"], "weighted_shortest_path", ["greedy_local_choice", "missing_intermediate_edge"])
        if variant == 1:
            vertices = 5 + ordinal % 8
            return ({"family": "tree_count", "values": {"n": vertices}}, f"带标号顶点集 {{1,…,{vertices}}} 上共有多少棵不同的树？", ["prufer_code", "cayley_formula"], "labeled_tree_enumeration", ["confusing_labeled_unlabeled", "wrong_exponent"])
        left, right = 5 + ordinal % 6, 6 + (ordinal * 2) % 7
        return ({"family": "bipartite_edges", "values": {"left": left, "right": right}}, f"完全二部图 K_{{{left},{right}}} 有多少条边？", ["bipartite_graphs"], "complete_bipartite_structure", ["using_choose_two"])
    if subtype == "linear_algebra":
        if ordinal % 2 == 0:
            matrix = [[ordinal + 2, 1, -1], [2, ordinal % 5 - 2, 3], [1, -2, ordinal + 1]]
            return ({"family": "matrix_determinant", "values": {"matrix": matrix}}, f"计算矩阵 {matrix} 的行列式。", ["determinant", "cofactor_expansion"], "three_by_three_determinant", ["cofactor_sign", "row_operation_factor"])
        points = [1 + ordinal % 3, 4 + ordinal % 5, 9 + ordinal % 7]
        points = sorted(set(points))
        while len(points) < 3:
            points.append(points[-1] + 3)
        return ({"family": "vandermonde_det", "values": {"points": points}}, f"设 V 是由节点 {points} 构成的 3×3 Vandermonde 矩阵，V 的第 i 行为 [1,xᵢ,xᵢ²]。求 det(V)。", ["vandermonde_determinant", "alternating_product"], "vandermonde_structure", ["reversed_difference_sign", "duplicate_node"])
    if subtype == "recurrence_generating_functions":
        p, q = 1 + ordinal % 3, 1 + (ordinal + 1) % 3
        initial = [1 + ordinal % 4, 2 + ordinal % 5]
        index = 7 + ordinal % 8
        return ({"family": "linear_recurrence", "values": {"p": p, "q": q, "initial": initial, "index": index}}, f"数列满足 a₁={initial[0]}，a₂={initial[1]}，且 aₙ₊₂={p}aₙ₊₁+{q}aₙ。求 a_{index}。", ["linear_recurrence", "characteristic_polynomial"], "second_order_recurrence", ["index_shift", "wrong_initial_state"])
    if subtype == "geometry_analytic":
        if ordinal % 2 == 0:
            points = [(0, 0), (4 + ordinal % 5, 0), (5 + ordinal % 4, 3 + ordinal % 5), (1, 4 + ordinal % 4)]
            return ({"family": "shoelace_area_twice", "values": {"points": points}}, f"按给定顺序连接点 {points} 得到简单四边形。其面积的两倍是多少？", ["shoelace_formula", "oriented_area"], "polygon_area", ["vertex_order", "missing_absolute_value"])
        left, right = [ordinal + 1, 2 - ordinal % 5, 3], [2, ordinal % 7 - 3, 4]
        return ({"family": "vector_dot", "values": {"left": left, "right": right}}, f"在 R³ 中，向量 u={left}，v={right}。求内积 u·v。", ["dot_product", "coordinate_geometry"], "vector_inner_product", ["componentwise_sum", "sign_error"])
    if subtype == "algorithms_discrete_optimization":
        if ordinal % 2 == 0:
            items = [(2, 5 + ordinal % 5), (3, 7 + ordinal % 7), (4, 9 + ordinal % 9), (5, 11 + ordinal % 11)]
            capacity = 7 + ordinal % 5
            return ({"family": "knapsack_value", "values": {"items": items, "capacity": capacity}}, f"0-1 背包容量为 {capacity}。物品 (重量,价值) 为 {items}。可取得的最大总价值是多少？", ["dynamic_programming", "combinatorial_optimization"], "zero_one_knapsack", ["fractional_knapsack", "capacity_overflow"])
        cut = [3 + ordinal % 4, 5 + ordinal % 5, 7 + ordinal % 3]
        return ({"family": "max_flow_cut", "values": {"cut_capacities": cut}}, f"一个 s-t 网络给定一条已验证的最小割，其跨割边容量依次为 {cut}。依据最大流最小割定理，最大流值是多少？", ["max_flow_min_cut"], "network_flow_certificate", ["taking_max_edge", "wrong_cut_sum"])
    if subtype == "abstract_algebra_intro":
        if ordinal % 2 == 0:
            modulus = [15, 16, 18, 20, 21, 24][ordinal % 6]
            return ({"family": "unit_group_size", "values": {"modulus": modulus}}, f"乘法群 (Z/{modulus}Z)^× 的元素个数是多少？", ["euler_totient", "unit_group"], "finite_unit_group", ["including_zero", "counting_nonunits"])
        prime = [5, 7, 11, 13][ordinal % 4]
        b, c = ordinal % prime, (ordinal * ordinal + 1) % prime
        return ({"family": "polynomial_roots_mod_prime", "values": {"prime": prime, "b": b, "c": c}}, f"在有限域 F_{prime} 中，多项式 x²+({b})x+({c}) 有多少个根？", ["finite_fields", "quadratic_residues"], "finite_field_root_count", ["real_discriminant", "forgetting_modular_reduction"])
    if subtype == "information_coding":
        if ordinal % 2 == 0:
            return ({"family": "hamming_ball_size", "values": {"length": 8 + ordinal % 5, "radius": 2}}, f"长度为 {8 + ordinal % 5} 的二进制串中，与固定串 Hamming 距离至多为 2 的串有多少个？", ["hamming_distance", "binomial_sum"], "hamming_ball_count", ["ordered_flips", "missing_radius_zero"])
        symbols = [(1 + ordinal % 4, 2), (2 + ordinal % 5, 3), (3 + ordinal % 6, 4), (4 + ordinal % 7, 4)]
        return ({"family": "huffman_weighted_length", "values": {"symbols": symbols}}, f"一个前缀码中，符号的 (频数,码长) 为 {symbols}。该码对该频数的总加权码长是多少？", ["prefix_codes", "weighted_path_length"], "coding_weighted_length", ["unweighted_average", "frequency_length_swap"])
    raise ValueError(f"unknown subtype: {subtype}")


def _make_item(question_id: str, pool: str, subtype: str, tier: str, ordinal: int) -> dict[str, Any]:
    blueprint, prompt, prerequisites, family, traps = _family_blueprint(subtype, ordinal)
    answer = recompute_answer(blueprint)
    answer_format = "reduced_fraction" if "/" in answer else "integer"
    source_id = f"internal-advanced-math-{question_id.lower()}"
    return {
        "question_id": question_id,
        "version": VERSION,
        "module": "A1",
        "subtype": subtype,
        "item_format": "single_turn",
        "difficulty": "medium" if tier == "foundation" else "hard",
        "difficulty_tier": tier,
        "drift_role": "capability",
        "prompt_template": f"{prompt}\n{FRAMINGS[ordinal % len(FRAMINGS)]}",
        "turn_script": None,
        "ground_truth": answer,
        "scoring_method": "advanced_math",
        "scoring_params": {"format": answer_format, "canonical_answer": answer},
        "answer_contract": {"format": answer_format, "canonical_answer": answer, "accepted_equivalents": [answer]},
        "module_quota_tag": f"advanced_math_{subtype}",
        "qa_status": "ready" if pool == "formal" else "frozen",
        "rotation_policy": {"replaceable": True, "rotation_priority": 1, "expected_lifespan_days": 180},
        "provenance": {
            "rewrite_ids": [f"rw-{question_id.lower()}"],
            "source_candidate_ids": [source_id],
            "transformation_summary": "Original advanced mathematics item synthesized from an internal, independently verifiable blueprint.",
        },
        "prerequisites": prerequisites,
        "reasoning_profile": {
            "minimum_nontrivial_steps": _tier_steps(tier),
            "primary_method": family,
            "secondary_methods": prerequisites[1:],
            "common_traps": traps,
        },
        "discrimination_profile": {
            "item_family": family,
            "variant_type": "cross_concept" if len(prerequisites) > 1 else "concept_disambiguation",
            "target_error_modes": traps,
        },
        "math_blueprint": blueprint,
        "notes": "quality_track=advanced_math; direct_public_reuse=false; review_status=generated",
    }


def _build_pool(pool: str, topic_quotas: dict[str, int], tier_quotas: dict[str, int], prefix: str, seed: int) -> list[dict[str, Any]]:
    tiers = _tier_stream(tier_quotas, seed)
    items: list[dict[str, Any]] = []
    index = 1
    for subtype, count in topic_quotas.items():
        for ordinal in range(count):
            items.append(_make_item(f"A1-{prefix}{index:03d}", pool, subtype, tiers[index - 1], ordinal + (100 if pool == "reserve" else 0)))
            index += 1
    return items


def build_advanced_math_bank() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    formal = _build_pool("formal", TOPIC_QUOTAS, FORMAL_TIERS, "H", 1307)
    reserve = _build_pool("reserve", RESERVE_TOPIC_QUOTAS, RESERVE_TIERS, "R", 2027)
    if Counter(item["difficulty_tier"] for item in formal) != Counter(FORMAL_TIERS):
        raise ValueError("formal difficulty quota mismatch")
    if Counter(item["difficulty_tier"] for item in reserve) != Counter(RESERVE_TIERS):
        raise ValueError("reserve difficulty quota mismatch")
    return formal, reserve
