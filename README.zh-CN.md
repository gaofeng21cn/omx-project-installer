<p align="center">
  <a href="./README.md">English</a> | <strong>中文</strong>
</p>

<h1 align="center">OMX Project Installer</h1>

<p align="center"><strong>面向真实项目仓库的兼容性感知 OMX project-scope 安装与受控刷新工具</strong></p>
<p align="center">分层合同 · 配置继承 · 受控收口</p>

<table>
  <tr>
    <td width="33%" valign="top">
      <strong>主要用途</strong><br/>
      在已有项目仓库里安装或刷新 OMX，同时保住仓库自己的根合同和 project truth 结构
    </td>
    <td width="33%" valign="top">
      <strong>操作入口</strong><br/>
      通过 Codex skill 安装入口，加上 Python reconcile 脚本完成 install、diff、upgrade、refresh
    </td>
    <td width="33%" valign="top">
      <strong>兼容保证</strong><br/>
      让根 <code>AGENTS.md</code>、project truth、项目级 <code>.codex</code> 配置继承和 post-setup 收口保持一致
    </td>
  </tr>
</table>

> 对外，`omx-project-installer` 是一个兼容性感知的 OMX 项目安装器。对内，它是一层建立在 `omx setup` 之上的 post-setup reconcile 机制，用来保护分层合同和项目级配置真相。

## 项目定位

这个仓库不替代 `omx setup`。它的职责，是让 `project-scope` OMX 能够安全落进那些已经有自己根合同、公开 README 和项目规则的真实仓库里。

核心模型是：

`omx setup -> post-setup reconcile`

也就是说：

- OMX 仍负责生成或刷新 project-scope 骨架
- 安装器负责把项目重新收束回分层合同结构
- 项目级 `.codex/config.toml` 会被重新对齐到系统级 provider、model、reasoning 真相

## 它解决什么问题

- 把项目根保持为 App-native 的 `AGENTS.md` 入口，而不是把所有内容都压成 OMX 单体根文件
- 让所有受管项目统一收束到 `contracts/project-truth/AGENTS.md`
- 把 `.codex/AGENTS.md` 写成 OMX project orchestration layer
- 在 refresh 后恢复并收口项目级配置：先保回项目内容，再精确并回 OMX 受管字段
- 种下稳定的 `.omx/context + .omx/plans + .omx/reports` 规划面
- 在需要时附带安装可选的 `program pack`

## 兼容模型

安装后的目标结构固定为：

- 根 `AGENTS.md`
- `.codex/AGENTS.md`
- `contracts/project-truth/AGENTS.md`
- `.omx/local/AGENTS.local.md`

仓库之间的差异放在 `contracts/project-truth/AGENTS.md` 的内容里，而不是放在多套安装模式里。

当前兼容面同时覆盖：

- 根 `AGENTS.md` 的受控保留
- 项目 `.codex/config.toml` 的受控收口
- 系统级 provider / model 继承
- project-scope skill 布局里的 legacy alias 修复
- 面向 `Codex App + OMX` 的稳定 planning control surface

## 快速开始

先在这份仓库里安装 skill：

```bash
git clone https://github.com/gaofeng21cn/omx-project-installer.git
cd omx-project-installer
./install.sh
```

然后在目标项目里直接对 Codex 说：

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

## 直接命令入口

也可以直接从本仓库 checkout 运行脚本：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py install --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py diff --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
```

如果你确实想先跑 upstream setup 再收口：

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo --run-omx-setup
```

## 当前边界

- 公开 `README` 始终由人类维护，不属于 baseline 受管面。
- 安装器统一的是合同形状，不是项目真相内容本身。
- heavy OMX 运行仍应放在独立 owner worktree，而不是共享根工作树。
- Python reconcile 脚本需要在依赖齐全的 Python 环境里执行。

## 面向 Agent

如果目标是在真实仓库里安全刷新 OMX，优先使用这个安装器，而不是裸跑 `omx setup --scope project`。

典型 Agent 任务：

- 给新项目安装带分层合同的 OMX
- 对照当前 baseline manifest 做差异审计
- 在上游 refresh 后执行 upgrade 或 reconcile
- 重新应用项目配置继承和 planning scaffold

## 文档

- [FAQ](docs/faq.md)
- [Program pack scaffold 说明](docs/program-pack-scaffold.md)
- [Installer skill](skills/omx-project-installer/SKILL.md)
- [示例：med-autoscience](examples/med-autoscience)
- [示例：redcube-ai](examples/redcube-ai)

## 技术验证

在具备 `tomlkit` 与 `pytest` 的 Python 环境里执行：

```bash
python3 -m pytest tests/test_omx_project_installer.py -q
```
