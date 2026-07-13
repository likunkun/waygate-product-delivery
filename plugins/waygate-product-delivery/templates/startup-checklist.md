# Product Delivery Startup Checklist

- Invoke `superpowers:using-superpowers` before any task action.
- Invoke `planning-with-files` and run its session catchup.
- Read or create `task_plan.md`, `findings.md`, and `progress.md`.
- Create or recover `.product-delivery/state.json`.
- Record the current feature slug and blocked gates in state.
- Plain startup enters `startup_mode_selection` and asks for execution and review modes together.
- `启动交付，自动模式，多 Agent 模式` uses stage-specific model profiles and authorizes spawned review agents.
- `启动交付，全速模式，多 Agent 模式` requires one uniform full-speed model profile for the main thread and all subagents.
- Model profile precedence is delivery override, project config, user config, then built-in defaults.
- Stage agents use `fork_context=false`; only the main coordinator writes canonical state.
