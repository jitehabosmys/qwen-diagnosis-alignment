# 2026-05-01 Qwen3-4B Strict LoRA 在 4090 上的复现记录

这份文档记录的是当前项目迁移到 `RTX 4090 24GB` 后，第一轮 `Qwen3-4B-Instruct-2507 + strict_json_prompt + LoRA` 复现实验。

这轮实验的定位不是新的主实验，而是：

1. 验证 4090 上的训练环境已经可用
2. 复现一份可用的 `4B strict` baseline
3. 为后续更大模型 `QLoRA` 和正式 `DPO` 提供对照基线

相关文档：

- [gpushare-4090-first-setup-checklist.md](/hy-tmp/llm-lab/docs/4090/gpushare-4090-first-setup-checklist.md)
- [2026-04-30-qwen3-4b-sft-log.md](/hy-tmp/llm-lab/docs/5060ti/2026-04-30-qwen3-4b-sft-log.md)
- [2026-05-01-project-status-before-4090.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-project-status-before-4090.md)

## 1. 实验标识

- 日期：`2026-05-01`
- 机器：`RTX 4090 24GB`
- 模型：`Qwen/Qwen3-4B-Instruct-2507`
- 训练方式：`LoRA`
- 协议：`strict_json_prompt`
- 模板：`qwen3_nothink`

训练配置：

- [5090ti_qwen3_4b_smoke_lora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_smoke_lora_sft_strict_json_prompt.yaml)
- [5090ti_qwen3_4b_full_lora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_full_lora_sft_strict_json_prompt.yaml)

推理配置：

- [qwen3_4b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_hf_infer_strict_json_prompt.yaml)
- [qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml)

输出目录：

- `/hy-tmp/outputs/llamafactory/qwen3-4b-smoke-lora-sft-strict-json-prompt-5090ti`
- `/hy-tmp/outputs/llamafactory/qwen3-4b-full-lora-sft-strict-json-prompt-5090ti`
- `/hy-tmp/outputs/llm-lab-inference-eval/20260501_160221`

W&B run：

- smoke: `3vafkykw`
- full: `rpysdovt`

## 2. 环境意义

这轮实验有一个比训练指标更重要的前提意义：

- `LLaMA-Factory` 在 4090 上已经恢复 GPU 可用
- `4B strict` 训练、HF 推理评测链路都已跑通

因此，从今天开始，这台 4090 可以被视为当前项目的正式主实验机，而不再只是环境搭建中的候选机器。

## 3. Smoke 结果

`4B strict smoke` 最终指标：

- `epoch = 20.0`
- `train_loss = 1.4019`
- `eval_loss = 1.5081`
- `train_runtime = 0:05:18.89`

这说明：

- 训练能稳定启动
- 数据、模板、checkpoint 链路都没有结构性错误
- 当前环境已经足以承接后续正式训练

和之前记录相比：

- 旧记录 smoke `eval_loss = 1.4479`
- 本次 smoke `eval_loss = 1.5081`

这个差异不大，但 smoke 本来就只用于验证链路，不建议过度解读。

## 4. Full 结果

`4B strict full` 最终指标：

- `epoch = 3.0`
- `train_loss = 1.7212`
- `eval_loss = 1.4024`
- `train_runtime = 0:06:49.27`
- `eval_samples = 48`

和旧记录对比：

- 旧记录：`train_loss = 1.8326`，`eval_loss = 1.4539`，`train_runtime ≈ 10m26s`
- 本次复现：`train_loss = 1.7212`，`eval_loss = 1.4024`，`train_runtime ≈ 6m49s`

从训练信号看，本次复现并没有回退，反而略优。

更保守的表述是：

- 本次 `4B strict full` 至少成功复现了旧 baseline
- 并且在当前这次运行中，收敛指标还略强一些

## 5. HF 自动规则评测结果

基于 `48` 条 strict eval 集，本次评测结果如下。

### 5.1 `qwen3_4b_strict_json_prompt_base`

主要结果：

- `json_parse_success = 48 / 48 = 100%`
- `schema_valid = 1 / 48 = 2.08%`
- `required_fields_present = 31 / 48 = 64.58%`
- `summary_nonempty = 31 / 48 = 64.58%`
- `root_cause_nonempty = 3 / 48 = 6.25%`
- `category_matches_reference = 24 / 48 = 50.00%`
- `severity_matches_reference = 29 / 48 = 60.42%`

这说明：

- 在 strict 协议下，`4B base` 已经能稳定输出可解析 JSON
- 但它仍然不会稳定满足完整目标 schema

### 5.2 `qwen3_4b_strict_json_prompt_lora`

主要结果：

- `json_parse_success = 48 / 48 = 100%`
- `required_fields_present = 48 / 48 = 100%`
- `no_extra_top_level_fields = 48 / 48 = 100%`
- `category_enum_valid = 48 / 48 = 100%`
- `severity_enum_valid = 48 / 48 = 100%`
- `summary_nonempty = 48 / 48 = 100%`
- `root_cause_nonempty = 48 / 48 = 100%`
- `missing_info_is_nonempty_list = 48 / 48 = 100%`
- `next_steps_is_nonempty_list = 48 / 48 = 100%`
- `schema_valid = 48 / 48 = 100%`
- `category_matches_reference = 37 / 48 = 77.08%`
- `severity_matches_reference = 31 / 48 = 64.58%`

这说明：

- 当前 `4B strict lora` 已经完全复现了我们期望的结构化输出能力
- 从工程角度，它足以作为 4090 后续主实验的正式 baseline

## 6. 生成长度与推理耗时

### `qwen3_4b_strict_json_prompt_base`

- `response_length_avg = 256.4375`
- `elapsed_seconds_avg = 8.1605`
- `finish_reason_counts.stop = 48`

### `qwen3_4b_strict_json_prompt_lora`

- `response_length_avg = 195.1458`
- `elapsed_seconds_avg = 6.2157`
- `finish_reason_counts.stop = 48`

这延续了之前已经观察到的趋势：

1. `LoRA` 版本输出更短
2. `LoRA` 版本推理更快
3. 对齐后的模型更容易直接命中目标格式，而不是拖尾生成

## 7. 如何评价这次复现

如果把这次实验放回当前项目主线里，最稳的评价是：

### 7.1 复现是成功的

理由：

- 训练链路跑通
- 评测链路跑通
- 结果没有回退
- `strict lora` 在 `48/48` 样本上达到 `schema_valid = 100%`

### 7.2 它足以作为 4090 上的 `4B strict` baseline

这次结果已经足够支撑：

- 后续更大模型 `QLoRA` 与它做对照
- 后续 pairwise judge 与它做对照
- 后续是否进入正式 `DPO` 的判断

### 7.3 但它还不是新的最终主实验

原因是：

- `4B` 的价值在当前阶段主要是稳定 baseline
- 项目主问题已经切换成：
  - 更大模型是否还值得继续上
  - 什么时候从 scale up 转向正式 `DPO`

## 8. 对后续路线的意义

这轮复现把 4090 上的项目阶段进一步收束成：

1. `4B strict` baseline 已经稳定落地
2. `HF` 仍然是当前正式主评测链路
3. 下一步最值得投入的是更大模型 `QLoRA`
4. `DPO` 仍然应放在更大模型 `SFT -> 评测 -> judge` 之后

## 9. 一句话结论

这次 `Qwen3-4B strict LoRA` 在 4090 上的复现是一次成功且健康的 baseline 落地：

**它不仅证明 4090 环境已经能稳定承接当前项目主线，还产出了一份足以支撑后续更大模型 `QLoRA` 与正式 `DPO` 决策的 `4B strict` 对照基线。**
