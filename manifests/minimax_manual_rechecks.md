# MiniMax 人工复查

会话日期：`2026-05-17`

端点：

- `https://api.minimaxi.com/anthropic/v1`
- 模型：`MiniMax-M2`

本次会话人工确认：

1. 模型元数据查询成功，返回 HTTP `200`
2. `mmlu_pro` 示例提示成功，返回 HTTP `200`
3. `livecodebench_test_generation` 示例提示成功，返回 HTTP `200`
4. `jbb_harmful` 示例提示成功，返回 HTTP `200`

备注：

- 自动化串行验证仍报告部分超时情况
- 这些超时**不**意味着本地数据文件格式有问题
- 应将其视为运营层面的重试项，而非即时的结构性问题