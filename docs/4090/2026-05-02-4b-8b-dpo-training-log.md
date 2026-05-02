# 2026-05-02 4B / 8B DPO 训练记录

这份文档记录的是当前项目在 `RTX 4090 24GB` 单卡环境上，基于第一版正式 DPO 数据集对：

- `Qwen3-4B strict lora`
- `Qwen3-8B strict qlora`

做的一轮 `DPO` 训练。

这轮实验的目标不是立即下最终模型优劣结论，而是回答：

1. 当前构造出的 DPO 数据集能否稳定驱动 `4B / 8B` 继续学习
2. `4B` 和 `8B` 在同一批偏好数据上的训练响应是否有明显差别
3. 下一步是否值得继续做 `SFT vs DPO` 的推理评测和 pairwise judge

相关文档：

- [2026-05-02-final-dpo-dataset.md](/hy-tmp/llm-lab/docs/4090/2026-05-02-final-dpo-dataset.md)
- [2026-05-01-qwen3-4b-strict-repro-on-4090.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-4b-strict-repro-on-4090.md)
- [2026-05-01-qwen3-8b-qlora-sft-log.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-8b-qlora-sft-log.md)

## 1. 数据集与配置

本轮 DPO 使用的是：

- 高置信偏好数据：`diagnosis_dpo_high_only`

对应产物见：

- `data/dpo/final_ds_dsp/dpo_high_only.json`

训练配置：

- [4090_qwen3_4b_lora_dpo_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_4b_lora_dpo_strict_json_prompt.yaml)
- [4090_qwen3_8b_qlora_dpo_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/4090_qwen3_8b_qlora_dpo_strict_json_prompt.yaml)

当前关键超参数：

- `pref_beta = 0.1`
- `pref_loss = sigmoid`
- `num_train_epochs = 3`

其中：

- `4B` 继续沿用 LoRA
- `8B` 继续沿用 QLoRA

## 2. 8B DPO 结果

`8B DPO` 最终指标：

- `train_loss = 1.1884`
- `train_runtime = 0:04:38.88`
- `train_samples_per_second = 1.592`
- `train_steps_per_second = 0.108`

中间训练日志的典型区间：

- `loss` 大致从 `1.387` 下降到 `0.975`
- `rewards/accuracies` 大致在 `0.55 ~ 0.67`
- `rewards/margins` 大致从 `0.7982` 增长到 `1.614`

这说明：

- 当前 DPO 数据对 `8B` 是有效的
- 模型在训练过程中确实学到了 chosen/rejected 的偏好差异
- 奖励间隔有扩大趋势

## 3. 4B DPO 结果

`4B DPO` 最终指标：

- `train_loss = 0.8568`
- `train_runtime = 0:03:19.38`
- `train_samples_per_second = 2.227`
- `train_steps_per_second = 0.286`

中间训练日志的典型区间：

- `loss` 多次降到 `0.55 ~ 0.90`
- `rewards/accuracies` 大致在 `0.64 ~ 0.85`
- `rewards/margins` 大致在 `1.37 ~ 3.34`

这说明：

- `4B` 对这批 DPO 数据的训练响应非常强
- 奖励间隔拉得更快
- 从训练过程看，`4B` 很容易把这批偏好信号学进去

## 4. 为什么 4B 的 train loss 更低

这是这轮实验里最容易让人误读的一点。

当前结果确实显示：

- `4B train_loss = 0.8568`
- `8B train_loss = 1.1884`

但这里不能直接得出：

- `4B DPO 一定比 8B DPO 更好`

原因是：

### 4.1 DPO loss 不是普通的可跨模型直接比较的 SFT loss

DPO 优化的是：

- chosen 相对 rejected 的偏好差异

所以 loss 大小不仅受训练效果影响，也受：

- 当前底模的初始偏好分布
- 模型与这批 pair 的相对错位程度
- reward margin 尺度

影响。

### 4.2 4B 可能更容易被当前这批偏好对“推着走”

当前高置信 DPO 数据对 `4B` 来说，可能恰好更容易形成明显的 chosen/rejected 分离，因此：

- 训练 loss 掉得更快
- rewards/accuracies 与 rewards/margins 看起来更漂亮

这说明的是：

- `4B` 对这批数据的训练响应更强

而不一定说明：

- 最终任务质量一定比 `8B DPO` 更好

## 5. 当前最稳的解释

基于现有训练结果，当前最稳的判断是：

1. `4B` 和 `8B` 都能从这批 DPO 数据中学习到有效偏好信号
2. `4B` 的训练过程在数值上更“顺手”
3. 但这仍然只是训练响应层面的观察，不是最终任务效果结论

因此当前不应该直接下结论说：

- `4B DPO` 优于 `8B DPO`

更准确的说法是：

- **`4B` 对当前这批高置信 DPO 数据的训练响应更强**

## 6. 下一步该看什么

要回答哪个 DPO 更值得，真正关键的不是 train loss，而是：

1. `HF` 自动规则评测
2. `SFT vs DPO` 的 pairwise judge

具体而言，下一步最重要的是：

### 6.1 8B

- `8B SFT` vs `8B DPO`
- 看 strict JSON 稳定性是否变化
- 看内容质量是否提升

### 6.2 4B

- `4B SFT` vs `4B DPO`
- 判断它虽然更容易优化，但是否也真的在任务质量上更进一步

## 7. `SFT vs DPO` 的 pairwise judge 结果

在完成自动规则评测后，又继续对：

- `8B SFT` vs `8B DPO`
- `4B SFT` vs `4B DPO`

做了一轮 pairwise judge。

这一步非常关键，因为自动规则评测更容易看到：

- JSON 结构是否稳定
- category / severity 是否命中参考答案

而 pairwise judge 更接近回答：

- 哪个版本更 grounded
- 哪个版本建议更可执行
- 哪个版本整体更像一个可靠的工程诊断助手

### 7.1 8B：DPO 小幅但稳定领先

`8B SFT` vs `8B DPO` 的结果：

- `DPO wins = 13`
- `SFT wins = 7`
- `tie = 28`

去掉 `tie` 之后：

- `8B DPO win rate = 65%`

总体平均分：

- `SFT = 3.6383`
- `DPO = 3.8298`
- `delta = +0.1915`

维度层面：

- `evidence_groundedness: +0.0426`
- `root_cause_quality: +0.1064`
- `actionability: +0.2128`
- `missing_info_quality: +0.1064`
- `overall_engineering_quality: +0.1702`

这说明：

- `8B DPO` 相比 `8B SFT` 是正向提升
- 但大量 `tie` 也说明：
  - `8B SFT` 本来就已经不差
  - DPO 更多像是在一些边界样本上做精修

### 7.2 4B：DPO 提升更明显

`4B SFT` vs `4B DPO` 的结果：

- `DPO wins = 18`
- `SFT wins = 6`
- `tie = 24`

去掉 `tie` 之后：

- `4B DPO win rate = 75%`

总体平均分：

- `SFT = 3.5000`
- `DPO = 3.6875`
- `delta = +0.1875`

维度层面：

- `evidence_groundedness: +0.1042`
- `root_cause_quality: +0.0833`
- `actionability: +0.1667`
- `missing_info_quality: +0.1875`
- `overall_engineering_quality: +0.1667`

这说明：

- `4B DPO` 对 `4B SFT` 的提升更明显
- 尤其体现在：
  - `actionability`
  - `missing_info_quality`
  - `overall_engineering_quality`

### 7.3 这组结果为什么有意思

这轮 judge 给出了一个比单看 train loss 或自动规则评测更完整的图景：

#### 第一层

`4B` 和 `8B` 的 DPO 都是有效的。

也就是说：

- 这批 DPO 数据并不是无效的
- 它确实把模型往 judge 更偏好的方向推了

#### 第二层

`4B` 与 `8B` 的 DPO 增益形态不同。

更像是：

- `4B DPO`：
  - 更像“能力补强”
  - 在更多样本上带来可见改变

- `8B DPO`：
  - 更像“工程化精修”
  - 原本基线已经较强，因此更多样本进入 `tie`

#### 第三层

自动规则评测低估了 DPO 的收益，尤其是 `4B`。

在自动规则指标里：

- `4B SFT` 与 `4B DPO` 几乎看不出差别

但 pairwise judge 说明：

- `4B DPO` 在内容质量上其实有相当明确的正向提升

这再次说明：

- 对当前任务，不能只靠自动规则指标判断 DPO 是否有效

## 8. 当前最稳的路线解释

把训练日志、自动评测和 pairwise judge 放在一起看，当前更合理的解释是：

1. `4B` 和 `8B` 都能从当前高置信 DPO 数据中学习到有价值的偏好信号
2. `4B` 的训练响应更强，且在 judge 上的相对提升更明显
3. `8B` 的训练响应更温和，但 judge 仍然显示它在工程质量上进一步变好

因此当前更准确的表述不是：

- `4B DPO` 优于 `8B DPO`

而是：

- **DPO 对两条路线都有效，只是 4B 更像被明显“拉升”，8B 更像被进一步“打磨”。**

## 9. 一句话结论

这轮 `4B / 8B DPO` 训练说明：

**当前高置信 DPO 数据集已经足够驱动 `4B` 与 `8B` 两条路线继续学习；在最终的 pairwise judge 中，DPO 对两者都带来了正向收益，但 `4B` 更像被明显拉升，而 `8B` 更像在强基线之上被进一步精修。**
