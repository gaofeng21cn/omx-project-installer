# FAQ

## 1. 这个 baseline 到底会做什么？

它会把目标项目收束成统一结构：

- 根 `AGENTS.md`
- `contracts/dev-hosts/`
- `contracts/project-truth/AGENTS.md`
- `.omx/local/AGENTS.local.md` 约定

并在项目级安装后自动做：

- 系统级 `~/.codex/config.toml` 中 `model_provider`、`model`、`model_reasoning_effort`、`[model_providers.*]` 回灌到项目级 `.codex/config.toml`
- legacy alias 修复：`analyze`、`build-fix`、`tdd`、`ecomode`、`ultraqa`、`swarm`
- baseline metadata 落盘：`.agent-contract-baseline.json`

## 2. 它会替代 `omx setup` 吗？

不会。

它的定位是：

`omx setup -> post-setup reconcile`

也就是：

- OMX 负责生成项目级骨架
- baseline 安装器负责把合同分层、配置继承和兼容修复补齐

## 3. 它会把系统级 API key / token 复制到项目级吗？

会。

这是有意为之，因为项目级 `.codex/config.toml` 需要与系统级 provider/model/reasoning 真相保持一致。

因此 baseline 也会同时确保项目根 `.gitignore` 至少包含：

- `.omx/`
- `.codex/`

这样项目级 `.codex/config.toml` 不会进入版本库。

## 4. 我需要区分 `runtime-service` 和 `project-native` 吗？

不需要。

现在 baseline 已经统一成单一 `project-truth` 结构，不再要求用户先做项目分类。

项目差异只体现在：

- `contracts/project-truth/AGENTS.md` 的内容

而不体现在安装模式上。

## 5. 如果我之后又手动跑了 `omx setup --force` 怎么办？

直接在项目目录里重新让 Codex 执行：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

或者直接运行：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
```

## 6. baseline 如何判断项目该放哪种合同？

它现在不判断类型。

所有项目统一收束到：

- `contracts/project-truth/AGENTS.md`

如果旧项目之前已经在用：

- `contracts/*-runtime-service/AGENTS.md`
- `contracts/*-repository/AGENTS.md`

安装器会在 `reconcile / upgrade` 时迁移到新的统一路径。

## 7. 给别人 Codex 的最短 prompt 是什么？

如果对方还没装 skill：

```text
请安装并使用 https://github.com/gaofeng21cn/agent-contract-baseline ，然后在当前项目目录使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

如果对方已经装过 skill：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```
