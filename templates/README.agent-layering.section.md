<!-- AGENT-CONTRACT-BASELINE:START -->
- 根目录 `AGENTS.md` 仅用于本仓库开发环境中的 Codex/OMX 协作，不单独承载项目真相合同
- 宿主适配层位于 `contracts/dev-hosts/`，用于区分 OMX CLI 与 Codex App / plain Codex 的开发宿主行为
- 项目真相合同位于 `{{PROJECT_CONTRACT_PATH}}`
- 可选本机私有覆盖层约定为 `.omx/local/AGENTS.local.md`，保持未跟踪
- 本地工具运行态目录 `.omx/` 与 `.codex/` 必须保持未跟踪，不进入版本库
<!-- AGENT-CONTRACT-BASELINE:END -->
