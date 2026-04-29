# Base Model vs LoRA Adapter 推理对比方案

这份文档用于指导下一步最重要的一件事：

**比较 base model 和当前 LoRA adapter 在“中文训练/部署问题诊断助手”任务上的输出差异。**

当前可用产物：

- base model：`/hy-tmp/models/Qwen/Qwen2___5-0___5B-Instruct`
- LoRA adapter：`/hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft`

后续如果要验证“更严格 prompt 约束”本身带来的收益，建议与现有版本明确区分命名：

- 默认 prompt 版：`default_prompt`
- 严格 JSON prompt 版：`strict_json_prompt`

这样后续不容易把“prompt 变化带来的效果”和“LoRA 微调带来的效果”混在一起。

建议实验矩阵至少包含：

1. `default_prompt + base`
2. `default_prompt + lora`
3. `strict_json_prompt + base`
4. `strict_json_prompt + lora`

## 1. 为什么这一步优先级高

目前我们已经知道：

- 训练链路能跑通
- loss 正常下降
- adapter 成功保存

但这些都还不能回答一个更重要的问题：

- **训练之后的模型，是否真的比 base model 更会按我们的 JSON schema 输出？**

所以这一步比继续盲目调大模型更重要。

## 2. 对比目标

这轮对比不追求复杂自动评测，先回答 4 个问题：

1. 输出是否更稳定地保持合法 JSON
2. `category` / `severity` 是否更稳定落在合法枚举
3. `missing_info` / `next_steps` 是否更完整
4. 回答是否更贴近当前任务风格，而不是泛泛而谈

## 3. 最小对比集

建议先抽 `10~20` 条样本，优先使用：

- 不在训练集里的新样本
- 或你手工编写的 probe 样本

尽量覆盖：

- dependency
- training
- data
- inference
- deployment

不要一上来就全量自动测，先做一轮可人工读完的对比。

## 4. 对比方法

推荐固定同一批输入，对比两组模型：

1. base model
2. base model + LoRA adapter

需要保持一致的因素：

- 同一个 prompt
- 同一个 generation 参数
- 同一批样本

否则对比没有意义。

## 5. 推理方式建议

当前最适合的第一版不是写复杂脚本，而是先复用 `LLaMA-Factory` 的推理能力。

已知可参考的官方示例：

- `/hy-tmp/LLaMA-Factory/examples/inference/qwen3_lora_sft.yaml`

虽然它是 Qwen3 示例，但思路一样：

- base 推理：只指定 `model_name_or_path`
- LoRA 推理：同时指定 `model_name_or_path` 和 `adapter_name_or_path`

对于我们当前实验，大致对应：

- `model_name_or_path: /hy-tmp/models/Qwen/Qwen2___5-0___5B-Instruct`
- `adapter_name_or_path: /hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft`
- `template: qwen`

## 6. 建议记录格式

建议把每条样本的对比结果记成一个结构化表格或 JSON，字段至少包括：

- `sample_id`
- `prompt`
- `base_output`
- `lora_output`
- `base_json_parse_ok`
- `lora_json_parse_ok`
- `base_schema_ok`
- `lora_schema_ok`
- `manual_notes`

这样后面如果要继续自动评测，不需要推翻重来。

## 7. 第一轮人工判定标准

人工阅读时，优先看下面几点：

1. 输出是不是严格 JSON
2. 有没有漏字段
3. 枚举字段是否合法
4. 有没有凭空编造日志中不存在的根因
5. `next_steps` 是否具体、可执行
6. 是否更符合“工程化、克制”的风格

## 8. 当前推荐顺序

建议这样推进：

1. 先准备 `10~20` 条 probe 样本
2. 跑 base model 输出
3. 跑 LoRA adapter 输出
4. 做人工逐条对比
5. 统计最简单的结构化指标

如果这一轮已经能明显看出 LoRA 优于 base，再考虑补自动评测脚本。

## 9. 现阶段不要过度扩张

这一步的目标是建立“训练是否真的有收益”的证据链，不是马上做一整套评测框架。

当前更重要的是：

- 先看得见提升没有
- 先确认 LoRA 是否真的学到了任务结构

等这一轮有结论后，再决定是否继续：

- 上 `1.5B`
- 做自动 JSON schema 校验
- 做更正式的评测脚本
