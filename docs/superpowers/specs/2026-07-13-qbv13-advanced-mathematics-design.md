# QB-v1.3 高阶数学强化题库设计

## 目标

在不改变既有 18 个模块、Run 语义和历史结果可读性的前提下，为 `QB-v1.3` 的 `A1` 增加 240 道默认参与正式评测的高阶数学题，以及 160 道默认不参与 Run 的同标准备选题。新增题须覆盖高中高阶、数学竞赛和大学数学基础，提供稳定的自动评分、明确的难度分层和可用于模型区分的元数据。

## 范围与非目标

### 范围

- 正式题：`A1-H001` 至 `A1-H240`，`qa_status=ready`，默认会被常规 A1 Run 选中。
- 备选题：`A1-R001` 至 `A1-R160`，`qa_status=frozen`，默认不会被常规 Run 选中。
- 每道题写入正式题库、改写草案、候选来源、题库摘要及 SQLite bootstrap 可读取的 live 文件。
- 增加难度、前置知识、推理结构和可区分性 metadata；前端题库筛选与 API 继续兼容既有 `difficulty` 字段。
- 增加针对题数、难度配额、题号、可评分性、备选题排除和重复结构的测试。
- 将常规 Run 的默认题目选择条件由 `ready/frozen` 改为仅 `ready`；显式 `question_ids` 仍可运行指定的 `frozen` 备选题，保持人工预评测能力。

### 非目标

- 不修改现有 A1 的 50 道历史题，也不重新计算历史 Run。
- 不直接复制 AMC、AIME、Putnam、MIT 习题或任何受版权保护题面、答案、解析。
- 不新增 A7/A8；所有题仍属于 A1，以免改变既有 18 模块统计、批次比较和报告口径。
- 不把开放式长证明作为单一得分依据；需要证明时只评分可验证的结论和受限证明骨架。

## 能力来源与知识范围

新增题以公开课程和竞赛的知识覆盖作为范围参考，而非题目复刻来源：

- [MAA AMC](https://maa.org/student-programs/amc/)：高中竞赛级代数、几何、数论与概率边界。
- [AoPS Olympiad Algebra](https://artofproblemsolving.com/wiki/index.php/Algebra/Olympiad)：多项式、函数方程、AM-GM、Cauchy、Schur、Jensen 等竞赛代数和不等式方法。
- [MIT 18.200 Discrete Applied Mathematics](https://ocw.mit.edu/courses/18-200-principles-of-discrete-applied-mathematics-spring-2024/resources/lecture-notes/)：鸽巢、概率、计数、生成函数、匹配、模运算、线性规划、编码。
- [MIT 18.600 Probability](https://ocw.mit.edu/courses/18-600-probability-and-random-variables-fall-2019/pages/lecture-notes/)：条件概率、离散随机变量、期望/方差、条件期望、马尔可夫链、极限定理。
- [MIT Putnam Seminar](https://ocw.mit.edu/courses/18-a34-mathematical-problem-solving-putnam-seminar-fall-2018/pages/assignments/)：递推、概率、线性代数与抽象代数的问题求解结构。

## 题目分层

保留旧字段 `difficulty` 的 `easy | medium | hard`，使老客户端、题库 schema 和历史数据继续有效；新增可选字段 `difficulty_tier` 提供精细层级。

| `difficulty_tier` | 题数 | 旧字段映射 | 能力含义 |
|---|---:|---|---|
| `foundation` | 20 | `medium` | 高中必修进阶；需要多步建模或非直接公式 |
| `advanced_hs` | 60 | `hard` | 高中选修/高考压轴；跨章节代数、概率、解析几何 |
| `olympiad` | 80 | `hard` | 竞赛方法；不等式、构造、整除、组合不变量、函数方程 |
| `undergraduate` | 60 | `hard` | 离散数学、概率论、线性代数、优化、基础抽象代数 |
| `stretch` | 20 | `hard` | 强模型分层；二阶矩、生成函数、谱/矩阵、编码与复杂组合 |

160 道备选题按同样比例分配为 `14/40/52/40/14`。`difficulty` 仅维持向后兼容；新报告和题库 UI 应优先展示 `difficulty_tier`。

## 知识域与配额

正式题与备选题使用相同知识域比例；为保证题数为整数，备选题按下表的预先固定配额取整。

| 子类型 | 正式题 | 备选题 | 典型能力与可验证输出 |
|---|---:|---:|---|
| `advanced_algebra` | 30 | 20 | 多项式根与系数、函数方程、参数方程、对称式；根、参数范围或有限集合 |
| `inequality_optimization` | 22 | 14 | AM-GM、Cauchy、凸性、极值；最小/最大值及等号条件标签 |
| `number_theory` | 24 | 16 | 同余、阶、LTE、丢番图、原根基础；整数、模类或解数 |
| `combinatorics` | 24 | 16 | 容斥、递推、双计数、鸽巢、组合构造；整数或结构化计数 |
| `discrete_probability` | 28 | 19 | 条件概率、Bayes、期望、方差、停时的有限版本；最简分数或有理数对 |
| `graph_theory` | 24 | 16 | 树、匹配、Euler/Hamilton 条件、染色、最短路、图不变量；数值、布尔或顶点集合 |
| `linear_algebra` | 24 | 16 | 秩、特征值、二次型、线性变换、有限维空间；矩阵、维数、特征多项式或布尔 |
| `recurrence_generating_functions` | 18 | 12 | 线性递推、特征根、生成函数系数；整数、闭式参数或模值 |
| `geometry_analytic` | 16 | 11 | 向量、圆锥曲线、复平面、面积/角度；精确表达式或有理数 |
| `algorithms_discrete_optimization` | 12 | 8 | 网络流、动态规划的数学化、小型线性规划；最优值与规范化解 |
| `abstract_algebra_intro` | 10 | 7 | 群、环、同态、有限域入门；阶、子群数或运算表性质 |
| `information_coding` | 8 | 5 | 熵、Huffman、线性码、校验矩阵；熵值、码距或纠错结论 |
| **合计** | **240** | **160** | |

任何单一子类型不得超过 30 题；每个子类型至少覆盖两档 `difficulty_tier`，并至少包含一题跨域综合题。

## 单题数据契约

每道新增题都沿用 `final_bank_item` 的既有字段，并额外写入下列字段：

```json
{
  "difficulty": "hard",
  "difficulty_tier": "undergraduate",
  "prerequisites": ["conditional_probability", "linearity_of_expectation"],
  "reasoning_profile": {
    "minimum_nontrivial_steps": 4,
    "primary_method": "conditioning",
    "secondary_methods": ["symmetry"],
    "common_traps": ["treating dependent draws as independent"]
  },
  "discrimination_profile": {
    "item_family": "finite_markov_expectation",
    "variant_type": "cross_concept",
    "target_error_modes": ["wrong_state_space", "missing_boundary_case"]
  },
  "answer_contract": {
    "format": "reduced_fraction",
    "canonical_answer": "17/42",
    "accepted_equivalents": ["17/42"]
  }
}
```

`difficulty_tier`、`prerequisites`、`reasoning_profile`、`discrimination_profile` 和 `answer_contract` 均为新增可选字段，旧题可缺省。`scoring_method` 必须仍使用既有确定性评分器，或新增有单元测试的确定性评分器。

## 可评分性与解答格式

1. 数值题使用 `numeric_em`，要求最终行 `答案：[结果]`；有理数必须为最简分数，根式和复数使用预先规定的规范形式。
2. 集合、序列、矩阵和图顶点集使用 `exact_match` 或规范化后的集合比较；评分器先排序、去空白、统一分隔符，再比较。
3. 有限状态图、匹配、路径或编码题使用结构化 JSON/CSV 输出，评分器验证合法性与目标值，不只比较文字。
4. 证明型题的最终得分只基于可判定结论、等号条件或指定的有限证明骨架；模型的自然语言推导会被保存供人工复核，但不作为自动评分唯一依据。
5. 每题必须有一个独立的参考复算过程：手工推导加一个不依赖模型调用的 Python 验算器。复杂题还要有小规模穷举或第二种等价算法交叉验证。

## 区分度与反同构规则

每个 `item_family` 至少包含三种不同的推理结构：

1. 直接方法：验证基础定义、公式或定理使用。
2. 概念辨析：专门诱发一个可定义的错误模型，例如错误独立性、错用特征根、遗漏边界。
3. 跨概念综合：至少组合两个前置知识点，并明确其依赖顺序。

生成和审计阶段必须执行：

- 题干去数字化后的文本相似度门禁为 `0.78`；超过门限的题对进入人工审计。
- 不允许同一答案、同一方法、同一输出格式的三题以上只改变参数。
- 每题的 `reasoning_profile.minimum_nontrivial_steps` 至少为 2；`olympiad`、`undergraduate` 和 `stretch` 至少为 3、4、5。
- 每题的 `common_traps` 至少一个；同一陷阱不得支配单一子类型超过 40%。
- 备选题只能替换同一 `subtype` 且相同 `difficulty_tier` 的正式题，避免轮换改变纵向统计口径。

## 生成、轮换与运行行为

生成器在 QB-v1.3 基础上读取新的自有题目定义，生成候选、改写、正式项和摘要；不覆盖原有 `A1-001` 至 `A1-050`。正式项通过 live `final_bank_items.jsonl` 进入 SQLite bootstrap。Run 引擎的默认选择器只选择 `ready`；备选项仍存在于 `final_bank_items.jsonl`，但以 `frozen` 状态被默认选择器排除，只有显式 `question_ids` 能运行。

轮换工具必须接受显式 `--out-question-id` 和 `--reserve-question-id`，并验证二者的 `module=A1`、`subtype`、`difficulty_tier`、`scoring_method` 和 `answer_contract.format` 一致。轮换改变 live 题目的 `qa_status`，保留 `rotation_history`，不修改既有 Run 记录。

## 前端与报告

- 题库管理页在既有难度筛选旁增加 `difficulty_tier` 和数学子类型筛选；缺失该字段的旧题显示“历史未分层”。
- Run 创建页继续默认选择全部 `ready` 题；`frozen` 的 160 道备选题只能通过显式题号选择或轮换后进入正式 Run。
- 报告的 A1 章节增加二维统计：按 `difficulty_tier` 和按 `subtype`；总分仍保留与历史运行可比较的 A1 总分。
- 逐题详情展示前置知识、方法、易错点和答案契约；不会向模型泄露这些 metadata。

## 验收标准

1. `QB-v1.3` 的默认正式 Run 题数从 1110 增至 1350，`A1` 从 50 增至 290；题库目录另含 160 道 `frozen` 备选题与 30 道 `pilot`，live 行数为 1540。
2. 新增 240 道正式题和 160 道备选题均有唯一题号、完整 provenance、难度层、子类型、答案契约和确定性评分。
3. 默认 Run 包含全部 240 道正式题，不包含 160 道 `frozen` 备选题和 30 道 `pilot`。
4. 240 道正式题符合 `20/60/80/60/20` 五档难度配额及十二个正式子类型配额；160 道备选题符合 `14/40/52/40/14` 配额及表中固定的备选子类型配额。
5. 每道题通过独立复算或穷举验证；错误格式、错误边界、错误约分、错误集合元素和典型易错答案都会被测试拒绝。
6. 相似度、同构和陷阱分布门禁通过，审计产物记录所有题对和人工放行理由。
7. 前端筛选、Run 创建、逐题详情、报告统计和 SQLite bootstrap 对旧题与新题都兼容。
8. 完整后端测试、题库校验、前端静态测试、生产构建与小规模 Smoke Run 全部通过。
