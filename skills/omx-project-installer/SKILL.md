---
name: omx-project-installer
description: Install or refresh oh-my-codex in a specific project directory while reconciling a layered AGENTS contract structure, inheriting system-level provider config into project config, and protecting root AGENTS.md plus project config during controlled updates.
---

# OMX Project Installer

## Overview

Use this skill when you want to install or refresh OMX for a specific repository without hand-managing the split between root `AGENTS.md`, `.codex/AGENTS.md`, `contracts/project-truth/AGENTS.md`, provider config inheritance, controlled project-level update protection, or the project-level continuous planning scaffold for `Codex App + OMX`.

This skill uses the `omx-project-installer` repository as the source of truth, then applies a post-setup reconciliation pass on top of `omx setup`.

## When To Use

- Install OMX into a new project and immediately apply the layered contract structure
- Refresh an existing OMX project after `omx setup --force`
- Adopt a project that already has a root `AGENTS.md` and preserve it before switching to a thin root entry
- Compare a project against the current baseline version
- Upgrade managed contract layers without overwriting the project truth contract
- Seed a stable `.omx/context + .omx/plans + .omx/reports` routing surface so Codex/OMX know where long-horizon planning should live
- Apply an optional `program pack` when a project should start with a domain-specific long-horizon scaffold

## Commands

Run the installer from the baseline repository checkout:

```bash
python skills/omx-project-installer/scripts/omx_project_installer.py install --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py install --target /abs/path/to/repo --program-pack medical_research_foundry_delivery_closeout
python skills/omx-project-installer/scripts/omx_project_installer.py diff --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py upgrade --target /abs/path/to/repo
python skills/omx-project-installer/scripts/omx_project_installer.py reconcile --target /abs/path/to/repo
```

## Workflow

1. Resolve target project and current contract layout
2. Run `omx setup --scope project` unless explicitly skipped
3. Preserve any pre-existing root `AGENTS.md`
4. Apply the App-native root contract, `.codex/AGENTS.md` OMX layer, and `contracts/project-truth/AGENTS.md`
5. Reconcile project `.codex/config.toml` with system-level provider and model settings
6. Restore the pre-setup project config snapshot, merge back OMX-managed config from the latest setup output, then re-apply strict user-scope provider/model inheritance
7. Repair the project-scope legacy alias layer for `analyze`、`build-fix`、`tdd`、`ecomode`、`ultraqa`、`swarm`
8. Seed a stable continuous planning scaffold under `.omx/context`, `.omx/plans`, and `.omx/reports`
9. Optionally seed a domain-specific `program pack`
10. Write baseline metadata for later `diff`, `upgrade`, and `reconcile`

Public `README` surfaces remain human-owned and are not baseline-managed.

## Project Truth

The installer always converges on one structure:

- root `AGENTS.md`
- `.codex/AGENTS.md`
- `contracts/project-truth/AGENTS.md`
- `.omx/local/AGENTS.local.md`

Repository differences live inside the content of `contracts/project-truth/AGENTS.md`, not in multiple install modes.

## Compatibility Guarantees

- Root `AGENTS.md` becomes the App-native project entry file
- `.codex/AGENTS.md` becomes the OMX project-scope orchestration layer
- `contracts/project-truth/AGENTS.md` becomes the single project authority path
- System-level provider configuration is copied back into project-level `.codex/config.toml`
- Project-scoped `omx setup` refreshes are wrapped in a controlled update flow so pre-existing `.codex/config.toml` content is restored, OMX-managed keys are merged back from setup output, and user-scope provider/model truth is re-applied
- Known legacy alias names are repaired after project-scope setup
- Missing `.omx/context + .omx/plans + .omx/reports` control surfaces are initialized by default
- `PROGRAM_ROUTING.md` is available as the stable planning map for `Codex App` and `OMX`
- Optional `program pack` scaffolds can be applied without overwriting existing project truth files
- Project truth contracts are not silently replaced during `upgrade` or `reconcile`

## Resources (optional)

### scripts/
- `omx_project_installer.py`
  - Main installer / diff / upgrade / reconcile entrypoint

### references/
- `omx-compatibility-notes.md`
  - Current OMX setup behavior that this installer compensates for
