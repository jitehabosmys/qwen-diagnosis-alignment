# 2026-04-29 推理评测结果说明

这份文档记录的是 `2026-04-29` 基于 `48` 条 eval 集进行的第一轮自动化推理评测结果。

这轮评测的目标不是直接判断“回答内容是否最好”，而是先回答一个更底层、更硬的问题：

**模型能否稳定输出合法 JSON，并满足我们要求的固定 schema。**

对应输出目录：

- [run_manifest.json](/hy-tmp/llm-lab/20260429_164620/run_manifest.json)
- [summary.json](/hy-tmp/llm-lab/20260429_164620/summary.json)

四组变体分别是：

- `default_prompt_base`
- `default_prompt_lora`
- `strict_json_prompt_base`
- `strict_json_prompt_lora`

## 1. 评测目的

当前任务不是普通开放式问答，而是一个有明确结构约束的诊断助手任务。  
因此第一轮评测先不讨论“内容是否最聪明”，而是先看：

- 是否输出合法 JSON
- 是否满足固定字段集合
- 是否满足字段类型和枚举约束

如果连这一步都过不了，后续人工评审或 `LLM-as-a-judge` 的意义都很有限。

## 2. 四组变体含义

### 2.1 `default_prompt_base`

- 使用原始 prompt 视图
- 不加载 LoRA adapter

作用：

- 作为最原始的基线

### 2.2 `default_prompt_lora`

- 使用原始 prompt 视图
- 加载默认版 LoRA adapter

作用：

- 测量默认 prompt 下，微调带来的真实结构化收益

### 2.3 `strict_json_prompt_base`

- 使用更强约束的 `strict_json_prompt` 视图
- 不加载 LoRA adapter

作用：

- 测量“只靠 prompt 加强约束”能带来多少格式收益

### 2.4 `strict_json_prompt_lora`

- 使用更强约束的 `strict_json_prompt` 视图
- 加载 strict 版 LoRA adapter

作用：

- 测量“更强 prompt 约束 + 微调”组合后的结果

## 3. 指标解释

### 3.1 `json_parse_success`

含义：

- 模型输出能否被 Python `json.loads` 直接解析为顶层 JSON 对象

这个指标最基础，也最重要。  
只要这一项失败，后面的 schema 检查全部失去意义。

### 3.2 `required_fields_present`

含义：

- 是否包含所有必需字段：
  - `category`
  - `severity`
  - `summary`
  - `root_cause`
  - `missing_info`
  - `next_steps`

它只检查“字段齐不齐”，不检查内容质量。

### 3.3 `no_extra_top_level_fields`

含义：

- 顶层字段是否**只有**上面那 6 个，没有多余字段

这个指标用来防止模型额外输出：

- `analysis`
- `confidence`
- `note`
- 其他我们没有设计进 schema 的字段

### 3.4 `category_enum_valid`

含义：

- `category` 是否落在允许集合中：
  - `dependency`
  - `training`
  - `data`
  - `inference`
  - `deployment`

### 3.5 `severity_enum_valid`

含义：

- `severity` 是否落在允许集合中：
  - `low`
  - `medium`
  - `high`

### 3.6 `summary_nonempty`

含义：

- `summary` 是否是非空字符串

### 3.7 `root_cause_nonempty`

含义：

- `root_cause` 是否是非空字符串

### 3.8 `missing_info_is_nonempty_list`

含义：

- `missing_info` 是否是非空数组

### 3.9 `next_steps_is_nonempty_list`

含义：

- `next_steps` 是否是非空数组

### 3.10 `schema_valid`

含义：

- 这是一个综合指标
- 只有当前面这些结构性条件全部通过时，才算 `schema_valid`

也就是说，它基本可以看作：

**“这一条输出在格式层面是否达到我们定义的目标 schema。”**

### 3.11 `category_matches_reference`

含义：

- 如果输出能解析成功，则比较模型输出的 `category` 是否与参考答案一致

这个指标比 schema 更偏向语义，但只检查一个离散字段。

### 3.12 `severity_matches_reference`

含义：

- 如果输出能解析成功，则比较模型输出的 `severity` 是否与参考答案一致

这个指标的解释要更谨慎，因为 `severity` 本身比 `category` 主观性更强。

## 4. 指标能说明什么，不能说明什么

这些指标能说明：

- 模型是否学会“按格式回答”
- LoRA 是否改善了 JSON/schema 稳定性
- 更严格 prompt 是否对 base 或 LoRA 有帮助

这些指标不能直接说明：

- 根因分析是否真正最准确
- 建议是否最有帮助
- 文本是否最符合工程直觉

所以它们适合作为第一层硬评测，而不是最终任务结论。

## 5. 本次 `48` 条结果

### 5.1 `default_prompt_base`

结果：

- `json_parse_success = 0 / 48`
- `schema_valid = 0 / 48`

解释：

- 原始 base model 在默认 prompt 下，几乎完全无法满足严格 JSON/schema 要求
- 这不是“偶尔格式差一点”，而是基线在这个任务上几乎没有结构化输出能力

### 5.2 `default_prompt_lora`

结果：

- `json_parse_success = 44 / 48 = 91.67%`
- `schema_valid = 44 / 48 = 91.67%`
- `category_matches_reference = 37 / 44 = 84.09%`
- `severity_matches_reference = 26 / 44 = 59.09%`

解释：

- LoRA 在默认 prompt 条件下，已经明显学会了严格 JSON 输出
- 从 `0%` 到 `91.67%` 的提升非常大
- 这说明当前 SFT 的核心收益不是抽象的 loss 降低，而是行为层面的格式学习

### 5.3 `strict_json_prompt_base`

结果：

- `json_parse_success = 5 / 48 = 10.42%`
- `schema_valid = 0 / 48`
- `category_matches_reference = 2 / 5 = 40%`
- `severity_matches_reference = 2 / 5 = 40%`

解释：

- 更强 prompt 约束对 base model 确实有帮助
- 但帮助非常有限
- base 从 `0 / 48` 提高到了 `5 / 48` 的 JSON 解析成功
- 然而它依然没有任何一条达到完整 `schema_valid`

结论：

**只靠 prompt engineering 不足以解决这个任务的结构化输出问题。**

### 5.4 `strict_json_prompt_lora`

结果：

- `json_parse_success = 44 / 48 = 91.67%`
- `schema_valid = 44 / 48 = 91.67%`
- `category_matches_reference = 24 / 44 = 54.55%`
- `severity_matches_reference = 22 / 44 = 50.00%`

说明：

- strict 版 LoRA 在格式指标上与默认版 LoRA 基本同一量级
- 至少在这 48 条上，没有出现“schema 通过率大幅继续上升”的现象

这意味着：

- 更严格的 prompt 约束没有让 LoRA 在**硬格式**上产生显著新增收益
- 当前 LoRA 的主要收益仍然来自训练本身，而不是 prompt 写得更严

## 6. 本次评测最重要的结论

从这轮 `48` 条自动评测可以比较稳地得出 3 个结论：

1. **LoRA 微调是结构化输出能力跃迁的主要来源。**
   `default_prompt_base` 为 `0/48`，`default_prompt_lora` 为 `44/48`，差异极大。

2. **更严格的 prompt 对 base 有帮助，但帮助有限。**
   `strict_json_prompt_base` 只把 JSON 解析率从 `0` 提到 `5/48`，仍无法得到任何完整 schema 合法样本。

3. **strict prompt 没有显著抬高当前 LoRA 的硬格式指标。**
   `strict_json_prompt_lora` 和 `default_prompt_lora` 在 JSON/schema 通过率上基本一致。

## 7. 如何解读 `category` 与 `severity` 对齐率

这里要特别注意：

- `category_matches_reference`
- `severity_matches_reference`

不应被过度解读。

原因：

1. 它们只检查单个字段，不代表整条回答质量。
2. `severity` 本身主观性更大。
3. strict prompt 版训练数据的目标仍是原始参考答案，并不是为“提高 category/severity 对齐率”单独设计的。

因此目前更合理的用法是：

- 先把它们当辅助信号
- 不把它们当成最终任务优劣的唯一标准

## 8. 当前局限

这轮评测已经很有价值，但仍有限制：

1. 主要评的是“结构是否对”，不是“内容是否最好”
2. 没有对 `summary` / `root_cause` / `next_steps` 做语义质量评分
3. 没有做人工逐条判定汇总
4. 还没有引入 `LLM-as-a-judge`

所以当前最稳妥的定位是：

**这轮评测已经证明 LoRA 显著提升了结构化输出稳定性，但还不能单靠自动规则指标宣称内容质量已经最优。**

## 9. 下一步建议

基于这轮结果，下一步最合理的是：

1. 人工检查失败样本
   - `default_prompt_lora` 的 4 个失败样本
   - `strict_json_prompt_lora` 的 4 个失败样本

2. 对比两套 LoRA 的失败模式
   - 是多输出解释文字
   - 是 JSON 缺字段
   - 还是内容结构被打断

3. 再引入第二层评测
   - 人工抽检
   - 必要时再加 `LLM-as-a-judge`

失败样本的第一轮人工观察记录见：

- [2026-04-29-inference-failure-analysis.md](/hy-tmp/llm-lab/docs/2026-04-29-inference-failure-analysis.md)

## 10. 一句话总结

这轮 `48` 条自动评测说明：

**在当前任务上，LoRA 微调对严格 JSON/schema 输出的提升是决定性的；更严格的 prompt 本身只能小幅改善 base model，但不足以替代微调。**
