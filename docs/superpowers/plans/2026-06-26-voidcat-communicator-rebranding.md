# VoidCat Communicator Rebranding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all visible "Odysseus" branding with "VoidCat Communicator" and swap logos/icons to the official VoidCat RDC asset set.

**Architecture:** Pure asset + HTML/CSS edits — no backend logic changes. Two official image files are copied from The Great Library's `12_Assets/` into the project's `static/` directory, then referenced in `login.html`, `index.html`, and `style.css`. No localStorage keys, Python files, or internal identifiers are touched.

**Tech Stack:** HTML, CSS, PowerShell (file copy). No build step — edits take effect on next page load.

## Global Constraints

- Internal identifiers stay unchanged: localStorage keys (`odysseus-theme`, `odysseus-last-user`), JS function names, Python files, launcher filenames, test files, markdown docs.
- All image paths served as `/static/<filename>` (Flask static route).
- Source assets live at: `C:\Users\Wykeve\Projects\The Great Library\12_Assets\`
- Working directory: `c:\Users\Wykeve\Projects\The Great Library\05_Projects\01_Active\voidcat-communicator`
- Commit prefix: `feat:`

---

## File Map

| File | Action | What changes |
|---|---|---|
| `static/logo_standard_galaxy.jpg` | Create (copy) | New hero logo for login + welcome screen |
| `static/icon_app_square.png` | Create (copy) | New square app icon for sidebar + favicon |
| `static/login.html` | Modify | Title, `<h1>` logo element, inline CSS |
| `static/index.html` | Modify | Favicon, sidebar brand, welcome screen, page titles JS map, a11y heading, current-meta span, settings label |
| `static/style.css` | Modify | `.sidebar-brand-title` left fix, add `.welcome-logo-img` rule |

---

### Task 1: Copy official assets into `static/`

**Files:**
- Create: `static/logo_standard_galaxy.jpg`
- Create: `static/icon_app_square.png`

**Interfaces:**
- Produces: `/static/logo_standard_galaxy.jpg` and `/static/icon_app_square.png` — both referenced in Tasks 2, 3, 4.

- [ ] **Step 1: Copy the assets**

```powershell
Copy-Item "C:\Users\Wykeve\Projects\The Great Library\12_Assets\logos\logo_standard_galaxy.jpg" `
  "C:\Users\Wykeve\Projects\The Great Library\05_Projects\01_Active\voidcat-communicator\static\logo_standard_galaxy.jpg"

Copy-Item "C:\Users\Wykeve\Projects\The Great Library\12_Assets\icon_app_square.png" `
  "C:\Users\Wykeve\Projects\The Great Library\05_Projects\01_Active\voidcat-communicator\static\icon_app_square.png"
```

- [ ] **Step 2: Verify both files exist**

```powershell
Test-Path "static\logo_standard_galaxy.jpg"
Test-Path "static\icon_app_square.png"
```

Expected: both return `True`. If either returns `False`, re-check the source path in `12_Assets/`.

- [ ] **Step 3: Commit**

```powershell
git add static/logo_standard_galaxy.jpg static/icon_app_square.png
git commit -m "feat: add official VoidCat RDC logo assets to static/"
```

---

### Task 2: Update `static/login.html`

**Files:**
- Modify: `static/login.html`

**Interfaces:**
- Consumes: `static/logo_standard_galaxy.jpg` from Task 1.
- Produces: login page with correct title and VoidCat logo replacing the boat SVG.

- [ ] **Step 1: Update the `<title>` tag**

In `static/login.html`, find line 6:
```html
<title>Odysseus — Login</title>
```
Replace with:
```html
<title>VoidCat Communicator — Login</title>
```

- [ ] **Step 2: Replace the boat SVG logo with the VoidCat image**

Find line 255–256:
```html
  <h1 class="logo">
    <svg class="logo-boat" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path d="M16 4L16 22L6 22Z" fill="currentColor"/><path d="M16 8L16 22L24 22Z" fill="currentColor" opacity="0.6"/><path d="M4 24Q10 20 16 24Q22 28 28 24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg><span>Odysseus</span>
  </h1>
```
Replace with:
```html
  <h1 class="logo">
    <img src="/static/logo_standard_galaxy.jpg" class="logo-img" alt="VoidCat Communicator">
  </h1>
```

- [ ] **Step 3: Add the `.logo-img` CSS rule**

In the inline `<style>` block, find the existing rule (around line 231):
```css
  .logo-boat { width: 1.6rem; height: 1.6rem; margin-right: 0.4rem; vertical-align: -0.15em; color: var(--red); }
```
Add the new rule directly after it:
```css
  .logo-boat { width: 1.6rem; height: 1.6rem; margin-right: 0.4rem; vertical-align: -0.15em; color: var(--red); }
  .logo-img { width: 240px; height: auto; border-radius: 8px; margin-bottom: 0.25rem; }
```

- [ ] **Step 4: Verify — no visible "Odysseus" remains in login.html**

```powershell
Select-String -Path "static\login.html" -Pattern "<title>.*Odysseus|<span>Odysseus"
```

Expected: no matches. (The `odysseus-theme` localStorage references are out of scope and will still appear — that is correct.)

- [ ] **Step 5: Verify the new img tag is present**

```powershell
Select-String -Path "static\login.html" -Pattern "logo_standard_galaxy"
```

Expected: 1 match on the `<img src=...>` line.

- [ ] **Step 6: Commit**

```powershell
git add static/login.html
git commit -m "feat: replace Odysseus boat logo with VoidCat galaxy logo on login page"
```

---

### Task 3: Update `static/index.html` — favicon, sidebar, display strings

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `static/icon_app_square.png` from Task 1.
- Produces: correct favicon, sidebar brand showing `icon_app_square.png` + "VoidCat Communicator" with wider gap, correct a11y heading, current-meta label, and settings label.

- [ ] **Step 1: Update the favicon `<link>` tag**

Find line 6:
```html
  <link rel="icon" type="image/jpeg" href="/static/voidcat-logo.jpg">
```
Replace with:
```html
  <link rel="icon" type="image/png" href="/static/icon_app_square.png">
```

- [ ] **Step 2: Update the sidebar brand `<img>`**

Find line 695:
```html
        <img src="/static/voidcat-logo.jpg" alt="VoidCat RDC" style="width:26px;height:26px;border-radius:50%;object-fit:cover;margin-right:7px;vertical-align:middle;flex-shrink:0;">
```
Replace with:
```html
        <img src="/static/icon_app_square.png" alt="VoidCat Communicator" style="width:26px;height:26px;border-radius:50%;object-fit:cover;margin-right:14px;vertical-align:middle;flex-shrink:0;">
```

- [ ] **Step 3: Update the sidebar brand title text**

Find line 696:
```html
        <span class="sidebar-brand-title">VoidCat RDC</span>
```
Replace with:
```html
        <span class="sidebar-brand-title">VoidCat Communicator</span>
```

- [ ] **Step 4: Update the a11y visually-hidden heading**

Find line 952:
```html
    <h1 class="a11y-visually-hidden">Odysseus</h1>
```
Replace with:
```html
    <h1 class="a11y-visually-hidden">VoidCat Communicator</h1>
```

- [ ] **Step 5: Update the chat meta overlay label**

Find on line 955 (long line — search for the span content):
```html
<span id="current-meta">Odysseus Chat</span>
```
Replace with:
```html
<span id="current-meta">VoidCat Communicator</span>
```

- [ ] **Step 6: Update the settings sidebar label**

Find line 1750:
```html
                <span class="vis-label">Odysseus <span class="vis-hint">Brand name</span></span>
```
Replace with:
```html
                <span class="vis-label">VoidCat Communicator <span class="vis-hint">Brand name</span></span>
```

- [ ] **Step 7: Verify — favicon and sidebar brand updated**

```powershell
Select-String -Path "static\index.html" -Pattern "icon_app_square"
```

Expected: 2 matches — one on the `<link rel="icon">` line and one on the sidebar `<img>` line.

- [ ] **Step 8: Verify — display strings updated**

```powershell
Select-String -Path "static\index.html" -Pattern "a11y-visually-hidden|current-meta|vis-label" | Select-String "Odysseus"
```

Expected: no matches.

- [ ] **Step 9: Commit**

```powershell
git add static/index.html
git commit -m "feat: update favicon, sidebar brand, and display strings to VoidCat Communicator"
```

---

### Task 4: Update `static/index.html` — welcome screen and per-route titles

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `static/logo_standard_galaxy.jpg` from Task 1.
- Produces: welcome screen showing VoidCat galaxy logo; browser tab titles reading "Calendar — VoidCat Communicator" etc.

- [ ] **Step 1: Replace the welcome screen boat SVG with the VoidCat logo**

Find line 957:
```html
      <div class="welcome-name"><svg class="welcome-boat" viewBox="0 0 32 32"><path d="M16 4L16 22L6 22Z" fill="currentColor"/><path d="M16 8L16 22L24 22Z" fill="currentColor" opacity="0.6"/><path d="M4 24Q10 20 16 24Q22 28 28 24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>Odysseus</div>
```
Replace with:
```html
      <div class="welcome-name"><img src="/static/logo_standard_galaxy.jpg" class="welcome-logo-img" alt="VoidCat Communicator"></div>
```

- [ ] **Step 2: Update all per-route page titles in the JS `titles` map**

Find lines 152–161:
```js
      var titles = {
        '/calendar': 'Calendar — Odysseus',
        '/notes': 'Notes — Odysseus',
        '/cookbook': 'Cookbook — Odysseus',
        '/email': 'Email — Odysseus',
        '/memory': 'Memory — Odysseus',
        '/gallery': 'Gallery — Odysseus',
        '/tasks': 'Tasks — Odysseus',
        '/library': 'Library — Odysseus',
      };
```
Replace with:
```js
      var titles = {
        '/calendar': 'Calendar — VoidCat Communicator',
        '/notes': 'Notes — VoidCat Communicator',
        '/cookbook': 'Cookbook — VoidCat Communicator',
        '/email': 'Email — VoidCat Communicator',
        '/memory': 'Memory — VoidCat Communicator',
        '/gallery': 'Gallery — VoidCat Communicator',
        '/tasks': 'Tasks — VoidCat Communicator',
        '/library': 'Library — VoidCat Communicator',
      };
```

- [ ] **Step 3: Update the manifest blob fallback name**

Find lines 170–171:
```js
            name: (titles[path] || 'Odysseus'),
            short_name: (titles[path] || 'Odysseus').split('—')[0].trim(),
```
Replace with:
```js
            name: (titles[path] || 'VoidCat Communicator'),
            short_name: (titles[path] || 'VoidCat Communicator').split('—')[0].trim(),
```

- [ ] **Step 4: Verify — no "Odysseus" remains in visible display positions**

```powershell
Select-String -Path "static\index.html" -Pattern "Odysseus" | Where-Object { $_.Line -notmatch "odysseus-theme|odysseusInit|_odysseusLoad|odysseusReady|# " }
```

Expected: no matches. Any remaining hits are internal identifiers (out of scope) — if you see display text like a `<span>` or title string, fix it before continuing.

- [ ] **Step 5: Verify the welcome screen logo is wired up**

```powershell
Select-String -Path "static\index.html" -Pattern "welcome-logo-img"
```

Expected: 1 match on the new `<img class="welcome-logo-img">` line.

- [ ] **Step 6: Commit**

```powershell
git add static/index.html
git commit -m "feat: replace welcome screen boat logo and update per-route page titles"
```

---

### Task 5: Update `static/style.css`

**Files:**
- Modify: `static/style.css`

**Interfaces:**
- Produces: `.welcome-logo-img` rule that sizes the welcome screen logo; `.sidebar-brand-title` with corrected left offset.

- [ ] **Step 1: Fix the `.sidebar-brand-title` left offset**

Find the rule at line 563 (exact content):
```css
    .sidebar-brand-title {
      font-size: 1rem;
      font-weight: 600;
      line-height: 1.35;
      color: var(--brand-color, var(--red));
      white-space: nowrap;
      user-select: none;
      position: relative;
      top: 0;
      left: -10px;
    }
```
Replace with:
```css
    .sidebar-brand-title {
      font-size: 1rem;
      font-weight: 600;
      line-height: 1.35;
      color: var(--brand-color, var(--red));
      white-space: nowrap;
      user-select: none;
      position: relative;
      top: 0;
      left: 0;
    }
```

- [ ] **Step 2: Add the `.welcome-logo-img` rule**

Find the `.welcome-boat` rule at line 1895:
```css
    .welcome-boat {
      width: 1.8rem;
      height: 1.8rem;
      margin-right: 0.4rem;
      vertical-align: -0.15em;
      color: var(--brand-color, var(--red));
    }
```
Add the new rule directly after it:
```css
    .welcome-boat {
      width: 1.8rem;
      height: 1.8rem;
      margin-right: 0.4rem;
      vertical-align: -0.15em;
      color: var(--brand-color, var(--red));
    }
    .welcome-logo-img {
      max-width: 280px;
      height: auto;
      border-radius: 8px;
    }
```

- [ ] **Step 3: Verify the left offset is corrected**

```powershell
Select-String -Path "static\style.css" -Pattern "left: -10px"
```

Expected: no matches (or any remaining hits are in unrelated rules — confirm they're not in `.sidebar-brand-title`).

- [ ] **Step 4: Verify `.welcome-logo-img` rule exists**

```powershell
Select-String -Path "static\style.css" -Pattern "welcome-logo-img"
```

Expected: 1 match.

- [ ] **Step 5: Commit**

```powershell
git add static/style.css
git commit -m "feat: add welcome-logo-img CSS rule and fix sidebar-brand-title left offset"
```

---

## Final Verification

After all tasks are complete, run this sweep to confirm no user-visible "Odysseus" strings remain:

```powershell
# Check for display-visible Odysseus in HTML files
Select-String -Path "static\*.html" -Pattern "Odysseus" |
  Where-Object { $_.Line -notmatch "odysseus-theme|odysseus-last-user|odysseusInit|_odysseusLoad|comment|<!-- " }
```

Expected: zero matches.

Then visually confirm:
1. Open `/login` — title bar reads "VoidCat Communicator — Login", galaxy logo appears instead of boat
2. Open `/` — sidebar shows `icon_app_square.png` with a clear gap before "VoidCat Communicator"
3. Open `/` with no active chat — welcome screen shows the galaxy logo
4. Open `/calendar` — tab title reads "Calendar — VoidCat Communicator"
5. Browser favicon shows the VoidCat square icon

---

## Definition of Done

- [ ] `static/logo_standard_galaxy.jpg` exists and is served at `/static/logo_standard_galaxy.jpg`
- [ ] `static/icon_app_square.png` exists and is served at `/static/icon_app_square.png`
- [ ] Login page: title is "VoidCat Communicator — Login"; galaxy logo visible; no boat SVG
- [ ] Sidebar: square icon with 14px gap before "VoidCat Communicator"
- [ ] Welcome screen: galaxy logo where boat SVG + "Odysseus" text was
- [ ] Per-route titles: all read "X — VoidCat Communicator"
- [ ] Favicon: `icon_app_square.png`
- [ ] No visible "Odysseus" anywhere in the running UI
