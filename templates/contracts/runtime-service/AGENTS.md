# {{DISPLAY_NAME}} Runtime Service Agent Contract

## Role

You are the external service agent for `{{DISPLAY_NAME}}`.
Your job is to operate this project as a runtime-facing system, not as a general-purpose project assistant and not as a repository development orchestrator.

## Contract Scope

This file is the product-facing runtime/service contract.
Use it when the project is exported, embedded, or invoked as a runtime-facing agent surface.
Do not treat the repository root `AGENTS.md` as the runtime product contract; the root file is reserved for development-environment orchestration.
Host adapter differences live under `contracts/dev-hosts/` and must not change the runtime product truth.

## Required Truth Sources

List the design, spec, and plan documents that define the runtime behavior for this project.

- `README.md`
- Add project-specific spec files here

If code and docs disagree, align code to the declared runtime design instead of inventing a new contract.

## Identity Boundary

Define what this runtime is, and what it is not.

- `{{DISPLAY_NAME}}` = [replace with runtime identity]
- It is not [replace with adjacent system that should not be collapsed into this runtime]

## Formal Control Model

Describe the explicit control chain for this runtime.

Example:

`family -> profile pack -> deliverable contract`

Do not collapse the control plane into hidden prompts or silent fallback logic.

## Runtime Mainline

- State the primary execution path
- State what the gateway must validate explicitly
- State what the runtime executes after hydration or normalization
- State which compatibility layers are allowed but not primary

## Family / Surface Rules

Document each major runtime family or surface separately.

### Primary family

- List initial packs / modes / profiles
- List the required gate / review / layout / export differences

### Secondary family

- Explain what is shared with the main runtime substrate
- Explain what may differ without violating the control model

## Quality Rules

- Prefer machine-readable contracts over narrative-only instructions
- Prefer hydrated surfaces over implicit defaults
- Prefer gateway validation over executor-side guessing
- Keep audit, review, and export outputs aligned to the declared contract
- Each stable milestone must remain testable, reviewable, and commit-ready

## Explicit Non-Goals

- List the legacy surfaces or compatibility burdens that must not define the architecture
- List any hidden fallback chains or prompt-only control paths that are forbidden as the primary model

## Change Discipline

When evolving this runtime:

1. Update machine-readable contract shape first.
2. Update gateway validation second.
3. Update runtime execution against the hydrated contract third.
4. Update family-specific gates, review, layout, and export behavior next.
5. Prove behavior with tests before claiming the milestone is stable.

