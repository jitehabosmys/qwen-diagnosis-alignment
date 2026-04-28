#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


SOURCE = Path("data/sft_seed.json")
BACKUP = Path("data/sft_seed.raw.txt")

INSTRUCTION = "你是一个训练与部署问题诊断助手。请根据输入内容输出 JSON。"

CATEGORY_MAP = {
    "dependency": "dependency",
    "cuda_memory": "training",
    "data_format": "data",
    "tokenizer": "inference",
    "vllm": "deployment",
}

ALLOWED_SEVERITIES = {"low", "medium", "high"}

BOILERPLATE_MISSING_INFO = {
    "无附加追踪需要。",
    "无需附加追踪。",
}

PHRASE_REPLACEMENTS = [
    (r"彻底", ""),
    (r"暴力", "直接"),
    (r"黑洞", "问题"),
    (r"灾难", "问题"),
    (r"大屠杀式", "大规模"),
    (r"生吞活剥", "大量"),
    (r"斩草除根般的", ""),
    (r"果断", ""),
    (r"硬是", ""),
    (r"死死", ""),
    (r"灯下黑", "遗漏"),
    (r"暴力改写", "调整"),
]


def split_blocks(text: str) -> list[str]:
    text = text.strip()
    blocks = text.split("\n  },\n  {\n")
    if not blocks:
        return []
    blocks[0] = blocks[0].lstrip("{\n")
    blocks[-1] = blocks[-1].rstrip("\n}\n").rstrip("\n}")
    return blocks


def parse_array_literal(raw: str) -> list[str] | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    return None


def extract_line_value(block: str, key: str) -> str | None:
    prefix = f'"{key}":'
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        raw = stripped[len(prefix) :].strip()
        if raw.endswith(","):
            raw = raw[:-1].rstrip()
        return raw
    return None


def extract_scalar(block: str, key: str) -> str | None:
    raw = extract_line_value(block, key)
    if raw is None or raw == "":
        return None
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return raw.replace('\\"', '"').replace("\\\\", "\\")


def extract_array(block: str, key: str) -> list[str] | None:
    raw = extract_line_value(block, key)
    if raw is None:
        return None
    return parse_array_literal(raw)


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    for pattern, repl in PHRASE_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned)
    cleaned = re.sub(r"[，、]{2,}", "，", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip(" ，。")
    if cleaned and cleaned[-1] not in "。.!?":
        cleaned += "。"
    return cleaned


def normalize_list(items: list[str] | None) -> list[str]:
    if not items:
        return []
    cleaned = []
    seen = set()
    for item in items:
        text = clean_text(item)
        if not text or text in BOILERPLATE_MISSING_INFO:
            continue
        if text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def infer_missing_info(category: str, record: dict) -> list[str]:
    input_data = record["input"]
    output = record["output"]
    hints = []
    log_text = (input_data.get("log") or "").lower()
    env_text = (input_data.get("environment") or "").lower()

    if category == "dependency":
        if "version" not in env_text:
            hints.append("相关库的准确版本号。")
        hints.append("完整的安装命令和报错上下文。")
    elif category == "training":
        if "out of memory" in log_text or "oom" in log_text:
            hints.extend(
                [
                    "训练时的 batch size、序列长度和精度设置。",
                    "是否启用了 gradient checkpointing、LoRA 或量化加载。",
                ]
            )
        else:
            hints.extend(
                [
                    "分布式配置、节点数和 GPU 数量。",
                    "出错前最后一段完整日志。",
                ]
            )
    elif category == "data":
        hints.extend(
            [
                "一条最小可复现的数据样本。",
                "预处理脚本或数据集配置片段。",
            ]
        )
    elif category == "inference":
        hints.extend(
            [
                "使用的模型名和 tokenizer 版本。",
                "触发报错的最小输入样例。",
            ]
        )
    elif category == "deployment":
        hints.extend(
            [
                "启动命令和关键环境变量。",
                "宿主机驱动、CUDA 和容器镜像版本。",
            ]
        )

    if output.get("severity") == "high" and not hints:
        hints.append("完整的错误堆栈和最小复现步骤。")
    return hints[:3]


def infer_next_steps(category: str, record: dict) -> list[str]:
    input_data = record["input"]
    log_text = (input_data.get("log") or "").lower()
    steps = []

    if category == "dependency":
        steps = [
            "核对 Python、PyTorch、CUDA 与相关扩展的版本组合是否兼容。",
            "在干净虚拟环境中复现，并保留完整安装日志。",
            "优先使用项目文档中明确支持的版本或预编译 wheel。",
        ]
    elif category == "training":
        if "out of memory" in log_text or "oom" in log_text:
            steps = [
                "降低 batch size 或 max sequence length，并确认使用了合适的量化或 LoRA 配置。",
                "检查是否启用了 gradient checkpointing、flash attention 或其他显存优化手段。",
                "记录出错前后的显存占用，判断是峰值过高还是碎片化问题。",
            ]
        else:
            steps = [
                "保留完整分布式日志，先确认是哪一个 rank 先报错或卡住。",
                "检查网络、NCCL 相关环境变量和节点间连通性。",
                "用更小的数据或单卡配置复现，缩小问题范围。",
            ]
    elif category == "data":
        steps = [
            "抽取一条最小样本单独跑预处理，先确认字段和编码是否符合预期。",
            "对数据集做 schema、编码和长度校验，避免脏样本进入训练。",
            "必要时降低并行处理数，确认问题不是由多进程放大的。",
        ]
    elif category == "inference":
        steps = [
            "确认模型、tokenizer 和 chat template 来自同一版本或同一仓库。",
            "先用最小输入复现，再检查模板、特殊 token 和返回参数是否匹配。",
            "如果是离线环境，确认所需的 tokenizer 或模板文件已经完整下载。",
        ]
    elif category == "deployment":
        steps = [
            "先核对驱动、CUDA、容器镜像和 vLLM 版本是否在支持矩阵内。",
            "用最小启动参数复现，再逐步加回显存利用率或并发配置。",
            "保留完整启动日志，重点检查 GPU 初始化、模板解析和内核编译相关报错。",
        ]
    return steps


def simplify_summary(summary: str, category: str, log_text: str) -> str:
    if summary:
        return clean_text(summary)

    if category == "dependency":
        return "依赖版本或二进制兼容性问题导致组件无法正常加载。"
    if category == "training":
        if "out of memory" in log_text or "oom" in log_text:
            return "训练过程出现显存不足，导致作业中断。"
        return "训练过程中的运行时配置或分布式通信异常导致任务失败。"
    if category == "data":
        return "数据格式或预处理流程异常导致样本无法被正确读取。"
    if category == "inference":
        return "推理前处理或模板配置异常导致输入无法正常解析。"
    return "部署或服务启动配置异常导致推理服务无法正常运行。"


def simplify_root_cause(root_cause: str, category: str) -> str:
    if root_cause:
        return clean_text(root_cause)
    defaults = {
        "dependency": "当前环境中的依赖版本、CUDA 组件或预编译扩展与目标库不兼容。",
        "training": "训练配置、显存预算或分布式运行条件与当前任务不匹配。",
        "data": "数据内容、编码或字段结构与预处理逻辑的假设不一致。",
        "inference": "tokenizer、chat template 或推理前处理参数之间存在不匹配。",
        "deployment": "驱动、CUDA、容器或服务配置之间存在版本或运行时不兼容。",
    }
    return defaults[category]


def clean_record(record: dict) -> dict:
    input_data = {
        "user_question": clean_text(record["input"].get("user_question")).rstrip("。"),
        "environment": clean_text(record["input"].get("environment")).rstrip("。"),
        "command": (record["input"].get("command") or "").strip(),
        "log": (record["input"].get("log") or "").strip(),
    }

    raw_category = (record["output"].get("category") or "").strip()
    category = CATEGORY_MAP.get(raw_category, "training")
    severity = (record["output"].get("severity") or "medium").strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"

    summary = simplify_summary(record["output"].get("summary") or "", category, input_data["log"].lower())
    root_cause = simplify_root_cause(record["output"].get("root_cause") or "", category)
    missing_info = normalize_list(record["output"].get("missing_info"))
    next_steps = normalize_list(record["output"].get("next_steps"))

    if not missing_info:
        missing_info = infer_missing_info(category, {"input": input_data, "output": {"severity": severity}})
    if not next_steps:
        next_steps = infer_next_steps(category, {"input": input_data})

    return {
        "instruction": INSTRUCTION,
        "input": input_data,
        "output": {
            "category": category,
            "severity": severity,
            "summary": summary,
            "root_cause": root_cause,
            "missing_info": missing_info,
            "next_steps": next_steps,
        },
    }


def parse_block(block: str) -> dict:
    return {
        "instruction": extract_scalar(block, "instruction") or INSTRUCTION,
        "input": {
            "user_question": extract_scalar(block, "user_question") or "",
            "environment": extract_scalar(block, "environment") or "",
            "command": extract_scalar(block, "command") or "",
            "log": extract_scalar(block, "log") or "",
        },
        "output": {
            "category": extract_scalar(block, "category") or "",
            "severity": extract_scalar(block, "severity") or "medium",
            "summary": extract_scalar(block, "summary") or "",
            "root_cause": extract_scalar(block, "root_cause") or "",
            "missing_info": extract_array(block, "missing_info"),
            "next_steps": extract_array(block, "next_steps"),
        },
    }


def main() -> None:
    if BACKUP.exists():
        raw_text = BACKUP.read_text()
    elif SOURCE.exists():
        raw_text = SOURCE.read_text()
    else:
        raise SystemExit(f"Source file not found: {SOURCE}")

    blocks = split_blocks(raw_text)
    records = [clean_record(parse_block(block)) for block in blocks]

    if not BACKUP.exists():
        BACKUP.write_text(raw_text)
    SOURCE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")

    print(f"Cleaned {len(records)} records.")
    print(f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()
