# 2026-05-01 vLLM Smoke 与 HF 对比计划

这份文档描述的是当前项目在 `4B strict lora` 路线上引入 `vLLM` 的最小验证计划。

当前结论不是“马上切换主链路”，而是：

- 先验证 `vLLM` 是否可用
- 再验证它是否足够快
- 再判断输出行为和 `HF` 是否一致到可以迁移主评测链

## 1. 为什么现在适合做 vLLM

到 `3B/4B` 阶段后，当前 `HF` 推理链路的瓶颈已经很明显：

- 单样本串行生成耗时较高
- 大规模自动评测越来越慢
- 后续如果要继续做 judge / 偏好对收集，推理成本会成为实验效率瓶颈

因此，现在引入 `vLLM` 不是为了替换模型比较结论，而是为了验证：

- 是否有更高吞吐的推理基础设施可用

## 2. 当前策略

当前策略是：

- 保留 `HF` 作为主评测链路
- 把 `vLLM` 当作独立的基础设施 smoke
- 先做小样本 `HF vs vLLM` 对比，不立刻替换全量实验

## 3. 相关配置

严格版 `HF` 推理配置：

- [qwen3_4b_base_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_hf_infer_strict_json_prompt.yaml)
- [qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_hf_infer_strict_json_prompt.yaml)

对应的 `vLLM` 推理配置：

- [qwen3_4b_base_vllm_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_base_vllm_infer_strict_json_prompt.yaml)
- [qwen3_4b_full_lora_vllm_infer_strict_json_prompt.yaml](/hy-tmp/llm-lab/configs/llamafactory/qwen3_4b_full_lora_vllm_infer_strict_json_prompt.yaml)

## 4. 建议验证顺序

### 第一步：`4B strict base` 最小 smoke

目标：

- 服务能否正常启动
- 返回是否为合法 JSON
- 是否存在明显异常偏移

### 第二步：`4B strict lora` 最小 smoke

目标：

- LoRA 是否能在 vLLM 下正常加载
- strict 路线下对齐效果是否明显退化

### 第三步：`HF vs vLLM` 小样本对比

建议先用 `5~10` 条样本，比较：

- `json_parse_success`
- `schema_valid`
- `response_length`
- 推理耗时

## 5. 关注指标

在 `HF vs vLLM` 小样本对比里，优先看：

1. 输出行为是否一致或近似一致
2. schema 是否明显退化
3. 生成长度是否大幅变化
4. 单样本耗时是否显著下降

## 6. 当前原则

在 `vLLM` 还没有完成小样本一致性验证之前：

- 不替换现有 `HF` 主评测链路
- 不把不同 backend 的结果混合到同一轮模型比较结论里

## 7. 一句话结论

当前 `vLLM` 的正确定位是：

**独立的推理基础设施验证实验，而不是立即替换现有 HF 主评测链路。**

当前首轮小样本观察记录见：

- [2026-05-01-hf-vs-vllm-observations.md](/hy-tmp/llm-lab/docs/5060ti/2026-05-01-hf-vs-vllm-observations.md)
