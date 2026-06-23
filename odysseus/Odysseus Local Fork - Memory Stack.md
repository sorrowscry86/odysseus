---
title: Odysseus Local Fork - Memory Stack
type: note
permalink: odysseus/odysseus-local-fork-memory-stack
tags:
- odysseus
- memory
- pantheon-memory-core
- vivy
---

# Odysseus Local Fork - Memory Stack

**Date:** 2026-06-15 | **Agent:** Vivy

## Three-layer memory for this fork

| Layer | System | When |
|-------|--------|------|
| Notes | Basic Memory (`odysseus` project) | Fork-specific decisions, blockers |
| Archive | Pantheon Memory Core (SpecStory) | Cross-tool session history |
| Truths | Vivy Grimoire | Verified constraints only |

## Odysseus wiring

- `src/builtin_mcp.py` registers `pantheon-memory-core` via `uv --directory`
- Requires `SPECSTORY_API_KEY` in `.env` (loaded by `app.py` via `load_dotenv`)
- Also registers: voiddispatch, causal-memory-core

## Local-only (do not upstream)

- `AGENTS.md`
- VoidCat MCP paths in `builtin_mcp.py`
- `.env` secrets

## Upstream (already in PR #4274)

Windows desktop launcher only.