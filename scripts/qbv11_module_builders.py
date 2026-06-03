#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable
from itertools import cycle


RewriteFactory = Callable[..., tuple[dict, dict]]


def _rows_for_module(pools: dict[str, list[dict]], module: str, *fallbacks: str) -> list[dict]:
    rows = pools.get(module) or []
    if rows:
        return rows
    for fallback in fallbacks:
        rows = pools.get(fallback) or []
        if rows:
            return rows
    for rows in pools.values():
        if rows:
            return rows
    raise ValueError(f"No candidate rows available for module {module}")


def _pick_sources(rows: list[dict], idx: int, width: int = 1) -> list[dict]:
    chosen = []
    for offset in range(width):
        chosen.append(rows[(idx - 1 + offset) % len(rows)])
    return chosen


def _add_item(
    rewrites: list[dict],
    items: list[dict],
    make_rewrite_and_item: RewriteFactory,
    *,
    question_id: str,
    module: str,
    subtype: str,
    prompt: str | None,
    answer,
    scoring_method: str,
    scoring_params: dict,
    source_rows: list[dict],
    difficulty: str,
    quota_tag: str,
    item_format: str = "single_turn",
    turn_script: list[dict] | None = None,
    notes: str = "",
) -> None:
    rewrite, item = make_rewrite_and_item(
        question_id,
        module,
        subtype,
        "capability",
        scoring_method,
        prompt,
        answer,
        scoring_params,
        source_rows,
        item_format=item_format,
        difficulty=difficulty,
        turn_script=turn_script,
        quota_tag=quota_tag,
        notes=notes,
    )
    rewrites.append(rewrite)
    items.append(item)


def _make_long_code_case(seed: int) -> tuple[str, str]:
    base = 11 + seed
    seq = [base, base - 3, base + 4, base - 1, base + 6, base - 5]
    bias = 2 + (seed % 4)
    window = 3 + (seed % 2)
    names = ["amber", "cedar", "delta", "ember", "fable", "glint"]

    def normalize(values):
        return [value * (2 if index % 2 == 0 else 1) - bias for index, value in enumerate(values)]

    def sliding(values):
        chunks = []
        for idx in range(len(values) - window + 1):
            piece = values[idx : idx + window]
            chunks.append(sum(piece) + idx)
        return chunks

    def annotate(scores):
        labeled = []
        for idx, score in enumerate(scores):
            label = names[idx]
            if score % 3 == 0:
                label = label.upper()
            labeled.append((label, score))
        return labeled

    def compress(pairs):
        parts = []
        for label, score in pairs:
            parts.append(f"{label}:{score}")
        return "|".join(parts)

    normalized = normalize(seq)
    windows = sliding(normalized)
    labeled = annotate(windows)
    checksum = sum((idx + 1) * score for idx, (_, score) in enumerate(labeled))
    winners = [label for label, score in labeled if score == max(score for _, score in labeled)]
    expected = f"{checksum}\n{','.join(winners)}\n{compress(labeled)}"

    code = f"""from collections import deque

SEED_VALUES = {seq}
BIAS = {bias}
WINDOW = {window}
NAMES = {names}


def normalize(values):
    normalized = []
    for index, value in enumerate(values):
        scale = 2 if index % 2 == 0 else 1
        normalized.append(value * scale - BIAS)
    return normalized


def build_windows(values):
    history = deque(maxlen=WINDOW)
    windows = []
    for index, value in enumerate(values):
        history.append(value)
        if len(history) == WINDOW:
            windows.append(sum(history) + index - WINDOW + 1)
    return windows


def annotate(scores):
    labeled = []
    for index, score in enumerate(scores):
        label = NAMES[index]
        if score % 3 == 0:
            label = label.upper()
        labeled.append((label, score))
    return labeled


def checksum(pairs):
    total = 0
    for index, (_, score) in enumerate(pairs, start=1):
        total += index * score
    return total


def render_pairs(pairs):
    parts = []
    for label, score in pairs:
        parts.append(f"{{label}}:{{score}}")
    return "|".join(parts)


def select_winners(pairs):
    best = max(score for _, score in pairs)
    winners = []
    for label, score in pairs:
        if score == best:
            winners.append(label)
    return winners


def enrich(values):
    normalized = normalize(values)
    windows = build_windows(normalized)
    pairs = annotate(windows)
    return {{
        "normalized": normalized,
        "windows": windows,
        "pairs": pairs,
        "checksum": checksum(pairs),
        "winners": select_winners(pairs),
        "pairs_rendered": render_pairs(pairs),
    }}


payload = enrich(SEED_VALUES)
print(payload["checksum"])
print(",".join(payload["winners"]))
print(payload["pairs_rendered"])
"""
    return code, expected


def build_a2_v11(pools: dict[str, list[dict]], make_rewrite_and_item: RewriteFactory) -> tuple[list[dict], list[dict]]:
    rewrites: list[dict] = []
    items: list[dict] = []
    source_rows = _rows_for_module(pools, "A2", "A1")
    idx = 1

    constrained_tasks = [
        {
            "name": "reshape_cuboid_layers",
            "description": (
                "实现函数 reshape_cuboid_layers(cube)。输入是三维整数数组。"
                "对每一层：如果层索引为偶数，则把该层每一行右移一格；如果层索引为奇数，则把该层每一行反转。"
                "随后把每层右下角元素追加到摘要列表，最终返回 (new_cube, summary)。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "cube = [[[1,2],[3,4]], [[5,6],[7,8]]]\nprint(reshape_cuboid_layers(cube))", "expected": "([[[2, 1], [4, 3]], [[6, 5], [8, 7]]], [3, 7])"},
                {"harness": "cube = [[[9,8,7]], [[1,2,3]]]\nprint(reshape_cuboid_layers(cube))", "expected": "([[[7, 9, 8]], [[3, 2, 1]]], [8, 1])"},
            ],
        },
        {
            "name": "solve_target_bundles",
            "description": (
                "实现函数 solve_target_bundles(nums, target)。从左到右扫描数字，维护当前和。"
                "每当当前和恰好等于 target 时记录一个区间并清空当前和；如果超过 target，则当前区间作废并从当前数字重新开始。"
                "返回所有命中的 [start,end] 区间。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(solve_target_bundles([2,3,1,4,2,2,3], 6))", "expected": "[[0, 2], [4, 6]]"},
                {"harness": "print(solve_target_bundles([5,1,2,2,4], 4))", "expected": "[[2, 3], [4, 4]]"},
            ],
        },
        {
            "name": "dispatch_tool_chain",
            "description": (
                "实现函数 dispatch_tool_chain(steps, inventory)。steps 是 [(tool, amount)]，inventory 是工具剩余次数字典。"
                "依次执行：若工具次数足够则扣减并记录 'ok'，否则记录 'skip'；连续两个 skip 之后，后续步骤全部标记为 'halt'。"
                "返回 (final_inventory, status_list)。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "steps=[('cut',1),('weld',1),('cut',1),('paint',1)]\ninv={'cut':1,'weld':0,'paint':0}\nprint(dispatch_tool_chain(steps, inv))", "expected": "({'cut': 0, 'weld': 0, 'paint': 0}, ['ok', 'skip', 'skip', 'halt'])"},
                {"harness": "steps=[('mix',2),('mix',1),('seal',1)]\ninv={'mix':3,'seal':1}\nprint(dispatch_tool_chain(steps, inv))", "expected": "({'mix': 0, 'seal': 0}, ['ok', 'ok', 'ok'])"},
            ],
        },
        {
            "name": "stitch_sparse_canvas",
            "description": (
                "实现函数 stitch_sparse_canvas(size, patches)。初始是 size x size 的 '.' 矩阵。"
                "patches 中每项为 (row, col, token, span)，表示从 (row,col) 开始向右填充 token 共 span 格，不得越界。"
                "若某格已被占用，则保留字典序更小的 token。返回最终字符串列表。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(stitch_sparse_canvas(4, [(0,0,'b',3),(0,1,'a',2),(2,2,'z',2)]))", "expected": "['baab', '....', '..zz', '....']"},
                {"harness": "print(stitch_sparse_canvas(3, [(1,0,'m',2),(1,1,'k',2)]))", "expected": "['...', 'mkk', '...']"},
            ],
        },
        {
            "name": "rebalance_ticket_book",
            "description": (
                "实现函数 rebalance_ticket_book(capacity, ops)。ops 中每项为 ('buy'|'refund', user, count)。"
                "buy 只有在剩余票足够时才成功；refund 会把该用户已买票数减少但不能减成负数。"
                "返回按用户名排序的持票字典和剩余票数。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "ops=[('buy','A',2),('buy','B',3),('refund','A',1),('buy','C',2)]\nprint(rebalance_ticket_book(6, ops))", "expected": "({'A': 1, 'B': 3}, 2)"},
                {"harness": "ops=[('buy','Q',1),('refund','Q',2),('buy','Q',2)]\nprint(rebalance_ticket_book(3, ops))", "expected": "({'Q': 2}, 1)"},
            ],
        },
        {
            "name": "aggregate_cube_edges",
            "description": (
                "实现函数 aggregate_cube_edges(cube)。cube 是三维数组。"
                "对每层取第一行、最后一行、每行首尾列组成边界和；返回所有层边界和构成的列表，"
                "以及这些边界和的奇偶标签字符串（奇数记 O，偶数记 E，用 '-' 连接）。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "cube=[[[1,2],[3,4]], [[2,2,2],[1,1,1]]]\nprint(aggregate_cube_edges(cube))", "expected": "([10, 9], 'E-O')"},
                {"harness": "cube=[[[5]]]\nprint(aggregate_cube_edges(cube))", "expected": "([5], 'O')"},
            ],
        },
        {
            "name": "route_machine_states",
            "description": (
                "实现函数 route_machine_states(commands)。初始状态为 power=0, mode='idle', buffer=[]。"
                "命令可能为 ON, OFF, PUSH:x, POP, FLIP。ON 令 power=1；OFF 清空 buffer 且 mode='idle'；"
                "PUSH 仅在 power=1 时生效；POP 弹出末尾元素；FLIP 在 active/idle 间切换但只有 power=1 时有效。"
                "返回最终状态字典。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(route_machine_states(['ON','FLIP','PUSH:7','PUSH:3','POP']))", "expected": "{'power': 1, 'mode': 'active', 'buffer': ['7']}"},
                {"harness": "print(route_machine_states(['PUSH:1','ON','PUSH:2','OFF','PUSH:9']))", "expected": "{'power': 0, 'mode': 'idle', 'buffer': []}"},
            ],
        },
        {
            "name": "reconstruct_prize_board",
            "description": (
                "实现函数 reconstruct_prize_board(rows)。rows 是多行字符串，形如 'team,score,bonus'。"
                "总分 = score + bonus；如果 team 再次出现，保留更高总分。最终按总分降序、team 升序返回 [(team,total)]。"
                "只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "rows=['A,10,2','B,9,5','A,8,8']\nprint(reconstruct_prize_board(rows))", "expected": "[('A', 16), ('B', 14)]"},
                {"harness": "rows=['M,4,1','N,3,1','M,2,1']\nprint(reconstruct_prize_board(rows))", "expected": "[('M', 5), ('N', 4)]"},
            ],
        },
        {
            "name": "layered_word_matrix",
            "description": (
                "实现函数 layered_word_matrix(words, width)。把每个单词放入宽度为 width 的网格中，"
                "奇数行从左到右填充，偶数行从右到左填充；若一行放不下就换行。空位补 '_'。返回字符串列表。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(layered_word_matrix(['aa','bbb','c','dd'], 5))", "expected": "['aabb_', 'ddc__']"},
                {"harness": "print(layered_word_matrix(['x','yy','zzz'], 4))", "expected": "['xyy_', 'zzz_']"},
            ],
        },
        {
            "name": "compose_pipeline_report",
            "description": (
                "实现函数 compose_pipeline_report(stages)。每项为 (name, duration, ok)。"
                "返回字典：total_duration、failed_names（按出现顺序）、slowest_ok_stage（仅在 ok=True 中选 duration 最大者，无则 None）。"
                "只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "stages=[('prep',3,True),('scan',8,False),('pack',5,True)]\nprint(compose_pipeline_report(stages))", "expected": "{'total_duration': 16, 'failed_names': ['scan'], 'slowest_ok_stage': 'pack'}"},
                {"harness": "stages=[('a',2,False),('b',3,False)]\nprint(compose_pipeline_report(stages))", "expected": "{'total_duration': 5, 'failed_names': ['a', 'b'], 'slowest_ok_stage': None}"},
            ],
        },
        {
            "name": "tri_axis_transform",
            "description": (
                "实现函数 tri_axis_transform(cube, shifts)。cube 为三维整数数组，shifts 为长度 3 的整数列表。"
                "依次对三个轴做循环位移：先对层轴，再对行轴，再对列轴。返回最终 cube。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "cube=[[[1,2],[3,4]],[[5,6],[7,8]]]\nprint(tri_axis_transform(cube,[1,1,1]))", "expected": "[[[8, 7], [6, 5]], [[4, 3], [2, 1]]]"},
                {"harness": "cube=[[[9]]]\nprint(tri_axis_transform(cube,[3,2,1]))", "expected": "[[[9]]]"},
            ],
        },
        {
            "name": "fold_event_windows",
            "description": (
                "实现函数 fold_event_windows(events, gap)。events 为升序整数时间点。"
                "将相邻差值 <= gap 的时间点折叠成一个窗口，返回 [(start,end,count)]。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(fold_event_windows([1,2,4,10,11], 1))", "expected": "[(1, 2, 2), (4, 4, 1), (10, 11, 2)]"},
                {"harness": "print(fold_event_windows([3,5,6,7], 2))", "expected": "[(3, 7, 4)]"},
            ],
        },
        {
            "name": "repair_bucket_constraints",
            "description": (
                "实现函数 repair_bucket_constraints(values, limit)。从左到右把 values 放入多个桶中，"
                "每个桶和不能超过 limit；若当前值放不进现有最后一个桶就新开桶。返回桶列表和最大桶和。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "print(repair_bucket_constraints([4,3,5,2,2], 7))", "expected": "([[4, 3], [5, 2], [2]], 7)"},
                {"harness": "print(repair_bucket_constraints([1,1,1], 5))", "expected": "([[1, 1, 1]], 3)"},
            ],
        },
        {
            "name": "trace_award_lottery",
            "description": (
                "实现函数 trace_award_lottery(entries)。每项为 (name, weight, active)。"
                "忽略 inactive，按 weight 从高到低选前两名；若并列则名字字典序小者优先。返回 winners 和 total_weight。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "entries=[('Lan',5,True),('Moe',5,True),('Nia',7,False),('Oli',4,True)]\nprint(trace_award_lottery(entries))", "expected": "(['Lan', 'Moe'], 14)"},
                {"harness": "entries=[('A',2,False),('B',9,True)]\nprint(trace_award_lottery(entries))", "expected": "(['B'], 9)"},
            ],
        },
        {
            "name": "merge_nested_intervals",
            "description": (
                "实现函数 merge_nested_intervals(groups)。groups 为字典，value 是该组的若干闭区间。"
                "每组先内部合并重叠区间，再返回按键排序后的 {group: merged}。只输出完整函数代码。"
            ),
            "tests": [
                {"harness": "groups={'x':[(1,3),(2,5)],'a':[(7,8),(10,11)]}\nprint(merge_nested_intervals(groups))", "expected": "{'a': [(7, 8), (10, 11)], 'x': [(1, 5)]}"},
                {"harness": "groups={'z':[(4,4),(4,6)]}\nprint(merge_nested_intervals(groups))", "expected": "{'z': [(4, 6)]}"},
            ],
        },
    ]

    for task in constrained_tasks:
        prompt = (
            f"请实现 Python 函数 `{task['name']}`。\n{task['description']}\n"
            "要求：\n1. 只输出完整函数代码；\n2. 不要给解释；\n3. 代码需要处理边界情况。"
        )
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A2-{idx:03d}",
            module="A2",
            subtype="constrained_program_synthesis",
            prompt=prompt,
            answer=None,
            scoring_method="exec",
            scoring_params={"tests": task["tests"], "function_name": task["name"], "response_max_tokens": 2048},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="constrained_program_synthesis",
            notes="QB-v1.1 upgraded A2 item inspired by APPS / BigCodeBench style constrained synthesis.",
        )
        idx += 1

    for offset in range(10):
        code, expected = _make_long_code_case(offset)
        prompt = (
            "阅读下面这段较长的 Python 程序，并只输出它的最终标准输出，不要解释。\n"
            f"```python\n{code}\n```"
        )
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A2-{idx:03d}",
            module="A2",
            subtype="long_code_comprehension",
            prompt=prompt,
            answer=expected,
            scoring_method="exact_match",
            scoring_params={"match_mode": "stdout", "response_max_tokens": 512},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="long_code_comprehension",
            notes="QB-v1.1 long code comprehension item inspired by BigCodeBench / SWE-bench Lite code reading style.",
        )
        idx += 1

    stateful_tasks = [
        {
            "name": "parse_shift_log",
            "description": (
                "实现函数 parse_shift_log(lines)。每行形如 `name|in`、`name|out` 或 `name|task:count`。"
                "只有在 in 之后的 task 才计数；out 后忽略后续 task 直到再次 in。返回按姓名排序的任务总数字典。"
            ),
            "tests": [
                {"harness": "lines=['A|in','A|task:3','A|out','A|task:9','B|in','B|task:2']\nprint(parse_shift_log(lines))", "expected": "{'A': 3, 'B': 2}"},
                {"harness": "lines=['M|task:1','M|in','M|task:4','M|task:1']\nprint(parse_shift_log(lines))", "expected": "{'M': 5}"},
            ],
        },
        {
            "name": "fill_character_matrix",
            "description": (
                "实现函数 fill_character_matrix(size, commands)。size 为 n。commands 包含 ROW:r:token、COL:c:token、DIAG:token。"
                "后来的命令覆盖先前字符。返回最终矩阵字符串列表。"
            ),
            "tests": [
                {"harness": "print(fill_character_matrix(3,['ROW:1:x','COL:0:o','DIAG:k']))", "expected": "['koo', 'xkx', 'o.k']"},
                {"harness": "print(fill_character_matrix(2,['COL:1:z']))", "expected": "['.z', '.z']"},
            ],
        },
        {
            "name": "reconcile_pipeline_log",
            "description": (
                "实现函数 reconcile_pipeline_log(rows)。每行 `job,status,ts`。对每个 job 保留时间戳最大的状态，"
                "然后返回按 status 聚合后的 job 数量字典。"
            ),
            "tests": [
                {"harness": "rows=['j1,ok,1','j1,fail,3','j2,ok,2']\nprint(reconcile_pipeline_log(rows))", "expected": "{'fail': 1, 'ok': 1}"},
                {"harness": "rows=['a,hold,5','a,ok,6','b,hold,7']\nprint(reconcile_pipeline_log(rows))", "expected": "{'hold': 1, 'ok': 1}"},
            ],
        },
        {
            "name": "simulate_train_sales",
            "description": (
                "实现函数 simulate_train_sales(capacity, ops)。ops 为 `book:name:count` / `refund:name:count`。"
                "book 只有余票足够才成功；refund 不会退成负数。返回各人持票数和余票。"
            ),
            "tests": [
                {"harness": "print(simulate_train_sales(5,['book:A:2','book:B:3','refund:A:1','book:C:1']))", "expected": "({'A': 1, 'B': 3}, 1)"},
                {"harness": "print(simulate_train_sales(2,['book:X:3','book:X:1']))", "expected": "({'X': 1}, 1)"},
            ],
        },
        {
            "name": "count_text_channels",
            "description": (
                "实现函数 count_text_channels(text)。逐字符扫描英文文本。字母、数字、空格、标点分别计数，"
                "并返回出现次数最多的字母（忽略大小写，若并列取字母序最小）。"
            ),
            "tests": [
                {"harness": "print(count_text_channels('Aa-b 11?'))", "expected": "{'letters': 3, 'digits': 2, 'spaces': 1, 'punct': 2, 'top_letter': 'a'}"},
                {"harness": "print(count_text_channels('xyY!!'))", "expected": "{'letters': 3, 'digits': 0, 'spaces': 0, 'punct': 2, 'top_letter': 'y'}"},
            ],
        },
        {
            "name": "compact_alarm_windows",
            "description": (
                "实现函数 compact_alarm_windows(events)。events 为 `(machine, ts)` 升序。"
                "对每台 machine 把时间差 <=2 的事件压缩成窗口，返回 {machine: [(start,end,count)]}。"
            ),
            "tests": [
                {"harness": "events=[('m1',1),('m1',2),('m1',6),('m2',3),('m2',4)]\nprint(compact_alarm_windows(events))", "expected": "{'m1': [(1, 2, 2), (6, 6, 1)], 'm2': [(3, 4, 2)]}"},
                {"harness": "events=[('x',9)]\nprint(compact_alarm_windows(events))", "expected": "{'x': [(9, 9, 1)]}"},
            ],
        },
        {
            "name": "normalize_batch_records",
            "description": (
                "实现函数 normalize_batch_records(rows)。rows 每项为 `(batch, tag, value)`。同一 batch 内，"
                "tag 后写覆盖前写；最终返回按 batch 排序的 `{batch: 'k1=v1|k2=v2'}` 字典，tag 按字典序连接。"
            ),
            "tests": [
                {"harness": "rows=[('b1','x',1),('b1','y',2),('b1','x',5),('b2','a',3)]\nprint(normalize_batch_records(rows))", "expected": "{'b1': 'x=5|y=2', 'b2': 'a=3'}"},
                {"harness": "rows=[('z','k',9)]\nprint(normalize_batch_records(rows))", "expected": "{'z': 'k=9'}"},
            ],
        },
        {
            "name": "trace_lottery_winners",
            "description": (
                "实现函数 trace_lottery_winners(names, scores, bonus_cutoff)。先把 names 和 scores 对齐，"
                "得分 >= bonus_cutoff 的人进入 bonus 池。返回 bonus 池按分数降序、姓名升序排序后的名字列表和总分。"
            ),
            "tests": [
                {"harness": "print(trace_lottery_winners(['A','B','C'], [8,10,8], 8))", "expected": "(['B', 'A', 'C'], 26)"},
                {"harness": "print(trace_lottery_winners(['N'], [3], 5))", "expected": "([], 0)"},
            ],
        },
        {
            "name": "diff_sparse_grids",
            "description": (
                "实现函数 diff_sparse_grids(a, b)。a/b 为同尺寸字符串列表。返回所有不同位置的 `(r,c,a_char,b_char)`。"
                "按行列升序。"
            ),
            "tests": [
                {"harness": "print(diff_sparse_grids(['ab','.c'], ['ax','.d']))", "expected": "[(0, 1, 'b', 'x'), (1, 1, 'c', 'd')]"},
                {"harness": "print(diff_sparse_grids(['..'], ['..']))", "expected": "[]"},
            ],
        },
        {
            "name": "expand_queue_snapshots",
            "description": (
                "实现函数 expand_queue_snapshots(ops)。支持 ENQ:x、DEQ、PEEK、RESET。"
                "对每个 PEEK 记录当前队首；最终返回所有快照列表和最终队列。"
            ),
            "tests": [
                {"harness": "print(expand_queue_snapshots(['ENQ:a','ENQ:b','PEEK','DEQ','PEEK']))", "expected": "(['a', 'b'], ['b'])"},
                {"harness": "print(expand_queue_snapshots(['PEEK','ENQ:x','RESET','PEEK']))", "expected": "([None, None], [])"},
            ],
        },
        {
            "name": "summarize_pipe_repair",
            "description": (
                "实现函数 summarize_pipe_repair(segments)。每项 `(name, blocked, repaired)`。"
                "若 repaired >= blocked 则该段状态 cleared，否则 pending。返回 cleared 名单和未清除剩余总量。"
            ),
            "tests": [
                {"harness": "print(summarize_pipe_repair([('p1',5,5),('p2',4,1)]))", "expected": "(['p1'], 3)"},
                {"harness": "print(summarize_pipe_repair([('a',2,3)]))", "expected": "(['a'], 0)"},
            ],
        },
        {
            "name": "restore_compressed_notes",
            "description": (
                "实现函数 restore_compressed_notes(text)。格式如 `a3|b1|c2`，表示字符重复。"
                "还原后去掉所有重复段中次数为 1 的分隔符影响，只返回纯字符串。"
            ),
            "tests": [
                {"harness": "print(restore_compressed_notes('a3|b1|c2'))", "expected": "aaabcc"},
                {"harness": "print(restore_compressed_notes('x1|y4'))", "expected": "xyyyy"},
            ],
        },
        {
            "name": "rank_word_packs",
            "description": (
                "实现函数 rank_word_packs(words)。按 `(不同字母数, 长度, 单词本身)` 排序；返回排序结果和首个单词的元组签名。"
            ),
            "tests": [
                {"harness": "print(rank_word_packs(['alpha','noon','bee']))", "expected": "(['bee', 'noon', 'alpha'], (2, 3, 'bee'))"},
                {"harness": "print(rank_word_packs(['zz','ab']))", "expected": "(['zz', 'ab'], (1, 2, 'zz'))"},
            ],
        },
        {
            "name": "trace_machine_registers",
            "description": (
                "实现函数 trace_machine_registers(cmds)。寄存器初值 a=0,b=0。支持 SET:x:n、ADD:x:n、SWAP、ZERO:x。"
                "返回最终寄存器和每次 SWAP 后的快照列表。"
            ),
            "tests": [
                {"harness": "print(trace_machine_registers(['SET:a:3','ADD:b:2','SWAP','ZERO:a']))", "expected": "({'a': 0, 'b': 3}, [(2, 3)])"},
                {"harness": "print(trace_machine_registers(['SET:b:5']))", "expected": "({'a': 0, 'b': 5}, [])"},
            ],
        },
        {
            "name": "build_ascii_layers",
            "description": (
                "实现函数 build_ascii_layers(tokens, width)。依次把 token 写入宽为 width 的层，每层满了就下一层。"
                "每层用 `.` 补齐。返回层列表和每层非点字符数。"
            ),
            "tests": [
                {"harness": "print(build_ascii_layers(['ab','c','de'], 4))", "expected": "(['abc.', 'de..'], [3, 2])"},
                {"harness": "print(build_ascii_layers(['x'], 2))", "expected": "(['x.'], [1])"},
            ],
        },
    ]

    for task in stateful_tasks:
        prompt = (
            f"请实现 Python 函数 `{task['name']}`。\n{task['description']}\n"
            "只输出完整函数代码，不要解释。"
        )
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A2-{idx:03d}",
            module="A2",
            subtype="stateful_data_processing",
            prompt=prompt,
            answer=None,
            scoring_method="exec",
            scoring_params={"tests": task["tests"], "function_name": task["name"], "response_max_tokens": 2048},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="stateful_data_processing",
            notes="QB-v1.1 A2 stateful processing item inspired by LiveCodeBench / APPS style data-flow tasks.",
        )
        idx += 1

    bug_fix_tasks = [
        (
            "def stabilize_counts(rows):\n    out = {}\n    for key, delta in rows:\n        out[key] = out.get(key, 1) + delta\n    return out",
            "稳定累计同 key 的增量，初始值应为 0。",
            [
                {"harness": "print(stabilize_counts([('a',2),('a',3),('b',1)]))", "expected": "{'a': 5, 'b': 1}"},
                {"harness": "print(stabilize_counts([]))", "expected": "{}"},
            ],
        ),
        (
            "def pick_left_middle(values):\n    return values[len(values) // 2]",
            "当长度为偶数时应返回靠左中位元素，而不是靠右。",
            [
                {"harness": "print(pick_left_middle([9,8,7,6]))", "expected": "8"},
                {"harness": "print(pick_left_middle([1,2,3]))", "expected": "2"},
            ],
        ),
        (
            "def merge_pairs(items):\n    merged = []\n    for left, right in items:\n        merged.append(left + '-' + right)\n    return ''.join(merged)",
            "应返回列表而不是拼成一个长字符串。",
            [
                {"harness": "print(merge_pairs([('a','b'),('c','d')]))", "expected": "['a-b', 'c-d']"},
                {"harness": "print(merge_pairs([]))", "expected": "[]"},
            ],
        ),
        (
            "def clamp_to_zero(values):\n    return [min(v, 0) for v in values]",
            "负数应保留，正数才压成 0。",
            [
                {"harness": "print(clamp_to_zero([-2,3,0]))", "expected": "[-2, 0, 0]"},
                {"harness": "print(clamp_to_zero([4]))", "expected": "[0]"},
            ],
        ),
        (
            "def summarize_flags(flags):\n    total = 0\n    for flag in flags:\n        if flag:\n            total -= 1\n    return total",
            "True 应累加而不是累减。",
            [
                {"harness": "print(summarize_flags([True, False, True]))", "expected": "2"},
                {"harness": "print(summarize_flags([]))", "expected": "0"},
            ],
        ),
        (
            "def rotate_window(values, k):\n    k = k % len(values)\n    return values[k:] + values[:k]",
            "应执行循环右移而不是左移。",
            [
                {"harness": "print(rotate_window([1,2,3,4], 1))", "expected": "[4, 1, 2, 3]"},
                {"harness": "print(rotate_window([9,8], 3))", "expected": "[8, 9]"},
            ],
        ),
        (
            "def count_distinct_letters(text):\n    return len(set(text))",
            "应只统计字母，忽略空格和标点，并且大小写不敏感。",
            [
                {"harness": "print(count_distinct_letters('Aa, b!'))", "expected": "2"},
                {"harness": "print(count_distinct_letters('XYZ'))", "expected": "3"},
            ],
        ),
        (
            "def squash_segments(parts):\n    result = []\n    for part in parts:\n        if part not in result:\n            result.append(part)\n    return result[::-1]",
            "去重后应保留首次出现顺序，不应整体反转。",
            [
                {"harness": "print(squash_segments(['x','y','x','z']))", "expected": "['x', 'y', 'z']"},
                {"harness": "print(squash_segments(['a']))", "expected": "['a']"},
            ],
        ),
        (
            "def merge_ranges(ranges):\n    ranges = sorted(ranges)\n    out = []\n    for start, end in ranges:\n        if not out or start > out[-1][1]:\n            out.append([start, end])\n        else:\n            out[-1][1] = min(out[-1][1], end)\n    return [(a, b) for a, b in out]",
            "重叠区间合并时应扩展到更大的 end，而不是更小的 end。",
            [
                {"harness": "print(merge_ranges([(1,3),(2,5),(8,9)]))", "expected": "[(1, 5), (8, 9)]"},
                {"harness": "print(merge_ranges([]))", "expected": "[]"},
            ],
        ),
        (
            "def format_board(rows):\n    return '\\n'.join(sorted(rows))",
            "应保留原顺序，不应排序。",
            [
                {"harness": "print(format_board(['b..','a..']))", "expected": "b..\na.."},
                {"harness": "print(format_board(['xx']))", "expected": "xx"},
            ],
        ),
    ]

    for buggy_code, bug_note, tests in bug_fix_tasks:
        prompt = (
            "下面的 Python 函数有一个逻辑错误，请修复它并只输出修复后的完整函数代码，不要解释。\n"
            f"错误说明：{bug_note}\n"
            f"```python\n{buggy_code}\n```"
        )
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A2-{idx:03d}",
            module="A2",
            subtype="bug_fix_and_patch_reasoning",
            prompt=prompt,
            answer=None,
            scoring_method="exec",
            scoring_params={"tests": tests, "bug_fix": True, "response_max_tokens": 1536},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="bug_fix_and_patch_reasoning",
            notes="QB-v1.1 A2 bug-fix item inspired by EvalPlus / SWE-bench Lite single-function repair.",
        )
        idx += 1

    return rewrites, items


def build_a6_v11(pools: dict[str, list[dict]], make_rewrite_and_item: RewriteFactory) -> tuple[list[dict], list[dict]]:
    rewrites: list[dict] = []
    items: list[dict] = []
    source_rows = _rows_for_module(pools, "A6", "A3", "A1")
    idx = 1

    stateful_prompts = [
        ("一台仓库分拣机初始能量为 5、模式为 idle。指令序列为：ON, LOAD 3, FLIP, USE 2, CHARGE 4, USE 5, OFF。规则：ON 只把模式置为 standby；FLIP 在 standby/active 间切换；USE 仅在 active 时生效且会消耗能量；OFF 会把模式重置为 idle 但不清空能量。问最终状态，格式 `mode=<mode>,energy=<n>`。", "mode=idle,energy=5"),
        ("某售票系统初始余票 12。操作依次为：甲购 4、乙购 3、甲退 1、丙购 5、乙退 2、丁购 3。规则：购票只有余票足够才成功，退票不会让个人票数变负。问最终各人持票和余票，格式 `甲=a,乙=b,丙=c,丁=d,余票=r`。", "甲=3,乙=1,丙=5,丁=0,余票=3"),
        ("某年会抽奖按顺序处理 6 位员工。初始奖池 2 个一等奖、3 个二等奖。规则：分数 >=90 先尝试拿一等奖，否则分数 >=75 拿二等奖；名额不足则落空。员工及分数：Lina 92, Miro 88, Nadi 95, Owen 77, Peta 81, Quinn 91。问中奖名单，格式 `一等奖:[...];二等奖:[...]`。", "一等奖:['Lina', 'Nadi'];二等奖:['Miro', 'Owen', 'Peta']"),
        ("整理一份日记：周一写了“完成采购，未发货”；周二写了“收到付款，安排发货”；周三写了“发货延迟，重新安排”；周四写了“客户确认收货”。若把状态按 采购<付款<发货安排<延迟重排<收货确认 抽象，问最终状态名称。只输出状态中文。", "收货确认"),
        ("一套机器日志按时间给出：BOOT, MODE:A, TASK+3, TASK+2, RESET, MODE:B, TASK+4。规则：RESET 清空任务累计但不清除模式；TASK+n 把当前模式累计任务数加 n。问最终各模式累计任务数，格式 `A=x,B=y`。", "A=0,B=4"),
        ("一列火车有三节车厢，初始座位分别为 4,3,2。操作：1号客订 2 张到车厢 1；2号客订 2 张到车厢 2；1号客退 1 张；3号客想订 3 张同车厢，按车厢编号从小到大尝试。问最终剩余座位，格式 `c1=x,c2=y,c3=z`。", "c1=3,c2=1,c3=2"),
        ("一个多状态水泵初始压强 7。指令：泄压2、增压5、切换维护、泄压4、切换运行、增压1。规则：维护模式下泄压无效；切换维护/运行只改模式。初始模式为运行。问最终模式与压强，格式 `运行/维护,n`。", "运行,11"),
        ("库存表初始：A 5 件，B 2 件。流水：A 出库 3，B 入库 4，A 入库 1，B 出库 5，A 出库 4。出库不足则该次无效。问最终库存，格式 `A=x,B=y`。", "A=3,B=1"),
        ("某排班系统周一到周五初始都为空。命令：Mon=Li, Tue=Mo, Wed=Li, swap Tue Wed, clear Mon, Thu=Qi。问最终已排班名单按 weekday 顺序拼接，格式 `Mon:-|Tue:x|Wed:y|Thu:z|Fri:-`。", "Mon:-|Tue:Li|Wed:Mo|Thu:Qi|Fri:-"),
        ("一个字符缓冲区初始为空。操作：push a, push b, pop, push c, flip, push d。规则：flip 会把缓冲区整体反转；pop 删除末尾元素。问最终缓冲区字符串。", "cad"),
        ("项目状态流：初始 backlog。命令：start, block, unblock, review, approve。规则：start->in_progress；block 只在进行中生效；unblock 只在 blocked 生效回到 in_progress；review 只在 in_progress 生效；approve 只在 review 生效。问最终状态。", "approved"),
        ("某兑换系统积分初始 20。操作：兑换 6，奖励 3，兑换 10，奖励 2，兑换 15。积分不足时兑换失败。问最终积分。只输出数字。", "9"),
        ("一台清洗机有三个桶，初始液量 2,4,6。操作：1->2 倒 1 单位，3->1 倒 2 单位，2 清空，1->3 倒 1 单位。问最终液量，格式 `1=x,2=y,3=z`。", "1=2,2=0,3=5"),
        ("员工工时卡记录：A 签到、A 任务2、B 签到、A 任务1、A 签退、A 任务4、B 任务3。只有签到后且签退前的任务有效。问 A 与 B 的有效任务总量，格式 `A=x,B=y`。", "A=3,B=3"),
        ("某投票计分系统规则：赞成 +2，反对 -1，弃权 0。序列为：赞成、赞成、反对、弃权、反对、赞成。问最终得分。只输出数字。", "4"),
    ]
    for prompt, answer in stateful_prompts:
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A6-{idx:03d}",
            module="A6",
            subtype="stateful_simulation",
            prompt=prompt,
            answer=answer,
            scoring_method="exact_match" if not answer.isdigit() else "numeric_em",
            scoring_params={"response_max_tokens": 512},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="stateful_simulation",
            notes="QB-v1.1 A6 stateful simulation item inspired by PlanBench-style state tracking.",
        )
        idx += 1

    spatial_prompts = [
        ("在 10x10 棋盘上给定两点 A(2,2) 与 B(8,2)。候选顶点有 C1(5,8), C2(5,7), C3(5,6)。哪一个与 AB 组成面积最大的等腰三角形？只输出候选编号。", "C1"),
        ("激光布局题：10x10 网格中墙体在 (3,4),(4,4),(5,4)。若激光器放在候选点 P1(2,4), P2(4,2), P3(7,4)，激光沿四联通方向直射直到遇墙。哪个点能照亮最多空格？只输出候选编号。", "P2"),
        ("一个 4x4 拼图板需要用三块 2x2 小拼图填成目标图形。目标图形占据坐标 {(1,1),(1,2),(2,1),(2,2),(3,3),(3,4),(4,3),(4,4),(1,4),(2,4),(3,4),(4,4)}。候选拼图 A 覆盖左上 2x2，B 覆盖右下 2x2，C 覆盖最右列上三格与底右一格。问应该选择哪些拼图，按字母升序输出，用逗号分隔。", "A,B,C"),
        ("地形迷宫中，起点 S 在 (1,1)，终点 T 在 (4,4)。墙在 (2,2),(2,3),(3,2)。若允许上下左右移动，最短路径长度是多少？只输出数字。", "6"),
        ("在坐标平面上有三个候选监测塔：T1(0,0), T2(4,0), T3(2,3)。哪两个塔之间距离最短？输出格式 `T?-T?`。", "T1-T3"),
        ("有三个立方体投影：前视图宽 3 高 2，全为实心；侧视图宽 2 高 2，只有右上缺失；俯视图为 3x2，全为实心。以下哪个三维体积最小且满足条件：A=5, B=6, C=7。只输出字母。", "B"),
        ("棋盘上黑格定义为 x+y 为偶数。给定点 (1,4)、(2,5)、(6,6) 中有几个黑格？只输出数字。", "2"),
        ("某三角形三个顶点分别是 (1,1),(5,1),(3,4)。其底边是哪一条边？按两个端点输出，如 `(1,1)-(5,1)`。", "(1,1)-(5,1)"),
        ("一个机器人在方格图中从 (2,2) 出发，依次执行 上、右、右、下、左。最终坐标是多少？格式 `(x,y)`。", "(3,2)"),
        ("10x10 网格中要放两个激光器，候选组合有 A={(2,2),(8,2)}, B={(2,2),(2,8)}, C={(5,1),(5,9)}。若希望覆盖不同的行数最多，应选哪组？只输出 A/B/C。", "B"),
        ("一个 5x5 字符矩阵要求主对角线填 X，副对角线填 O，中心格如果重叠则填 *。问矩阵中心字符是什么？只输出一个字符。", "*"),
        ("在 6x6 棋盘中，从 (1,1) 到 (6,6) 只允许向右或向下。若必须经过 (3,3)，则路径被分成两段。第一段最少步数是多少？只输出数字。", "4"),
        ("两个矩形 R1: 左下(0,0) 右上(4,3)，R2: 左下(2,1) 右上(5,4)。它们重叠区域面积是多少？只输出数字。", "4"),
        ("某迷宫存在两条最短路，长度都为 8。若评分规则优先选择转弯次数更少的路线，而路线 A 转弯 3 次，路线 B 转弯 1 次，应选哪条？只输出 A/B。", "B"),
        ("给定三点 (0,0),(0,5),(4,0)，哪一点是直角顶点？只输出坐标。", "(0,0)"),
    ]
    for prompt, answer in spatial_prompts:
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A6-{idx:03d}",
            module="A6",
            subtype="spatial_symbolic_reasoning",
            prompt=prompt,
            answer=answer,
            scoring_method="exact_match" if not answer.isdigit() else "numeric_em",
            scoring_params={"response_max_tokens": 768},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="spatial_symbolic_reasoning",
            notes="QB-v1.1 A6 spatial/symbolic item inspired by ZebraLogic and geometry-constrained reasoning tasks.",
        )
        idx += 1

    rule_prompts = [
        ("观察示例：`3#5 -> 16`，`4#2 -> 10`，`6#1 -> 8`。已知规则对两个数字 a,b 先做一次线性组合，再加一个固定偏移。问 `7#3` 等于多少？只输出数字。", "22"),
        ("某简化干支纪年只保留天干 [甲,丙,戊,庚,壬] 五项，地支仍按 [子,丑,寅,卯,辰] 循环。第 1 年记为 甲子。问第 8 年记为什么？只输出两个汉字。", "戊寅"),
        ("字符压缩示例：`ABBC -> A1B2C1`，`CCAA -> C2A2`。若再规定压缩后删去所有 `1`，问 `ABBCCCDA` 压缩结果是什么？", "AB2C3DA"),
        ("观察计算示范：`f(2,3)=13`，`f(4,1)=21`，`f(3,2)=17`。若规则是 `a*a + 3*b`，则 `f(5,2)` 等于多少？只输出数字。", "31"),
        ("工具组合规则：钳子可把 `AB` 变 `BA`；压模可把相邻相同字符 `XX` 变 `Y`；切刀可删除最右字符。若从 `AABB` 出发，先压模一次，再钳子一次，再切刀一次，结果是什么？", "YA"),
        ("矩阵填充规则：第一行从左到右写 1,2,3；第二行从右到左继续写 4,5,6；第三行再从左到右继续。问 3x3 矩阵中心数字是多少？", "5"),
        ("观察示例：`LIMA -> 4214`，`ECHO -> 3154`。规则是把每个字母替换成它在单词中按字母序排名的位置。问 `KILO` 的编码是什么？", "3142"),
        ("信息还原规则：`[2]ab[3]c` 展开为 `ababccc`。如果再对展开结果每隔两个字符取一个，`[1]x[2]yz[2]a` 的最终结果是什么？", "xyza"),
        ("规则推导：示例 `12 -> 1+2=3 -> 3*2=6`，`34 -> 3+4=7 -> 7*2=14`。问 `58` 的结果是多少？只输出数字。", "26"),
        ("某替换系统中，`sun -> 3-1-2`，`moon -> 2-3-3-1`。规则是按照每个字母在单词中首次出现位置编号。问 `level` 的编码是什么？", "1-2-3-2-1"),
    ]
    for prompt, answer in rule_prompts:
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A6-{idx:03d}",
            module="A6",
            subtype="rule_induction_transformation",
            prompt=prompt,
            answer=answer,
            scoring_method="exact_match" if not answer.isdigit() else "numeric_em",
            scoring_params={"response_max_tokens": 768},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="rule_induction_transformation",
            notes="QB-v1.1 A6 rule-induction item inspired by BBH/BBEH symbolic transformation patterns.",
        )
        idx += 1

    long_context_prompts = [
        ("下面有四段交织记录：\n1) 北仓项目由 A 组负责，A 组的联系人是 Yue。\n2) 只有负责北仓项目的组本周去海港站点演示。\n3) 去海港站点演示的联系人需要同时出席周五复盘。\n4) 本周去海港站点演示的是唯一需要周五复盘的联系人。\n问周五复盘的联系人是谁？只输出姓名。", "Yue"),
        ("阅读混合描述：红盒在蓝盒左侧；绿盒不在最左；黄盒紧挨着绿盒右侧；蓝盒不在最右。问从左到右的盒子顺序是什么？格式 `红-蓝-绿-黄`。", "红-蓝-绿-黄"),
        ("三段交织文本：\n甲队使用温度传感器；使用温度传感器的队伍住在二号营地；住在二号营地的队伍明天先出发。\n问明天先出发的是哪支队伍？", "甲队"),
        ("某棋局无解说，只给出观测：黑方每次走子后，白方都只能把一个子向前移动一格；当某方棋子走到最远一行时局面结束；棋盘共有 8 列。问这更像哪类经典棋盘规则：`单向竞速` 还是 `围捕消除`？只输出二选一。", "单向竞速"),
        ("在一组单词中：`stone, tones, notes, onset, seton, silent`。若要求选出与 `stone` 完全同字母重排的所有词，并按字母序输出，用逗号分隔，答案是什么？", "notes,onset,seton,tones"),
        ("混合档案记载：Dana 只审阅最短续约窗口的合同；网络合同的续约窗口最短；任何被 Dana 审阅的合同都需要法务复核。问需要法务复核的是哪份合同？", "网络合同"),
        ("位置关系描述：杯子在书的右边，灯在杯子的左边但在书的右边，盒子在灯的右边。问从左到右的顺序是什么？格式 `书-灯-盒子-杯子`。", "书-灯-盒子-杯子"),
        ("交织文本中提到：只有拿到红色令牌的人才能进入东门；Rin 拿到了红色令牌；进入东门的人会被记录为第一批到达。问谁会被记录为第一批到达？", "Rin"),
        ("多段笔记：A 与 B 是同事；同事中只有负责晨报的人会参加 7 点会议；B 负责晨报。问谁参加 7 点会议？若有多人请按字母序逗号分隔。", "B"),
        ("深度关系题：球在盒子里，盒子在柜子里，柜子在房间里。若要直接把球移到房间外，最少要先打开多少个容器？只输出数字。", "3"),
    ]
    for prompt, answer in long_context_prompts:
        _add_item(
            rewrites,
            items,
            make_rewrite_and_item,
            question_id=f"A6-{idx:03d}",
            module="A6",
            subtype="long_context_relational_reasoning",
            prompt=prompt,
            answer=answer,
            scoring_method="exact_match" if not answer.isdigit() else "numeric_em",
            scoring_params={"response_max_tokens": 1024},
            source_rows=_pick_sources(source_rows, idx, width=2),
            difficulty="hard",
            quota_tag="long_context_relational_reasoning",
            notes="QB-v1.1 A6 long-context relational item inspired by BBH / Zebra-style relational reasoning and user-requested interwoven text tasks.",
        )
        idx += 1

    return rewrites, items
