# FAQ

本仓库的公开名字是 `omx-project-installer`。

它的核心职责是提供一个高兼容性的 OMX project-scope 安装器。

## 1. 这个 baseline 到底会做什么？

它会把目标项目收束成统一结构：

- 根 `AGENTS.md`
- `contracts/project-truth/AGENTS.md`
- `.codex/AGENTS.md`
- `.omx/local/AGENTS.local.md` 约定

并在项目级安装后自动做：

- 系统级 `~/.codex/config.toml` 中 `model_provider`、`model`、`model_reasoning_effort`、`[model_providers.*]` 回灌到项目级 `.codex/config.toml`
- 受控更新保护：优先恢复 pre-setup 快照或最近一次 `setup` backup，再对受管字段应用严格继承，而不是接受 upstream 对整个文件的粗暴覆盖
- legacy alias 修复：补齐 `analyze`、`build-fix`、`tdd`、`ecomode`、`ultraqa`、`swarm`
- continuous planning scaffold：
  - `.omx/context/CURRENT_PROGRAM.md`
  - `.omx/context/PROGRAM_ROUTING.md`
  - `.omx/context/OMX_TEAM_PROMPT.md`
  - `.omx/plans/spec-*.md`
  - `.omx/plans/prd-*.md`
  - `.omx/plans/test-spec-*.md`
  - `.omx/plans/implementation-*.md`
  - `.omx/reports/<program-id>/*`
- baseline metadata 落盘：`.agent-contract-baseline.json`

## 2. 它会替代 `omx setup` 吗？

不会。

它的定位是：

`omx setup -> post-setup reconcile`

也就是：

- OMX 负责生成 project-scope 骨架
- baseline 安装器负责把根 `AGENTS.md` 恢复成 App-native 入口，把 OMX 编排层放到 `.codex/AGENTS.md`，并把配置继承和兼容修复补齐
- baseline 安装器不托管公开 README；README 的语言、叙事和外部呈现由项目自己维护

当前推荐的受控入口是：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
```

如果你确实要先跑 upstream refresh，再收口：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo --run-omx-setup
```

默认受控更新策略是：

- `--root-agents-policy auto`
- `--project-config-policy auto`

也就是说：

- 根 `AGENTS.md` 如果被 upstream OMX 顶层模板顶掉，优先恢复 pre-setup 快照 / 最近 backup；如果当前文件本来就是项目侧内容，则不再无条件重写
- 项目 `.codex/config.toml` 优先恢复 pre-setup 快照 / 最近 backup，再只对 provider / model 等受管字段做严格继承
- 如果你确实想强制改写，也可以显式传：
  - `--root-agents-policy template`
  - `--project-config-policy setup-output`

## 2.1 它为什么还要种 `.omx` 规划文档？

因为很多项目真正卡住的不是“没装上 OMX”，而是：

- `Codex App` 进入项目后，不知道长期规划该写到哪里
- `OMX` 每次都要靠一大段一次性提示词才能重新接上上下文

因此 installer 现在会额外提供一个稳定 planning control surface，尤其是：

- `CURRENT_PROGRAM.md`
- `PROGRAM_ROUTING.md`
- `OMX_TEAM_PROMPT.md`

其中 `PROGRAM_ROUTING.md` 的职责就是明确：

- roadmap 写到哪里
- PRD / test-spec / implementation 写到哪里
- reports 写到哪里
- optional program pack 在当前项目里对应哪些文档

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
请安装并使用 https://github.com/gaofeng21cn/omx-project-installer ，然后在当前项目目录使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

如果对方已经装过 skill：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

## 8. 旧 skill alias 兼容补丁现在为什么还保留？

因为它还没有在 project-scope 安装路径里真正闭环。

当前正式版 `oh-my-codex@0.12.0` 里，已经可以确认进入正式包的部分是：

- `templates/AGENTS.md` 中的 runtime-only keyword gating
- catalog 中对 `analyze` / `build-fix` / `tdd` / `ecomode` / `ultraqa` / `swarm` 的 alias / merged 注册

但项目级 `omx setup --scope project` 仍然会把这些 alias / merged skill 当成非 active 目录跳过或删除。

这意味着：

- 正式模板仍然会引用这些入口
- project-scope `.codex/skills/` 却可能没有这些入口

所以 installer 仍然必须在项目里补齐这六个 legacy alias，直到 upstream 的 project-scope setup 也把这件事处理完整。

## 9. 既然仓库已经改名，为什么 metadata 文件还是 `.agent-contract-baseline.json`？

这是为了兼容已经落地到项目里的旧安装结果。

当前仓库已经对外改名为 `omx-project-installer`，但项目内 metadata 文件名暂时保留为：

- `.agent-contract-baseline.json`

这样可以避免对已经接管过的项目再做一次不必要的 metadata 文件迁移。

也就是说：

- **公开品牌名**：`omx-project-installer`
- **项目内历史兼容文件名**：`.agent-contract-baseline.json`

## 10. 什么是 `program pack`？

`program pack` 是 installer 的可选层，不是项目真相本身。

它的职责是：

- 在项目刚接入时，种下一组有领域语义的长期主线文档
- 让 `Codex App + OMX` 从第一轮开始就知道应该往哪类 `.omx` 文档里写规划

它不负责：

- 覆盖项目已有 `CURRENT_PROGRAM.md`
- 覆盖项目已有 reports
- 覆盖项目已经演化出来的 active state

当前首个 pack：

- `medical_research_foundry_delivery_closeout`
