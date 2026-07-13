# QB-v1.3 高阶数学强化题库实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 QB-v1.3 的 A1 增加 240 道默认运行的高阶数学题与 160 道默认排除的轮换备选题，并让 API、前端、报告、SQLite 与评分系统可识别精细难度和数学元数据。

**Architecture:** 新建纯数据的 `advanced_math_bank.py`，由 `generate_qbv13_bank.py` 合并其候选、改写和正式题；题目全部由本地确定性蓝图生成，题面与答案不来自公开题目复刻。保留旧 `difficulty`，新增可选 `difficulty_tier` 与 JSON 元数据；SQLite 将该 tier 投影为可检索列，`full_item_json` 仍是唯一完整存储。

**Tech Stack:** Python 3、FastAPI、SQLite、JSON Schema、React 18、Vite、Node test、unittest。

---

### Task 1: 固化高级数学数据契约和默认 Run 语义

**Files:**
- Modify: `schema/final_bank_item.schema.json`
- Modify: `scripts/evaluation_engine.py:191-218`
- Modify: `tests/test_evaluation_system.py`
- Create: `tests/test_advanced_math_contract.py`

- [ ] **Step 1: 写失败的 schema/选择器测试**

```python
def test_default_filter_excludes_frozen_reserve_items():
    items = [
        {"question_id": "A1-H001", "version": "QB-v1.3", "module": "A1", "qa_status": "ready"},
        {"question_id": "A1-R001", "version": "QB-v1.3", "module": "A1", "qa_status": "frozen"},
    ]
    assert [item["question_id"] for item in filter_items(items)] == ["A1-H001"]
    assert [item["question_id"] for item in filter_items(items, question_ids=["A1-R001"])] == ["A1-R001"]


def test_advanced_math_metadata_schema_is_backward_compatible():
    schema = json.loads((ROOT / "schema" / "final_bank_item.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["difficulty_tier"]["enum"] == ["foundation", "advanced_hs", "olympiad", "undergraduate", "stretch", None]
    assert props["prerequisites"]["items"] == {"type": "string"}
    assert {"reasoning_profile", "discrimination_profile", "answer_contract"} <= set(props)
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_contract -v`  
Expected: `filter_items` 返回 frozen 题，且 schema 不认识 `difficulty_tier`。

- [ ] **Step 3: 实现最小数据契约**

在 schema 中追加以下可选字段：

```json
"difficulty_tier": {"type": ["string", "null"], "enum": ["foundation", "advanced_hs", "olympiad", "undergraduate", "stretch", null]},
"prerequisites": {"type": "array", "items": {"type": "string"}},
"reasoning_profile": {"type": ["object", "null"]},
"discrimination_profile": {"type": ["object", "null"]},
"answer_contract": {"type": ["object", "null"]}
```

将 `filter_items` 的默认集合替换为：

```python
filtered = items if question_ids else [
    item for item in items if item.get("qa_status", "ready") == "ready"
]
```

- [ ] **Step 4: 运行针对性测试**

Run: `python -m unittest tests.test_advanced_math_contract tests.test_evaluation_system -v`  
Expected: PASS，显式题号可运行 frozen，常规模块和 smoke Run 不可运行 frozen。

- [ ] **Step 5: 提交**

```bash
git add schema/final_bank_item.schema.json scripts/evaluation_engine.py tests/test_advanced_math_contract.py tests/test_evaluation_system.py
git commit -m "feat: add advanced math metadata and reserve exclusion"
```

### Task 2: 扩展 SQLite、API 与题库筛选

**Files:**
- Modify: `scripts/sqlite_runtime.py:380-470, 900-1040`
- Modify: `scripts/evaluation_api.py:596-632`
- Modify: `scripts/evaluation_engine.py:1082-1115`
- Modify: `tests/test_review_workflow.py`
- Create: `tests/test_advanced_math_repository.py`

- [ ] **Step 1: 写失败的 repository/API 测试**

```python
def test_difficulty_tier_is_persisted_and_filterable(tmp_path):
    store = SQLiteStore(db_path=tmp_path / "evaluation.sqlite", runs_dir=tmp_path / "runs", bank_items_path=tmp_path / "bank.jsonl")
    store.create_bank_item({**make_math_item("A1-H001"), "difficulty_tier": "olympiad"})
    store.create_bank_item({**make_math_item("A1-H002"), "difficulty_tier": "undergraduate"})
    result = store.list_bank_items(version="QB-v1.3", difficulty_tier="olympiad")
    assert [row["question_id"] for row in result["items"]] == ["A1-H001"]
    assert store.get_bank_facets(version="QB-v1.3", module="A1")["difficulty_tiers"] == [{"value": "olympiad", "count": 1}, {"value": "undergraduate", "count": 1}]
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_repository -v`  
Expected: `difficulty_tier` 参数和 facet 不存在。

- [ ] **Step 3: 实现存储投影与 API 参数**

在 `_init_schema` 中加入：

```python
self._ensure_column(conn, "bank_items", "difficulty_tier", "TEXT")
conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_difficulty_tier ON bank_items(difficulty_tier)")
```

在写入/更新 `bank_items` 时，把 `item.get("difficulty_tier")` 同步写入列；为 `list_bank_items`、`EvaluationRunService.list_bank_items` 与 `/api/bank/items` 添加 `difficulty_tier: str | None`。`get_bank_facets` 返回按 value 排序的 `difficulty_tiers`。

- [ ] **Step 4: 运行针对性测试**

Run: `python -m unittest tests.test_advanced_math_repository tests.test_review_workflow -v`  
Expected: PASS，旧题仍能读取且其 `difficulty_tier` 为 `None`。

- [ ] **Step 5: 提交**

```bash
git add scripts/sqlite_runtime.py scripts/evaluation_api.py scripts/evaluation_engine.py tests/test_advanced_math_repository.py tests/test_review_workflow.py
git commit -m "feat: filter bank items by advanced math tier"
```

### Task 3: 实现结构化答案规范化与确定性数学评分

**Files:**
- Create: `scripts/advanced_math_scoring.py`
- Modify: `scripts/evaluation_engine.py`（将新 scoring method 分派到数学评分器）
- Create: `tests/test_advanced_math_scoring.py`

- [ ] **Step 1: 写失败的评分器测试**

```python
def test_reduced_fraction_requires_coprime_numerator_and_denominator():
    assert score_advanced_math("答案：17/42", {"format": "reduced_fraction", "canonical_answer": "17/42"})[0] == 1.0
    assert score_advanced_math("答案：34/84", {"format": "reduced_fraction", "canonical_answer": "17/42"})[0] == 0.0


def test_vertex_set_is_order_insensitive_but_validated():
    params = {"format": "vertex_set", "canonical_answer": ["a", "c", "f"], "universe": ["a", "b", "c", "d", "e", "f"]}
    assert score_advanced_math("答案：{f,a,c}", params)[0] == 1.0
    assert score_advanced_math("答案：{a,c,x}", params)[0] == 0.0


def test_matrix_requires_exact_shape_and_entries():
    params = {"format": "matrix", "canonical_answer": [[1, 0], [-2, 3]]}
    assert score_advanced_math("答案：[[1,0],[-2,3]]", params)[0] == 1.0
    assert score_advanced_math("答案：[[1,0,-2,3]]", params)[0] == 0.0
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_scoring -v`  
Expected: import error，因为评分器不存在。

- [ ] **Step 3: 实现评分器**

提供下列纯函数并只返回 `(score, details)`：

```python
def extract_answer_payload(text: str) -> str: ...
def parse_reduced_fraction(payload: str) -> tuple[int, int] | None: ...
def parse_vertex_set(payload: str, universe: list[str]) -> list[str] | None: ...
def parse_matrix(payload: str) -> list[list[int]] | None: ...
def score_advanced_math(text: str, params: dict) -> tuple[float, dict]: ...
```

支持的 `answer_contract.format` 固定为 `integer`、`reduced_fraction`、`mod_class`、`finite_set`、`vertex_set`、`matrix`、`ordered_tuple`、`boolean`。未识别格式必须得 0 分并记录 `unsupported_answer_format`；不得调用模型或使用浮点近似作为最终正确性判定。

- [ ] **Step 4: 接入引擎并验证**

Run: `python -m unittest tests.test_advanced_math_scoring tests.test_evaluation_system -v`  
Expected: PASS；Run item 使用 `scoring_method="advanced_math"` 时输出有 `score_details`。

- [ ] **Step 5: 提交**

```bash
git add scripts/advanced_math_scoring.py scripts/evaluation_engine.py tests/test_advanced_math_scoring.py
git commit -m "feat: add deterministic advanced math scoring"
```

### Task 4: 创建 400 道自有数学题蓝图与独立复算器

**Files:**
- Create: `scripts/advanced_math_bank.py`
- Create: `tests/test_advanced_math_bank.py`

- [ ] **Step 1: 写失败的题库配额与复算器测试**

```python
def test_advanced_math_blueprints_have_exact_ids_and_quotas():
    ready, reserve = build_advanced_math_bank()
    assert [item["question_id"] for item in ready] == [f"A1-H{index:03d}" for index in range(1, 241)]
    assert [item["question_id"] for item in reserve] == [f"A1-R{index:03d}" for index in range(1, 161)]
    assert Counter(item["difficulty_tier"] for item in ready) == Counter(foundation=20, advanced_hs=60, olympiad=80, undergraduate=60, stretch=20)
    assert Counter(item["difficulty_tier"] for item in reserve) == Counter(foundation=14, advanced_hs=40, olympiad=52, undergraduate=40, stretch=14)


def test_every_advanced_math_item_recomputes_its_canonical_answer():
    for item in [*build_advanced_math_bank()[0], *build_advanced_math_bank()[1]]:
        assert recompute_answer(item["math_blueprint"]) == item["answer_contract"]["canonical_answer"]
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_bank -v`  
Expected: import error，因为蓝图模块不存在。

- [ ] **Step 3: 实现蓝图工厂和固定配额**

定义不可变 `TOPIC_QUOTAS`、`TIER_QUOTAS` 与 `RESERVE_TOPIC_QUOTAS`，值必须与设计文档表格一致。每个题目由以下工厂创建：

```python
def make_math_item(*, question_id, pool, subtype, tier, blueprint, prompt, answer_contract, prerequisites, reasoning_profile, discrimination_profile):
    return {
        "question_id": question_id,
        "version": "QB-v1.3",
        "module": "A1",
        "subtype": subtype,
        "item_format": "single_turn",
        "difficulty": "medium" if tier == "foundation" else "hard",
        "difficulty_tier": tier,
        "drift_role": "capability",
        "prompt_template": prompt + "\n请写出推理；最后一行严格写作 `答案：[结果]`。",
        "ground_truth": answer_contract["canonical_answer"],
        "scoring_method": "advanced_math",
        "scoring_params": answer_contract,
        "answer_contract": answer_contract,
        "qa_status": "ready" if pool == "formal" else "frozen",
        "rotation_policy": {"replaceable": True, "rotation_priority": 1, "expected_lifespan_days": 180},
        "math_blueprint": blueprint,
        "prerequisites": prerequisites,
        "reasoning_profile": reasoning_profile,
        "discrimination_profile": discrimination_profile,
    }
```

题面必须由 400 个独立的 `blueprint` 生成，不使用参数替换循环。每个 blueprint 固定 `family`、输入、复算函数、答案格式和至少一个 `common_traps`；其 `source_candidate_ids` 使用 `internal-advanced-math-<question_id-lower>`，`source_names` 为 `QB-v1.3 advanced mathematics original`，`direct_public_reuse=False`。

- [ ] **Step 4: 实现复算器并运行测试**

`recompute_answer` 采用 family 分派；例如使用 `math.comb` 验证组合题、整数高斯消元或余子式验证矩阵题、枚举不超过 12 个顶点的小图、`fractions.Fraction` 验证概率题。任何未知 family、非法 blueprint 或复算值不一致都必须抛出 `ValueError`。

Run: `python -m unittest tests.test_advanced_math_bank -v`  
Expected: PASS，400 道题均由独立复算器验证。

- [ ] **Step 5: 提交**

```bash
git add scripts/advanced_math_bank.py tests/test_advanced_math_bank.py
git commit -m "feat: add QB-v1.3 advanced mathematics blueprints"
```

### Task 5: 生成候选层、改写层、正式项与可审计清单

**Files:**
- Modify: `scripts/generate_qbv13_bank.py`
- Create: `manifests/qbv13_advanced_math_audit.json`
- Modify: `manifests/final_bank_summary_qbv1_3.json`
- Modify: `final_bank_specs/generated/final_bank_items_qbv1_3.jsonl`
- Modify: `rewrite_drafts/generated/rewrite_drafts_qbv1_3.jsonl`
- Modify: `final_bank_specs/generated/final_bank_items.jsonl`
- Modify: `rewrite_drafts/generated/rewrite_drafts.jsonl`
- Create: `normalized/qbv13_advanced_math_candidates.jsonl`
- Create: `tests/test_qbv13_advanced_math_generation.py`

- [ ] **Step 1: 写失败的生成集成测试**

```python
def test_qbv13_generation_includes_formal_and_reserve_math_items():
    rewrites, items, summary = build_qbv13()
    formal = [item for item in items if item["question_id"].startswith("A1-H")]
    reserve = [item for item in items if item["question_id"].startswith("A1-R")]
    assert len(formal) == 240
    assert len(reserve) == 160
    assert Counter(item["qa_status"] for item in formal) == Counter(ready=240)
    assert Counter(item["qa_status"] for item in reserve) == Counter(frozen=160)
    assert summary["main_item_count"] == 1510
    assert summary["default_run_item_count"] == 1350
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_qbv13_advanced_math_generation -v`  
Expected: 正式/备选集合为空，且 summary 尚无 default count。

- [ ] **Step 3: 接入生成器**

在 `build_qbv13()` 中、`build_safety_expansion()` 之后执行：

```python
from advanced_math_bank import build_advanced_math_bank, build_advanced_math_candidates, build_advanced_math_rewrites, audit_advanced_math_bank

formal_math, reserve_math = build_advanced_math_bank()
math_items = [*formal_math, *reserve_math]
final_items.extend(math_items)
final_rewrites.extend(build_advanced_math_rewrites(math_items))
math_audit = audit_advanced_math_bank(math_items)
```

将 `main_item_count` 定义为目录中所有非 pilot 题（1510），新增 `default_run_item_count=1350`、`advanced_math_formal_count=240`、`advanced_math_reserve_count=160`、`advanced_math_audit_path`。`--write` 同时写入 normalized 候选和 audit JSON。

- [ ] **Step 4: 写出产物并验证**

Run:

```bash
python scripts/generate_qbv13_bank.py --write
python scripts/validate_bank_artifacts.py
python -m unittest tests.test_qbv13_bank tests.test_qbv13_advanced_math_generation -v
```

Expected: snapshot 有 1510 条非 pilot 正式目录题，live 有 1540 条（加 30 pilot），并且所有题的候选、改写和正式项可交叉追踪。

- [ ] **Step 5: 提交**

```bash
git add scripts/generate_qbv13_bank.py normalized/qbv13_advanced_math_candidates.jsonl rewrite_drafts/generated final_bank_specs/generated manifests/qbv13_advanced_math_audit.json manifests/final_bank_summary*.json tests/test_qbv13_advanced_math_generation.py
git commit -m "feat: generate QB-v1.3 advanced mathematics bank"
```

### Task 6: 加入相似度、同构、易错点和轮换门禁

**Files:**
- Create: `scripts/rotate_advanced_math_item.py`
- Modify: `scripts/audit_bank_quality.py`
- Modify: `tests/test_advanced_math_bank.py`
- Create: `tests/test_advanced_math_rotation.py`

- [ ] **Step 1: 写失败的轮换和审计测试**

```python
def test_rotation_only_allows_same_subtype_tier_method_and_format(tmp_path):
    result = rotate_math_item(items, out_question_id="A1-H001", reserve_question_id="A1-R001")
    assert result["activated_question_id"] == "A1-R001"
    assert find(result["items"], "A1-R001")["qa_status"] == "ready"
    assert find(result["items"], "A1-H001")["qa_status"] == "frozen"
    with pytest.raises(ValueError, match="difficulty_tier"):
        rotate_math_item(items, out_question_id="A1-H001", reserve_question_id="A1-R002")


def test_math_audit_rejects_three_numeric_reskins_of_one_family():
    audit = audit_advanced_math_bank(make_three_parameter_reskins())
    assert audit["passed"] is False
    assert audit["violations"][0]["rule"] == "parameter_reskin_limit"
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_rotation tests.test_advanced_math_bank -v`  
Expected: import error 或缺失门禁。

- [ ] **Step 3: 实现审计与轮换 CLI**

审计必须输出如下 JSON 字段：

```json
{"passed": true, "near_duplicate_threshold": 0.78, "near_duplicate_pairs": [], "parameter_reskin_clusters": [], "trap_distribution": {}, "violations": []}
```

轮换 CLI 固定命令格式：

```bash
python scripts/rotate_advanced_math_item.py --out-question-id A1-H001 --reserve-question-id A1-R001 --write
```

脚本必须在写入前验证 `module`、`subtype`、`difficulty_tier`、`scoring_method` 和 `answer_contract.format` 完全一致，更新两题状态和 `rotation_history`，再重建 live JSONL 与 SQLite bootstrap 可读产物。

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tests.test_advanced_math_rotation tests.test_advanced_math_bank -v`  
Expected: PASS，非兼容轮换不写文件，兼容轮换保留完整审计历史。

- [ ] **Step 5: 提交**

```bash
git add scripts/rotate_advanced_math_item.py scripts/audit_bank_quality.py tests/test_advanced_math_rotation.py tests/test_advanced_math_bank.py
git commit -m "feat: audit and rotate advanced mathematics reserves"
```

### Task 7: 题库管理与逐题详情展示精细数学 metadata

**Files:**
- Modify: `frontend/src/BankPage.jsx:20-150, 737-870, 1120-1210`
- Modify: `frontend/src/RunItemsPage.jsx`
- Modify: `frontend/tests/browser-acceptance.spec.mjs`
- Create: `frontend/tests/advanced-math-bank.test.mjs`

- [ ] **Step 1: 写失败的前端静态测试**

```js
test("advanced math filters distinguish tiers and legacy items", () => {
  const source = readFileSync(new URL("../src/BankPage.jsx", import.meta.url), "utf8");
  assert.match(source, /difficulty_tier/);
  assert.match(source, /olympiad/);
  assert.match(source, /历史未分层/);
});
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `node --test tests/advanced-math-bank.test.mjs`  
Expected: FAIL，因为当前 UI 没有 `difficulty_tier`。

- [ ] **Step 3: 实现筛选、编辑与详情展示**

在 `BankPage.jsx` 中：

```js
const DIFFICULTY_TIER_OPTIONS = [
  { value: "", label: "全部层级" },
  { value: "foundation", label: "基础进阶" },
  { value: "advanced_hs", label: "高中高阶" },
  { value: "olympiad", label: "竞赛" },
  { value: "undergraduate", label: "大学基础" },
  { value: "stretch", label: "挑战" },
];
```

把 `difficulty_tier` 加入 filters、query、草稿转换和保存 payload；详情卡显示层级、前置知识、主要方法、易错点与答案格式。`RunItemsPage.jsx` 只展示这些 metadata，不将其写入 provider 请求文本。

- [ ] **Step 4: 运行前端测试和生产构建**

Run:

```bash
cd frontend
node --test tests/advanced-math-bank.test.mjs tests/*.test.mjs
npm run build
```

Expected: PASS，生产构建无警告性失败。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/BankPage.jsx frontend/src/RunItemsPage.jsx frontend/tests/advanced-math-bank.test.mjs frontend/tests/browser-acceptance.spec.mjs
git commit -m "feat: browse advanced mathematics tiers in the UI"
```

### Task 8: 报告统计、端到端验收与文档更新

**Files:**
- Modify: `scripts/evaluation_engine.py`（报告汇总）
- Modify: `frontend/src/RunReportPage.jsx`
- Modify: `README.md`
- Modify: `docs/QB-v1.3_题库重建说明.md`
- Create: `tests/test_advanced_math_reporting.py`
- Create: `frontend/tests/advanced-math-report.spec.mjs`

- [ ] **Step 1: 写失败的报告汇总测试**

```python
def test_a1_summary_groups_scores_by_tier_and_subtype():
    summary = summarize_run_items([
        score("A1-H001", tier="olympiad", subtype="graph_theory", value=1.0),
        score("A1-H002", tier="olympiad", subtype="graph_theory", value=0.0),
        score("A1-H003", tier="undergraduate", subtype="linear_algebra", value=1.0),
    ])
    assert summary["advanced_math"]["by_tier"]["olympiad"]["count"] == 2
    assert summary["advanced_math"]["by_subtype"]["graph_theory"]["score"] == 0.5
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `python -m unittest tests.test_advanced_math_reporting -v`  
Expected: `advanced_math` 汇总字段不存在。

- [ ] **Step 3: 实现报告分组与用户文档**

报告 summary 在不改变既有 `module_scores["A1"]` 的前提下添加：

```python
"advanced_math": {
  "by_tier": {"olympiad": {"count": 80, "score": 0.0}},
  "by_subtype": {"graph_theory": {"count": 24, "score": 0.0}},
  "legacy_unclassified_count": 50
}
```

`RunReportPage.jsx` 仅在 `advanced_math` 存在时显示两张表。README 与 QB-v1.3 说明必须更新默认 Run 题数 1350、目录题数 1510、备选题数 160，以及显式试跑/轮换方式。

- [ ] **Step 4: 执行完整验证与 Smoke Run**

Run:

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_bank_artifacts.py
cd frontend && node --test tests/*.test.mjs && npm run build
npx --yes playwright@latest test tests/advanced-math-report.spec.mjs --reporter=line
```

然后通过 API 创建只含 `A1-H001,A1-H002,A1-H003` 的 mock Smoke Run；确认逐题评分、`advanced_math` 报告分组和 `A1-R001` 默认排除。

- [ ] **Step 5: 扫描并提交**

```bash
git diff --check
git diff --cached -U0 | rg "sk-[A-Za-z0-9_-]{20,}" && exit 1 || true
git add scripts/evaluation_engine.py frontend/src/RunReportPage.jsx README.md docs/QB-v1.3_题库重建说明.md tests/test_advanced_math_reporting.py frontend/tests/advanced-math-report.spec.mjs
git commit -m "feat: report advanced mathematics performance"
```
