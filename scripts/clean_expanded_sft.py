#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_CATEGORIES = ["dependency", "training", "data", "inference", "deployment"]
EXPECTED_INSTRUCTION = "你是一个训练与部署问题诊断助手。请根据输入内容输出 JSON。"

DEFAULT_INPUTS = {
    "dependency": "data/sft_expanded_dependency.jsonl",
    "training": "data/sft_expanded_training.jsonl",
    "data": "data/sft_expanded_data.jsonl",
    "inference": "data/sft_expanded_inference.jsonl",
    "deployment": "data/sft_expanded_deployment.jsonl",
}

SUSPICIOUS_PATTERNS = {
    "bad_api.available_chat_templates": ["available_chat_templates"],
    "bad_package.qwen_vl": ["pip install qwen-vl", "qwen_vl"],
    "bad_package.transformers_all": ["pip install transformers[all]"],
    "bad_command.vllm_generation": ["vllm generation --model"],
    "bad_fix.tf_cluster_resolver": ["tf.distribute.cluster_resolver"],
    "bad_fix.sequence_slice": ["sequence = [bos_id] + sequence[1:]"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean and filter expanded SFT JSONL samples.")
    parser.add_argument(
        "--output",
        default="data/sft_train_clean.jsonl",
        help="Merged clean training file.",
    )
    parser.add_argument(
        "--rejected-output",
        default="data/sft_train_rejected.jsonl",
        help="Rejected samples with reasons.",
    )
    parser.add_argument(
        "--report-output",
        default="data/sft_train_clean_report.json",
        help="JSON report with counts and reject reasons.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text().splitlines(), 1):
        if not raw_line.strip():
            continue
        record = json.loads(raw_line)
        record["_file"] = str(path)
        record["_line"] = line_no
        records.append(record)
    return records


def validate_schema(record: dict[str, Any], expected_category: str) -> list[str]:
    reasons: list[str] = []

    if record.get("instruction") != EXPECTED_INSTRUCTION:
        reasons.append("schema.instruction")

    input_data = record.get("input")
    output_data = record.get("output")
    if not isinstance(input_data, dict):
        return reasons + ["schema.input"]
    if not isinstance(output_data, dict):
        return reasons + ["schema.output"]

    for key in ["user_question", "environment", "command", "log"]:
        value = input_data.get(key)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"schema.input.{key}")

    category = output_data.get("category")
    severity = output_data.get("severity")
    if category not in ALLOWED_CATEGORIES:
        reasons.append("schema.output.category")
    if severity not in {"low", "medium", "high"}:
        reasons.append("schema.output.severity")
    if category != expected_category:
        reasons.append("category_mismatch")

    for key in ["summary", "root_cause"]:
        value = output_data.get(key)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"schema.output.{key}")

    for key in ["missing_info", "next_steps"]:
        value = output_data.get(key)
        if not isinstance(value, list) or not value:
            reasons.append(f"schema.output.{key}")
            continue
        if not all(isinstance(item, str) and item.strip() for item in value):
            reasons.append(f"schema.output.{key}")

    return reasons


def flatten_text(record: dict[str, Any]) -> str:
    output_data = record["output"]
    parts = [
        record["input"]["user_question"],
        record["input"]["environment"],
        record["input"]["command"],
        record["input"]["log"],
        output_data["summary"],
        output_data["root_cause"],
        *output_data["missing_info"],
        *output_data["next_steps"],
    ]
    return "\n".join(parts)


def suspicious_reasons(record: dict[str, Any]) -> list[str]:
    text = flatten_text(record)
    reasons: list[str] = []
    for reason, needles in SUSPICIOUS_PATTERNS.items():
        if any(needle in text for needle in needles):
            reasons.append(reason)
    return reasons


def dedup_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        record["output"]["category"].strip(),
        record["input"]["user_question"].strip(),
        record["input"]["log"].strip(),
    )


def strip_internal_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "instruction": record["instruction"],
        "input": record["input"],
        "output": record["output"],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()

    cleaned: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reject_reasons = Counter()
    kept_per_category = Counter()
    rejected_per_category = Counter()
    seen_keys: set[tuple[str, str, str]] = set()

    total_records = 0
    source_counts: dict[str, int] = {}

    for expected_category, filename in DEFAULT_INPUTS.items():
        path = Path(filename)
        rows = load_jsonl(path)
        source_counts[expected_category] = len(rows)
        total_records += len(rows)

        for record in rows:
            reasons = validate_schema(record, expected_category)
            reasons.extend(suspicious_reasons(record))

            key = dedup_key(record) if not reasons else None
            if key is not None and key in seen_keys:
                reasons.append("duplicate.question_log")

            if reasons:
                rejected_per_category[expected_category] += 1
                for reason in set(reasons):
                    reject_reasons[reason] += 1
                rejected.append(
                    {
                        "reasons": sorted(set(reasons)),
                        "source_file": record["_file"],
                        "source_line": record["_line"],
                        "record": strip_internal_fields(record),
                    }
                )
                continue

            seen_keys.add(key)
            normalized = strip_internal_fields(record)
            cleaned.append(normalized)
            kept_per_category[expected_category] += 1

    write_jsonl(Path(args.output), cleaned)
    write_jsonl(Path(args.rejected_output), rejected)

    report = {
        "total_input": total_records,
        "total_kept": len(cleaned),
        "total_rejected": len(rejected),
        "source_counts": source_counts,
        "kept_per_category": dict(kept_per_category),
        "rejected_per_category": dict(rejected_per_category),
        "reject_reasons": dict(reject_reasons.most_common()),
    }
    Path(args.report_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
