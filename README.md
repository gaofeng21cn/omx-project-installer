# Agent Contract Baseline

`agent-contract-baseline` 提供一套可复用的仓库级 Agent 合同基线，以及一个兼容性感知的 OMX 项目安装器 skill。

目标不是替代 `omx setup`，而是补上它当前没有提供的整合层：

- 将项目根 `AGENTS.md` 从单体文件收束成“薄入口 + 宿主适配层 + 项目真相合同 + 本机 overlay”
- 在项目级安装后，把系统级 `~/.codex/config.toml` 中的 provider / model / reasoning 连接真相回灌到项目级 `.codex/config.toml`
- 修复项目级安装后遗留的旧 skill alias 兼容问题
- 记录 baseline 版本与受管文件，支持后续 `diff / upgrade / reconcile`

## 核心模型

每个目标项目被拆成四层：

1. 仓库开发入口合同：根 `AGENTS.md`
2. 宿主适配层：`contracts/dev-hosts/`
3. 项目真相合同：由模式决定
4. 本机私有 overlay：`.omx/local/AGENTS.local.md`

这里的“项目真相合同”有两种模式：

- `runtime-service`
  - 适合像 `redcube-ai` 这种还要对外定义 runtime/service 语义的项目
- `project-native`
  - 适合像 `med-autoscience` 这种已经有很强项目原生仓库合同的项目

## 仓库结构

- `baseline.manifest.json`
  - 基线版本、模式、受管文件、config 继承规则、legacy alias 修复规则
- `templates/`
  - 通用模板
- `examples/`
  - 从现有项目抽出的参考快照
- `skills/omx-project-installer/`
  - 兼容性感知的 OMX 项目安装器 skill

## 安装器职责

`omx-project-installer` 的默认职责是：

1. 在目标项目下运行 `omx setup --scope project`
2. 备份已有根 `AGENTS.md`
3. 落通用根入口、宿主适配层、README 分层说明与项目合同 stub
4. 把系统级 provider / model / reasoning 配置回灌到项目级 `.codex/config.toml`
5. 修复 legacy skill alias
6. 写入 `.agent-contract-baseline.json`

## 与 OMX 当前行为的兼容关系

当前 `omx setup` 的关键限制：

- 它会更新项目级 `.codex/config.toml`
- 它会生成项目根 `AGENTS.md`
- 它没有“整合已有 AGENTS.md”的模式
- 它不会自动把系统级 provider / model / reasoning 配置重新压回项目级 config

因此本仓库采用：

`omx setup -> post-setup reconcile`

也就是：

- OMX 负责生成本地骨架
- baseline 安装器负责修复兼容性、恢复项目真相层，并把系统级模型配置重新压回项目级

## 当前状态

第一批 examples 来自：

- `redcube-ai`
- `med-autoscience`

这两个项目是 baseline 的种子样本，而不是模板本身。

## 一键安装

在新机器上：

```bash
git clone https://github.com/gaofeng21cn/agent-contract-baseline.git
cd agent-contract-baseline
./install.sh
```

如果你更喜欢 Python：

```bash
python install.py
```

安装完成后，在目标项目目录里直接对 Codex 说：

```text
使用 $omx-project-installer，把当前项目按 runtime-service 或 project-native 模式完成 OMX project-scope 安装与合同分层收口。
```
