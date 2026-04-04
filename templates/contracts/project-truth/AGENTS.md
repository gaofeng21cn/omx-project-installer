# {{DISPLAY_NAME}} Project Truth Contract

This file is the single project truth contract for the repository.
It defines what this project is, what it is not, which boundaries are authoritative, and what structural constraints must survive future refactors.

## Scope

Apply this contract to the repository as a whole unless a deeper `AGENTS.md` explicitly overrides it for a narrower subtree.

This contract is not the repository development entrypoint.
The root `AGENTS.md` remains the development/orchestration entry file, while this file holds the project-specific truth that should not be mixed back into host setup mechanics.

## Project Identity

Document the real identity of the project here.

- What this project is
- What it is not
- Who the human operators are
- What the agent is expected to do
- What the platform/runtime layer is expected to do

## Architecture Priorities

Document the highest-priority stable architecture rules here.

- Preferred control chain
- Preferred stable interfaces
- Preferred mutation paths
- What must not be reintroduced as legacy fallback architecture

## Stability Rules

Document what counts as stable and what requires isolation.

- Mainline branch expectations
- Worktree or branch-isolation rules
- Shared checkout assumptions
- Conditions for large refactors versus direct mainline work

## Documentation Layers

Describe which documentation directories are public/stable and which are internal/process artifacts.

## Data And State Mutation

State how important state changes must be performed and audited.

- Read-before-write expectations
- Approved controller or mutation surfaces
- Audit trail requirements
- Explicit failure over silent correction

## Review Surface

State where humans are expected to review formal outputs and where agents should write durable state.

## Domain-Specific Direction

Put project-specific quality bias, strategic direction, or domain-specific stopping rules here.

This section is where one project may look like a runtime/service truth contract and another may look like a repository-native platform contract.
The structure stays the same; the content is project-specific.

## Conflict Handling

- User instructions override this file
- Deeper `AGENTS.md` files override this file for narrower scopes
- OMX or Codex host orchestration rules govern how work executes
- This file governs what project-specific truth and boundaries must be preserved

