# 2026-04-29 Qwen2.5-0.5B LoRA SFT 实验记录

这份记录对应一次在恒源云 `RTX 5060 Ti 16GB` 单卡环境上完成的 `SFT` 实验。  
目标不是追求最终最佳效果，而是验证以下事项是否成立：

- 当前 `430` 条中文诊断数据可以被 `LLaMA-Factory` 正确读取并训练
- `Qwen2.5-0.5B-Instruct + LoRA` 能在 `5060 Ti 16GB` 上稳定跑完
- 训练过程中不会出现数据格式错误、tokenizer 错误、显存错误或 loss 发散
- 第一轮真实训练能产出可用于后续推理验证的 adapter

本记录主要依据：

- 训练日志：[train-sft.log](/hy-tmp/llm-lab/logs/train-sft.log)
- 训练配置：[5060ti_qwen25_05b_full_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml)
- 数据切分报告：[prepare_5060ti_report.json](/hy-tmp/llm-lab/data/llamafactory/prepare_5060ti_report.json)

## 1. 实验背景

本项目的数据任务是“中文训练/部署问题诊断助手”。

输入包括：

- 用户问题
- 环境信息
- 命令
- 错误日志

输出为固定 JSON，字段包括：

- `category`
- `severity`
- `summary`
- `root_cause`
- `missing_info`
- `next_steps`

这次训练使用的是已经转换为 `alpaca` 格式的数据集，不再现场做数据构造，只验证训练链路和首轮收敛表现。

## 2. 训练目标与边界

这次实验的定位应当明确为：

- 第一轮真实 `SFT`
- 低风险、小模型、单卡验证实验
- 面向后续更大模型或更复杂流程的前置探针

因此，这次实验**不回答**以下问题：

- 这个任务在 `0.5B` 模型上最终效果是否足够好
- `LoRA` 是否优于 `QLoRA`
- `Qwen2.5-0.5B` 是否优于 `1.5B` 或 `4B`
- 结构化输出在真实外部分布上的泛化能力如何

这次实验主要回答的是：

- 数据管道是否正确
- 训练配置是否稳定
- 小模型是否至少能开始学习这类结构化输出

## 3. 实验环境

从训练日志可确认：

- 设备：单卡 `cuda:0`
- 分布式：`False`
- 计算精度：`torch.bfloat16`

日志证据：

```text
Process rank: 0, world size: 1, device: cuda:0, distributed training: False, compute dtype: torch.bfloat16
```

模型从本地缓存目录加载：

```text
/hy-tmp/models/Qwen/Qwen2___5-0___5B-Instruct/config.json
```

这说明在前面的模型下载阶段已经成功走通 `ModelScope -> 本地缓存 -> LLaMA-Factory 加载` 的链路。

## 4. 数据切分与样本规模

这次训练不是直接把 `430` 条全部喂给训练器，而是先做了确定性切分。

根据 [prepare_5060ti_report.json](/hy-tmp/llm-lab/data/llamafactory/prepare_5060ti_report.json)：

- 原始总数据：`430`
- 训练集：`382`
- 评估集：`48`
- smoke 子集：`32`

本次 full SFT 使用的是：

- `dataset: diagnosis_sft_train`
- `eval_dataset: diagnosis_sft_eval`

训练日志中 trainer summary 也与之吻合：

```text
Num examples = 382
```

评估日志中则明确为：

```text
Num examples = 48
```

这里要特别注意一件事：

- 日志中早期出现的 `Converting format of dataset ... 764 examples`
- 以及评估侧的 `96 examples`

不应直接解读为真实样本数。  
用于训练和评估的有效样本数，应以 trainer summary 和数据切分报告为准，即 `382 / 48`。

## 5. 训练配置

核心配置来自 [5060ti_qwen25_05b_full_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml)：

- 基座模型：`Qwen/Qwen2.5-0.5B-Instruct`
- 微调方式：`LoRA`
- `lora_rank: 8`
- `lora_alpha: 16`
- `lora_dropout: 0.05`
- `lora_target: all`
- `cutoff_len: 1536`
- `per_device_train_batch_size: 1`
- `gradient_accumulation_steps: 16`
- `learning_rate: 2e-4`
- `num_train_epochs: 3`
- `lr_scheduler_type: cosine`
- `warmup_steps: 4`
- `bf16: true`
- `eval_steps: 25`
- `save_steps: 25`

这是一个非常典型的“小模型 + LoRA + 单卡首轮验证”配置：

- 物理 batch 很小，避免 16GB 显存直接吃满
- 通过梯度累加把逻辑 batch 拉到 `16`
- 学习率偏积极，但配合小模型和 LoRA 是合理的
- `cutoff_len=1536` 高于最保守的 `1024`，但在这张卡上仍跑通了

## 6. 模型初始化与结构确认

日志显示加载到的是 `Qwen2Config`，关键字段包括：

- `hidden_size: 896`
- `num_hidden_layers: 24`
- `num_attention_heads: 14`
- `num_key_value_heads: 2`
- `vocab_size: 151936`

这与 `Qwen2.5-0.5B-Instruct` 的小参数量级相符。

同时日志中还能确认：

- `KV cache is disabled during training`
- `Gradient checkpointing enabled`
- `Using torch SDPA for faster training and inference`

这三点很重要：

1. `KV cache` 在训练中被关闭，这是正常行为，否则会浪费显存。
2. 梯度检查点已开启，说明框架主动做了显存换算力。
3. 这次训练的 attention 实现实际走的是 **PyTorch SDPA**，不是显式强制的 `flash_attention_2`。

这里也顺便澄清一个容易混淆的点：

- 模型配置里出现的 `layer_types: full_attention`

表示的是模型层结构类型，而不是“这次训练一定用了 eager/full attention 实现”。  
真正的运行时 attention 后端，应以：

```text
Using torch SDPA for faster training and inference.
```

这条日志为准。

## 7. 数据管道与监督目标构造

日志里打印了一条完整的训练样本，包括：

- `input_ids`
- `inputs`
- `label_ids`
- `labels`

从这条样本可以确认当前 SFT 数据管道的几个关键事实：

1. 输入采用 chat template 组织，包含 `system / user / assistant` 三段。
2. 监督目标只覆盖 assistant 输出。
3. 用户输入与 system prompt 对应位置的 `label_ids` 被设置为大量 `-100`。

这意味着损失函数只在 assistant 响应部分计算，而不会要求模型去预测用户 prompt。  
这是标准的 instruction tuning / chat SFT 训练目标构造方式。

这部分非常值得记录，因为它说明：

- 当前数据转换不是“把整段文本当纯续写训练”
- 而是进行了明确的监督掩码处理

这对结构化输出学习尤其关键。

## 8. LoRA 注入情况

日志中明确写到：

```text
Fine-tuning method: LoRA
Found linear modules: v_proj,o_proj,up_proj,gate_proj,k_proj,down_proj,q_proj
trainable params: 4,399,104 || all params: 498,431,872 || trainable%: 0.8826
```

可以据此得出几个确定结论：

1. 这次不是全参数微调，而是标准 `LoRA` 微调。
2. LoRA 注入覆盖了 attention 投影层和 MLP 线性层，属于较完整的目标模块覆盖。
3. 总参数接近 `4.98e8`，但真正训练的只有 `4.4e6`，约占 `0.88%`。

这也是这次训练能在 `5060 Ti 16GB` 上跑通的核心原因之一。

另一个细节是：

```text
Upcasting trainable params to float32.
```

这意味着虽然总体计算采用 `bf16`，但可训练的 LoRA 参数在关键更新路径上做了 `float32` 上采样，以提升数值稳定性。

## 9. 训练主循环

trainer summary 给出的关键数据是：

- `Num examples = 382`
- `Instantaneous batch size per device = 1`
- `Gradient Accumulation steps = 16`
- `Total optimization steps = 72`
- `Number of trainable parameters = 4,399,104`

这组数字可以这样理解：

- 单次前向的物理 batch 是 `1`
- 每累计 `16` 次前向/反向图后，才做一次参数更新
- 因此逻辑 batch 大致相当于 `16`

总优化步数 `72` 与：

- `382` 条训练样本
- `3` 个 epoch
- 梯度累加 `16`

是互相一致的。  
所以从训练调度角度看，这次配置确实按预期执行了，没有出现 epoch 数、步数或 batch 逻辑错位。

## 10. 中间评估与 checkpoint

本次配置设置了：

- `save_steps: 25`
- `eval_steps: 25`

日志中可以看到三个关键 checkpoint：

- `checkpoint-25`
- `checkpoint-50`
- `checkpoint-72`

并且在这些阶段都执行了评估或保存：

```text
Saving model checkpoint to /hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft/checkpoint-25
Saving model checkpoint to /hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft/checkpoint-50
Saving model checkpoint to /hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft/checkpoint-72
```

这说明：

- 训练中途保存正常
- 最终收尾保存也正常
- 输出目录结构符合预期，便于后续挑 checkpoint 做推理对比

## 11. 损失曲线与收敛观察

日志中能直接看到的关键评估点包括：

- `epoch 1.042` 时，`eval_loss = 2.06`
- `epoch 2.084` 时，`eval_loss = 1.95`
- 训练结束后，最终 `eval_loss = 1.935`

训练总指标为：

- `train_loss = 2.1676`
- `train_runtime = 0:06:52.00`
- `train_samples_per_second = 2.781`
- `train_steps_per_second = 0.175`

此外还生成了两张图：

- `/hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft/training_loss.png`
- `/hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft/training_eval_loss.png`

从这次日志能做出的稳妥判断是：

1. 训练过程没有出现 `nan`、loss 爆炸或明显数值不稳定。
2. eval loss 在这次 `48` 条验证集上呈下降趋势。
3. 在这 3 个 epoch 的短程训练里，没有观察到明显的过拟合迹象。

但这里也应当克制：

- `eval_loss` 下降并不等于最终“效果已经很好”
- 也不能只凭这组 loss 就宣称模型具备很强泛化能力

更准确的说法是：

**这轮训练已经证明模型开始学到任务格式与响应风格，且当前配置在小规模验证集上表现出正常收敛。**

## 12. 训练结果是否“跑对了”

从工程视角，这次实验可以判定为“跑对了”。

证据包括：

- 模型与 tokenizer 成功加载
- 数据集成功读取、分词、构造标签
- 单卡 `bf16` 训练正常启动
- LoRA 成功注入到目标线性层
- 训练完整跑满 `3` 个 epoch
- 中间 checkpoint 与最终输出全部成功保存
- `eval_loss` 呈下降趋势

因此，这次实验至少完成了以下里程碑：

1. `5060 Ti 16GB` 可以稳定承载 `Qwen2.5-0.5B + LoRA + cutoff_len 1536` 的首轮真实训练
2. 当前 `382/48` 的训练/评估切分是可训练的
3. 当前数据格式与 LLaMA-Factory 接口兼容
4. 后续可以进入推理验证阶段，而不必继续在“训练是否能跑通”上消耗时间

## 13. 这次实验的局限

虽然训练链路已经跑通，但这次结果仍有明显边界：

1. 模型很小，只有 `0.5B`
2. 训练总数据只有 `382` 条 train
3. 评估集只有 `48` 条，规模偏小
4. 当前只看了 loss，没有做结构化输出质量评测
5. 当前没有做 base model 与 LoRA adapter 的定量对比

所以这次实验的正确定位不是“模型效果验证完成”，而是：

**训练系统验证完成，初步收敛验证完成，任务学习迹象存在。**

## 14. 下一步建议

为了让这次实验真正具备学习价值，下一步不应该立刻无脑切更大模型，而应该先做推理验证。

建议按这个顺序继续：

1. 随机抽取 `10~20` 条训练外样本，分别用 base model 和 LoRA adapter 推理
2. 统计 JSON 可解析率
3. 检查 `category`、`severity` 是否落在合法枚举
4. 检查 `missing_info`、`next_steps` 是否非空且更具体
5. 人工对比 base vs adapter 的结构稳定性和诊断克制程度

如果这一步确认有收益，再考虑下一阶段：

- `Qwen2.5-1.5B-Instruct`
- `QLoRA` 对比
- 更正式的自动评测脚本
- 为后续 `DPO` 或 `vLLM` 推理验证做准备

## 15. 一句话结论

这次 `2026-04-29` 的 `Qwen2.5-0.5B-Instruct + LoRA` 单卡 SFT 实验，在 `RTX 5060 Ti 16GB` 上**稳定跑通且收敛信号正常**。  
它已经足以证明：当前数据、训练配置和工具链具备继续向“推理验证与下一轮模型实验”推进的基础。
