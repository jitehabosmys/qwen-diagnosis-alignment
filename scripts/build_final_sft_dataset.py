#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HQ400_PATH = Path("data/sft_train_high_quality_400.jsonl")
SEED49_PATH = Path("data/sft_seed_top49.json")
FINAL_JSONL_PATH = Path("data/sft_train_final.jsonl")
FINAL_JSON_PATH = Path("data/sft_train_final.json")
REPORT_PATH = Path("data/sft_train_final_report.json")

# Hand-picked after manual review:
# - keep seeds that are specific and technically plausible
# - skip seeds with overly theatrical explanations or risky workaround-style steps
KEEP_SEED_INDICES = [
    1, 3, 6, 7, 10, 11, 12, 13, 15, 16,
    17, 20, 21, 23, 25, 26, 29, 34, 35, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49,
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    hq_rows = load_jsonl(HQ400_PATH)
    seed_rows = json.loads(SEED49_PATH.read_text())
    selected_seeds = [seed_rows[i - 1] for i in KEEP_SEED_INDICES]

    final_rows = hq_rows + selected_seeds

    write_jsonl(FINAL_JSONL_PATH, final_rows)
    FINAL_JSON_PATH.write_text(json.dumps(final_rows, ensure_ascii=False, indent=2) + "\n")

    report = {
        "hq400_count": len(hq_rows),
        "selected_seed_count": len(selected_seeds),
        "final_total": len(final_rows),
        "selected_seed_indices": KEEP_SEED_INDICES,
        "final_category_counts": dict(Counter(row["output"]["category"] for row in final_rows)),
        "final_severity_counts": dict(Counter(row["output"]["severity"] for row in final_rows)),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
