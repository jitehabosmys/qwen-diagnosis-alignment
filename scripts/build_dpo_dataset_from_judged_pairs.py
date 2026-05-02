from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "data/dpo/merged_ds_dsp_max2/judge_results.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/dpo/final"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build final LLaMA-Factory-compatible DPO datasets from merged judge_results.jsonl, "
            "exporting both high-only and high-plus-medium variants."
        )
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=DEFAULT_INPUT,
        help="Merged judge_results.jsonl path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write final DPO datasets.",
    )
    parser.add_argument(
        "--max-per-sample-id",
        type=int,
        default=2,
        help="Maximum number of pairs to keep for each sample_id per exported dataset.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_record(record: dict[str, Any]) -> dict[str, Any] | None:
    judge_result = record.get("judge_result", {})
    winner = judge_result.get("winner")
    if winner not in {"A", "B"}:
        return None

    if winner == "A":
        chosen = record["candidate_a"]
        rejected = record["candidate_b"]
        chosen_model = record["model_a"]
        rejected_model = record["model_b"]
    else:
        chosen = record["candidate_b"]
        rejected = record["candidate_a"]
        chosen_model = record["model_b"]
        rejected_model = record["model_a"]

    return {
        "sample_id": record["sample_id"],
        "system": record.get("system", "") or "",
        "instruction": record.get("instruction", ""),
        "input": record.get("input", ""),
        "chosen": chosen,
        "rejected": rejected,
        "metadata": {
            "chosen_model": chosen_model,
            "rejected_model": rejected_model,
            "judge_model": record.get("judge_model"),
            "winner": winner,
            "winner_confidence": judge_result.get("winner_confidence"),
            "dimension_winners": judge_result.get("dimension_winners"),
            "dimension_scores": judge_result.get("dimension_scores"),
            "overall_scores": judge_result.get("overall_scores"),
            "judge_reason": judge_result.get("reason"),
        },
    }


def select_records(
    rows: list[dict[str, Any]],
    allowed_confidences: set[str],
    max_per_sample_id: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        judge_result = row.get("judge_result", {})
        if judge_result.get("winner_confidence") not in allowed_confidences:
            continue
        normalized = normalize_record(row)
        if normalized is None:
            continue
        grouped.setdefault(normalized["sample_id"], []).append(normalized)

    selected: list[dict[str, Any]] = []
    for sample_id in sorted(grouped):
        records = grouped[sample_id]
        # Sort by confidence first, then by sum of overall scores delta if available.
        def sort_key(item: dict[str, Any]) -> tuple[int, float]:
            confidence = item["metadata"].get("winner_confidence")
            conf_rank = {"high": 2, "medium": 1, "low": 0}.get(confidence, 0)
            overall_scores = item["metadata"].get("overall_scores") or {}
            chosen_score = overall_scores.get("A_score")
            rejected_score = overall_scores.get("B_score")
            delta = 0.0
            winner = item["metadata"].get("winner")
            if isinstance(chosen_score, (int, float)) and isinstance(rejected_score, (int, float)):
                if winner == "A":
                    delta = float(chosen_score) - float(rejected_score)
                elif winner == "B":
                    delta = float(rejected_score) - float(chosen_score)
            return (conf_rank, delta)

        records.sort(key=sort_key, reverse=True)
        selected.extend(records[:max_per_sample_id])
    return selected


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(args.input_file)
    high_only = select_records(rows, {"high"}, args.max_per_sample_id)
    high_plus_medium = select_records(rows, {"high", "medium"}, args.max_per_sample_id)

    write_json(args.output_dir / "dpo_high_only.json", high_only)
    write_json(args.output_dir / "dpo_high_plus_medium.json", high_plus_medium)

    manifest = {
        "input_file": str(args.input_file),
        "max_per_sample_id": args.max_per_sample_id,
        "high_only_count": len(high_only),
        "high_plus_medium_count": len(high_plus_medium),
        "high_only_sample_ids": len({row["sample_id"] for row in high_only}),
        "high_plus_medium_sample_ids": len({row["sample_id"] for row in high_plus_medium}),
        "confidence_distribution": Counter(
            row.get("judge_result", {}).get("winner_confidence", "unknown") for row in rows if row.get("judge_result")
        ),
    }
    write_json(args.output_dir / "build_manifest.json", manifest)
    print("[build_dpo_dataset_from_judged_pairs] wrote outputs to", args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
