# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is **Learn Claude Code** — an educational repository that teaches harness engineering for AI agents. It demonstrates how to build the "vehicle" (tools, context, permissions) that a model drives. Each of the 12 sessions (`s01`–`s12`) adds one mechanism to a progressively more capable agent, culminating in `agents/s_full.py` which combines them all.

## Commands

### Python agents (backend)

Each agent file is self-contained. Create a `.env` from `.env.example` first:

```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and MODEL_ID
```

Run any session directly:

```bash
python agents/s01_agent_loop.py    # The basic agent loop
python agents/s02_tool_use.py      # Tool dispatch (bash, read, write, edit)
python agents/s_full.py            # Full reference (all mechanisms)
```

### Web frontend

```bash
cd web
npm install
npm run dev         # Starts Next.js dev server on http://localhost:3000
npm run build       # Production build (includes content extraction step)
```

## Architecture

```
agents/          # Python harness implementations (s01-s12 + s_full)
  s01            # The core agent loop: while stop_reason == "tool_use"
  s02            # Tool use: bash, read, write, edit dispatch
  s03            # TodoWrite: structured progress tracking
  s04            # Subagents: context-isolated child agents
  s05            # Skill loading: on-demand domain knowledge injection
  s06            # Context compaction: auto-compress long conversations
  s07            # Task system: persistent task state beyond conversation
  s08            # Background tasks: async shell execution
  s09            # Agent teams: spawn teammates with inbox communication
  s10            # Team protocols: plan gates, shutdown handshakes
  s11            # Autonomous agents: auto-claim loop, solo→idle→work cycle
  s12            # Worktree task isolation: git worktree for safe task execution
  s_full         # All mechanisms combined (capstone reference, not teaching)
docs/            # Markdown docs in en/, ja/, zh/ mirroring each session
web/             # Next.js app for interactive learning (React 19, Tailwind 4)
skills/          # Claude Code skill definitions (agent-builder, code-review, etc.)
```

### Key patterns

- **Agent loop**: `while stop_reason == "tool_use":` — feed tool results back to the model until it decides to stop. This pattern is present in every session file.
- **Tool dispatch**: Tools defined as JSON schemas, dispatched via a dict mapping name→handler function. Each session adds new tools.
- **Anthropic-compatible API**: Uses `ANTHROPIC_BASE_URL` to support third-party providers (MiniMax, GLM, Kimi, DeepSeek). The env pattern is standardized across all agent files.
- **Progressive learning**: Each session file is standalone and introduces exactly one new concept. Sessions build on each other but don't import from each other.
- **The model IS the agent**: The code is the harness. Complex behavior comes from the model's reasoning, not from procedural orchestration.
