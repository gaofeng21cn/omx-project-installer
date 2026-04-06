# Program Pack Scaffold

## Goal

把 `omx-project-installer` 从“只会种最小 continuous scaffold”的工具，升级成“可以同时种下 planning routing 与长期 program pack”的项目级安装器。

目标不是把某个项目的长 prompt 硬编码进 baseline，而是让 `Codex App` / `OMX` 进入项目后，先读固定路由面，就知道：

- 当前主线写在哪里
- 长期路线图写在哪里
- 子线 PRD / test spec 写在哪里
- 报告该回写到哪里
- 哪些文件是 installer 可补缺的，哪些是真正的人类/项目真相面

## Scope

这轮只做两层：

1. 通用 `planning routing` 机制
2. 一个可选 `medical_research_foundry_delivery_closeout` program pack

不做：

- 覆盖项目已有 `.omx` 真相文件
- 把 reports / CURRENT_PROGRAM 强制重置为模板
- 直接把多个项目的具体运行状态内联进 installer baseline

## Design

### 1. Base scaffold 增加 routing surface

在现有 `.omx/context/CURRENT_PROGRAM.md` 与 `.omx/context/OMX_TEAM_PROMPT.md` 之外，新增一个固定上下文文件：

- `.omx/context/PROGRAM_ROUTING.md`

这个文件只回答结构性问题：

- 哪类规划写到哪类文件
- 哪些是长期主线文档，哪些是子线文档
- reports 的固定目录
- `program pack` 的职责边界

这样 `Codex App` 不需要靠会话回忆项目约定，而是先读一个稳定 routing 文件。

### 2. Program pack 作为 installer 的可选层

installer 新增可选 `--program-pack <pack-id>`。

当 pack 被选择时，installer 从 manifest 注册表读取该 pack 对应的模板集合，并将这些模板写入目标项目 `.omx/`。

pack 只负责补充：

- long-horizon context
- autopilot prompt
- roadmap
- program PRD
- program test spec

pack 不负责：

- 覆盖已有 `CURRENT_PROGRAM.md`
- 覆盖已有 reports
- 覆盖项目已经演化出来的 active subline truth

### 3. Preserve-first policy

installer 对 base scaffold 和 pack scaffold 都保持同一条原则：

- 文件不存在才创建
- 已存在就记录为 `preserved`
- metadata 记录当前所选 `program_pack`

这样后续 `upgrade/reconcile` 可以继续“补缺不覆盖”。

### 4. Manifest-driven registry

`baseline.manifest.json` 新增：

- `program_routing` 模板
- `program_packs` 注册表

脚本不硬编码具体 pack 文件路径，而是从 manifest 读取 pack 定义，按模板路径逐个渲染。

### 5. First pack

首个 pack：

- `medical_research_foundry_delivery_closeout`

它提供一组通用但有明确领域语义的长期主线模板，覆盖：

- `CURRENT_PROGRAM` 应继续指向 active mainline
- `PROGRAM_ROUTING` 告诉 Codex/OMX 如何写计划
- long-horizon prompt 指向 delivery-plane closeout 这一类长期 program

## Acceptance

1. 不带 pack 的 install，仍会生成 base scaffold，并额外生成 `PROGRAM_ROUTING.md`
2. 带 pack 的 install，会额外种下 pack 文档
3. 已存在的 routing / pack 文件不会被覆盖
4. metadata 会记录当前 `program_pack`
5. `upgrade/reconcile` 在未显式改 pack 时，会沿用 metadata 中已记录的 pack
