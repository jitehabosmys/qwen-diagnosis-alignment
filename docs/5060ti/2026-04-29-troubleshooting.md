# 2026-04-29 GPU 云服务器排障记录

这份文档记录的是在 `gpushare` 远程服务器上，为了跑通 `llm-lab` 的数据准备、`LLaMA-Factory` 训练和 Git 提交/推送，实际遇到的问题与处理方式。

写这份文档的目的不是罗列零散技巧，而是把今天踩过的坑整理成：

- 现象
- 根因
- 处理方法
- 后续建议

便于后面复盘，也便于下次快速定位。

## 1. GitHub Clone 拉取慢或超时

### 现象

在国内云服务器上直接执行：

```bash
git clone https://github.com/<user>/<repo>.git
```

经常会卡住、超时，或者速度非常慢。

### 临时处理

一种常见做法是给 URL 加代理前缀，例如：

```bash
git clone https://ghfast.top/https://github.com/<user>/<repo>.git
```

这样有时能加速 `clone` 或 `fetch`。

### 我们实际踩到的问题

为了省事，曾经配置过全局 URL 改写：

```bash
git config --global url."https://ghfast.top/https://github.com/".insteadOf "https://github.com/"
```

这条配置的副作用非常大：

- 它不只影响 `clone`
- 也会影响 `fetch`
- 还会影响 `push`

也就是说，只要 Git 看到 `https://github.com/...`，就会偷偷改写成：

```bash
https://ghfast.top/https://github.com/...
```

这在拉取时可能有帮助，但在推送时很容易出问题，因为第三方代理站通常不适合承接 GitHub 的写入认证链路。

### 建议

不要把这种 URL 改写作为长期全局配置。  
更稳妥的做法是：

- 只在 `clone` 时手动用代理 URL
- 或只把它当成临时方案
- 不要让它接管 `push`

如果已经配过这条全局规则，建议删除：

```bash
git config --global --unset url."https://ghfast.top/https://github.com/".insteadOf
```

然后检查是否还存在类似规则：

```bash
git config --global --get-regexp '^url\..*insteadof$'
```

## 2. `git commit` 报 `Author identity unknown`

### 现象

执行 `git commit` 时，Git 报错：

```text
Author identity unknown
fatal: unable to auto-detect email address
```

### 根因

这不是网络问题，也不是仓库权限问题。  
它只说明：

- 当前机器或当前仓库还没有配置提交作者信息

Git 不知道这次 commit 要写成谁提交的。

### 处理方法

可以只在当前仓库设置：

```bash
git config user.name "jitehabosmys"
git config user.email "2524532849@qq.com"
```

如果希望这台机器全局生效，也可以加 `--global`。

### 注意

`user.name` 和 `user.email` 只影响：

- `git commit`

它们**不影响**：

- `git push` 的远程写权限认证

这个区别非常重要，后面遇到 `push` 问题时不要混淆。

## 3. `git push` 先超时，后 401

### 现象

同一个 `git push origin main`，前后出现过两类不同报错：

第一类：

```text
Failed to connect to github.com port 443 ... Connection timed out
```

第二类：

```text
Missing or invalid credentials.
401
```

而且报错里还出现了：

```text
.../extensions/git/dist/askpass-main.js
```

### 根因

这不是“问题变了”，而是同一条链路先后暴露出了两层问题：

1. 第一次超时：请求连 GitHub 都没连上，死在网络层。
2. 第二次 401：这次请求连上了 GitHub，但在 HTTPS 认证阶段失败了。

也就是说，第二次并不是新的根因，而是：

- 网络偶尔通了
- 随后进入鉴权阶段
- 但凭证不正确或没有正确传递

### 关于 `askpass`

日志里出现 `askpass-main.js`，说明当前终端环境下：

- Git 的 HTTPS 凭证输入不是纯终端模式
- 而是被 Cursor/VS Code 的 Git 扩展接管了

这在远程服务器上不一定稳定，常见问题包括：

- 凭证没有保存
- 凭证为空
- askpass 传了错误 token
- 代理、编辑器和 Git 的认证链路互相干扰

### 结论

遇到“第一次超时，第二次 401”，应该理解成：

- 第一次卡在网络层
- 第二次走到了认证层

不是矛盾，而是第二次比第一次走得更远。

## 4. HTTPS 推送为什么不稳定

### 现象

远端是标准 GitHub HTTPS：

```bash
https://github.com/jitehabosmys/llm-lab.git
```

但在云服务器上推送经常遇到：

- 443 超时
- askpass 凭证错误
- 401

### 根因

云服务器到 `github.com:443` 的链路本身就可能不稳定。  
即使偶尔连上，HTTPS 还需要：

- 用户名
- GitHub PAT
- 凭证 helper 或 askpass 正常工作

这比 SSH 链路更复杂。

### 结论

如果已经在远程机器上长期开发，并且确实需要反复 `push`，优先改用 SSH，而不是继续和 HTTPS + PAT + askpass 的组合缠斗。

## 5. GitHub Push 从 HTTPS 切换到 SSH

### 适用场景

已经在服务器上生成了 SSH 公钥，并且把公钥添加到了 GitHub 账户里。

### 处理步骤

先把远端从 HTTPS 改成 SSH：

```bash
git remote set-url origin git@github.com:jitehabosmys/llm-lab.git
```

然后确认：

```bash
git remote -v
```

应该看到：

```text
origin  git@github.com:jitehabosmys/llm-lab.git (fetch)
origin  git@github.com:jitehabosmys/llm-lab.git (push)
```

接着测试连通性：

```bash
ssh -T git@github.com
```

第一次通常会提示确认 host key，输入：

```text
yes
```

如果返回类似：

```text
Hi jitehabosmys! You've successfully authenticated...
```

说明 SSH 认证已经打通。

然后再执行：

```bash
git push origin main
```

### 优点

SSH 方案的好处是：

- 不依赖 PAT
- 不依赖编辑器 askpass
- 更适合长期在远程服务器使用

## 6. 如果 GitHub SSH 22 端口不通

### 现象

有些云服务器到 GitHub 的 `22` 端口会被限制，导致：

```bash
ssh -T git@github.com
```

连接失败。

### 处理方法

可以改用 GitHub 的 SSH over 443。  
在 `~/.ssh/config` 中加入：

```sshconfig
Host github.com
  HostName ssh.github.com
  Port 443
  User git
```

然后再试：

```bash
ssh -T git@github.com
git push origin main
```

这样仍然是 SSH，只是从 22 端口切换到了 443 端口。

## 7. `uv` 依赖下载慢

### 现象

在云服务器上执行 `uv sync` 时，如果直接走默认 PyPI，依赖解析和下载可能很慢。

### 处理方法

本次项目采用了项目级 `uv.toml`：

```toml
index-url = "https://repo.huaweicloud.com/repository/pypi/simple"
offline = false
```

这类配置的优点是：

- 只影响当前项目
- 不污染系统全局 pip 配置
- `uv sync`、`uv add` 都能直接复用

### 备注

`uv` 不完全依赖传统 `pip.conf` 的行为，所以单独放一个项目级 `uv.toml` 是比较稳的办法。

## 8. Hugging Face 无法访问，导致 tokenizer 加载失败

### 现象

在 `LLaMA-Factory` 里启动训练时，出现：

```text
[Errno 101] Network is unreachable
Failed to load tokenizer.
OSError: Failed to load tokenizer.
```

并且日志里会看到它在请求：

```text
https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/...
```

### 根因

这类报错很多时候不是数据错了，也不是 YAML 写错了，而是：

- 当前服务器访问不了 `huggingface.co`
- 模型和 tokenizer 又还没有缓存到本地

所以训练在加载 tokenizer 阶段直接失败。

### 处理方法

这次实际使用的修复路径是改走 `ModelScope`。

如果 `LLaMA-Factory` 环境里已经安装了 `modelscope`，可以先导出：

```bash
export USE_MODELSCOPE_HUB=1
```

然后再执行训练命令。

此外，在配置里显式指定本地缓存目录也很有帮助，例如：

```yaml
cache_dir: /hy-tmp/models
```

### 结论

遇到这类错误时，不要先怀疑训练数据。  
应优先排查：

1. 当前是否能访问 Hugging Face
2. 本地是否已有模型缓存
3. 是否可以切换到 `ModelScope`

## 9. `LLaMA-Factory` 训练里 attention 实现的误判

### 现象

模型配置中能看到：

```text
layer_types: full_attention
```

容易让人误以为这次训练使用的是“full attention/eager attention”。

### 根因

这是两个不同层面的概念：

- `layer_types: full_attention` 描述的是模型结构
- 训练时实际采用哪种 attention 后端，要看运行时日志

### 正确判断方式

这次训练日志里明确写了：

```text
Using torch SDPA for faster training and inference.
```

因此应当判断为：

- 运行时 attention 后端是 `torch SDPA`
- 不是显式强制 `flash_attention_2`
- 也不能因为模型层类型写着 `full_attention`，就简单理解成训练时用了 eager/full attention

## 10. `smoke` 跑通不代表效果已经验证完成

### 现象

`smoke` 阶段 loss 能下降，checkpoint 能保存，很容易让人误以为任务已经验证完成。

### 正确认识

`smoke` 解决的是：

- 链路是否能跑通
- 数据能不能被读
- loss 会不会立刻炸
- checkpoint 能不能落盘

它不解决：

- 真实任务效果到底如何
- JSON 输出是否更稳定
- adapter 相比 base model 是否真的有提升

### 建议

顺序应当是：

1. 先 `smoke`
2. 再 full SFT
3. 再做推理验证

不要把 `smoke 成功` 误写成“效果验证成功”。

## 11. 当前最值得保留的经验

如果只保留几条最关键的结论，应该是下面这些：

1. `git config user.name/user.email` 只解决 commit 身份，不解决 push 权限。
2. GitHub URL 的全局 `insteadOf` 规则会影响 push，不应该长期粗暴使用。
3. `git push` 先超时后 401，通常是网络层和认证层先后暴露出来，不是两个互不相干的问题。
4. 在远程服务器上长期使用 GitHub，SSH 往往比 HTTPS + PAT + askpass 更稳。
5. Hugging Face 不通时，`LLaMA-Factory` 的 tokenizer 报错很多时候只是下载源问题，不是训练数据问题。
6. `smoke` 的价值是验证链路，不是验证最终效果。
