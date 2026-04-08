# OMX Compatibility Notes

Current `omx setup` behavior that this installer compensates for:

- `omx setup --scope project` writes project-local `.codex/config.toml`
- `omx setup --scope project` writes project-root `AGENTS.md`
- setup does not provide a project-contract merge mode for an existing root `AGENTS.md`
- setup does not restore provider / model / reasoning truth from user scope back into project scope

The installer therefore uses:

`omx setup -> post-setup reconcile`

That reconcile phase is responsible for:

1. Preserving any existing root `AGENTS.md`
2. Re-applying thin root contract layering
3. Restoring the pre-setup project config snapshot before OMX-managed config is merged back in from setup output
4. Restoring system-level provider, model, and reasoning configuration into project scope
5. Writing baseline metadata for later diff/upgrade/reconcile operations
