# 2026-04-29 推理失败样本分析

这份文档记录的是 `2026-04-29` 四组推理评测中失败样本的第一轮人工观察。

评测结果来源：

- [summary.json](/hy-tmp/llm-lab/20260429_164620/summary.json)

相关原始结果文件：

- [default_prompt_base_results.jsonl](/hy-tmp/llm-lab/20260429_164620/default_prompt_base_results.jsonl)
- [default_prompt_lora_results.jsonl](/hy-tmp/llm-lab/20260429_164620/default_prompt_lora_results.jsonl)
- [strict_json_prompt_base_results.jsonl](/hy-tmp/llm-lab/20260429_164620/strict_json_prompt_base_results.jsonl)
- [strict_json_prompt_lora_results.jsonl](/hy-tmp/llm-lab/20260429_164620/strict_json_prompt_lora_results.jsonl)

这份分析不重新统计整体结果，而是关注：

- 各组失败样本的典型模式是什么
- 为什么失败
- 这些失败分别说明了什么

## 1. 总体观察

四组模型的失败模式差异很明显：

1. `default_prompt_base`
   - 主要失败在“根本没有按目标 schema 输出”
   - 常见表现是：
     - 输出 Markdown code fence
     - 使用错误字段名
     - 顶层结构不是目标 JSON

2. `strict_json_prompt_base`
   - 相比 `default_prompt_base`，更愿意往 JSON 靠
   - 但仍经常：
     - 输出 code fence
     - 用错字段类型
     - 把 `root_cause` 写成数组或对象
     - 把 `missing_info` / `next_steps` 留空

3. `default_prompt_lora`
   - 大多数样本已经非常接近正确答案
   - 失败主要是“局部 JSON 语法损坏”
   - 典型表现：
     - 漏逗号
     - 引号未闭合
     - 输出被异常拉长导致字符串截断

4. `strict_json_prompt_lora`
   - 失败模式与 `default_prompt_lora` 很接近
   - 已经不是“不会按 schema 回答”
   - 而是“少量生成过程中的局部 JSON 损坏”

这说明四组之间不是简单的“都不行/都行”，而是失败层级完全不同。

## 2. `default_prompt_base` 失败模式

### 2.1 主要失败类型

最典型的问题有两个：

1. 输出被包在 Markdown code fence 里，例如：

```text
```json
{
  ...
}
```
```

这会导致严格 `json.loads` 直接失败，错误通常是：

```text
Expecting value at line 1 column 1
```

2. 就算输出了 JSON，也不是目标 schema，而是模型自己发明的结构，例如：

- `diagnosis`
- `solution`
- `诊断结果`
- `问题`
- `解决方法`

### 2.2 代表性观察

从失败样本中能看到：

- 有些样本输出的是“看起来像答案的 JSON”，但字段完全不对
- 有些样本明显偏向通用问答模板，而不是我们定义的固定诊断 schema
- 有些样本出现重复、冗长解释，说明模型没有学会当前任务的结构约束

### 2.3 结论

`default_prompt_base` 的失败不是“小语法错”，而是：

**任务格式对齐失败。**

也就是说，它没有稳定学会：

- 只输出 JSON
- 使用指定字段名
- 按目标任务风格组织信息

## 3. `strict_json_prompt_base` 失败模式

### 3.1 主要失败类型

严格 prompt 对 base 确实有改善，但改善主要停留在表面：

1. 输出更像 JSON 了
2. 有时会尝试使用目标字段名
3. 但仍经常保留 code fence
4. 字段类型和字段内容仍经常不满足要求

### 3.2 代表性问题

典型现象包括：

- `root_cause` 被写成数组，而不是字符串
- `missing_info` / `next_steps` 为空数组
- `summary` 很短，但并不满足完整任务要求
- 顶层虽然接近 schema，但依然不是合法可用结果

### 3.3 结论

`strict_json_prompt_base` 说明了一件很关键的事：

**prompt engineering 可以让 base model 更愿意模仿结构，但不足以让它真正学会任务约束。**

也就是说，prompt 只能把它往正确方向推一点，但推不到“稳定可用”的程度。

## 4. `default_prompt_lora` 失败模式

### 4.1 主要失败类型

这一组最重要的观察是：

失败已经不再是“字段名完全错了”，而是“几乎正确，但 JSON 语法坏掉了”。

典型错误有：

1. 漏逗号
2. 字符串未闭合
3. 输出异常膨胀，最终截断

### 4.2 代表性样本

#### `eval_007`

现象：

- `root_cause` 字段后面少了逗号

结果：

- JSON 解析失败

这类错误说明：

- 模型知道应该输出哪些字段
- 也知道大致内容该怎么写
- 但局部生成时没有把 JSON 语法完整收尾

#### `eval_011`

现象：

- `next_steps` 中嵌入了带引号的代码片段
- 内层字符串没有正确转义

结果：

- JSON 结构被打断

这说明：

- 模型已经很接近任务格式
- 失败点更像是“长字符串 + 引号/代码片段”导致的转义问题

#### `eval_025`

现象：

- `missing_info` 字段内容异常膨胀
- 重复列出大量依赖项
- 最终字符串被截断，导致未闭合

结果：

- JSON 失败并不是 schema 不会，而是长文本失控

#### `eval_044`

现象：

- `root_cause` 字段进入重复输出
- 大量重复模板片段
- 最终字符串未闭合

结果：

- 同样属于生成失控导致的结构损坏

### 4.3 结论

`default_prompt_lora` 的失败模式说明：

**LoRA 已经学会目标 schema，本组剩余问题主要是局部生成稳定性问题，而不是任务格式理解问题。**

## 5. `strict_json_prompt_lora` 失败模式

### 5.1 主要失败类型

这一组只剩两个失败样本：

- `eval_003`
- `eval_035`

两者失败原因几乎一致：

- `root_cause` 字段后漏逗号

错误形式是：

```text
Expecting ',' delimiter at line 6 column 3
```

### 5.2 观察

这组失败非常值得注意，因为它表明：

- strict prompt 并没有从根本上消除“局部 JSON 语法损坏”
- 但它把失败收敛到了非常少量、非常局部的错误

换句话说，这已经不是“模型不会输出 schema”，而是：

**模型几乎会了，只是偶发地在字段边界上丢了一个逗号。**

### 5.3 结论

`strict_json_prompt_lora` 说明：

- strict prompt 对 LoRA 的主要作用，可能更多是收缩失败模式
- 而不是显著提高总体通过率

至少在这轮 `48` 条里，strict 版 LoRA 和默认版 LoRA 在通过率上差异不大，但 strict 版失败样本更集中、更同质。

## 6. 四组失败模式的层级差异

可以把四组失败理解成四个层级：

### 层级 1：`default_prompt_base`

问题是：

- 根本没按目标任务格式回答

### 层级 2：`strict_json_prompt_base`

问题是：

- 表面更像 JSON，但 schema 理解仍不稳定

### 层级 3：`default_prompt_lora`

问题是：

- schema 已基本学会
- 剩余问题是局部语法损坏或文本膨胀

### 层级 4：`strict_json_prompt_lora`

问题是：

- 失败样本很少
- 且高度集中在局部逗号缺失这种“小语法病”

这四个层级非常清楚地说明了：

**LoRA 改变的不只是“指标数值”，而是整个失败模式的性质。**

## 7. 当前最值得写进实验结论的观察

如果要把失败分析压缩成最有价值的结论，可以写成下面几条：

1. base model 的主要问题不是“偶发语法错”，而是根本未对齐到目标 schema。
2. strict prompt 能提升 base 的结构模仿意愿，但无法替代微调。
3. LoRA 之后，失败模式从“任务格式错误”转变为“局部 JSON 语法损坏”。
4. strict prompt + LoRA 没有显著提高整体通过率，但使失败模式更集中、更可解释。

## 8. 下一步建议

基于这轮失败样本，下一步最有价值的工作是：

1. 在自动评测里增加更细的失败分类
   - code fence
   - 字段缺失
   - 漏逗号
   - 字符串未闭合
   - 额外解释文本

2. 考虑对输出做轻量后处理实验
   - 例如剥离 code fence 后再 parse
   - 但这应当作为单独实验，不要和“严格原始输出”混在一起

3. 后续如果继续训练，可以专门针对：
   - 长字符串失控
   - 逗号缺失
   - 引号转义失败

做更有针对性的样本增强。
