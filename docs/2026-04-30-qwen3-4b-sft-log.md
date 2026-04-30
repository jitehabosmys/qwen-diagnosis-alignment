# 2026-04-30 Qwen3-4B LoRA SFT 实验记录

这份记录对应一次在当前单卡环境上完成的 `Qwen3-4B-Instruct-2507 + LoRA` `SFT` 实验，以及随后基于 `48` 条评测集做的第一轮自动规则评测。

这轮实验的目标不是直接宣布 `4B` 成为最终答案，而是回答两个问题：

1. `4B` 在当前机器上是否稳定可训、可评测
2. `4B` 相比 `3B` 是否有继续 scale up 的潜力与价值

## 1. 实验标识

- 日期：`2026-04-30`
- 模型：`Qwen/Qwen3-4B-Instruct-2507`
- 微调方式：`LoRA`
- 模板：`qwen3_nothink`

训练配置：

- [5090ti_qwen3_4b_smoke_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_smoke_lora_sft.yaml)
- [5090ti_qwen3_4b_full_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_full_lora_sft.yaml)

推理配置：

- [qwen3_4b_base_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_hf_infer.yaml)
- [qwen3_4b_full_lora_hf_infer.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer.yaml)

训练输出目录：

- `/hy-tmp/outputs/llamafactory/qwen3-4b-smoke-lora-sft-5090ti`
- `/hy-tmp/outputs/llamafactory/qwen3-4b-full-lora-sft-5090ti`

自动评测输出目录：

- `/hy-tmp/outputs/llm-lab-inference-eval/20260430_220052`

W&B run：

- full: `ufyqdlh9`

## 2. Smoke 结果

`4B smoke` 最终指标：

- `epoch = 20.0`
- `train_loss = 1.6048`
- `eval_loss = 1.4479`
- `train_runtime ≈ 6m07s`

这说明：

- `4B` 在当前机器上可以稳定启动
- 没有出现 OOM、模板错误、checkpoint 异常
- 单从训练收敛信号看，`4B smoke` 优于 `3B smoke`

## 3. Full 结果

`4B full` 最终指标：

- `train_loss = 1.8326`
- `eval_loss = 1.4539`
- `train_runtime ≈ 10m26s`
- `eval_samples = 48`

这说明：

- `4B full` 在当前机器上也能稳定跑满
- 相比 `3B full`，训练时间只略有增加
- 但收敛信号继续增强

## 4. 训练层面的初步解读

从训练指标看，当前趋势很清楚：

- `0.5B < 3B < 4B`

至少在 `eval_loss` 上，随着模型规模增大，结果持续改善。

但这里仍然需要保持纪律：

- loss 更低，不等于内容质量一定更好
- 是否值得继续 scale up，不能只看训练指标

因此 `4B` 的关键价值在于：

- 它已经值得进入下一步评测验证

## 5. 自动规则评测结果

基于 `48` 条 eval 集，当前 `4B` 的默认 prompt base/lora 已完成第一轮自动规则评测。

### 5.1 `qwen3_4b_default_prompt_base`

主要结果：

- `json_parse_success = 27 / 48 = 56.25%`
- `schema_valid = 0 / 48`
- `severity_enum_valid = 5 / 48 = 10.42%`
- `root_cause_nonempty = 9 / 48 = 18.75%`

这说明：

- `4B base` 已经比更小模型更容易输出“看起来像 JSON”的内容
- 但在默认 prompt 条件下，它仍然不会稳定遵循当前任务的固定 schema

### 5.2 `qwen3_4b_default_prompt_lora`

主要结果：

- `json_parse_success = 46 / 48 = 95.83%`
- `required_fields_present = 46 / 48 = 95.83%`
- `no_extra_top_level_fields = 46 / 48 = 95.83%`
- `severity_enum_valid = 46 / 48 = 95.83%`
- `schema_valid = 38 / 48 = 79.17%`
- `category_matches_reference = 29 / 46 = 63.04%`
- `severity_matches_reference = 29 / 46 = 63.04%`

这说明：

- `4B + LoRA` 已经在默认 prompt 下显著学会了目标结构
- 但 `schema_valid = 79.17%` 也说明当前还不是“几乎完美”状态
- 后续仍值得继续观察内容质量和失败模式

## 6. 生成长度与推理耗时的额外观察

这轮 `4B` 的一个很有价值的现象是：

- `base` 和 `lora` 的推理时间差异很明显
- 而且这种差异可以用生成长度解释

### 6.1 `qwen3_4b_default_prompt_base`

- `response_length_avg = 389.9792`
- `response_length_max = 512`
- `elapsed_seconds_avg = 20.7312`
- `finish_reason_counts`:
  - `stop = 36`
  - `length = 12`

### 6.2 `qwen3_4b_default_prompt_lora`

- `response_length_avg = 218.2083`
- `response_length_max = 512`
- `elapsed_seconds_avg = 11.6656`
- `finish_reason_counts`:
  - `stop = 47`
  - `length = 1`

### 6.3 这说明什么

两个关键信号非常清楚：

1. `4B lora` 的平均输出长度远短于 `4B base`
2. `4B lora` 的平均推理耗时也明显更低

这意味着：

- `LoRA` 不只是让输出更符合 schema
- 它还让模型更少拖尾、更少跑偏、更少撞 `max_new_tokens`
- 也因此推理更快

这是一条很有价值的观察，因为它说明：

**更对齐的模型不仅内容更规整，也可能在真实任务里具有更好的推理效率。**

## 7. 当前阶段结论

这轮 `4B` 实验至少已经说明：

1. `4B` 在当前机器上是稳定可训、可评测的
2. `4B` 的训练收敛信号继续优于 `3B`
3. `4B lora` 在默认 prompt 下已经具备较强结构化输出能力
4. `4B lora` 相比 `4B base` 生成更短、更快、更容易自然停止

## 8. 下一步

当前最合理的下一步不是立刻下“4B 就是最终主模型”的结论，而是继续做：

- `4B` 与 `3B` 的自动评测对比
- `3B lora` vs `4B lora` 的 pairwise judge

只有在内容质量层也验证 `4B` 的收益后，才能判断：

- 是否继续 scale up 值得
- 还是该把重心转向 alignment / DPO

## 9. 一句话总结

这轮 `Qwen3-4B-Instruct-2507 + LoRA` 实验说明：

**`4B` 不仅训练可行，而且在当前任务上表现出更强的收敛信号；同时 LoRA 还显著缩短了输出长度并降低了推理耗时，因此 `4B` 已经完全值得进入下一阶段的内容质量评测。**
