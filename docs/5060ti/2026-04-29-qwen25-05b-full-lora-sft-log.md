# 2026-04-29 Qwen2.5-0.5B Full LoRA SFT 实验记录

这份记录对应一次在恒源云 `RTX 5060 Ti 16GB` 单卡环境上完成的 `Qwen2.5-0.5B-Instruct + LoRA` 全量 `SFT` 实验。

这份文档是在原始训练记录基础上整理出的正式版本，主要目标是：

- 固定本次训练的实验上下文
- 记录训练配置、关键日志和收敛结果
- 为后续做 `base model vs LoRA adapter` 推理对比提供依据

原始记录可视为本文件的前身：

- [train-log.md](/hy-tmp/llm-lab/docs/5060ti/train-log.md)

## 1. 实验标识

- 实验日期：`2026-04-29`
- 训练类型：`Full SFT`
- 基座模型：`Qwen/Qwen2.5-0.5B-Instruct`
- 微调方式：`LoRA`
- 运行设备：`RTX 5060 Ti 16GB`

本次训练配置文件：

- [5060ti_qwen25_05b_full_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml)

本次训练日志：

- [train-sft.log](/hy-tmp/llm-lab/logs/train-sft.log)

本次训练输出目录：

- `/hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft`

## 2. W&B 记录

本次训练已经接入 W&B，本地 run 元数据目录为：

- `/hy-tmp/LLaMA-Factory/wandb/run-20260429_143509-bz3utjby`

当前可确认的 run id：

- `bz3utjby`

对应本地元数据文件：

- `/hy-tmp/LLaMA-Factory/wandb/run-20260429_143509-bz3utjby/files/wandb-metadata.json`
- `/hy-tmp/LLaMA-Factory/wandb/run-20260429_143509-bz3utjby/files/config.yaml`

如果后面你在 W&B 网页端确认了 project / entity / 页面 URL，建议把链接补到这里。  
目前从本地信息能稳定确认的是：

- run id：`bz3utjby`
- 程序入口：`llamafactory-cli`
- 启动参数：`/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml`

## 3. 实验目标

这次实验的目标不是追求最终最佳效果，而是回答以下问题：

- 当前 `430` 条中文诊断数据是否能被 `LLaMA-Factory` 正常读取并训练
- `Qwen2.5-0.5B-Instruct + LoRA` 是否能在 `5060 Ti 16GB` 上稳定跑满全量 SFT
- 第一轮真实训练是否能产出一个可用于后续推理验证的 adapter

## 4. 数据切分

根据 [prepare_5060ti_report.json](/hy-tmp/llm-lab/data/llamafactory/prepare_5060ti_report.json)：

- 原始总数据：`430`
- train：`382`
- eval：`48`
- smoke：`32`

本次 full SFT 使用：

- `dataset: diagnosis_sft_train`
- `eval_dataset: diagnosis_sft_eval`

训练器汇总日志也与之对应：

- `Num examples = 382`
- `Eval Num examples = 48`

## 5. 训练环境

从日志确认：

- 单卡 `cuda:0`
- 非分布式训练
- `torch.bfloat16`

模型从本地缓存加载：

- `/hy-tmp/models/Qwen/Qwen2___5-0___5B-Instruct`

运行时还确认了：

- `KV cache is disabled during training`
- `Gradient checkpointing enabled`
- `Using torch SDPA for faster training and inference`

这里需要明确：

- 模型配置里出现的 `layer_types: full_attention` 是结构定义
- 真正的运行时 attention 后端应以日志里的 `torch SDPA` 为准

## 6. 训练配置摘要

核心配置如下：

- `finetuning_type: lora`
- `lora_rank: 8`
- `lora_alpha: 16`
- `lora_dropout: 0.05`
- `lora_target: all`
- `cutoff_len: 1536`
- `per_device_train_batch_size: 1`
- `gradient_accumulation_steps: 16`
- `learning_rate: 2e-4`
- `num_train_epochs: 3`
- `warmup_steps: 4`
- `bf16: true`
- `eval_steps: 25`
- `save_steps: 25`

这属于一套偏保守、适合首轮验证的单卡 LoRA 配置。

## 7. LoRA 注入结果

训练日志确认：

```text
Fine-tuning method: LoRA
Found linear modules: v_proj,o_proj,up_proj,gate_proj,k_proj,down_proj,q_proj
trainable params: 4,399,104 || all params: 498,431,872 || trainable%: 0.8826
```

可以确定：

- 本次并非全参训练
- 真正参与训练的参数约 `440 万`
- 占总参数约 `0.88%`

这也是当前实验能在 `5060 Ti 16GB` 上稳定跑通的关键原因之一。

## 8. 训练主循环

trainer summary 给出的关键量是：

- `Num examples = 382`
- `Instantaneous batch size per device = 1`
- `Gradient Accumulation steps = 16`
- `Total optimization steps = 72`
- `Number of trainable parameters = 4,399,104`

理解方式：

- 物理 batch 是 `1`
- 每 `16` 步累积一次梯度，再做一次优化更新
- 总共进行了 `72` 个优化 step

## 9. Checkpoint 与输出

本次训练中生成了关键 checkpoint：

- `checkpoint-25`
- `checkpoint-50`
- `checkpoint-72`

最终输出目录下已经包含：

- `adapter_model.safetensors`
- `adapter_config.json`
- `README.md`
- `train_results.json`
- `eval_results.json`
- `trainer_log.jsonl`
- `training_loss.png`
- `training_eval_loss.png`

这说明：

- 训练中途保存正常
- 最终 adapter 产物完整
- 已经具备进入推理验证阶段的最低条件

## 10. 收敛观察

中间和最终评估结果如下：

- step 25 / epoch 1.042：`eval_loss = 2.0596`
- step 50 / epoch 2.084：`eval_loss = 1.9494`
- 训练结束最终评估：`eval_loss = 1.9353`

训练总指标：

- `train_loss = 2.1676`
- `train_runtime = 0:06:52.00`
- `train_steps_per_second = 0.175`

从这次日志能做出的稳妥判断是：

- 训练过程没有出现 `nan`
- 没有明显的数值发散
- 当前 `48` 条 eval 集上 loss 呈下降趋势

更克制的说法是：

**这轮训练已经证明模型开始学习任务格式和输出风格，但仅凭 loss 还不足以证明最终任务效果。**

## 11. 当前结论

从工程角度，这次 full SFT 可以判定为成功跑通。

它回答了三个关键问题：

1. 当前 `382/48` 的数据切分是可训练的
2. `Qwen2.5-0.5B + LoRA + cutoff_len 1536` 可以在 `5060 Ti 16GB` 上稳定跑完
3. 训练产物已经足够支撑下一阶段的推理验证

## 12. 下一步

当前最合理的下一步不是立刻换更大模型，而是做：

- `base model vs LoRA adapter` 推理对比

建议参考：

- [base-vs-lora-inference-plan.md](/hy-tmp/llm-lab/docs/5060ti/base-vs-lora-inference-plan.md)
- [2026-04-29-inference-eval-results.md](/hy-tmp/llm-lab/docs/5060ti/2026-04-29-inference-eval-results.md)
