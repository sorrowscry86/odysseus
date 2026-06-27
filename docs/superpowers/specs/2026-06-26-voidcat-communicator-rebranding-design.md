# VoidCat Communicator — Full Rebranding Design

**Date:** 2026-06-26
**Author:** Vivy (via brainstorming skill)
**Status:** Approved — ready for implementation

---

## Summary

Replace all visible "Odysseus" branding in the UI with "VoidCat Communicator" and swap
logo/icon assets to the official VoidCat RDC set from `12_Assets/`. Internal code
identifiers (localStorage keys, function names, Python routes, filenames) are out of
scope — no breaking changes to existing user sessions.

---

## Scope

### In scope — visible UI only
- Page `<title>` tags
- Display text rendered to the user (headings, labels, chat overlay, settings panel)
- Logo images (login header, welcome screen, sidebar brand)
- Favicon / app icon

### Out of scope
- localStorage keys (`odysseus-theme`, `odysseus-last-user`)
- Internal function names (`window._odysseusLoadTime`, `odysseusInitMermaid`, etc.)
- Python source files (routes, services, agent prompts)
- Launcher filenames (`Odysseus.Launcher.ps1`)
- Test files
- Markdown documentation files
- `.specstory/` debug dumps

---

## Assets

Two official assets are copied from `12_Assets/` into `static/`:

| Source (The Great Library) | Destination (voidcat-communicator) | Used for |
|---|---|---|
| `12_Assets/logos/logo_standard_galaxy.jpg` | `static/logo_standard_galaxy.jpg` | Login page header, welcome screen |
| `12_Assets/icon_app_square.png` | `static/icon_app_square.png` | Sidebar brand icon, favicon |

The existing `static/voidcat-logo.jpg` remains on disk but is no longer referenced. All
`<link rel="icon">` references are updated to point to `icon_app_square.png`.

---

## File Changes

### `static/login.html`

| Location | Before | After |
|---|---|---|
| `<title>` | `Odysseus — Login` | `VoidCat Communicator — Login` |
| `<h1 class="logo">` | SVG boat + `<span>Odysseus</span>` | `<img src="/static/logo_standard_galaxy.jpg" class="logo-img" alt="VoidCat Communicator">` |
| CSS (inline `<style>`) | `.logo-boat { … }` rule | Add `.logo-img { width:240px; height:auto; border-radius:8px; margin-bottom:0.25rem; }` |

The existing `.logo-boat` and `.logo span` rules are left in place (inert, not harmful).

---

### `static/index.html`

#### Favicon
| Before | After |
|---|---|
| `href="/static/voidcat-logo.jpg"` | `href="/static/icon_app_square.png"` |

#### Sidebar brand (`<div class="sidebar-brand">`)
| Element | Before | After |
|---|---|---|
| `<img>` src | `/static/voidcat-logo.jpg` | `/static/icon_app_square.png` |
| `<img>` alt | `VoidCat RDC` | `VoidCat Communicator` |
| `<img>` inline `margin-right` | `7px` | `14px` |
| `<span class="sidebar-brand-title">` | `VoidCat RDC` | `VoidCat Communicator` |

#### Welcome screen (`<div class="welcome-name">`)

Replace:
```html
<div class="welcome-name">
  <svg class="welcome-boat" viewBox="0 0 32 32">…</svg>Odysseus
</div>
```

With:
```html
<div class="welcome-name">
  <img src="/static/logo_standard_galaxy.jpg" class="welcome-logo-img" alt="VoidCat Communicator">
</div>
```

#### Per-route page titles (JS object in `<script>`)

Replace all entries in the `titles` map:

| Before | After |
|---|---|
| `'/calendar': 'Calendar — Odysseus'` | `'/calendar': 'Calendar — VoidCat Communicator'` |
| `'/notes': 'Notes — Odysseus'` | `'/notes': 'Notes — VoidCat Communicator'` |
| `'/cookbook': 'Cookbook — Odysseus'` | `'/cookbook': 'Cookbook — VoidCat Communicator'` |
| `'/email': 'Email — Odysseus'` | `'/email': 'Email — VoidCat Communicator'` |
| `'/memory': 'Memory — Odysseus'` | `'/memory': 'Memory — VoidCat Communicator'` |
| `'/gallery': 'Gallery — Odysseus'` | `'/gallery': 'Gallery — VoidCat Communicator'` |
| `'/tasks': 'Tasks — Odysseus'` | `'/tasks': 'Tasks — VoidCat Communicator'` |
| `'/library': 'Library — Odysseus'` | `'/library': 'Library — VoidCat Communicator'` |

Also update the manifest blob fallback names:
```js
// Before
name: (titles[path] || 'Odysseus'),
short_name: (titles[path] || 'Odysseus').split('—')[0].trim(),

// After
name: (titles[path] || 'VoidCat Communicator'),
short_name: (titles[path] || 'VoidCat Communicator').split('—')[0].trim(),
```

#### Other display strings

| Element | Before | After |
|---|---|---|
| `<h1 class="a11y-visually-hidden">` | `Odysseus` | `VoidCat Communicator` |
| `<span id="current-meta">` | `Odysseus Chat` | `VoidCat Communicator` |
| Settings visual label | `Odysseus <span class="vis-hint">Brand name</span>` | `VoidCat Communicator <span class="vis-hint">Brand name</span>` |

---

### `static/style.css`

| Rule | Change |
|---|---|
| `.sidebar-brand-title` | Remove `left: -10px` → `left: 0` (was compensating for old icon layout) |
| Add `.welcome-logo-img` | `max-width: 280px; height: auto; border-radius: 8px;` |

---

## What Is NOT Changing

- No localStorage migration needed (keys stay as `odysseus-*`)
- No Python files touched
- No test files touched
- No markdown docs updated
- No file renames

---

## Definition of Done

- Login page shows `logo_standard_galaxy.jpg` where the boat SVG was, title reads "VoidCat Communicator — Login"
- Sidebar shows `icon_app_square.png` with visible gap before "VoidCat Communicator" label
- Welcome screen shows `logo_standard_galaxy.jpg` where the boat SVG + "Odysseus" text was
- Browser tab title on `/calendar`, `/notes`, etc. reads "Calendar — VoidCat Communicator" etc.
- Favicon is `icon_app_square.png`
- No "Odysseus" visible anywhere in the running UI
