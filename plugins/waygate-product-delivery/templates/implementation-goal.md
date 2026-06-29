# Implementation Goal

- status: active
- objective:
- current_task_cursor:

## Stop Rules

- 不要在 TASK 未完成时停止。
- closure validator 未通过时不要 complete goal。
- closure 失败时 goal 保持 active，下一步是修复 closure evidence。
