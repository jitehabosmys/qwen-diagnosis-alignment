# 恒源云训练全流程

## 1. 目标

这份文档描述的是：  
**拿到恒源云 GPU 实例之后，如何从 SSH 登录开始，一步步把当前项目的数据接上 LLaMA-Factory，并完成第一轮训练。**

适用场景：

- 机器：恒源云按量实例
- 当前优先卡：`RTX 5060 Ti 16GB`
- 后续正式卡：`RTX 4090 24GB`
- 训练框架：`LLaMA-Factory`
- 数据：本项目已准备好的 `430` 条 SFT 数据

## 2. 工作原则

在恒源云上，最重要的原则是：

- **小文件放系统盘**
- **所有大文件放 `/hy-tmp`**

根据欢迎页说明：

- `/hy-tmp`：本地高速盘，适合训练数据、模型、cache、checkpoint
- `/hy-public`：公共只读数据盘
- 系统盘不要放满，否则实例可能无法正常启动

所以本项目建议统一使用：

```bash
/hy-tmp/llm-lab
```

作为工作目录。

## 3. SSH 登录后第一步

登录示例：

```bash
ssh -p <端口> root@<主机>
```

登录后先检查基础环境：

```bash
whoami
uname -a
nvidia-smi
df -h
```

重点确认：

- 当前是不是 root
- GPU 是否可见
- 驱动是否正常
- `/hy-tmp` 是否存在
- 系统盘是否足够空闲

## 4. 创建工作目录

建议执行：

```bash
mkdir -p /hy-tmp/llm-lab
mkdir -p /hy-tmp/.cache
mkdir -p /hy-tmp/models
mkdir -p /hy-tmp/outputs
mkdir -p /hy-tmp/logs
```

如果你准备把仓库直接放进去：

```bash
cd /hy-tmp
git clone <你的仓库地址> llm-lab
cd /hy-tmp/llm-lab
```

如果还没有推到远程，也可以从本地传：

```bash
scp -P <端口> -r ./llm-lab root@<主机>:/hy-tmp/
```

## 5. 配置缓存目录

这一步非常重要。  
如果不改，很多缓存会默认写到 root 目录或系统盘。

建议把下面这些环境变量写到 `~/.bashrc`：

```bash
export HF_HOME=/hy-tmp/.cache/huggingface
export TRANSFORMERS_CACHE=/hy-tmp/.cache/huggingface/transformers
export HUGGINGFACE_HUB_CACHE=/hy-tmp/.cache/huggingface/hub
export TORCH_HOME=/hy-tmp/.cache/torch
export XDG_CACHE_HOME=/hy-tmp/.cache
```

追加写入命令：

```bash
cat >> ~/.bashrc <<'EOF'
export HF_HOME=/hy-tmp/.cache/huggingface
export TRANSFORMERS_CACHE=/hy-tmp/.cache/huggingface/transformers
export HUGGINGFACE_HUB_CACHE=/hy-tmp/.cache/huggingface/hub
export TORCH_HOME=/hy-tmp/.cache/torch
export XDG_CACHE_HOME=/hy-tmp/.cache
EOF
source ~/.bashrc
```

## 6. 建议先装 tmux

训练不要直接挂在裸 SSH 会话里。

安装：

```bash
apt-get update
apt-get install -y tmux
```

创建 session：

```bash
tmux new -s train
```

断线重连后恢复：

```bash
tmux attach -t train
```

## 7. 准备项目环境

进入项目目录：

```bash
cd /hy-tmp/llm-lab
```

如果机器上没有 `uv`，先装 `uv`。  
如果已经有 `uv`，直接：

```bash
uv sync
source .venv/bin/activate
```

检查关键包：

```bash
python -V
python -c "import torch; print(torch.__version__)"
python -c "import openai, anthropic; print('ok')"
```

## 8. 准备 LLaMA-Factory

建议把 LLaMA-Factory 单独放在 `/hy-tmp` 下面：

```bash
cd /hy-tmp
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
```

安装依赖：

```bash
uv sync
source .venv/bin/activate
```

如果官方仓库没有内置你环境需要的依赖，也可以按官方文档改用：

```bash
pip install -e .
```

## 9. 准备数据给 LLaMA-Factory

本项目已经准备好 LLaMA-Factory 训练数据：

- [diagnosis_sft_alpaca.json](/home/sytssmys/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json)
- [dataset_info.json](/home/sytssmys/llm-lab/data/llamafactory/dataset_info.json)

建议把它们复制或软链接到 LLaMA-Factory 的 `data/` 目录。

方式一：软链接

```bash
cd /hy-tmp/LLaMA-Factory
ln -sf /hy-tmp/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json data/diagnosis_sft_alpaca.json
```

`dataset_info.json` 需要注意：  
如果官方仓库原本已经有 `data/dataset_info.json`，不要直接覆盖整个文件，应该把我们的数据集定义合并进去。

本项目的数据集定义内容是：

```json
{
  "diagnosis_sft_final": {
    "file_name": "diagnosis_sft_alpaca.json",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output",
      "system": "system"
    }
  }
}
```

如果你想直接替换成最小版本：

```bash
cp /hy-tmp/llm-lab/data/llamafactory/dataset_info.json data/dataset_info.json
```

## 10. 两张卡的实际使用策略

### 10.1 `5060 Ti 16GB`

推荐用途：

- 验证训练流程
- 跑第一轮真实 SFT
- 调通数据、模板、参数

推荐模型：

- `Qwen2.5-0.5B-Instruct`
- `Qwen2.5-1.5B-Instruct`

不建议：

- 一开始就上大模型
- 一开始就追求最终结果

### 10.2 `4090 24GB`

推荐用途：

- 正式主实验
- 更完整的 SFT
- 后续 DPO / vLLM 验证

更详细策略见：

- [gpu-strategy-5060ti-vs-4090.md](/home/sytssmys/llm-lab/docs/gpu-strategy-5060ti-vs-4090.md)

## 11. 第一次训练建议

如果你已经完成 LLaMA-Factory 安装，并准备在 `5060 Ti 16GB` 上直接开跑，详细执行方案见：

- [gpushare-5060ti-sft-playbook.md](/hy-tmp/llm-lab/docs/gpushare-5060ti-sft-playbook.md)

### 11.1 先做 smoke test

不要一上来就跑完整训练。  
建议先用：

- 小模型
- 少量 step
- 少量数据

目标是确认：

- 数据能被读到
- tokenizer / template 正常
- loss 在动
- checkpoint 能保存

### 11.2 再做第一轮真实训练

如果 smoke test 没问题，再用：

- 完整 `430` 条数据
- 小模型
- LoRA / QLoRA

去跑第一轮真实 SFT。

此时的目标是：

- 看结构化 JSON 输出是否变稳定
- 看 loss 是否下降
- 看训练耗时和显存是否合理

## 12. 输出目录建议

训练输出统一建议放在：

```bash
/hy-tmp/outputs
```

例如：

```bash
/hy-tmp/outputs/llamafactory-qwen25-05b-sft
/hy-tmp/outputs/llamafactory-qwen25-15b-sft
```

不要默认输出到系统盘。

## 13. 训练完成后要做什么

训练完成后立刻做三件事：

1. 保存日志
2. 打包 checkpoint / adapter
3. 备份到本地或远端

例如：

```bash
tar -czf /hy-tmp/outputs/run-artifacts.tar.gz /hy-tmp/outputs/<your_run_dir>
```

再下载回本地：

```bash
scp -P <端口> root@<主机>:/hy-tmp/outputs/run-artifacts.tar.gz .
```

因为 `/hy-tmp` 不是长期可靠存储，实例长期关机或策略变化都可能导致数据丢失。

## 14. 这一阶段最推荐的工作方式

推荐你按这个顺序做：

1. 登录机器
2. 检查 GPU / 磁盘
3. 在 `/hy-tmp` 放仓库
4. 配置 cache 到 `/hy-tmp`
5. 安装 `tmux`
6. 安装项目环境
7. 安装 LLaMA-Factory
8. 链接数据到 `LLaMA-Factory/data`
9. 先跑 smoke test
10. 再跑第一轮真实 SFT
11. 训练完立即打包备份

## 15. 当前项目可直接使用的数据

训练主文件：

- [sft_train_final.jsonl](/home/sytssmys/llm-lab/data/sft_train_final.jsonl)
- [sft_train_final.json](/home/sytssmys/llm-lab/data/sft_train_final.json)

LLaMA-Factory 文件：

- [diagnosis_sft_alpaca.json](/home/sytssmys/llm-lab/data/llamafactory/diagnosis_sft_alpaca.json)
- [dataset_info.json](/home/sytssmys/llm-lab/data/llamafactory/dataset_info.json)

数据构建说明：

- [data-construction-log.md](/home/sytssmys/llm-lab/docs/data-construction-log.md)

## 16. 一句话总结

进入恒源云之后，正确的工作方式不是“直接在 root 目录里开训”，而是：

**把代码、模型、缓存、checkpoint 全部组织到 `/hy-tmp`，先用 5060 Ti 跑通流程和第一轮训练，再把 4090 留给正式实验。**
