# 正式题库规格层说明

本目录用于冻结正式私有题库的规格信息，而不是保存公开来源题面。

建议保存的内容包括:

- `question_id`
- `module`
- `subtype`
- `item_format`
- `difficulty`
- `scoring_method`
- `rotation_policy`
- `qa_status`
- `provenance`

对于多轮组题，还应冻结:

- 固定脚本结构
- 分支规则
- 评分口径
- 版本号

建议遵循:

- [final_bank_item.schema.json](../schema/final_bank_item.schema.json)

设计原则:

1. 正式题库的运行控制信息和公开候选层分离。
2. 正式题规格可追溯到改写草案和公开来源，但不直接暴露公开原题。
3. 正式题的冻结、轮换、退役都应在这一层可记录。
