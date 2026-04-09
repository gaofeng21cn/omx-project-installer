# OMX Compatibility Notes

Current `omx setup` behavior that this installer compensates for
(validated against `oh-my-codex v0.12.3` on 2026-04-09):

## A. Root `AGENTS.md` protection and layered contract preservation

- `omx setup --scope project` still targets project-root `AGENTS.md`
- non-interactive project-scope refresh skips overwriting an existing project-root `AGENTS.md` unless `--force` is used
- first install, explicit `--force`, or recovery to the OMX single-file root contract can still write project-root `AGENTS.md`
- setup does not provide a project-contract merge mode for an existing layered root `AGENTS.md`

Interpretation:

- the old "protect root AGENTS from every refresh" risk is lower than before
- the "preserve installer-managed layered root contract" requirement still exists

## B. Project `.codex/AGENTS.md` generation

- `omx setup --scope project` does not create the project-specific `.codex/AGENTS.md` orchestration layer used by this installer

Interpretation:

- project `.codex/AGENTS.md` is still an installer responsibility, not an upstream setup artifact

## C. Project config reconciliation and user-scope truth inheritance

- `omx setup --scope project` writes project-local `.codex/config.toml`
- setup does not restore provider / model / reasoning truth from user scope back into project scope
- setup does not provide a project-config mode that only updates OMX-managed fields while preserving strict user-scope inheritance truth

The installer therefore uses:

`omx setup -> post-setup reconcile`

That reconcile phase is responsible for:

1. Preserving any existing root `AGENTS.md` when project refresh should not collapse back to the OMX single-file root contract
2. Re-applying thin root contract layering when project root entry drift or force/setup paths require it
3. Writing the project-specific `.codex/AGENTS.md` orchestration layer
4. Restoring the pre-setup project config snapshot before OMX-managed config is merged back in from setup output
5. Restoring system-level provider, model, and reasoning configuration into project scope
6. Writing baseline metadata for later diff/upgrade/reconcile operations

## D. OPL heavy OMX execution discipline (external contract)

For OPL heavy OMX workflows (long-running automation, team/swarm runtime surfaces, or hook-heavy execution paths), installer guidance now treats execution isolation as a compatibility requirement:

- heavy OMX must run in a dedicated owner worktree
- session-only isolation is not accepted as a substitute for repository/worktree isolation
- shared root worktree is reserved for light operations only (read/audit/reconcile entrypoints), not heavy runtime execution

Interpretation:

- session runtime state isolation and repository write isolation are different boundaries
- preventing hook interference requires worktree-level ownership, not only session-level separation

## E. Compatibility audit scope (new)

Compatibility audit now explicitly covers two dimensions:

1. Static contract checks
   - layered root contract integrity (`AGENTS.md` + `.codex/AGENTS.md` + `contracts/project-truth/AGENTS.md`)
   - strict project-config reconciliation semantics (managed-field merge + user-scope provider/model/reasoning truth inheritance)
2. Runtime contamination risk checks
   - whether heavy OMX execution is confined to owner worktrees
   - whether session-only isolation is incorrectly used as the isolation boundary
   - whether shared root worktrees are exposed to heavy runtime/hook side effects

So "compatibility" is no longer defined as static-file convergence alone; it also includes operational cleanliness of runtime execution surfaces.
