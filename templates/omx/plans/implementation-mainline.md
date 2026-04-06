# Implementation Plan - {{DISPLAY_NAME}} Mainline

## Purpose

把当前 active mainline 的工作拆成 OMX 可以持续执行的最小 tranche。

## Recommended Lane Split

如果可并行，默认拆成：

- `Lane A`: implementation
- `Lane B`: tests / verification
- `Lane C`: docs / report sync / wording audit

leader 固定保留：

- integration
- truth conflict resolution
- final verification
- checkpoint
- report truth

## Execution Rule

- 只做服务当前 active program 的事情
- 每完成一个 tranche 自动进入下一个 tranche
- 如果 scope 发生变化，先更新 `CURRENT_PROGRAM`、`PROGRAM_ROUTING` 与 reports，再继续执行
