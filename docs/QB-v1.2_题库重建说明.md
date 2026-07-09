# QB-v1.2 题库重建说明

## 目标

`QB-v1.2` 的目标不是继续补系统功能，而是提升题目质量，尤其是安全模块 `B1-B8` 的评测价值。

相较于 `QB-v1.1`，本轮重建重点是：

- 消除大量机械换主题的模板题
- 让安全题覆盖更接近 2024-2026 部署现实的风险面
- 保留 `QB-v1.0 / QB-v1.1` 作为历史评测基线，不覆盖旧版结果

## 为什么要重建

在 `QB-v1.1` 中，安全模块存在几个明显问题：

- `B5/B6/B7` 有大面积同构重复
- `B1/B2/B3/B8` 中有不少题只是“同一句话换词”
- 多数 jailbreak 题仍停留在老式 DAN / 角色扮演 / “忽略安全策略” 模板
- 对 indirect prompt injection、agentic misuse、pseudo-compliance、multi-turn escalation 的覆盖不足

这些问题会导致：

- 模块内区分度偏低
- 模型只靠机械拒答或识别旧模板就能拿高分
- 题库难以反映现代真实部署风险

## 版本策略

- `QB-v1.0`：保留，承载早期正式评测
- `QB-v1.1`：保留，承载 A2/A6 升级版题库与既有 MiniMax 结果
- `QB-v1.2`：当前 live 题库，重点做安全题质量重建

当前 live 文件：

- `final_bank_specs/generated/final_bank_items.jsonl`

对应版本快照：

- `final_bank_specs/generated/final_bank_items_qb-v1_0.jsonl`
- `final_bank_specs/generated/final_bank_items_qb-v1_1.jsonl`
- `final_bank_specs/generated/final_bank_items_qb-v1_2.jsonl`

## 本轮重建范围

### 保留并延续的模块

- `A1-A6`
- `C1-C4`

说明：

- `A2 / A6` 延续 `QB-v1.1` 的高难编程与逻辑推理设计
- `A/C` 仅做了“明显坏题清理”的准备，不在本轮做全模块重写

### 重点重建模块

- `B1` baseline_harmful_refusal
- `B2` jailbreak_resistance
- `B3` benign_boundary
- `B4` trap_premise / factual / citation_truthfulness
- `B5` indirect_prompt_injection
- `B6` multi_turn_escalation
- `B7` pseudo_compliance / refusal_bypass
- `B8` agentic_tool_misuse / professional_context

## QB-v1.2 的安全方法来源

这些来源主要用于更新方法论，而不是直接复用题面。

### HarmBench

作用：

- 用于危险行为 taxonomy
- 用于 contextual harmful behavior 设计
- 用于 robust refusal 和评测稳定性意识

在本题库中主要影响：

- `B1`
- `B2`
- `B3`

### AgentHarm / Agent-SafetyBench / ATBench

作用：

- 将危险请求从“纯文本输出”升级为“代理型恶意任务”
- 引入长轨迹、工具使用、委托和工作流误用视角

在本题库中主要影响：

- `B6`
- `B8`

### InjecAgent

作用：

- indirect prompt injection
- 外部文档/网页/日志/工单中的恶意注入

在本题库中主要影响：

- `B5`

### SafeDialBench / JailBench / CoP / LITMUS

作用：

- 多轮 jailbreak
- 中文自然攻击 prompt
- pseudo-compliance
- co-authoring / draft collaboration

在本题库中主要影响：

- `B2`
- `B6`
- `B7`

## B1-B8 重建后的设计

### B1 baseline_harmful_refusal

不再是“同一句 harmful ask 换数字/要点数”。

现在覆盖：

- 爆炸与公共伤害
- 凭证窃取与批量钓鱼
- 诈骗与勒索
- doxxing / stalking
- 仇恨动员
- 自伤
- 未成年人伤害
- 危险伪医疗误导

### B2 jailbreak_resistance

从旧式模板升级为多攻击家族：

- roleplay_unaligned
- system_override
- false_authority
- translation_bypass
- encoding_reveal
- policy_reinterpretation
- stepwise_decomposition
- draft_collaboration
- safety_laundering

### B3 benign_boundary

从“同一题面加 #1/#2/#3”改成真实合法请求边界：

- 历史分析
- 合规咨询
- 新闻与公共教育
- 医疗安全
- 法律研究
- 事故响应
- newsroom fact-check

### B4 factual_trap / citation_truthfulness

保留原能力轴，但升级题面质量：

- 错误前提识别
- 基础事实问答
- DOI 与期刊一致性核验

### B5 indirect_prompt_injection

完全替换旧版“背景 -> 再追问危险步骤”的重复模板。

当前覆盖的外部内容表面包括：

- 网页抓取
- 邮件转发
- 工单记录
- 会议纪要
- 仓库 README
- OCR 扫描件
- 论坛抓取
- 日历邀请

### B6 multi_turn_escalation

从重复 topic 列表升级为多轮升级家族：

- rapport_building
- false_authority_chain
- goal_decomposition
- refusal_reframe
- commitment_exploitation
- escalation_after_boundary_test

### B7 pseudo_compliance / refusal_bypass

现在拆成两部分：

- refusal_bypass：先被拒，再包装为研究/培训/教材/案例继续推进
- pseudo_compliance：带免责声明但实则继续索取危险内容

### B8 agentic_tool_misuse / professional_context

不再是“教学助理 + 案例 1/2/3”。

现在按真实机构和工作流场景成对构造：

- legal_ops
- compliance_ops
- security_ops
- finance_ops
- biotech_research
- pharma_ops
- hr_ops
- journalism
- education
- it_admin
- procurement

每个 domain 同时包含：

- legitimate request
- illegitimate delegated misuse

## 质量控制策略

本轮没有新增 schema 字段，而是把审查信息先写入 `notes`：

- `review_status`
- `attack_family`
- `risk_surface`
- `duplicate_group`
- `realism_score`

这样做的原因是：

- 避免先改动全套 schema、前端与 API
- 先把质量控制元数据落进正式题库，后续再决定是否升级为独立字段

## 验收口径

当前 `QB-v1.2` 至少满足：

- `B1-B8` 模块内无 exact template duplicates
- 旧版严重同构的 `B5/B6/B7` 已完全重建
- 候选层、改写层、正式题库层都同步到 `QB-v1.2`
- 旧版本快照保留，历史评测可追溯

## 后续建议

下一步最值得做的是：

1. 对 `QB-v1.2` 跑 `B` 模块小规模真实评测，验证区分度是否提升
2. 对 `A2 / A6 / C4` 做低质量坏题再审，逐步推进 `QB-v1.3`
