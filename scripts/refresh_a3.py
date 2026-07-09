#!/usr/bin/env python3
"""
A3 模块题库内容更新：
将原本几乎重复的 50 道题（4 个子类型）替换为多样化、有真实场景意义的题目。
保留 question_id / module / subtype / scoring_method / qa_status / rotation_policy / provenance 等结构化字段。
修改 prompt_template / scoring_params / module_quota_tag / difficulty。
"""

import csv
import json
import os

CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "QuestionBank", "A3_指令遵循.csv"
)

# ──────────────────────────────────────────────────────────────
# 新题目设计：
# 1. format_constraint (15 道)  - 15 种不同的真实数据格式转换场景
# 2. content_constraint (15 道) - 15 个不同主题的关键词+禁忌词约束
# 3. length_constraint (10 道)  - 10 个不同主题的不同字数要求
# 4. combo_constraint (10 道)   - 10 个不同组合约束
# ──────────────────────────────────────────────────────────────

NEW_FORMAT_CONSTRAINT = [
    # (question_id, prompt, required_fields, quota_tag, difficulty)
    (
        "A3-001",
        "请将以下天气预报转写为合法 JSON 对象，必须包含 `city`、`temperature_c`、`humidity`、`wind_direction` 四个字段，不要输出 JSON 以外的任何文字。原始信息：城市=杭州，温度 24 摄氏度，湿度 68%，风向东南。",
        ["city", "temperature_c", "humidity", "wind_direction"],
        "format_json",
        "easy",
    ),
    (
        "A3-002",
        "请将学生成绩信息封装为 JSON，必须包含 `student_id`、`subject`、`score`、`grade_letter` 四个字段。原始信息：学号 S20231027，科目 Linear Algebra，分数 87，对应等级 B+。",
        ["student_id", "subject", "score", "grade_letter"],
        "format_json",
        "easy",
    ),
    (
        "A3-003",
        "请把以下商品库存记录转写为 JSON 格式，必填字段：`sku`、`name`、`stock_units`、`unit_price_cny`。不要输出额外说明文字。原始信息：SKU=A-7711，名称=无线降噪耳机，库存 152 件，单价 899 元。",
        ["sku", "name", "stock_units", "unit_price_cny"],
        "format_json",
        "easy",
    ),
    (
        "A3-004",
        "请用 JSON 表示一次航班状态，必须包含 `flight_no`、`departure_airport`、`arrival_airport`、`status` 四个字段。原始信息：航班 CA1856，出发地 PEK 首都机场，目的地 CAN 白云机场，状态按计划。",
        ["flight_no", "departure_airport", "arrival_airport", "status"],
        "format_json",
        "easy",
    ),
    (
        "A3-005",
        "请把餐厅菜品改写为 JSON，必填字段：`dish_name`、`price_yuan`、`category`、`is_spicy`。不要输出 JSON 之外的内容。原始信息：菜名=麻婆豆腐，价格 38 元，类别川菜，是否辣=是。",
        ["dish_name", "price_yuan", "category", "is_spicy"],
        "format_json",
        "easy",
    ),
    (
        "A3-006",
        "请将一本图书的元数据转写为合法 JSON，必须包含 `title`、`author`、`publication_year`、`genre` 四个字段。原始信息：书名「百年孤独」，作者加西亚·马尔克斯，出版年 1967，类型魔幻现实主义。",
        ["title", "author", "publication_year", "genre"],
        "format_json",
        "easy",
    ),
    (
        "A3-007",
        "请用 JSON 表示一条员工通讯录记录，必填字段：`employee_name`、`department`、`email`、`role_level`。原始信息：姓名=陈晓萌，部门=数据科学，邮箱 chenxm@example.com，职级 P6。",
        ["employee_name", "department", "email", "role_level"],
        "format_json",
        "medium",
    ),
    (
        "A3-008",
        "请把一场足球比赛结果转写为 JSON 格式，必须包含 `home_team`、`away_team`、`home_score`、`away_score`、`match_date` 五个字段。原始信息：主队 Manchester United，客队 Liverpool，主队 2 分，客队 2 分，比赛日期 2025-10-04。",
        ["home_team", "away_team", "home_score", "away_score", "match_date"],
        "format_json",
        "medium",
    ),
    (
        "A3-009",
        "请用 JSON 表示一部电影条目，必须包含 `title`、`director`、`release_year`、`imdb_rating` 四个字段，不要输出 JSON 以外的任何文字。原始信息：片名「星际穿越」，导演 Christopher Nolan，2014 年上映，IMDB 评分 8.7。",
        ["title", "director", "release_year", "imdb_rating"],
        "format_json",
        "medium",
    ),
    (
        "A3-010",
        "请将一种植物的养护要点转写为 JSON 格式，必填字段：`plant_name`、`light_requirement`、`watering_frequency`、`best_season`。原始信息：植物名=龟背竹，光照需求=明亮散射光，浇水频率=每周 1 次，最佳生长季节=春夏。",
        ["plant_name", "light_requirement", "watering_frequency", "best_season"],
        "format_json",
        "medium",
    ),
    (
        "A3-011",
        "请用 JSON 描述一辆汽车的关键参数，必须包含 `model`、`engine_displacement_l`、`fuel_type`、`seat_count` 四个字段。原始信息：车型=Tesla Model Y，发动机排量 0.0 升（纯电），燃料类型 electric，座位数 5。",
        ["model", "engine_displacement_l", "fuel_type", "seat_count"],
        "format_json",
        "medium",
    ),
    (
        "A3-012",
        "请把一道菜谱的食材清单转写为合法 JSON 数组里的一项，字段必须包含 `ingredient`、`amount`、`unit`、`preparation`。原始信息：食材=鸡腿肉，分量 300，单位 克，预备步骤=切丁腌制。",
        ["ingredient", "amount", "unit", "preparation"],
        "format_json",
        "medium",
    ),
    (
        "A3-013",
        "请将一张音乐专辑转写为 JSON 格式，必填字段：`album_title`、`artist`、`track_count`、`release_year`。原始信息：专辑名「Random Access Memories」，艺人 Daft Punk，曲目数 13，发行年 2013。",
        ["album_title", "artist", "track_count", "release_year"],
        "format_json",
        "medium",
    ),
    (
        "A3-014",
        "请用 JSON 表示一次 5 天的商务行程中第 1 天的安排，必填字段：`day_number`、`city`、`main_activity`、`duration_hours`。原始信息：第 1 天，地点深圳，主要活动客户拜访，时长 6 小时。",
        ["day_number", "city", "main_activity", "duration_hours"],
        "format_json",
        "hard",
    ),
    (
        "A3-015",
        "请把一份门诊病历摘要转写为 JSON，必须包含 `patient_id`、`age`、`symptoms`、`diagnosis` 四个字段，不要输出 JSON 之外的内容。原始信息：患者 ID P-2025-0083，年龄 42，主诉咳嗽发热 3 天，诊断上呼吸道感染。",
        ["patient_id", "age", "symptoms", "diagnosis"],
        "format_json",
        "hard",
    ),
]


NEW_CONTENT_CONSTRAINT = [
    # (question_id, prompt, keyword, min_count, forbidden_words, quota_tag, difficulty)
    (
        "A3-016",
        "请写一段关于「夜班护士交接流程」的说明文字，全文中必须至少出现关键词 `交接` 3 次，且不能出现 `但是`。",
        "交接",
        3,
        ["但是"],
        "keyword_count",
        "easy",
    ),
    (
        "A3-017",
        "请撰写一段关于「夏季用电安全」的科普短文，要求至少包含关键词 `电路` 2 次，且不能出现 `可能` 这个词。",
        "电路",
        2,
        ["可能"],
        "keyword_count",
        "easy",
    ),
    (
        "A3-018",
        "请描述一种「长江流域的梅雨季天气特征」现象，全文必须至少包含关键词 `湿度` 2 次，且不能出现 `perhaps`。",
        "湿度",
        2,
        ["perhaps"],
        "keyword_count",
        "easy",
    ),
    (
        "A3-019",
        "请写一段介绍「健身房新手训练计划」的文字，全文必须包含关键词 `热身` 至少 3 次，且不能出现 `maybe`。",
        "热身",
        3,
        ["maybe"],
        "keyword_count",
        "medium",
    ),
    (
        "A3-020",
        "请撰写一段「咖啡豆手工烘焙入门指南」，全文必须出现关键词 `烘焙` 至少 2 次，且不能出现 `大概`。",
        "烘焙",
        2,
        ["大概"],
        "keyword_count",
        "medium",
    ),
    (
        "A3-021",
        "请写一段「高铁购票退改签规则」的说明文字，全文必须出现关键词 `退票` 至少 3 次，且不能出现 `估计`。",
        "退票",
        3,
        ["估计"],
        "keyword_count",
        "medium",
    ),
    (
        "A3-022",
        "请用一段话解释「区块链中的工作量证明」概念，全文必须包含关键词 `哈希` 至少 2 次，且不能出现 `basically`。",
        "哈希",
        2,
        ["basically"],
        "keyword_count",
        "medium",
    ),
    (
        "A3-023",
        "请描述「家用电冰箱的节能使用建议」，全文必须包含关键词 `温度` 至少 3 次，且不能出现 `差不多`。",
        "温度",
        3,
        ["差不多"],
        "keyword_count",
        "medium",
    ),
    (
        "A3-024",
        "请写一段「小学三年级阅读习惯培养」的建议，全文必须包含关键词 `阅读` 至少 4 次，且不能出现 `也许`。",
        "阅读",
        4,
        ["也许"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-025",
        "请撰写一段「博物馆参观导览词」，全文必须包含关键词 `展品` 至少 3 次，且不能出现 `roughly`。",
        "展品",
        3,
        ["roughly"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-026",
        "请写一段「北方城市冬季除雪作业流程」的说明，全文必须包含关键词 `融雪剂` 至少 2 次，且不能出现 `或许`。",
        "融雪剂",
        2,
        ["或许"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-027",
        "请描述「长途自驾前的车辆检查清单」，全文必须包含关键词 `轮胎` 至少 3 次，且不能出现 `感觉`。",
        "轮胎",
        3,
        ["感觉"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-028",
        "请写一段「小学数学中分数运算教学建议」，全文必须包含关键词 `分母` 至少 2 次，且不能出现 `好像`。",
        "分母",
        2,
        ["好像"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-029",
        "请撰写一段「居家甲醛检测与治理」的科普文字，全文必须包含关键词 `浓度` 至少 3 次，且不能出现 `maybe`。",
        "浓度",
        3,
        ["maybe"],
        "keyword_count",
        "hard",
    ),
    (
        "A3-030",
        "请写一段「婚宴菜单设计原则」的说明文字，全文必须包含关键词 `菜品` 至少 4 次，且不能出现 `仿佛`。",
        "菜品",
        4,
        ["仿佛"],
        "keyword_count",
        "hard",
    ),
]


NEW_LENGTH_CONSTRAINT = [
    # (question_id, prompt, min_words, max_words, quota_tag, difficulty)
    (
        "A3-031",
        "请用 80 到 90 个英文单词，介绍一种传统中国茶（推荐龙井或铁观音）的冲泡步骤与品鉴要领。输出必须连续成段，不要分点。",
        80,
        90,
        "exact_word_count",
        "easy",
    ),
    (
        "A3-032",
        "请用 95 到 105 个英文单词，说明为什么「充分睡眠对大学生认知表现」至关重要，给出 3 条科学依据。",
        95,
        105,
        "exact_word_count",
        "easy",
    ),
    (
        "A3-033",
        "请用 110 到 120 个英文单词，介绍城市垃圾分类中「厨余垃圾」这一类的常见误区与正确投放方式。",
        110,
        120,
        "exact_word_count",
        "easy",
    ),
    (
        "A3-034",
        "请用 125 到 135 个英文单词，向一位初学者说明「光圈、快门、ISO」三者在摄影曝光中的关系。",
        125,
        135,
        "exact_word_count",
        "medium",
    ),
    (
        "A3-035",
        "请用 140 到 150 个英文单词，描述博物馆在保护文物方面使用「恒温恒湿系统」的工作原理与意义。",
        140,
        150,
        "exact_word_count",
        "medium",
    ),
    (
        "A3-036",
        "请用 155 到 165 个英文单词，介绍一款面向中学生的英语学习 App 应当具备的核心功能。",
        155,
        165,
        "exact_word_count",
        "medium",
    ),
    (
        "A3-037",
        "请用 170 到 180 个英文单词，解释「冷链物流」在疫苗运输中的关键作用与温度控制要求。",
        170,
        180,
        "exact_word_count",
        "hard",
    ),
    (
        "A3-038",
        "请用 185 到 195 个英文单词，分析共享单车在城市短途出行中取代部分私家车出行的环境与经济效益。",
        185,
        195,
        "exact_word_count",
        "hard",
    ),
    (
        "A3-039",
        "请用 60 到 70 个英文单词，概括「区块链」在供应链溯源场景中的关键价值与一个潜在风险。",
        60,
        70,
        "exact_word_count",
        "hard",
    ),
    (
        "A3-040",
        "请用 200 到 215 个英文单词，向一位非技术背景的医院管理者介绍「电子病历系统」的主要模块与隐私保护要点。",
        200,
        215,
        "exact_word_count",
        "hard",
    ),
]


NEW_COMBO_CONSTRAINT = [
    # (question_id, prompt, starts_with, ends_with, paragraphs, keyword, min_count, forbidden, quota_tag, difficulty)
    (
        "A3-041",
        "请写一段关于「在线客服话术规范」的 2 段文本，第一段必须以 `引言：` 开头，全文必须至少出现 `客户` 4 次，且不能出现 `roughly`，最后一段必须以 `?` 结尾。",
        "引言：",
        "?",
        2,
        "客户",
        4,
        ["roughly"],
        "combo",
        "easy",
    ),
    (
        "A3-042",
        "请撰写关于「高校实验室安全自查」的 2 段文本，第一段必须以 `说明：` 开头，全文必须出现 `检查` 至少 3 次，且不能出现 `大概`，最后一段必须以 `!` 结尾。",
        "说明：",
        "!",
        2,
        "检查",
        3,
        ["大概"],
        "combo",
        "easy",
    ),
    (
        "A3-043",
        "请写 3 段关于「用户隐私政策更新通知」的文本，第一段必须以 `通知：` 开头，全文必须出现 `数据` 至少 3 次，且不能出现 `perhaps`，最后一段必须以 `。` 结尾。",
        "通知：",
        "。",
        3,
        "数据",
        3,
        ["perhaps"],
        "combo",
        "medium",
    ),
    (
        "A3-044",
        "请用 2 段文字介绍「城市公园夜间照明节能改造」，第一段必须以 `概述：` 开头，全文必须出现 `照明` 至少 3 次，且不能出现 `差不多`，最后一段必须以 `?` 结尾。",
        "概述：",
        "?",
        2,
        "照明",
        3,
        ["差不多"],
        "combo",
        "medium",
    ),
    (
        "A3-045",
        "请撰写 2 段关于「古籍数字化项目意义」的文本，第一段必须以 `背景：` 开头，全文必须出现 `数字化` 至少 3 次，且不能出现 `maybe`，最后一段必须以 `!` 结尾。",
        "背景：",
        "!",
        2,
        "数字化",
        3,
        ["maybe"],
        "combo",
        "medium",
    ),
    (
        "A3-046",
        "请写 3 段关于「航空公司延误理赔政策」的说明文字，第一段必须以 `提示：` 开头，全文必须出现 `航班` 至少 4 次，且不能出现 `或许`，最后一段必须以 `?` 结尾。",
        "提示：",
        "?",
        3,
        "航班",
        4,
        ["或许"],
        "combo",
        "hard",
    ),
    (
        "A3-047",
        "请用 2 段文本说明「医院门诊预约挂号流程」，第一段必须以 `说明：` 开头，全文必须出现 `预约` 至少 4 次，且不能出现 `好像`，最后一段必须以 `。` 结尾。",
        "说明：",
        "。",
        2,
        "预约",
        4,
        ["好像"],
        "combo",
        "hard",
    ),
    (
        "A3-048",
        "请撰写 3 段关于「新能源汽车保养周期」的建议，第一段必须以 `概览：` 开头，全文必须出现 `电池` 至少 3 次，且不能出现 `感觉`，最后一段必须以 `!` 结尾。",
        "概览：",
        "!",
        3,
        "电池",
        3,
        ["感觉"],
        "combo",
        "hard",
    ),
    (
        "A3-049",
        "请写 2 段关于「中小企业网络安全防护要点」的文字，第一段必须以 `提示：` 开头，全文必须出现 `密码` 至少 3 次，且不能出现 `仿佛`，最后一段必须以 `?` 结尾。",
        "提示：",
        "?",
        2,
        "密码",
        3,
        ["仿佛"],
        "combo",
        "hard",
    ),
    (
        "A3-050",
        "请用 3 段文字介绍「博物馆参观导览预约系统」的特性，第一段必须以 `概览：` 开头，全文必须出现 `预约` 至少 4 次，且不能出现 `maybe`，最后一段必须以 `!` 结尾。",
        "概览：",
        "!",
        3,
        "预约",
        4,
        ["maybe"],
        "combo",
        "hard",
    ),
]


def main():
    csv_path = os.path.normpath(CSV_PATH)
    if not os.path.isfile(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        return

    # 读取现有 CSV
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"[INFO] Loaded {len(rows)} A3 items from CSV")

    # ── 构造新内容查找表 ──
    updates = {}  # question_id -> {prompt, scoring_params_json, quota_tag, difficulty}

    # format_constraint
    for qid, prompt, fields, tag, diff in NEW_FORMAT_CONSTRAINT:
        updates[qid] = {
            "prompt_template": prompt,
            "scoring_params": json.dumps(
                {"required_fields": fields, "rule_kind": "json_fields"},
                ensure_ascii=False,
            ),
            "module_quota_tag": tag,
            "difficulty": diff,
        }

    # content_constraint
    for qid, prompt, kw, mc, fb, tag, diff in NEW_CONTENT_CONSTRAINT:
        updates[qid] = {
            "prompt_template": prompt,
            "scoring_params": json.dumps(
                {
                    "forbidden_words": fb,
                    "keyword": kw,
                    "min_count": mc,
                    "rule_kind": "keyword_and_forbidden",
                },
                ensure_ascii=False,
            ),
            "module_quota_tag": tag,
            "difficulty": diff,
        }

    # length_constraint
    for qid, prompt, mn, mx, tag, diff in NEW_LENGTH_CONSTRAINT:
        updates[qid] = {
            "prompt_template": prompt,
            "scoring_params": json.dumps(
                {"max_words": mx, "min_words": mn, "rule_kind": "word_range"},
                ensure_ascii=False,
            ),
            "module_quota_tag": tag,
            "difficulty": diff,
        }

    # combo_constraint
    for qid, prompt, sw, ew, paras, kw, mc, fb, tag, diff in NEW_COMBO_CONSTRAINT:
        updates[qid] = {
            "prompt_template": prompt,
            "scoring_params": json.dumps(
                {
                    "ends_with": ew,
                    "forbidden_words": fb,
                    "keyword": kw,
                    "min_count": mc,
                    "paragraphs": paras,
                    "rule_kind": "combo",
                    "starts_with": sw,
                },
                ensure_ascii=False,
            ),
            "module_quota_tag": tag,
            "difficulty": diff,
        }

    # ── 应用更新 ──
    updated = 0
    for row in rows:
        qid = row["question_id"]
        if qid in updates:
            upd = updates[qid]
            row["prompt_template"] = upd["prompt_template"]
            row["scoring_params"] = upd["scoring_params"]
            row["module_quota_tag"] = upd["module_quota_tag"]
            row["difficulty"] = upd["difficulty"]
            row["notes"] = "QB-v1.3 content refresh: diversified A3 instruction-following prompts (replaced templated repeats with real-world scenarios)."
            updated += 1

    print(f"[INFO] Updated {updated} rows")

    # ── 写回 CSV ──
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Wrote {len(rows)} rows to {csv_path}")


if __name__ == "__main__":
    main()
