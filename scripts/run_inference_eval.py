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
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_DATA = REPO_ROOT / "data/llamafactory/diagnosis_sft_eval_alpaca.json"
DEFAULT_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_05b_base_hf_infer.yaml"
DEFAULT_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_05b_full_lora_hf_infer.yaml"
DEFAULT_3B_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_3b_base_hf_infer.yaml"
DEFAULT_3B_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_3b_full_lora_hf_infer.yaml"
DEFAULT_4B_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen3_4b_base_hf_infer.yaml"
DEFAULT_4B_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen3_4b_full_lora_hf_infer.yaml"
DEFAULT_STRICT_EVAL_DATA = REPO_ROOT / "data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json"
DEFAULT_STRICT_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_05b_base_hf_infer_strict_json_prompt.yaml"
DEFAULT_STRICT_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_05b_full_lora_hf_infer_strict_json_prompt.yaml"
DEFAULT_3B_STRICT_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_3b_base_hf_infer_strict_json_prompt.yaml"
DEFAULT_3B_STRICT_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen25_3b_full_lora_hf_infer_strict_json_prompt.yaml"
DEFAULT_4B_STRICT_BASE_CONFIG = REPO_ROOT / "configs/llamafactory/qwen3_4b_base_hf_infer_strict_json_prompt.yaml"
DEFAULT_4B_STRICT_LORA_CONFIG = REPO_ROOT / "configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml"


@dataclass
class VariantSpec:
    name: str
    config_path: Path
    eval_data_path: Path | None = None


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run base-model vs LoRA-adapter inference on the diagnosis eval set "
            "and compute first-pass schema metrics."
        )
    )
    parser.add_argument(
        "--eval-data",
        type=Path,
        default=DEFAULT_EVAL_DATA,
        help=f"Eval dataset in alpaca JSON format. Default: {DEFAULT_EVAL_DATA}",
    )
    parser.add_argument(
        "--variant",
        action="append",
        help=(
            "Variant spec in the form name=path/to/config.yaml "
            "or name=path/to/config.yaml@path/to/eval.json. "
            "Can be repeated. If omitted, uses built-in base and lora configs."
        ),
    )
    parser.add_argument(
        "--matrix",
        choices=[
            "default_prompt",
            "strict_json_prompt",
            "both",
            "qwen25_3b_default_prompt",
            "qwen25_3b_strict_json_prompt",
            "qwen3_4b_default_prompt",
            "qwen3_4b_strict_json_prompt",
        ],
        default="default_prompt",
        help=(
            "Predefined evaluation matrix. "
            "`default_prompt` runs the existing base/lora pair; "
            "`strict_json_prompt` runs the strict-prompt base/lora pair; "
            "`both` runs all four 0.5B variants; "
            "`qwen25_3b_default_prompt` runs the 3B base/lora pair; "
            "`qwen25_3b_strict_json_prompt` runs the 3B strict base/lora pair; "
            "`qwen3_4b_default_prompt` runs the 4B base/lora pair; "
            "`qwen3_4b_strict_json_prompt` runs the 4B strict base/lora pair. "
            "Ignored when --variant is provided."
        ),
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=10,
        help="Maximum number of eval samples to run. Default: 10",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for results. Default: /hy-tmp/outputs/llm-lab-inference-eval/<timestamp>",
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
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected list-style eval data at {path}")
    if max_samples <= 0:
        return records
    return records[:max_samples]


def build_prompt(record: dict[str, Any]) -> str:
    instruction = (record.get("instruction") or "").strip()
    input_text = (record.get("input") or "").strip()
    if instruction and input_text:
        return f"{instruction}\n{input_text}"
    return instruction or input_text


def strict_parse_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    payload = text.strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, f"{exc.msg} at line {exc.lineno} column {exc.colno}"
    if not isinstance(parsed, dict):
        return None, f"Top-level JSON is {type(parsed).__name__}, expected object"
    return parsed, None


def parse_reference_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {"total_samples": 0}

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
    summary: dict[str, Any] = {"total_samples": total}
    for key in metric_keys:
        passed = sum(1 for result in results if result["metrics"][key])
        summary[key] = {"count": passed, "rate": round(passed / total, 4)}

    ref_keys = ["category_matches_reference", "severity_matches_reference"]
    for key in ref_keys:
        comparable = [result["metrics"][key] for result in results if result["metrics"][key] is not None]
        if comparable:
            passed = sum(1 for item in comparable if item)
            summary[key] = {"count": passed, "rate": round(passed / len(comparable), 4)}

    summary["failing_sample_ids"] = {
        "json_parse_success": [r["sample_id"] for r in results if not r["metrics"]["json_parse_success"]],
        "schema_valid": [r["sample_id"] for r in results if not r["metrics"]["schema_valid"]],
    }

    response_lengths = [r["response_length"] for r in results if isinstance(r.get("response_length"), int)]
    prompt_lengths = [r["prompt_length"] for r in results if isinstance(r.get("prompt_length"), int)]
    elapsed_seconds = [r["elapsed_seconds"] for r in results if isinstance(r.get("elapsed_seconds"), (int, float))]
    finish_reasons = {}
    finish_reason_counts: dict[str, int] = {}
    if response_lengths:
        finish_reasons["response_length_avg"] = round(sum(response_lengths) / len(response_lengths), 4)
        finish_reasons["response_length_min"] = min(response_lengths)
        finish_reasons["response_length_max"] = max(response_lengths)
    if prompt_lengths:
        finish_reasons["prompt_length_avg"] = round(sum(prompt_lengths) / len(prompt_lengths), 4)
        finish_reasons["prompt_length_min"] = min(prompt_lengths)
        finish_reasons["prompt_length_max"] = max(prompt_lengths)
    if elapsed_seconds:
        finish_reasons["elapsed_seconds_avg"] = round(sum(elapsed_seconds) / len(elapsed_seconds), 4)
        finish_reasons["elapsed_seconds_min"] = round(min(elapsed_seconds), 4)
        finish_reasons["elapsed_seconds_max"] = round(max(elapsed_seconds), 4)
    for result in results:
        reason = result.get("finish_reason")
        if isinstance(reason, str):
            finish_reason_counts[reason] = finish_reason_counts.get(reason, 0) + 1
    if finish_reason_counts:
        finish_reasons["finish_reason_counts"] = finish_reason_counts
    if finish_reasons:
        summary["generation_stats"] = finish_reasons
    return summary


def ensure_llamafactory_import(src_path: Path) -> None:
    try:
        import llamafactory  # noqa: F401
    except ImportError:
        candidate = src_path.resolve()
        if candidate.exists():
            sys.path.insert(0, str(candidate))
    import llamafactory  # noqa: F401  # type: ignore


def make_output_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path("/hy-tmp/outputs/llm-lab-inference-eval") / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_variant_specs(raw_variants: list[str] | None) -> list[VariantSpec]:
    if not raw_variants:
        return [
            VariantSpec(name="default_prompt_base", config_path=DEFAULT_BASE_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
            VariantSpec(name="default_prompt_lora", config_path=DEFAULT_LORA_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
        ]

    variants: list[VariantSpec] = []
    for item in raw_variants:
        if "=" not in item:
            raise ValueError(f"Variant must be in name=path form, got: {item}")
        name, path = item.split("=", 1)
        eval_data_path: Path | None = None
        if "@" in path:
            path, eval_data = path.split("@", 1)
            eval_data_path = Path(eval_data.strip())
            if not eval_data_path.is_absolute():
                eval_data_path = (REPO_ROOT / eval_data_path).resolve()
        config_path = Path(path.strip())
        if not config_path.is_absolute():
            config_path = (REPO_ROOT / config_path).resolve()
        variants.append(VariantSpec(name=name.strip(), config_path=config_path, eval_data_path=eval_data_path))
    return variants


def get_predefined_variants(matrix: str) -> list[VariantSpec]:
    if matrix == "default_prompt":
        return [
            VariantSpec(name="default_prompt_base", config_path=DEFAULT_BASE_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
            VariantSpec(name="default_prompt_lora", config_path=DEFAULT_LORA_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
        ]
    if matrix == "strict_json_prompt":
        return [
            VariantSpec(
                name="strict_json_prompt_base",
                config_path=DEFAULT_STRICT_BASE_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
            VariantSpec(
                name="strict_json_prompt_lora",
                config_path=DEFAULT_STRICT_LORA_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
        ]
    if matrix == "both":
        return [
            VariantSpec(name="default_prompt_base", config_path=DEFAULT_BASE_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
            VariantSpec(name="default_prompt_lora", config_path=DEFAULT_LORA_CONFIG, eval_data_path=DEFAULT_EVAL_DATA),
            VariantSpec(
                name="strict_json_prompt_base",
                config_path=DEFAULT_STRICT_BASE_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
            VariantSpec(
                name="strict_json_prompt_lora",
                config_path=DEFAULT_STRICT_LORA_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
        ]
    if matrix == "qwen25_3b_default_prompt":
        return [
            VariantSpec(
                name="qwen25_3b_default_prompt_base",
                config_path=DEFAULT_3B_BASE_CONFIG,
                eval_data_path=DEFAULT_EVAL_DATA,
            ),
            VariantSpec(
                name="qwen25_3b_default_prompt_lora",
                config_path=DEFAULT_3B_LORA_CONFIG,
                eval_data_path=DEFAULT_EVAL_DATA,
            ),
        ]
    if matrix == "qwen25_3b_strict_json_prompt":
        return [
            VariantSpec(
                name="qwen25_3b_strict_json_prompt_base",
                config_path=DEFAULT_3B_STRICT_BASE_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
            VariantSpec(
                name="qwen25_3b_strict_json_prompt_lora",
                config_path=DEFAULT_3B_STRICT_LORA_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
        ]
    if matrix == "qwen3_4b_default_prompt":
        return [
            VariantSpec(
                name="qwen3_4b_default_prompt_base",
                config_path=DEFAULT_4B_BASE_CONFIG,
                eval_data_path=DEFAULT_EVAL_DATA,
            ),
            VariantSpec(
                name="qwen3_4b_default_prompt_lora",
                config_path=DEFAULT_4B_LORA_CONFIG,
                eval_data_path=DEFAULT_EVAL_DATA,
            ),
        ]
    if matrix == "qwen3_4b_strict_json_prompt":
        return [
            VariantSpec(
                name="qwen3_4b_strict_json_prompt_base",
                config_path=DEFAULT_4B_STRICT_BASE_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
            VariantSpec(
                name="qwen3_4b_strict_json_prompt_lora",
                config_path=DEFAULT_4B_STRICT_LORA_CONFIG,
                eval_data_path=DEFAULT_STRICT_EVAL_DATA,
            ),
        ]
    raise ValueError(f"Unknown matrix: {matrix}")


def run_variant(
    name: str,
    config: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from llamafactory.chat import ChatModel

    log(f"Loading variant `{name}`")
    chat_model = ChatModel(config)
    if not bool(config.get("do_sample", False)):
        generation_config = getattr(getattr(chat_model, "engine", None), "model", None)
        generation_config = getattr(generation_config, "generation_config", None)
        if generation_config is not None:
            generation_config.do_sample = False
            for attr in ("temperature", "top_p", "top_k", "typical_p", "min_p"):
                if hasattr(generation_config, attr):
                    setattr(generation_config, attr, None)

    results: list[dict[str, Any]] = []
    total = len(records)
    log(f"Running variant `{name}` on {total} sample(s)")
    for index, record in enumerate(records, start=1):
        sample_id = record.get("sample_id") or f"eval_{index:03d}"
        prompt_text = build_prompt(record)
        system = record.get("system")
        reference = parse_reference_json(record.get("output", ""))
        started = time.time()
        responses = chat_model.chat(messages=[{"role": "user", "content": prompt_text}], system=system)
        first_response = responses[0] if responses else None
        response_text = first_response.response_text if first_response else ""
        metrics = evaluate_output(response_text, reference)
        elapsed = time.time() - started
        log(
            "Variant `{}` sample {}/{} ({}) finished in {:.2f}s | json_parse_success={} | schema_valid={}".format(
                name,
                index,
                total,
                sample_id,
                elapsed,
                metrics["json_parse_success"],
                metrics["schema_valid"],
            )
        )
        results.append(
            {
                "sample_id": sample_id,
                "variant": name,
                "prompt": prompt_text,
                "system": system,
                "raw_output": response_text,
                "response_length": first_response.response_length if first_response else None,
                "prompt_length": first_response.prompt_length if first_response else None,
                "finish_reason": first_response.finish_reason if first_response else None,
                "elapsed_seconds": round(elapsed, 4),
                "reference_output": reference,
                "metrics": metrics,
            }
        )
    return results


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    ensure_llamafactory_import(args.llamafactory_src)
    output_dir = make_output_dir(args.output_dir)
    variants = parse_variant_specs(args.variant) if args.variant else get_predefined_variants(args.matrix)
    log(f"Output directory: {output_dir}")
    log(f"Matrix mode: {args.matrix}")

    run_manifest = {
        "default_eval_data": str(args.eval_data),
        "matrix": args.matrix,
        "max_samples": args.max_samples,
        "output_dir": str(output_dir),
        "variants": [
            {
                "name": variant.name,
                "config_path": str(variant.config_path),
                "eval_data_path": str(variant.eval_data_path or args.eval_data),
            }
            for variant in variants
        ],
    }
    write_json(output_dir / "run_manifest.json", run_manifest)

    all_results: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, Any] = {}
    for variant in variants:
        config = parse_simple_yaml(variant.config_path)
        eval_data_path = variant.eval_data_path or args.eval_data
        records = load_eval_records(eval_data_path, args.max_samples)
        log(f"Prepared variant `{variant.name}` with eval data: {eval_data_path}")
        results = run_variant(variant.name, config, records)
        all_results[variant.name] = results
        summaries[variant.name] = summarize_results(results)
        write_jsonl(output_dir / f"{variant.name}_results.jsonl", results)
        log(f"Finished variant `{variant.name}`")

    write_json(output_dir / "summary.json", summaries)
    log("Wrote summary.json")

    print(json.dumps({"output_dir": str(output_dir), "variants": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
