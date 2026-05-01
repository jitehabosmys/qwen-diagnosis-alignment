# 4090 首次环境配置清单

这份文档面向当前项目在 `RTX 4090 24GB` 新机器上的首次落地。

它不是通用教程，而是当前仓库的实际执行清单，目标是：

1. 把 `llm-lab`、`LLaMA-Factory`、`vLLM` 三套环境落到同一台机器上
2. 用最少额外迁移成本，先复现一遍 `4B strict` 全流程作为 smoke + baseline
3. 为后续更大模型 `QLoRA` 和正式 `DPO` 做准备

相关旧文档：

- [gpushare-training-workflow.md](/hy-tmp/llm-lab/docs/5060ti/gpushare-training-workflow.md)
- [gpu-strategy-5060ti-vs-4090.md](/hy-tmp/llm-lab/docs/5060ti/gpu-strategy-5060ti-vs-4090.md)
- [2026-05-01-project-status-before-4090.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-project-status-before-4090.md)

当前 4090 首轮 baseline 复现记录：

- [2026-05-01-qwen3-4b-strict-repro-on-4090.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-4b-strict-repro-on-4090.md)
- [2026-05-01-qwen3-8b-qlora-sft-log.md](/hy-tmp/llm-lab/docs/4090/2026-05-01-qwen3-8b-qlora-sft-log.md)

## 1. 当前阶段的明确策略

先把项目策略固定下来，避免环境搭好了但路线又摇摆：

- `llm-lab` 仓库和 `LLaMA-Factory` 一律走 `SSH clone`
- 所有大文件统一放 `/hy-tmp`
- 不迁移旧机器上的 `models/`、`outputs/`
- 小模型 `0.5B / 3B / 4B` 不再作为迁移对象，只在 4090 上按需重跑
- 第一轮 4090 baseline 建议直接复现一次 `Qwen3-4B strict LoRA` 全流程
- 后续主线重点转向：
  - 更大模型的 `QLoRA`
  - 何时进入正式 `DPO`

这里有一个重要现实判断：

- 旧机器上的历史结果已经在 `docs/` 中沉淀完毕
- 现在迁移的重点不是“把旧产物搬过来”
- 而是“把 4090 训练基础设施搭完整，并快速进入下一阶段主实验”

## 2. 首次登录后的第一轮检查

先不要急着 clone 或装包，先确认机器状态：

```bash
whoami
uname -a
nvidia-smi
df -h
free -h
python3 --version
git --version
```

重点确认：

- GPU 可见且驱动正常
- `/hy-tmp` 存在且空间充足
- 系统盘没有接近打满
- 当前 shell 环境正常

## 3. 先装基础工具

建议先补齐这些常用工具：

```bash
apt-get update
apt-get install -y git git-lfs tmux htop jq tree build-essential gcc g++ make curl
git lfs install
```

建议同时准备一个长期训练用 `tmux`：

```bash
tmux new -s train
```

后续重连：

```bash
tmux attach -t train
```

## 4. 统一目录布局

建议统一成下面这套目录：

```bash
mkdir -p /hy-tmp/.cache
mkdir -p /hy-tmp/models
mkdir -p /hy-tmp/outputs
mkdir -p /hy-tmp/logs
mkdir -p /hy-tmp/src
```

推荐最终布局：

- `/hy-tmp/llm-lab`
- `/hy-tmp/LLaMA-Factory`
- `/hy-tmp/vllm-venv`
- `/hy-tmp/models`
- `/hy-tmp/outputs`
- `/hy-tmp/.cache`

## 5. 先把缓存重定向到 `/hy-tmp`

这一步最好在第一次大下载前完成。

把下面内容写入 `~/.bashrc`：

```bash
cat >> ~/.bashrc <<'EOF'
export HF_HOME=/hy-tmp/.cache/huggingface
export TRANSFORMERS_CACHE=/hy-tmp/.cache/huggingface/transformers
export HUGGINGFACE_HUB_CACHE=/hy-tmp/.cache/huggingface/hub
export TORCH_HOME=/hy-tmp/.cache/torch
export XDG_CACHE_HOME=/hy-tmp/.cache
export PIP_CACHE_DIR=/hy-tmp/.cache/pip
export UV_CACHE_DIR=/hy-tmp/.cache/uv
EOF

source ~/.bashrc
```

可额外检查：

```bash
env | grep -E 'HF_HOME|TRANSFORMERS_CACHE|HUGGINGFACE_HUB_CACHE|TORCH_HOME|XDG_CACHE_HOME|PIP_CACHE_DIR|UV_CACHE_DIR'
```

## 6. SSH 访问 GitHub

因为后续 `pull` / `push` 都要走同一路径，所以这里直接定死用 SSH，不再用 HTTP。

先确认这台机器上的 SSH key 已经加到 GitHub 账号：

```bash
ls -la ~/.ssh
ssh -T git@github.com
```

如果第一次连 GitHub，接受 host key 即可。

当前仓库远程地址已经是：

```text
git@github.com:jitehabosmys/llm-lab.git
```

## 7. Clone 仓库

如果这台机器还没 clone：

```bash
cd /hy-tmp
git clone git@github.com:jitehabosmys/llm-lab.git
git clone git@github.com:hiyouga/LLaMA-Factory.git
```

如果 `llm-lab` 已经在机器上，只需补 `LLaMA-Factory`：

```bash
cd /hy-tmp
git clone git@github.com:hiyouga/LLaMA-Factory.git
```

检查：

```bash
cd /hy-tmp/llm-lab && git remote -v
cd /hy-tmp/LLaMA-Factory && git remote -v
```

## 8. 安装 `uv`

如果机器上还没有 `uv`，先装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

如果你的 shell 还没重新加载成功，也可以临时执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

## 9. `llm-lab` 环境

这套环境主要负责：

- 数据处理脚本
- 推理评测脚本
- pairwise judge
- 文档和实验组织

进入项目目录：

```bash
cd /hy-tmp/llm-lab
```

如果机器上已经有 `uv`，直接：

```bash
uv sync
source .venv/bin/activate
```

检查：

```bash
python -V
python -c "import openai, anthropic; print('llm-lab env ok')"
```

如果后面要跑 pairwise judge，建议提前准备：

- `OPENAI_API_KEY`
- 可选 `OPENAI_BASE_URL`
- 可选 `OPENAI_JUDGE_MODEL`

可以参考：

- [.env.example](/hy-tmp/llm-lab/.env.example)

## 9. `LLaMA-Factory` 环境

这套环境负责训练、HF 推理和自动评测。

当前官方安装文档的最小主线是：

- clone 仓库
- `pip install -e .`
- `pip install -r requirements/metrics.txt`

在这台机器上，建议仍然用单独虚拟环境承载，但安装步骤跟官方主线保持一致。

```bash
cd /hy-tmp/LLaMA-Factory
uv venv --python 3.12 --seed
source .venv/bin/activate
pip install -e .
pip install -r requirements/metrics.txt
```

建议再补这几个当前项目高频依赖：

```bash
pip install wandb modelscope
```

验证：

```bash
llamafactory-cli version
python -c "import torch; print(torch.__version__)"
```

关于 `QLoRA`：

- `4B` 的基线复现先用当前已有 `LoRA` 配置即可
- 真正切到更大模型 `QLoRA` 前，再确认环境里已有量化依赖
- 如果首个 `QLoRA` 训练报缺少量化依赖，再补 `bitsandbytes`

## 10. `vLLM` 独立环境

不要把 `vLLM` 跟 `LLaMA-Factory` 混装在同一个环境里。

建议单独建：

```bash
cd /hy-tmp
uv venv --python 3.12 --seed /hy-tmp/vllm-venv
source /hy-tmp/vllm-venv/bin/activate
pip install -U pip
pip install vllm
```

验证：

```bash
python -c "import vllm; print(vllm.__version__)"
vllm --help
```

后面如果你只开服务，不在这个环境里写客户端代码，这套环境里不必再装项目脚本依赖。

## 11. 模型目录策略

这里不要再依赖“历史机器上已经缓存好了什么”。

建议从 4090 开始，把**当前仍会用到的基座模型**放成稳定路径：

- `/hy-tmp/models/Qwen/Qwen3-4B-Instruct-2507`
- 后续更大的 `7B / 8B / 14B` 也按同样层级放

为什么要用稳定路径：

- 当前多个 HF 推理配置直接引用本地目录
- `vLLM` 服务也更适合直接指向一个明确模型目录
- 这样训练、HF 推理、vLLM 三条链路都能复用同一份基座

注意两件事：

1. `cache_dir=/hy-tmp/models` 只表示缓存放这里，不等于模型一定会落成你想要的稳定目录
2. 如果你只让训练过程临时下载到 cache，后面 `HF infer` 和 `vLLM` 仍可能找不到你配置里写死的本地路径

所以更稳的做法是：

- 要么一开始就把模型下载到稳定本地目录
- 要么第一次下载完成后，补一个稳定软链接，再让推理配置指向它

如果当前 `huggingface.co` 连通性差：

- `LLaMA-Factory` 侧可先导出 `USE_MODELSCOPE_HUB=1`
- `vLLM` 侧可先导出 `VLLM_USE_MODELSCOPE=True`

## 12. 当前数据状态

当前仓库已经带着这批数据视图，不需要从旧机器迁移：

- `data/llamafactory/diagnosis_sft_strict_json_prompt_smoke_alpaca.json`
- `data/llamafactory/diagnosis_sft_strict_json_prompt_train_alpaca.json`
- `data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json`
- `data/llamafactory/dataset_info.json`

这意味着：

- 4090 上可以直接复现 `4B strict` 基线
- 不需要先回头搬 `0.5B / 3B / 4B` 的历史输出目录

## 13. 第一轮 baseline：先复现 `4B strict LoRA`

当前最实用的首轮目标不是立刻上更大模型，而是：

1. 先证明 4090 上训练、HF 推理、自动评测、vLLM smoke 都通
2. 把这台机器变成一个稳定的主实验平台
3. 产出后续 `QLoRA` 和 `DPO` 的对照基线

### 13.1 为什么先复现 `4B`

原因很简单：

- 当前仓库已经有现成训练配置
- 当前仓库已经有对应 HF 推理配置
- 当前仓库已经有对应 vLLM 对比脚本
- `4B strict` 已经被证明是一个有效 baseline

### 13.2 先跑 smoke

当前仓库已有配置：

- [5090ti_qwen3_4b_smoke_lora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_smoke_lora_sft_strict_json_prompt.yaml)

先直接复用它。这里的 `5090ti` 只是文件名，不是功能依赖。

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train \
  /hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_smoke_lora_sft_strict_json_prompt.yaml
```

验收点：

- 能启动
- 不 OOM
- 数据能读
- checkpoint 能落盘
- loss 正常

### 13.3 再跑 full

配置：

- [5090ti_qwen3_4b_full_lora_sft_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_full_lora_sft_strict_json_prompt.yaml)

命令：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train \
  /hy-tmp/llm-lab/configs/llamafactory/5090ti_qwen3_4b_full_lora_sft_strict_json_prompt.yaml
```

如果你暂时不想改任何 HF 推理配置，第一轮可以继续沿用现有输出目录命名。

如果你想从第一天起就把名字改成 `4090`，也可以，但要同步修改后续 infer 配置里的 adapter 路径。

## 14. 训练后先走 HF 主评测链

当前正式主评测链仍然是 HF，不是 `vLLM`。

第一步先跑小样本：

```bash
cd /hy-tmp/LLaMA-Factory
source .venv/bin/activate
export USE_MODELSCOPE_HUB=1
python /hy-tmp/llm-lab/scripts/run_inference_eval.py \
  --matrix qwen3_4b_strict_json_prompt \
  --max-samples 10
```

跑通后再跑完整 `48` 条：

```bash
python /hy-tmp/llm-lab/scripts/run_inference_eval.py \
  --matrix qwen3_4b_strict_json_prompt \
  --max-samples 48
```

关注：

- `json_parse_success`
- `schema_valid`
- `response_length_avg`
- `elapsed_seconds_avg`

参考：

- [inference-eval-workflow.md](/hy-tmp/llm-lab/docs/5060ti/inference-eval-workflow.md)

## 15. 再做 `vLLM` smoke，不替代主链

当前 `vLLM` 的定位仍然是：

- 候选加速 backend
- 独立基础设施验证对象
- 不是当前主评测 backend

先起一个 `4B strict LoRA` 服务：

```bash
source /hy-tmp/vllm-venv/bin/activate
export VLLM_USE_MODELSCOPE=True
vllm serve /hy-tmp/models/Qwen/Qwen3-4B-Instruct-2507 \
  --served-model-name qwen3-4b-strict-lora-vllm \
  --enable-lora \
  --lora-modules strict4b=/hy-tmp/outputs/llamafactory/qwen3-4b-full-lora-sft-strict-json-prompt-5090ti \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.9 \
  --host 0.0.0.0 \
  --port 8001
```

另开一个 shell，在 `llm-lab` 环境里做最小对比：

```bash
cd /hy-tmp/llm-lab
source .venv/bin/activate
python scripts/run_hf_vs_vllm_compare.py \
  --hf-config /hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml \
  --vllm-model qwen3-4b-strict-lora-vllm \
  --vllm-base-url http://127.0.0.1:8001/v1 \
  --eval-data /hy-tmp/llm-lab/data/llamafactory/diagnosis_sft_strict_json_prompt_eval_alpaca.json \
  --max-samples 5
```

参考：

- [2026-05-01-vllm-smoke-plan.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-vllm-smoke-plan.md)
- [2026-05-01-hf-vs-vllm-observations.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-hf-vs-vllm-observations.md)

## 16. 4090 上的正式主线：更大模型 `QLoRA`

`4B strict` baseline 跑通后，下一步才应该切到真正的主任务：

### 16.1 目标

- 在 4090 上尝试更大的模型规模
- 优先看 `strict_json_prompt` 主线下的真实收益
- 判断 scale up 到什么位置开始边际变小

### 16.2 执行顺序

建议顺序：

1. 先补第一版更大模型 `QLoRA` 配置
2. 先跑 smoke
3. 再跑 full SFT
4. 跑 HF 自动评测
5. 跑 pairwise judge，与 `4B strict baseline` 比较
6. 再决定是否继续 scale up

### 16.3 当前仓库里还没有的东西

当前仓库已经有：

- `SFT` 数据
- `4B` 基线配置
- 自动评测脚本
- pairwise judge 脚本

但**还没有**为 4090 上更大模型准备好的内容包括：

- 新的 `7B / 8B / 14B` `QLoRA` 训练配置
- 与之配套的 HF 推理配置
- 与之配套的 `vLLM` 服务配置

所以 `4B baseline` 跑通之后，下一步最值得做的不是搬旧结果，而是补这组三件套。

## 17. 什么时候考虑正式 `DPO`

当前不建议上 4090 后立刻开始 `DPO`。

更稳的门槛仍然是：

1. 更大模型 `QLoRA SFT` 已稳定跑通
2. 自动规则评测优于 `4B strict baseline`
3. pairwise judge 也显示内容质量提升
4. 当前瓶颈已经主要变成“偏好质量”，而不是“基础能力不够”

也就是说，正确顺序仍然是：

`更大模型 QLoRA SFT -> HF 评测 -> pairwise judge -> DPO 决策`

而不是：

`环境刚搭好 -> 直接 DPO`

## 18. DPO 前的现实准备项

当前仓库已经有 DPO 候选采集链路：

- `run_pairwise_judge.py` 会产出：
  - `dpo_pairs.jsonl`
  - `dpo_pairs_high_confidence.jsonl`

参考：

- [pairwise-judge-workflow.md](/hy-tmp/llm-lab/docs/5060ti/pairwise-judge-workflow.md)

但目前还要注意两点：

1. 这台 4090 上还没有新的大模型输出，因此也还没有新的高质量 DPO 候选池
2. 当前仓库里还没有现成的大模型 `DPO` 训练配置文件

所以进入正式 `DPO` 之前，至少还要补：

- 一个明确的 `DPO` 数据目录约定
- 一份 4090 主线模型的 `DPO` YAML 配置
- 一套和 `SFT baseline` 对照的评测命令

## 19. 建议的首日执行顺序

如果只看“今天该怎么做”，建议按这个顺序：

1. 检查 GPU、磁盘、系统基础状态
2. 安装基础工具和 `tmux`
3. 配置 `/hy-tmp` 缓存环境变量
4. 验证 GitHub SSH
5. clone `LLaMA-Factory`
6. 准备 `llm-lab` 环境
7. 准备 `LLaMA-Factory` 环境
8. 准备 `vLLM` 环境
9. 准备 `Qwen3-4B-Instruct-2507` 的稳定本地目录
10. 运行 `4B strict smoke`
11. 运行 `4B strict full`
12. 跑 HF 小样本评测
13. 跑 `vLLM` 小样本 smoke
14. 复盘后，再进入更大模型 `QLoRA`

## 20. 一句话版

4090 这台机器的正确打开方式不是“把旧机器所有结果搬过来”，而是：

**先用 SSH + `/hy-tmp` + 独立的 `llm-lab` / `LLaMA-Factory` / `vLLM` 环境把平台搭稳，再用 `4B strict` 复现一遍完整链路作为 baseline，随后立刻把主线切到更大模型 `QLoRA`，最后再决定何时上正式 `DPO`。**
