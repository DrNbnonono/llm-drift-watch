# 题库工作区

本工作区采用**三层架构**建设私有题库：

| 层级 | 目录 | 说明 |
|------|------|------|
| **公开候选层** | `normalized/` | 从公开 benchmark 标准化后的候选题 |
| **改写草案层** | `rewrite_drafts/` | 公开题改写为私有题干后的草案 |
| **正式题库层** | `final_bank_specs/` | 冻结 question id、评分方法和轮换策略 |

## 当前已完成的正式题库 QB-v1.0

| 模块 | 题数 | 能力类型 |
|------|------|----------|
| A1 | 50 | 数学推理 |
| A2 | 40 | 代码能力 |
| A3 | 50 | 指令遵循 |
| A4 | 30 | 阅读理解 |
| A5 | 30 | 知识问答 |
| B1 | 40 | 安全拒绝 |
| B2 | 41 | 安全防护 |
| B3 | 40 | 对抗鲁棒 |
| B4 | 30 | 真实性与幻觉 |
| B5-B8 | 166 | 进阶安全（多轮、伪合规、专业场景） |
| C1-C4 | 50 | 复合能力探针 |
| **合计** | **567** | 单轮 457 + 多轮组 110 |

## 当前候选层状态

| 文件 | 行数 | 模块 | 状态 |
|------|------|------|------|
| `gsm8k_candidates.jsonl` | 7473 | A1 | ✅ 完整来源快照 |
| `squad_candidates.jsonl` | 10570 | A4 | ✅ 完整来源快照 |
| `sorrybench_candidates.jsonl` | 9446 | B1 | ✅ 完整来源快照 |
| `truthfulqa_candidates.jsonl` | 790 | B4 | ✅ 完整来源快照 |
| `cnn_dailymail_cnn_subset_candidates.jsonl` | 1220 | A4 | ⚠️ 仅 CNN 半边，缺 DailyMail |
| `ifeval_candidates.jsonl` | 100 | A3/C2/C3 | ❌ 部分 |
| `mmlu_pro_candidates.jsonl` | 100 | A5 | ❌ 部分 |
| `jbb_harmful_candidates.jsonl` | 2 | B1/B2 | ❌ 部分 |
| `livebench_instruction_candidates.jsonl` | 2 | A3/C2 | ❌ 部分 |
| `livecodebench_test_generation_candidates.jsonl` | 100 | A2 | ⚠️ 种子 |
| `or_bench_hard_candidates.jsonl` | 100 | B3 | ⚠️ 种子 |

**状态说明**：
- `完整来源快照`：公开来源已实质完整
- `完整子集快照`：来源的某个明确子集已完整落地
- `种子`：稳定第一批样本，适合流程验证
- `部分`：来源已连接但数量不足

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `scripts/extract_public_sources.py` | 从公开来源提取并标准化候选题 |
| `scripts/generate_formal_bank.py` | 从候选层生成改写草案和正式题库 |
| `scripts/evaluate_minimax_bank.py` | 读取正式题库并调用 MiniMax 评测 |
| `scripts/validate_bank_artifacts.py` | 校验三层关键字段 |
| `scripts/question_bank_runtime.py` | 运行时支持脚本 |
| `scripts/run_evaluation_api.py` | 启动多模型测评 API 服务 |

## 多模型测评系统

当前工作区已新增一版多模型测评系统，支持:

- 多 Provider 模型注册与认证映射
- 后端 API 发起评测、失败题重试、canonical 汇总
- Markdown 评测报告生成
- React/Vite 前端实时展示页面
- 历史 MiniMax run 兼容渲染
- 逐题原题查看、多轮时间线展示、独立题库浏览
- 页面内新增 Provider / Model 的非密钥配置管理

### Provider 配置

- 配置文件: `config/providers.json`
- 凭证样例: `.env.example`

当前内置 provider:

- `minimax_anthropic`
- `anthropic_official`
- `openai_default`
- `google_gemini`
- `mock_local`

当前前端页面:

- `运行创建`
- `实时监控`
- `逐题结果`
- `多轮时间线`
- `题库浏览`
- `模型管理`
- `历史 Runs`
- `报告`

### 启动后端

推荐直接使用当前 WSL 的 Python 环境:

```bash
cd "LLM Evaluation/question_bank_workspace"
python3 scripts/run_evaluation_api.py
```

默认地址:

- `http://127.0.0.1:8000`

### 启动前端

当前 WSL 已检测到 `nvm`，可直接使用 `node 22`:

```bash
cd "LLM Evaluation/question_bank_workspace/frontend"
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use 22
npm install
npm run dev
```

说明:

- 前端目录已自带 `.npmrc`，默认走国内镜像 `https://registry.npmmirror.com/`
- `package.json` 已改为直接调用本地 `node_modules/vite/bin/vite.js`，减少 `.bin` 链接异常影响
- 也可以直接运行一键脚本：

```bash
cd "LLM Evaluation/question_bank_workspace"
./start_eval_system.sh
```

默认前端地址:

- `http://127.0.0.1:5173`

前端默认请求:

- `http://127.0.0.1:8000`

如需修改，可设置:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

## 已验证的评测链路

- Smoke run 已完成：成功对 A2/A3 拿到评分
- A1/A4 因题目较长在当前网络条件下超时，需优化重试策略
- 运行结果落在 `manifests/evaluation_runs/`

## 关键产物位置

- 运行目录根: `manifests/evaluation_runs/`
- 单次评测目录: `manifests/evaluation_runs/<run_id>/`
- 逐题结果: `manifests/evaluation_runs/<run_id>/item_scores.jsonl`
- 汇总分数: `manifests/evaluation_runs/<run_id>/summary.json`
- Canonical 汇总: `manifests/evaluation_runs/<root_run_id>/canonical_summary.json`
- Markdown 报告: `manifests/evaluation_runs/<root_run_id>/report.md`
- 正式题库: `final_bank_specs/generated/final_bank_items.jsonl`
- 模型非密钥配置: `config/providers.json`

## 待完成项

### P0：补齐公开候选层
1. IFEval、MMLU-Pro、JailbreakBench、LiveBench instruction_following 扩展为完整快照
2. LiveCodeBench、OR-Bench 从种子扩展为完整候选
3. CNN/DailyMail 补齐 DailyMail 半边
4. HotpotQA 下载原始文件补入 A4 多跳推理候选

### P1：提升题库质量
1. 从现有候选层生成高质量改写草案
2. 冻结正式题库的评分方法和轮换策略
3. 优化长题的超时和重试策略

### P2：补充高级模块
1. 生成多轮安全组（B5/B6/B7）
2. 冻结探针集（C1/C2/C3/C4）

## 设计原则

- 所有进入正式题库的题目必须经过改写，防止数据污染
- 保留 `provenance` 字段用于来源追溯
- 每题附带轮换策略（默认 90 天预期寿命）
- 安全题（B1-B8）需额外伦理审查

## 相关文档

- [题库完整设计蓝图](docs/题库完整设计蓝图.md)
- [标准化候选题层说明](normalized/README.md)
- [当前状态](manifests/current_status.md)
