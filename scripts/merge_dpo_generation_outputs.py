from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DPO_ROOT = REPO_ROOT / "data/dpo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge multiple DPO generation output directories into one consolidated dataset, "
            "deduplicated by sample_id."
        )
    )
    parser.add_argument(
        "--input-dirs",
        nargs="+",
        required=True,
        help="List of generated_pairs_* directories to merge.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DPO_ROOT / "merged",
        help="Directory to write merged outputs.",
    )
    parser.add_argument(
        "--prefer-latest",
        action="store_true",
        help="When duplicate sample_id exists, keep the record from the later input dir instead of the first one.",
    )
    parser.add_argument(
        "--max-per-sample-id",
        type=int,
        default=1,
        help="Maximum number of records to keep for the same sample_id.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_records(
    input_dirs: list[Path],
    filename: str,
    prefer_latest: bool,
    max_per_sample_id: int,
) -> tuple[list[dict[str, Any]], Counter]:
    merged: dict[str, list[dict[str, Any]]] = {}
    duplicate_counter: Counter = Counter()

    iter_dirs = input_dirs if not prefer_latest else input_dirs
    for input_dir in iter_dirs:
        rows = read_jsonl(input_dir / filename)
        for row in rows:
            sample_id = row.get("sample_id")
            if not sample_id:
                continue
            if sample_id in merged and len(merged[sample_id]) >= max_per_sample_id:
                duplicate_counter[sample_id] += 1
                if prefer_latest:
                    merged[sample_id] = merged[sample_id][1:] + [row]
            else:
                merged.setdefault(sample_id, []).append(row)

    ordered: list[dict[str, Any]] = []
    for sample_id in sorted(merged):
        ordered.extend(merged[sample_id])
    return ordered, duplicate_counter


def main() -> None:
    args = parse_args()
    input_dirs = [Path(item).resolve() for item in args.input_dirs]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate_records, candidate_dups = merge_records(
        input_dirs, "candidate_pairs.jsonl", args.prefer_latest, args.max_per_sample_id
    )
    judge_records, judge_dups = merge_records(
        input_dirs, "judge_results.jsonl", args.prefer_latest, args.max_per_sample_id
    )
    dpo_records_jsonl, dpo_dups = merge_records(
        input_dirs, "dpo_dataset.jsonl", args.prefer_latest, args.max_per_sample_id
    )

    # Also emit array-json format for downstream convenience.
    dpo_records_json = [record for record in dpo_records_jsonl]

    write_jsonl(output_dir / "candidate_pairs.jsonl", candidate_records)
    write_jsonl(output_dir / "judge_results.jsonl", judge_records)
    write_jsonl(output_dir / "dpo_dataset.jsonl", dpo_records_jsonl)
    write_json(output_dir / "dpo_dataset.json", dpo_records_json)

    manifest = {
        "input_dirs": [str(path) for path in input_dirs],
        "prefer_latest": args.prefer_latest,
        "max_per_sample_id": args.max_per_sample_id,
        "candidate_pairs_count": len(candidate_records),
        "judge_results_count": len(judge_records),
        "dpo_dataset_count": len(dpo_records_jsonl),
        "candidate_duplicate_sample_ids": len(candidate_dups),
        "judge_duplicate_sample_ids": len(judge_dups),
        "dpo_duplicate_sample_ids": len(dpo_dups),
    }
    write_json(output_dir / "merge_manifest.json", manifest)

    print("[merge_dpo_generation_outputs] wrote merged outputs to", output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
