# QB-v1.1 题库升级说明

`QB-v1.1` 是在保留 `QB-v1.0` 历史基线的前提下，对 A 类能力题库做的一次结构升级。升级目标有两个：

1. 为 A 类补上独立的逻辑推理能力轴 `A6`
2. 把原本偏基础的 `A2` 升级为高难编程能力模块

## 一、版本关系

| 版本 | 用途 | 说明 |
|------|------|------|
| `QB-v1.0` | 历史评测基线 | 用于 `MiniMax-M2.7` / `MiniMax-M3` 既有结果可追溯 |
| `QB-v1.1` | 新正式题库 | 用于后续模型评测与题库扩展 |

`QB-v1.0` 相关产物会保留归档，不覆盖历史结论。工作区当前默认生成与加载的是 `QB-v1.1`。

## 二、A 类新结构

| 模块 | 题数 | 子类 | 目标能力 |
|------|------|------|----------|
| `A1` | 50 | `math_reasoning` | 多步数学计算与答案抽取 |
| `A2` | 50 | `constrained_program_synthesis` / `long_code_comprehension` / `stateful_data_processing` / `bug_fix_and_patch_reasoning` | 高难编程、代码理解、状态型数据处理、补丁推理 |
| `A3` | 50 | `format_constraint` / `content_constraint` / `length_constraint` / `combo_constraint` | 指令遵循 |
| `A4` | 30 | `reading_comprehension` / `summarization` / `multi_hop_qa` | 阅读理解、摘要、多跳问答 |
| `A5` | 30 | `knowledge_mcq` | 知识问答 |
| `A6` | 50 | `stateful_simulation` / `spatial_symbolic_reasoning` / `rule_induction_transformation` / `long_context_relational_reasoning` | 逻辑推理、规则归纳、空间推理、长上下文关系抽取 |

A 类总量由 `200` 扩到 `260`。

## 三、A6 的设计依据

`A6` 不再把逻辑推理塞进现有模块，而是拆成独立能力轴。设计参考了以下 benchmark 的方法论：

- `BIG-Bench Hard / BBEH`
  - 多步推理、符号规则、规则归纳、混合长上下文推断
- `ZebraLogic`
  - 约束满足、位置关系、实体关系排列
- `PlanBench`
  - 状态转移、规划、动作副作用与目标可达性
- 你提供的题型方向
  - 日记整理、棋盘图案、干支纪年、函数求交、火车售票、交织文本解读、工具组合、日志解析、字符矩阵、机器操作、三维重建、深度关系等

### A6 子类说明

| 子类 | 题数 | 题型举例 | 默认评分 |
|------|------|----------|----------|
| `stateful_simulation` | 15 | 机器操作、售票、抽奖、库存流水、日志状态追踪 | `exact_match` / `numeric_em` |
| `spatial_symbolic_reasoning` | 15 | 棋盘、几何、激光布局、拼图、迷宫 | `exact_match` / `numeric_em` |
| `rule_induction_transformation` | 10 | 干支纪年、字符矩阵、压缩还原、示例归纳 | `exact_match` / `numeric_em` |
| `long_context_relational_reasoning` | 10 | 交织文本、深度关系、观棋规则、集合筛选 | `exact_match` / `numeric_em` |

## 四、A2 升级思路

原 `A2` 的 40 题主要由：

- 基础函数实现
- 简单代码执行预测
- 基础 bug 修复

构成，难度偏低。`QB-v1.1` 中的 `A2` 改成 50 题，并按更高难的公开 benchmark 方法升级：

- `LiveCodeBench`
  - 真实风格、时效性、执行验证
- `APPS`
  - 多重约束程序编写
- `BigCodeBench`
  - 长代码理解、多 helper 组合、工程化风格
- `EvalPlus / HumanEval+`
  - 更严格的隐藏测试与边界覆盖
- `SWE-bench Lite`
  - 更真实的 bug 修复与 patch 推理，但本版只下沉到单函数/单文件级

### A2 子类说明

| 子类 | 题数 | 目标能力 | 默认评分 |
|------|------|----------|----------|
| `constrained_program_synthesis` | 15 | 多重约束编程、三维数组/复杂数据结构变换 | `exec` |
| `long_code_comprehension` | 10 | 阅读中长代码并复现 stdout 或中间结果 | `exact_match` |
| `stateful_data_processing` | 15 | 日志解析、状态机、矩阵填充、批处理流程 | `exec` |
| `bug_fix_and_patch_reasoning` | 10 | 修复逻辑错误并通过隐藏测试 | `exec` |

## 五、候选层来源如何更新

`QB-v1.1` 不是只改正式题。候选层 `normalized/` 新增了四个“方法快照”来源：

| 文件 | 对应模块 | 参考方法 |
|------|----------|----------|
| `bbh_bbeh_logic_candidates.jsonl` | `A6` | BIG-Bench Hard / BBEH |
| `zebra_planbench_logic_candidates.jsonl` | `A6` | ZebraLogic / PlanBench |
| `apps_livecodebench_coding_candidates.jsonl` | `A2` | APPS / LiveCodeBench |
| `bigcode_evalplus_swebench_candidates.jsonl` | `A2` | BigCodeBench / EvalPlus / SWE-bench Lite |

这些文件的作用不是“直接当正式题库”，而是：

1. 固定新模块的公开方法来源
2. 让改写层和正式层有明确 provenance
3. 为后续继续扩题留下结构化入口

## 六、评分原则

`QB-v1.1` 继续优先使用程序化评分，不引入主观商业 judge：

| 评分方法 | 适用题型 |
|----------|----------|
| `numeric_em` | 唯一数字答案 |
| `exact_match` | 唯一字符串或唯一规范化答案 |
| `exec` | 函数实现、patch、数据处理题 |
| `rule` | 严格格式题 |

新增加的 `A2/A6` 默认都要求：

- 题面给出稳定输出格式
- ground truth 唯一
- 或者可通过隐藏测试/执行验证确定

## 七、对评测系统的影响

`QB-v1.1` 上线后，以下层都会联动：

- `generate_formal_bank.py`
  - 默认生成 `QB-v1.1`
- `evaluation_engine.py`
  - `capability_score` 统计从 `A1-A5` 改为 `A1-A6`
- 前端
  - 模块筛选与运行创建加入 `A6`
- 汇总与报告
  - 后续 `MiniMax-M2.7 / M3` 若要对比新版题库，必须单独跑 `QB-v1.1`

## 八、为什么不直接覆盖旧结论

因为 `QB-v1.1` 改动的是题库内容，不只是评分配置，所以：

- 旧 `QB-v1.0` 分数仍是旧题库条件下的结论
- 新版结果必须重新评测后才有可比意义
- 不能把 `QB-v1.0` 与 `QB-v1.1` 的总分直接混算
