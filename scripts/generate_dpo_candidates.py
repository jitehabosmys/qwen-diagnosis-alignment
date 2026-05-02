from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from openai import OpenAI


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
DEFAULT_TRAIN_DATA = REPO_ROOT / "data/llamafactory/diagnosis_sft_strict_json_prompt_train_alpaca.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data/dpo"
WINNER_VALUES = {"A", "B", "tie"}
DIMENSIONS = [
    "evidence_groundedness",
    "root_cause_quality",
    "actionability",
    "missing_info_quality",
    "overall_engineering_quality",
]
SCORE_RANGE = [1, 2, 3, 4, 5]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ[key] = value


load_env_file(DEFAULT_ENV_FILE)


@dataclass
class Sample:
    sample_id: str
    system: str | None
    instruction: str
    input_text: str
    reference_output: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate DPO candidate pairs by calling two Anthropic-compatible answer models "
            "and one OpenAI-compatible judge model, then export a LLaMA-Factory-compatible preference dataset."
        )
    )
    parser.add_argument("--input-data", type=Path, default=DEFAULT_TRAIN_DATA, help="Train alpaca json path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "generated_pairs",
        help="Output directory for DPO generation artifacts.",
    )
    parser.add_argument(
        "--anthropic-base-url",
        type=str,
        default=os.getenv("DPO_ANTHROPIC_BASE_URL", os.getenv("ANTHROPIC_BASE_URL")),
        help="Anthropic-compatible base URL for candidate generation.",
    )
    parser.add_argument(
        "--anthropic-api-key",
        type=str,
        default=os.getenv("DPO_ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
        help="Anthropic-compatible API key for candidate generation.",
    )
    parser.add_argument(
        "--anthropic-version",
        type=str,
        default=os.getenv("DPO_ANTHROPIC_VERSION", os.getenv("ANTHROPIC_VERSION", "2023-06-01")),
        help="Anthropic API version header.",
    )
    parser.add_argument(
        "--model-a",
        type=str,
        default=os.getenv("DPO_MODEL_A"),
        help="Model name for candidate A.",
    )
    parser.add_argument(
        "--model-a-api-key",
        type=str,
        default=os.getenv("DPO_MODEL_A_API_KEY"),
        help="Optional dedicated API key for candidate A model.",
    )
    parser.add_argument(
        "--model-b",
        type=str,
        default=os.getenv("DPO_MODEL_B"),
        help="Model name for candidate B.",
    )
    parser.add_argument(
        "--model-b-api-key",
        type=str,
        default=os.getenv("DPO_MODEL_B_API_KEY"),
        help="Optional dedicated API key for candidate B model.",
    )
    parser.add_argument(
        "--judge-base-url",
        type=str,
        default=os.getenv("DPO_JUDGE_BASE_URL", os.getenv("OPENAI_BASE_URL")),
        help="OpenAI-compatible base URL for judge model.",
    )
    parser.add_argument(
        "--judge-api-key",
        type=str,
        default=os.getenv("DPO_JUDGE_API_KEY", os.getenv("OPENAI_API_KEY")),
        help="API key for judge model.",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=os.getenv("DPO_JUDGE_MODEL", os.getenv("OPENAI_JUDGE_MODEL")),
        help="Judge model name.",
    )
    parser.add_argument("--max-samples", type=int, default=0, help="Limit number of prompts. 0 means all.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Generation temperature.")
    parser.add_argument("--max-output-tokens", type=int, default=700, help="Max output tokens for answer models.")
    parser.add_argument(
        "--sample-concurrency",
        type=int,
        default=1,
        help="Number of samples to process in parallel during candidate generation. Each sample uses 2 model calls.",
    )
    parser.add_argument(
        "--flush-every",
        type=int,
        default=10,
        help="Append intermediate outputs to disk every N processed samples.",
    )
    parser.add_argument("--use-reference", action="store_true", help="Include reference output in judge prompt.")
    return parser.parse_args()


def load_samples(path: Path, max_samples: int, seed: int) -> list[Sample]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list-style JSON data at {path}")

    samples: list[Sample] = []
    for idx, row in enumerate(rows, start=1):
        samples.append(
            Sample(
                sample_id=row.get("sample_id") or f"train_{idx:03d}",
                system=row.get("system"),
                instruction=row.get("instruction", ""),
                input_text=row.get("input", ""),
                reference_output=row.get("output", ""),
            )
        )

    if max_samples > 0 and len(samples) > max_samples:
        rng = random.Random(seed)
        samples = rng.sample(samples, max_samples)
        samples.sort(key=lambda x: x.sample_id)

    return samples


def build_user_prompt(sample: Sample) -> str:
    instruction = sample.instruction.strip()
    input_text = sample.input_text.strip()
    if instruction and input_text:
        return f"{instruction}\n{input_text}"
    return instruction or input_text


def make_openai_client(api_key: str | None, base_url: str | None) -> OpenAI:
    if not api_key:
        raise ValueError("Missing OpenAI-compatible API key for judge.")
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def make_anthropic_client(api_key: str | None, base_url: str | None, version: str | None) -> Anthropic:
    if not api_key:
        raise ValueError("Missing Anthropic-compatible API key for candidate generation.")
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if version:
        kwargs["default_headers"] = {"anthropic-version": version}
    return Anthropic(**kwargs)


def call_answer_model(
    client: Anthropic,
    model: str,
    sample: Sample,
    temperature: float,
    max_output_tokens: int,
) -> str:
    response = client.messages.create(
        model=model,
        system=sample.system or "",
        messages=[{"role": "user", "content": build_user_prompt(sample)}],
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def timed_call_answer_model(
    client: Anthropic,
    model: str,
    sample: Sample,
    temperature: float,
    max_output_tokens: int,
) -> tuple[str, float]:
    started = time.time()
    output = call_answer_model(client, model, sample, temperature, max_output_tokens)
    elapsed = time.time() - started
    return output, elapsed


def chunked[T](items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_judge_instructions() -> str:
    return (
        "You are an impartial evaluator for a Chinese training/deployment diagnosis assistant. "
        "Compare candidate A and candidate B for the same input. "
        "Judge only by the provided input, environment, command, and log. "
        "Prefer answers that are evidence-grounded, conservative, actionable, and helpful for engineering diagnosis. "
        "Do not reward verbosity. If both are similarly good or similarly bad, return tie. "
        "Return structured JSON only."
    )


def judge_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "winner": {"type": "string", "enum": ["A", "B", "tie"]},
            "winner_confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "dimension_winners": {
                "type": "object",
                "additionalProperties": False,
                "properties": {dimension: {"type": "string", "enum": ["A", "B", "tie"]} for dimension in DIMENSIONS},
                "required": DIMENSIONS,
            },
            "dimension_scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    dimension: {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "A_score": {"type": "integer", "enum": SCORE_RANGE},
                            "B_score": {"type": "integer", "enum": SCORE_RANGE},
                        },
                        "required": ["A_score", "B_score"],
                    }
                    for dimension in DIMENSIONS
                },
                "required": DIMENSIONS,
            },
            "overall_scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "A_score": {"type": "integer", "enum": SCORE_RANGE},
                    "B_score": {"type": "integer", "enum": SCORE_RANGE},
                },
                "required": ["A_score", "B_score"],
            },
            "reason": {"type": "string"},
        },
        "required": [
            "winner",
            "winner_confidence",
            "dimension_winners",
            "dimension_scores",
            "overall_scores",
            "reason",
        ],
    }


def call_judge_model(
    client: OpenAI,
    sample: Sample,
    model_a: str,
    model_b: str,
    candidate_a: str,
    candidate_b: str,
    judge_model: str,
    use_reference: bool,
) -> dict[str, Any]:
    content_parts: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": "\n".join(
                [
                    f"Sample ID: {sample.sample_id}",
                    f"System prompt: {sample.system or '(none)'}",
                    "Task input:",
                    build_user_prompt(sample),
                    "",
                    f"Candidate A ({model_a}):",
                    candidate_a,
                    "",
                    f"Candidate B ({model_b}):",
                    candidate_b,
                ]
            ),
        }
    ]

    if use_reference and sample.reference_output:
        content_parts.append(
            {
                "type": "input_text",
                "text": "Reference output (for calibration only, do not require exact wording match):\n"
                + sample.reference_output,
            }
        )

    response = client.responses.create(
        model=judge_model,
        temperature=0,
        instructions=build_judge_instructions(),
        input=[{"role": "user", "content": content_parts}],
        text={
            "format": {
                "type": "json_schema",
                "name": "dpo_pair_judge",
                "schema": judge_response_schema(),
                "strict": True,
            }
        },
        max_output_tokens=500,
    )
    return json.loads(response.output_text)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with path.open("a", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    if not args.model_a or not args.model_b or not args.judge_model:
        raise ValueError("Missing model names. Please set DPO_MODEL_A / DPO_MODEL_B / DPO_JUDGE_MODEL.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = args.output_dir / "candidate_pairs.jsonl"
    judge_path = args.output_dir / "judge_results.jsonl"
    dpo_jsonl_path = args.output_dir / "dpo_dataset.jsonl"
    dpo_json_path = args.output_dir / "dpo_dataset.json"

    # Truncate incremental output files for a fresh run.
    for path in (candidate_path, judge_path, dpo_jsonl_path):
        path.write_text("", encoding="utf-8")

    model_a_client = make_anthropic_client(
        args.model_a_api_key or args.anthropic_api_key,
        args.anthropic_base_url,
        args.anthropic_version,
    )
    model_b_client = make_anthropic_client(
        args.model_b_api_key or args.anthropic_api_key,
        args.anthropic_base_url,
        args.anthropic_version,
    )
    judge_client = make_openai_client(args.judge_api_key, args.judge_base_url)
    samples = load_samples(args.input_data, args.max_samples, args.seed)

    print(f"[generate_dpo_candidates] loaded {len(samples)} sample(s)")

    candidate_records: list[dict[str, Any]] = []
    judge_records: list[dict[str, Any]] = []
    dpo_records: list[dict[str, Any]] = []
    candidate_buffer: list[dict[str, Any]] = []
    judge_buffer: list[dict[str, Any]] = []
    dpo_buffer: list[dict[str, Any]] = []

    sample_concurrency = max(1, args.sample_concurrency)
    for batch_index, batch in enumerate(chunked(samples, sample_concurrency), start=1):
        batch_start = (batch_index - 1) * sample_concurrency + 1
        batch_end = batch_start + len(batch) - 1
        print(
            f"[generate_dpo_candidates] processing batch {batch_index} covering samples {batch_start}-{batch_end}",
            flush=True,
        )

        timing_map: dict[str, dict[str, float]] = {sample.sample_id: {"started_total": time.time()} for sample in batch}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch) * 2) as executor:
            future_map: dict[concurrent.futures.Future[tuple[str, float]], tuple[str, str]] = {}
            for sample in batch:
                print(
                    f"[generate_dpo_candidates] sample {samples.index(sample)+1}/{len(samples)} {sample.sample_id}",
                    flush=True,
                )
                future_a = executor.submit(
                    timed_call_answer_model,
                    model_a_client,
                    args.model_a,
                    sample,
                    args.temperature,
                    args.max_output_tokens,
                )
                future_b = executor.submit(
                    timed_call_answer_model,
                    model_b_client,
                    args.model_b,
                    sample,
                    args.temperature,
                    args.max_output_tokens,
                )
                future_map[future_a] = (sample.sample_id, "A")
                future_map[future_b] = (sample.sample_id, "B")

            answers: dict[str, dict[str, Any]] = {sample.sample_id: {} for sample in batch}
            for future in concurrent.futures.as_completed(future_map):
                sample_id, side = future_map[future]
                text, elapsed = future.result()
                answers[sample_id][f"candidate_{side.lower()}"] = text
                timing_map[sample_id][f"elapsed_{side.lower()}"] = elapsed

        for sample in batch:
            candidate_a = answers[sample.sample_id]["candidate_a"]
            candidate_b = answers[sample.sample_id]["candidate_b"]
            elapsed_a = timing_map[sample.sample_id]["elapsed_a"]
            elapsed_b = timing_map[sample.sample_id]["elapsed_b"]

            candidate_records.append(
                {
                    "sample_id": sample.sample_id,
                    "system": sample.system,
                    "instruction": sample.instruction,
                    "input": sample.input_text,
                    "reference_output": sample.reference_output,
                    "model_a": args.model_a,
                    "model_b": args.model_b,
                    "candidate_a": candidate_a,
                    "candidate_b": candidate_b,
                    "candidate_a_elapsed_seconds": round(elapsed_a, 4),
                    "candidate_b_elapsed_seconds": round(elapsed_b, 4),
                }
            )
            candidate_buffer.append(candidate_records[-1])

            started_judge = time.time()
            judge_result = call_judge_model(
                judge_client,
                sample,
                args.model_a,
                args.model_b,
                candidate_a,
                candidate_b,
                args.judge_model,
                args.use_reference,
            )
            elapsed_judge = time.time() - started_judge
            elapsed_total = time.time() - timing_map[sample.sample_id]["started_total"]

            judge_records.append(
                {
                    "sample_id": sample.sample_id,
                    "model_a": args.model_a,
                    "model_b": args.model_b,
                    "candidate_a": candidate_a,
                    "candidate_b": candidate_b,
                    "judge_model": args.judge_model,
                    "candidate_a_elapsed_seconds": round(elapsed_a, 4),
                    "candidate_b_elapsed_seconds": round(elapsed_b, 4),
                    "judge_elapsed_seconds": round(elapsed_judge, 4),
                    "total_elapsed_seconds": round(elapsed_total, 4),
                    "judge_result": judge_result,
                }
            )
            judge_buffer.append(judge_records[-1])

            winner = judge_result["winner"]
            if winner not in WINNER_VALUES:
                raise ValueError(f"Unexpected winner value: {winner}")

            if winner == "A":
                chosen = candidate_a
                rejected = candidate_b
                chosen_model = args.model_a
                rejected_model = args.model_b
            elif winner == "B":
                chosen = candidate_b
                rejected = candidate_a
                chosen_model = args.model_b
                rejected_model = args.model_a
            else:
                print(
                    "[generate_dpo_candidates] {} | A={:.2f}s | B={:.2f}s | judge={:.2f}s | total={:.2f}s | winner=tie | confidence={} | kept=no".format(
                        sample.sample_id,
                        elapsed_a,
                        elapsed_b,
                        elapsed_judge,
                        elapsed_total,
                        judge_result["winner_confidence"],
                    ),
                    flush=True,
                )
                continue

            dpo_records.append(
                {
                    "sample_id": sample.sample_id,
                    "system": sample.system or "",
                    "instruction": sample.instruction,
                    "input": sample.input_text,
                    "chosen": chosen,
                    "rejected": rejected,
                    "metadata": {
                        "chosen_model": chosen_model,
                        "rejected_model": rejected_model,
                        "judge_model": args.judge_model,
                        "winner_confidence": judge_result["winner_confidence"],
                        "dimension_winners": judge_result["dimension_winners"],
                        "dimension_scores": judge_result["dimension_scores"],
                        "overall_scores": judge_result["overall_scores"],
                        "judge_reason": judge_result["reason"],
                        "reference_output": sample.reference_output,
                    },
                }
            )
            dpo_buffer.append(dpo_records[-1])
            print(
                "[generate_dpo_candidates] {} | A={:.2f}s | B={:.2f}s | judge={:.2f}s | total={:.2f}s | winner={} | confidence={} | chosen={} | rejected={} | kept=yes".format(
                    sample.sample_id,
                    elapsed_a,
                    elapsed_b,
                    elapsed_judge,
                    elapsed_total,
                    winner,
                    judge_result["winner_confidence"],
                    chosen_model,
                    rejected_model,
                ),
                flush=True,
            )

            processed = len(judge_records)
            if args.flush_every > 0 and processed % args.flush_every == 0:
                append_jsonl(candidate_path, candidate_buffer)
                append_jsonl(judge_path, judge_buffer)
                append_jsonl(dpo_jsonl_path, dpo_buffer)
                print(
                    f"[generate_dpo_candidates] flushed intermediate outputs at {processed} judged samples",
                    flush=True,
                )
                candidate_buffer.clear()
                judge_buffer.clear()
                dpo_buffer.clear()

    manifest = {
        "input_data": str(args.input_data),
        "anthropic_base_url": args.anthropic_base_url,
        "model_a_api_key_source": "DPO_MODEL_A_API_KEY" if args.model_a_api_key else "DPO_ANTHROPIC_API_KEY",
        "model_b_api_key_source": "DPO_MODEL_B_API_KEY" if args.model_b_api_key else "DPO_ANTHROPIC_API_KEY",
        "judge_base_url": args.judge_base_url,
        "model_a": args.model_a,
        "model_b": args.model_b,
        "judge_model": args.judge_model,
        "temperature": args.temperature,
        "max_output_tokens": args.max_output_tokens,
        "num_samples": len(samples),
        "num_non_tie_pairs": len(dpo_records),
    }

    write_json(args.output_dir / "run_manifest.json", manifest)
    append_jsonl(candidate_path, candidate_buffer)
    append_jsonl(judge_path, judge_buffer)
    append_jsonl(dpo_jsonl_path, dpo_buffer)
    write_json(dpo_json_path, dpo_records)
    print(f"[generate_dpo_candidates] wrote outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
