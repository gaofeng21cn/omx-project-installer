继续当前 active program：

- `{{PROGRAM_ID}}`

必须先读取：

- `{{CURRENT_PROGRAM_PATH}}`
- `{{PROGRAM_ROUTING_PATH}}`
- `{{PROGRAM_SPEC_PATH}}`
- `{{PROGRAM_PRD_PATH}}`
- `{{PROGRAM_TEST_SPEC_PATH}}`
- `{{PROGRAM_IMPLEMENTATION_PATH}}`
- `{{PROGRAM_REPORT_STATUS_PATH}}`
- `{{PROGRAM_REPORT_ISSUES_PATH}}`

然后按 `CURRENT_PROGRAM.md` 中定义的 long-horizon order 持续推进。

执行要求：

- 默认最大化利用 `OMX team mode`
- 默认采用 `team-plan -> team-exec -> team-verify -> team-fix` 循环
- leader 保留：
  - truth conflict resolution
  - integration
  - final verification
  - checkpoint
  - report truth
- 如果 team state 已 `missing`、worker stalled、或 pane 异常退出：
  - 先读取最新 `LATEST_STATUS.md`、`ITERATION_LOG.md`、`OPEN_ISSUES.md`
  - 然后直接重开 team 继续当前 active program
  - 不要把旧 team 生命周期当 blocker
- 除非遇到 hard blocker、破坏性操作、或 frozen truth conflict，否则不要停下来询问
- 每完成一个有意义里程碑，必须更新：
  - `{{PROGRAM_REPORT_STATUS_PATH}}`
  - `{{PROGRAM_REPORT_LOG_PATH}}`
  - `{{PROGRAM_REPORT_ISSUES_PATH}}`
