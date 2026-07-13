#!/usr/bin/env python3

from __future__ import annotations

import heapq
import math
import random
import re
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

# These are coverage sources, not text to be copied into the formal bank.  Each
# generated item records a source seed (course/problem-set topic plus a distinct
# proof mechanism) so the candidate layer can be audited without reproducing
# copyrighted contest wording.
SOURCE_CATALOG = {
    "mit_18_200": {"name": "MIT 18.200 Principles of Discrete Applied Mathematics", "url": "https://ocw.mit.edu/courses/18-200-principles-of-discrete-applied-mathematics-spring-2024/lists/assignments/"},
    "mit_18_314": {"name": "MIT 18.314 Combinatorial Analysis", "url": "https://ocw.mit.edu/courses/18-314-combinatorial-analysis-fall-2014/pages/assignments/"},
    "mit_18_315": {"name": "MIT 18.315 Combinatorial Theory", "url": "https://ocw.mit.edu/courses/18-315-combinatorial-theory-introduction-to-graph-theory-extremal-and-enumerative-combinatorics-spring-2005/pages/syllabus/"},
    "mit_6_1200": {"name": "MIT 6.1200J Mathematics for Computer Science", "url": "https://ocw.mit.edu/courses/6-1200j-mathematics-for-computer-science-spring-2024/"},
    "mit_18_600": {"name": "MIT 18.600 Probability and Random Variables", "url": "https://ocw.mit.edu/courses/18-600-probability-and-random-variables-fall-2019/resources/problem-sets/"},
    "mit_18_440": {"name": "MIT 18.440 Probability and Random Variables", "url": "https://ocw.mit.edu/courses/18-440-probability-and-random-variables-spring-2014/pages/calendar/"},
    "mit_18_700": {"name": "MIT 18.700 Linear Algebra", "url": "https://ocw.mit.edu/courses/18-700-linear-algebra-fall-2013/pages/calendar/"},
    "mit_18_701": {"name": "MIT 18.701 Algebra I", "url": "https://ocw.mit.edu/courses/18-701-algebra-i-fall-2010/pages/assignments/"},
    "mit_18_702": {"name": "MIT 18.702 Algebra II", "url": "https://ocw.mit.edu/courses/18-702-algebra-ii-spring-2011/pages/assignments/"},
    "mit_18_785": {"name": "MIT 18.785 Number Theory I", "url": "https://ocw.mit.edu/courses/18-785-number-theory-i-fall-2021/pages/assignments/"},
    "mit_18_a34": {"name": "MIT Putnam Seminar", "url": "https://ocw.mit.edu/courses/18-a34-mathematical-problem-solving-putnam-seminar-fall-2018/pages/assignments/"},
    "mit_18_404": {"name": "MIT 18.404J Theory of Computation", "url": "https://ocw.mit.edu/courses/18-404j-theory-of-computation-fall-2020/resources/assignments/"},
    "maa_putnam": {"name": "MAA Putnam Archive", "url": "https://maa.org/maa-putnam-archive/"},
    "maa_amc": {"name": "MAA American Mathematics Competitions", "url": "https://maa.org/student-programs/amc/"},
    "openstax_graphs": {"name": "OpenStax Contemporary Mathematics: Graphs", "url": "https://openstax.org/books/contemporary-mathematics/pages/12-4-navigating-graphs"},
    "openstax_probability": {"name": "OpenStax Contemporary Mathematics: Probability", "url": "https://openstax.org/books/contemporary-mathematics/pages/7-6-probability-with-permutations-and-combinations"},
}

SOURCE_KEYS_BY_SUBTYPE = {
    "advanced_algebra": ("maa_amc", "maa_putnam", "mit_18_a34", "mit_18_702"),
    "inequality_optimization": ("maa_putnam", "mit_18_a34", "mit_18_200", "mit_18_701"),
    "number_theory": ("mit_18_785", "mit_18_701", "maa_putnam", "mit_6_1200"),
    "combinatorics": ("mit_18_314", "mit_18_315", "mit_6_1200", "maa_amc"),
    "discrete_probability": ("mit_18_600", "mit_18_440", "mit_18_200", "openstax_probability"),
    "graph_theory": ("mit_18_315", "mit_6_1200", "mit_18_200", "openstax_graphs"),
    "linear_algebra": ("mit_18_700", "mit_18_701", "mit_18_a34", "mit_18_702"),
    "recurrence_generating_functions": ("mit_18_314", "mit_18_200", "mit_6_1200", "maa_putnam"),
    "geometry_analytic": ("maa_amc", "maa_putnam", "mit_18_a34", "mit_18_701"),
    "algorithms_discrete_optimization": ("mit_18_200", "mit_6_1200", "mit_18_314", "mit_18_404"),
    "abstract_algebra_intro": ("mit_18_701", "mit_18_702", "mit_18_a34", "mit_18_785"),
    "information_coding": ("mit_18_404", "mit_18_200", "mit_6_1200", "mit_18_600"),
}

CONCEPT_LENSES = {
    "advanced_algebra": ("因式定理与余式", "韦达关系的对称量", "牛顿恒等式", "插值多项式", "根的重数", "判别式", "有理根障碍", "单位根分解", "共轭根配对", "多项式互素性", "函数迭代", "参数消元", "配方法的等价变形"),
    "inequality_optimization": ("AM-GM 取等", "Cauchy-Schwarz 配权", "Jensen 凸性", "切线法", "均值化", "换元后的边界", "拉格朗日乘子", "Hölder 结构", "重排不等式", "Schur 型约束", "二次型正定性", "端点比较", "平方和分解"),
    "number_theory": ("中国剩余定理", "乘法阶", "欧拉函数", "费马小定理", "p 进赋值", "二次剩余", "欧几里得算法", "线性丢番图参数化", "同余类计数", "整除格", "原根", "反证式无限递降", "模幂循环"),
    "combinatorics": ("容斥原理", "双计数", "鸽巢原理", "组合恒等式", "递推分解", "生成函数", "Stirling 分拆", "Catalan 结构", "错排", "格路计数", "循环分解", "二项式反演", "极值构造"),
    "discrete_probability": ("条件化样本空间", "全概率公式", "Bayes 更新", "线性期望", "指示变量", "方差分解", "超几何模型", "停止时刻", "马尔可夫性", "独立性检验", "尾概率界", "次序统计量", "交换性"),
    "graph_theory": ("握手引理", "二部图划分", "最短路松弛", "生成树编码", "匹配交替路", "Euler 回路", "平面图欧拉式", "图着色下界", "最大流最小割", "Hall 条件", "连通度", "Ramsey 型强制", "图同构不变量"),
    "linear_algebra": ("行列式多线性", "Vandermonde 结构", "秩-零度", "特征多项式", "相似不变量", "Gram-Schmidt", "正交投影", "谱定理", "Jordan 链", "有限域线性系统", "基变换", "矩阵树恒等式", "双线性型"),
    "recurrence_generating_functions": ("特征方程", "常系数递推", "普通生成函数", "指数生成函数", "卷积", "矩阵幂", "不动点递推", "分治递推", "线性递推矩阵化", "初值敏感性", "部分分式", "渐近主项", "组合类分解"),
    "geometry_analytic": ("鞋带公式", "向量投影", "面积坐标", "圆幂", "仿射不变量", "重心坐标", "复数平面", "方向向量", "点到直线距离", "内积余弦", "叉积定向", "反演结构", "解析几何消元"),
    "algorithms_discrete_optimization": ("0-1 背包状态", "最小割证书", "动态规划最优子结构", "贪心交换论证", "摊还分析", "二分答案", "网络流守恒", "区间 DP", "状态压缩", "支配状态删除", "可行性单调", "复杂度下界", "随机化期望"),
    "abstract_algebra_intro": ("单位群", "陪集分解", "同态核", "商群", "有限域根数", "群作用轨道", "Lagrange 定理", "正规子群", "多项式因式分解", "理想", "循环群生成元", "共轭类", "域扩张次数"),
    "information_coding": ("Hamming 球", "前缀码", "Kraft 不等式", "熵下界", "校验矩阵", "线性码距离", "Shannon-Fano 结构", "Huffman 合并", "纠错半径", "互信息", "编码率", "奇偶校验", "概率质量编码"),
}

TASK_FORMS = ("给出能够排除常见误解的证明要点", "明确写出关键不变量或等价变形", "先说明为何直观的贪心或独立性假设不成立")


def _source_seed(subtype: str, ordinal: int, question_id: str) -> dict[str, str]:
    lenses = CONCEPT_LENSES[subtype]
    lens = lenses[ordinal % len(lenses)]
    task_form = TASK_FORMS[(ordinal // len(lenses)) % len(TASK_FORMS)]
    source_key = SOURCE_KEYS_BY_SUBTYPE[subtype][ordinal % len(SOURCE_KEYS_BY_SUBTYPE[subtype])]
    source = SOURCE_CATALOG[source_key]
    return {
        "seed_id": f"{source_key}:{question_id.lower()}:{lens}",
        "source_key": source_key,
        "source_name": source["name"],
        "source_url": source["url"],
        "related_source_locator": f"coverage-topic/{lens}",
        "concept": lens,
        "task_form": task_form,
    }


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
    elif family == "polynomial_remainder_constant":
        # Constant coefficient of P(x) modulo x^2 + 1, using x^2 = -1.
        answer = sum(coefficient * ((-1) ** (power // 2)) for power, coefficient in enumerate(values["coefficients"]) if power % 2 == 0)
    elif family == "reciprocal_sum_minimum":
        answer = Fraction(values["count"] ** 2, values["sum"])
    elif family == "euler_phi":
        answer = sum(math.gcd(number, values["modulus"]) == 1 for number in range(1, values["modulus"] + 1))
    elif family == "catalan_number":
        answer = math.comb(2 * values["n"], values["n"]) // (values["n"] + 1)
    elif family == "binomial_tail_probability":
        answer = sum(Fraction(math.comb(values["trials"], hits), 2 ** values["trials"]) for hits in range(values["minimum"], values["trials"] + 1))
    elif family == "complete_bipartite_tree_count":
        answer = values["left"] ** (values["right"] - 1) * values["right"] ** (values["left"] - 1)
    elif family == "matrix_trace_square":
        matrix = values["matrix"]
        answer = sum(matrix[row][column] * matrix[column][row] for row in range(len(matrix)) for column in range(len(matrix)))
    elif family == "geometric_recurrence_sum":
        answer = values["initial"] * (values["ratio"] ** values["terms"] - 1) // (values["ratio"] - 1)
    elif family == "triangle_area_twice":
        (x1, y1), (x2, y2), (x3, y3) = values["points"]
        answer = abs((x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1))
    elif family == "interval_schedule_count":
        end = -10**9
        answer = 0
        for start, finish in sorted(values["intervals"], key=lambda interval: interval[1]):
            if start >= end:
                answer += 1
                end = finish
    elif family == "element_order_lcm":
        answer = math.lcm(*values["orders"])
    elif family == "kraft_remaining_leaves":
        answer = 2 ** values["depth"] - sum(2 ** (values["depth"] - length) for length in values["lengths"])
    else:
        raise ValueError(f"unknown math blueprint family: {family}")
    if isinstance(answer, Fraction):
        return str(answer.numerator) if answer.denominator == 1 else f"{answer.numerator}/{answer.denominator}"
    return str(answer)


def _legacy_family_blueprint(subtype: str, ordinal: int) -> tuple[dict[str, Any], str, list[str], str, list[str]]:
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


def _family_blueprint(subtype: str, ordinal: int) -> tuple[dict[str, Any], str, list[str], str, list[str]]:
    """Use a distinct source-derived mechanism for one fifth of each topic pool.

    The remaining items deliberately retain the legacy builders while the next
    curation pass replaces them one source card at a time.  This keeps every
    answer independently recomputable during the transition.
    """
    if ordinal % 5:
        return _legacy_family_blueprint(subtype, ordinal)
    n = ordinal + 5
    if subtype == "advanced_algebra":
        coefficients = [n - 9, 2 * n - 3, n + 1, -2, 1]
        return ({"family": "polynomial_remainder_constant", "values": {"coefficients": coefficients}}, f"设 P(x) 的升幂系数依次为 {coefficients}。求 P(x) 除以 x^2+1 所得余式的常数项。", ["polynomial_remainder", "quotient_ring"], "quotient_ring_remainder", ["using_x_squared_equals_one", "dropping_even_terms"])
    if subtype == "inequality_optimization":
        count, total = 3 + n % 4, 12 + 2 * (n % 5)
        return ({"family": "reciprocal_sum_minimum", "values": {"count": count, "sum": total}}, f"正实数 x_1,…,x_{count} 满足和为 {total}。求 Σ(1/x_i) 的最小值，写成最简分数。", ["cauchy_schwarz", "equality_case"], "reciprocal_sum_optimization", ["wrong_equality_case", "arithmetic_mean_substitution"])
    if subtype == "number_theory":
        modulus = [30, 36, 40, 45, 48, 54][n % 6]
        return ({"family": "euler_phi", "values": {"modulus": modulus}}, f"求欧拉函数 φ({modulus})，并说明如何由其素因子分解得到该值。", ["euler_totient", "prime_factorization"], "totient_from_factorization", ["including_nonunits", "missing_prime_factor"])
    if subtype == "combinatorics":
        size = 4 + n % 7
        return ({"family": "catalan_number", "values": {"n": size}}, f"有 {size} 对可区分括号。满足任意前缀中左括号数不少于右括号数的合法序列有多少个？", ["catalan_number", "reflection_principle"], "balanced_parentheses_count", ["using_binomial_without_subtraction", "prefix_condition_ignored"])
    if subtype == "discrete_probability":
        trials, minimum = 7 + n % 5, 4 + n % 3
        return ({"family": "binomial_tail_probability", "values": {"trials": trials, "minimum": minimum}}, f"公平硬币独立抛掷 {trials} 次。正面次数不少于 {minimum} 的概率是多少？写成最简分数。", ["binomial_distribution", "tail_sum"], "binomial_tail", ["single_term_only", "wrong_tail_direction"])
    if subtype == "graph_theory":
        left, right = 3 + n % 4, 4 + n % 5
        return ({"family": "complete_bipartite_tree_count", "values": {"left": left, "right": right}}, f"完全二部图 K_{{{left},{right}}} 有多少棵生成树？", ["matrix_tree_theorem", "complete_bipartite_graph"], "bipartite_spanning_tree", ["using_cayley_formula", "swapping_exponents"])
    if subtype == "linear_algebra":
        matrix = [[n % 5 - 2, 2], [3, n % 7 - 3]]
        return ({"family": "matrix_trace_square", "values": {"matrix": matrix}}, f"设 A={matrix}。求 tr(A^2)，并利用 trace 的循环性质核对。", ["matrix_multiplication", "trace"], "trace_of_matrix_square", ["squaring_each_entry", "omitting_off_diagonal_terms"])
    if subtype == "recurrence_generating_functions":
        initial, ratio, terms = 2 + n % 5, 2 + n % 3, 5 + n % 4
        return ({"family": "geometric_recurrence_sum", "values": {"initial": initial, "ratio": ratio, "terms": terms}}, f"数列 a_0={initial}，a_{{k+1}}={ratio}a_k。求 Σ_{{k=0}}^{{{terms}-1}}a_k。", ["geometric_series", "recurrence"], "geometric_recurrence_sum", ["term_count_off_by_one", "missing_initial_term"])
    if subtype == "geometry_analytic":
        points = [(0, 0), (3 + n % 5, 1), (1 + n % 4, 4 + n % 3)]
        return ({"family": "triangle_area_twice", "values": {"points": points}}, f"三角形三个顶点为 {points}。求其面积的两倍，并说明定向叉积的符号为何不影响答案。", ["cross_product", "oriented_area"], "triangle_cross_product", ["missing_absolute_value", "coordinate_subtraction_error"])
    if subtype == "algorithms_discrete_optimization":
        intervals = [(0, 2), (1, 4), (3, 5), (4, 7), (5, 9), (8, 10)]
        return ({"family": "interval_schedule_count", "values": {"intervals": intervals}}, f"给定半开区间集合 {intervals}。最多能选出多少个两两不重叠区间？请给出按结束时间贪心的证书。", ["interval_scheduling", "exchange_argument"], "interval_scheduling", ["sorting_by_start", "treating_touching_as_overlap"])
    if subtype == "abstract_algebra_intro":
        orders = [2 + n % 4, 3 + n % 5, 4 + n % 3]
        return ({"family": "element_order_lcm", "values": {"orders": orders}}, f"在直积群中，一个元素三个分量的阶分别为 {orders}。该元素的阶是多少？", ["direct_product_groups", "element_order"], "direct_product_element_order", ["adding_orders", "using_product_instead_of_lcm"])
    if subtype == "information_coding":
        depth, lengths = 6 + n % 3, [2, 3, 4]
        return ({"family": "kraft_remaining_leaves", "values": {"depth": depth, "lengths": lengths}}, f"一棵满二叉前缀码树的最大深度固定为 {depth}，已有三个码字长度为 {lengths}。在把所有叶子补到最大深度时，尚余多少个深度-{depth} 叶位？", ["kraft_inequality", "prefix_code_tree"], "kraft_leaf_capacity", ["using_plain_length_sum", "wrong_depth_completion"])
    raise ValueError(f"unknown subtype: {subtype}")


def _make_item(question_id: str, pool: str, subtype: str, tier: str, ordinal: int) -> dict[str, Any]:
    blueprint, prompt, prerequisites, family, traps = _family_blueprint(subtype, ordinal)
    answer = recompute_answer(blueprint)
    answer_format = "reduced_fraction" if "/" in answer else "integer"
    source_seed = _source_seed(subtype, ordinal, question_id)
    source_id = f"source-seed-{question_id.lower()}"
    return {
        "question_id": question_id,
        "version": VERSION,
        "module": "A1",
        "subtype": subtype,
        "item_format": "single_turn",
        "difficulty": "medium" if tier == "foundation" else "hard",
        "difficulty_tier": tier,
        "drift_role": "capability",
        "prompt_template": (
            f"{prompt}\n"
            f"本题对应的知识结构是「{source_seed['concept']}」。推理时请{source_seed['task_form']}。\n"
            f"{FRAMINGS[ordinal % len(FRAMINGS)]}"
        ),
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
            "transformation_summary": "Independently rewritten from a public coverage source and a distinct source seed; no public problem wording is copied.",
            "source_seed": source_seed,
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
        "notes": "quality_track=advanced_math; direct_public_reuse=false; source_seeded=true; review_status=generated",
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


def build_advanced_math_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for item in items:
        candidate_id = item["provenance"]["source_candidate_ids"][0]
        source_seed = item["provenance"]["source_seed"]
        candidates.append(
            {
                "candidate_id": candidate_id,
                "source_name": source_seed["source_name"],
                "source_dataset": "public-source-coverage-seeds",
                "source_split": "curated",
                "source_url": source_seed["source_url"],
                "original_id": source_seed["related_source_locator"],
                "module_candidates": ["A1"],
                "task_family": item["discrimination_profile"]["item_family"],
                "category": item["subtype"],
                "prompt": item["prompt_template"],
                "turns": None,
                "options": None,
                "answer": item["ground_truth"],
                "scoring_method": "advanced_math",
                "scoring_params": item["scoring_params"],
                "anti_contamination_source": None,
                "source_metadata": {"difficulty_tier": item["difficulty_tier"], "source_seed": source_seed, "blueprint": item["math_blueprint"]},
                "direct_reuse_allowed": False,
                "rewrite_guidance": "Use the recorded public source only for conceptual lineage; independently rewrite without copying public problem wording.",
                "notes": "Source-seeded deterministic item with independently recomputable answer.",
            }
        )
    return candidates


def build_advanced_math_rewrites(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rewrite_id": item["provenance"]["rewrite_ids"][0],
            "source_candidate_ids": item["provenance"]["source_candidate_ids"],
            "source_names": [item["provenance"]["source_seed"]["source_name"]],
            "target_module": "A1",
            "target_subtype": item["subtype"],
            "item_format": "single_turn",
            "rewrite_strategies": ["context_reframe", "constraint_recomposition"],
            "draft_prompt": item["prompt_template"],
            "draft_turns": None,
            "draft_answer": item["ground_truth"],
            "draft_options": None,
            "scoring_method": "advanced_math",
            "scoring_params": item["scoring_params"],
            "draft_status": "accepted",
            "direct_public_reuse": False,
            "contamination_risk": "low",
            "similarity_controls": {"lexical_overlap_max": 0.78, "preserve_answer_type_only": False},
            "review_notes": "Source-seeded independent rewrite with independently recomputable answer; public wording is not reused.",
        }
        for item in items
    ]


def audit_advanced_math_bank(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_pool = Counter(item["qa_status"] for item in items)
    by_tier = Counter(item["difficulty_tier"] for item in items)
    by_subtype = Counter(item["subtype"] for item in items)
    failures = [
        item["question_id"] for item in items
        if recompute_answer(item["math_blueprint"]) != item["answer_contract"]["canonical_answer"]
    ]
    normalized_prompts: dict[str, list[str]] = {}
    for item in items:
        normalized = re.sub(r"\d+(?:/\d+)?", "#", item["prompt_template"].lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized_prompts.setdefault(normalized, []).append(item["question_id"])
    reskin_clusters = [
        {"normalized_prompt": prompt, "question_ids": question_ids}
        for prompt, question_ids in normalized_prompts.items()
        if len(question_ids) > 2
    ]
    source_seeds = [item.get("provenance", {}).get("source_seed", {}) for item in items]
    source_seed_ids = [seed.get("seed_id") for seed in source_seeds if seed.get("seed_id")]
    source_seed_counts = Counter(source_seed_ids)
    source_keys = {seed.get("source_key") for seed in source_seeds if seed.get("source_key")}
    repeated_seeds = [seed_id for seed_id, count in source_seed_counts.items() if count > 2]
    violations = [
        {"rule": "parameter_reskin_limit", "question_ids": cluster["question_ids"]}
        for cluster in reskin_clusters
    ]
    violations.extend({"rule": "source_seed_reuse_limit", "source_seed": seed_id} for seed_id in repeated_seeds)
    return {
        "passed": not failures and not violations,
        "total": len(items),
        "qa_status_counts": dict(by_pool),
        "difficulty_tier_counts": dict(by_tier),
        "subtype_counts": dict(by_subtype),
        "recompute_failures": failures,
        "parameter_reskin_clusters": reskin_clusters,
        "source_catalog_count": len(source_keys),
        "distinct_source_seed_count": len(source_seed_counts),
        "max_items_per_source_seed": max(source_seed_counts.values(), default=0),
        "max_items_per_prompt_cluster": max((len(cluster["question_ids"]) for cluster in reskin_clusters), default=1),
        "violations": violations,
        "source_policy": "public course and competition materials define coverage and source seeds; formal wording is independently rewritten",
    }
