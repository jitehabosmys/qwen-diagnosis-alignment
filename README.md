# llm-lab

一个围绕中文“训练 / 部署问题诊断助手”数据构建与微调实验的小型项目。

当前仓库已经包含：

- 种子数据筛选与扩写脚本
- 扩写后样本的清洗与内容筛选脚本
- 最终 SFT 训练集
- LLaMA-Factory 可直接使用的数据格式
- 数据构建过程文档
- 多轮 `0.5B / 3B / 4B` SFT 与评测记录
- strict prompt 主线与 pairwise judge 工作流

关键文件：

- 最终训练集：
  - `data/sft_train_final.jsonl`
  - `data/sft_train_final.json`
- LLaMA-Factory 数据：
  - `data/llamafactory/diagnosis_sft_alpaca.json`
  - `data/llamafactory/dataset_info.json`
- 数据构建记录：
  - `docs/data-construction-log.md`
- 当前阶段总览：
  - [2026-05-01-project-status-before-4090.md](/hy-tmp/llm-lab/docs/2026-05-01-project-status-before-4090.md)

主要脚本：

- `scripts/collect_until_target.py`
- `scripts/expand_sft_anthropic.py`
- `scripts/expand_sft_openai.py`
- `scripts/clean_expanded_sft.py`
- `scripts/select_sft_high_quality.py`
- `scripts/build_final_sft_dataset.py`
- `scripts/prepare_llamafactory_sft.py`
