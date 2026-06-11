# YouAgent Architecture

YouAgent is a local-first computer agent harness. The codebase should be organized by responsibility instead of putting all modules directly under `src/mini_worker/`.

## Target package layout

```text
src/mini_worker/
├── entrypoints/          # Console and public CLI entrypoints
│   └── local.py          # `youagent` entrypoint
├── core/                 # Agent loop and orchestration
│   ├── runtime.py        # AgentRuntime / tool-call loop
│   └── events.py         # Event and trace event model (planned)
├── models/               # LLM provider resolution and clients
│   ├── config.py         # Provider presets and API config
│   └── llm.py            # ChatClient
├── tools/                # Tool registry and built-in tools
│   ├── registry.py       # ToolRegistry / ToolSpec
│   ├── filesystem.py     # File tools (planned split)
│   ├── shell.py          # Shell tools (planned split)
│   └── web.py            # Fetch / browser tools (planned split)
├── workspace/            # Workspace-specific context and state
│   ├── context.py        # @file context, context budget, plan detection
│   ├── memory.py         # SessionMemory
│   ├── settings.py       # Workspace config store
│   └── snapshots.py      # Undo snapshots (planned split)
├── skill_runtime/        # Local skills and reusable playbooks
│   └── registry.py       # SkillRegistry / Skill model
├── security/             # Policy and approvals
│   ├── policy.py         # SecurityPolicy
│   └── approval.py       # Approval Center (planned)
└── compat/               # Backwards-compatible module shims (planned)
```

## Current state

The first refactor step has landed:

- `src/mini_worker/entrypoints/local.py` is the new public console entrypoint.
- `pyproject.toml` now points `youagent` to `mini_worker.entrypoints.local:main`.
- Existing root modules such as `local_cli.py`, `context.py`, `skills.py`, `runtime.py`, `tools.py`, `llm.py`, and `settings.py` remain in place for compatibility.

This avoids breaking imports while creating a clear migration path.

## Migration rules

1. Do not add new large modules directly under `src/mini_worker/` unless they are temporary shims.
2. Put CLI-only code under `entrypoints/` or a future `cli/` package.
3. Put agent loop code under `core/`.
4. Put model/provider code under `models/`.
5. Put file, shell, web, and MCP tools under `tools/`.
6. Put AGENTS.md loading, @file context, memory, settings, and snapshots under `workspace/`.
7. Put reusable Skill logic under `skill_runtime/`.
8. Put policy, risk classification, and user approvals under `security/`.
9. Keep old module paths as shims during migration to avoid breaking CLI and tests.
10. Move one subsystem at a time, with a small compatibility wrapper for each move.

## Recommended next refactor order

1. Move `context.py` to `workspace/context.py` and keep `context.py` as a re-export shim.
2. Move `skills.py` to `skill_runtime/registry.py` and keep `skills.py` as a re-export shim.
3. Move `settings.py` and `memory.py` to `workspace/` with shims.
4. Move `llm.py` and `config.py` to `models/` with shims.
5. Split `tools.py` into registry, filesystem, shell, web, and browser modules.
6. Move snapshot helpers from `code_cli.py` into `workspace/snapshots.py`.
7. Split `local_cli.py` into smaller command modules once the dependencies are in place.

## Why this matters

The goal is to make the project explainable in interviews and maintainable in practice:

```text
EntryPoint → Runtime → Model Client → Tool Registry → Workspace Context → Trace/Undo
```

This structure makes it clear that YouAgent is not just a CLI script. It is a harness with separate layers for execution, context, tools, skills, security, and persistence.
