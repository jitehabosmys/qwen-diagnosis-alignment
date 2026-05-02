# 2026-05-02 最终 DPO 数据集说明

这份文档用于固定当前项目第一版正式 `DPO` 数据集的来源、构造方式、筛选规则与数量统计。

当前阶段目标不是追求“越多越好”，而是确保：

1. pair 的差异主要来自任务相关偏好，而不是空答或格式故障
2. prompt 分布尽量贴近当前任务主线
3. 最终产物能直接喂给 `LLaMA-Factory`

相关脚本：

- 候选生成与 judge：[generate_dpo_candidates.py](/hy-tmp/llm-lab/scripts/generate_dpo_candidates.py)
- 多批次合并：[merge_dpo_generation_outputs.py](/hy-tmp/llm-lab/scripts/merge_dpo_generation_outputs.py)
- 最终 DPO 数据导出：[build_dpo_dataset_from_judged_pairs.py](/hy-tmp/llm-lab/scripts/build_dpo_dataset_from_judged_pairs.py)

相关产物：

- 候选与 judge 合并目录：`/hy-tmp/llm-lab/data/dpo/merged_ds_dsp_max2`
- 最终 DPO 数据目录：`/hy-tmp/llm-lab/data/dpo/final_ds_dsp`

## 1. prompt 从哪里来

当前 DPO prompt 主来源不是 `eval`，而是现有 `train` 分布样本。

原因很简单：

- `eval` 集需要继续保持为后续评测基准
- `DPO` 本质上仍然是训练数据
- 当前任务分布已经在现有 `train` 样本中体现得足够明确

因此，这一版 DPO 候选生成直接使用：

- `data/llamafactory/diagnosis_sft_strict_json_prompt_train_alpaca.json`

也就是当前 strict 主线的 train 样本视图。

## 2. pair 是怎么得到的

每条 train prompt 会经历三步：

### 第一步：两个候选模型分别生成答案

当前使用的候选模型组合是：

- `deepseek-v4-pro`
- `deepseek-v4-flash`

生成阶段使用：

- Anthropic-compatible API
- 两个模型分别对同一条 prompt 生成回答

为了提高效率，脚本支持：

- 同时处理多个 sample
- 每个 sample 内部 A/B 两个模型并发生成

当前常用设置是：

- `sample_concurrency = 2`

也就是：

- 同时 2 条样本
- 每条样本同时 2 个模型
- 候选生成阶段稳定并发约 `4`

### 第二步：Judge 对 A/B 做 pairwise 比较

Judge 使用：

- OpenAI-compatible 模型

判断维度与当前项目已有 pairwise judge 工作流保持一致：

- `evidence_groundedness`
- `root_cause_quality`
- `actionability`
- `missing_info_quality`
- `overall_engineering_quality`

Judge 输出：

- `winner`
- `winner_confidence`
- 各维度 winner
- 各维度分数
- `overall_scores`
- `reason`

### 第三步：把 winner 映射成 `chosen / rejected`

如果：

- winner = `A`

则：

- `chosen = candidate_a`
- `rejected = candidate_b`

如果：

- winner = `B`

则：

- `chosen = candidate_b`
- `rejected = candidate_a`

如果：

- winner = `tie`

则该样本不进入最终 DPO 数据。

## 3. 为什么同一个 `sample_id` 允许出现最多 2 次

当前项目在做多批次候选生成后，并没有强制每个 `sample_id` 只保留 1 对，而是允许：

- **每个 `sample_id` 最多保留 2 对**

这样做的原因是：

1. 当前目标是第一版正式 DPO，需要比单对更大的数据量
2. 同一条 prompt 下，有时会出现两类都很有价值的偏好差异：
   - 一类偏向证据约束 / 根因判断
   - 一类偏向 next_steps / missing_info / 工程风格
3. 如果强制只保留 1 对，会损失不少有效区分信息

但也不无限放开，因为：

- 同一 prompt 重复太多次会隐式放大该样本权重
- 容易降低整体分布均衡性

所以当前折中规则是：

- `max_per_sample_id = 2`

## 4. 多批次结果是如何合并的

因为候选生成不是一次性完成的，而是分多次进行：

- smoke
- 100 条
- 200 条
- 中途中断后补的若干批

所以在进入正式 DPO 之前，先做了一次批次合并。

合并时：

- 以 `sample_id` 为键
- 按 `max_per_sample_id = 2` 限制保留数量
- `prefer_latest = true`

也就是说：

- 如果同一 `sample_id` 出现在多个批次
- 优先保留后面批次的记录

原因是后续批次通常使用了更稳定的脚本逻辑和更健康的模型组合。

## 5. 为什么合并后不是 300 多对全部都能直接训练

当前合并后的统计显示：

- `candidate_pairs_count = 324`
- `judge_results_count = 324`

但这不等于：

- 324 对都能直接进入 DPO 训练

原因有两个：

### 5.1 `tie` 会被过滤

Judge 返回 `tie` 的样本不会进入最终 preference 数据。

### 5.2 最终训练集要按 confidence 再分层

当前不是把全部非 tie 样本直接拿去训，而是导出两版：

- `high_only`
- `high_plus_medium`

这样后续可以：

- 先用 `high_only` 做更干净的 DPO smoke
- 再用 `high_plus_medium` 做更大规模的正式 DPO

## 6. 当前最终统计

基于：

- 输入：`/hy-tmp/llm-lab/data/dpo/merged_ds_dsp_max2/judge_results.jsonl`
- `max_per_sample_id = 2`

最终导出统计如下：

### 原始 judge 结果分布

- `medium = 168`
- `high = 155`
- `low = 1`

### `high_only`

- `high_only_count = 148`
- `high_only_sample_ids = 122`

### `high_plus_medium`

- `high_plus_medium_count = 275`
- `high_plus_medium_sample_ids = 190`

这些数字说明：

- 当前高置信 pair 已足够支撑一版 DPO smoke
- 高 + 中置信 pair 已足够支撑第一版正式 DPO

## 7. 当前数据质量的整体判断

这版 DPO 数据的优点是：

1. 不再是“空答 vs 正常答”的故障筛选型数据
2. Judge 主要在比较：
   - 是否更 grounded
   - 是否更保守
   - missing_info 是否更有帮助
   - next_steps 是否更可执行
3. 候选模型不是一边倒：
   - 强模型明显更强
   - 弱模型也能在部分样本上胜出
   - `tie` 比例也比较健康

当前最重要的结论不是：

- 数据已经完美

而是：

- 数据已经通过“可用性门槛”
- 可以进入正式 DPO 训练阶段

## 8. 推荐使用方式

当前建议按两阶段使用：

### 第一阶段：DPO smoke

使用：

- `data/dpo/final_ds_dsp/dpo_high_only.json`

理由：

- 置信度最高
- 噪声最小
- 最容易解释 DPO 是否有效

### 第二阶段：正式 DPO

使用：

- `data/dpo/final_ds_dsp/dpo_high_plus_medium.json`

理由：

- 数据量更大
- 覆盖的 prompt 分布更广
- 如果 `high_only` 方向正向，可以继续扩展到这一版

## 9. 一句话结论

当前这版最终 DPO 数据集并不是简单地把候选答案拼在一起，而是经过：

1. train prompt 采样
2. 双模型候选生成
3. LLM judge 选 winner
4. 多批次合并
5. 每个 `sample_id` 最多保留 `2` 对
6. 按 confidence 分层导出

得到的第一版正式 preference 数据。

**它已经足够支撑一版高置信 DPO smoke（148 对）和一版更大规模的正式 DPO（275 对）。**
