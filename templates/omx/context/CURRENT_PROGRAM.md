# CURRENT_PROGRAM

- program_id: `{{PROGRAM_ID}}`
- owner model:
  - `Codex App`: 规划、监督、阶段验收、最终集成判断
  - `OMX`: 长时间连续执行、team lane 拆分、验证、report 回写
- default execution mode: `maximize OMX team mode`
- target repository: `{{TARGET_PATH}}`

## Mission

把 `{{DISPLAY_NAME}}` 收敛成一条长期 active mainline，而不是让 OMX 每次靠一次性长提示词重建上下文。

当前这个 control surface 的职责是：

- 固定当前唯一 active program
- 固定 long-horizon order
- 固定必须回写的 reports
- 让 `Codex App` 与 `OMX` 围绕同一组文档持续接力

## Current Phase

- `Phase 0: mainline initialization`
- 当前唯一活跃子线：`T0 current-program truth reset`

## Long-Horizon Order

1. 冻结当前唯一 active program 与 north star
2. 把最小可执行基线做出来，并建立验证闭环
3. 把 reports、verification、integration 流程收紧成稳定自动驾驶表面
4. 只有前面全绿后，才允许进入更厚的能力扩张

## Governing Truth Sources

必须优先读取并遵守：

- `{{TARGET_PATH}}/AGENTS.md`
- `{{TARGET_PATH}}/{{PROJECT_CONTRACT_PATH}}`
- `{{CURRENT_PROGRAM_PATH}}`
- `{{PROGRAM_ROUTING_PATH}}`
- `{{TEAM_PROMPT_PATH}}`
- `{{PROGRAM_SPEC_PATH}}`
- `{{PROGRAM_PRD_PATH}}`
- `{{PROGRAM_TEST_SPEC_PATH}}`
- `{{PROGRAM_IMPLEMENTATION_PATH}}`
- `{{PROGRAM_REPORT_STATUS_PATH}}`
- `{{PROGRAM_REPORT_ISSUES_PATH}}`

## Required Report Surface

固定写回目录：

- `{{TARGET_PATH}}/{{REPORT_DIR}}/`

每轮有意义推进后必须更新：

- `LATEST_STATUS.md`
- `ITERATION_LOG.md`
- `OPEN_ISSUES.md`

## Execution Rules

- 默认最大化利用 `OMX team mode`
- 每完成一个 tranche，自动进入下一个 tranche
- 不把单轮 milestone 完成当成整个 program 结束
- 除非遇到 hard blocker、破坏性操作、或 frozen truth 冲突，否则不要停下来询问

## Stop Conditions

只有以下情况才允许停下来询问：

- 需要破坏性 git 操作
- frozen truth sources 之间出现不可裁决冲突
- 需要新的产品级改向，而不是继续当前 mainline
- 需要仓库外的人类输入、额外授权、或外部凭据
