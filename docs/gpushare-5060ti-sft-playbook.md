# 5060 Ti SFT 执行手册

这份文档只回答一件事：

**在 `RTX 5060 Ti 16GB` 上，如何用当前仓库的数据，把第一轮 `SFT` 训练链路跑通。**

适用前提：

- 工作目录：`/hy-tmp/llm-lab`
- 训练框架：`/hy-tmp/LLaMA-Factory`
- 当前阶段：只做 `SFT`，不做 `DPO`、`vLLM`、`DeepSpeed`

## 1. 这张卡的任务边界

`5060 Ti 16GB` 在当前项目里不是最终实验卡，而是：

- 流程验证卡
- 首轮真实训练卡
- 风险暴露卡

这轮训练的验收目标只有四个：

- 数据能被 `LLaMA-Factory` 正确读取
- 训练能正常保存 checkpoint
- loss 在下降，没有 `nan`
- 模型输出的 JSON 稳定性明显好于 base model

## 2. 本仓库新增的文件

这次为 `5060 Ti` 准备了三类文件：

- 数据切分脚本：[prepare_5060ti_splits.py](/hy-tmp/llm-lab/scripts/prepare_5060ti_splits.py)
- smoke 配置：[5060ti_qwen25_05b_smoke_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_smoke_lora_sft.yaml)
- full 配置：[5060ti_qwen25_05b_full_lora_sft.yaml](/hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml)

数据元信息已经补到：

- [dataset_info.json](/hy-tmp/llm-lab/data/llamafactory/dataset_info.json)

新增的数据集名字是：

- `diagnosis_sft_smoke`
- `diagnosis_sft_train`
- `diagnosis_sft_eval`

## 3. 第一步：切分数据

先在 `llm-lab` 环境里执行：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
python scripts/prepare_5060ti_splits.py
```

默认行为：

- 从 `430` 条总数据里切出 `48` 条 eval
- 剩余部分作为 full train
- 从 train 再抽 `32` 条作为 smoke train
- 切分是确定性的，默认 seed 为 `42`

输出文件：

- `data/llamafactory/diagnosis_sft_smoke_alpaca.json`
- `data/llamafactory/diagnosis_sft_train_alpaca.json`
- `data/llamafactory/diagnosis_sft_eval_alpaca.json`
- `data/llamafactory/prepare_5060ti_report.json`

注意：

- `smoke` 是 `train` 的子集，不是独立任务集
- `eval` 与 `train/smoke` 不重叠

## 4. 第二步：先跑 smoke

切到 `LLaMA-Factory` 环境：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
```

如果这台机器直连 `huggingface.co` 不通，先切到 `ModelScope`：

```bash
export USE_MODELSCOPE_HUB=1
```

启动命令：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_smoke_lora_sft.yaml
```

这份配置的设计原则是保守：

- 模型：`Qwen/Qwen2.5-0.5B-Instruct`
- 方式：`LoRA`
- `cutoff_len=1024`
- `max_steps=40`
- `gradient_accumulation_steps=8`

smoke 的目标不是效果，而是确认：

- 模板能过
- 数据能过
- 显存能过
- checkpoint 能落盘

## 5. 第三步：再跑第一轮真实训练

如果 smoke 没报结构性错误，再跑 full：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml
```

这份配置的核心参数：

- 模型：`Qwen/Qwen2.5-0.5B-Instruct`
- 训练集：`diagnosis_sft_train`
- 验证集：`diagnosis_sft_eval`
- `cutoff_len=1536`
- `gradient_accumulation_steps=16`
- `num_train_epochs=3`

输出目录默认放在：

- `/hy-tmp/outputs/llamafactory/qwen25-05b-smoke-lora-sft`
- `/hy-tmp/outputs/llamafactory/qwen25-05b-full-lora-sft`

## 6. 跑完以后看什么

这轮不要只看 loss。

至少检查下面几项：

1. 训练日志里 loss 是否持续下降且没有 `nan`
2. 输出目录里是否真的生成了 checkpoint
3. 随机抽 `10` 条样本做推理时，JSON 可解析率是否上升
4. `category` 和 `severity` 是否基本只落在合法枚举值里
5. `missing_info` 和 `next_steps` 是否仍经常为空

## 7. 如果要升到 1.5B

不要先写第三份配置，直接在命令行覆盖更稳妥：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train \
  /hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_full_lora_sft.yaml \
  model_name_or_path=Qwen/Qwen2.5-1.5B-Instruct \
  output_dir=/hy-tmp/outputs/llamafactory/qwen25-15b-full-lora-sft \
  gradient_accumulation_steps=32
```

原因很简单：

- 先复用已经跑通的配置
- 只改必要变量
- 这样更容易定位“是模型变大带来的问题”，还是“配置本身就有问题”

## 8. 两个现实注意点

### 8.1 `template`

这里默认写的是：

```yaml
template: qwen
```

这是按当前 `Qwen2.5 Instruct` 的常见文本模板写的。  
如果你的 `LLaMA-Factory` 版本对这个模型要求的是 `qwen2`，直接在命令行覆盖：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train \
  /hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_smoke_lora_sft.yaml \
  template=qwen2
```

### 8.2 `bf16`

配置里默认是：

```yaml
bf16: true
```

如果环境报 dtype 或硬件支持相关错误，就改成：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train \
  /hy-tmp/llm-lab/configs/llamafactory/5060ti_qwen25_05b_smoke_lora_sft.yaml \
  bf16=false \
  fp16=true
```

### 8.3 模型下载源

当前这台恒源云机器如果出现：

```text
Network is unreachable
Failed to load tokenizer
```

优先判断为：

- `huggingface.co` 不可达
- 模型和 tokenizer 尚未缓存到本地

当前 `LLaMA-Factory` 环境已经安装了 `modelscope`，所以最短修复路径通常不是改数据或改训练参数，而是：

```bash
export USE_MODELSCOPE_HUB=1
```

然后重跑训练命令。  
配置里已经把模型缓存目录固定为：

```text
/hy-tmp/models
```

如果之后你想彻底避免启动时下载，也可以先把模型下到本地，再把 `model_name_or_path` 改成一个本地目录。

## 9. 当前最合理的执行顺序

建议就按这个顺序，不要跳：

1. 运行切分脚本
2. 跑 `0.5B smoke`
3. 检查日志、checkpoint、简单推理
4. 跑 `0.5B full`
5. 只有前面都顺了，再尝试 `1.5B`

如果你现在是在 `LLaMA-Factory` 刚装好的状态，先把 smoke 跑出来比继续写计划更重要。
