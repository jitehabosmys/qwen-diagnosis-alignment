# 2026-04-30 Strict Prompt 路线观察

这份文档记录的是在 `3B` 与 `4B` 模型上，使用 `strict_json_prompt` 后观察到的关键现象。

这不是最终路线结论，而是对一个很重要问题的阶段性观察：

**当模型规模变大之后，strict prompt 的作用方式是否发生了变化。**

## 1. 为什么值得单独记录

在 `0.5B` 阶段，strict prompt 给人的印象是：

- 对 base 有一定帮助
- 但对内容质量提升并不明显
- 甚至在部分对比里不如 default prompt 版自然

因此如果只看 `0.5B`，很容易得出一个草率结论：

- strict prompt 可能价值有限

但到了 `3B/4B` 阶段，情况开始明显变化。  
这说明：

- strict prompt 的作用不是固定不变的
- 它和模型规模存在交互效应

## 2. `3B strict` 的观察

### 2.1 `qwen25_3b_strict_json_prompt_base`

基于 `48` 条评测集：

- `json_parse_success = 48 / 48 = 100%`
- `schema_valid = 29 / 48 = 60.42%`
- `response_length_avg = 145.08`
- `elapsed_seconds_avg = 5.85s`

这个结果非常值得注意，因为它说明：

- 在 `3B` 上，strict prompt 本身已经足以让 base 模型稳定输出合法 JSON
- 而且有相当比例的样本直接满足目标 schema

也就是说，`3B base` 在 strict 协议下已经不再是“完全不会遵守规则”的状态。

### 2.2 `qwen25_3b_strict_json_prompt_lora`

- `json_parse_success = 47 / 48 = 97.92%`
- `schema_valid = 46 / 48 = 95.83%`
- `response_length_avg = 213.94`
- `elapsed_seconds_avg = 8.53s`

这说明：

- LoRA 仍然显著提升了 `3B` 的结构稳定性
- 但此时提升已经不只是“从 0 到有”，而是“从较强 base 再推进到高稳定区”

### 2.3 一个有趣现象

在 `3B strict` 上：

- `base` 反而比 `lora` 更短、更快

这意味着：

- `3B strict base` 虽然没那么完整
- 但它已经会比较克制地输出协议化答案
- `LoRA` 则让它回答得更完整、更充分，因此输出更长、耗时更高

## 3. `4B strict` 的观察

### 3.1 `qwen3_4b_strict_json_prompt_base`

- `json_parse_success = 48 / 48 = 100%`
- `schema_valid = 2 / 48 = 4.17%`
- `response_length_avg = 259.27`
- `elapsed_seconds_avg = 13.35s`

这说明：

- `4B base` 在 strict 协议下已经完全学会“输出合法 JSON”
- 但这并不等于它已经学会目标 schema

也就是说：

- strict prompt 能把 `4B base` 拉进“协议空间”
- 但并不能单独保证它稳定落在我们定义的任务协议内部

### 3.2 `qwen3_4b_strict_json_prompt_lora`

- `json_parse_success = 48 / 48 = 100%`
- `schema_valid = 48 / 48 = 100%`
- `response_length_avg = 213.94`
- `elapsed_seconds_avg = 10.77s`

这个结果非常强。

它说明：

- `4B + LoRA + strict prompt` 在当前评测集上已经实现了完整的结构协议对齐
- 而且不只是“合法 JSON”，而是“全量 schema_valid”

### 3.3 第二个有趣现象

在 `4B strict` 上：

- `lora` 不仅更规范
- 而且比 `base` 更短、更快

这说明：

- LoRA 不只是提升结构正确率
- 还减少了 base 的拖尾、啰嗦和跑偏

这和 `3B strict` 的现象不完全一样，说明模型规模进一步增大后，LoRA 对生成行为的影响模式也在变化。

### 3.4 为什么 `4B strict base` 会出现“100% JSON 但几乎 0% schema”

这是这轮结果里一个非常值得单独解释的现象。

表面上看，`4B strict base` 已经：

- `json_parse_success = 100%`

但同时又几乎：

- `schema_valid = 0%`

这并不意味着模型“很差”，而是意味着：

- 它已经被 strict prompt 拉进了协议化回答空间
- 但还没有精确学会我们定义的字段实现方式

从失败样本看，最典型的问题主要有两类：

#### A. `root_cause` 被写成数组，而不是字符串

很多样本会生成：

```json
"root_cause": [
  "...",
  "..."
]
```

而当前 schema 期待的是：

```json
"root_cause": "..."
```

这说明：

- 模型知道这里应该给出根因
- 但它更自然地把根因组织成多条列表
- 而不是压缩成一个字符串字段

换句话说，它理解了“要说根因”，但没有严格遵守“根因字段是字符串”这一协议细节。

#### B. 部分样本会省略 `summary` 或 `root_cause`

还有一些样本只输出：

- `category`
- `severity`
- `missing_info`
- `next_steps`

却没有完整给出：

- `summary`
- `root_cause`

这说明：

- 模型并不是不知道这是诊断任务
- 而是会自然退化成一种“给建议”的回答模式
- 没有完整执行六字段协议

#### 结论

因此，`4B strict base` 的主要问题不是：

- JSON 非法
- 完全不懂结构

而是：

**协议实现不精确。**

更具体地说，它经常是：

- 字段类型不对
- 少数字段缺失
- 结构“看起来很像对的”，但不够严格

这恰恰反过来支持了 strict 路线的价值：

- strict prompt 已经足以让 `4B base` 进入协议化回答轨道
- 而 LoRA 再进一步把这种“看起来像”推进到“严格一致”

## 4. 这两组现象合起来说明什么

当前最值得记住的不是单个数字，而是这条规律：

### 规律 1

**strict prompt 对更大模型的帮助明显强于它对 `0.5B` 的帮助。**

在 `3B/4B` 上，strict prompt 已经能显著约束 base 进入协议化回答状态。  
而在 `0.5B` 上，它更多只是弱帮助。

### 规律 2

**strict prompt 负责把模型拉进协议空间，LoRA 负责把模型推到协议内部的稳定区域。**

这句话在 `4B` 上体现得尤其明显：

- `base`: 100% 合法 JSON，但几乎不 schema valid
- `lora`: 100% 合法 JSON，且 100% schema valid

### 规律 3

**更对齐的模型不一定更慢。**

至少在 `4B strict` 上，LoRA 后的模型：

- 更规整
- 更短
- 更快

这说明对齐带来的收益，不只体现在内容质量，也体现在生成效率。

## 5. 为什么这支持“主线转向 strict”

如果只看 `0.5B`，很难有信心把 strict 当作正式主线。  
但现在 `3B/4B` 的结果已经给出了更强的支持：

- strict prompt 更接近真实使用协议
- 在更强模型上，它确实发挥出了更有价值的作用
- 它让 base 更像一个被约束的协议执行者
- LoRA 再在这个协议上完成稳定对齐

因此，当前更合理的路线判断是：

- `default_prompt` 保留为研究基线
- `strict_json_prompt` 逐步成为正式训练、推理和评测主线

## 6. 一句话总结

`3B/4B` 的结果说明：

**strict prompt 在更大模型上不再只是“略微帮助”，而是开始显著改变 base 模型的协议遵循行为；LoRA 则进一步把这种协议遵循推到稳定、高一致的状态。因此，strict 路线已经具备成为后续主线的实验依据。**
