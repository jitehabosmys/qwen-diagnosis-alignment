#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path

ARCHIVE_DATA = Path("data/archive")
ARCHIVE_SCRIPTS = Path("scripts/archive")

DATA_FILES_TO_ARCHIVE = [
    "data/extra_seed.json",
    "data/sft_seed.json",
    "data/sft_seed.raw.txt",
    "data/sft_seed_top40.json",
    "data/sft_expanded_data.jsonl",
    "data/sft_expanded_data.jsonl.invalid.jsonl",
    "data/sft_expanded_data.jsonl.log",
    "data/sft_expanded_dependency.jsonl",
    "data/sft_expanded_dependency.jsonl.invalid.jsonl",
    "data/sft_expanded_dependency.jsonl.log",
    "data/sft_expanded_deployment.jsonl",
    "data/sft_expanded_deployment.jsonl.invalid.jsonl",
    "data/sft_expanded_deployment.jsonl.log",
    "data/sft_expanded_inference.jsonl",
    "data/sft_expanded_inference.jsonl.invalid.jsonl",
    "data/sft_expanded_inference.jsonl.log",
    "data/sft_expanded_training.jsonl",
    "data/sft_expanded_training.jsonl.invalid.jsonl",
    "data/sft_expanded_training.jsonl.log",
    "data/sft_train_clean.jsonl",
    "data/sft_train_clean_report.json",
    "data/sft_train_rejected.jsonl",
    "data/sft_train_high_quality.jsonl",
    "data/sft_train_high_quality_rejected.jsonl",
    "data/sft_train_high_quality_report.json",
    "data/sft_train_high_quality_400.jsonl",
    "data/sft_train_high_quality_400_rejected.jsonl",
    "data/sft_train_high_quality_400_report.json",
    "data/sft_train_high_quality_450.jsonl",
    "data/sft_train_high_quality_450_rejected.jsonl",
    "data/sft_train_high_quality_450_report.json",
]

SCRIPTS_TO_ARCHIVE = [
    "scripts/check_anthropic_api.py",
    "scripts/clean_sft_seed.py",
]


def move_file(path_str: str, target_dir: Path) -> None:
    path = Path(path_str)
    if not path.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        target.unlink()
    shutil.move(str(path), str(target))


def main() -> int:
    for path in DATA_FILES_TO_ARCHIVE:
        move_file(path, ARCHIVE_DATA)
    for path in SCRIPTS_TO_ARCHIVE:
        move_file(path, ARCHIVE_SCRIPTS)
    print("Archived intermediate data and scripts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
