# 2026-05-01 Qwen3-8B QLoRA 吞吐优化实验

这份文档记录的是在 `Qwen3-8B + QLoRA + strict_json_prompt` 主线上，对训练吞吐做的一次小范围工程优化实验。

实验目的不是提升模型能力，而是回答一个更直接的问题：

- 在不改变有效 batch 大小的前提下，是否可以通过增大物理 batch、减少梯度累积，显著缩短训练时间，同时保持训练效果基本不变

相关文档：

- [2026-05-01-qwen3-8b-qlora-sft-log.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-8b-qlora-sft-log.md)
- [2026-05-01-qwen3-4b-strict-repro-on-4090.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-4b-strict-repro-on-4090.md)

## 1. 对照对象

基线配置：

- [4090_qwen3_8b_full_qlora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_8b_full_qlora_sft_strict_json_prompt.yaml)

吞吐优化配置：

- [4090_qwen3_8b_full_qlora_sft_strict_json_prompt_bs2.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_8b_full_qlora_sft_strict_json_prompt_bs2.yaml)

两版配置保持不变的部分：

- 模型：`Qwen/Qwen3-8B`
- 微调方式：`QLoRA`
- 协议：`strict_json_prompt`
- `cutoff_len = 1536`
- `learning_rate = 2e-4`
- `num_train_epochs = 3`
- `lora_rank = 8`
- `lora_alpha = 16`
- `lora_target = all`

唯一刻意修改的两项是：

### 基线版

- `per_device_train_batch_size = 1`
- `gradient_accumulation_steps = 32`

### 吞吐优化版

- `per_device_train_batch_size = 2`
- `gradient_accumulation_steps = 16`

因此两版的有效 batch 大小基本一致，差异主要体现在：

- 每次优化更新前需要执行的 micro-step 数量不同
- 训练吞吐和显卡利用率可能不同

## 2. 运行时显存观察

在 `bs=2 / grad_acc=16` 这版训练中，观察到的典型 GPU 状态大致为：

- 显存：`20867MiB / 24564MiB`
- GPU 利用率：`90%`
- 功耗：`379W / 450W`

这说明：

- 当前配置没有贴着显存上限跑
- GPU 利用率相较 `bs=1` 更高
- 这版已经更像“把 4090 吃满”的训练配置

## 3. 结果对比

### 基线版 `bs=1 / grad_acc=32`

- `train_runtime = 0:09:15.69`
- `train_samples_per_second = 2.062`
- `train_steps_per_second = 0.065`
- `train_loss = 1.7031`
- `eval_loss = 1.3887`

### 吞吐优化版 `bs=2 / grad_acc=16`

- `train_runtime = 0:06:06.39`
- `train_samples_per_second = 3.128`
- `train_steps_per_second = 0.098`
- `train_loss = 1.7034`
- `eval_loss = 1.3890`

## 4. 如何解读

最重要的观察有三条：

### 4.1 时间显著缩短

训练时间从：

- `9m15s`

降到：

- `6m06s`

也就是大约降到原来的 `66%` 左右。

这说明当前 `8B QLoRA` 训练的瓶颈之一，确实来自过小的物理 batch 和较多的梯度累积轮次。

### 4.2 吞吐明显提升

- `train_samples_per_second: 2.062 -> 3.128`
- `train_steps_per_second: 0.065 -> 0.098`

提升幅度大致在 `50%` 左右。

这说明：

- 把 `batch_size` 从 `1` 提到 `2`
- 同时把 `grad_acc` 从 `32` 降到 `16`

在当前单卡环境下明显提高了设备利用效率。

### 4.3 训练效果几乎不变

- `train_loss: 1.7031 -> 1.7034`
- `eval_loss: 1.3887 -> 1.3890`

这个差异足够小，可以视为同一水平的正常波动，而不是实质性退化。

## 5. 结论

这轮实验给出的工程结论非常清楚：

1. `bs=2 / grad_acc=16` 在 `4090 + 8B QLoRA` 上是稳定可行的
2. 它没有带来明显的训练效果退化
3. 它显著缩短了训练时间
4. 因此它比 `bs=1 / grad_acc=32` 更适合作为当前 `8B full` 的默认训练配置候选

## 6. 对后续工作的意义

这轮优化的价值不在于“模型更强”，而在于：

- 让后续围绕 `8B` 的实验迭代成本更低
- 让后续若继续做：
  - prompt 调整
  - 数据修补
  - `DPO` 前的再训练

都可以优先复用这版更高吞吐的配置

## 7. 一句话结论

在当前 `4090 + Qwen3-8B + QLoRA` 主线上，把：

- `batch_size: 1 -> 2`
- `gradient_accumulation_steps: 32 -> 16`

是一笔很划算的工程优化：

**训练时间明显缩短，吞吐显著提升，而训练结果几乎不变，因此这版配置可以视为当前 `8B full` 的更优默认工程配置。**
