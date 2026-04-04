---
name: omx-project-installer
description: Install or refresh oh-my-codex in a specific project directory while reconciling a layered AGENTS contract structure, inheriting system-level provider config into project config, and repairing legacy project-scope skill alias compatibility.
---

# OMX Project Installer

## Overview

Use this skill when you want to install or refresh OMX for a specific repository without hand-managing `AGENTS.md`, host adapter layering, `contracts/project-truth/AGENTS.md`, provider config inheritance, or legacy project-scope skill alias repair.

This skill uses the `agent-contract-baseline` repository as the source of truth, then applies a post-setup reconciliation pass on top of `omx setup`.

## When To Use

- Install OMX into a new project and immediately apply the layered contract structure
- Refresh an existing OMX project after `omx setup --force`
- Adopt a project that already has a root `AGENTS.md` and preserve it before switching to a thin root entry
- Compare a project against the current baseline version
- Upgrade managed contract layers without overwriting the project truth contract

## Commands

Run the installer from the baseline repository checkout:

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py install --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py diff --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
```

## Workflow

1. Resolve target project and current contract layout
2. Run `omx setup --scope project` unless explicitly skipped
3. Preserve any pre-existing root `AGENTS.md`
4. Apply thin root contract, host adapters, README layering section, and `contracts/project-truth/AGENTS.md`
5. Reconcile project `.codex/config.toml` with system-level provider and model settings
6. Repair legacy project-scope skill aliases
7. Write baseline metadata for later `diff`, `upgrade`, and `reconcile`

## Project Truth

The installer always converges on one structure:

- root `AGENTS.md`
- `contracts/dev-hosts/`
- `contracts/project-truth/AGENTS.md`
- `.omx/local/AGENTS.local.md`

Repository differences live inside the content of `contracts/project-truth/AGENTS.md`, not in multiple install modes.

## Compatibility Guarantees

- Root `AGENTS.md` becomes a thin, reproducible entry file
- `contracts/dev-hosts/` becomes the explicit host adapter layer
- `contracts/project-truth/AGENTS.md` becomes the single project authority path
- System-level provider configuration is copied back into project-level `.codex/config.toml`
- Known legacy alias names are repaired after project-scope setup
- Project truth contracts are not silently replaced during `upgrade` or `reconcile`

## Resources (optional)

### scripts/
- `omx_project_installer.py`
  - Main installer / diff / upgrade / reconcile entrypoint

### references/
- `omx-compatibility-notes.md`
  - Current OMX setup behavior that this installer compensates for
