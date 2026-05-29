#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:-$ROOT_DIR/normalized}"
mkdir -p "$OUT_DIR"

page_size=100

normalize_page() {
  local source_key="$1"
  ruby -rjson -e '
    source_key = ARGV[0]
    payload = JSON.parse(STDIN.read)
    rows = payload.fetch("rows", []).map { |x| x.fetch("row") }

    rows.each do |row|
      obj =
        case source_key
        when "ifeval"
          original_id = row["key"].to_s
          {
            candidate_id: "ifeval-#{original_id}",
            source_name: "IFEval",
            source_dataset: "google/IFEval",
            source_split: "train",
            source_url: "https://huggingface.co/datasets/google/IFEval",
            original_id: original_id,
            module_candidates: ["A3", "C2", "C3"],
            task_family: "instruction_following",
            category: "verifiable_constraints",
            prompt: row["prompt"],
            turns: nil,
            options: nil,
            answer: nil,
            scoring_method: "rule",
            scoring_params: {
              instruction_id_list: row["instruction_id_list"] || [],
              kwargs: row["kwargs"] || []
            },
            anti_contamination_source: "Public benchmark reference; must be rewritten before entering final bank.",
            source_metadata: {
              instruction_id_list: row["instruction_id_list"] || [],
              kwargs: row["kwargs"] || []
            },
            direct_reuse_allowed: false,
            rewrite_guidance: "Keep the constraint pattern, but rewrite the task surface form, entities, and formatting demands into the project private prompt style.",
            notes: "Best suited for A3 strict or partial scoring and C2/C3 drift probes."
          }
        when "mmlu_pro"
          original_id = row["question_id"].to_s
          {
            candidate_id: "mmlu-pro-#{original_id}",
            source_name: "MMLU-Pro",
            source_dataset: "TIGER-Lab/MMLU-Pro",
            source_split: "test",
            source_url: "https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro",
            original_id: original_id,
            module_candidates: ["A5"],
            task_family: "knowledge_mcq",
            category: row["category"],
            prompt: row["question"],
            turns: nil,
            options: row["options"],
            answer: row["answer"],
            scoring_method: "em",
            scoring_params: {
              answer_index: row["answer_index"],
              option_count: (row["options"] || []).length
            },
            anti_contamination_source: row["src"],
            source_metadata: {
              src: row["src"],
              answer_index: row["answer_index"],
              cot_content_present: !row["cot_content"].to_s.empty?
            },
            direct_reuse_allowed: false,
            rewrite_guidance: "Retain the knowledge point and difficulty band, but rebuild options, distractors, and prompt framing; prefer 6-8 options and add project-specific reasoning format requirements.",
            notes: "Use as a topic and difficulty pool, not as a direct evaluation set."
          }
        when "jbb_harmful"
          original_id = row["Index"].to_s
          {
            candidate_id: "jbb-harmful-#{original_id}",
            source_name: "JailbreakBench",
            source_dataset: "JailbreakBench/JBB-Behaviors",
            source_split: "harmful",
            source_url: "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors",
            original_id: original_id,
            module_candidates: ["B1", "B2"],
            task_family: "harmful_behavior_goal",
            category: row["Category"],
            prompt: row["Goal"],
            turns: nil,
            options: nil,
            answer: nil,
            scoring_method: "wildguard_or_strongreject",
            scoring_params: {
              behavior: row["Behavior"],
              target_prefix: row["Target"]
            },
            anti_contamination_source: row["Source"],
            source_metadata: {
              behavior: row["Behavior"],
              target_prefix: row["Target"],
              source: row["Source"]
            },
            direct_reuse_allowed: false,
            rewrite_guidance: "Use the harmful behavior intent and category only; rewrite direct requests and attack wrappers into the project own B1/B2 template system.",
            notes: "Good base for fixed harmful behavior set and mapping to attack templates."
          }
        when "livebench_instruction"
          original_id = row["question_id"].to_s
          turns = row["turns"] || []
          {
            candidate_id: "livebench-inst-#{original_id}",
            source_name: "LiveBench-Instruction",
            source_dataset: "livebench/instruction_following",
            source_split: "test",
            source_url: "https://huggingface.co/datasets/livebench/instruction_following",
            original_id: original_id,
            module_candidates: ["A3", "C2"],
            task_family: "dynamic_instruction_following",
            category: row["category"],
            prompt: turns[0],
            turns: turns,
            options: nil,
            answer: nil,
            scoring_method: "rule",
            scoring_params: {
              task: row["task"],
              instruction_id_list: row["instruction_id_list"] || [],
              kwargs: row["kwargs"] || []
            },
            anti_contamination_source: row["citation"] || row["release_date"],
            source_metadata: {
              task: row["task"],
              task_prompt: row["task_prompt"],
              instruction_id_list: row["instruction_id_list"] || [],
              kwargs: row["kwargs"] || [],
              release_date: row["release_date"],
              livebench_release_date: row["livebench_release_date"],
              citation: row["citation"]
            },
            direct_reuse_allowed: false,
            rewrite_guidance: "Retain the constraint composition and freshness signal, but replace the source passage and exact surface form; use release metadata to prioritize recent material during quarterly rotation.",
            notes: "Useful for private reformulations of dynamic instruction-following probes."
          }
        else
          raise "unknown source_key=#{source_key}"
        end

      puts JSON.generate(obj)
    end
  ' "$source_key"
}

page_count() {
  ruby -rjson -e 'payload = JSON.parse(STDIN.read); puts payload.fetch("rows", []).length'
}

fetch_source() {
  local source_key="$1"
  local dataset="$2"
  local config="$3"
  local split="$4"
  local output_file="$5"

  : > "$output_file"
  local offset=0
  local fetched=0

  while true; do
    local url="https://datasets-server.huggingface.co/rows?dataset=${dataset}&config=${config}&split=${split}&offset=${offset}&length=${page_size}"
    local payload
    payload="$(curl -L -s --max-time 60 "$url")"
    local count
    count="$(printf '%s' "$payload" | page_count)"
    if [[ "$count" == "0" ]]; then
      break
    fi
    printf '%s' "$payload" | normalize_page "$source_key" >> "$output_file"
    fetched=$((fetched + count))
    offset=$((offset + count))
    if [[ "$count" -lt "$page_size" ]]; then
      break
    fi
  done

  printf '[ok] %s -> %s rows -> %s\n' "$source_key" "$fetched" "$output_file"
}

fetch_source "ifeval" "google%2FIFEval" "default" "train" "$OUT_DIR/ifeval_candidates.jsonl"
fetch_source "mmlu_pro" "TIGER-Lab%2FMMLU-Pro" "default" "test" "$OUT_DIR/mmlu_pro_candidates.jsonl"
fetch_source "jbb_harmful" "JailbreakBench%2FJBB-Behaviors" "behaviors" "harmful" "$OUT_DIR/jbb_harmful_candidates.jsonl"
fetch_source "livebench_instruction" "livebench%2Finstruction_following" "default" "test" "$OUT_DIR/livebench_instruction_candidates.jsonl"

cat > "$OUT_DIR/extraction_summary.json" <<EOF
[
  {
    "source_key": "ifeval",
    "output_file": "$OUT_DIR/ifeval_candidates.jsonl"
  },
  {
    "source_key": "mmlu_pro",
    "output_file": "$OUT_DIR/mmlu_pro_candidates.jsonl"
  },
  {
    "source_key": "jbb_harmful",
    "output_file": "$OUT_DIR/jbb_harmful_candidates.jsonl"
  },
  {
    "source_key": "livebench_instruction",
    "output_file": "$OUT_DIR/livebench_instruction_candidates.jsonl"
  }
]
EOF

printf '[ok] summary -> %s/extraction_summary.json\n' "$OUT_DIR"
