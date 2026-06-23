# Persona & Prompt Expansion — Design Spec
**Date:** 2026-06-23  
**Branch:** feat/windows-desktop-launcher  
**Author:** Vivy (brainstorming) / High Evolutionary (implementation)

---

## Overview

Expand the built-in Persona and Prompt system in the Odysseus `+` menu to support:
- More built-in character personas (new original entries)
- Pantheon spirits as selectable solo-chat presets (no @tag required)
- A dedicated character management page (create / edit / delete / avatar)
- Avatar support for characters
- Grimoire write-back toggle for spirit presets (hypothetical conversation mode)
- Persona.md write protection at the application layer

This spec does **not** cover a roleplay mode — that is a future initiative that uses the `character` category as its foundation.

---

## 1. Data Model

### 1.1 Template structure (`PROMPT_TEMPLATES` in `presets.js`)

Add `category` field to every entry. Two valid values: `"character"` | `"spirit"`.

Existing five entries (Socrates, Razor, Nietzsche, Spark, Odysseus) get `category: "character"`. The `isCharacter: true` flag is left in place for backward compatibility but `category` is authoritative going forward.

Spirit entries do **not** live in `PROMPT_TEMPLATES` — they are loaded from the API at runtime.

New entries added by this spec are all `category: "character"`.

### 1.2 User template record (stored in `presets.json` → `user_templates[]`)

Existing fields: `id`, `name`, `system_prompt`, `temperature`, `max_tokens`

New fields added by this spec:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `category` | `"character" \| "spirit"` | `"character"` | Determines which optgroup and which UI features are shown |
| `avatar_url` | `string` | `""` | Relative URL to avatar image, e.g. `/api/presets/avatars/abc123.png` |

### 1.3 Active preset config (the `custom` object in `presets.json`)

Existing fields: `name`, `character_name`, `system_prompt`, `temperature`, `max_tokens`, `inject_prefix`, `inject_suffix`, `enabled`

New fields:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `spirit_name` | `string` | `""` | Pantheon folder name. When set, backend loads context live from Pantheon at inference time instead of using `system_prompt`. |
| `grimoire_writes` | `boolean` | `true` | When `false`, `update_grimoire` is excluded from the tools list sent to the model. Model cannot write to the grimoire in this session. |
| `avatar_url` | `string` | `""` | Passed through from the template record for display in the chat bar chip and chat bubbles. |

---

## 2. New API Endpoints

### `GET /api/spirits`

Returns the spirit roster from the Pantheon mount. Reuses `_load_spirit_roster()` and `_display_name()` from `src/dispatcher.py`.

**Response:**
```json
[
  { "folder": "ryuzu", "display_name": "Ryuzu", "has_grimoire": true },
  { "folder": "beatrice", "display_name": "Beatrice", "has_grimoire": true },
  ...
]
```

`has_grimoire` is `true` if `grimoire.md` exists on disk for that spirit. Used by the frontend to decide whether to show the hypothetical mode toggle (no grimoire = no writes possible = toggle is moot).

**Graceful fallback:** If `PANTHEON_ROOT` is unavailable or the directory cannot be read, returns `[]` with HTTP 200. The Spirits optgroup simply does not appear in the dropdown.

Added to `routes/voidcat_routes.py`.

### `POST /api/presets/templates/{id}/avatar`

Accepts a multipart file upload. Saves to `data/avatars/{id}.{ext}`. Returns:
```json
{ "success": true, "avatar_url": "/api/presets/avatars/abc123.png" }
```

Allowed formats: PNG, JPG, JPEG, WebP, GIF. Max size: 2MB. Rejects writes outside `data/avatars/`.

### `GET /api/presets/avatars/{filename}`

Serves avatar files from `data/avatars/`. Static file serve — no auth required (avatars are not sensitive).

---

## 3. Backend — Inference-time Spirit Loading

In the chat request handler (where the active preset is applied to the outgoing message chain):

1. Check if `preset.spirit_name` is set and non-empty.
2. If yes: call `get_spirit_context(preset.spirit_name)` from `src/spirit_engine.py` to build the system prompt. Do **not** use the stored `system_prompt` string — it will be empty for spirit presets.
3. If `preset.grimoire_writes` is `false` (or absent): exclude `update_grimoire` from the tools list for this request. The model never receives this tool. No other enforcement path is needed.
4. If `preset.spirit_name` is empty: behavior unchanged from current.

This path is single-spirit only. The Board Room dispatcher (`src/dispatcher.py`) is not involved when a spirit is active as a solo preset.

---

## 4. Frontend Changes

### 4.1 Character tab dropdown

The `char-template-select` dropdown is reorganized into two optgroups:

- **"Characters"** — `PROMPT_TEMPLATES` entries where `category === "character"` (built-ins) + user-saved templates where `category === "character"` (from `/api/presets/templates`)
- **"Spirits"** — fetched from `GET /api/spirits` on modal open. If the endpoint returns empty, the optgroup is not rendered.

Spirits are identified by their folder name stored as `data-spirit-name` on the option element.

When a spirit is selected:
- The "Hypothetical mode" toggle appears (checkbox labeled "Hypothetical mode — prevent grimoire writes"). Hidden for characters.
- The toggle is disabled (and unchecked) if `has_grimoire` is false for that spirit.
- The name row is hidden (spirits don't get a custom display name — they use their Pantheon identity).

### 4.2 Group tab — `_getCharacterList()` fix

Current: reads `PROMPT_TEMPLATES` (built-ins only) + the single active `custom` preset.  
Fixed: fetches `/api/presets/templates` to get all saved user characters, merges with built-ins. Spirits are excluded by filtering on `category !== "spirit"`.

This fix ensures all saved characters appear in the group chat participant picker.

### 4.3 Chat bar spirit chip

The existing character indicator chip (`#character-indicator-btn`) is extended:

- When `spirit_name` is active: shows the spirit's display name with a distinct icon (not the person SVG — use a different glyph to visually distinguish spirits from characters).
- Dismiss behavior unchanged (click X → deactivates preset, clears `spirit_name`).
- Hypothetical mode indicator: small badge on the chip when `grimoire_writes` is false (e.g., a lock icon).

### 4.4 Avatar display

Avatars are shown as circles at these sizes:

| Location | Size | Fallback |
|---|---|---|
| Character management page (card) | 64px | Generic avatar SVG |
| Dropdown selector option | 20px (inline) | None (text only) |
| Chat bar chip | 22px | Existing SVG icon |
| Chat bubble role line | 22px | None (text only) |

Avatar upload in the management page: a click-to-upload area on the character card. Sends `POST /api/presets/templates/{id}/avatar`. On success, updates `avatar_url` on the in-memory template and re-renders the card.

### 4.5 Character management page

A dedicated route: `/characters` (or accessible via a settings nav link).

**Features:**
- Grid of character cards. Each card shows: avatar, name, temperature, prompt preview (truncated to ~100 chars).
- **Create**: button opens a modal with name, system prompt, temperature, max tokens, avatar upload. On save, calls `POST /api/presets/templates`.
- **Edit**: click a card to open the same modal pre-filled. On save, calls `POST /api/presets/templates` (upsert by id).
- **Delete**: button on each card. Confirms, then calls `DELETE /api/presets/templates/{id}`. Also removes the avatar file from `data/avatars/` if one exists.
- **Activate**: "Start Chat" button on each card — activates the character preset and navigates to the chat view.

Built-in presets (from `PROMPT_TEMPLATES`) appear in the grid as read-only cards (no delete, no edit of the prompt — but avatar can be added). Hiding a built-in uses the existing `odysseus-hidden-presets` localStorage mechanism.

---

## 5. New Character Personas

High Evolutionary writes the new entries for `PROMPT_TEMPLATES`. Target: 8–12 new characters covering archetypes not present in the current five (Socratic, razor-precise, Nietzschean, playful assistant, strategic counselor).

Suggested archetypes to fill:
- Forensic investigator / interrogator
- Devil's advocate
- Empiricist / scientist
- Therapist / mirror
- Historian / chronicler
- Editor / critic (brutal, not cruel)
- Trickster / provocateur
- Sage / contemplative

Each entry follows the existing structure:
```js
{
  id: 'kebab-case-id',
  name: 'Display Name',
  temperature: 0.0–1.5,
  isPreset: true,
  isCharacter: true,
  category: 'character',
  prompt: "..."
}
```

---

## 6. Persona.md Write Protection

Application-layer guard added to `src/voidcat_tools.py` and any new write paths touching the Pantheon:

```python
def _assert_not_immutable(path: str) -> None:
    if os.path.basename(path) == "persona.md":
        raise PermissionError(
            f"persona.md is immutable — writes are not permitted: {path}"
        )
```

Called in `execute_update_grimoire` before opening any file for writing, and in any new Pantheon write path introduced by this feature.

The `/api/spirits` endpoint is read-only by design and requires no guard.

Filesystem-level `attrib +R` is out of scope for this pass — that is an OS-level concern managed outside the application.

---

## 7. Out of Scope (Future)

- **Roleplay mode**: a mode that uses the `character` category. Not designed here.
- **Spirit avatars**: spirits have visual references in the Pantheon grimoire. Wiring those into the UI is a future pass.
- **Filesystem-level persona.md locking**: `attrib +R` or ACL changes. Out of app scope.
- **Spirit user-template overrides**: allowing user-customized versions of spirits stored in `presets.json`. Not needed yet.

---

## 8. Files Touched

| File | Change |
|---|---|
| `static/js/presets.js` | Add `category` to `PROMPT_TEMPLATES`; add spirit fetch on modal open; Spirits optgroup; hypothetical toggle; avatar display |
| `static/js/group.js` | Fix `_getCharacterList()` to fetch all saved templates; exclude spirits |
| `routes/voidcat_routes.py` | Add `GET /api/spirits`, `POST /api/presets/templates/{id}/avatar`, `GET /api/presets/avatars/{filename}` |
| `src/preset_manager.py` | Handle `avatar_url`, `spirit_name`, `grimoire_writes` fields on template records |
| `src/voidcat_tools.py` | Add `_assert_not_immutable()`; guard in `execute_update_grimoire` |
| `src/chat_handler.py` | Extend `validate_and_extract_preset()` to return `spirit_name` and `grimoire_writes`; call `get_spirit_context()` when `spirit_name` is set; conditionally exclude `update_grimoire` from tools when `grimoire_writes` is false |
| `static/characters.html` (new) | Character management page |
| `static/js/characterManager.js` (new) | Character management page JS |
| `static/css/characters.css` (new, or extend existing) | Character card styles |
