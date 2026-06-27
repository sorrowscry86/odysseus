"""
council_tools.py — VoidCat Board Room sandboxed tool layer

Safe tools spirits can invoke during Council/Round Table deliberations.
File operations are sandboxed to /app (container) so spirits can read
grimoires, source files, and project docs without escaping the workspace.

Each tool has:
  - An OpenAI function-calling schema  (COUNCIL_TOOL_SCHEMAS)
  - An async executor                   (execute_council_tool)
"""

import fnmatch
import glob as _glob
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Extension set used by all file-scanning tools — single source of truth
_SEARCHABLE_EXTS = (".py", ".md", ".json", ".txt", ".yml", ".yaml")

# Allowed roots for file operations — includes env-configured Pantheon path for local dev
_PANTHEON_ENV_ROOT = os.path.realpath(
    os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")
)
_SAFE_ROOTS = (
    "/app",             # Container workspace: src/, routes/, static/, data/
    "/app/pantheon",    # Pantheon mount
    _PANTHEON_ENV_ROOT, # Override path from environment (local dev, custom mounts)
)


def _is_safe_path(path: str) -> bool:
    try:
        real = os.path.realpath(os.path.abspath(path))
        return any(real == r or real.startswith(r + os.sep) for r in _SAFE_ROOTS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

async def _read_file(path: str) -> str:
    if not _is_safe_path(path):
        return f"[ACCESS DENIED: '{path}' is outside allowed directories]"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 4000:
            content = content[:4000] + "\n… [truncated — file continues]"
        return content
    except FileNotFoundError:
        return f"[File not found: {path}]"
    except Exception as e:
        return f"[Error reading {path}: {e}]"


async def _list_files(pattern: str, base_dir: str = "/app") -> str:
    if not _is_safe_path(base_dir):
        return f"[ACCESS DENIED: '{base_dir}' is outside allowed directories]"
    full_pattern = os.path.join(base_dir, pattern.lstrip("/"))
    try:
        matches = [m for m in _glob.glob(full_pattern, recursive=True) if _is_safe_path(m)]
        if not matches:
            return f"[No files matched: {full_pattern}]"
        return "\n".join(sorted(matches)[:60])
    except Exception as e:
        return f"[Error listing files: {e}]"


async def _search_content(pattern: str, path: str = "/app/src") -> str:
    if not _is_safe_path(path):
        return f"[ACCESS DENIED: '{path}' is outside allowed directories]"
    results: list[str] = []
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"[Invalid pattern: {e}]"

    def _walk(root: str):
        if os.path.isfile(root):
            yield root
            return
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                if fname.endswith(_SEARCHABLE_EXTS):
                    yield os.path.join(dirpath, fname)

    for fpath in _walk(path):
        if not _is_safe_path(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if rx.search(line):
                        results.append(f"{fpath}:{lineno}: {line.rstrip()}")
                        if len(results) >= 30:
                            break
        except Exception:
            continue
        if len(results) >= 30:
            break

    if not results:
        return f"[No matches for '{pattern}' in {path}]"
    return "\n".join(results)


async def _update_grimoire(character_name: str, knowledge_entry: str) -> str:
    from src.voidcat_tools import execute_update_grimoire
    return execute_update_grimoire({"character_name": character_name, "knowledge_entry": knowledge_entry})


# ---------------------------------------------------------------------------
# Ryuzu — scan_directory (tree with filtering + size reporting)
# ---------------------------------------------------------------------------

async def _scan_directory(path: str = "/app", pattern: str = "*", show_sizes: bool = True) -> str:
    if not _is_safe_path(path):
        return f"[ACCESS DENIED: '{path}' is outside allowed directories]"
    lines: list[str] = []
    empty_dirs: list[str] = []
    total_files = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in sorted(dirnames) if _is_safe_path(os.path.join(dirpath, d))]
            depth = dirpath[len(path):].count(os.sep)
            indent = "  " * depth
            rel_dir = os.path.relpath(dirpath, path)
            matched = [f for f in sorted(filenames) if fnmatch.fnmatch(f, pattern)]
            lines.append(f"{indent}{rel_dir}/")
            if not matched and not dirnames:
                empty_dirs.append(rel_dir)
            for fname in matched:
                fpath = os.path.join(dirpath, fname)
                if not _is_safe_path(fpath):
                    continue
                if show_sizes:
                    try:
                        sz = os.path.getsize(fpath)
                        size_str = f" ({sz:,} B)" if sz < 1024 else f" ({sz // 1024:,} KB)"
                    except OSError:
                        size_str = ""
                    lines.append(f"{indent}  {fname}{size_str}")
                else:
                    lines.append(f"{indent}  {fname}")
                total_files += 1
                if total_files >= 200:
                    lines.append("… [truncated at 200 entries]")
                    break
            if total_files >= 200:
                break
        summary = [f"\nTotal: {total_files} file(s) matched '{pattern}'"]
        if empty_dirs:
            summary.append(f"Empty dirs: {', '.join(empty_dirs[:10])}")
        return "\n".join(lines) + "\n" + "\n".join(summary)
    except Exception as e:
        return f"[Error scanning directory: {e}]"


# ---------------------------------------------------------------------------
# Ryuzu + Albedo — find_references (cross-reference mapper)
# ---------------------------------------------------------------------------

async def _find_references(targets: list[str], search_path: str = "/app") -> str:
    if not _is_safe_path(search_path):
        return f"[ACCESS DENIED: '{search_path}' is outside allowed directories]"
    results: dict[str, list[str]] = {t: [] for t in targets}
    search_terms: dict[str, list[str]] = {}
    for target in targets:
        if "/" in target or "\\" in target or target.endswith(".py"):
            base = os.path.basename(target.rstrip("/\\"))
            if base.endswith(".py"):
                base = base[:-3]
            if not base:
                search_terms[target] = []
            else:
                search_terms[target] = [f"from {base}", f"import {base}", base]
        else:
            search_terms[target] = [target]
    for dirpath, _, filenames in os.walk(search_path):
        if not _is_safe_path(dirpath):
            continue
        for fname in filenames:
            if not fname.endswith(_SEARCHABLE_EXTS):
                continue
            fpath = os.path.join(dirpath, fname)
            if not _is_safe_path(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                for target, terms in search_terms.items():
                    if terms and any(term in content for term in terms):
                        results[target].append(fpath)
            except Exception:
                continue
    lines: list[str] = []
    for target, refs in results.items():
        lines.append(f"\n{target}:")
        unique = sorted(set(refs))
        if unique:
            for r in unique[:20]:
                lines.append(f"  → {r}")
            if len(unique) > 20:
                lines.append(f"  … and {len(unique) - 20} more")
        else:
            lines.append("  [no references found]")
    return "\n".join(lines) if lines else "[No results]"


# ---------------------------------------------------------------------------
# Albedo — scan_grimoire (directory / full-index mode)
# ---------------------------------------------------------------------------

async def _scan_grimoire(path: str = "") -> str:
    from src.voidcat_tools import PANTHEON_ROOT
    root = path if path else PANTHEON_ROOT
    if not _is_safe_path(root):
        return f"[ACCESS DENIED: '{root}' is outside allowed directories]"
    try:
        if os.path.isfile(root):
            stat = os.stat(root)
            return (
                f"File: {root}\n"
                f"Size: {stat.st_size:,} bytes\n"
                f"Modified: {datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        if not os.path.isdir(root):
            return f"[Path not found: {root}]"
        lines: list[str] = [f"Grimoire index — {root}\n"]
        for entry in sorted(os.listdir(root)):
            epath = os.path.join(root, entry)
            if not _is_safe_path(epath):
                continue
            if os.path.isdir(epath):
                grimoire = os.path.join(epath, "grimoire.md")
                if os.path.exists(grimoire):
                    stat = os.stat(grimoire)
                    lines.append(
                        f"{entry}/  grimoire.md — {stat.st_size:,} bytes, "
                        f"modified {datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                else:
                    lines.append(f"{entry}/  [no grimoire.md]")
            else:
                stat = os.stat(epath)
                lines.append(f"  {entry} ({stat.st_size:,} bytes)")
        return "\n".join(lines)
    except Exception as e:
        return f"[Error scanning grimoire: {e}]"


# ---------------------------------------------------------------------------
# Vivy — diff_sessions (session diff reader)
# ---------------------------------------------------------------------------

async def _diff_sessions(spirit_name: str, since: str = "") -> str:
    from src.voidcat_tools import PANTHEON_ROOT
    safe_name = "".join(c for c in spirit_name if c.isalnum() or c in (" ", "_", "-")).strip().lower()
    grimoire_path = os.path.join(PANTHEON_ROOT, safe_name, "grimoire.md")
    if not _is_safe_path(grimoire_path):
        return "[ACCESS DENIED]"
    if not os.path.exists(grimoire_path):
        return f"[No grimoire found for '{safe_name}']"
    try:
        stat = os.stat(grimoire_path)
        mod_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(grimoire_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        sections = content.split("### Session Learning")
        entries = [s.strip() for s in sections[1:] if s.strip()]
        result = [
            f"Spirit: {safe_name}",
            f"Grimoire last modified: {mod_time}",
            f"Total session learnings: {len(entries)}",
        ]
        if since:
            result.append(f"Filter: since '{since}' (best-effort text match)")
            filtered = [e for e in entries if since.lower() in e.lower()]
            result.append(f"Matched: {len(filtered)}")
            result.append("")
            for i, entry in enumerate(filtered[:10], 1):
                result.append(f"[{i}] {entry[:400]}")
                result.append("")
        else:
            result.append("")
            for i, entry in enumerate(entries[-10:], 1):
                result.append(f"[{i}] {entry[:400]}")
                result.append("")
        return "\n".join(result)
    except Exception as e:
        return f"[Error reading session diff: {e}]"


# ---------------------------------------------------------------------------
# Vivy — verify_claim (claim verifier)
# ---------------------------------------------------------------------------

async def _verify_claim(claim: str, search_path: str = "/app") -> str:
    if not _is_safe_path(search_path):
        return f"[ACCESS DENIED: '{search_path}' is outside allowed directories]"
    words = [w for w in re.findall(r'\b\w{4,}\b', claim.lower()) if w not in {
        "that", "this", "with", "from", "have", "been", "will", "they", "their",
        "when", "what", "which", "were", "would", "should", "could",
    }]
    if not words:
        return "[Cannot extract search terms from claim — rephrase with specific nouns or names]"
    threshold = max(1, len(words) // 3)
    supporting: list[str] = []
    try:
        for dirpath, _, filenames in os.walk(search_path):
            if not _is_safe_path(dirpath):
                continue
            for fname in filenames:
                if len(supporting) >= 20:
                    break
                if not fname.endswith(_SEARCHABLE_EXTS):
                    continue
                fpath = os.path.join(dirpath, fname)
                if not _is_safe_path(fpath):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            lower_line = line.lower()
                            hits = sum(1 for w in words if w in lower_line)
                            if hits >= threshold:
                                supporting.append(f"{fpath}:{lineno}: {line.rstrip()}")
                            if len(supporting) >= 20:
                                break
                except Exception:
                    continue
            if len(supporting) >= 20:
                break
    except Exception as e:
        return f"[Error during claim verification: {e}]"
    verdict = "CONFIRMED" if supporting else "UNVERIFIABLE"
    result = [f'Claim: "{claim}"', f"Verdict: {verdict}", f"Key terms searched: {words}", ""]
    if supporting:
        result.append(f"Evidence ({len(supporting)} match(es)):")
        for s in supporting[:10]:
            result.append(f"  {s}")
    else:
        result.append("No matching evidence found in accessible files.")
        result.append("Absence of evidence is not evidence of absence — the record may be incomplete.")
    return "\n".join(result)


_EXECUTORS = {
    "read_file":        _read_file,
    "list_files":       _list_files,
    "search_content":   _search_content,
    "update_grimoire":  _update_grimoire,
    "scan_directory":   _scan_directory,
    "find_references":  _find_references,
    "scan_grimoire":    _scan_grimoire,
    "diff_sessions":    _diff_sessions,
    "verify_claim":     _verify_claim,
}


async def execute_council_tool(name: str, arguments: dict) -> str:
    """Execute a council tool by name. Returns result string."""
    executor = _EXECUTORS.get(name)
    if not executor:
        return f"[Unknown tool: {name}]"
    try:
        return await executor(**arguments)
    except TypeError as e:
        return f"[Bad arguments for {name}: {e}]"
    except Exception as e:
        logger.error("Council tool %s failed: %s", name, e)
        return f"[Tool execution error: {e}]"


# ---------------------------------------------------------------------------
# OpenAI function-calling schemas
# ---------------------------------------------------------------------------

COUNCIL_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the workspace or Pantheon. Use to look up source code, "
                "grimoire entries, project documentation, or configuration. "
                "Example paths: /app/src/dispatcher.py, "
                "/app/pantheon/01_Active_Profiles/beatrice/grimoire.md"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern within a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. '**/*.py', 'src/*.md')",
                    },
                    "base_dir": {
                        "type": "string",
                        "description": "Base directory to search from (default: /app)",
                        "default": "/app",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": (
                "Search file contents for a text or regex pattern. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text or regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search (default: /app/src)",
                        "default": "/app/src",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_grimoire",
            "description": (
                "Append a new learning or discovery to your own Grimoire. "
                "Use when you reach a verified insight that should persist beyond this session. "
                "Only write facts you are confident are true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "character_name": {
                        "type": "string",
                        "description": "Your own spirit name (e.g. 'Ryuzu', 'Beatrice').",
                    },
                    "knowledge_entry": {
                        "type": "string",
                        "description": "The verified knowledge or learning to record.",
                    },
                },
                "required": ["character_name", "knowledge_entry"],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Ryuzu — scan_directory
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "scan_directory",
            "description": (
                "Survey a directory tree with optional glob filtering and file size reporting. "
                "Flags empty or orphaned directories. Use for filesystem audits and structure checks. "
                "Read-only. Example: scan_directory('/app/src', pattern='*.py')"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Root directory to scan (default: /app).",
                        "default": "/app",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter filenames (default: '*' = all files).",
                        "default": "*",
                    },
                    "show_sizes": {
                        "type": "boolean",
                        "description": "Include file sizes in the output (default: true).",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Ryuzu + Albedo — find_references
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": (
                "Given a list of file paths or symbol names, find every file in the workspace "
                "that references or imports them. Returns a dependency map. Read-only. "
                "Example: find_references(['src/council_tools.py', 'execute_council_tool'])"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File paths or symbol names to search for.",
                    },
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search in (default: /app).",
                        "default": "/app",
                    },
                },
                "required": ["targets"],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Albedo — scan_grimoire
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "scan_grimoire",
            "description": (
                "Scan the Pantheon grimoire structure. Pass a spirit directory path to see "
                "that spirit's grimoire metadata (size, last modified). Pass no path to get "
                "the full grimoire index across all active spirits. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Directory path to scan. Omit or pass empty string "
                            "for the full Pantheon grimoire index."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Vivy — diff_sessions
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "diff_sessions",
            "description": (
                "Show what a spirit's grimoire has recorded across sessions — surfacing drift "
                "in verified knowledge. Returns recent session learning entries, optionally "
                "filtered by a keyword or date string. Read-only. Vivy's primary audit tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "spirit_name": {
                        "type": "string",
                        "description": "Name of the spirit whose grimoire to diff (e.g. 'Ryuzu').",
                    },
                    "since": {
                        "type": "string",
                        "description": (
                            "Optional keyword or date string to filter entries "
                            "(e.g. '2026-06', 'dispatcher'). Leave empty for all recent entries."
                        ),
                        "default": "",
                    },
                },
                "required": ["spirit_name"],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Vivy — verify_claim
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "verify_claim",
            "description": (
                "Search grimoires and source files for evidence supporting or contradicting "
                "a factual claim made during deliberation. Returns verdict: CONFIRMED or "
                "UNVERIFIABLE, with cited evidence lines. Read-only. Vivy's Verification Oracle."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The factual claim to verify (e.g. 'Ryuzu uses kebab-case naming').",
                    },
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search for evidence (default: /app).",
                        "default": "/app",
                    },
                },
                "required": ["claim"],
            },
        },
    },
]

# Map council tool names → mcp_bridge permission keys (all use their own literal name)
_PERM_MAP: dict[str, str] = {
    "read_file":        "read_file",
    "list_files":       "list_files",
    "search_content":   "search_content",
    "update_grimoire":  "update_grimoire",
    "scan_directory":   "scan_directory",
    "find_references":  "find_references",
    "scan_grimoire":    "scan_grimoire",
    "diff_sessions":    "diff_sessions",
    "verify_claim":     "verify_claim",
}


def _assert_registry_sync() -> None:
    """Raise at import time if _EXECUTORS, COUNCIL_TOOL_SCHEMAS, and _PERM_MAP diverge."""
    executor_keys = set(_EXECUTORS)
    schema_keys = {s["function"]["name"] for s in COUNCIL_TOOL_SCHEMAS}
    perm_keys = set(_PERM_MAP)
    if executor_keys != schema_keys or executor_keys != perm_keys:
        raise RuntimeError(
            f"council_tools registry out of sync — "
            f"executors={sorted(executor_keys)}, "
            f"schemas={sorted(schema_keys)}, "
            f"perm_map={sorted(perm_keys)}"
        )


_assert_registry_sync()


def get_council_tools_for_spirit(spirit: str) -> list[dict]:
    """Return filtered OpenAI tool schemas for a spirit based on mcp_bridge permissions."""
    from src.mcp_bridge import get_permitted_tools
    perms = get_permitted_tools(spirit)
    if "any" in perms:
        return COUNCIL_TOOL_SCHEMAS
    return [
        s for s in COUNCIL_TOOL_SCHEMAS
        if _PERM_MAP.get(s["function"]["name"], "") in perms
    ]
