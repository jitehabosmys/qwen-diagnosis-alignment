#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_CATEGORIES = ["dependency", "training", "data", "inference", "deployment"]
DEFAULT_ANTHROPIC_SCRIPT = "scripts/expand_sft_anthropic.py"
DEFAULT_OPENAI_SCRIPT = "scripts/expand_sft_openai.py"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect expanded SFT samples until the total line count reaches a target.")
    parser.add_argument("--target-total", type=int, required=True, help="Stop when the total generated sample count reaches this value.")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES, help="Categories to cycle through.")
    parser.add_argument("--runner", default="uv run python", help="Command prefix used to execute the expansion script.")
    parser.add_argument(
        "--provider",
        choices=["auto", "anthropic", "openai"],
        default="auto",
        help="Which API-compatible expansion script to use. auto prefers Anthropic and falls back to OpenAI.",
    )
    parser.add_argument("--script", default="", help="Optional explicit expansion script path. Overrides --provider when set.")
    parser.add_argument("--variants-per-seed", type=int, default=3, help="Variants per seed request.")
    parser.add_argument("--seeds-per-request", type=int, default=1, help="Seeds packed into one request.")
    parser.add_argument("--max-workers", type=int, default=1, help="Worker count passed through to the expansion script.")
    parser.add_argument("--sleep-seconds", type=float, default=2.0, help="Delay between category runs.")
    parser.add_argument("--max-rounds", type=int, default=1000, help="Safety cap on total category runs.")
    return parser.parse_args()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def current_total(categories: list[str]) -> tuple[int, dict[str, int]]:
    per_category = {}
    total = 0
    for category in categories:
        path = Path("data") / f"sft_expanded_{category}.jsonl"
        count = count_lines(path)
        per_category[category] = count
        total += count
    return total, per_category


def resolve_script(args: argparse.Namespace) -> tuple[str, str]:
    if args.script:
        return args.script, "custom"
    if args.provider == "anthropic":
        return DEFAULT_ANTHROPIC_SCRIPT, "anthropic"
    if args.provider == "openai":
        return DEFAULT_OPENAI_SCRIPT, "openai"

    if os.environ.get("ANTHROPIC_API_KEY"):
        return DEFAULT_ANTHROPIC_SCRIPT, "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return DEFAULT_OPENAI_SCRIPT, "openai"

    raise RuntimeError(
        "No usable API credentials found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
        "or pass --provider/--script explicitly."
    )


def run_category(args: argparse.Namespace, category: str, script: str, provider_label: str) -> int:
    command = (
        args.runner.split()
        + [
            script,
            "--category",
            category,
            "--seeds-per-request",
            str(args.seeds_per_request),
            "--variants-per-seed",
            str(args.variants_per_seed),
            "--max-workers",
            str(args.max_workers),
        ]
    )
    print(f"[run] provider={provider_label} {' '.join(command)}", flush=True)
    proc = subprocess.run(command, cwd=Path.cwd())
    return proc.returncode


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    rounds = 0

    try:
        script, provider_label = resolve_script(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    while rounds < args.max_rounds:
        total, per_category = current_total(args.categories)
        print(
            json.dumps(
                {
                    "total": total,
                    "per_category": per_category,
                    "provider": provider_label,
                    "script": script,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if total >= args.target_total:
            print(f"Reached target total: {total} >= {args.target_total}", flush=True)
            return 0

        category = min(args.categories, key=lambda name: per_category.get(name, 0))
        code = run_category(args, category, script, provider_label)
        rounds += 1
        if code != 0:
            print(f"[warn] category={category} exit_code={code}", file=sys.stderr, flush=True)
        time.sleep(args.sleep_seconds)

    print(f"Stopped after max rounds: {args.max_rounds}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
