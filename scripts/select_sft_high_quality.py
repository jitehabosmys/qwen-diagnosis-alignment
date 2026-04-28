#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

INPUT_PATH = Path("data/sft_train_clean.jsonl")
DEFAULT_OUTPUT = Path("data/sft_train_high_quality.jsonl")
DEFAULT_REJECTED = Path("data/sft_train_high_quality_rejected.jsonl")
DEFAULT_REPORT = Path("data/sft_train_high_quality_report.json")

GENERIC_ROOT_PATTERNS = [
    "可能由于",
    "可能是",
    "环境问题",
    "路径配置错误",
    "版本不兼容",
]

WEAK_STEP_PATTERNS = [
    "参考官方文档",
    "检查文档",
    "尝试在虚拟环境中重新安装",
    "在干净的虚拟环境中重新执行安装命令",
    "尝试使用浏览器手动下载",
    "使用在线 Jinja2 检查器",
    "忽略警告如果确认无影响",
    "torch.cuda.empty_cache()",
]

BAD_EXPLANATION_PATTERNS = [
    "先导入 bitsandbytes 再导入 transformers",
    "GradScaler 的 init_scale 参数为较小值",
    "日志记录、评估步骤或未释放的中间变量导致显存逐渐累积",
    "优化器状态和梯度累积在反向传播后未及时释放",
]

GOOD_SIGNAL_PATTERNS = [
    "LD_LIBRARY_PATH",
    "CUDA_HOME",
    "destroy_process_group()",
    "gpu_memory_utilization",
    "max_model_len",
    "dataset_info.json",
    "tokenizer_config.json",
    "hf_device_map",
    "sentencepiece",
    "ProcessGroup",
    "KV cache",
    "chat_template",
    "403",
]

ALLOWED_CATEGORIES = ["dependency", "training", "data", "inference", "deployment"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select a higher-quality subset from the cleaned SFT data.")
    parser.add_argument("--input", default=str(INPUT_PATH), help="Input clean JSONL path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output selected JSONL path.")
    parser.add_argument("--rejected-output", default=str(DEFAULT_REJECTED), help="Output rejected JSONL path.")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    parser.add_argument("--target-total", type=int, default=180, help="Target selected sample count.")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text().splitlines(), 1):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        row["_line"] = line_no
        rows.append(row)
    return rows


def flatten(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False)


def score_record(record: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    output = record["output"]
    text = flatten(record)
    root = output["root_cause"]
    steps = output["next_steps"]
    missing = output["missing_info"]

    if len(root) >= 28:
        score += 1
    if len(steps) >= 2:
        score += 1
    if len(missing) >= 2:
        score += 1

    if any(pattern in text for pattern in GOOD_SIGNAL_PATTERNS):
        score += 2
        reasons.append("specific_signal")

    if any(pattern in root for pattern in GENERIC_ROOT_PATTERNS):
        score -= 2
        reasons.append("generic_root")

    matched_weak_steps = [pattern for pattern in WEAK_STEP_PATTERNS if any(pattern in step for step in steps)]
    if matched_weak_steps:
        score -= len(matched_weak_steps)
        reasons.append("weak_steps")

    matched_bad = [pattern for pattern in BAD_EXPLANATION_PATTERNS if pattern in text]
    if matched_bad:
        score -= 3 * len(matched_bad)
        reasons.append("questionable_advice")

    if output["severity"] == "low":
        score -= 1
        reasons.append("low_severity")

    if "OOM" in record["input"]["log"] or "out of memory" in record["input"]["log"]:
        score += 1
        reasons.append("clear_log_signal")

    if "404" in record["input"]["log"] or "403" in record["input"]["log"] or "No such file or directory" in record["input"]["log"]:
        score += 1
        reasons.append("concrete_error")

    if "Traceback" in record["input"]["log"] or "RuntimeError" in record["input"]["log"] or "ValueError" in record["input"]["log"]:
        score += 1

    return score, sorted(set(reasons))


def category_quotas(rows: list[dict[str, Any]], target_total: int) -> dict[str, int]:
    counts = Counter(row["output"]["category"] for row in rows)
    total = len(rows)
    quotas = {}
    assigned = 0
    for category in ALLOWED_CATEGORIES:
        raw_quota = target_total * counts[category] / total
        quotas[category] = math.floor(raw_quota)
        assigned += quotas[category]

    remainder = target_total - assigned
    if remainder > 0:
        order = sorted(
            ALLOWED_CATEGORIES,
            key=lambda category: (target_total * counts[category] / total) - quotas[category],
            reverse=True,
        )
        for category in order[:remainder]:
            quotas[category] += 1

    return quotas


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    rows = load_rows(Path(args.input))

    scored_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        score, score_reasons = score_record(row)
        enriched = {
            "record": row,
            "score": score,
            "score_reasons": score_reasons,
        }
        scored_by_category[row["output"]["category"]].append(enriched)

    quotas = category_quotas(rows, min(args.target_total, len(rows)))

    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    score_distribution = Counter()
    selected_per_category = Counter()
    rejected_per_category = Counter()
    reject_reason_counts = Counter()

    for category in ALLOWED_CATEGORIES:
        bucket = scored_by_category[category]
        bucket.sort(
            key=lambda item: (
                item["score"],
                len(item["record"]["output"]["next_steps"]),
                len(item["record"]["output"]["missing_info"]),
                len(item["record"]["output"]["root_cause"]),
            ),
            reverse=True,
        )
        keep_n = min(quotas.get(category, 0), len(bucket))
        kept = bucket[:keep_n]
        dropped = bucket[keep_n:]

        for item in kept:
            record = item["record"]
            selected.append(record)
            selected_per_category[category] += 1
            score_distribution[item["score"]] += 1

        for item in dropped:
            rejected_per_category[category] += 1
            for reason in item["score_reasons"] or ["lower_ranked"]:
                reject_reason_counts[reason] += 1
            rejected.append(
                {
                    "score": item["score"],
                    "score_reasons": item["score_reasons"] or ["lower_ranked"],
                    "category": category,
                    "source_line": item["record"]["_line"],
                    "record": {
                        "instruction": item["record"]["instruction"],
                        "input": item["record"]["input"],
                        "output": item["record"]["output"],
                    },
                }
            )

    selected.sort(key=lambda row: (row["output"]["category"], row["input"]["user_question"]))

    cleaned_selected = [
        {
            "instruction": row["instruction"],
            "input": row["input"],
            "output": row["output"],
        }
        for row in selected
    ]

    write_jsonl(Path(args.output), cleaned_selected)
    write_jsonl(Path(args.rejected_output), rejected)

    report = {
        "input_total": len(rows),
        "selected_total": len(cleaned_selected),
        "rejected_total": len(rejected),
        "target_total": args.target_total,
        "quotas": quotas,
        "selected_per_category": dict(selected_per_category),
        "rejected_per_category": dict(rejected_per_category),
        "score_distribution": dict(sorted(score_distribution.items(), reverse=True)),
        "top_reject_reasons": dict(reject_reason_counts.most_common(20)),
    }
    Path(args.report_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
