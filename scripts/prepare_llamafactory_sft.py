#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

SOURCE_PATH = Path("data/sft_train_final.jsonl")
OUTPUT_DIR = Path("data/llamafactory")
OUTPUT_DATASET = OUTPUT_DIR / "diagnosis_sft_alpaca.json"
OUTPUT_DATASET_INFO = OUTPUT_DIR / "dataset_info.json"
OUTPUT_REPORT = OUTPUT_DIR / "prepare_report.json"

SYSTEM_PROMPT = "你是一个训练与部署问题诊断助手。请根据输入内容输出 JSON。"
INSTRUCTION = "请阅读下面的用户问题、环境、命令和日志，输出诊断结果 JSON。"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def format_input(item: dict) -> str:
    input_data = item["input"]
    return "\n".join(
        [
            f"用户问题: {input_data['user_question']}",
            f"环境: {input_data['environment']}",
            f"命令: {input_data['command']}",
            "日志:",
            input_data["log"],
        ]
    )


def convert_record(item: dict) -> dict:
    return {
        "instruction": INSTRUCTION,
        "input": format_input(item),
        "output": json.dumps(item["output"], ensure_ascii=False, indent=2),
        "system": SYSTEM_PROMPT,
    }


def main() -> int:
    rows = load_jsonl(SOURCE_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = [convert_record(item) for item in rows]
    OUTPUT_DATASET.write_text(json.dumps(converted, ensure_ascii=False, indent=2) + "\n")

    dataset_info = {
        "diagnosis_sft_final": {
            "file_name": OUTPUT_DATASET.name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        }
    }
    OUTPUT_DATASET_INFO.write_text(json.dumps(dataset_info, ensure_ascii=False, indent=2) + "\n")

    report = {
        "source": str(SOURCE_PATH),
        "output_dataset": str(OUTPUT_DATASET),
        "dataset_info": str(OUTPUT_DATASET_INFO),
        "total_records": len(converted),
        "format": "alpaca",
    }
    OUTPUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
