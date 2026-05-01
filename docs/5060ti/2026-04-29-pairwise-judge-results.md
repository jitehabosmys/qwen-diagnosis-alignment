# 2026-04-29 Pairwise Judge 结果记录

这份文档记录的是 `2026-04-29` 在完成硬规则评测之后，使用 `LLM-as-a-judge` 对两组 LoRA 结果做 pairwise 比较的结果。

本轮比较对象：

- `default_prompt_lora`
- `strict_json_prompt_lora`

对应结果目录：

- [judge_summary.json](/hy-tmp/llm-lab/20260429_190458/judge_summary.json)
- [dpo_pairs.jsonl](/hy-tmp/llm-lab/20260429_190458/dpo_pairs.jsonl)
- [dpo_pairs_high_confidence.jsonl](/hy-tmp/llm-lab/20260429_190458/dpo_pairs_high_confidence.jsonl)

## 1. 评测目的

这轮 pairwise judge 的目标不是再检查：

- JSON 是否能解析
- schema 是否完整

这些硬约束已经在前面的自动规则评测中完成。

这一步要回答的是更高一层的问题：

- 在都基本满足结构要求的前提下，哪一版回答内容更好？
- 更严格的 prompt 约束，是否真的提升了诊断质量？
- 哪一版更适合作为后续 DPO 数据来源？

## 2. 评测方式

本轮使用的是 pairwise judge，而不是单点评分。

原因是：

- 更接近后续 DPO 的 `chosen / rejected` 结构
- 对 judge 来说，“A 和 B 哪个更好”通常比“给单条答案打绝对分”更稳定

judge 的五个维度是：

- `evidence_groundedness`
- `root_cause_quality`
- `actionability`
- `missing_info_quality`
- `overall_engineering_quality`

此外脚本还做了 schema gate：

- 如果一边 `schema_valid=true`、另一边 `schema_valid=false`，直接判通过 schema 的一方胜
- 只有两边都通过 schema gate，才真正进入 LLM judge

## 3. 总体结果

### 3.1 总 pair 数

- `total_pairs = 48`

### 3.2 judge 来源分布

- `openai_pairwise_judge = 42`
- `gate_schema_validity = 6`

解释：

- 绝大多数样本已经进入了真正的内容比较
- 少数样本在 schema gate 阶段直接分出胜负

### 3.3 总胜负

- `default_prompt_lora` 胜：`28`
- `strict_json_prompt_lora` 胜：`20`
- `tie = 0`

换算为不含 tie 的胜率：

- `default_prompt_lora = 58.33%`
- `strict_json_prompt_lora = 41.67%`

## 4. 维度级结果

### 4.1 `evidence_groundedness`

- `default_prompt_lora = 24`
- `strict_json_prompt_lora = 16`
- `tie = 8`

解释：

- 默认 prompt 版更常被 judge 认为“更贴近输入证据”
- strict 版并没有在证据贴合性上占优

### 4.2 `root_cause_quality`

- `default_prompt_lora = 24`
- `strict_json_prompt_lora = 13`
- `tie = 11`

解释：

- 默认 prompt 版在根因把握上明显占优
- strict 版有时会显得更僵、更模板化

### 4.3 `actionability`

- `default_prompt_lora = 23`
- `strict_json_prompt_lora = 15`
- `tie = 10`

解释：

- 默认 prompt 版给出的建议更容易被 judge 认为“可执行”

### 4.4 `missing_info_quality`

- `default_prompt_lora = 18`
- `strict_json_prompt_lora = 10`
- `tie = 20`

解释：

- 这个维度 tie 很多
- 说明两边在“缺失信息提问质量”上的差异没有前几个维度那么稳定
- 但默认 prompt 版仍略占上风

### 4.5 `overall_engineering_quality`

- `default_prompt_lora = 26`
- `strict_json_prompt_lora = 16`
- `tie = 6`

解释：

- 这个维度是当前最值得重视的总观感指标
- judge 更倾向认为默认 prompt 版整体更像一个合格的训练/部署问题诊断助手

## 5. 结果如何解读

### 5.1 可以确认的事实

本轮结果已经足以支持下面这个判断：

**在当前 pairwise judge 设置下，`default_prompt_lora` 整体略优于 `strict_json_prompt_lora`。**

而且这个结论不是只靠单个总胜负得出的，而是：

- 总胜负上 default 更高
- 大多数维度上 default 也更高
- 尤其在 `root_cause_quality`、`actionability`、`overall_engineering_quality` 上表现更明显

### 5.2 这不意味着 strict prompt 完全无效

这轮结果不能解释成：

- strict prompt 没价值
- strict prompt 一定是错误方向

更合理的解释是：

1. strict prompt 对 base model 有一定结构帮助
2. 但在 LoRA 已经基本学会 schema 的前提下，strict prompt 没有继续提升格式收益
3. 反而可能轻微牺牲了表达的自然性、内容的灵活性或诊断风格

也就是说：

**strict prompt 在当前阶段没有带来额外的内容质量红利。**

## 6. 与前面自动评测的关系

这轮 pairwise judge 需要和前面的自动规则评测一起看。

前面自动评测已经说明：

- `default_prompt_lora` 和 `strict_json_prompt_lora` 在 JSON/schema 通过率上很接近

而这轮 pairwise judge 进一步说明：

- 在结构指标差不多的情况下
- 默认 prompt 版在内容质量上略优

把两者合在一起，当前最稳的结论是：

**strict prompt 没有显著提高 LoRA 的结构化输出表现，且在内容质量上还略逊于默认 prompt 版。**

## 7. DPO 产物价值

这轮 pairwise judge 的另一个重要产出是 DPO 候选对。

### 7.1 全量可用 pair

- `usable_for_dpo_count = 48`

这意味着：

- 每个样本最终都能得到一个非 tie 的胜负结论

### 7.2 高置信 pair

- `high_confidence_for_dpo_count = 18`

其中：

- `default_prompt_lora` 被选为 `chosen`：`11`
- `strict_json_prompt_lora` 被选为 `chosen`：`7`

来源分布：

- `openai_pairwise_judge = 12`
- `gate_schema_validity = 6`

### 7.3 如何使用

这说明当前最合理的 DPO 数据策略是：

1. 把 `dpo_pairs_high_confidence.jsonl` 当成第一优先级候选池
2. 不要立刻把所有 pair 都当作同等质量数据
3. 优先使用：
   - judge 明确高置信
   - 或 schema gate 直接分出胜负

这样更有利于后续得到干净的偏好信号。

## 8. 当前阶段的实验结论

如果把这轮 pairwise judge 的结论压缩成最重要的几条，可以写成：

1. 在内容质量的 pairwise judge 中，`default_prompt_lora` 以 `28:20` 略优于 `strict_json_prompt_lora`。
2. 默认 prompt 版在 `evidence_groundedness`、`root_cause_quality`、`actionability`、`overall_engineering_quality` 上整体更占优。
3. strict prompt 对 LoRA 没有带来明显的内容质量提升。
4. 因此当前主实验分支更适合继续沿用 `default_prompt_lora`，而不是切换到 strict prompt 版。

## 9. 下一步建议

基于这轮结果，下一步最合理的是：

1. 将 `default_prompt_lora` 继续作为当前主实验分支
2. 把 `dpo_pairs_high_confidence.jsonl` 作为后续 DPO 数据候选池
3. 如需继续做 judge，可优先比较：
   - `default_prompt_base` vs `default_prompt_lora`
   - 其他模型规模或训练轮次的 LoRA 版本

## 10. 一句话结论

这轮 pairwise judge 表明：

**在结构化输出已经基本稳定的前提下，默认 prompt 版 LoRA 在内容质量上略优于 strict prompt 版 LoRA，因此当前项目主线应继续保留 `default_prompt_lora`。**
