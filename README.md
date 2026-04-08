# OMX Project Installer

`omx-project-installer` 是一个兼容性感知的 OMX project-scope 安装器。它的职责是在 upstream 的 project-scope 刷新仍可能直接改写关键项目文件时，让 OMX 安装进具体项目目录而不破坏项目自己的根 `AGENTS.md`、Codex App 体验和系统级模型配置。

> **Quick Start**
>
> 1. 安装工具仓库：
>
> ```bash
> git clone https://github.com/gaofeng21cn/omx-project-installer.git
> cd omx-project-installer
> ./install.sh
> ```
>
> 2. 在目标项目目录里直接对 Codex 说：
>
> ```text
> 请安装并使用 https://github.com/gaofeng21cn/omx-project-installer ，然后在当前项目目录使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
> ```
>
> 3. 常见问题见：
> [`docs/faq.md`](docs/faq.md)

目标不是替代 `omx setup`，而是补上它当前没有提供的整合层：

- 将项目根 `AGENTS.md` 从单体文件收束成“App-native 根入口 + `.codex/AGENTS.md` OMX 编排层 + project-truth 合同 + 本机 overlay”
- 在项目级安装后，把系统级 `~/.codex/config.toml` 中的 provider / model / reasoning 连接真相回灌到项目级 `.codex/config.toml`
- 为 project-scope 更新提供受控刷新机制，避免粗暴覆盖根 `AGENTS.md` 与项目级 `.codex/config.toml`
- 为 `Codex App + OMX` 种下稳定的 `.omx/context + .omx/plans + .omx/reports` 规划路由面
- 在需要时为特定领域种下可选的 `program pack`
- 记录 baseline 版本与受管文件，支持后续 `diff / upgrade / reconcile`

## 核心模型

每个目标项目被拆成四层：

1. 项目根入口合同：根 `AGENTS.md`
2. 项目真相合同：`contracts/project-truth/AGENTS.md`
3. OMX project-scope 编排层：`.codex/AGENTS.md`
4. 本机私有 overlay：`.omx/local/AGENTS.local.md`

项目差异不再体现在安装模式上，而体现在 `contracts/project-truth/AGENTS.md` 的具体内容里。
例如：

- `redcube-ai` 的 project-truth 更偏向 runtime/service 真相
- `med-autoscience` 的 project-truth 更偏向 repository-native 平台真相

## 仓库结构

- `baseline.manifest.json`
  - 基线版本、受管文件、统一 project-truth 路径、config 继承规则、受控更新策略、program pack 注册表
- `templates/`
  - 根 `AGENTS.md` / `.codex/AGENTS.md` / project-truth 模板 / `.omx` continuous scaffold / 可选 program pack 模板
- `examples/`
  - 从现有项目抽出的参考快照
- `skills/omx-project-installer/`
  - 兼容性感知的 OMX 项目安装器 skill

## 安装器职责

`omx-project-installer` 的默认职责是：

1. 在目标项目下运行 `omx setup --scope project`
2. 备份已有根 `AGENTS.md`
3. 落项目根入口、`.codex/AGENTS.md` OMX 编排层与 `contracts/project-truth/AGENTS.md`
4. 保护根 `AGENTS.md` 的 App-native 入口分层，不接受 upstream 单体模板直接落根
5. 保护项目级 `.codex/config.toml`：如果 refresh 期间执行了 `omx setup`，先恢复 pre-setup 快照，再把 OMX 受管配置从最新 setup 输出精确并回，同时严格回灌系统级 provider / model / reasoning
6. 在项目级 `.codex/skills/` 修复 legacy alias 兼容面，补齐 `analyze`、`build-fix`、`tdd`、`ecomode`、`ultraqa`、`swarm`
7. 种下 `.omx/context + .omx/plans + .omx/reports` continuous planning scaffold
8. 可选地种下 `program pack`
9. 写入 `.agent-contract-baseline.json`

默认 continuous planning scaffold 至少包含：

- `.omx/context/CURRENT_PROGRAM.md`
- `.omx/context/PROGRAM_ROUTING.md`
- `.omx/context/OMX_TEAM_PROMPT.md`
- `.omx/plans/spec-*.md`
- `.omx/plans/prd-*.md`
- `.omx/plans/test-spec-*.md`
- `.omx/plans/implementation-*.md`
- `.omx/reports/<program-id>/README.md`
- `.omx/reports/<program-id>/LATEST_STATUS.md`
- `.omx/reports/<program-id>/ITERATION_LOG.md`
- `.omx/reports/<program-id>/OPEN_ISSUES.md`

其中 `PROGRAM_ROUTING.md` 的职责很具体：

- 告诉 `Codex App` 进入项目后，当前应该先读哪些 `.omx` 文档
- 告诉 `OMX` 长期 roadmap、PRD、test-spec、implementation、reports 分别应该写到哪里
- 把“长期规划写作约定”从一次性聊天提示词，收束成项目内固定控制面

如果项目需要一上来就具备某类长期主线骨架，可以安装 optional `program pack`。当前首个 pack 是：

- `medical_research_foundry_delivery_closeout`
  - 面向 `Research Foundry` 的医学交付主线
  - 为 delivery/publication plane closeout 提供 long-horizon context、autopilot prompt、roadmap、PRD、test spec

公开 README 不属于 baseline 受管面，其语言、叙事和对外说明必须由目标项目自行维护。

## 与 OMX 当前行为的兼容关系

当前 `omx setup` 的关键限制：

- 它会更新项目级 `.codex/config.toml`
- 它会生成项目根 `AGENTS.md`
- 它没有“整合已有 AGENTS.md”的模式
- 它不会自动把系统级 provider / model / reasoning 配置重新压回项目级 config
- 它对项目级 `.codex/config.toml` 没有“只更新受管字段”的模式

因此本仓库采用：

`omx setup -> post-setup reconcile`

也就是：

- OMX 负责生成 project-scope 本地骨架
- baseline 安装器负责把项目根 `AGENTS.md` 恢复为 App-native 入口、把 OMX 编排层落到 `.codex/AGENTS.md`、恢复项目真相层，并把系统级模型配置重新压回项目级
- 如果通过 installer 触发 upstream refresh，baseline 会先恢复 pre-setup 的项目 config，再只把 OMX 受管字段从 setup 输出精确并回，随后对系统级 provider / model / reasoning 应用严格继承，避免把整份 `.codex/config.toml` 当缓存整体替换
- baseline 安装器不托管公开 README，也不会根据固定模板改写 README 的语言或公开叙事

## 受控更新入口

如果你只是想刷新 OMX 到当前项目，不要直接运行裸 `omx setup --scope project`。

推荐入口：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
```

如果确实需要先拉一遍 upstream setup，再收口：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo --run-omx-setup
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo --run-omx-setup
```

这个“受控刷新”模式会做三件事：

1. 让 upstream `omx setup` 刷新 prompts / skills / native agents / managed config 骨架
2. 把根 `AGENTS.md` 收回 installer 的 App-native 根入口模板
3. 把 pre-setup 项目 config 恢复回来，把 OMX 受管字段精确并回，再对系统级 provider / model / reasoning 做严格继承

默认策略现在是：

- `--root-agents-policy auto`
- `--project-config-policy auto`

如果你要显式改策略，也可以覆盖：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile \
  --target /abs/path/to/repo \
  --run-omx-setup \
  --root-agents-policy template \
  --project-config-policy setup-output
```

## 当前状态

第一批 examples 来自：

- `redcube-ai`
- `med-autoscience`

这两个项目是当前 installer 设计的种子样本，而不是模板本身。

## 一键安装

在新机器上：

```bash
git clone https://github.com/gaofeng21cn/omx-project-installer.git
cd omx-project-installer
./install.sh
```

如果你更喜欢 Python：

```bash
python install.py
```

安装完成后，在目标项目目录里直接对 Codex 说：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

如果你要同时种下长期 planning pack，可以直接运行：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py install \
  --target /abs/path/to/repo \
  --program-pack medical_research_foundry_delivery_closeout
```

## 给 Codex 的快速开始指令

如果你是要把一条指令直接转发给别人的 Codex，推荐使用下面这句：

```text
请安装并使用 https://github.com/gaofeng21cn/omx-project-installer ，然后在当前项目目录使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

如果对方已经装过这个 skill，更短的版本就是：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

## FAQ

- 常见问题与行为边界：
  [`docs/faq.md`](docs/faq.md)

## 定位说明

对外你只需要安装并使用一个 skill：

- `$omx-project-installer`

模板、examples、测试、FAQ 和安装脚本都只是这个 skill 的实现与验证资产。

它可以被别的仓库索引或引用，但源码真相源继续保留在这个独立仓库中。
