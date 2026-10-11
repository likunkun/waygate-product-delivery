# Hooks

V1.0 packages hook assets for future binding. Hook behavior must remain silent while inactive and must read `.product-delivery/state.json` as the source of truth when active.

This plugin does not provide a timed continuation hook and does not send a synthetic `继续` after 20 seconds. Cross-turn continuation is coordinated through a verified Codex Host Goal binding. Human-decision gates remain paused until a matching user response is recorded. The Host Goal owner is the top-level delivery coordinator captured from `CODEX_THREAD_ID`; hooks and spawned review subagents must never claim or transfer that ownership.
In 1.2.2, Stop guard exposes a durable retry_contract when continuation is wait_for_host_goal_retry. The host must schedule the same owner thread at retry_at; this packaged hook asset is not a timer or an installed Paseo scheduler.
