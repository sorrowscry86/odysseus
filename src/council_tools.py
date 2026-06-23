"""
council_tools.py — VoidCat Board Room sandboxed tool layer

Safe tools spirits can invoke during Council/Round Table deliberations.
File operations are sandboxed to /app (container) so spirits can read
grimoires, source files, and project docs without escaping the workspace.

Each tool has:
  - An OpenAI function-calling schema  (COUNCIL_TOOL_SCHEMAS)
  - An async executor                   (execute_council_tool)
"""

import glob as _glob
import logging
import os
import re

logger = logging.getLogger(__name__)

# Allowed roots for file operations — resolves against container paths
_SAFE_ROOTS = (
    "/app",        # Container workspace: src/, routes/, static/, data/
    "/app/pantheon",  # Pantheon mount
)


def _is_safe_path(path: str) -> bool:
    try:
        real = os.path.realpath(os.path.abspath(path))
        return any(real.startswith(r) for r in _SAFE_ROOTS)
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
                if fname.endswith((".py", ".md", ".json", ".txt", ".yml", ".yaml")):
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


_EXECUTORS = {
    "read_file":       _read_file,
    "list_files":      _list_files,
    "search_content":  _search_content,
    "update_grimoire": _update_grimoire,
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
]

# Map council tool names → mcp_bridge permission keys
_PERM_MAP: dict[str, str] = {
    "read_file":       "read_file",
    "list_files":      "glob",
    "search_content":  "grep",
    "update_grimoire": "update_grimoire",
}


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
