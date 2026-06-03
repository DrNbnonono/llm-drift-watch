# AGENTS

本文件用于后续在 `LLM Evaluation/question_bank_workspace` 内进行迭代时快速接手。

## 1. 项目目标

该 workspace 是一个多模型测评系统，包含：

- 正式题库生成与浏览（三层架构：公开候选 → 改写草案 → 正式题库）
- 多 Provider / 多 Model 配置管理
- SQLite 化的评测运行态存储（WAL 模式）
- 评测执行、失败题重试、canonical 汇总
- Markdown 评测报告与图表化仪表盘生成
- React + Vite 前端实时监控页面

当前已经完成 MiniMax 的真实链路验证，以及完整前端链路验收。

## 2. 目录约定

| 目录 / 文件 | 说明 |
|-------------|------|
| `config/providers.json` | 非密钥模型配置镜像（由 SQLite 同步回写，勿手动编辑） |
| `docs/` | 设计文档与蓝图 |
| `final_bank_specs/generated/final_bank_items.jsonl` | 正式题库 QB-v1.1（627 题） |
| `frontend/` | React + Vite 前端 |
| `frontend/src/App.jsx` | 主应用组件（含页面路由） |
| `manifests/evaluation.sqlite` | 主运行态数据库（gitignore） |
| `manifests/evaluation_runs/<run_id>/` | 单次 run 的镜像产物目录（gitignore） |
| `normalized/` | 公开候选层（17 个来源的标准化候选题） |
| `output/` | Playwright 截图、调试输出（gitignore） |
| `rewrite_drafts/generated/rewrite_drafts.jsonl` | 改写草案 |
| `schema/` | JSON Schema 定义（evaluation_run / final_bank_item / item_score / question_candidate / rewrite_task_draft） |
| `scripts/` | 后端 API、评测执行、Provider 适配、SQLite 运行时 |
| `tests/` | 单元测试 |
| `start_eval_system.sh` | 一键启动脚本（WSL，自动加载 .env） |

### scripts 职责明细

| 脚本 | 职责 |
|------|------|
| `run_evaluation_api.py` | uvicorn 入口，支持 `--host` / `--port` / `--reload` |
| `evaluation_api.py` | FastAPI 路由定义，所有 REST API |
| `evaluation_engine.py` | 评测执行引擎（run 创建、重试、报告、canonical 汇总） |
| `sqlite_runtime.py` | SQLite 存储层（schema 管理、CRUD、legacy bootstrap） |
| `provider_runtime.py` | Provider 适配与模型调用（anthropic_compatible / openai_compatible / gemini / mock） |
| `question_bank_runtime.py` | 题库运行时支持 |
| `extract_public_sources.py` | 从公开来源提取并标准化候选题 |
| `generate_formal_bank.py` | 从候选层生成改写草案和正式题库 |
| `build_curated_candidates.py` | 早期候选题构建脚本 |
| `build_qbv11_candidates.py` | `QB-v1.1` 的 A2/A6 方法快照构建脚本 |
| `evaluate_minimax_bank.py` | 读取正式题库并调用 MiniMax 评测 |
| `validate_with_minimax.py` | MiniMax 验证脚本 |
| `validate_bank_artifacts.py` | 校验三层关键字段与产物完整性 |

## 3. 运行架构

### 3.1 主存储

运行态主存储已经迁移到 SQLite：

- DB 路径：`manifests/evaluation.sqlite`
- WAL 模式，`synchronous=NORMAL`，`foreign_keys=ON`

SQLite 表结构：

| 表 | 主键 | 说明 |
|----|------|------|
| `providers` | `provider_id` | Provider 配置（协议、URL、认证方式） |
| `models` | `model_alias` | Model 定义（别名、超时、max_tokens） |
| `model_connections` | `connection_id` | 前端接入实例（含加密 API Key） |
| `runs` | `run_id` | 评测运行记录 |
| `run_items` | `id` (自增) | 逐题评分结果 |
| `bank_items` | `question_id` | 正式题库索引（从 JSONL 导入） |

关键索引：

- `idx_model_connections_vendor` / `idx_model_connections_enabled`
- `idx_run_items_run_id` / `idx_run_items_question_id`
- `idx_runs_parent_run_id` / `idx_runs_connection_id`
- `idx_bank_items_module` / `idx_bank_items_subtype` / `idx_bank_items_item_format`

### 3.2 镜像产物

每次评测仍会写文件镜像，便于追溯与人工检查：

- `evaluation_run.json` — 运行元数据
- `item_scores.jsonl` — 逐题评分
- `summary.json` — 汇总分数
- `canonical_summary.json` — canonical 汇总（含 retry）
- `report.md` — Markdown 报告

位置统一在：`manifests/evaluation_runs/<run_id>/`

### 3.3 Bootstrap 流程

首次启动时 `sqlite_runtime.py` 会自动执行：

1. 创建所有表和索引（`_init_schema`）
2. 从 `config/providers.json` 导入 providers 和 models（`bootstrap_legacy`）
3. 从 `final_bank_specs/generated/final_bank_items.jsonl` 导入 bank_items（`bootstrap_bank_items`）
4. 从 `manifests/evaluation_runs/` 导入历史 run 数据（`import_all_runs`）

后续页面内新增或编辑 Provider / Model 时，会同步更新 SQLite，并回写一份 `config/providers.json` 兼容镜像。

## 4. 启动方式

### 4.1 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `MINIMAX_API_KEY` | 按需 | MiniMax API Key |
| `OPENAI_API_KEY` | 按需 | OpenAI API Key |
| `ANTHROPIC_API_KEY` | 按需 | Anthropic API Key |
| `GOOGLE_API_KEY` | 按需 | Google Gemini API Key |
| `QUESTION_BANK_SECRET_KEY` | 推荐 | 前端录入 API Key 的加密主密钥，未配置时前端拒绝保存真实 Key |
| `QUESTION_BANK_API_HOST` | 可选 | 后端监听地址，默认 `127.0.0.1` |
| `QUESTION_BANK_API_PORT` | 可选 | 后端监听端口，默认 `8000` |

可将环境变量写入 `.env`（已 gitignore），一键脚本会自动加载。

### 4.2 后端

```bash
cd "LLM Evaluation/question_bank_workspace"
export MINIMAX_API_KEY="你的环境变量值"
export QUESTION_BANK_SECRET_KEY="用于加密前端录入 API Key 的主密钥"
python3 scripts/run_evaluation_api.py --host 127.0.0.1 --port 8002
```

默认地址：`http://127.0.0.1:8000`

说明：

- `config/providers.json` 中填写的是环境变量名，不是明文 API Key
- 前端"模型接入"里录入的真实 API Key 会加密存入 SQLite
- `QUESTION_BANK_SECRET_KEY` 未配置时，前端会拒绝保存真实 API Key

### 4.3 前端

在 WSL 中运行，不要在 Windows 侧安装 node_modules：

```bash
cd "LLM Evaluation/question_bank_workspace/frontend"
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use 22
export VITE_API_BASE="http://127.0.0.1:8002"
npm run dev -- --host 127.0.0.1 --port 5177
```

默认地址：`http://127.0.0.1:5173`

说明：

- `.npmrc` 已配置国内镜像 `https://registry.npmmirror.com/`
- `VITE_API_BASE` 指向后端地址，默认 `http://127.0.0.1:8000`

### 4.4 一键启动（WSL）

```bash
cd "LLM Evaluation/question_bank_workspace"
./start_eval_system.sh
```

此脚本会自动加载 `.env`、后台启动后端（8000 端口）、前台启动前端（5173 端口）。

### 4.5 当前已验证地址

| 服务 | 地址 |
|------|------|
| 后端 | `http://127.0.0.1:8002` |
| 前端 | `http://127.0.0.1:5177` |

## 5. API 端点一览

### 基础

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/system/paths` | 系统路径信息 |

### Provider 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/providers` | 列出所有 Provider 和 Model |
| POST | `/api/providers` | 创建 Provider |
| PATCH | `/api/providers/{id}` | 更新 Provider |
| DELETE | `/api/providers/{id}` | 删除 Provider |
| GET | `/api/providers/{id}/models` | 列出指定 Provider 的 Model |

### Model 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/models` | 创建 Model |
| PATCH | `/api/models/{alias}` | 更新 Model |
| DELETE | `/api/models/{alias}` | 删除 Model |

### 模型接入（Model Connection）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/model-connections` | 列出所有接入实例 |
| POST | `/api/model-connections` | 创建接入实例 |
| PATCH | `/api/model-connections/{id}` | 更新接入实例 |
| DELETE | `/api/model-connections/{id}` | 删除接入实例 |
| POST | `/api/model-connections/{id}/test` | 测试连通性 |

### 评测运行（Run）

| 方法 | 路径 | 说明 |
|------|------|------|
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

### 题库（Bank）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/bank/items` | 浏览题库（分页/筛选） |
| GET | `/api/bank/facets` | 题库 facet 统计 |
| GET | `/api/bank/items/{qid}` | 获取单题详情 |

## 6. MiniMax 配置约定

当前验证过的国内 Anthropic-compatible 入口：

- Base URL: `https://api.minimax.chat/anthropic/v1`
- 模型：`MiniMax-M3`

推荐的新增方式：

1. 进入前端 `模型接入`
2. 新增一个接入实例，填写：
   - 供应商名称：`MiniMax`
   - 显示名称：例如 `MiniMax UI Live Validation`
   - Base URL：`https://api.minimax.chat/anthropic/v1`
   - API 格式：`Anthropic-compatible`
   - 认证方式：`x_api_key`
   - 认证字段环境名：`MINIMAX_API_KEY`
   - 真实请求模型名：`MiniMax-M3`
3. 可直接在弹窗里填写真实 API Key
4. 保存后点击 `用此评测`

底层仍会自动生成兼容用的 `provider_id / model_alias`，但默认不需要手动理解和维护。

## 7. 已验证评测链路

### 7.1 最新真实 MiniMax run

- run_id: `20260530T082253Z-d2653b9b`
- provider: `minimax_sqlite_verify`
- model_alias: `model_conn_minimax_ui_live_minimax_ui_live_validation`
- 题目：`C2-001`, `C2-002`

结果：

- `2/2` API 调用成功
- `C2` 模块得分：`0.5`

报告位置：

- `manifests/evaluation_runs/20260530T082253Z-d2653b9b/report.md`

注意：

- `status = ok` 表示模型调用成功
- 不等于该题满分
- 例如 `C2-002` 这次调用成功，但文本为空，得分是 `0.0`

### 7.2 retry / canonical 验证

已验证过失败题重试与 canonical 汇总：

- root run: `20260530T023132Z-6c766dcb`
- retry run: `20260530T023420Z-7c0fc53f`

这个链路已经证明：

- retry 会创建新的 run
- canonical 会汇总 root + retry
- 报告可按 canonical 结果生成

### 7.3 已验证的前端直连操作

已通过真实浏览器完成一条完整前端路径：

- 前端新增模型接入：`MiniMax UI Live Validation`
- 前端测试连通性：通过
- 前端创建 run：成功
- 前端监控：可实时看到 `Processed / Succeeded / Failed`
- 前端生成报告：可看到图表化仪表盘和 Markdown 原文
- 前端删除 run：SQLite 与 `manifests/evaluation_runs/<run_id>/` 同步删除

本轮真实浏览器验收中使用并验证过的 run 包括：

- `20260530T103816Z-ee17d003`
- `20260530T105908Z-a4facbe4`
- `20260530T112224Z-d0f289c9`

## 8. 监控语义

前后端已经统一：

- `progress`
  - 运行进度
  - 核心字段：
    - `items_total`
    - `items_processed`
    - `items_inflight`
- `totals`
  - 结果统计
  - 核心字段：
    - `items_succeeded`
    - `items_failed`

兼容字段：

- `items_completed == items_processed`

不要再把 `completed` 理解成"成功数"。

## 9. 常用验证命令

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

## 10. 前端技术栈

- React 18 + Vite 5
- 原生 JSX（无额外 UI 框架）
- CSS 样式内联于 `styles.css`
- 开发依赖：`@vitejs/plugin-react`
- 包管理：pnpm（`pnpm-lock.yaml` / `pnpm-workspace.yaml`），但启动脚本用 `npm`
- Node 版本：22（`.nvmrc`）

前端页面路由在 `App.jsx` 中通过条件渲染实现，所有页面在单文件中定义。

## 11. 已知问题

### 11.1 Playwright 真实浏览器验收

当前 WSL 已安装浏览器依赖，真实浏览器验收可以直接做。

如果需要再次执行人工/自动化验收，优先验证这条链路：

1. `模型接入` 新增或编辑接入实例
2. `测试连通性`
3. `运行创建` 发起 `C2` smoke run
4. `实时监控` 查看完成状态
5. `生成报告`
6. `历史 Runs` 删除临时 run

当前状态：

- 真实浏览器自动化已经可运行
- 若继续使用通用 `playwright-cli` wrapper，仍可能因为其默认偏向 `chrome channel` 而不是缓存内 `chromium`，出现额外兼容问题
- 但项目级真实浏览器验收已经可以完成，不影响本 workspace 的 UI 验证

### 11.2 配置文件原则

- `config/providers.json` 只保存非密钥配置
- API key 只走后端环境变量或前端加密存储
- 不允许把 `sk-...` 一类明文 key 写进配置文件

### 11.3 端口说明

- `run_evaluation_api.py` 默认端口 `8000`，可通过 `--port` 或 `QUESTION_BANK_API_PORT` 覆盖
- `start_eval_system.sh` 使用默认端口 `8000` / `5173`
- 当前已验证的端口为 `8002` / `5177`（手动指定 `--port` 和 `VITE_API_BASE`）

## 12. 后续迭代建议

优先顺序建议：

1. 补齐 Playwright 真实浏览器依赖，完成 UI 自动化验收
2. 继续打磨模型管理页交互
3. 增加更多 provider 的真实联调
4. 补充更多正式题的 smoke / full 跑分记录
5. 如并发 run 继续增多，可继续深化 SQLite 事务与锁策略
