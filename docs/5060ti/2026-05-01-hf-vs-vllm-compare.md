# 2026-05-01 HF vs vLLM 小规模对比实验

这份文档定义的是一个最小的 `HF vs vLLM` 对比实验，用于验证：

- 在同一个模型、同一组样本、同一套 strict 协议下
- `vLLM` 是否能在不显著破坏输出质量的前提下提升推理效率

## 1. 当前定位

这不是主评测链路替换计划，而是一个独立的基础设施验证实验。

在完成本实验之前：

- `HF` 仍然是当前正式评测主链路
- `vLLM` 只作为独立 smoke / 小样本对比对象

## 2. 相关文件

HF 配置：

- [qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml)

vLLM 配置：

- [qwen3_4b_full_lora_vllm_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_vllm_infer_strict_json_prompt.yaml)

对比脚本：

- [run_hf_vs_vllm_compare.py](/hy-tmp/llm-lab/scripts/run_hf_vs_vllm_compare.py)

## 3. 前置条件

需要两套环境：

### HF / LLaMA-Factory 环境

```bash
source /hy-tmp/LLaMA-Factory/.venv/bin/activate
```

### vLLM 独立环境

```bash
source /hy-tmp/vllm-venv/bin/activate
```

并且需要先启动 `vLLM` OpenAI 兼容服务。

## 4. 建议先启动的 vLLM 服务

建议先启动 `4B strict lora`：

```bash
source /hy-tmp/vllm-venv/bin/activate

python -m vllm.entrypoints.openai.api_server \
  --model /hy-tmp/models/Qwen/Qwen3-4B-Instruct-2507 \
  --served-model-name qwen3-4b-strict-lora-vllm \
  --trust-remote-code \
  --enable-lora \
  --lora-modules strict4b=/hy-tmp/outputs/llamafactory/qwen3-4b-full-lora-sft-strict-json-prompt-5090ti \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.9 \
  --host 0.0.0.0 \
  --port 8001
```

## 5. 最小对比命令

启动好 vLLM 服务后，在 `llm-lab` 环境中跑：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
python scripts/run_hf_vs_vllm_compare.py \
  --hf-config /hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml \
  --vllm-model qwen3-4b-strict-lora-vllm \
  --vllm-base-url http://127.0.0.1:8001/v1 \
  --eval-data /hy-tmp/llm-lab/data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json \
  --max-samples 5
```

## 6. 输出内容

输出目录中会包含：

- `hf_results.jsonl`
- `hf_summary.json`
- `vllm_results.jsonl`
- `vllm_summary.json`
- `hf_vs_vllm_comparison.json`

## 7. 当前最重要的比较项

优先看：

- `json_parse_success`
- `schema_valid`
- `response_length_avg`
- `elapsed_seconds_avg`
- `finish_reason_counts`

## 8. 一句话结论

这套小实验的目的不是立刻替换主评测链路，而是先回答：

**在 `4B strict lora` 上，`vLLM` 是否能以可接受的一致性换来明显更好的推理速度。**
