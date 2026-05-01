from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path("/hy-tmp/outputs/llm-lab-hf-vs-vllm")
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
REQUIRED_FIELDS = [
    "category",
    "severity",
    "summary",
    "root_cause",
    "missing_info",
    "next_steps",
]
CATEGORY_ENUM = {"dependency", "training", "data", "inference", "deployment"}
SEVERITY_ENUM = {"low", "medium", "high"}


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
class GenerationResult:
    sample_id: str
    variant: str
    prompt: str
    system: str | None
    raw_output: str
    reference_output: dict[str, Any] | None
    metrics: dict[str, Any]
    response_length: int | None
    prompt_length: int | None
    finish_reason: str | None
    elapsed_seconds: float


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a small-scale comparison between local Hugging Face inference "
            "and a vLLM OpenAI-compatible endpoint on the same eval samples."
        )
    )
    parser.add_argument("--hf-config", type=Path, required=True, help="HF/LLaMA-Factory inference config yaml.")
    parser.add_argument("--vllm-model", type=str, required=True, help="Model name exposed by the vLLM server.")
    parser.add_argument(
        "--vllm-base-url",
        type=str,
        default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"),
        help="OpenAI-compatible base URL for the vLLM server.",
    )
    parser.add_argument(
        "--vllm-api-key",
        type=str,
        default=os.getenv("OPENAI_API_KEY", "EMPTY"),
        help="API key for the vLLM OpenAI-compatible endpoint. Default: OPENAI_API_KEY or EMPTY.",
    )
    parser.add_argument(
        "--eval-data",
        type=Path,
        default=REPO_ROOT / "data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json",
        help="Eval dataset in alpaca JSON format.",
    )
    parser.add_argument("--max-samples", type=int, default=5, help="How many samples to compare. Default: 5")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: /hy-tmp/outputs/llm-lab-hf-vs-vllm/<timestamp>",
    )
    parser.add_argument(
        "--llamafactory-src",
        type=Path,
        default=Path(os.getenv("LLAMAFACTORY_SRC", "/hy-tmp/LLaMA-Factory/src")),
        help="Path to LLaMA-Factory src for importing ChatModel if not installed.",
    )
    return parser.parse_args()


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line in {path}: {raw_line}")
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value.strip())
    return data


def parse_scalar(raw: str) -> Any:
    if raw in {"null", "Null", "NULL", "~"}:
        return None
    if raw in {"true", "True"}:
        return True
    if raw in {"false", "False"}:
        return False
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def load_eval_records(path: Path, max_samples: int) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list-style eval data at {path}")
    if max_samples <= 0:
        return rows
    return rows[:max_samples]


def build_prompt(record: dict[str, Any]) -> str:
    instruction = (record.get("instruction") or "").strip()
    input_text = (record.get("input") or "").strip()
    if instruction and input_text:
        return f"{instruction}\n{input_text}"
    return instruction or input_text


def parse_reference_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def strict_parse_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    payload = text.strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, f"{exc.msg} at line {exc.lineno} column {exc.colno}"
    if not isinstance(parsed, dict):
        return None, f"Top-level JSON is {type(parsed).__name__}, expected object"
    return parsed, None


def evaluate_output(raw_output: str, reference: dict[str, Any] | None) -> dict[str, Any]:
    parsed, parse_error = strict_parse_json(raw_output)
    metrics: dict[str, Any] = {
        "json_parse_success": parsed is not None,
        "parse_error": parse_error,
        "required_fields_present": False,
        "no_extra_top_level_fields": False,
        "category_enum_valid": False,
        "severity_enum_valid": False,
        "summary_nonempty": False,
        "root_cause_nonempty": False,
        "missing_info_is_nonempty_list": False,
        "next_steps_is_nonempty_list": False,
        "schema_valid": False,
        "category_matches_reference": None,
        "severity_matches_reference": None,
    }
    if parsed is None:
        return metrics

    keys = set(parsed.keys())
    required = set(REQUIRED_FIELDS)
    metrics["required_fields_present"] = required.issubset(keys)
    metrics["no_extra_top_level_fields"] = keys == required
    metrics["category_enum_valid"] = parsed.get("category") in CATEGORY_ENUM
    metrics["severity_enum_valid"] = parsed.get("severity") in SEVERITY_ENUM
    metrics["summary_nonempty"] = isinstance(parsed.get("summary"), str) and bool(parsed.get("summary").strip())
    metrics["root_cause_nonempty"] = isinstance(parsed.get("root_cause"), str) and bool(
        parsed.get("root_cause").strip()
    )
    metrics["missing_info_is_nonempty_list"] = isinstance(parsed.get("missing_info"), list) and bool(
        parsed.get("missing_info")
    )
    metrics["next_steps_is_nonempty_list"] = isinstance(parsed.get("next_steps"), list) and bool(parsed.get("next_steps"))
    metrics["schema_valid"] = all(
        [
            metrics["required_fields_present"],
            metrics["no_extra_top_level_fields"],
            metrics["category_enum_valid"],
            metrics["severity_enum_valid"],
            metrics["summary_nonempty"],
            metrics["root_cause_nonempty"],
            metrics["missing_info_is_nonempty_list"],
            metrics["next_steps_is_nonempty_list"],
        ]
    )
    if reference is not None:
        metrics["category_matches_reference"] = parsed.get("category") == reference.get("category")
        metrics["severity_matches_reference"] = parsed.get("severity") == reference.get("severity")
    return metrics


def ensure_llamafactory_import(src_path: Path) -> None:
    try:
        import llamafactory  # noqa: F401
    except ImportError:
        candidate = src_path.resolve()
        if candidate.exists():
            sys.path.insert(0, str(candidate))
    import llamafactory  # noqa: F401


def make_output_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEFAULT_OUTPUT_ROOT / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def summarize_results(results: list[GenerationResult]) -> dict[str, Any]:
    total = len(results)
    summary: dict[str, Any] = {"total_samples": total}
    if total == 0:
        return summary

    metric_keys = [
        "json_parse_success",
        "required_fields_present",
        "no_extra_top_level_fields",
        "category_enum_valid",
        "severity_enum_valid",
        "summary_nonempty",
        "root_cause_nonempty",
        "missing_info_is_nonempty_list",
        "next_steps_is_nonempty_list",
        "schema_valid",
    ]
    for key in metric_keys:
        passed = sum(1 for result in results if result.metrics[key])
        summary[key] = {"count": passed, "rate": round(passed / total, 4)}

    finish_reason_counts: dict[str, int] = {}
    response_lengths = [result.response_length for result in results if isinstance(result.response_length, int)]
    prompt_lengths = [result.prompt_length for result in results if isinstance(result.prompt_length, int)]
    elapsed_seconds = [result.elapsed_seconds for result in results]
    for result in results:
        if isinstance(result.finish_reason, str):
            finish_reason_counts[result.finish_reason] = finish_reason_counts.get(result.finish_reason, 0) + 1

    generation_stats: dict[str, Any] = {
        "elapsed_seconds_avg": round(sum(elapsed_seconds) / len(elapsed_seconds), 4),
        "elapsed_seconds_min": round(min(elapsed_seconds), 4),
        "elapsed_seconds_max": round(max(elapsed_seconds), 4),
        "finish_reason_counts": finish_reason_counts,
    }
    if response_lengths:
        generation_stats["response_length_avg"] = round(sum(response_lengths) / len(response_lengths), 4)
        generation_stats["response_length_min"] = min(response_lengths)
        generation_stats["response_length_max"] = max(response_lengths)
    if prompt_lengths:
        generation_stats["prompt_length_avg"] = round(sum(prompt_lengths) / len(prompt_lengths), 4)
        generation_stats["prompt_length_min"] = min(prompt_lengths)
        generation_stats["prompt_length_max"] = max(prompt_lengths)
    summary["generation_stats"] = generation_stats
    return summary


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[GenerationResult]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(
                json.dumps(
                    {
                        "sample_id": row.sample_id,
                        "variant": row.variant,
                        "prompt": row.prompt,
                        "system": row.system,
                        "raw_output": row.raw_output,
                        "response_length": row.response_length,
                        "prompt_length": row.prompt_length,
                        "finish_reason": row.finish_reason,
                        "elapsed_seconds": row.elapsed_seconds,
                        "reference_output": row.reference_output,
                        "metrics": row.metrics,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def compare_variants(hf_results: list[GenerationResult], vllm_results: list[GenerationResult], hf_label: str, vllm_label: str) -> dict[str, Any]:
    by_id = {row.sample_id: row for row in vllm_results}
    rows = []
    for hf_row in hf_results:
        other = by_id[hf_row.sample_id]
        rows.append(
            {
                "sample_id": hf_row.sample_id,
                "hf_schema_valid": hf_row.metrics["schema_valid"],
                "vllm_schema_valid": other.metrics["schema_valid"],
                "hf_json_parse_success": hf_row.metrics["json_parse_success"],
                "vllm_json_parse_success": other.metrics["json_parse_success"],
                "hf_elapsed_seconds": hf_row.elapsed_seconds,
                "vllm_elapsed_seconds": other.elapsed_seconds,
                "hf_response_length": hf_row.response_length,
                "vllm_response_length": other.response_length,
            }
        )

    total = len(rows)
    summary = {
        "total_samples": total,
        "schema_valid_match_count": sum(1 for row in rows if row["hf_schema_valid"] == row["vllm_schema_valid"]),
        "json_parse_match_count": sum(
            1 for row in rows if row["hf_json_parse_success"] == row["vllm_json_parse_success"]
        ),
        "hf_avg_elapsed_seconds": round(sum(row["hf_elapsed_seconds"] for row in rows) / total, 4),
        "vllm_avg_elapsed_seconds": round(sum(row["vllm_elapsed_seconds"] for row in rows) / total, 4),
        "avg_elapsed_delta_vllm_minus_hf": round(
            sum(row["vllm_elapsed_seconds"] - row["hf_elapsed_seconds"] for row in rows) / total,
            4,
        ),
        "hf_avg_response_length": round(
            sum((row["hf_response_length"] or 0) for row in rows) / total,
            4,
        ),
        "vllm_avg_response_length": round(
            sum((row["vllm_response_length"] or 0) for row in rows) / total,
            4,
        ),
        "avg_response_length_delta_vllm_minus_hf": round(
            sum(((row["vllm_response_length"] or 0) - (row["hf_response_length"] or 0)) for row in rows) / total,
            4,
        ),
        "hf_label": hf_label,
        "vllm_label": vllm_label,
    }
    return {"summary": summary, "per_sample": rows}


def run_hf_variant(config: dict[str, Any], records: list[dict[str, Any]], label: str) -> list[GenerationResult]:
    from llamafactory.chat import ChatModel

    log(f"Loading HF variant `{label}`")
    chat_model = ChatModel(config)
    results: list[GenerationResult] = []
    for index, record in enumerate(records, start=1):
        sample_id = record.get("sample_id") or f"eval_{index:03d}"
        prompt_text = build_prompt(record)
        system = record.get("system")
        reference = parse_reference_json(record.get("output", ""))
        started = time.time()
        responses = chat_model.chat(messages=[{"role": "user", "content": prompt_text}], system=system)
        elapsed = time.time() - started
        first = responses[0] if responses else None
        raw_output = first.response_text if first else ""
        metrics = evaluate_output(raw_output, reference)
        results.append(
            GenerationResult(
                sample_id=sample_id,
                variant=label,
                prompt=prompt_text,
                system=system,
                raw_output=raw_output,
                reference_output=reference,
                metrics=metrics,
                response_length=first.response_length if first else None,
                prompt_length=first.prompt_length if first else None,
                finish_reason=first.finish_reason if first else None,
                elapsed_seconds=round(elapsed, 4),
            )
        )
        log(
            f"HF `{label}` sample {index}/{len(records)} ({sample_id}) "
            f"{elapsed:.2f}s | json={metrics['json_parse_success']} | schema={metrics['schema_valid']}"
        )
    return results


def run_vllm_variant(
    client: OpenAI,
    model_name: str,
    max_new_tokens: int,
    records: list[dict[str, Any]],
    label: str,
) -> list[GenerationResult]:
    log(f"Using vLLM model `{model_name}` as `{label}`")
    results: list[GenerationResult] = []
    for index, record in enumerate(records, start=1):
        sample_id = record.get("sample_id") or f"eval_{index:03d}"
        prompt_text = build_prompt(record)
        system = record.get("system")
        reference = parse_reference_json(record.get("output", ""))
        started = time.time()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system or ""},
                {"role": "user", "content": prompt_text},
            ],
            temperature=0,
            max_tokens=max_new_tokens,
        )
        elapsed = time.time() - started
        choice = response.choices[0]
        raw_output = choice.message.content or ""
        usage = getattr(response, "usage", None)
        prompt_length = getattr(usage, "prompt_tokens", None) if usage else None
        response_length = getattr(usage, "completion_tokens", None) if usage else None
        finish_reason = choice.finish_reason
        metrics = evaluate_output(raw_output, reference)
        results.append(
            GenerationResult(
                sample_id=sample_id,
                variant=label,
                prompt=prompt_text,
                system=system,
                raw_output=raw_output,
                reference_output=reference,
                metrics=metrics,
                response_length=response_length,
                prompt_length=prompt_length,
                finish_reason=finish_reason,
                elapsed_seconds=round(elapsed, 4),
            )
        )
        log(
            f"vLLM `{label}` sample {index}/{len(records)} ({sample_id}) "
            f"{elapsed:.2f}s | json={metrics['json_parse_success']} | schema={metrics['schema_valid']}"
        )
    return results


def main() -> None:
    args = parse_args()
    ensure_llamafactory_import(args.llamafactory_src)
    output_dir = make_output_dir(args.output_dir)
    hf_config = parse_simple_yaml(args.hf_config)
    records = load_eval_records(args.eval_data, args.max_samples)

    hf_label = args.hf_config.stem
    vllm_label = f"vllm_{args.vllm_model}"
    write_json(
        output_dir / "run_manifest.json",
        {
            "hf_config": str(args.hf_config),
            "vllm_model": args.vllm_model,
            "vllm_base_url": args.vllm_base_url,
            "eval_data": str(args.eval_data),
            "max_samples": args.max_samples,
        },
    )

    hf_results = run_hf_variant(hf_config, records, hf_label)
    write_jsonl(output_dir / "hf_results.jsonl", hf_results)
    write_json(output_dir / "hf_summary.json", summarize_results(hf_results))

    client = OpenAI(base_url=args.vllm_base_url, api_key=args.vllm_api_key)
    vllm_results = run_vllm_variant(
        client=client,
        model_name=args.vllm_model,
        max_new_tokens=int(hf_config.get("max_new_tokens", 512)),
        records=records,
        label=vllm_label,
    )
    write_jsonl(output_dir / "vllm_results.jsonl", vllm_results)
    write_json(output_dir / "vllm_summary.json", summarize_results(vllm_results))

    comparison = compare_variants(hf_results, vllm_results, hf_label, vllm_label)
    write_json(output_dir / "hf_vs_vllm_comparison.json", comparison)
    print(json.dumps({"output_dir": str(output_dir), "comparison_summary": comparison["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
