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
- legacy alias 修复：`analyze`、`build-fix`、`tdd`、`ecomode`、`ultraqa`、`swarm`
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

## 8. 如果 OMX 上游已经 merge 了 legacy alias 修复，为什么这里还保留兼容修复？

因为“已经 merge”不等于“已经进入正式 release”。

当前判断标准不是 PR 状态，而是：

- 最新正式 release / npm 包里发布的 `templates/AGENTS.md`
- 是否已经不再引用这些旧路径：
  - `~/.codex/skills/analyze/SKILL.md`
  - `~/.codex/skills/ecomode/SKILL.md`
  - `~/.codex/skills/tdd/SKILL.md`
  - `~/.codex/skills/build-fix/SKILL.md`
  - `~/.codex/skills/ultraqa/SKILL.md`
- 是否已经包含 runtime-only keyword gating

在 upstream 的正式 release 真正包含这些修复之前，安装器会继续保留：

- legacy alias 修复
- runtime-only keyword gating 兼容修复

这样可以保证项目级安装在当前正式版本的 OMX 上依然可用，而不会因为“PR 已 merge”就提前删掉必要补丁。

## 9. 什么时候可以删掉这些兼容修复？

当且仅当 upstream 发布了一个**新于当前检查版本**的正式 release，并且该 release 中的 `templates/AGENTS.md` 已经同时满足：

1. 所有旧 legacy skill 路径都已移除
2. `analyze` / `build-fix` / `tdd` / `ecomode` / `ultraqa` / `swarm` 都已切到当前 canonical 逻辑
3. runtime-only keyword gating 已进入正式模板

到那时，才适合在 baseline 安装器里降级或删除这部分兼容修复。

## 10. 既然仓库已经改名，为什么 metadata 文件还是 `.agent-contract-baseline.json`？

这是为了兼容已经落地到项目里的旧安装结果。

当前仓库已经对外改名为 `omx-project-installer`，但项目内 metadata 文件名暂时保留为：

- `.agent-contract-baseline.json`

这样可以避免对已经接管过的项目再做一次不必要的 metadata 文件迁移。

也就是说：

- **公开品牌名**：`omx-project-installer`
- **项目内历史兼容文件名**：`.agent-contract-baseline.json`

## 11. 什么是 `program pack`？

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
