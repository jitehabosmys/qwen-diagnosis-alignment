# Pairwise Judge 工作流

这份文档描述的是当前仓库第二层评测流程：

**在硬规则评测之后，使用 OpenAI 官方 Python SDK 调用 judge 模型，对两组候选输出做 pairwise 比较。**

## 1. 目标

这一步不再只看：

- JSON 是否合法
- schema 是否完整

而是开始评内容质量，主要比较：

- `evidence_groundedness`
- `root_cause_quality`
- `actionability`
- `missing_info_quality`
- `overall_engineering_quality`

同时，这一步还可以顺手产出 DPO 候选对。

## 2. 相关文件

脚本：

- [run_pairwise_judge.py](/hy-tmp/llm-lab/scripts/run_pairwise_judge.py)

环境变量示例：

- [.env.example](/hy-tmp/llm-lab/.env.example)

## 3. 前置条件

需要：

- 仓库 `.venv` 中已安装官方 `openai` SDK
- 已设置 `OPENAI_API_KEY`

如果你使用的不是 OpenAI 官方域名，而是兼容 OpenAI Responses API 的服务，也可以额外设置：

- `OPENAI_BASE_URL`

当前仓库 `pyproject.toml` 已包含 `openai` 依赖。  
如果需要激活本项目环境：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
```

不要直接用系统 Python 运行这个脚本。  
应优先使用仓库自己的 `.venv`，否则可能出现：

```text
ModuleNotFoundError: No module named 'openai'
```

脚本会默认尝试读取仓库根目录的 `.env`，并在环境变量尚未存在时加载其中的键值。  
因此你可以把下面这些配置直接写进 `.env`：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_JUDGE_MODEL=gpt-5-mini
```

## 4. 输入形式

脚本读取两份推理结果文件，例如：

- `default_prompt_lora_results.jsonl`
- `strict_json_prompt_lora_results.jsonl`

每条样本按相同 `sample_id` 配对后，再交给 judge。

## 5. 评测流程

### 5.1 第一步：schema gate

在真正调用 judge 前，脚本先做硬门槛过滤：

- 如果 A `schema_valid=true` 而 B `schema_valid=false`，直接判 A 胜
- 如果 B `schema_valid=true` 而 A `schema_valid=false`，直接判 B 胜
- 如果两边都 `schema_valid=false`，直接标记为 `tie` / 跳过内容判断

这样能避免把明显不合法的输出交给 LLM judge 浪费 token。

### 5.2 第二步：LLM judge

只有当两边都通过 schema gate 时，才真正调用 judge 模型。

judge 返回：

- `winner`: `A | B | tie`
- `winner_confidence`: `low | medium | high`
- `dimension_winners`
- `dimension_scores`
- `overall_scores`
- `reason`

## 6. 当前 judge 维度

### `evidence_groundedness`

是否严格依据输入中的问题、环境、命令、日志作答，而不是凭空发挥。

### `root_cause_quality`

根因是否抓住主要矛盾，是否解释力更强，是否不过度武断。

### `actionability`

排查建议是否具体、保守、可执行，而不是空泛建议。

### `missing_info_quality`

提出的缺失信息是否真能帮助下一步定位，而不是机械补问。

### `overall_engineering_quality`

整体是否像一个合格的训练/部署问题诊断助手：克制、结构清晰、优先级合理。

## 6.1 分数输出

除了维度 winner 之外，当前 judge 还会为每个维度输出：

- `A_score: 1-5`
- `B_score: 1-5`

并且额外输出：

- `overall_scores.A_score`
- `overall_scores.B_score`

这些分数的主要用途不是替代 pairwise winner，而是：

- 观察不同模型规模之间的平均分变化
- 估计 `0.5B -> 3B -> 4B` 的边际收益
- 作为“何时停止继续 scale up、转向 DPO”的辅助信号

建议把分数主要用于：

- 平均分
- 平均分差
- 边际提升趋势

而不是过度解读单条样本的绝对打分。

## 7. A/B 顺序偏置处理

脚本会对每条样本随机化 A/B 展示顺序。  
内部会在 judge 返回后再映射回真实候选标签，降低位置偏置。

## 8. 输出文件

默认输出目录：

- `/hy-tmp/outputs/llm-lab-pairwise-judge/<timestamp>/`

主要文件：

- `run_manifest.json`
- `judge_results.jsonl`
- `judge_summary.json`
- `dpo_pairs.jsonl`
- `dpo_pairs_high_confidence.jsonl`

## 9. DPO 产物说明

### `dpo_pairs.jsonl`

保存所有非 `tie` 的 pair，字段包括：

- `sample_id`
- `chosen_variant`
- `rejected_variant`
- `chosen_output`
- `rejected_output`
- `judge_source`
- `winner_confidence`
- `dimension_winners`
- `judge_reason`

### `dpo_pairs_high_confidence.jsonl`

只保留高置信 pair：

- schema gate 直接判胜的样本
- 或 judge 给出 `winner_confidence=high` 的样本

这份文件更适合后续优先进入 DPO 数据池。

### `judge_summary.json` 中新增的分数统计

当前汇总中还会新增：

- `dimension_score_averages`
- `overall_score_averages`

你可以用这些统计：

- 看大模型相对小模型到底“高多少分”
- 判断继续 scale up 的收益是否开始变小

## 10. 最小运行命令

以默认版 LoRA 和 strict 版 LoRA 做对比：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
export OPENAI_API_KEY=...
python scripts/run_pairwise_judge.py \
  --candidate-a /hy-tmp/llm-lab/20260429_164620/default_prompt_lora_results.jsonl \
  --candidate-b /hy-tmp/llm-lab/20260429_164620/strict_json_prompt_lora_results.jsonl \
  --label-a default_prompt_lora \
  --label-b strict_json_prompt_lora \
  --concurrency 4
```

如果需要显式指定兼容接口地址：

```bash
python scripts/run_pairwise_judge.py ... --base-url https://your-openai-compatible-endpoint
```

如果希望 judge 参考数据集参考答案：

```bash
python scripts/run_pairwise_judge.py ... --use-reference
```

## 11. 当前建议

第一轮不要一上来比太多组合。  
优先比较：

1. `default_prompt_lora` vs `strict_json_prompt_lora`
2. `default_prompt_base` vs `default_prompt_lora`

这样最容易回答两个核心问题：

- strict prompt 对 LoRA 是否真的带来内容质量提升
- LoRA 相比 base 的内容质量提升究竟有多明显

如果已经完成 `3B` 的 SFT 和自动规则评测，下一步最推荐的新增比较是：

3. `default_prompt_lora (0.5B)` vs `qwen25_3b_default_prompt_lora`

这组比较最适合回答：

- 更大的模型在完成同类 SFT 后，内容质量是否明显更强
- 后续 DPO 主线是否应从 `0.5B` 转向 `3B`

推荐命令模板：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
python scripts/run_pairwise_judge.py \
  --candidate-a /hy-tmp/llm-lab/20260429_164620/default_prompt_lora_results.jsonl \
  --candidate-b /hy-tmp/outputs/llm-lab-inference-eval/20260430_170248/qwen25_3b_default_prompt_lora_results.jsonl \
  --label-a qwen25_05b_default_prompt_lora \
  --label-b qwen25_3b_default_prompt_lora \
  --concurrency 4
```
