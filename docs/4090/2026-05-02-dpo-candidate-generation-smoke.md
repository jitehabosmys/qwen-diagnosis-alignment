# 2026-05-02 DPO 候选生成 Smoke：200 条 train prompt

这份文档记录的是当前项目围绕 `DPO` 做的第一轮较成规模候选数据生成与筛选实验。

这轮实验的目标不是直接开始 `DPO` 训练，而是先回答：

1. 用现有 `train` 分布样本生成偏好对是否可行
2. 当前候选模型搭配是否能稳定产出有区分度的 pair
3. Judge 是否在比较真正的任务偏好，而不是技术性故障或格式问题

相关文件：

- 候选生成脚本：[generate_dpo_candidates.py](/hy-tmp/llm-lab/scripts/generate_dpo_candidates.py)
- 产物目录：`/hy-tmp/llm-lab/data/dpo/generated_pairs_ds_dsp_200`

## 1. 生成设置

当前这轮 DPO 候选生成使用：

- prompt 来源：`train` 样本
- 样本规模：`200`
- 候选模型 A：`deepseek-v4-pro`
- 候选模型 B：`deepseek-v4-flash`
- Judge：OpenAI-compatible judge model

流程为：

1. 从 `train` 样本中取 prompt
2. 使用两个候选模型分别生成答案
3. 使用 LLM judge 做 pairwise 比较
4. 导出：
   - 原始候选答案
   - judge 结果
   - 可直接喂给 LLaMA-Factory 的 `chosen/rejected` 数据

## 2. 总体统计

基于 `200` 条 prompt，当前得到：

- `judge_records = 200`
- `dpo_records = 162`

其中：

- `winner_counts`
  - `A = 116`
  - `B = 46`
  - `tie = 38`

- `confidence_counts`
  - `medium = 110`
  - `high = 90`

去掉 `tie` 之后：

- `deepseek-v4-pro` 胜率约 `71.60%`
- `deepseek-v4-flash` 胜率约 `28.40%`

这说明：

- `pro` 明显更强，但不是压倒性碾压
- `flash` 仍然能在相当一部分样本上胜出
- 数据分布已经从“单边碾压”进入“有区分度、但不过分失衡”的区间

## 3. 耗时观察

当前平均耗时大致为：

- `avg_total = 30.13s`
- `avg_a = 15.28s`
- `avg_b = 9.22s`
- `avg_judge = 7.87s`

这说明：

- 候选生成本身已经进入可规模化区间
- `judge` 耗时不是主要瓶颈
- 真正的主要成本仍在候选模型生成，尤其是更强的 `deepseek-v4-pro`

从工程角度，这个成本已经足以继续扩到 `400 ~ 500` 条，而不需要重新设计整条管线。

## 4. 当前数据质量判断

这轮 `200` 条的结果比最初的 `5 / 20 / 100` 条 smoke 更能说明问题。

当前最重要的积极信号有三个：

### 4.1 不再是一边倒的“故障型对比”

前一轮不健康数据曾经出现：

- 一边空答
- 另一边正常回答
- judge 只是在筛掉空答案

当前这轮已经不再是这种情况。  
两边候选答案都能稳定输出，judge 比较的是：

- 证据是否贴合日志
- 根因分析是否保守
- next_steps 是否更可执行
- missing_info 是否更有帮助

这说明现在的 pair 已经具有真正的 DPO 训练价值。

### 4.2 `tie` 明显增多是健康信号

当前 `tie = 38 / 200 = 19%`。

这说明：

- 不是所有样本都能被轻易拉开
- 有相当多样本属于“两边都还不错，但略有优劣”的边界区间

这类样本通常比“明显空答 vs 正常答”的 pair 更有训练信息密度。

### 4.3 `medium` 与 `high` 接近，说明区分粒度合理

当前：

- `medium = 110`
- `high = 90`

这意味着：

- 既有明显更优的 pair
- 也有差距较小但仍可判断的 pair

这比“全部 high confidence”更适合偏好训练，因为它说明 judge 不是机械在挑最容易的样本。

## 5. 亮点 pair

下面几条样本比较能代表这轮数据的质量特点。

### 5.1 `train_024`：弱模型因更保守而胜出

结果：

- winner：`deepseek-v4-flash`
- confidence：`medium`

亮点：

- 两边都抓住了“rank 0 无法分配 cache blocks”的核心
- 但 `pro` 给出了和日志方向相反的建议：
  - “降低 gpu_memory_utilization”
- `flash` 则更贴合日志原文和部署语境

这说明 judge 并没有无条件偏向更强模型，而是在奖励：

- 更贴证据
- 更保守
- 更符合现场环境的建议

### 5.2 `train_127`：更强模型也会因过度建议而输

结果：

- winner：`deepseek-v4-flash`
- confidence：`high`

亮点：

- 两边都识别出 `DDP ready-twice` 和 LoRA 参数重复使用问题
- 但 `pro` 给出了一些低置信或不够稳妥的临时绕法：
  - `switch backend to gloo`
  - `static_graph=True`
- `flash` 虽然更短，但建议更集中、更安全

这说明 current judge 对“工程上危险但看起来很聪明”的建议有一定抑制作用。

### 5.3 `train_041`：更强模型在数据问题上体现出更好的排障深度

结果：

- winner：`deepseek-v4-pro`
- confidence：`high`

亮点：

- 两边都能识别缺少 `text` 字段
- `pro` 给出了更完整的排障路径：
  - 字段重命名
  - 嵌套结构展开
  - 列名映射
  - 单样本结构检查

这说明 `pro` 的优势主要体现在：

- 更系统
- 更适合闭环排障

而不是单纯更长。

### 5.4 `train_198`：Gated 模型权限问题上的信息增益

结果：

- winner：`deepseek-v4-pro`
- confidence：`high`

亮点：

- 两边都识别了 `403` 与 LLaMA-2 gated access 有关
- `pro` 额外补了更完整的认证链条：
  - 是否已获批访问
  - token 是否已配置
  - `transformers` / `huggingface_hub` 版本

这说明对于权限、环境链路类问题，`pro` 往往能提供更适合运维与部署排障的上下文。

### 5.5 `train_312`：健康的 `tie`

结果：

- winner：`tie`
- confidence：`medium`

亮点：

- 两边都正确识别为 optimizer step 阶段的显存问题
- 两边都有可执行的缓解建议
- judge 认为整体质量非常接近

这种样本非常有价值，因为它说明：

- 当前模型搭配不是简单地一边倒
- judge 也愿意在质量接近时返回 `tie`

这能避免 DPO 数据池被强行灌入大量“硬分”但信息不高的 pair。

## 6. 当前阶段结论

对于这批 `200` 条 train prompt 候选生成结果，我的判断是：

1. 候选模型组合已经可用
2. judge 行为健康，主要在比较任务相关质量
3. 数据分布没有明显退化
4. 这批数据已经足够支撑继续扩到 `400 ~ 500` 条

但同时也要保持一点纪律：

- `pro` 仍然明显更强
- chosen 往往也更完整、更长
- 后续仍要继续观察是否出现长度偏置

因此当前最合理的做法不是立刻 DPO，而是：

1. 再扩一轮到 `400` 条左右
2. 观察胜率、tie、confidence 分布是否稳定
3. 再决定是否直接进入第一版正式 DPO

## 7. 一句话结论

这批 `200` 条 train prompt 的 DPO 候选数据已经通过了“可用性门槛”：

**`deepseek-v4-pro` 与 `deepseek-v4-flash` 的组合不再只是“强弱模型对打”，而是在真实任务偏好上形成了有区分度但不过度失衡的 pair 分布，因此值得继续扩展到更大规模。**
