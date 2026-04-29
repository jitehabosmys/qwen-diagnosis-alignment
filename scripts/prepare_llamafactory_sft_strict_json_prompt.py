#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("data/llamafactory")

SOURCE_DATASETS = {
    "full": OUTPUT_DIR / "diagnosis_sft_alpaca.json",
    "train": OUTPUT_DIR / "diagnosis_sft_train_alpaca.json",
    "eval": OUTPUT_DIR / "diagnosis_sft_eval_alpaca.json",
    "smoke": OUTPUT_DIR / "diagnosis_sft_smoke_alpaca.json",
}

OUTPUT_DATASETS = {
    "full": OUTPUT_DIR / "diagnosis_sft_strict_json_prompt_alpaca.json",
    "train": OUTPUT_DIR / "diagnosis_sft_strict_json_prompt_train_alpaca.json",
    "eval": OUTPUT_DIR / "diagnosis_sft_strict_json_prompt_eval_alpaca.json",
    "smoke": OUTPUT_DIR / "diagnosis_sft_strict_json_prompt_smoke_alpaca.json",
}

OUTPUT_REPORT = OUTPUT_DIR / "prepare_strict_json_prompt_report.json"

STRICT_SYSTEM_PROMPT = (
    "你是一个训练与部署问题诊断助手。"
    "你的输出必须是严格合法的 JSON 对象。"
    "不要输出 Markdown，不要输出代码块，不要输出任何额外解释。"
)

STRICT_INSTRUCTION = (
    "请阅读下面的用户问题、环境、命令和日志。"
    "只输出一个严格合法的 JSON 对象，不要添加任何额外文本。"
    "JSON 顶层必须且只能包含以下字段："
    "category, severity, summary, root_cause, missing_info, next_steps。"
    "其中 category 只能是 dependency、training、data、inference、deployment 之一；"
    "severity 只能是 low、medium、high 之一；"
    "missing_info 和 next_steps 必须是非空数组。"
)


def load_json(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected JSON array in {path}")
    return rows


def convert_record(item: dict[str, Any]) -> dict[str, Any]:
    converted = dict(item)
    converted["instruction"] = STRICT_INSTRUCTION
    converted["system"] = STRICT_SYSTEM_PROMPT
    return converted


def build_dataset_info_entries() -> dict[str, Any]:
    return {
        "diagnosis_sft_strict_json_prompt_full": {
            "file_name": OUTPUT_DATASETS["full"].name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
        "diagnosis_sft_strict_json_prompt_train": {
            "file_name": OUTPUT_DATASETS["train"].name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
        "diagnosis_sft_strict_json_prompt_eval": {
            "file_name": OUTPUT_DATASETS["eval"].name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
        "diagnosis_sft_strict_json_prompt_smoke": {
            "file_name": OUTPUT_DATASETS["smoke"].name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "prompt_variant": "strict_json_prompt",
        "system_prompt": STRICT_SYSTEM_PROMPT,
        "instruction": STRICT_INSTRUCTION,
        "datasets": {},
    }

    for split_name, source_path in SOURCE_DATASETS.items():
        rows = load_json(source_path)
        converted = [convert_record(item) for item in rows]
        output_path = OUTPUT_DATASETS[split_name]
        output_path.write_text(json.dumps(converted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["datasets"][split_name] = {
            "source": str(source_path),
            "output": str(output_path),
            "count": len(converted),
        }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    OUTPUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
