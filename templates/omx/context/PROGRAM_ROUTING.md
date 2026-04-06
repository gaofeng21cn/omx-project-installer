# Program Routing

这个文件定义 `Codex App` 与 `OMX` 在当前项目中应该把哪类规划写到哪类控制面。

## Core Control Surfaces

- 当前唯一 active program：
  - `{{CURRENT_PROGRAM_PATH}}`
- 当前 team 执行提示：
  - `{{TEAM_PROMPT_PATH}}`
- 当前 routing 说明：
  - `{{PROGRAM_ROUTING_PATH}}`

## Planning Rules

- 长期 program operating model：
  - `{{PROGRAM_SPEC_PATH}}`
- 当前 mainline PRD：
  - `{{PROGRAM_PRD_PATH}}`
- 当前 mainline test spec：
  - `{{PROGRAM_TEST_SPEC_PATH}}`
- 当前 mainline implementation plan：
  - `{{PROGRAM_IMPLEMENTATION_PATH}}`
- 当项目进入更细的长期 program 时：
  - roadmap 写到 `.omx/plans/roadmap-*.md`
  - 子线 PRD 写到 `.omx/plans/prd-*.md`
  - 子线 test spec 写到 `.omx/plans/test-spec-*.md`
  - 子线 implementation plan 写到 `.omx/plans/implementation-*.md`

## Report Rules

固定回写目录：

- `{{TARGET_PATH}}/{{REPORT_DIR}}/`

每次有意义推进后必须更新：

- `{{PROGRAM_REPORT_STATUS_PATH}}`
- `{{PROGRAM_REPORT_LOG_PATH}}`
- `{{PROGRAM_REPORT_ISSUES_PATH}}`

## Optional Program Pack

- installed pack:
  - `{{INSTALLED_PROGRAM_PACK_ID}}`
- pack summary:
  - `{{INSTALLED_PROGRAM_PACK_DESCRIPTION}}`

如果已安装 optional pack，优先补读这些 pack 文档：

{{INSTALLED_PROGRAM_PACK_DOCS}}

## Preserve Rules

- installer 只负责补缺，不覆盖项目已经演化出来的 truth surfaces
- `CURRENT_PROGRAM.md` 与 reports 一旦进入项目真实运行，就应视为项目真相面
- program pack 只负责提供长期协作骨架，不替代项目自己的 active state
