from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path("data/llamafactory/diagnosis_sft_alpaca.json")
DEFAULT_OUTPUT_DIR = Path("data/llamafactory")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare deterministic smoke/train/eval splits for the 5060 Ti "
            "LLaMA-Factory SFT workflow."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source alpaca dataset JSON path. Default: {DEFAULT_SOURCE}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for split datasets. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--eval-count",
        type=int,
        default=48,
        help="Number of examples reserved for eval. Default: 48",
    )
    parser.add_argument(
        "--smoke-count",
        type=int,
        default=32,
        help=(
            "Number of examples used for smoke training. "
            "This subset is sampled from the train split. Default: 32"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for deterministic splitting. Default: 42",
    )
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(records)!r}")
    if not records:
        raise ValueError(f"Source dataset is empty: {path}")
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    records = load_records(args.source)

    if args.eval_count <= 0:
        raise ValueError("--eval-count must be positive")
    if args.smoke_count <= 0:
        raise ValueError("--smoke-count must be positive")
    if len(records) <= args.eval_count:
        raise ValueError(
            f"Dataset has {len(records)} records, but eval_count={args.eval_count} "
            "leaves no training data."
        )

    rng = random.Random(args.seed)
    indices = list(range(len(records)))
    rng.shuffle(indices)

    eval_indices = indices[: args.eval_count]
    train_indices = indices[args.eval_count :]

    if len(train_indices) < args.smoke_count:
        raise ValueError(
            f"Train split has only {len(train_indices)} records, smaller than "
            f"smoke_count={args.smoke_count}."
        )

    smoke_indices = train_indices[: args.smoke_count]

    train_records = [records[i] for i in train_indices]
    eval_records = [records[i] for i in eval_indices]
    smoke_records = [records[i] for i in smoke_indices]

    output_dir = args.output_dir
    smoke_path = output_dir / "diagnosis_sft_smoke_alpaca.json"
    train_path = output_dir / "diagnosis_sft_train_alpaca.json"
    eval_path = output_dir / "diagnosis_sft_eval_alpaca.json"
    report_path = output_dir / "prepare_5060ti_report.json"

    write_json(smoke_path, smoke_records)
    write_json(train_path, train_records)
    write_json(eval_path, eval_records)
    write_json(
        report_path,
        {
            "source": str(args.source),
            "seed": args.seed,
            "total_records": len(records),
            "train_count": len(train_records),
            "eval_count": len(eval_records),
            "smoke_count": len(smoke_records),
            "train_dataset": str(train_path),
            "eval_dataset": str(eval_path),
            "smoke_dataset": str(smoke_path),
            "note": "smoke split is a subset of the train split",
        },
    )

    print(
        json.dumps(
            {
                "train_count": len(train_records),
                "eval_count": len(eval_records),
                "smoke_count": len(smoke_records),
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
