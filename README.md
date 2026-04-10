<p align="center">
  <strong>English</strong> | <a href="./README.zh-CN.md">中文</a>
</p>

<h1 align="center">OMX Project Installer</h1>

<p align="center"><strong>Compatibility-aware OMX project-scope install and controlled refresh for real repositories</strong></p>
<p align="center">Layered Contracts · Config Inheritance · Controlled Reconcile</p>

<table>
  <tr>
    <td width="33%" valign="top">
      <strong>Primary Use</strong><br/>
      Install or refresh OMX inside an existing repository without losing the repository's own root contract and project truth structure
    </td>
    <td width="33%" valign="top">
      <strong>Interface</strong><br/>
      Codex skill installation plus a Python reconcile script for install, diff, upgrade, and refresh flows
    </td>
    <td width="33%" valign="top">
      <strong>Compatibility Guarantee</strong><br/>
      Keep root <code>AGENTS.md</code>, project truth, project-level <code>.codex</code> config inheritance, and controlled post-setup reconciliation aligned
    </td>
  </tr>
</table>

> Publicly, `omx-project-installer` is a compatibility-aware OMX project installer. Internally, it is a post-setup reconciliation layer over `omx setup` that preserves layered contracts and project-level config truth.

## Product Position

This repository does not replace `omx setup`. Its job is to make `project-scope` OMX usable in repositories that already have their own root contract, public README, and project-specific operating rules.

Validated against `oh-my-codex v0.12.4` on 2026-04-10:

- upstream still writes project-root `AGENTS.md` for `project` scope
- upstream still does not generate project `.codex/AGENTS.md`
- upstream still does not restore strict user-scope provider / model / reasoning truth into project `.codex/config.toml`
- upstream `0.12.4` now preserves non-OMX entries in `.codex/hooks.json`, so extra hook-file protection is no longer part of this baseline

The core model is:

`omx setup -> post-setup reconcile`

That means:

- OMX still generates or refreshes the project-scope scaffold
- this installer restores the layered project contract shape
- project-level `.codex/config.toml` is reconciled back to system-level provider, model, and reasoning truth

## What It Helps You Do

- Keep the repository root on an App-native `AGENTS.md` entry instead of collapsing everything into one OMX root file.
- Converge every installed project onto one truth path: `contracts/project-truth/AGENTS.md`.
- Write `.codex/AGENTS.md` as the OMX project orchestration layer.
- Repair project-level config after refresh by restoring project content and merging back OMX-managed keys precisely.
- Seed a stable `.omx/context + .omx/plans + .omx/reports` planning surface.
- Apply optional `program pack` scaffolds when a project should start with a domain-specific long-horizon frame.

## Compatibility Model

The installed project shape is always:

- root `AGENTS.md`
- `.codex/AGENTS.md`
- `contracts/project-truth/AGENTS.md`
- `contracts/dev-hosts/{README,omx-cli,codex-app}.md`
- `.omx/local/AGENTS.local.md`

Repository differences belong inside `contracts/project-truth/AGENTS.md`, not inside multiple install modes.

The current compatibility surface also covers:

- controlled root `AGENTS.md` preservation
- controlled project `.codex/config.toml` reconcile
- system-level provider and model inheritance
- managed host adapter contracts under `contracts/dev-hosts/`
- legacy alias repair for project-scope skill layouts that upstream still does not materialize
- a stable planning control surface for `Codex App + OMX`

## Quick Start

Install the skill from this repository:

```bash
git clone https://github.com/gaofeng21cn/omx-project-installer.git
cd omx-project-installer
./install.sh
```

Then, inside a target repository, tell Codex:

```text
使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。
```

## Direct Commands

Run the installer from this repository checkout:

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py install --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py diff --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
```

If you intentionally want to run upstream setup first and then close the gap:

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo --run-omx-setup
```

## Current Boundaries

- Public `README` content remains human-owned and is not baseline-managed.
- The installer standardizes the contract shape, but the project truth content remains repository-specific.
- Heavy OMX runtime work should still run in an isolated owner worktree rather than in a shared root checkout.
- The Python reconcile script expects a working Python environment with its dependencies available.

## For Agents

If the goal is to refresh OMX safely inside a real repository, prefer this installer over a naked `omx setup --scope project`.

Typical agent tasks:

- install OMX into a new project with layered contracts
- diff a project against the current baseline manifest
- upgrade or reconcile a repository after upstream refresh
- reapply project config inheritance and planning scaffolds

## Documentation

- [FAQ](docs/faq.md)
- [Program pack scaffold notes](docs/program-pack-scaffold.md)
- [Installer skill](skills/omx-project-installer/SKILL.md)
- [Example: med-autoscience](examples/med-autoscience)
- [Example: redcube-ai](examples/redcube-ai)

## Technical Validation

In a Python environment with `tomlkit` and `pytest` available:

```bash
python3 -m pytest tests/test_omx_project_installer.py -q
```
