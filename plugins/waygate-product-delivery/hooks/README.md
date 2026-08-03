# Hooks

V1.0 packages hook assets for future binding. Hook behavior must remain silent while inactive and must read `.product-delivery/state.json` as the source of truth when active.

This plugin does not provide a timed continuation hook and does not send a synthetic `继续` after 20 seconds. Cross-turn continuation is coordinated through a verified Codex Host Goal binding. Human-decision gates remain paused until a matching user response is recorded. The Host Goal owner is the top-level delivery coordinator captured from `CODEX_THREAD_ID`; hooks and spawned review subagents must never claim or transfer that ownership.
