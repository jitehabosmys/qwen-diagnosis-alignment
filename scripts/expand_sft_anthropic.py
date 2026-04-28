#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = "curl/8.5.0"
ALLOWED_CATEGORIES = {"dependency", "training", "data", "inference", "deployment"}

SYSTEM_PROMPT = """你是一名负责构造训练数据的工程师。

任务：
1. 参考给定 seed 样本，为每条 seed 扩写出若干条“同类型但不重复”的新样本。
2. 输出必须是严格 JSON，且只能输出 JSON，不要添加解释。
3. 输出的每条样本必须保持与 seed 相同的 schema：
   - instruction
   - input.user_question
   - input.environment
   - input.command
   - input.log
   - output.category
   - output.severity
   - output.summary
   - output.root_cause
   - output.missing_info
   - output.next_steps
4. output.category 只能是以下之一：
   - dependency
   - training
   - data
   - inference
   - deployment
5. output.severity 只能是 low、medium、high。
6. output.missing_info 和 output.next_steps 必须是非空数组。
7. 不要照抄 seed，必须改写环境、命令、日志细节、提问方式或信息完整度。
8. 不要引入明显超出日志证据的强结论，风格要克制、工程化、可执行。
9. 尽量生成与单卡训练、推理部署、常见依赖问题相关的样本，避免过于小众的硬件或特殊框架。

输出格式：
{
  "generated": [
    {
      "seed_id": 1,
      "samples": [ ... ]
    }
  ]
}
"""


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Expand SFT seeds with an Anthropic-compatible API.")
    parser.add_argument("--seed-file", default="data/sft_seed_top49.json", help="Path to curated seed JSON file.")
    parser.add_argument("--output-file", default="data/sft_expanded_candidates.jsonl", help="Path to write generated JSONL samples.")
    parser.add_argument("--base-url", default=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), help="Anthropic-compatible API base URL.")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"), help="API key. Falls back to ANTHROPIC_API_KEY.")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"), help="Model name.")
    parser.add_argument("--anthropic-version", default=os.environ.get("ANTHROPIC_VERSION", "2023-06-01"), help="Anthropic API version header.")
    parser.add_argument("--max-workers", type=int, default=3, help="Concurrent request count.")
    parser.add_argument("--seeds-per-request", type=int, default=2, help="How many seeds to pack into one request.")
    parser.add_argument("--variants-per-seed", type=int, default=4, help="How many expansions to generate for each seed.")
    parser.add_argument("--max-tokens", type=int, default=4000, help="Max output tokens per request.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N seeds. 0 means all.")
    parser.add_argument("--category", choices=sorted(ALLOWED_CATEGORIES), help="Only expand one category at a time.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output file instead of appending.")
    return parser.parse_args()


def load_seeds(path: Path, limit: int, category: str | None) -> list[dict[str, Any]]:
    records = json.loads(path.read_text())
    if category:
        records = [record for record in records if record.get("output", {}).get("category") == category]
    if limit > 0:
        records = records[:limit]
    for idx, record in enumerate(records):
        record["_seed_id"] = idx
    return records


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_user_prompt(seed_batch: list[dict[str, Any]], variants_per_seed: int) -> str:
    simplified = []
    for record in seed_batch:
        simplified.append(
            {
                "seed_id": record["_seed_id"],
                "instruction": record["instruction"],
                "input": record["input"],
                "output": record["output"],
            }
        )
    payload = {
        "task": f"请为每条 seed 扩写 {variants_per_seed} 条新样本。",
        "requirements": [
            "保持同一任务类型和同一输出 schema。",
            "可以改写环境、命令、日志、用户描述方式和缺失信息，但不要直接复制 seed。",
            "output.category 与 seed 保持一致或保持在同一问题域内。",
            "next_steps 要具体、保守、可执行。",
            "missing_info 要体现继续排查时真正需要的上下文。",
        ],
        "seeds": simplified,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def post_messages(
    *,
    base_url: str,
    api_key: str,
    anthropic_version: str,
    model: str,
    max_tokens: int,
    temperature: float,
    user_prompt: str,
) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    url = base_url.rstrip("/") + "/v1/messages"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": anthropic_version,
            "user-agent": DEFAULT_USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_text(response: dict[str, Any]) -> str:
    parts = response.get("content", [])
    texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
    return "".join(texts).strip()


def parse_generated(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    groups = payload.get("generated", [])
    samples: list[dict[str, Any]] = []
    for group in groups:
        seed_id = group.get("seed_id")
        for item in group.get("samples", []):
            item["_source_seed_id"] = seed_id
            samples.append(item)
    return samples


def validate_sample(sample: dict[str, Any]) -> list[str]:
    errors = []
    if sample.get("instruction") != "你是一个训练与部署问题诊断助手。请根据输入内容输出 JSON。":
        errors.append("instruction mismatch")

    input_data = sample.get("input")
    output = sample.get("output")
    if not isinstance(input_data, dict):
        errors.append("input missing")
    if not isinstance(output, dict):
        errors.append("output missing")
        return errors

    for key in ["user_question", "environment", "command", "log"]:
        if not isinstance(input_data.get(key), str) or not input_data.get(key).strip():
            errors.append(f"bad input.{key}")

    if output.get("category") not in ALLOWED_CATEGORIES:
        errors.append("bad category")
    if output.get("severity") not in {"low", "medium", "high"}:
        errors.append("bad severity")
    for key in ["summary", "root_cause"]:
        if not isinstance(output.get(key), str) or not output.get(key).strip():
            errors.append(f"bad output.{key}")
    for key in ["missing_info", "next_steps"]:
        value = output.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
            errors.append(f"bad output.{key}")
    return errors


def strip_internal_fields(sample: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in sample.items() if not k.startswith("_")}


def write_samples(path: Path, samples: list[dict[str, Any]], overwrite: bool) -> None:
    mode = "w" if overwrite else "a"
    with path.open(mode) as f:
        for sample in samples:
            f.write(json.dumps(strip_internal_fields(sample), ensure_ascii=False) + "\n")


def expand_batch(args: argparse.Namespace, seed_batch: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt = build_user_prompt(seed_batch, args.variants_per_seed)
    started = time.time()
    response = post_messages(
        base_url=args.base_url,
        api_key=args.api_key,
        anthropic_version=args.anthropic_version,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        user_prompt=prompt,
    )
    text = extract_text(response)
    parsed = parse_generated(text)
    valid = []
    invalid = []
    for sample in parsed:
        errors = validate_sample(sample)
        if errors:
            invalid.append({"sample": sample, "errors": errors})
        else:
            valid.append(sample)
    stats = {
        "seed_ids": [record["_seed_id"] for record in seed_batch],
        "latency_sec": round(time.time() - started, 2),
        "valid": len(valid),
        "invalid": len(invalid),
    }
    return valid, {"stats": stats, "invalid": invalid, "raw_text": text}


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("Missing API key. Use --api-key or ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1

    seed_path = Path(args.seed_file)
    if not seed_path.exists():
        print(f"Seed file not found: {seed_path}", file=sys.stderr)
        return 1

    seeds = load_seeds(seed_path, args.limit, args.category)
    if not seeds:
        msg = f"No seeds found in {seed_path}"
        if args.category:
            msg += f" for category={args.category}"
        print(msg, file=sys.stderr)
        return 1
    batches = chunked(seeds, args.seeds_per_request)
    output_path = Path(args.output_file)
    if args.category and output_path.name == "sft_expanded_candidates.jsonl":
        output_path = Path("data") / f"sft_expanded_{args.category}.jsonl"
    log_path = output_path.with_suffix(output_path.suffix + ".log")
    error_path = output_path.with_suffix(output_path.suffix + ".invalid.jsonl")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite:
        output_path.write_text("")
        log_path.write_text("")
        error_path.write_text("")

    total_valid = 0
    total_invalid = 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {executor.submit(expand_batch, args, batch): batch for batch in batches}
        for future in as_completed(future_map):
            batch = future_map[future]
            seed_ids = [record["_seed_id"] for record in batch]
            try:
                valid, meta = future.result()
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                line = json.dumps({"seed_ids": seed_ids, "error": f"HTTP {exc.code}", "body": body}, ensure_ascii=False)
                with log_path.open("a") as f:
                    f.write(line + "\n")
                print(f"[error] seeds={seed_ids} http_status={exc.code}", file=sys.stderr)
                continue
            except Exception as exc:
                line = json.dumps({"seed_ids": seed_ids, "error": repr(exc)}, ensure_ascii=False)
                with log_path.open("a") as f:
                    f.write(line + "\n")
                print(f"[error] seeds={seed_ids} {exc}", file=sys.stderr)
                continue

            write_samples(output_path, valid, overwrite=False)
            with log_path.open("a") as f:
                f.write(json.dumps(meta["stats"], ensure_ascii=False) + "\n")
            with error_path.open("a") as f:
                for item in meta["invalid"]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            total_valid += len(valid)
            total_invalid += len(meta["invalid"])
            print(
                f"[done] seeds={seed_ids} valid={len(valid)} invalid={len(meta['invalid'])} latency={meta['stats']['latency_sec']}s",
                file=sys.stderr,
            )

    print(
        json.dumps(
            {
                "seed_file": str(seed_path),
                "category": args.category,
                "output_file": str(output_path),
                "batches": len(batches),
                "valid_samples": total_valid,
                "invalid_samples": total_invalid,
                "max_workers": args.max_workers,
                "seeds_per_request": args.seeds_per_request,
                "variants_per_seed": args.variants_per_seed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
