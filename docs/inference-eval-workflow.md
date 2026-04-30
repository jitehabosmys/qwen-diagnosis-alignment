# 推理评测流程

这份文档描述的是当前仓库第一版 `base model vs LoRA adapter` 推理评测流程。

目标不是一上来做复杂评测，而是先建立一条可复用的最小链路：

1. 用同一批样本分别跑 `base` 和 `lora`
2. 自动统计 JSON / schema 类硬指标
3. 再基于结果做人工抽检

当前推荐把评测矩阵按意图拆开：

- `default_prompt`
- `strict_json_prompt`

## 1. 相关文件

推理配置：

- [qwen25_05b_base_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_05b_base_hf_infer.yaml)
- [qwen25_05b_full_lora_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_05b_full_lora_hf_infer.yaml)
- [qwen25_3b_base_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_3b_base_hf_infer.yaml)
- [qwen25_3b_full_lora_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_3b_full_lora_hf_infer.yaml)
- [qwen3_4b_base_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_hf_infer.yaml)
- [qwen3_4b_full_lora_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer.yaml)
- [qwen25_05b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_05b_base_hf_infer_strict_json_prompt.yaml)
- [qwen25_05b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_05b_full_lora_hf_infer_strict_json_prompt.yaml)
- [qwen25_3b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_3b_base_hf_infer_strict_json_prompt.yaml)
- [qwen25_3b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen25_3b_full_lora_hf_infer_strict_json_prompt.yaml)
- [qwen3_4b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_hf_infer_strict_json_prompt.yaml)
- [qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml)

评测脚本：

- [run_inference_eval.py](/hy-tmp/llm-lab/scripts/run_inference_eval.py)

默认评测集：

- [diagnosis_sft_eval_alpaca.json](/hy-tmp/llm-lab/data/llamafactory/diagnosis_sft_eval_alpaca.json)
- [diagnosis_sft_strict_json_prompt_eval_alpaca.json](/hy-tmp/llm-lab/data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json)

## 2. 运行前提

这份脚本不是用仓库自己的 `.venv` 跑，而是建议直接复用 `LLaMA-Factory` 的环境：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
```

然后从仓库根目录执行脚本，或者显式指定脚本绝对路径。

如果模型依然需要通过 `ModelScope` 加载，先导出：

```bash
export USE_MODELSCOPE_HUB=1
```

## 3. 最小运行命令

先跑默认 prompt 矩阵的小规模对比：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix default_prompt --max-samples 10
```

这份脚本现在会默认按 `llm-lab` 仓库根目录解析：

- `data/llamafactory/diagnosis_sft_eval_alpaca.json`
- `configs/llamafactory/qwen25_05b_base_hf_infer.yaml`
- `configs/llamafactory/qwen25_05b_full_lora_hf_infer.yaml`

所以即使你当前工作目录在 `/hy-tmp/LLaMA-Factory`，也不需要手动把这些默认路径改成绝对路径。

默认行为：

- 使用 `48` 条 eval 集中的前 `10` 条
- 分别加载 `default_prompt_base` 与 `default_prompt_lora` 推理配置
- 输出到 `/hy-tmp/outputs/llm-lab-inference-eval/<timestamp>/`

如果要跑 strict prompt 矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix strict_json_prompt --max-samples 10
```

如果要一次跑完四组矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix both --max-samples 10
```

如果要跑 `Qwen2.5-3B` 的默认 prompt base/lora 矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix qwen25_3b_default_prompt --max-samples 10
```

如果要跑 `Qwen2.5-3B` 的 strict prompt base/lora 矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix qwen25_3b_strict_json_prompt --max-samples 10
```

如果要跑 `Qwen3-4B` 的默认 prompt base/lora 矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix qwen3_4b_default_prompt --max-samples 10
```

如果要跑 `Qwen3-4B` 的 strict prompt base/lora 矩阵：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py --matrix qwen3_4b_strict_json_prompt --max-samples 10
```

## 4. 输出内容

输出目录中会包含：

- `run_manifest.json`
- `<variant>_results.jsonl`
- `summary.json`

其中每条结果至少包含：

- `sample_id`
- `variant`
- `prompt`
- `raw_output`
- `response_length`
- `prompt_length`
- `finish_reason`
- `elapsed_seconds`
- `reference_output`
- `metrics`

## 5. 当前自动指标

第一版脚本先做硬规则评测：

- `json_parse_success`
- `required_fields_present`
- `no_extra_top_level_fields`
- `category_enum_valid`
- `severity_enum_valid`
- `summary_nonempty`
- `root_cause_nonempty`
- `missing_info_is_nonempty_list`
- `next_steps_is_nonempty_list`
- `schema_valid`

另外，如果参考答案可解析，还会附带：

- `category_matches_reference`
- `severity_matches_reference`

这些不是最终效果结论，但很适合做第一轮探针。

## 5.1 生成过程统计

当前脚本还会额外记录一些生成过程相关字段：

- `response_length`
- `prompt_length`
- `finish_reason`
- `elapsed_seconds`

并在 `summary.json` 里汇总：

- `response_length_avg`
- `prompt_length_avg`
- `elapsed_seconds_avg`
- `finish_reason_counts`

这组统计很适合用来观察：

- base 是否更容易生成更长、更拖尾的输出
- LoRA 是否因为更快命中目标格式而更早结束
- 更大模型的推理时间增长到底来自模型计算，还是来自生成长度变化

## 6. 人工检查建议

自动跑完以后，不要只看 `summary.json`。

建议人工优先检查：

1. `json_parse_success` 失败样本
2. `schema_valid` 失败样本
3. `base` 和 `lora` 差异最大的样本

人工重点看：

- 是否臆造输入中不存在的信息
- `next_steps` 是否具体可执行
- 是否更符合“工程化、克制”的任务风格

## 7. 下一步扩展

这份脚本故意只做第一层评测。  
如果这一轮已经能证明 `lora` 在结构稳定性上优于 `base`，再考虑继续加：

- 更完整的参考答案比对
- `LLM-as-a-judge`
- 更大的 probe set
- 多模型、多 adapter 批量对比
