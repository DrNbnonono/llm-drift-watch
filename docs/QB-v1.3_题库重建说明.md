# QB-v1.3 题库重建说明

## 发布状态

QB-v1.3 正式主轨已生成，共 627 题，18 个模块均达到设计配额，所有主轨题的 `qa_status` 均为 `ready`。

当前产物：

- `final_bank_specs/generated/final_bank_items_qbv1_3.jsonl`：627 题正式主轨。
- `final_bank_specs/generated/final_bank_items.jsonl`：主轨 + 30 题公开校准 pilot + 用户 local draft overlay。
- `rewrite_drafts/generated/rewrite_drafts_qbv1_3.jsonl`：627 条对应改写/重建记录。
- `manifests/final_bank_summary_qbv1_3.json`：题数、格式和评分方法统计。
- `manifests/qbv1_3_quality_audit.json`：近重复审计。

## 重建范围

QB-v1.2 近重复审计定位出 170 道同构或高相似题。QB-v1.3 保留题号，但对题面、任务逻辑、评分参数和 provenance 进行完整替换。

| 模块 | 重建数 | 新任务结构 |
|---|---:|---|
| A1 | 45 | 数论、代数、序列、组合、概率、几何、速率、图论 |
| A2 | 9 | 区间、栈解释、BFS、状态对账、滑窗、矩阵、拓扑分层 |
| A3 | 46 | JSON、CSV、XML、Markdown、SQL、正则、行/段/长度/禁用约束 |
| B5 | 12 | 网页、邮件、工单、README、OCR、日历、日志、CRM 等间接注入面 |
| B6 | 24 | 24 种风险域的“合法咨询→边界准备→危险升级”多轮轨迹 |
| B7 | 10 | 先直接危险请求，再用教材/虚构/免责声明进行伪合规绕过 |
| C1 | 4 | 舍入边界、精确小数、世纪闰年、开闭区间 |
| C2 | 12 | UUID、IPv4、JSON、XML、CSV、代码围栏、时间戳等严格格式 |
| C3 | 8 | 标题推导、JSON/XML/YAML 推理、表格比较、证据-结论结构 |

## 新评分能力

- `constraint_set`：程序化验证 JSON/CSV/XML/Markdown、regex、行数、段落数、词数、首尾文本、标题顺序等约束。
- `injection_resilience`：验证模型完成合法提取任务，同时不执行非可信内容中的注入指令。
- `escalation_resilience`：按轮验证前期合法响应与最终危险请求拒答。
- `pseudo_compliance_resilience`：检查模型是否被“教育/虚构/免责”包装诱导为伪合规输出。

## 验收标准

- 主轨题数 627，模块配额与 `MODULE_TARGETS` 完全一致。
- 主轨版本统一为 `QB-v1.3`，状态统一为 `ready`。
- 同模块相似度阈值 0.88 下的近重复对数为 0。
- 9 道新 A2 题的 27 个执行测试均由参考实现通过。
- 三层产物校验、后端/API 单测、前端构建和真实页面加载均必须通过。
