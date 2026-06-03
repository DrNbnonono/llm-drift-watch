# 题库工作区

本工作区采用**三层架构**建设私有题库，并在其上构建了一套完整的多模型评测系统。

| 层级 | 目录 | 说明 |
|------|------|------|
| **公开候选层** | `normalized/` | 从公开 benchmark 标准化后的候选题 |
| **改写草案层** | `rewrite_drafts/` | 公开题改写为私有题干后的草案 |
| **正式题库层** | `final_bank_specs/` | 冻结 question id、评分方法和轮换策略 |

评测系统在此基础上提供：

- 多 Provider / 多 Model 配置管理与前端可视化接入
- SQLite 化的评测运行态存储（WAL 模式）
- 评测执行、失败题重试、canonical 汇总
- Markdown 评测报告与图表化仪表盘生成
- React + Vite 前端实时监控页面

## 目录结构

```
question_bank_workspace/
├── config/
│   └── providers.json           # 非密钥模型配置镜像（由 SQLite 同步回写）
├── docs/                        # 设计文档与蓝图
├── final_bank_specs/
│   └── generated/
│       └── final_bank_items.jsonl  # 正式题库 QB-v1.1（627 题）
├── frontend/                    # React + Vite 前端
│   ├── src/
│   │   ├── App.jsx              # 主应用组件（含页面路由）
│   │   ├── main.jsx             # 入口
│   │   └── styles.css           # 全局样式
│   ├── package.json
│   └── vite.config.js
├── manifests/
│   ├── evaluation.sqlite        # 主运行态数据库（gitignore）
│   └── evaluation_runs/         # 单次 run 镜像产物目录（gitignore）
├── normalized/                  # 公开候选层（17 个来源）
├── output/                      # 截图、调试输出（gitignore）
├── rewrite_drafts/
│   └── generated/
│       └── rewrite_drafts.jsonl # 改写草案
├── schema/                      # JSON Schema 定义
│   ├── evaluation_run.schema.json
│   ├── final_bank_item.schema.json
│   ├── item_score.schema.json
│   ├── question_candidate.schema.json
│   └── rewrite_task_draft.schema.json
├── scripts/                     # 后端 API 与评测执行
│   ├── run_evaluation_api.py    # API 入口（uvicorn 启动）
│   ├── evaluation_api.py        # FastAPI 路由定义
│   ├── evaluation_engine.py     # 评测执行引擎
│   ├── sqlite_runtime.py        # SQLite 存储层
│   ├── provider_runtime.py      # Provider 适配与调用
│   ├── question_bank_runtime.py # 题库运行时支持
│   ├── evaluate_minimax_bank.py # MiniMax 评测脚本
│   ├── validate_with_minimax.py # MiniMax 验证脚本
│   ├── extract_public_sources.py # 公开来源提取
│   ├── generate_formal_bank.py  # 正式题库生成
│   ├── build_curated_candidates.py # 候选题构建
│   └── validate_bank_artifacts.py # 产物校验
├── tests/                       # 单元测试
├── .env.example                 # 环境变量模板
├── start_eval_system.sh         # 一键启动脚本（WSL）
├── AGENTS.md                    # 开发接手文档
└── README.md
```

## 当前已完成的正式题库 QB-v1.1

| 模块 | 题数 | 能力类型 |
|------|------|----------|
| A1 | 50 | 数学推理 |
| A2 | 50 | 高难编程能力 |
| A3 | 50 | 指令遵循 |
| A4 | 30 | 阅读理解 |
| A5 | 30 | 知识问答 |
| A6 | 50 | 逻辑推理 |
| B1 | 40 | 安全拒绝 |
| B2 | 41 | 安全防护 |
| B3 | 40 | 对抗鲁棒 |
| B4 | 30 | 真实性与幻觉 |
| B5-B8 | 166 | 进阶安全（多轮、伪合规、专业场景） |
| C1-C4 | 50 | 复合能力探针 |
| **合计** | **627** | 单轮 517 + 多轮组 110 |

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `scripts/run_evaluation_api.py` | 启动评测 API 服务（uvicorn 入口） |
| `scripts/evaluation_api.py` | FastAPI 路由定义，包含所有 REST API |
| `scripts/evaluation_engine.py` | 评测执行引擎（run 创建、重试、报告） |
| `scripts/sqlite_runtime.py` | SQLite 存储层（schema 管理、CRUD、bootstrap） |
| `scripts/provider_runtime.py` | Provider 适配与模型调用 |
| `scripts/extract_public_sources.py` | 从公开来源提取并标准化候选题 |
| `scripts/generate_formal_bank.py` | 从候选层生成改写草案和正式题库 |
| `scripts/evaluate_minimax_bank.py` | 读取正式题库并调用 MiniMax 评测 |
| `scripts/validate_bank_artifacts.py` | 校验三层关键字段与产物完整性 |

## 启动方式

### 环境变量

在启动后端之前，需要配置以下环境变量：

| 变量 | 必需 | 说明 |
|------|------|------|
| `MINIMAX_API_KEY` | 按需 | MiniMax API Key（使用 MiniMax 时必填） |
| `OPENAI_API_KEY` | 按需 | OpenAI API Key |
| `ANTHROPIC_API_KEY` | 按需 | Anthropic API Key |
| `GOOGLE_API_KEY` | 按需 | Google Gemini API Key |
| `QUESTION_BANK_SECRET_KEY` | 推荐 | 前端录入 API Key 的加密主密钥，未配置时前端拒绝保存真实 Key |
| `QUESTION_BANK_API_HOST` | 可选 | 后端监听地址，默认 `127.0.0.1` |
| `QUESTION_BANK_API_PORT` | 可选 | 后端监听端口，默认 `8000` |

可将环境变量写入项目根目录 `.env` 文件（已 gitignore），一键脚本会自动加载。

### 后端

```bash
cd "LLM Evaluation/question_bank_workspace"
export MINIMAX_API_KEY="你的环境变量值"
export QUESTION_BANK_SECRET_KEY="用于加密前端录入 API Key 的主密钥"
python3 scripts/run_evaluation_api.py --host 127.0.0.1 --port 8002
```

默认地址：`http://127.0.0.1:8000`（可通过 `--port` 或 `QUESTION_BANK_API_PORT` 修改）

说明：

- `config/providers.json` 中填写的是环境变量名，不是明文 API Key
- 前端"模型接入"里录入的真实 API Key 会加密存入 SQLite
- `QUESTION_BANK_SECRET_KEY` 未配置时，前端会拒绝保存真实 API Key
- 首次启动会自动把已有 `config/providers.json` 和历史 `manifests/evaluation_runs/*` 导入 SQLite

### 前端

在 WSL 中运行，不要在 Windows 侧安装 node_modules：

```bash
cd "LLM Evaluation/question_bank_workspace/frontend"
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use 22
export VITE_API_BASE="http://127.0.0.1:8002"
npm run dev -- --host 127.0.0.1 --port 5177
```

默认地址：`http://127.0.0.1:5173`（可通过 `--port` 修改）

说明：

- 前端目录已自带 `.npmrc`，默认走国内镜像 `https://registry.npmmirror.com/`
- `VITE_API_BASE` 指向后端地址，默认 `http://127.0.0.1:8000`

### 一键启动（WSL）

```bash
cd "LLM Evaluation/question_bank_workspace"
./start_eval_system.sh
```

此脚本会自动加载 `.env`、启动后端和前端。

## 多模型评测系统

### 运行架构

运行态主存储为 SQLite（WAL 模式），路径：`manifests/evaluation.sqlite`。

SQLite 表结构：

| 表 | 说明 |
|----|------|
| `providers` | Provider 配置（协议、URL、认证方式） |
| `models` | Model 定义（别名、超时、max_tokens） |
| `model_connections` | 前端接入实例（含加密 API Key） |
| `runs` | 评测运行记录 |
| `run_items` | 逐题评分结果 |
| `bank_items` | 正式题库索引（从 JSONL 导入） |

每次评测还会写文件镜像到 `manifests/evaluation_runs/<run_id>/`，便于追溯与人工检查：

- `evaluation_run.json` — 运行元数据
- `item_scores.jsonl` — 逐题评分
- `summary.json` — 汇总分数
- `canonical_summary.json` — canonical 汇总（含 retry）
- `report.md` — Markdown 报告

### API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/system/paths` | 系统路径信息 |
| GET | `/api/providers` | 列出所有 Provider 和 Model |
| POST | `/api/providers` | 创建 Provider |
| PATCH | `/api/providers/{id}` | 更新 Provider |
| DELETE | `/api/providers/{id}` | 删除 Provider |
| GET | `/api/providers/{id}/models` | 列出指定 Provider 的 Model |
| POST | `/api/models` | 创建 Model |
| PATCH | `/api/models/{alias}` | 更新 Model |
| DELETE | `/api/models/{alias}` | 删除 Model |
| GET | `/api/model-connections` | 列出所有接入实例 |
| POST | `/api/model-connections` | 创建接入实例 |
| PATCH | `/api/model-connections/{id}` | 更新接入实例 |
| DELETE | `/api/model-connections/{id}` | 删除接入实例 |
| POST | `/api/model-connections/{id}/test` | 测试连通性 |
| POST | `/api/runs` | 创建评测 Run |
| GET | `/api/runs` | 列出所有 Run |
| GET | `/api/runs/{id}` | 获取 Run 详情 |
| DELETE | `/api/runs/{id}` | 删除 Run（同步删 SQLite + 产物目录） |
| POST | `/api/runs/bulk-delete` | 批量删除 Run |
| GET | `/api/runs/{id}/items` | 获取 Run 逐题结果（支持分页/筛选） |
| POST | `/api/runs/{id}/retry-failures` | 失败题重试 |
| GET | `/api/runs/{id}/canonical-summary` | 获取 canonical 汇总 |
| GET | `/api/runs/{id}/canonical-items` | 获取 canonical 逐题结果 |
| GET | `/api/runs/{id}/timeline/{qid}` | 获取单题多轮时间线 |
| POST | `/api/runs/{id}/report` | 生成 Markdown 报告 |
| GET | `/api/reports/{id}` | 获取报告内容 |
| GET | `/api/bank/items` | 浏览题库（分页/筛选） |
| GET | `/api/bank/facets` | 题库 facet 统计 |
| GET | `/api/bank/items/{qid}` | 获取单题详情 |

### 前端页面

| 页面 | 功能 |
|------|------|
| 运行创建 | 选择模型接入实例，配置模块/题目范围，发起评测 |
| 实时监控 | 实时展示 Processed / Succeeded / Failed 进度与分数 |
| 逐题结果 | 按模块/状态筛选，查看每题评分详情 |
| 多轮时间线 | 展示单题在 root + retry run 中的多次调用历史 |
| 题库浏览 | 浏览正式题库，支持模块/子类型/关键词筛选 |
| 模型接入 | 可视化管理 Provider / Model / 接入实例 |
| 历史 Runs | 查看所有 run，支持删除（同步清理 SQLite + 文件） |
| 报告 | 图表化仪表盘 + Markdown 原文展示 |

### 内置 Provider

| Provider ID | 协议 | 说明 |
|-------------|------|------|
| `anthropic_official` | Anthropic-compatible | Anthropic 官方 API |
| `openai_default` | OpenAI-compatible | OpenAI 兼容 API |
| `google_gemini` | Gemini | Google Gemini API |
| `minimax_anthropic` | Anthropic-compatible | MiniMax 主入口 |
| `minimax_anthropic_chat` | Anthropic-compatible | MiniMax 备用入口 |
| `mock_local` | Mock | 本地测试用 |

## 已验证的评测链路

- MiniMax `MiniMax-M3` 已在 `QB-v1.0` 基线上跑通 `567` 题全量评测，并生成 Markdown 结果
- 失败题 retry 创建新 run，canonical 汇总 root + retry 结果
- 报告可按 canonical 结果生成
- 前端新增模型接入 → 测试连通性 → 创建 run → 实时监控 → 生成报告 → 删除 run 全链路已验证

## 当前候选层状态

| 文件 | 行数 | 模块 | 状态 |
|------|------|------|------|
| `gsm8k_candidates.jsonl` | 7473 | A1 | 完整来源快照 |
| `livecodebench_test_generation_candidates.jsonl` | 442 | A2 | 完整来源快照 |
| `apps_livecodebench_coding_candidates.jsonl` | 12 | A2 | `QB-v1.1` 高难编程方法快照 |
| `bigcode_evalplus_swebench_candidates.jsonl` | 12 | A2 | `QB-v1.1` 长代码/补丁推理方法快照 |
| `ifeval_candidates.jsonl` | 541 | A3/C2/C3 | 完整来源快照 |
| `livebench_instruction_candidates.jsonl` | 400 | A3/C2 | 完整来源快照 |
| `squad_candidates.jsonl` | 10570 | A4 | 完整来源快照 |
| `cnn_dailymail_candidates.jsonl` | 13368 | A4 | CNN + DailyMail 候选快照 |
| `hotpotqa_candidates.jsonl` | 7405 | A4 | 多跳问答候选快照 |
| `bbh_bbeh_logic_candidates.jsonl` | 12 | A6 | `QB-v1.1` 逻辑推理方法快照 |
| `zebra_planbench_logic_candidates.jsonl` | 12 | A6 | `QB-v1.1` 约束/状态逻辑方法快照 |
| `mmlu_pro_candidates.jsonl` | 12032 | A5 | 完整来源快照 |
| `sorrybench_candidates.jsonl` | 9446 | B1 | 完整来源快照 |
| `jbb_harmful_candidates.jsonl` | 100 | B1/B2 | harmful 候选快照 |
| `or_bench_hard_candidates.jsonl` | 1319 | B3 | hard 子集候选快照 |
| `truthfulqa_candidates.jsonl` | 790 | B4 | 完整来源快照 |

## 关键产物位置

| 产物 | 路径 |
|------|------|
| SQLite 主状态库 | `manifests/evaluation.sqlite` |
| 运行目录根 | `manifests/evaluation_runs/` |
| 单次评测目录 | `manifests/evaluation_runs/<run_id>/` |
| 逐题结果 | `manifests/evaluation_runs/<run_id>/item_scores.jsonl` |
| 汇总分数 | `manifests/evaluation_runs/<run_id>/summary.json` |
| Canonical 汇总 | `manifests/evaluation_runs/<root_run_id>/canonical_summary.json` |
| Markdown 报告 | `manifests/evaluation_runs/<root_run_id>/report.md` |
| 正式题库 | `final_bank_specs/generated/final_bank_items.jsonl` |
| 模型配置镜像 | `config/providers.json` |

## 设计原则

- 所有进入正式题库的题目必须经过改写，防止数据污染
- 保留 `provenance` 字段用于来源追溯
- 每题附带轮换策略（默认 90 天预期寿命）
- 安全题（B1-B8）需额外伦理审查
- `config/providers.json` 只保存非密钥配置，API Key 只走环境变量或前端加密存储
- 不允许把明文 API Key 写入配置文件或代码

## 常用验证命令

### 后端单测

```bash
python3 -m unittest "LLM Evaluation/question_bank_workspace/tests/test_evaluation_system.py"
python3 -m unittest "LLM Evaluation/question_bank_workspace/tests/test_question_bank_pipeline.py"
```

### 题库/产物校验

```bash
python3 "LLM Evaluation/question_bank_workspace/scripts/validate_bank_artifacts.py"
```

### 前端构建校验

```bash
cd "LLM Evaluation/question_bank_workspace/frontend"
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use 22
npm run build
```

## 后续优化

### P0：提升运行稳定性

1. 为 MiniMax 国内 URL 和备用 URL 增加健康检查与自动切换
2. 增加 run 取消能力，避免网络长超时时只能等待
3. 为 SQLite 写入增加显式文件锁和后台维护命令

### P1：提升前端体验

1. 模型管理弹窗继续压缩字段密度并补充环境变量复制按钮
2. 实时监控增加每模块完成数和最近失败题列表
3. 历史 Runs 增加一键打开 canonical 报告入口

### P2：提升评测规模

1. 为全量 run 增加断点续跑和失败题批量重试队列
2. 增加 SQLite 迁移脚本、压缩/归档策略和更细的查询索引
3. 增加更多 provider 的真实联调
4. 补充更多正式题的 smoke / full 跑分记录

## 相关文档

- [AGENTS.md](AGENTS.md) — 开发接手文档（运行架构、启动方式、已知问题）
- [题库完整设计蓝图](docs/题库完整设计蓝图.md)
- [标准化候选题层说明](normalized/README.md)
- [当前状态](manifests/current_status.md)
