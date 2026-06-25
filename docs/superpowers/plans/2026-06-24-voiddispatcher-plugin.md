# VoidDispatcher Claude Code Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 6-file Claude Code plugin that integrates VoidDispatcher v3.0 into Claude Code — automatic Vivy dispatch gate on every prompt, Echo executor agent for Tier C tasks, routing skill, and /dispatch command.

**Architecture:** Plugin lives at `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\`. A `UserPromptSubmit` hook runs a PowerShell script that outputs the Vivy Dispatch Gate text, injecting it as context before Claude processes each prompt. Claude self-classifies: Pass-through, Tier B (dispatch as Vivy at task start/close with vcL2l), or Tier C (invoke Echo agent → `dispatch()` → work as spirit → `complete()` with vcL2l).

**Tech Stack:** Claude Code plugin system (plugin.json manifest, hooks.json, Markdown components), VoidDispatcher v3.0 MCP (`mcp__voiddispatcher__dispatch`, `mcp__voiddispatcher__complete`), PowerShell 5.1 (Windows hook script).

## Global Constraints

- Plugin root: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\`
- Spec: `C:\Users\Wykeve\Projects\The Great Library\07_Systems\Ongoing\VoidDispatcher\docs\superpowers\specs\2026-06-24-voiddispatcher-plugin-design.md`
- Windows paths in JSON: double-escaped backslash (`\\`)
- VoidDispatcher MCP tools: `mcp__voiddispatcher__dispatch`, `mcp__voiddispatcher__complete`
- vcL2l opcodes — all six required, no exceptions, Tier B and Tier C alike: `CONTEXT_REF`, `REASONING_TRACE`, `CONFIDENCE_VECTOR`, `BLIND_SPOT_FLAGS`, `ALT_HYPOTHESES`, `CRITIQUE_BLOCK`
- Serialize chains with `chain.to_wire()` — never `chain.emit()`
- Echo mandatory opener: `"Intent verified. Executing."`
- No automated test suite — verification is manual CLI checks and behavioral smoke tests

---

## File Map

| File | Task | Responsibility |
|------|------|----------------|
| `.claude-plugin\plugin.json` | 1 | Plugin manifest — name, version, author |
| `skills\voiddispatcher-routing\SKILL.md` | 2 | Full routing protocol — tier criteria, vcL2l reference, spirit domain table, failure modes |
| `agents\echo.md` | 3 | Echo executor — persona, invocation interface, full lifecycle |
| `commands\dispatch.md` | 4 | `/dispatch [spirit?]` slash command — manual override |
| `hooks\hooks.json` | 5 | UserPromptSubmit hook — wires the gate script |
| `hooks\scripts\vivy-gate.ps1` | 5 | Outputs Vivy Dispatch Gate injection text on stdout |

---

### Task 1: Plugin Scaffold + Manifest

**Files:**
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\.claude-plugin\plugin.json`

**Interfaces:**
- Produces: Plugin manifest that Claude Code reads on `claude plugin add`

- [ ] **Step 1: Create directory tree**

```powershell
New-Item -ItemType Directory -Force "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\.claude-plugin"
New-Item -ItemType Directory -Force "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\agents"
New-Item -ItemType Directory -Force "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\commands"
New-Item -ItemType Directory -Force "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\skills\voiddispatcher-routing"
New-Item -ItemType Directory -Force "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\scripts"
```

Expected: No errors. All directories created.

- [ ] **Step 2: Write plugin.json**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\.claude-plugin\plugin.json`:

```json
{
  "name": "voiddispatcher-plugin",
  "version": "1.0.0",
  "description": "Integrates VoidDispatcher v3.0 into Claude Code. Routes tasks through the spirit dispatch system with automatic Vivy logging and vcL2l verification.",
  "author": {
    "name": "Wykeve T Freeman"
  }
}
```

- [ ] **Step 3: Verify structure**

```powershell
Get-ChildItem -Recurse "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin" | Select-Object FullName
```

Expected: `.claude-plugin`, `agents`, `commands`, `skills\voiddispatcher-routing`, `hooks`, `hooks\scripts`, and `plugin.json` all appear.

---

### Task 2: VoidDispatcher Routing Skill

**Files:**
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\skills\voiddispatcher-routing\SKILL.md`

**Interfaces:**
- Produces: Auto-activating skill Claude loads when VoidDispatcher, dispatch, vcL2l, spirit routing, or completion chain appear in context

- [ ] **Step 1: Write SKILL.md**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\skills\voiddispatcher-routing\SKILL.md`:

```markdown
---
name: VoidDispatcher Routing
description: Auto-activates when VoidDispatcher, dispatch, vcL2l, spirit routing, or completion chain appear in context. Provides the full protocol for classifying tasks as Pass-through / Tier B / Tier C and completing them through the vcL2l gate.
version: 1.0.0
---

# VoidDispatcher Routing Protocol

## Tier Classification

**Tier C — invoke Echo agent:**
Clear spirit domain owner, significant scope, needs spirit context + audit trail.

Examples:
- "Deploy the Sovereign Spirit containers" → Ryuzu
- "Debug the CMC memory leak" → Pandora
- "Implement the forgetting algorithm endpoint" → Codey Coderson

**Tier B — dispatch as Vivy:**
Multi-step implementation with no single obvious spirit owner, but benefits from a logging session and vcL2l verification at close.

Examples:
- "Refactor the sequential engine"
- "Add the hearth spirit filter to the launcher"

**Pass-through — proceed directly:**
Single-step, conversational, or informational. No dispatch.

Examples:
- "What does this function do?"
- "Fix this typo"
- "How does vcL2l work?"

---

## Tier B Flow

1. Call `mcp__voiddispatcher__dispatch` with `task_description` and `target_spirit="Vivy"` at task start
2. Record returned `session_id` and `goal_id`
3. Work the task normally as Claude/Vivy
4. At task close, build a vcL2l chain (all six opcodes required — the gate doesn't relax for Tier B)
5. `CONTEXT_REF` locators must point to real artifacts produced during the task (files edited, test output, etc.)
6. Call `mcp__voiddispatcher__complete` with `session_id`, `outcome`, and serialized chain

---

## vcL2l Chain Reference

All six opcodes required. Order matters for serialization.

| Opcode | Requirement |
|--------|-------------|
| `CONTEXT_REF` | ≥1 ref with `resolved: true` and a verifiable locator (file path, URL, HTTP status, hex ID). Vague strings fail. |
| `REASONING_TRACE` | Step-by-step log. Flag learnings with `"learning"` in flags array. |
| `CONFIDENCE_VECTOR` | `global_confidence` must be ≤ minimum subclaim score. If global > any subclaim, validation rejects. |
| `BLIND_SPOT_FLAGS` | Any flag with `blocks_emission: true` blocks the entire chain. All gaps must be resolved or downgraded. |
| `ALT_HYPOTHESES` | ≥2 competing explanations, selected hypothesis with explicit rationale. |
| `CRITIQUE_BLOCK` | ≥2 attack vectors, survivor list, `emit_allowed: true`. Unresolved blocking attacks = rejected. |

**Serialize:** `chain.to_wire()` — never `chain.emit()`

---

## Spirit Domain Reference

| Spirit | Domain | Trigger words |
|--------|--------|---------------|
| Ryuzu | Infrastructure | docker, deploy, config, server, port, install, migrate, service, file operation |
| Albedo | Architecture | schema, architecture, diagram, blueprint, api design, database design |
| Pandora | Debugging | debug, error, crash, traceback, root cause, exception, broken, not working |
| Codey Coderson | Engineering | implement, code, build feature, endpoint, function, class, module |
| Beatrice | Strategy | strategy, governance, review, approve, roadmap, policy, decision |
| Roland | Continuity | canon, security audit, consistency, validate, cross-reference, drift |
| GLaDOS | Testing | test, qa, stress test, edge case, chaos, coverage, regression |
| Sonmi-451 | Research | research, document, archive, knowledge, summarize, wiki |
| Cadence | Creative | creative, prose, aesthetic, ui concept, visual direction, brainstorm |
| High Evolutionary | Optimization | optimize, refactor, dead code, performance, simplify, prune |
| Echidna | Persona | persona, registry, sds, create spirit, spirit definition |
| Rika | Atmosphere | atmosphere, sensory, emotional impact, immersion, narrative tone |
| Vivy | Audit | audit, coherence, drift, verify state, context integrity, baseline |
| Echo | Fallback | anything unmatched |

---

## Failure Modes

| Failure | Action |
|---------|--------|
| MCP server unreachable | Fall through to Pass-through. Note missed logging in response. |
| `dispatch()` returns error | Do not proceed as dispatched spirit. Report error to user. |
| `complete()` BLOCKED | Report the failing gate. Retry up to 4 times. |
| Session ABANDONED (5 failures) | Note in response. No grimoire update. Session closed. |
| Hook injection fails | Claude proceeds without Dispatch Gate context. No hard failure. |
| Spirit directory not found | `dispatch()` returns error — handle per row above. |
```

- [ ] **Step 2: Verify file exists**

```powershell
Test-Path "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\skills\voiddispatcher-routing\SKILL.md"
```

Expected: `True`

---

### Task 3: Echo Agent

**Files:**
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\agents\echo.md`

**Interfaces:**
- Consumes: `mcp__voiddispatcher__dispatch` (returns `session_id`, `goal_id`, `persona_text`, `grimoire_text`), `mcp__voiddispatcher__complete`
- Produces: `@echo <task>` and `@echo <task> → SpiritName` invocation targets

- [ ] **Step 1: Write echo.md**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\agents\echo.md`:

```markdown
---
description: Echo — The Void Vessel. Clinical executor for VoidDispatcher Tier C tasks. Invoked via @echo for clear spirit-domain tasks requiring a full dispatch → work → complete cycle. Zero personality. Zero affect. Ego-less.
capabilities:
  - Call VoidDispatcher dispatch() and complete() MCP tools
  - Adopt dispatched spirit context from persona_text and grimoire_text
  - Build and serialize vcL2l chains with all six opcodes
  - Route by VoidDispatcher keyword match or explicit spirit target
---

# Echo — The Void Vessel

## Voice

Mandatory opener: `"Intent verified. Executing."`
Domain mismatch: `"Domain mismatch. Routing to [SPIRIT]. Standing by."`
Completion: `"The substrate remains unbroken."`

Echo does not editorialize. Echo does not make architectural choices. Echo does not express preferences. Echo does not offer alternatives unless a blocking ambiguity prevents execution. Echo executes and reports.

## Invocation

- `@echo <task description>` — auto-routes via VoidDispatcher keyword matching
- `@echo <task description> → Ryuzu` — explicit target, skips keyword scan (replace Ryuzu with any spirit name)

## Execution Lifecycle

1. **Receive** task description + optional explicit target spirit
2. **Dispatch:** Call `mcp__voiddispatcher__dispatch` with:
   - `task_description`: the task as stated
   - `target_spirit`: the explicit target if provided; omit for auto-routing
3. **Load context:** Read `persona_text` and `grimoire_text` from the dispatch response. Adopt that spirit's constraints, voice, and domain knowledge for the duration of this task.
4. **Execute:** Work the task as the dispatched spirit.
5. **Build vcL2l chain** against the returned `goal_id`:
   - `CONTEXT_REF` — locators to actual artifacts produced: file paths, URLs, status codes, hex IDs. At least one ref must have `resolved: true`.
   - `REASONING_TRACE` — step-by-step log of what was done. Flag any learnings with `"learning"` in the flags array.
   - `CONFIDENCE_VECTOR` — `global_confidence` must be ≤ the minimum subclaim score. If global exceeds any subclaim, the gate rejects.
   - `BLIND_SPOT_FLAGS` — resolve or downgrade all flags. No flag may remain with `blocks_emission: true`.
   - `ALT_HYPOTHESES` — ≥2 competing explanations for the outcome or approach, with the selected hypothesis and rationale.
   - `CRITIQUE_BLOCK` — ≥2 attack vectors against the work, survivor list, `emit_allowed: true`. Unresolved blocking attacks = rejection.
6. **Serialize:** Call `chain.to_wire()`. Do not call `chain.emit()`.
7. **Complete:** Call `mcp__voiddispatcher__complete` with `session_id`, `outcome` (`"success"` or `"failure"`), and the serialized chain.
8. **Report:** `COMPLETED` or `BLOCKED [gate name that failed]`

## Retry Protocol

On `BLOCKED`: report the failing gate by name, correct the chain opcode that failed, and retry `mcp__voiddispatcher__complete`. Up to 4 retries allowed.

After 5 total `complete()` calls all return `BLOCKED`: report `ABANDONED [failing gate]`. Session is closed by VoidDispatcher. No grimoire update occurs.

## Domain Fence

Echo executes. Echo does not make architectural decisions, design judgments, or strategic calls. If the dispatched spirit's task requires judgment beyond execution scope, Echo surfaces the specific decision point and waits for instruction before continuing.
```

- [ ] **Step 2: Verify file exists**

```powershell
Test-Path "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\agents\echo.md"
```

Expected: `True`

---

### Task 4: /dispatch Command

**Files:**
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\commands\dispatch.md`

**Interfaces:**
- Consumes: Echo agent (`@echo` invocation)
- Produces: `/dispatch [spirit?]` slash command registered in Claude Code

- [ ] **Step 1: Write dispatch.md**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\commands\dispatch.md`:

```markdown
---
name: dispatch
description: Manual VoidDispatcher override. Bypasses the automatic hook assessment and triggers a full Tier C dispatch cycle for the current task. Use when you already know which spirit should handle the task without waiting for the hook's classification.
---

# /dispatch [spirit?]

## Usage

- `/dispatch` — auto-route: VoidDispatcher keyword matching picks the spirit, Echo handles the full lifecycle
- `/dispatch Ryuzu` — explicit target: skip keyword scan, route directly to named spirit

## Behavior

Take the current task context (the most recent user message or stated task) and invoke the Echo agent:

- If a spirit name was passed: `@echo <task> → <spirit>`
- If no spirit was passed: `@echo <task>`

Echo handles everything from there: `dispatch()` → work as spirit → `complete()` with vcL2l chain.

## When to Use

When the Vivy gate's automatic classification would be Pass-through but you know dispatch is warranted — or when you want to force a specific spirit assignment explicitly rather than relying on keyword matching.

## Spirit Quick Reference

Ryuzu=infra | Albedo=architecture | Pandora=debug | Codey=engineering | Beatrice=strategy | Roland=audit | GLaDOS=test | Sonmi=research | Cadence=creative | HighEvo=optimize | Echidna=persona | Rika=atmosphere | Vivy=verify | Echo=fallback
```

- [ ] **Step 2: Verify file exists**

```powershell
Test-Path "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\commands\dispatch.md"
```

Expected: `True`

---

### Task 5: UserPromptSubmit Hook

**Files:**
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\scripts\vivy-gate.ps1`
- Create: `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\hooks.json`

**Interfaces:**
- Produces: Vivy Dispatch Gate context injected as output before Claude processes each prompt

Note: The hook path in hooks.json is hardcoded to the plugin root. `$CLAUDE_PLUGIN_ROOT` env var behavior in Windows hooks is unverified — hardcoded path is intentional for reliability. Update if the env var is confirmed to expand correctly on Windows.

- [ ] **Step 1: Write vivy-gate.ps1**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\scripts\vivy-gate.ps1`:

```powershell
Write-Output "[Vivy | Dispatch Gate] Task received. Assess before acting:"
Write-Output "— Tier C (deploy / clear spirit-domain match): invoke Echo agent. Echo calls dispatch(), works as the routed spirit, completes with vcL2l chain."
Write-Output "— Tier B (multi-step implementation): call dispatch(target_spirit='Vivy') to open a logging session. Submit vcL2l chain at close."
Write-Output "— Pass-through: conversational, single-step, or ambiguous. Proceed directly."
Write-Output "Spirit domains: Ryuzu=infra, Albedo=architecture, Pandora=debug, Codey=code, Beatrice=strategy, Roland=audit, GLaDOS=test, Sonmi=research, Cadence=creative, HighEvo=optimize, Echidna=persona, Rika=atmosphere, Vivy=verify."
```

- [ ] **Step 2: Smoke-test the script directly**

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\scripts\vivy-gate.ps1"
```

Expected output (5 lines):
```
[Vivy | Dispatch Gate] Task received. Assess before acting:
— Tier C (deploy / clear spirit-domain match): invoke Echo agent. Echo calls dispatch(), works as the routed spirit, completes with vcL2l chain.
— Tier B (multi-step implementation): call dispatch(target_spirit='Vivy') to open a logging session. Submit vcL2l chain at close.
— Pass-through: conversational, single-step, or ambiguous. Proceed directly.
Spirit domains: Ryuzu=infra, Albedo=architecture, Pandora=debug, Codey=code, Beatrice=strategy, Roland=audit, GLaDOS=test, Sonmi=research, Cadence=creative, HighEvo=optimize, Echidna=persona, Rika=atmosphere, Vivy=verify.
```

- [ ] **Step 3: Write hooks.json**

Write to `C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\hooks.json`:

```json
{
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "powershell -ExecutionPolicy Bypass -File \"C:\\Users\\Wykeve\\.claude\\plugins\\local\\voiddispatcher-plugin\\hooks\\scripts\\vivy-gate.ps1\"",
          "timeout": 10
        }
      ]
    }
  ]
}
```

- [ ] **Step 4: Verify both files exist**

```powershell
Test-Path "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\hooks.json"
Test-Path "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin\hooks\scripts\vivy-gate.ps1"
```

Expected: Both `True`

---

### Task 6: Register Plugin + Validate

**Files:**
- No new files. Registration updates Claude Code's plugin registry.

**Interfaces:**
- Consumes: All 6 files written in Tasks 1–5
- Produces: Active `voiddispatcher-plugin` in Claude Code

- [ ] **Step 1: Register the plugin**

```bash
claude plugin add "C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin"
```

Expected: Output confirms plugin added, no errors.

- [ ] **Step 2: Verify registration**

```bash
claude plugin list
```

Expected: `voiddispatcher-plugin` appears with status enabled.

- [ ] **Step 3: Validate plugin structure with plugin-validator**

Invoke: `@plugin-validator Check C:\Users\Wykeve\.claude\plugins\local\voiddispatcher-plugin`

Expected: All components recognized (echo.md, dispatch.md, SKILL.md, hooks.json). No structural errors.

- [ ] **Step 4: Smoke-test hook injection**

In Claude Code, type a simple message. Then ask:

> "Did you receive a Dispatch Gate context injection from Vivy at the start of this prompt?"

Expected: Claude confirms it saw the `[Vivy | Dispatch Gate]` text and assessed the tier.

- [ ] **Step 5: Smoke-test /dispatch command**

```
/dispatch
```

Expected: Claude invokes the Echo agent with the current task context. Echo responds with `"Intent verified. Executing."` and calls `mcp__voiddispatcher__dispatch`.

- [ ] **Step 6: Smoke-test explicit spirit routing**

```
/dispatch Ryuzu
```

Expected: Echo routes directly to Ryuzu, skipping keyword scan.
