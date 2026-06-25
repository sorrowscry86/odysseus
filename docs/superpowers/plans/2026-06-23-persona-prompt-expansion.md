# Persona & Prompt Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Pantheon spirits as solo-chat presets, expand the character template system with category-awareness and avatar support, fix group chat character discovery, add a character management page, and enforce persona.md immutability at the application layer.

**Architecture:** The existing `character_name` → `get_spirit_context()` injection path in `chat_processor.py` already handles Pantheon context loading. Spirit presets set `spirit_name` on the preset config, which routes through `chat_handler.py` to set `character_name = spirit_name`, triggering the existing injection. The frontend fetches the spirit roster dynamically from a new `/api/spirits` endpoint backed by the Pantheon mount.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, vanilla JS (ES modules), existing `src/spirit_engine.py`, `src/dispatcher.py`, `routes/preset_routes.py`

## Global Constraints

- No new Python dependencies — use only stdlib + packages already in the project
- All Pantheon write paths must call `_assert_not_immutable()` before opening files
- `category` field on templates: only valid values are `"character"` and `"spirit"`
- Avatar files stored in `{data_dir}/avatars/`, served at `/api/presets/avatars/{filename}`
- Max avatar upload size: 2MB; allowed formats: PNG, JPG, JPEG, WebP, GIF
- Spirit presets skip the `"Your name is {name}."` prefix — the persona.md establishes identity
- `grimoire_writes` defaults `true`; when `false`, `update_grimoire` is not offered (in agent mode) and stored as a preference; non-agent chat has no tools regardless
- Section 5 of the spec (new character personas) is **deferred** — not implemented in this plan
- Frontend: no new npm packages; extend existing ES module patterns

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/voidcat_tools.py` | Modify | Add `_assert_not_immutable()`, guard in `execute_update_grimoire` |
| `routes/preset_routes.py` | Modify | Add `avatar_url`/`category` to `UserTemplateRequest`; add avatar upload + serve endpoints; avatar cleanup on delete |
| `src/preset_manager.py` | Modify | Store `data_dir`; avatar cleanup in `delete_user_template` |
| `routes/voidcat_routes.py` | Modify | Add `GET /api/spirits` |
| `routes/chat_helpers.py` | Modify | Add `spirit_name`/`grimoire_writes` to `PresetInfo`; update `extract_preset` |
| `src/chat_handler.py` | Modify | Extend `validate_and_extract_preset()` for spirit presets |
| `static/js/presets.js` | Modify | `category` on `PROMPT_TEMPLATES`; spirits optgroup; hypothetical toggle; avatar in chip |
| `static/js/group.js` | Modify | Fix `_getCharacterList()` to fetch all saved templates; exclude spirits |
| `static/characters.html` | Create | Character management page HTML |
| `static/js/characterManager.js` | Create | Character management page JS |
| `tests/test_voidcat_tools_immutable.py` | Create | Immutability guard tests |
| `tests/test_spirits_endpoint.py` | Create | `/api/spirits` endpoint tests |
| `tests/test_preset_avatar.py` | Create | Avatar upload/serve/cleanup tests |
| `tests/test_spirit_preset_inference.py` | Create | Spirit preset inference in chat_handler |

---

## Task 1: Persona.md write protection

**Files:**
- Modify: `src/voidcat_tools.py`
- Create: `tests/test_voidcat_tools_immutable.py`

**Interfaces:**
- Produces: `_assert_not_immutable(path: str) -> None` — raises `PermissionError` if path basename is `persona.md`

- [ ] **Step 1: Write the failing test**

Create `tests/test_voidcat_tools_immutable.py`:

```python
import os
import pytest
from src.voidcat_tools import _assert_not_immutable, execute_update_grimoire


def test_assert_not_immutable_blocks_persona(tmp_path):
    persona_path = str(tmp_path / "persona.md")
    with pytest.raises(PermissionError, match="immutable"):
        _assert_not_immutable(persona_path)


def test_assert_not_immutable_allows_grimoire(tmp_path):
    grimoire_path = str(tmp_path / "grimoire.md")
    # Should not raise
    _assert_not_immutable(grimoire_path)


def test_assert_not_immutable_allows_other_files(tmp_path):
    other_path = str(tmp_path / "notes.md")
    _assert_not_immutable(other_path)  # no raise


def test_execute_update_grimoire_blocks_persona_target(tmp_path, monkeypatch):
    """If spirit_dir somehow contains only persona.md and no grimoire.md,
    the function should not write persona.md even if grimoire path is constructed."""
    # Patch PANTHEON_ROOT to tmp_path
    monkeypatch.setattr("src.voidcat_tools.PANTHEON_ROOT", str(tmp_path))
    spirit_dir = tmp_path / "ryuzu"
    spirit_dir.mkdir()
    # No grimoire.md — it gets created by the function, so test the guard indirectly
    # by verifying a direct persona.md write raises
    with pytest.raises(PermissionError):
        _assert_not_immutable(str(spirit_dir / "persona.md"))
```

- [ ] **Step 2: Run test — expect ImportError or NameError**

```
pytest tests/test_voidcat_tools_immutable.py -v
```

Expected: `ImportError: cannot import name '_assert_not_immutable'`

- [ ] **Step 3: Add `_assert_not_immutable` and guard to `src/voidcat_tools.py`**

Add after the `logger` line:

```python
def _assert_not_immutable(path: str) -> None:
    """Raise PermissionError if path targets persona.md — immutable by law."""
    if os.path.basename(path) == "persona.md":
        raise PermissionError(
            f"persona.md is immutable — writes are forbidden: {path}"
        )
```

In `execute_update_grimoire`, add the guard before opening the file:

```python
    try:
        _assert_not_immutable(grimoire_path)  # ← add this line
        with open(grimoire_path, "a", encoding="utf-8") as f:
```

- [ ] **Step 4: Run tests — expect PASS**

```
pytest tests/test_voidcat_tools_immutable.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```
git add src/voidcat_tools.py tests/test_voidcat_tools_immutable.py
git commit -m "feat: enforce persona.md immutability at application layer"
```

---

## Task 2: Template model — avatar_url and category fields

**Files:**
- Modify: `routes/preset_routes.py` (extend `UserTemplateRequest`)
- Modify: `src/preset_manager.py` (store `data_dir`; cleanup avatar on delete)
- Create: `tests/test_preset_avatar.py`

**Interfaces:**
- `UserTemplateRequest` gains: `avatar_url: str = ""`, `category: str = "character"`
- `PresetManager.__init__` now stores `self.data_dir = data_dir`
- `PresetManager.delete_user_template(template_id)` deletes `{data_dir}/avatars/{filename}` if `avatar_url` set

- [ ] **Step 1: Write failing tests**

Create `tests/test_preset_avatar.py`:

```python
import os
import json
import pytest
from src.preset_manager import PresetManager


@pytest.fixture
def pm(tmp_path):
    return PresetManager(str(tmp_path))


def test_save_template_with_avatar_url(pm):
    tmpl = {
        "id": "test-001",
        "name": "Razor",
        "system_prompt": "Be brief.",
        "temperature": 0.4,
        "max_tokens": 0,
        "avatar_url": "/api/presets/avatars/test-001.png",
        "category": "character",
    }
    assert pm.save_user_template(tmpl)
    saved = pm.get_user_templates()
    assert saved[0]["avatar_url"] == "/api/presets/avatars/test-001.png"
    assert saved[0]["category"] == "character"


def test_delete_template_removes_avatar_file(pm, tmp_path):
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()
    avatar_file = avatars_dir / "test-002.png"
    avatar_file.write_bytes(b"fake-png")

    tmpl = {
        "id": "test-002",
        "name": "Spark",
        "system_prompt": "Be bright.",
        "temperature": 1.0,
        "max_tokens": 0,
        "avatar_url": "/api/presets/avatars/test-002.png",
        "category": "character",
    }
    pm.save_user_template(tmpl)
    pm.delete_user_template("test-002")

    assert not avatar_file.exists()


def test_delete_template_no_avatar_does_not_crash(pm):
    tmpl = {
        "id": "test-003",
        "name": "Socrates",
        "system_prompt": "Only questions.",
        "temperature": 0.9,
        "max_tokens": 0,
        "avatar_url": "",
        "category": "character",
    }
    pm.save_user_template(tmpl)
    pm.delete_user_template("test-003")  # should not raise
```

- [ ] **Step 2: Run tests — expect failures**

```
pytest tests/test_preset_avatar.py -v
```

Expected: 3 FAILED (avatar_url not stored, delete_user_template doesn't clean up)

- [ ] **Step 3: Update `routes/preset_routes.py` — extend `UserTemplateRequest`**

```python
class UserTemplateRequest(BaseModel):
    id: str = ""
    name: str = Field(..., min_length=1, max_length=100)
    system_prompt: str = Field("", max_length=10000)
    temperature: float = Field(1.0, ge=0.0, le=2.0)
    max_tokens: int = Field(0, ge=0, le=65536)
    avatar_url: str = Field("", max_length=500)
    category: str = Field("character", pattern="^(character|spirit)$")
```

- [ ] **Step 4: Update `src/preset_manager.py` — store data_dir and clean avatar on delete**

In `__init__`, add `self.data_dir = data_dir` after `self.presets_file = ...`.

Replace `delete_user_template`:

```python
def delete_user_template(self, template_id: str) -> bool:
    """Delete a user template by id, and its avatar file if present."""
    templates = self.presets.get("user_templates", [])
    target = next((t for t in templates if t.get("id") == template_id), None)
    # Clean up avatar file if one was stored
    if target and target.get("avatar_url"):
        try:
            filename = os.path.basename(target["avatar_url"])
            avatar_path = os.path.join(self.data_dir, "avatars", filename)
            if os.path.isfile(avatar_path):
                os.remove(avatar_path)
        except Exception as e:
            logger.warning(f"Failed to remove avatar file for {template_id}: {e}")
    self.presets["user_templates"] = [t for t in templates if t.get("id") != template_id]
    return self.save(self.presets)
```

- [ ] **Step 5: Run tests — expect PASS**

```
pytest tests/test_preset_avatar.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Commit**

```
git add routes/preset_routes.py src/preset_manager.py tests/test_preset_avatar.py
git commit -m "feat: add avatar_url and category fields to template model"
```

---

## Task 3: GET /api/spirits endpoint

**Files:**
- Modify: `routes/voidcat_routes.py`
- Create: `tests/test_spirits_endpoint.py`

**Interfaces:**
- Produces: `GET /api/spirits` → `[{"folder": str, "display_name": str, "has_grimoire": bool}]`

- [ ] **Step 1: Write failing test**

Create `tests/test_spirits_endpoint.py`:

```python
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def pantheon(tmp_path):
    """Create a minimal Pantheon structure."""
    for name, has_grimoire in [("ryuzu", True), ("beatrice", True), ("echo", False)]:
        spirit_dir = tmp_path / name
        spirit_dir.mkdir()
        (spirit_dir / "persona.md").write_text(f"# {name} persona")
        if has_grimoire:
            (spirit_dir / "grimoire.md").write_text(f"# {name} grimoire")
    return tmp_path


def test_get_spirits_returns_roster(pantheon, monkeypatch):
    monkeypatch.setenv("PANTHEON_ROOT", str(pantheon))
    # Reimport to pick up new env
    import importlib
    import src.dispatcher as disp
    disp._KNOWN_SPIRITS = []  # reset cache
    monkeypatch.setattr("src.dispatcher.PANTHEON_ROOT", str(pantheon))

    from routes.voidcat_routes import setup_voidcat_routes
    from unittest.mock import MagicMock
    router = setup_voidcat_routes(MagicMock())

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/spirits")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    folders = {s["folder"] for s in data}
    assert "ryuzu" in folders
    assert "beatrice" in folders
    echo_entry = next(s for s in data if s["folder"] == "echo")
    assert echo_entry["has_grimoire"] is False
    ryuzu_entry = next(s for s in data if s["folder"] == "ryuzu")
    assert ryuzu_entry["has_grimoire"] is True


def test_get_spirits_returns_empty_when_pantheon_missing(monkeypatch):
    monkeypatch.setattr("src.dispatcher.PANTHEON_ROOT", "/nonexistent/path")
    import src.dispatcher as disp
    disp._KNOWN_SPIRITS = []

    from routes.voidcat_routes import setup_voidcat_routes
    from unittest.mock import MagicMock
    router = setup_voidcat_routes(MagicMock())

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/spirits")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run test — expect failure**

```
pytest tests/test_spirits_endpoint.py -v
```

Expected: FAILED — route not found

- [ ] **Step 3: Add `GET /api/spirits` to `routes/voidcat_routes.py`**

Add inside `setup_voidcat_routes`, after the existing routes:

```python
    @router.get("/api/spirits")
    async def get_spirits():
        """Return the spirit roster from the Pantheon mount."""
        try:
            from src.dispatcher import _load_spirit_roster, _display_name, PANTHEON_ROOT
            roster = _load_spirit_roster()
            result = []
            for folder in roster:
                grimoire_path = os.path.join(PANTHEON_ROOT, folder, "grimoire.md")
                result.append({
                    "folder": folder,
                    "display_name": _display_name(folder),
                    "has_grimoire": os.path.isfile(grimoire_path),
                })
            return result
        except Exception as e:
            logger.warning(f"Failed to load spirit roster: {e}")
            return []
```

Ensure `import os` is at the top of `voidcat_routes.py` (it already is).

- [ ] **Step 4: Run tests — expect PASS**

```
pytest tests/test_spirits_endpoint.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```
git add routes/voidcat_routes.py tests/test_spirits_endpoint.py
git commit -m "feat: add GET /api/spirits endpoint for dynamic Pantheon roster"
```

---

## Task 4: Avatar upload and serve endpoints

**Files:**
- Modify: `routes/preset_routes.py`
- Create: `tests/test_preset_avatar_endpoints.py`

**Interfaces:**
- Produces: `POST /api/presets/templates/{template_id}/avatar` → `{"success": bool, "avatar_url": str}`
- Produces: `GET /api/presets/avatars/{filename}` → file response

- [ ] **Step 1: Write failing tests**

Create `tests/test_preset_avatar_endpoints.py`:

```python
import io
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.preset_manager import PresetManager
from routes.preset_routes import setup_preset_routes


@pytest.fixture
def app(tmp_path):
    pm = PresetManager(str(tmp_path))
    # Save a template to upload avatar for
    pm.save_user_template({
        "id": "tmpl-001",
        "name": "Razor",
        "system_prompt": "Be brief.",
        "temperature": 0.4,
        "max_tokens": 0,
        "avatar_url": "",
        "category": "character",
    })
    fapp = FastAPI()
    fapp.include_router(setup_preset_routes(pm))
    return fapp, pm, tmp_path


def test_upload_avatar_saves_file(app):
    fapp, pm, tmp_path = app
    client = TestClient(fapp)

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header
    resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("avatar.png", io.BytesIO(fake_png), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "avatar_url" in data
    assert data["avatar_url"].startswith("/api/presets/avatars/")

    # File exists on disk
    filename = os.path.basename(data["avatar_url"])
    assert os.path.isfile(tmp_path / "avatars" / filename)


def test_upload_avatar_rejects_oversized_file(app):
    fapp, _, _ = app
    client = TestClient(fapp)
    big_data = b"x" * (2 * 1024 * 1024 + 1)  # 2MB + 1 byte
    resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("big.png", io.BytesIO(big_data), "image/png")},
    )
    assert resp.status_code == 413


def test_serve_avatar_returns_file(app):
    fapp, pm, tmp_path = app
    client = TestClient(fapp)

    # Upload first
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    upload_resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("av.png", io.BytesIO(fake_png), "image/png")},
    )
    filename = os.path.basename(upload_resp.json()["avatar_url"])

    serve_resp = client.get(f"/api/presets/avatars/{filename}")
    assert serve_resp.status_code == 200
    assert serve_resp.content == fake_png


def test_serve_avatar_404_for_missing(app):
    fapp, _, _ = app
    client = TestClient(fapp)
    resp = client.get("/api/presets/avatars/nonexistent.png")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect failure**

```
pytest tests/test_preset_avatar_endpoints.py -v
```

Expected: 4 FAILED — routes not found

- [ ] **Step 3: Add avatar endpoints to `routes/preset_routes.py`**

Add these imports at the top if not already present:

```python
import os
import shutil
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
```

Add inside `setup_preset_routes(preset_manager)`:

```python
    _ALLOWED_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    _MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB

    @router.post("/api/presets/templates/{template_id}/avatar")
    async def upload_avatar(
        template_id: str,
        file: UploadFile = File(...),
        _admin: None = Depends(require_admin),
    ):
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in _ALLOWED_AVATAR_EXTS:
            raise HTTPException(415, f"Unsupported format: {ext}")

        data = await file.read()
        if len(data) > _MAX_AVATAR_BYTES:
            raise HTTPException(413, "Avatar exceeds 2MB limit")

        avatars_dir = os.path.join(preset_manager.data_dir, "avatars")
        os.makedirs(avatars_dir, exist_ok=True)

        filename = f"{template_id}{ext}"
        dest = os.path.join(avatars_dir, filename)

        # Security: ensure dest stays inside avatars_dir
        if not os.path.abspath(dest).startswith(os.path.abspath(avatars_dir)):
            raise HTTPException(400, "Invalid template_id")

        with open(dest, "wb") as f_out:
            f_out.write(data)

        avatar_url = f"/api/presets/avatars/{filename}"

        # Update avatar_url on the template record
        templates = preset_manager.get_user_templates()
        for t in templates:
            if t.get("id") == template_id:
                t["avatar_url"] = avatar_url
                preset_manager.save_user_template(t)
                break

        return {"success": True, "avatar_url": avatar_url}

    @router.get("/api/presets/avatars/{filename}")
    async def serve_avatar(filename: str):
        # Security: reject path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(400, "Invalid filename")
        avatars_dir = os.path.join(preset_manager.data_dir, "avatars")
        path = os.path.join(avatars_dir, filename)
        if not os.path.isfile(path):
            raise HTTPException(404, "Avatar not found")
        return FileResponse(path)
```

- [ ] **Step 4: Run tests — expect PASS**

```
pytest tests/test_preset_avatar_endpoints.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```
git add routes/preset_routes.py tests/test_preset_avatar_endpoints.py
git commit -m "feat: avatar upload and serve endpoints for character templates"
```

---

## Task 5: Spirit preset inference in chat pipeline

**Files:**
- Modify: `routes/chat_helpers.py` (`PresetInfo` dataclass + `extract_preset`)
- Modify: `src/chat_handler.py` (`validate_and_extract_preset`)
- Create: `tests/test_spirit_preset_inference.py`

**Interfaces:**
- `PresetInfo` gains: `spirit_name: str = ""`, `grimoire_writes: bool = True`
- `validate_and_extract_preset` returns 6-tuple: `(temperature, max_tokens, system_prompt, character_name, spirit_name, grimoire_writes)`
- When `spirit_name` set: `character_name` is set to `spirit_name` (triggers existing SDS injection in `chat_processor.py`); "Your name is X" prefix is skipped; `system_prompt` left None (Pantheon handles it)

- [ ] **Step 1: Write failing tests**

Create `tests/test_spirit_preset_inference.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def _make_handler(preset_data: dict):
    from src.chat_handler import ChatHandler
    pm = MagicMock()
    pm.presets = {"custom": preset_data}
    handler = ChatHandler(
        session_manager=MagicMock(),
        memory_manager=MagicMock(),
        chat_processor=MagicMock(),
        research_handler=MagicMock(),
        preset_manager=pm,
        upload_handler=MagicMock(),
    )
    return handler


def test_spirit_preset_sets_character_name_to_spirit_name():
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "ryuzu",
        "grimoire_writes": True,
        "system_prompt": "",
        "character_name": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    })
    temperature, max_tokens, system_prompt, character_name, spirit_name, grimoire_writes = (
        handler.validate_and_extract_preset("custom")
    )
    assert character_name == "ryuzu"
    assert spirit_name == "ryuzu"
    assert grimoire_writes is True
    # No "Your name is ryuzu." prefix — system_prompt should be None
    assert system_prompt is None


def test_spirit_preset_no_name_prefix():
    """Spirit presets must NOT prepend 'Your name is X.' — persona.md owns identity."""
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "beatrice",
        "grimoire_writes": False,
        "system_prompt": "",
        "character_name": "",
        "temperature": 1.0,
        "max_tokens": 0,
    })
    _, _, system_prompt, _, _, grimoire_writes = handler.validate_and_extract_preset("custom")
    assert system_prompt is None or "Your name is" not in (system_prompt or "")
    assert grimoire_writes is False


def test_character_preset_still_gets_name_prefix():
    """Regular character presets (no spirit_name) must still get 'Your name is X.'"""
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "",
        "grimoire_writes": True,
        "system_prompt": "Be helpful.",
        "character_name": "Spark",
        "temperature": 1.0,
        "max_tokens": 0,
    })
    _, _, system_prompt, character_name, spirit_name, _ = handler.validate_and_extract_preset("custom")
    assert character_name == "Spark"
    assert spirit_name == ""
    assert "Your name is Spark." in system_prompt


def test_grimoire_writes_defaults_true_when_absent():
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "echo",
        "system_prompt": "",
        "character_name": "",
        "temperature": 1.0,
        "max_tokens": 0,
        # grimoire_writes not set — should default True
    })
    _, _, _, _, _, grimoire_writes = handler.validate_and_extract_preset("custom")
    assert grimoire_writes is True
```

- [ ] **Step 2: Run tests — expect FAIL**

```
pytest tests/test_spirit_preset_inference.py -v
```

Expected: FAILED — `validate_and_extract_preset` returns 4-tuple, not 6

- [ ] **Step 3: Update `src/chat_handler.py`**

Replace `validate_and_extract_preset`:

```python
def validate_and_extract_preset(self, preset_id: Optional[str]) -> tuple:
    """Returns (temperature, max_tokens, preset_system_prompt, character_name,
    spirit_name, grimoire_writes)."""
    if preset_id and preset_id not in self.preset_manager.presets:
        raise HTTPException(400, f"Invalid preset_id: {preset_id}")

    temperature = DEFAULT_TEMPERATURE
    max_tokens = DEFAULT_MAX_TOKENS
    preset_system_prompt = None
    character_name = ""
    spirit_name = ""
    grimoire_writes = True

    if preset_id and preset_id in self.preset_manager.presets:
        preset = self.preset_manager.presets[preset_id]
        if preset.get("enabled") is False:
            logger.info(f"Preset {preset_id} is disabled, using defaults")
            return temperature, max_tokens, preset_system_prompt, character_name, spirit_name, grimoire_writes

        spirit_name = preset.get("spirit_name", "") or ""
        grimoire_writes = preset.get("grimoire_writes", True)

        if spirit_name:
            # Spirit preset: route context loading through get_spirit_context via
            # the existing character_name injection path in chat_processor.py.
            # Do NOT prepend "Your name is X." — the persona.md owns identity.
            character_name = spirit_name
        else:
            # Character preset: existing behavior
            if preset.get("system_prompt"):
                preset_system_prompt = preset["system_prompt"]
            character_name = preset.get("character_name", "")
            if character_name:
                name_line = f"Your name is {character_name}."
                if preset_system_prompt:
                    preset_system_prompt = f"{name_line} {preset_system_prompt}"
                else:
                    preset_system_prompt = name_line

        if "temperature" in preset:
            temperature = preset["temperature"]
        if "max_tokens" in preset:
            max_tokens = preset["max_tokens"]

    logger.info(f"Preset {preset_id}: temp={temperature}, max_tokens={max_tokens}, spirit={spirit_name}")
    return temperature, max_tokens, preset_system_prompt, character_name, spirit_name, grimoire_writes
```

- [ ] **Step 4: Update `routes/chat_helpers.py`**

Add fields to `PresetInfo`:

```python
@dataclass
class PresetInfo:
    """Extracted preset parameters."""
    temperature: Optional[float]
    max_tokens: Optional[int]
    system_prompt: Optional[str]
    character_name: Optional[str]
    spirit_name: str = ""
    grimoire_writes: bool = True
```

Update `extract_preset`:

```python
def extract_preset(chat_handler, preset_id) -> PresetInfo:
    """Extract preset parameters via chat_handler."""
    temperature, max_tokens, system_prompt, char_name, spirit_name, grimoire_writes = (
        chat_handler.validate_and_extract_preset(preset_id)
    )
    return PresetInfo(
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        character_name=char_name,
        spirit_name=spirit_name,
        grimoire_writes=grimoire_writes,
    )
```

- [ ] **Step 5: Run tests — expect PASS**

```
pytest tests/test_spirit_preset_inference.py -v
```

Expected: 4 PASSED

- [ ] **Step 6: Run full test suite — check for regressions**

```
pytest tests/ -x -q 2>&1 | tail -20
```

Expected: no new failures. If `extract_preset` callers break, fix them (they unpack `PresetInfo` fields by attribute, not positionally — should be safe).

- [ ] **Step 7: Commit**

```
git add src/chat_handler.py routes/chat_helpers.py tests/test_spirit_preset_inference.py
git commit -m "feat: spirit preset inference — live Pantheon context via spirit_name"
```

---

## Task 6: Frontend — category field, spirits optgroup, hypothetical toggle, avatar chip

**Files:**
- Modify: `static/js/presets.js`

No automated tests for this task — verify manually (steps below).

- [ ] **Step 1: Add `category: "character"` to all `PROMPT_TEMPLATES` entries**

In `static/js/presets.js`, update each entry in `PROMPT_TEMPLATES`:

```js
export const PROMPT_TEMPLATES = [
  {
    id: 'socrates',
    name: 'Socrates',
    temperature: 0.9,
    isPreset: true,
    isCharacter: true,
    category: 'character',     // ← add
    prompt: "Never answer directly..."
  },
  {
    id: 'razor',
    name: 'Razor',
    temperature: 0.4,
    isPreset: true,
    isCharacter: true,
    noName: true,
    category: 'character',     // ← add
    prompt: "Strip everything to the bone..."
  },
  // repeat for nietzsche, spark, odysseus
];
```

- [ ] **Step 2: Add spirit fetch and optgroup to `_populateCharSelect`**

Replace the `_populateCharSelect` function:

```js
async function _populateCharSelect() {
  const select = document.getElementById('char-template-select');
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = '<option value="__default__">Default (no persona)</option>';

  const savedNames = new Set(userTemplates.map(t => t.name));

  // Characters group — saved templates
  const savedChars = userTemplates.filter(t => (t.category || 'character') === 'character');
  if (savedChars.length) {
    const group = document.createElement('optgroup');
    group.label = 'Saved';
    savedChars.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.name;
      opt.textContent = t.name;
      group.appendChild(opt);
    });
    select.appendChild(group);
  }

  // Built-in characters group
  const hiddenPresets = loadStoredArray('odysseus-hidden-presets');
  const builtins = PROMPT_TEMPLATES.filter(
    t => !savedNames.has(t.name) && !hiddenPresets.includes(t.name) && t.category === 'character'
  );
  if (builtins.length) {
    const group = document.createElement('optgroup');
    group.label = 'Characters';
    builtins.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.name;
      opt.textContent = t.name;
      group.appendChild(opt);
    });
    select.appendChild(group);
  }

  // Spirits group — fetched from API
  try {
    const res = await fetch(`${API_BASE}/api/spirits`);
    if (res.ok) {
      const spirits = await res.json();
      if (spirits.length) {
        const group = document.createElement('optgroup');
        group.label = 'Spirits';
        spirits.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.display_name;
          opt.dataset.spiritFolder = s.folder;
          opt.dataset.hasGrimoire = s.has_grimoire ? 'true' : 'false';
          opt.textContent = s.display_name;
          group.appendChild(opt);
        });
        select.appendChild(group);
      }
    }
  } catch (e) {
    console.warn('[presets] Failed to load spirit roster:', e);
  }

  if (currentVal) select.value = currentVal;
}
```

Make `_populateCharSelect` async and update `loadUserTemplates` to await it:

```js
async function loadUserTemplates() {
  try {
    const res = await fetch(`${API_BASE}/api/presets/templates`);
    if (res.ok) {
      userTemplates = await res.json();
    } else {
      userTemplates = [];
    }
  } catch (e) {
    userTemplates = [];
  }
  await _populateCharSelect();
}
```

- [ ] **Step 3: Add hypothetical mode toggle to the modal HTML**

In `static/index.html` (or wherever the preset modal lives), add inside the character tab panel, after the spirit template select:

```html
<div id="spirit-hypothetical-row" style="display:none; margin-top:8px;">
  <label style="display:flex; align-items:center; gap:8px; font-size:12px; cursor:pointer;">
    <input type="checkbox" id="spirit-hypothetical-toggle">
    <span>Hypothetical mode — prevent grimoire writes</span>
  </label>
  <div style="font-size:10px; opacity:0.5; margin-top:3px; margin-left:24px;">
    Conversations won't be recorded to this spirit's grimoire.
  </div>
</div>
```

- [ ] **Step 4: Wire spirit selection to show the toggle and store spirit_name**

In `initNameDropdown()`, inside the `select.addEventListener('change', ...)` handler, add after the `_tryLoadTemplate(val)` call:

```js
    // Spirit detection
    const selectedOpt = select.options[select.selectedIndex];
    const spiritFolder = selectedOpt ? selectedOpt.dataset.spiritFolder : '';
    const hasGrimoire = selectedOpt ? selectedOpt.dataset.hasGrimoire === 'true' : false;
    const hypotheticalRow = document.getElementById('spirit-hypothetical-row');
    const hypotheticalToggle = document.getElementById('spirit-hypothetical-toggle');
    const nameRow = document.getElementById('char-name-row');

    if (spiritFolder) {
      // Spirit selected — hide name row, show hypothetical toggle
      if (nameRow) nameRow.style.display = 'none';
      if (hypotheticalRow) {
        hypotheticalRow.style.display = '';
        if (hypotheticalToggle) {
          hypotheticalToggle.disabled = !hasGrimoire;
          hypotheticalToggle.checked = false;
          hypotheticalToggle.title = hasGrimoire
            ? '' : 'This spirit has no grimoire — writes are impossible regardless';
        }
      }
    } else {
      if (hypotheticalRow) hypotheticalRow.style.display = 'none';
    }
```

- [ ] **Step 5: Store spirit_name and grimoire_writes in saveCustomPreset**

In `saveCustomPreset`, after building `config`, add:

```js
  const _selectedOpt = document.getElementById('char-template-select')?.options[
    document.getElementById('char-template-select')?.selectedIndex
  ];
  const _spiritFolder = _selectedOpt?.dataset?.spiritFolder || '';
  const _hypotheticalToggle = document.getElementById('spirit-hypothetical-toggle');
  const _grimoire_writes = _spiritFolder
    ? !(_hypotheticalToggle?.checked)
    : true;

  const config = {
    name: name,
    enabled: enabled,
    temperature: Math.max(0, Math.min(2, temperature)),
    max_tokens: max_tokens,
    system_prompt: _spiritFolder ? '' : system_prompt,
    inject_prefix: _prefixInput ? _prefixInput.value : '',
    inject_suffix: _suffixInput ? _suffixInput.value : '',
    spirit_name: _spiritFolder,
    grimoire_writes: _grimoire_writes,
  };
```

- [ ] **Step 6: Extend `_syncCharIndicator` for spirit chip**

In `_syncCharIndicator`, inside the `if (hasChar || injectActive)` block, after the existing `hasChar` branch, add a spirit branch:

```js
    const isSpirit = enabled && !!custom?.spirit_name;
    const _SPIRIT_ICON = '<circle cx="12" cy="8" r="4"/><path d="M12 14c-6 0-8 2-8 4v1h16v-1c0-2-2-4-8-4z"/><path d="M9 8l1.5 1.5M15 8l-1.5 1.5" stroke-width="1.5"/>';

    if (isSpirit) {
      btn.style.display = '';
      btn.classList.add('active');
      if (iconEl) iconEl.innerHTML = _SPIRIT_ICON;
      const spiritLabel = custom.spirit_name.charAt(0).toUpperCase() + custom.spirit_name.slice(1);
      if (nameSpan) nameSpan.textContent = spiritLabel;
      btn.title = `Spirit: ${spiritLabel} — click to configure`;
      // Hypothetical mode badge
      const _lockBadge = btn.querySelector('.spirit-lock-badge');
      if (!custom.grimoire_writes) {
        if (!_lockBadge) {
          const badge = document.createElement('span');
          badge.className = 'spirit-lock-badge';
          badge.textContent = '🔒';
          badge.style.cssText = 'font-size:9px;margin-left:2px;';
          btn.appendChild(badge);
        }
      } else if (_lockBadge) {
        _lockBadge.remove();
      }
    }
```

Also update the `hasChar` condition to `(hasChar || isSpirit || injectActive)`.

- [ ] **Step 7: Manual verification**

Start the dev server:
```
python app.py
```

Open `http://localhost:7860`, click the `+` menu:
- Confirm "Characters" optgroup shows Socrates, Razor, Nietzsche, Spark, Odysseus
- Confirm "Spirits" optgroup appears (if Pantheon mounted) with spirit names
- Select a spirit → hypothetical toggle appears, name row hidden
- Select a character → hypothetical toggle hidden, name row visible
- Activate a spirit → chat bar shows spirit chip with spirit icon
- Enable hypothetical mode → lock badge appears on chip

- [ ] **Step 8: Commit**

```
git add static/js/presets.js static/index.html
git commit -m "feat: spirits optgroup, hypothetical toggle, and spirit chip in preset modal"
```

---

## Task 7: Fix group.js `_getCharacterList`

**Files:**
- Modify: `static/js/group.js`

- [ ] **Step 1: Replace `_getCharacterList` in `static/js/group.js`**

Replace the existing `_getCharacterList` function (line ~286):

```js
async function _getCharacterList() {
  // Built-in characters from PROMPT_TEMPLATES — exclude spirits
  const chars = PROMPT_TEMPLATES
    .filter(t => t.isCharacter && (t.category || 'character') === 'character')
    .map(t => ({ id: t.id, name: t.name, prompt: t.prompt }));

  // All saved user templates from server — exclude spirits
  try {
    const res = await fetch(`${API_BASE}/api/presets/templates`);
    if (res.ok) {
      const templates = await res.json();
      templates
        .filter(t => (t.category || 'character') === 'character')
        .forEach(t => {
          if (!chars.find(c => c.name === t.name)) {
            chars.push({
              id: t.id,
              name: t.name,
              prompt: t.system_prompt || '',
            });
          }
        });
    }
  } catch (e) {
    console.warn('[group] Failed to fetch saved templates:', e);
  }

  return chars;
}
```

- [ ] **Step 2: Manual verification**

Open `+` menu → Group tab → click "Add participant":
- Confirm the character dropdown shows all saved characters, not just the currently active one
- Confirm Pantheon spirits do NOT appear in the group character picker

- [ ] **Step 3: Commit**

```
git add static/js/group.js
git commit -m "fix: group chat _getCharacterList fetches all saved templates, excludes spirits"
```

---

## Task 8: Character management page

**Files:**
- Create: `static/characters.html`
- Create: `static/js/characterManager.js`

- [ ] **Step 1: Create `static/characters.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Characters — Odysseus</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <style>
    .char-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
      padding: 24px;
    }
    .char-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      background: var(--bg-secondary, var(--bg));
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .char-card-header {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .char-avatar {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      object-fit: cover;
      background: var(--border);
      flex-shrink: 0;
      cursor: pointer;
    }
    .char-avatar-placeholder {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
      cursor: pointer;
    }
    .char-card-name {
      font-weight: 600;
      font-size: 14px;
    }
    .char-card-temp {
      font-size: 11px;
      opacity: 0.5;
    }
    .char-card-prompt {
      font-size: 12px;
      opacity: 0.65;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .char-card-actions {
      display: flex;
      gap: 6px;
      margin-top: auto;
    }
    .char-card-actions button {
      flex: 1;
      padding: 5px 8px;
      font-size: 11px;
      border-radius: 5px;
      border: 1px solid var(--border);
      background: none;
      color: var(--fg);
      cursor: pointer;
    }
    .char-card-actions button:hover { background: color-mix(in srgb, var(--fg) 8%, transparent); }
    .char-card-actions .btn-danger { color: var(--color-error, #e55); }
    .char-card.builtin { opacity: 0.8; }
    .char-add-card {
      border: 2px dashed var(--border);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--fg);
      opacity: 0.5;
      font-size: 13px;
      gap: 8px;
      min-height: 120px;
    }
    .char-add-card:hover { opacity: 0.8; background: color-mix(in srgb, var(--fg) 4%, transparent); }
    .char-page-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
    }
    .char-page-header h1 { font-size: 18px; font-weight: 600; margin: 0; }
    .char-modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,0.5);
      display: none; align-items: center; justify-content: center; z-index: 1000;
    }
    .char-modal-backdrop.open { display: flex; }
    .char-modal {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      width: 480px;
      max-width: 95vw;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .char-modal h2 { margin: 0; font-size: 16px; }
    .char-modal label { font-size: 12px; opacity: 0.7; display: block; margin-bottom: 4px; }
    .char-modal input, .char-modal textarea, .char-modal select {
      width: 100%; box-sizing: border-box;
      padding: 7px 9px; border: 1px solid var(--border);
      border-radius: 6px; background: var(--bg); color: var(--fg); font-size: 13px;
    }
    .char-modal textarea { height: 120px; resize: vertical; font-family: inherit; }
    .char-modal-footer { display: flex; gap: 8px; justify-content: flex-end; }
    .char-modal-footer button {
      padding: 7px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
      border: 1px solid var(--border); background: none; color: var(--fg);
    }
    .char-modal-footer .btn-primary {
      background: var(--accent, #6c6cf0); color: #fff; border-color: transparent;
    }
    #char-avatar-upload { display: none; }
  </style>
</head>
<body>
  <div class="char-page-header">
    <h1>Characters</h1>
    <a href="/" style="font-size:12px; opacity:0.6; text-decoration:none;">← Back to chat</a>
  </div>

  <div class="char-grid" id="char-grid">
    <div class="char-add-card" id="char-add-btn">
      <span style="font-size:20px;">+</span> New Character
    </div>
  </div>

  <!-- Edit / Create modal -->
  <div class="char-modal-backdrop" id="char-modal-backdrop">
    <div class="char-modal">
      <h2 id="char-modal-title">New Character</h2>
      <input type="hidden" id="char-modal-id">
      <div style="display:flex; gap:12px; align-items:flex-start;">
        <div>
          <div id="char-modal-avatar-preview" class="char-avatar-placeholder" title="Click to upload avatar">👤</div>
          <input type="file" id="char-avatar-upload" accept=".png,.jpg,.jpeg,.webp,.gif">
        </div>
        <div style="flex:1;">
          <label>Name</label>
          <input type="text" id="char-modal-name" placeholder="Character name" maxlength="100">
        </div>
      </div>
      <div>
        <label>System Prompt</label>
        <textarea id="char-modal-prompt" placeholder="Describe how this character thinks, speaks, and behaves..."></textarea>
      </div>
      <div style="display:flex; gap:12px;">
        <div style="flex:1;">
          <label>Temperature <span id="char-modal-temp-val">1.0</span></label>
          <input type="range" id="char-modal-temp" min="0" max="2" step="0.1" value="1.0">
        </div>
        <div style="flex:1;">
          <label>Max Tokens</label>
          <input type="number" id="char-modal-tokens" min="0" max="65536" value="0" placeholder="0 = no limit">
        </div>
      </div>
      <div class="char-modal-footer">
        <button id="char-modal-cancel">Cancel</button>
        <button class="btn-primary" id="char-modal-save">Save</button>
      </div>
    </div>
  </div>

  <script type="module" src="/static/js/characterManager.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `static/js/characterManager.js`**

```js
// static/js/characterManager.js

const API_BASE = '';
let _templates = [];
let _editingId = null;
let _pendingAvatarFile = null;

async function loadTemplates() {
  try {
    const [tmplRes, builtinRes] = await Promise.all([
      fetch(`${API_BASE}/api/presets/templates`),
      Promise.resolve({ ok: true, json: async () => [] }),
    ]);
    _templates = tmplRes.ok ? await tmplRes.json() : [];
  } catch (e) {
    _templates = [];
  }
  renderGrid();
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderGrid() {
  const grid = document.getElementById('char-grid');
  const addBtn = document.getElementById('char-add-btn');

  // Remove all cards except the add button
  grid.querySelectorAll('.char-card').forEach(el => el.remove());

  _templates
    .filter(t => (t.category || 'character') === 'character')
    .forEach(t => {
      const card = document.createElement('div');
      card.className = 'char-card';
      const avatarHtml = t.avatar_url
        ? `<img class="char-avatar" src="${esc(t.avatar_url)}" alt="${esc(t.name)}">`
        : `<div class="char-avatar-placeholder">👤</div>`;
      card.innerHTML = `
        <div class="char-card-header">
          ${avatarHtml}
          <div>
            <div class="char-card-name">${esc(t.name)}</div>
            <div class="char-card-temp">temp ${(t.temperature ?? 1.0).toFixed(1)}</div>
          </div>
        </div>
        <div class="char-card-prompt">${esc((t.system_prompt || '').substring(0, 150))}</div>
        <div class="char-card-actions">
          <button class="btn-edit" data-id="${esc(t.id)}">Edit</button>
          <button class="btn-activate" data-id="${esc(t.id)}">Start Chat</button>
          <button class="btn-danger btn-delete" data-id="${esc(t.id)}">Delete</button>
        </div>
      `;
      card.querySelector('.btn-edit').addEventListener('click', () => openModal(t));
      card.querySelector('.btn-activate').addEventListener('click', () => activateAndChat(t));
      card.querySelector('.btn-delete').addEventListener('click', () => deleteTemplate(t));
      grid.insertBefore(card, addBtn);
    });
}

function openModal(template = null) {
  _editingId = template ? template.id : null;
  _pendingAvatarFile = null;

  document.getElementById('char-modal-title').textContent = template ? 'Edit Character' : 'New Character';
  document.getElementById('char-modal-id').value = template ? template.id : '';
  document.getElementById('char-modal-name').value = template ? template.name : '';
  document.getElementById('char-modal-prompt').value = template ? (template.system_prompt || '') : '';
  const tempInput = document.getElementById('char-modal-temp');
  const tempVal = document.getElementById('char-modal-temp-val');
  tempInput.value = template ? (template.temperature ?? 1.0) : 1.0;
  tempVal.textContent = parseFloat(tempInput.value).toFixed(1);
  document.getElementById('char-modal-tokens').value = template ? (template.max_tokens || 0) : 0;

  const preview = document.getElementById('char-modal-avatar-preview');
  if (template && template.avatar_url) {
    preview.innerHTML = `<img src="${esc(template.avatar_url)}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;">`;
  } else {
    preview.innerHTML = '👤';
  }

  document.getElementById('char-modal-backdrop').classList.add('open');
  document.getElementById('char-modal-name').focus();
}

async function saveModal() {
  const id = document.getElementById('char-modal-id').value;
  const name = document.getElementById('char-modal-name').value.trim();
  if (!name) { alert('Name is required.'); return; }

  const rawTokens = parseInt(document.getElementById('char-modal-tokens').value) || 0;
  const template = {
    id: id || '',
    name,
    system_prompt: document.getElementById('char-modal-prompt').value,
    temperature: parseFloat(document.getElementById('char-modal-temp').value),
    max_tokens: rawTokens > 65536 ? 0 : rawTokens,
    avatar_url: _editingId
      ? (_templates.find(t => t.id === _editingId)?.avatar_url || '')
      : '',
    category: 'character',
  };

  const res = await fetch(`${API_BASE}/api/presets/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(template),
  });
  if (!res.ok) { alert('Failed to save character.'); return; }
  const data = await res.json();

  // Upload avatar if one was selected
  if (_pendingAvatarFile && data.template) {
    const savedId = data.template.id;
    const fd = new FormData();
    fd.append('file', _pendingAvatarFile);
    await fetch(`${API_BASE}/api/presets/templates/${savedId}/avatar`, {
      method: 'POST', body: fd,
    });
  }

  document.getElementById('char-modal-backdrop').classList.remove('open');
  await loadTemplates();
}

async function deleteTemplate(t) {
  if (!confirm(`Delete "${t.name}"? This cannot be undone.`)) return;
  await fetch(`${API_BASE}/api/presets/templates/${t.id}`, { method: 'DELETE' });
  await loadTemplates();
}

async function activateAndChat(t) {
  // Save as the active custom preset and navigate to chat
  await fetch(`${API_BASE}/api/presets/custom`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: t.name,
      enabled: true,
      temperature: t.temperature ?? 1.0,
      max_tokens: t.max_tokens || 0,
      system_prompt: t.system_prompt || '',
      inject_prefix: '',
      inject_suffix: '',
      spirit_name: '',
      grimoire_writes: true,
    }),
  });
  window.location.href = '/';
}

// Wiring
document.getElementById('char-add-btn').addEventListener('click', () => openModal());
document.getElementById('char-modal-cancel').addEventListener('click', () => {
  document.getElementById('char-modal-backdrop').classList.remove('open');
});
document.getElementById('char-modal-save').addEventListener('click', saveModal);
document.getElementById('char-modal-temp').addEventListener('input', e => {
  document.getElementById('char-modal-temp-val').textContent = parseFloat(e.target.value).toFixed(1);
});
document.getElementById('char-modal-backdrop').addEventListener('click', e => {
  if (e.target === document.getElementById('char-modal-backdrop')) {
    document.getElementById('char-modal-backdrop').classList.remove('open');
  }
});

// Avatar upload
document.getElementById('char-modal-avatar-preview').addEventListener('click', () => {
  document.getElementById('char-avatar-upload').click();
});
document.getElementById('char-avatar-upload').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  _pendingAvatarFile = file;
  const url = URL.createObjectURL(file);
  const preview = document.getElementById('char-modal-avatar-preview');
  preview.innerHTML = `<img src="${url}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;">`;
});

// Initial load
loadTemplates();
```

- [ ] **Step 3: Add a nav link to the characters page**

In `static/index.html`, add a link to `/characters` in the sidebar or settings area. Find where the settings/nav links live and add:

```html
<a href="/characters" class="nav-link" title="Character Library">Characters</a>
```

(Exact placement depends on the sidebar structure — find the settings nav block.)

- [ ] **Step 4: Register the characters.html route in `app.py`**

Find where static HTML pages are served and add the `/characters` route:

```python
@app.get("/characters")
async def characters_page():
    return FileResponse("static/characters.html")
```

- [ ] **Step 5: Manual verification**

Navigate to `http://localhost:7860/characters`:
- Confirm the character grid loads with saved templates
- Create a new character, upload an avatar → confirm it appears in the card
- Edit an existing character → confirm changes persist
- Delete a character → confirm card removed and avatar file cleaned up
- Click "Start Chat" → confirm navigates to chat with the character active

- [ ] **Step 6: Commit**

```
git add static/characters.html static/js/characterManager.js app.py static/index.html
git commit -m "feat: character management page with avatar support"
```

---

## Final verification

- [ ] Run full test suite:

```
pytest tests/ -q 2>&1 | tail -30
```

Expected: no regressions introduced by this work.

- [ ] Ctrl+F5 hard refresh in the browser (static files are bind-mounted but browser caches JS).

- [ ] End-to-end check:
  1. Open `+` → select a spirit → activate → confirm chat routes to that spirit (no @tag needed)
  2. Activate a spirit with hypothetical mode on → confirm `grimoire_writes: false` in the saved preset config
  3. Open `/characters` → create a character with an avatar → confirm it appears in the `+` menu Characters group and in the Group tab character picker
  4. Try writing to a persona.md via a direct API call → confirm 500 with "immutable" message
