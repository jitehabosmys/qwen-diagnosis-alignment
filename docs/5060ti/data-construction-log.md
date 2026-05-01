# 数据构建记录

## 1. 目标

本项目的数据目标是构建一套可用于中文 `SFT` 的“训练/部署问题诊断助手”数据集。

输入包含：

- 用户问题
- 环境信息
- 命令
- 错误日志

输出为结构化 JSON：

```json
{
  "category": "dependency|training|data|inference|deployment",
  "severity": "low|medium|high",
  "summary": "一句话总结",
  "root_cause": "最可能根因",
  "missing_info": ["进一步排查需要的信息"],
  "next_steps": ["下一步建议"]
}
```

最终训练主文件是：

- [sft_train_final.jsonl](/home/sytssmys/llm-lab/data/sft_train_final.jsonl)
- [sft_train_final.json](/home/sytssmys/llm-lab/data/sft_train_final.json)

最终 LLaMA-Factory 数据文件是：

- [diagnosis_sft_alpaca.json](/home/sytssmys/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json)
- [dataset_info.json](/home/sytssmys/llm-lab/data/llamafactory/dataset_info.json)

## 2. 数据构建总流程

这套数据不是一次性“搜集完直接训练”，而是按下面的链路迭代得到的：

1. Gemini Deep Research + 技术社区素材收集原始案例
2. 手工整理原始案例，形成初始 seed
3. 从 seed 中挑出质量更高、类别更均衡的 `top49`
4. 用 API 调用大模型进行同类扩写
5. 对扩写结果做结构清洗
6. 对清洗结果做内容筛选
7. 人工复核 `top49`，选一部分回并到最终集
8. 转换为 LLaMA-Factory 可直接使用的 `alpaca` 格式

## 3. 原始 seed 来源

初始 seed 的来源主要是：

- Gemini Deep Research 搜集的社区报错素材
- 用户补充的训练 / 推理 / 部署相关案例
- 重点围绕：
  - `bitsandbytes`
  - `flash-attn`
  - `DeepSpeed`
  - `Accelerate`
  - `Pydantic / Transformers` 版本冲突
  - `LLaMA-Factory` 数据问题
  - `vLLM` 的 KV cache / CUDA graph / max seq len
  - LoRA / tokenizer / embedding size mismatch

最早的原始文件在整理后归档到了：

- [data/archive/sft_seed.raw.txt](/home/sytssmys/llm-lab/data/archive/sft_seed.raw.txt)
- [data/archive/sft_seed.json](/home/sytssmys/llm-lab/data/archive/sft_seed.json)

原始 seed 清洗脚本归档在：

- [scripts/archive/clean_sft_seed.py](/home/sytssmys/llm-lab/scripts/archive/clean_sft_seed.py)

## 4. 选出 `top49` seed

在初始 seed 基础上，进一步筛出一份更适合扩写的种子集：

- 文件：[sft_seed_top49.json](/home/sytssmys/llm-lab/data/sft_seed_top49.json)

筛选时重点考虑了：

- 类别分布不要过于偏向某一类
- 日志要尽量具体
- 场景要尽量贴近单卡微调、部署、依赖故障
- 输出 schema 要稳定

后续所有自动扩写都以 `top49` 为基础。

## 5. 自动扩写

### 5.1 两条扩写路径

本项目实际尝试过两条 API 扩写路径：

- Anthropic 兼容接口
- OpenAI 兼容接口

对应脚本：

- [expand_sft_anthropic.py](/home/sytssmys/llm-lab/scripts/expand_sft_anthropic.py)
- [expand_sft_openai.py](/home/sytssmys/llm-lab/scripts/expand_sft_openai.py)

批量收集脚本：

- [collect_until_target.py](/home/sytssmys/llm-lab/scripts/collect_until_target.py)

### 5.2 模型尝试过程

实际经历过的尝试大致如下：

1. 先尝试 OpenAI 兼容接口跑较强模型
2. 因为成本顾虑，尝试 Anthropic 兼容的小模型 `mimo-v2.5`
3. `mimo-v2.5` 可以稳定生成，但内容质量偏模板化
4. 后续切回 `gpt-5.3-codex` 批量扩写，结构和内容质量明显更好

最终大规模可用扩写主要来自 `gpt-5.3-codex`。

### 5.3 扩写时使用的 system prompt

Anthropic 和 OpenAI 版本使用的是同一套系统提示词，定义在两个脚本里。

核心内容如下：

```text
你是一名负责构造训练数据的工程师。

任务：
1. 参考给定 seed 样本，为每条 seed 扩写出若干条“同类型但不重复”的新样本。
2. 输出必须是严格 JSON，且只能输出 JSON，不要添加解释。
3. 输出的每条样本必须保持与 seed 相同的 schema：
   - instruction
   - input.user_question
   - input.environment
   - input.command
   - input.log
   - output.category
   - output.severity
   - output.summary
   - output.root_cause
   - output.missing_info
   - output.next_steps
4. output.category 只能是以下之一：
   - dependency
   - training
   - data
   - inference
   - deployment
5. output.severity 只能是 low、medium、high。
6. output.missing_info 和 output.next_steps 必须是非空数组。
7. 不要照抄 seed，必须改写环境、命令、日志细节、提问方式或信息完整度。
8. 不要引入明显超出日志证据的强结论，风格要克制、工程化、可执行。
9. 尽量生成与单卡训练、推理部署、常见依赖问题相关的样本，避免过于小众的硬件或特殊框架。
```

来源：

- [expand_sft_anthropic.py](/home/sytssmys/llm-lab/scripts/expand_sft_anthropic.py)
- [expand_sft_openai.py](/home/sytssmys/llm-lab/scripts/expand_sft_openai.py)

### 5.4 扩写时使用的 user prompt

每次请求并不是简单说“帮我扩几条”，而是把 seed 打包成一个 JSON payload 发给模型。

生成逻辑来自两个脚本里的 `build_user_prompt`。

核心结构如下：

```json
{
  "task": "请为每条 seed 扩写 N 条新样本。",
  "requirements": [
    "保持同一任务类型和同一输出 schema。",
    "可以改写环境、命令、日志、用户描述方式和缺失信息，但不要直接复制 seed。",
    "output.category 与 seed 保持一致或保持在同一问题域内。",
    "next_steps 要具体、保守、可执行。",
    "missing_info 要体现继续排查时真正需要的上下文。"
  ],
  "seeds": [
    {
      "seed_id": 0,
      "instruction": "...",
      "input": {...},
      "output": {...}
    }
  ]
}
```

这样做有几个目的：

- 让模型明确知道自己是在“扩写数据”而不是“回答问题”
- 保持输出 schema 稳定
- 让模型在同一类问题域内做变体生成
- 便于后续按 `seed_id` 追踪来源

### 5.5 批量生成策略

实际生成过程中使用了几种不同配置。

低成本模型阶段更保守：

- `seeds-per-request=1`
- `variants-per-seed=3`
- `max-workers=1`

OpenAI 兼容高质量阶段适度提高并发：

- `max-workers=3`
- `seeds-per-request=1`
- `variants-per-seed=3`

批量收集是通过下面的脚本滚动跑的：

- [collect_until_target.py](/home/sytssmys/llm-lab/scripts/collect_until_target.py)

这个脚本按类别轮转，谁样本少就先补谁，直到总量达到目标为止。

## 6. 第一轮清洗

自动扩写后的样本不会直接训练，而是先做结构清洗。

脚本：

- [clean_expanded_sft.py](/home/sytssmys/llm-lab/scripts/clean_expanded_sft.py)

主要处理：

- 删除内部字段，如 `_source_seed_id`
- 检查 schema 是否完整
- 检查 `instruction` 是否一致
- 检查 `category` / `severity` 是否合法
- 检查 `missing_info` / `next_steps` 是否为非空数组
- 删除类别错位样本
- 删除一小批明显可疑的 API / 命令 / 修复建议

这一步得到中间文件：

- [data/archive/sft_train_clean.jsonl](/home/sytssmys/llm-lab/data/archive/sft_train_clean.jsonl)

## 7. 第二轮内容筛选

结构对了，还不够。还需要对内容做质量筛选。

脚本：

- [select_sft_high_quality.py](/home/sytssmys/llm-lab/scripts/select_sft_high_quality.py)

这一轮不是纯人工逐条看完，而是：

1. 先人工抽样，看出哪些类型的坏味道最常见
2. 再把这些坏味道写成启发式规则进行打分筛选

加分项包括：

- 有明确技术信号
  - `LD_LIBRARY_PATH`
  - `CUDA_HOME`
  - `gpu_memory_utilization`
  - `dataset_info.json`
  - `destroy_process_group()`
- 日志本身信息量足够大
- 根因与建议比较具体

扣分项包括：

- 根因里大量出现“可能由于/可能是/环境问题/版本不兼容”
- 建议太空
- 带明显坏建议
  - `torch.cuda.empty_cache()` 被当成主修复方案
  - “先 import A 再 import B” 这种补丁式建议
  - “浏览器手动下载验证权限”这类低质量建议

在这一步中曾产出多个版本：

- [data/archive/sft_train_high_quality.jsonl](/home/sytssmys/llm-lab/data/archive/sft_train_high_quality.jsonl)
- [data/archive/sft_train_high_quality_450.jsonl](/home/sytssmys/llm-lab/data/archive/sft_train_high_quality_450.jsonl)
- 当前最终主干使用的是 `400` 版中间集：
  - [data/archive/sft_train_high_quality_400.jsonl](/home/sytssmys/llm-lab/data/archive/sft_train_high_quality_400.jsonl)

## 8. 人工复核 seed 并合并到最终集

除了自动筛出的 `400` 条高质量扩写样本，还对 `top49` seed 做了一轮人工复核。

目的是：

- 不把 seed 整包并入
- 只保留其中技术上更稳、风格更克制的条目
- 丢掉解释过满、风格过于夸张、或者 workaround 风险太高的 seed

最终手工选入了 `30` 条 seed。

合并脚本：

- [build_final_sft_dataset.py](/home/sytssmys/llm-lab/scripts/build_final_sft_dataset.py)

关键常量：

- `KEEP_SEED_INDICES`

最终得到：

- [sft_train_final.jsonl](/home/sytssmys/llm-lab/data/sft_train_final.jsonl)
- [sft_train_final.json](/home/sytssmys/llm-lab/data/sft_train_final.json)

最终规模：

- `400` 条高质量扩写
- `30` 条人工保留 seed
- 合计 `430` 条

## 9. 转换为 LLaMA-Factory 格式

为了让后续微调更顺手，最终数据又被转换为 LLaMA-Factory 可直接使用的 `alpaca` 格式。

脚本：

- [prepare_llamafactory_sft.py](/home/sytssmys/llm-lab/scripts/prepare_llamafactory_sft.py)

转换方式：

- `instruction`: 固定任务说明
- `input`: 将 `user_question / environment / command / log` 拼成一个长输入串
- `output`: 原本的 `output` JSON，序列化为字符串
- `system`: 固定系统提示词

输出文件：

- [diagnosis_sft_alpaca.json](/home/sytssmys/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json)
- [dataset_info.json](/home/sytssmys/llm-lab/data/llamafactory/dataset_info.json)

## 10. 归档与目录整理

为了避免 `data/` 和 `scripts/` 目录过于混乱，对中间产物做了统一归档，而不是直接删除。

归档脚本：

- [archive_intermediate_files.py](/home/sytssmys/llm-lab/scripts/archive_intermediate_files.py)

归档目录：

- [data/archive](/home/sytssmys/llm-lab/data/archive)
- [scripts/archive](/home/sytssmys/llm-lab/scripts/archive)

这样做的好处是：

- 主目录保持干净
- 中间结果仍然可追溯
- 后续如果要回看筛选策略或对比不同版本数据，仍然可以找到原文件

## 11. 本次数据构建的经验

### 11.1 便宜模型可以用来铺量，但不适合做最终主力

低成本模型可以帮助快速验证流程，但内容往往更模板化、泛化表达更多、幻觉风险更高。

### 11.2 更强模型的收益主要体现在“减少后处理成本”

`gpt-5.3-codex` 这类模型不只是“更会写”，而是会显著降低后续：

- 结构清洗成本
- 内容筛选成本
- 人工复核成本

### 11.3 自动筛选有用，但不能完全替代人工复核

启发式规则可以过滤掉一大批明显低质量样本，但：

- 类别误标
- 语义上过度猜测
- workaround 风格建议

这些问题最终还是需要人工再看一轮。

### 11.4 最终训练集不必盲目追求 500+

在预算有限、实验目标是“跑通第一版 SFT”时，一份更干净的 `430` 条数据，往往比一份更杂的 `800` 条更合适。

## 12. 最终可训练数据清单

推荐直接用于训练的主文件：

- [sft_train_final.jsonl](/home/sytssmys/llm-lab/data/sft_train_final.jsonl)

如果用 LLaMA-Factory，推荐直接使用：

- [diagnosis_sft_alpaca.json](/home/sytssmys/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json)
- [dataset_info.json](/home/sytssmys/llm-lab/data/llamafactory/dataset_info.json)
