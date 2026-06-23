---
title: Odysseus Local Fork - Wykeve
type: note
permalink: local-fork/odysseus-local-fork-wykeve
tags:
- odysseus
- local
- voidcat
---

# Odysseus - Wykeve Local Fork

Path: `C:\Users\Wykeve\Projects\The Great Library\odysseus`

## Policy

- **Local customizations stay local** - do not push VoidCat-specific MCP/plugins upstream
- Upstream contributions go to `dev` via fork `sorrowscry86/odysseus`

## Upstream contribution (2026-06-15)

- Windows desktop launcher with preflight checks
- Issue #4273, PR #4274
- Credit: Wykeve (VoidCat), voidcat.org

## Local-only (uncommitted)

- `AGENTS.md` - local fork guidelines
- `src/builtin_mcp.py`, VoidCat MCP wiring
- `mcps/` workspace MCP descriptors

## Run

- Desktop: `Odysseus.vbs` or Desktop shortcut from `build-windows-launcher.ps1`
- Console: `launch-windows.ps1`
- ChromaDB optional: `docker compose up -d chromadb`