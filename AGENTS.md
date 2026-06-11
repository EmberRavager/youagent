# YouAgent Agent Guide

This document is for AI coding agents working on this repository.

## Product direction

YouAgent is a local-first computer agent harness, not only a coding agent.

The public entrypoint should be a single command:

```bash
youagent
```

The expected experience should feel closer to Claude Code or OpenCode:

- `youagent` starts an interactive local agent session.
- `youagent <task>` runs a one-shot local task.
- Slash commands such as `/model`, `/undo`, `/trace`, `/help`, `/exit` work inside the interactive session.
- Legacy subcommands such as `youagent chat`, `youagent serve`, and `youagent tasks` may remain available for compatibility, but they should not be the main product story.

## Core product principles

1. Local-first: operate inside a local workspace by default.
2. Safe by default: avoid destructive actions unless explicitly requested.
3. Traceable: every agent task should be auditable.
4. Reversible where possible: file changes should have an undo path.
5. Tool-using: capabilities come from tools and MCP-mounted extensions.
6. Model-flexible: use OpenAI-compatible provider presets and custom gateways.

## Current important modules

- `src/mini_worker/local_cli.py`: preferred single-entry interactive CLI for `youagent`.
- `src/mini_worker/cli.py`: legacy CLI for `chat`, `serve`, `tasks`, etc.
- `src/mini_worker/code_cli.py`: experimental command set that currently contains reusable snapshot/model helpers.
- `src/mini_worker/runtime.py`: tool-calling loop.
- `src/mini_worker/tools.py`: built-in tools and MCP tool registration.
- `src/mini_worker/llm.py`: OpenAI-compatible chat completions client.
- `src/mini_worker/config.py`: provider presets and model resolution.
- `src/mini_worker/memory.py`: session message persistence.
- `src/mini_worker/settings.py`: local config storage.
- `src/mini_worker/mcp.py`: MCP runtime mounting.

## Memory model

Current memory is session-message persistence only:

```text
.mini_worker/sessions/<session>.json
```

Do not describe it as vector memory or long-term semantic memory unless implemented.

## Trace and undo

Current task traces are written to:

```text
.youagent/runs/*.md
```

Current undo snapshots are written to:

```text
.youagent/snapshots/<timestamp-task>/
```

Undo is file-level snapshot restore. It cannot reverse external side effects from shell commands, databases, network requests, package managers, or other system-level operations.

## Documentation guidance

README should describe YouAgent as a local computer agent harness. Coding tasks are only one use case.

Preferred product line:

```text
Scan → Plan → Preview → Execute → Trace → Undo
```

Avoid over-claiming support for all models. The current low-level client uses OpenAI-compatible `/chat/completions`.

## Future work

- Move reusable snapshot/model logic out of `code_cli.py` into dedicated modules.
- Add explicit approval flow for file writes and risky shell commands.
- Add file-management tools: large-file search, duplicate detection, organize-by-type/date, trash/move/copy.
- Add safer patch/diff preview for file modifications.
- Add first-class slash commands in the interactive session.
- Add tests for CLI, trace, undo, model config and tool safety.
