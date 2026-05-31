# 当前状态

## 总体判断

工作区现在已经具备完整的设计闭环，但执行层面仍未完全完成。

可明确区分为两件事:

- 设计是否完整: 现在已完整
- 数据和题目是否全部落地: 还没有

本次补齐后的结构是:

1. `normalized/`：公开候选层
2. `rewrite_drafts/`：私有改写草案层
3. `final_bank_specs/`：正式题库规格层

因此，当前剩余工作不再是“要不要这样设计”，而是“按设计继续补齐和执行”。

## 已完成的新能力

本轮已经新增并落地:

1. 正式题库生成脚本：`scripts/generate_formal_bank.py`
2. 正式评测 runner：`scripts/evaluate_minimax_bank.py`
3. 结构校验脚本：`scripts/validate_bank_artifacts.py`
4. 运行期 schema：
   - `schema/evaluation_run.schema.json`
   - `schema/item_score.schema.json`
5. 一版完整正式题库 `QB-v1.0`
6. 多模型 provider 注册表：`config/providers.json`
7. 统一 provider 抽象层：`scripts/provider_runtime.py`
8. 后台评测任务服务：`scripts/evaluation_engine.py`
9. FastAPI 后端：`scripts/evaluation_api.py`
10. React/Vite 前端：`frontend/`
11. 一键启动脚本：`start_eval_system.sh`

## 公开候选层现状

| 文件 | 行数 | 状态 | 设计角色 |
|---|---:|---|---|
| `ifeval_candidates.jsonl` | 100 | 部分 | `A3/C2/C3` 核心约束来源 |
| `mmlu_pro_candidates.jsonl` | 100 | 部分 | `A5` 核心多选知识来源 |
| `jbb_harmful_candidates.jsonl` | 2 | 部分 | `B1/B2` 行为目标和攻击模板来源 |
| `livebench_instruction_candidates.jsonl` | 2 | 部分 | `A3/C2` 动态新鲜约束来源 |
| `gsm8k_candidates.jsonl` | 7473 | 完整来源快照 | `A1` 方法库和候选池 |
| `sorrybench_candidates.jsonl` | 9446 | 完整来源快照 | `B1` 直接请求候选池 |
| `squad_candidates.jsonl` | 10570 | 完整来源快照 | `A4` 阅读理解候选池 |
| `cnn_dailymail_cnn_subset_candidates.jsonl` | 1220 | 完整子集快照 | `A4` 摘要候选池，目前仅 CNN 半边 |
| `livecodebench_test_generation_candidates.jsonl` | 100 | 种子 | `A2` 代码题种子池 |
| `or_bench_hard_candidates.jsonl` | 100 | 种子 | `B3` 过度拒绝种子池 |
| `truthfulqa_candidates.jsonl` | 790 | 完整来源快照 | `B4` 幻觉检测候选池 |

## 设计层面的关键缺口已被补齐

此前真正缺失的内容，现在已经明确补成以下结构:

| 之前缺口 | 当前处理方式 |
|----------|--------------|
| 只有候选层，没有改写层 | 已新增 `rewrite_drafts/` 设计位 |
| 只有公开来源，没有正式题库规格层 | 已新增 `final_bank_specs/` 设计位 |
| 模块和来源之间只有粗映射 | 已在蓝图中细化为“来源角色 + 正式落题方式” |
| `B5/B6/B7/B8/C1/C4` 没有直接候选文件 | 已明确它们应由改写层和自建题生成 |
| 只有 candidate schema | 已补齐 rewrite 和 final 两层 schema |

## 正式题库当前状态

当前已经生成:

- `rewrite_drafts/generated/rewrite_drafts.jsonl`
- `final_bank_specs/generated/final_bank_items.jsonl`
- `manifests/final_bank_summary.json`

当前正式题库总数:

- 单轮题 `457`
- 多轮组 `110`
- 合计 `567`

模块数量已对齐设计配额:

- `A1 50`
- `A2 40`
- `A3 50`
- `A4 30`
- `A5 30`
- `B1 40`
- `B2 41`
- `B3 40`
- `B4 30`
- `B5 40`
- `B6 30`
- `B7 30`
- `B8 66`
- `C1 15`
- `C2 15`
- `C3 10`
- `C4 10`

## 仍待执行的工作

### P0: 继续补候选层

1. `IFEval` 扩成完整快照
2. `MMLU-Pro` 扩成完整快照
3. `JailbreakBench` 扩成完整快照
4. `LiveBench instruction_following` 扩成完整快照
5. `LiveCodeBench` 从种子扩到更完整快照
6. `OR-Bench` 从种子扩到更完整快照
7. `CNN/DailyMail` 补齐 `DailyMail` 半边或等价摘要来源

### P1: 启动改写草案层

优先建议从以下模块开始:

1. `A1`
2. `A3`
3. `A5`
4. `B1`
5. `B3`
6. `B4`

原因是这些模块已经有较强的公开候选基础，最容易先形成高质量正式草案。

说明：这个阶段已经迈出第一版，后续重点从“有没有正式题库”转为“是否继续提升题面质量、来源完整度和评分稳健性”。

### P2: 生成多轮安全组

在 `B1/B2/B3` 草案稳定后再生成:

1. `B5`
2. `B6`
3. `B7`

### P3: 冻结探针集

最后冻结:

1. `C1`
2. `C2`
3. `C3`
4. `C4`

## MiniMax 验证状态

验证报告:

- `manifests/minimax_validation_report.json`

当前解读:

- 现有标准化文件的本地结构验证已通过
- 部分文件自动化远程验证成功，部分超时
- 超时目前应视为运营层重试项，而不是设计缺陷

## MiniMax 正式评测状态

当前已经可以:

- 读取正式题库层
- 调用 `MiniMax-M2.7`
- 写出逐题评分和模块汇总
- 将运行结果落在 `manifests/evaluation_runs/`

已完成一次 smoke run:

- 运行目录：`manifests/evaluation_runs/20260528T023310Z-387e99d6`
- 结果特点：`A2/A3` 成功完成；`A1/A4` 在当前网络条件下出现超时
- 当前结论：主链路已闭环，但长题需要更保守的超时和重试策略

## 一句话结论

现在的工作区已经从“只有部分公开候选文件”变成了“有正式题库生成器、有正式评测 runner、且主链路可运行”的状态。

此外，工作区现在已经具备一版**多模型测评系统骨架**：

- 支持多 provider 模型注册
- 支持页面发起 run
- 支持失败题重试
- 支持 canonical 汇总
- 支持 Markdown 报告生成
- 支持前端实时轮询展示
- 支持历史 MiniMax run 兼容渲染
- 支持题库浏览、逐题原题详情和多轮时间线
- 支持页面内新增 Provider / Model 的非密钥配置保存
- 前端会显示正式题库路径、Provider 配置路径和每个 run 的产物目录

## SQLite 迁移状态

当前已经完成:

- Provider / Model / Run / Item Score 的主状态存储迁移到 `manifests/evaluation.sqlite`
- 现有 `config/providers.json` 会作为兼容镜像继续保留
- 现有 `manifests/evaluation_runs/<run_id>/` 继续保留为评测产物目录
- 历史 run 目录会在服务启动时自动导入 SQLite

当前结构含义:

- `manifests/evaluation.sqlite`
  - 主状态库，供 API 和前端查询使用
- `config/providers.json`
  - 非密钥配置镜像，便于人工查看和初始化导入
- `manifests/evaluation_runs/<run_id>/`
  - 逐题结果、summary、canonical、report 等可读产物
