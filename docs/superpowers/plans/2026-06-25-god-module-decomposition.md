# God-Module Decomposition Plan
**Date:** 2026-06-25
**Identified by:** High Evolutionary Deep Scan
**Status:** Tracked — requires dedicated branch per module

## Problem

Four files exceed 2,500 lines, violating single-responsibility and making PRs
hard to review, test coverage hard to isolate, and hot-reload slow:

| File | Lines | Dominant concern |
|---|---|---|
| `src/tool_implementations.py` | ~3,950 | All LLM tool handlers (manage_tasks, manage_calendar, manage_mcp, manage_endpoints, manage_notes, manage_webhooks, manage_api_tokens, manage_vault…) |
| `routes/email_routes.py` | ~3,410 | Email read/send/search + IMAP sync + sender-sig logic |
| `src/agent_loop.py` | ~3,250 | Full agent execution loop, streaming, tool dispatch, context management |
| `routes/cookbook_routes.py` | ~3,300 | Recipe CRUD + chef agent + cookbook-aware search |

## Decomposition Pattern

Follow the existing `*_helpers.py` pattern already in use (`email_helpers.py`,
`auth_helpers.py`, `task_endpoint.py`):

1. Extract **pure-logic helpers** (parsing, validation, DB queries) into a
   `*_helpers.py` or `*_service.py` module under `src/`.
2. Keep the **route handler** or **tool dispatch entry point** thin — it just
   validates input, calls the helper, and formats the response.
3. New file size target: each resulting file under 800 lines.

## Per-Module Notes

### `src/tool_implementations.py`
- Already has inline sub-handlers (do_manage_tasks, do_manage_calendar, etc.)
- Each `do_manage_*` function is a self-contained unit → move to `src/tool_handlers/manage_*.py`
- Entry point `src/tool_implementations.py` becomes a thin dispatcher (~200 lines)

### `routes/email_routes.py`
- IMAP sync logic → `src/email_sync_helpers.py`
- Sender signature logic → already partially in `builtin_actions.py`; move to `src/sender_sig_service.py`
- Route handlers stay thin

### `src/agent_loop.py`
- Context management → `src/context_manager.py`
- Tool dispatch → `src/tool_dispatcher.py`
- Streaming protocol → `src/streaming_helpers.py`

### `routes/cookbook_routes.py`
- Chef agent logic → `src/chef_agent.py`
- Recipe search/indexing → `src/recipe_search.py`
- Route handlers stay thin

## Execution Order

Do these sequentially, one branch per module, with full test coverage before
merging. Mixing two god-module refactors in one branch creates merge hell.

Suggested order: `tool_implementations.py` → `agent_loop.py` → `email_routes.py` → `cookbook_routes.py`
