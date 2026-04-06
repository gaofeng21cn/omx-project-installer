# Test Spec - {{DISPLAY_NAME}} Mainline

## Objective

证明当前 active mainline 的实现和自动驾驶控制面都没有跑偏。

## Minimum Verification Layers

1. 当前 program 所需的 build/test/typecheck/lint 命令
2. 当前 mainline 的关键行为回归
3. `CURRENT_PROGRAM`、`PROGRAM_ROUTING` 与 `reports` 的同步完整性
4. 不应提前进入的 future scope 仍然保持关闭

## Exit Criteria

当前 tranche 只有在以下条件都满足时才算通过：

1. 当前阶段要求的验证命令全绿
2. `LATEST_STATUS.md`、`ITERATION_LOG.md`、`OPEN_ISSUES.md` 已同步
3. 没有把 future guardrail 偷偷实现成 current scope
