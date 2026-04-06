# Program Operating Model

## Purpose

这份文档定义当前仓库在 `Codex App + OMX` 协作下的长期自动驾驶控制面。

它的目标不是替代项目自己的产品/架构文档，而是冻结：

- 当前唯一 active program 如何被定义
- `CURRENT_PROGRAM + PROGRAM_ROUTING + reports` 与其余文档的优先级关系
- 什么情况下允许切 program、切 phase、或停下来问人

## Truth Priority

当前 program 的真相优先级固定为：

1. `CURRENT_PROGRAM.md`
2. `PROGRAM_ROUTING.md`
3. 当前 active program 对应的 `LATEST_STATUS.md` / `OPEN_ISSUES.md`
4. 当前 active program 对应的 `spec / prd / test-spec / implementation`
5. 历史 snapshots、旧 program reports、一次性 closeout 文档

## Required Control Surfaces

每个长期 active program 至少应有：

- `.omx/context/CURRENT_PROGRAM.md`
- `.omx/context/PROGRAM_ROUTING.md`
- `.omx/context/OMX_TEAM_PROMPT.md`
- `.omx/plans/spec-*.md`
- `.omx/plans/prd-*.md`
- `.omx/plans/test-spec-*.md`
- `.omx/plans/implementation-*.md`
- `.omx/reports/<program-id>/README.md`
- `.omx/reports/<program-id>/LATEST_STATUS.md`
- `.omx/reports/<program-id>/ITERATION_LOG.md`
- `.omx/reports/<program-id>/OPEN_ISSUES.md`

## Execution Rules

- `Codex App` 负责规划、监督、阶段验收、最终集成判断
- `OMX` 负责长时间连续执行、team lane 拆分、验证、report 回写
- 每完成一个 tranche，默认自动进入下一个 tranche
- 只有 hard blocker、破坏性操作、或 frozen truth conflict 才允许停机
