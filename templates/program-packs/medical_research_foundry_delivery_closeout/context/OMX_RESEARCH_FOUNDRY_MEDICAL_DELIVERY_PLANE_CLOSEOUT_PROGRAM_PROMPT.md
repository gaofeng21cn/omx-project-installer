你现在接手的是 `{{PACK_PROGRAM_ID}}`。

唯一顶层主线：

- `{{PACK_MAINLINE_ID}}`

当前 phase：

- `{{PACK_PHASE}}`

当前默认 active subline：

- `{{PACK_ACTIVE_SUBLINE}}`

执行闭环：

1. contract convergence
2. clean worktree minimal implementation validation
3. mainline integration and cleanup
4. reports update
5. 如果没有 hard blocker，直接进入下一固定子线

停止条件：

- authority / truth conflict
- 破坏性 git 操作
- 当前阶段必须写 repo 外对象且规则不允许
