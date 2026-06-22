"""
builtin_mcp.py

Auto-registration of built-in MCP servers on startup.
Each server runs as a stdio subprocess managed by McpManager.
"""

import logging
import os
import shutil
import sys
import asyncio

from core.platform_compat import IS_WINDOWS, which_tool

logger = logging.getLogger(__name__)


def _find_npx() -> str:
    """Find the npx binary, checking common locations if not on PATH.

    On Windows the shim is `npx.cmd`, which `which_tool` resolves via PATHEXT.
    """
    npx = which_tool("npx")
    if npx:
        return npx
    if IS_WINDOWS:
        # Minimal-PATH fallbacks: npm's global bin lives under %APPDATA%\npm,
        # and node's installer dir carries npx.cmd alongside node.exe.
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        for candidate in (
            os.path.join(appdata, "npm", "npx.cmd"),
            r"C:\Program Files\nodejs\npx.cmd",
        ):
            if os.path.isfile(candidate):
                return candidate
        node = which_tool("node")
        if node:
            cand = os.path.join(os.path.dirname(node), "npx.cmd")
            if os.path.isfile(cand):
                return cand
        return "npx.cmd"  # fallback, will fail with a clear error
    # Common POSIX locations when PATH is minimal (e.g. systemd)
    for candidate in [
        os.path.expanduser("~/.npm-global/bin/npx"),
        os.path.expanduser("~/.local/bin/npx"),
        "/usr/local/bin/npx",
        "/usr/bin/npx",
    ]:
        if os.path.isfile(candidate):
            return candidate
    # Try to find node and use npx from same dir
    node = shutil.which("node")
    if node:
        npx_candidate = os.path.join(os.path.dirname(node), "npx")
        if os.path.isfile(npx_candidate):
            return npx_candidate
    return "npx"  # fallback, will fail with a clear error

# Server definitions: id -> (script path relative to project root, display name)
#
# bash / python / filesystem / web_search were folded into native in-process
# execution (src/tool_execution.py:_direct_fallback). Those trivial subprocess
# wrappers are gone.
#
# image_gen / memory / rag / email still run as stdio MCP servers — each
# carries hundreds of LOC of unique IMAP / HTTP / manager logic not worth
# duplicating into the native path right now.
_BUILTIN_SERVERS = {
    "image_gen":  ("mcp_servers/image_gen_server.py",  "Built-in: Image Generation"),
    "memory":     ("mcp_servers/memory_server.py",     "Built-in: Memory"),
    "rag":        ("mcp_servers/rag_server.py",        "Built-in: RAG"),
    "email":      ("mcp_servers/email_server.py",      "Built-in: Email"),
}

# NPX-based built-in servers (run via npx, not Python)
_BUILTIN_NPX_SERVERS = {
    "builtin_browser": {
        "name": "Built-in: Browser",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest", "--headless", "--caps", "vision"],
    },
}

# VoidCat RDC MCP suite — mirrors the suite in Claude Desktop
_CMC_DIR = r"C:\Users\Wykeve\Projects\The Great Library\07_Systems\Ongoing\CMC\Causal-Memory-Core"
_PANTHEON_MEMORY_DIR = r"C:\Users\Wykeve\Projects\pantheon-memory-core"


def _voidcat_entrypoint_ready(cfg: dict) -> tuple[bool, str]:
    """Return whether a VoidCat MCP server can start, and a detail string."""
    command = (cfg.get("command") or "").strip()
    args = cfg.get("args") or []
    if command == "uv" and len(args) >= 2 and args[0] == "--directory":
        project_dir = args[1]
        entry = os.path.join(project_dir, "server.py")
        if os.path.exists(entry):
            return True, entry
        return False, entry
    if args:
        entry = args[0]
        if os.path.exists(entry):
            return True, entry
        return False, entry
    return False, command or "(missing command)"


def _voidcat_env(cfg: dict) -> dict:
    env = dict(cfg.get("env") or {})
    specstory_key = os.getenv("SPECSTORY_API_KEY", "").strip()
    if specstory_key:
        env["SPECSTORY_API_KEY"] = specstory_key
    return env


_VOIDCAT_SERVERS = {
    "voiddispatch": {
        "name": "VoidCat: VoidDispatcher",
        "command": "python",
        "args": [
            r"C:\Users\Wykeve\Projects\The Great Library\07_Systems\Ongoing\VoidDispatcher\src\void_dispatcher.py",
        ],
        "env": {},
    },
    "pantheon-memory-core": {
        "name": "VoidCat: Pantheon Memory Core",
        "command": "uv",
        "args": [
            "--directory",
            _PANTHEON_MEMORY_DIR,
            "run",
            "server.py",
        ],
        "env": {},
        "requires_env": ("SPECSTORY_API_KEY",),
    },
    "causal-memory-core": {
        "name": "VoidCat: Causal Memory Core",
        "command": "python",
        "args": [
            rf"{_CMC_DIR}\src\mcp_server.py",
        ],
        "env": {
            "PYTHONPATH": _CMC_DIR,
            "DB_PATH": rf"{_CMC_DIR}\causal_memory.db",
        },
    },
}

# Global flag to disable MCP if there are compatibility issues
MCP_DISABLED = os.environ.get("ODYSSEUS_DISABLE_MCP", "").lower() in ("1", "true", "yes")


async def register_builtin_servers(mcp_manager):
    """Connect all built-in MCP servers to the manager."""
    if MCP_DISABLED:
        logger.info("Built-in MCP servers disabled via ODYSSEUS_DISABLE_MCP")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python = sys.executable

    async def _connect_python_server(server_id: str, script_path: str, name: str):
        try:
            ok = await mcp_manager.connect_server(
                server_id=server_id,
                name=name,
                transport="stdio",
                command=python,
                args=[script_path],
                env={"PYTHONPATH": base_dir},
            )
            if ok:
                logger.info(f"Built-in MCP server registered: {name}")
            else:
                logger.warning(f"Built-in MCP server failed to connect: {name}")
        except asyncio.CancelledError:
            logger.warning(f"Built-in MCP server {name} cancelled")
            raise
        except BaseException as e:
            logger.warning(f"Built-in MCP server {name} error: {type(e).__name__}: {e}")

    for server_id, (script, name) in _BUILTIN_SERVERS.items():
        script_path = os.path.join(base_dir, script)
        if not os.path.exists(script_path):
            logger.warning(f"Built-in MCP server script not found: {script_path}")
            continue
        asyncio.create_task(_connect_python_server(server_id, script_path, name))

    # Register NPX-based servers in the background (they take longer to start)
    npx_path = _find_npx()
    logger.info(f"NPX binary resolved to: {npx_path}")

    async def _start_npx_servers():
        await asyncio.sleep(3)  # let Python servers finish first
        for server_id, cfg in _BUILTIN_NPX_SERVERS.items():
            # Skip the server if its npx package isn't cached. Without this
            # check, npx would try to download/install the package on first
            # use, which can take minutes (or hang) on fresh installs without
            # Playwright system deps. Wrapping that in asyncio.wait_for to
            # bound the wait sounds reasonable, but mcp.client.stdio uses an
            # internal anyio task group that can't survive the resulting
            # cross-task cancellation: it raises "Attempted to exit cancel
            # scope in a different task than it was entered in" in a sibling
            # task, which cascades cancellations into the rest of the event
            # loop and downs the app. Detecting installed-state up-front lets
            # us bail with a useful warning before we ever touch stdio_client.
            args = cfg["args"]
            pkg_spec = _npx_package_from_args(args)
            if pkg_spec and not await _is_npx_package_cached(npx_path, pkg_spec):
                logger.warning(
                    f"{cfg['name']} is not available.\n"
                    f"  Reason: npm package {pkg_spec!r} is not installed in the npx cache.\n"
                    f"  Impact: tools provided by this MCP server will be unavailable.\n"
                    f"  Fix:    {os.path.basename(npx_path)} -y {pkg_spec} --version\n"
                    f"          (run once, then restart Odysseus)\n"
                    f"  Notes:  this server is optional; see README.md "
                    f"'Built-in MCP servers' for details."
                )
                continue

            logger.info(f"Starting NPX server: {cfg['name']} ({npx_path} {' '.join(args)})")
            try:
                ok = await mcp_manager.connect_server(
                    server_id=server_id,
                    name=cfg["name"],
                    transport="stdio",
                    command=npx_path,
                    args=args,
                )
                if ok:
                    logger.info(f"Built-in NPX server registered: {cfg['name']}")
                else:
                    logger.warning(f"Built-in NPX server failed to connect: {cfg['name']}")
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                logger.warning(f"Built-in NPX server {cfg['name']} error: {type(e).__name__}: {e}")

    asyncio.create_task(_start_npx_servers())

    async def _start_voidcat_servers():
        await asyncio.sleep(5)  # let built-in servers settle first
        for server_id, cfg in _VOIDCAT_SERVERS.items():
            ready, detail = _voidcat_entrypoint_ready(cfg)
            if not ready:
                logger.warning(
                    f"{cfg['name']} not available - entrypoint not found: {detail}"
                )
                continue
            missing_env = [
                key for key in cfg.get("requires_env", ())
                if not os.getenv(key, "").strip()
            ]
            if missing_env:
                logger.warning(
                    f"{cfg['name']} not available - missing env: {', '.join(missing_env)}"
                )
                continue
            logger.info(f"Starting VoidCat MCP server: {cfg['name']}")
            try:
                ok = await mcp_manager.connect_server(
                    server_id=server_id,
                    name=cfg["name"],
                    transport="stdio",
                    command=cfg["command"],
                    args=cfg["args"],
                    env=_voidcat_env(cfg),
                )
                if ok:
                    logger.info(f"VoidCat MCP server registered: {cfg['name']}")
                else:
                    logger.warning(f"VoidCat MCP server failed to connect: {cfg['name']}")
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                logger.warning(f"VoidCat MCP server {cfg['name']} error: {type(e).__name__}: {e}")

    asyncio.create_task(_start_voidcat_servers())


def _npx_package_from_args(args):
    """Pick the package spec out of an npx args list shaped like
    ['-y', '<package@version>', ...flags]. Returns None if the
    convention doesn't match (we then skip the cache check and just
    try the connect)."""
    if not args:
        return None
    if "-y" in args:
        idx = args.index("-y") + 1
        if idx < len(args) and not args[idx].startswith("-"):
            return args[idx]
    # No -y prefix: first non-flag arg is the package
    for a in args:
        if not a.startswith("-"):
            return a
    return None


async def _is_npx_package_cached(npx_path, package_spec, timeout_s=5):
    """Probe whether an npx package is already in the local cache.

    Runs `npx --no-install <pkg> --version`. --no-install tells npx to
    fail instead of downloading, so a cache miss returns fast. We treat
    "exited 0 with non-empty stdout" as proof of a working cached copy.
    Anything else (non-zero exit, empty stdout, timeout, missing npx,
    network error) means we should skip the server.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            npx_path, "--no-install", package_spec, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, ValueError):
        return False
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return False
    return proc.returncode == 0 and bool(stdout.strip())
