# Repository Guidelines

**Local fork.** This is a customized, local-only deployment. Upstream contributions use the fork; VoidCat-specific changes stay uncommitted here.

## Agent Memory (3-layer stack)

**Layer 1 — Basic Memory** (local notes, default project: `great-library`). At session start: `list_memory_projects`, then `search_notes` / `build_context` for **Session Bootstrap** and active task context. Project `odysseus` holds local-fork notes only. End significant sessions with `write_note` (decisions, blockers, next steps).

**Layer 2 — Pantheon Memory Core** (SpecStory archive via MCP `pantheon-memory-core`). At session start: `query_specstory_archives` for prior work on the active topic; use `retrieve_session_tome` when a session ID is relevant. End significant sessions with `inscribe_pantheon_record` (title + markdown summary). Requires `SPECSTORY_API_KEY` in environment (Odysseus: `.env`; Cursor: `.cursor/mcp.json`).

**Layer 3 — Spirit grimoires** (verified truths per spirit). Consult only when Wykeve assigns a Pantheon spirit; `persona.md` is read-only. Grok sessions use builder context, not a default spirit grimoire.

## Project Structure & Module Organization

Odysseus is a self-hosted AI workspace: FastAPI Python backend, static HTML/JS frontend. It connects to local model servers (Ollama, vLLM, llama.cpp) and remote APIs (OpenAI, OpenRouter).

Three Python layers: **`core/`** (auth, database, middleware, session manager — imported by `src/` and `routes/`), **`src/`** (LLM core, agent loop, tools, memory, research, search), **`routes/`** (thin FastAPI handlers per feature), **`services/`** (isolated domain modules: cookbook/hwfit, memory, search, TTS/STT — prefer for new features), **`mcp_servers/`** (email, image gen, memory, RAG). `app.py` mounts static files, registers routers, wires startup/shutdown.

**`launcher/`** is a WinForms PowerShell desktop dashboard. `launcher/Odysseus.Launcher.ps1` is the main GUI; it dot-sources six modules from `launcher/lib/` (Context, Environment, Server, Browser, PluginHost, Logging) and discovers plugins from `launcher/plugins/`. Entry points: `launch-windows-app.ps1` spawns the launcher headlessly; `Odysseus.vbs` is the silent VBScript wrapper (no console flash). `build-windows-launcher.ps1` installs a Desktop shortcut pointing at `Odysseus.vbs`.

Writable paths and config live in `src/constants.py` (`core/constants.py` re-exports). Use named constants (`AUTH_FILE`, `DATA_DIR`, `internal_api_base()`); never hardcode `/app/...`, `http://localhost:7000`, or relative `data/...` strings.

## Build, Test, and Development Commands

**Run the app:**
```bash
docker compose up -d --build                              # Docker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000   # native (Python 3.11+)
```

**Windows (native):**
```powershell
powershell -ExecutionPolicy Bypass -File .\launch-windows.ps1

# Desktop GUI launcher (status dashboard + preflight checks):
.\Odysseus.vbs                                              # silent, no console flash
powershell -ExecutionPolicy Bypass -File .\launch-windows-app.ps1
# Install Desktop shortcut:
powershell -ExecutionPolicy Bypass -File .\build-windows-launcher.ps1
```

**Tests and checks:**
```bash
python -m pytest                                          # full suite
python -m pytest tests/test_auth_routes.py::test_fn       # single test
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/<changed-file>.js
```

**Docker changes:** `docker compose config`, `docker compose up -d --build`, `docker compose logs --tail=120 odysseus`

## Coding Style & Naming Conventions

No enforced formatter/linter config. Follow the style of the file you edit; PEP 8 for Python. New `src/` and `services/` code tends toward type hints.

UI changes must match existing CSS variables (`--red`, `--fg`, `--bg`), reuse button/card classes, use inline SVG (no emoji), and Fira Code font. Run the app and verify visually — type-checks alone are not enough.

## Testing Guidelines

pytest with `asyncio_mode = "auto"` (`pyproject.toml`). Tests in `tests/`; helpers in `tests/helpers/`; policy in `tests/TESTING_STANDARD.md`. `conftest.py` stubs heavy deps intentionally — do not replace with real imports.

Marker taxonomy via `conftest.py`: `python -m pytest -m area_security`, `python -m pytest -m "area_services and sub_cookbook"`. When adding routes/tools that touch user data, add owner-scope tests (e.g. `test_document_tool_owner_scope.py`).

## Local Change Validation

Before committing locally, run the smallest relevant checks:

```bash
git diff --check
python -m py_compile <changed .py files>
python -m pytest tests/<changed test file>
```

Run the app (`launch-windows.ps1`, `uvicorn`, or `docker compose up`) and confirm the change end-to-end. Attach notes or screenshots for UI work. One logical change per commit; do not weaken tests with `skip`/`xfail` to mask failures.

**Commit messages** (local history): `Area: short imperative phrase` or bare `Fix/Add/Remove phrase` (e.g. `Settings/Add Models: fuse Local Type select`, `Fix Cookbook serve server selection`). Multi-word scope uses `/`.

## Board Room Protocol & Live Development

**Board Room Architecture:** The Board Room allows multiple Spirits to converse. It operates on the `voidcat_routes.py` backend and `voidcat-boardroom.js` frontend. Avatar references are typically located in `C:\Users\Wykeve\Projects\The Great Library\12_Assets\Spirit Cards`.

**Docker Live Mounts:** The `static/`, `src/`, `routes/`, and `app.py` directories are bind-mounted in `docker-compose.yml`. Host-side edits instantly reflect in the container without requiring a rebuild. SearXNG is mapped to port `8282` to avoid conflicts.

**GUI Caching Quirk:** The static file server uses a custom `_RevalidatingStatic` class that forces `Cache-Control: no-cache` for `.js`, `.css`, and `.html`. Because of this, **a hard refresh (Ctrl+F5) is strictly required** in the browser to view any GUI changes made to the `static/` folder.

**Testing Board Room:** Run smoke tests via `python -m pytest tests/test_voidcat_boardroom.py`. **Crucial:** The `PANTHEON_ROOT` environment variable MUST be set to the path of `00_The_Pantheon` on the host before running these tests.

**Model Preference:** For complex reasoning or structural changes, the user prefers the Gemini 3.1 Pro (High) model.