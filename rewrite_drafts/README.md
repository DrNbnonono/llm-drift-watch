# 改写草案层说明

本目录用于承接 `normalized/` 中的公开候选题，并把它们转换成项目内部可用的私有题草案。

这一层的职责不是“保存更多公开题”，而是回答以下问题:

- 这道正式题来自哪些候选来源
- 用了什么改写手法
- 目标要落到哪个模块和子类型
- 评分逻辑是否继承、是否重写
- 是否需要扩展成多轮脚本
- 是否已经通过人工审核和污染风险检查

推荐组织方式:

- `rewrite_drafts/A/`
- `rewrite_drafts/B/`
- `rewrite_drafts/C/`

每条草案建议遵循:

- [rewrite_task_draft.schema.json](../schema/rewrite_task_draft.schema.json)

本层的关键原则:

1. 不直接复制公开题面。
2. 改写后仍需保留可追溯 provenance。
3. 多轮题在这里生成，而不是在 `normalized/` 里直接拼接。
4. 只有通过审核的草案才能进入 `final_bank_specs/`。
