# 2026-05-01 Qwen3-8B QLoRA Strict SFT 实验记录

这份文档记录的是当前项目在 `RTX 4090 24GB` 单卡环境上完成的一轮 `Qwen3-8B + QLoRA + strict_json_prompt` 训练。

这轮实验的目标不是立刻宣布 `8B` 接管全部主线，而是先回答三个更现实的问题：

1. `8B` 级别模型能否在当前 `4090 24GB` 环境上稳定训练
2. 相比已经稳定落地的 `4B strict` baseline，`8B` 是否继续给出更强的训练信号
3. 当前项目是否已经可以正式把“更大模型 `QLoRA`”作为下一阶段主实验方向

相关文档：

- [2026-05-01-qwen3-4b-strict-repro-on-4090.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-4b-strict-repro-on-4090.md)
- [gpushare-4090-first-setup-checklist.md](/hy-tmp/llm-lab/docs/4090/gpushare-4090-first-setup-checklist.md)
- [2026-05-01-project-status-before-4090.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-project-status-before-4090.md)
- [2026-05-01-qwen3-8b-qlora-throughput-tuning.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-8b-qlora-throughput-tuning.md)

## 1. 实验标识

- 日期：`2026-05-01`
- 机器：`RTX 4090 24GB`
- 模型：`Qwen/Qwen3-8B`
- 微调方式：`QLoRA`
- 协议：`strict_json_prompt`
- 模板：`qwen3_nothink`

训练配置：

- [4090_qwen3_8b_smoke_qlora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_8b_smoke_qlora_sft_strict_json_prompt.yaml)
- [4090_qwen3_8b_full_qlora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_8b_full_qlora_sft_strict_json_prompt.yaml)

推理配置：

- [qwen3_8b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_8b_base_hf_infer_strict_json_prompt.yaml)
- [qwen3_8b_full_qlora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_8b_full_qlora_hf_infer_strict_json_prompt.yaml)

输出目录：

- `/hy-tmp/outputs/llamafactory/qwen3-8b-smoke-qlora-sft-strict-json-prompt-4090`
- `/hy-tmp/outputs/llamafactory/qwen3-8b-full-qlora-sft-strict-json-prompt-4090`

W&B run：

- smoke: `omsj5z6l`
- full: `dh792mou`

## 2. 配置摘要

这轮实验和之前的 `4B strict` baseline 相比，有两个关键变化：

1. 模型规模从 `4B` 提升到 `8B`
2. 微调方式从普通 `LoRA` 改成 `QLoRA`

当前量化相关配置：

- `quantization_bit: 4`
- `quantization_type: nf4`
- `double_quantization: true`

训练侧保持了尽量少的变量变化：

- `finetuning_type: lora`
- `lora_rank: 8`
- `lora_alpha: 16`
- `lora_dropout: 0.05`
- `lora_target: all`
- `bf16: true`

这轮设计原则很明确：

- 先回答 `8B` 是否稳定可训
- 不在第一轮就同时引入过多新的训练技巧

## 3. Smoke 结果

`8B QLoRA smoke` 最终指标：

- `epoch = 20.0`
- `train_loss = 1.4574`
- `eval_loss = 1.4259`
- `train_runtime = 0:05:14.72`

从工程角度，这已经说明：

- `8B QLoRA` 在当前 `4090 24GB` 环境上可以稳定启动
- 数据、模板、量化、LoRA 注入、checkpoint、评估链路都正常
- 当前环境已经不只是“勉强能训 8B”，而是“能比较从容地训 8B”

## 4. Full 结果

`8B QLoRA full` 最终指标：

- `epoch = 3.0`
- `train_loss = 1.7031`
- `eval_loss = 1.3887`
- `train_runtime = 0:09:15.69`
- `eval_samples = 48`

这说明：

- `8B QLoRA` 不只是 smoke 通过，而是完整 `SFT` 也稳定跑满
- 训练耗时相对 `4B` 有增加，但仍处在当前单卡主实验可接受范围内

## 5. 与 4B strict baseline 的对照

当前最有价值的对照对象不是更早的 `0.5B / 3B`，而是刚在 4090 上稳定复现的 `4B strict` baseline。

### 5.1 Smoke 对照

`4B strict smoke`：

- `train_loss = 1.4019`
- `eval_loss = 1.5081`
- `train_runtime = 0:05:18.89`

`8B QLoRA smoke`：

- `train_loss = 1.4574`
- `eval_loss = 1.4259`
- `train_runtime = 0:05:14.72`

这里最值得重视的是：

- `8B smoke eval_loss = 1.4259`
- `4B smoke eval_loss = 1.5081`

说明在 smoke 阶段，`8B` 已经给出了更强的收敛信号。

### 5.2 Full 对照

`4B strict full`：

- `train_loss = 1.7212`
- `eval_loss = 1.4024`
- `train_runtime = 0:06:49.27`

`8B QLoRA full`：

- `train_loss = 1.7031`
- `eval_loss = 1.3887`
- `train_runtime = 0:09:15.69`

这里可以做出一个比较克制但清楚的判断：

- `8B full` 的训练信号优于 `4B full`
- 提升幅度不是断崖式的，但方向明确
- 训练耗时有增加，但没有失控

## 6. 显存与训练可行性观察

当前观察到的显存占用大致在：

- smoke 约 `11.3GB / 24.6GB`
- full 约 `13.8GB / 24.6GB`

这说明：

- 当前这版 `8B QLoRA` 在 4090 上并不是贴边运行
- `per_device_train_batch_size = 1` 更像是稳妥起点，而不是被显存逼到的极限
- 后续如需优化吞吐，存在尝试 `batch_size = 2`、同时减半 `gradient_accumulation_steps` 的空间

## 7. 如何评价这轮 8B 实验

### 7.1 训练层面是成功的

理由：

- smoke 跑通
- full 跑通
- 没有看到量化导致的明显异常
- 当前训练收敛信号优于 `4B strict` baseline

### 7.2 这说明直接上 8B 是合理的

项目在迁移到 4090 之后，本来就需要回答：

- 继续 scale up 是否还值得

这轮结果已经给出第一层正面答案：

- 至少从训练信号看，`4B -> 8B` 仍然有收益

### 7.3 但这还不是最终能力结论

目前这轮结果主要回答的是：

- 可训性
- 收敛趋势
- 训练成本是否可接受

它还没有正式回答：

- `8B strict` 的结构化输出是否完全不退化
- `8B` 的内容质量是否在 judge 视角下明确优于 `4B`

这两件事仍然要靠：

1. HF 自动规则评测
2. `4B strict lora` vs `8B strict qlora` 的 pairwise judge

## 8. 对后续路线的影响

这轮结果对项目路线的影响很直接：

1. `4B strict` 已经完成 baseline 使命
2. `8B QLoRA` 已经值得进入正式评测
3. 当前主问题变成：
   - `8B` 相比 `4B` 的内容质量是否也明确更强
   - 是否需要继续上更大模型
   - 还是该开始把重点转向 `DPO`

因此下一步最合理的顺序是：

1. 跑 `8B strict` 的 HF 自动评测
2. 跑 `8B strict qlora` vs `4B strict lora` 的 pairwise judge
3. 再决定：
   - `8B` 是否接管主线
   - 是否继续 scale up
   - 何时正式进入 `DPO`

## 9. HF 推理评测：第一次结果与 thinking 泄漏

完成训练后，`8B strict` 首轮 HF 推理评测最初使用的是：

- `template: qwen3_nothink`

当时得到的结果是：

### `qwen3_8b_strict_json_prompt_base`

- `json_parse_success = 0 / 48`
- `schema_valid = 0 / 48`
- `response_length_avg = 475.2708`
- `response_length_max = 512`
- `finish_reason_counts`:
  - `stop = 22`
  - `length = 26`

### `qwen3_8b_strict_json_prompt_lora`

- `json_parse_success = 46 / 48 = 95.83%`
- `schema_valid = 46 / 48 = 95.83%`

失败样本：

- `eval_013`
- `eval_021`

最关键的观察是：

- `8B base` 并不是“不会回答”
- 而是会在最终 JSON 前面先输出 `<think>...</think>` 推理内容
- 严格 JSON 评测器从首字符开始解析，因此这会直接把 `48/48` 全部判成 parse fail

换句话说，当时的 `8B base` 失败，不是内容能力本身崩坏，而是：

**在当前这条 `LLaMA-Factory + HF` 推理链里，没有真正硬关闭 thinking，导致 strict JSON 评测被 reasoning 泄漏系统性污染。**

## 10. 正确关闭 thinking 后的 HF 推理评测

后续在本地最小验证后，推理配置改成：

- `template: qwen3`
- `enable_thinking: false`

这一步非常关键，因为在当前推理链里：

- `qwen3_nothink` 并不等价于真正的 generation-time hard switch
- 真正有效的 no-think 方式是：
  - `template = qwen3`
  - `enable_thinking = false`

在这个条件下重新评测后，得到的结果如下。

### `qwen3_8b_strict_json_prompt_base`

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
- `category_matches_reference = 20 / 48 = 41.67%`
- `severity_matches_reference = 28 / 48 = 58.33%`

生成统计：

- `response_length_avg = 157.5`
- `elapsed_seconds_avg = 5.1503`
- `finish_reason_counts.stop = 48`

这说明：

- `8B base` 在真正 no-think 条件下，结构遵循能力其实非常强
- 之前的“base 很烂”结论并不成立
- 真正成立的结论应该是：
  - 如果没有严格关掉 thinking，`8B base` 会因为 `<think>` 泄漏而看起来极差
  - 一旦真正关掉 thinking，它会变成一个非常听话的 JSON 输出器

### `qwen3_8b_strict_json_prompt_lora`

- `json_parse_success = 47 / 48 = 97.92%`
- `schema_valid = 47 / 48 = 97.92%`
- `category_matches_reference = 33 / 47 = 70.21%`
- `severity_matches_reference = 30 / 47 = 63.83%`

失败样本只剩：

- `eval_002`

这说明：

- 正确关闭 thinking 后，`8B qlora` 的结构稳定性略有改善
- 但它仍然没有完全恢复到 `4B strict lora` 的 `48/48 schema_valid`

## 11. `8B` 与 `4B` 的 pairwise judge

第一次比较（thinking 未真正关掉）时，`8B` 相比 `4B` 的结果是：

- `4B wins = 19`
- `8B wins = 23`
- `tie = 6`
- 去掉 tie 后：`8B win rate = 54.76%`
- `overall_score delta = +0.413`

在正确 no-think 条件下重新比较后，结果是：

- `4B wins = 18`
- `8B wins = 23`
- `tie = 7`
- 去掉 tie 后：`8B win rate = 56.10%`
- `overall_score delta = +0.2128`

维度分数平均提升：

- `evidence_groundedness: +0.2340`
- `root_cause_quality: +0.1702`
- `actionability: +0.1702`
- `missing_info_quality: +0.2128`
- `overall_engineering_quality: +0.1915`

这说明两件事：

1. `8B` 相比 `4B` 的内容质量优势在重新评测后仍然存在
2. 但在更干净的 no-think 比较条件下，这种优势更像是：
   - 中等偏小的稳健领先
   - 而不是明显碾压

## 12. 这轮推理结果真正说明了什么

### 12.1 关于 `8B base`

当前最重要的结论不是“`8B base` 很烂”，而是：

**如果没有严格关闭 thinking，`8B base` 会系统性泄漏 `<think>`，从而把 strict JSON 评测完全污染。**

这意味着：

- 对 reasoning-capable 基座做 strict 结构任务评测时
- thinking 开关本身就是一个关键实验变量
- 不能在未控住该变量的条件下直接下能力结论

### 12.2 关于 `8B qlora`

当前 `8B qlora` 已经表现出：

- 比 `4B` 更高的内容质量
- 但在 strict JSON 稳定性上仍略逊于 `4B strict lora`

因此当前最合适的评价不是：

- `8B` 全面取代 `4B`

而是：

- `8B` 值得保留为更强主实验候选
- 但当前还需要进一步补它的 strict 输出稳态

### 12.3 关于后续路线

这组结果也在提醒一个更大的实验设计问题：

- `3B -> 4B` 的提升里，可能混入了 `Qwen2.5 -> Qwen3` 的代际收益
- `4B -> 8B` 更接近同代 dense 模型内部的 scale up
- 因此当前看到的 `8B` 优势没有特别夸张，也并不奇怪

## 13. 一句话结论

这轮 `8B` 推理评测最关键的启示是：

**对 Qwen3 这类 reasoning-capable 模型做 strict JSON 评测时，必须真正硬关闭 thinking；否则 `8B base` 会因为 `<think>` 泄漏而被系统性误判。**

在真正 no-think 条件下，`8B base` 的结构遵循能力非常强，`8B qlora` 相比 `4B strict lora` 也仍然保持内容质量上的稳健领先，但这种领先已经收敛为中等偏小的边际收益。

## 14. 阶段结论

这轮 `Qwen3-8B + QLoRA + strict_json_prompt` 实验说明：

**在 4090 单卡上，`8B` 不仅稳定可训，而且已经在训练收敛信号上明确优于当前 `4B strict` baseline；因此更大模型 `QLoRA` 已经从“值得尝试”进入了“值得正式评测与主线比较”的阶段。**
