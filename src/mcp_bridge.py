"""
mcp_bridge.py — VoidCat MCP Gatekeeper

Fences MCP tool execution behind context-aware spirit permissions.
Ryuzu remains the Gatekeeper for infrastructure tools.
Each spirit's allowed tool domains are enforced here before dispatch.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spirit permission matrix
# Each spirit maps to a set of allowed tool categories.
# "any" = unrestricted access (Ryuzu only — she IS the infrastructure)
# ---------------------------------------------------------------------------
_SPIRIT_PERMISSIONS: dict[str, set[str]] = {
    "ryuzu":            {"any"},
    "echo":             {"any"},
    "albedo":           {"read_file", "write_file", "bash", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn", "propose_resolution",
                         "find_references", "scan_grimoire"},
    "beatrice":         {"read_file", "write_file", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn", "propose_resolution",
                         "request_extension"},
    "codey_coderson":   {"bash", "python", "read_file", "write_file", "edit_file",
                         "grep", "glob", "ls", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn"},
    "sonmi_451":        {"read_file", "write_file", "web_search", "web_fetch",
                         "update_grimoire", "manage_documents", "pass_turn"},
    "pandora":          {"bash", "python", "read_file", "grep", "glob", "ls",
                         "web_search", "web_fetch", "update_grimoire", "pass_turn"},
    "cadence":          {"read_file", "write_file", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn"},
    "echidna":          {"read_file", "write_file", "update_grimoire", "pass_turn"},
    "roland":           {"read_file", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn"},
    "glados":           {"bash", "python", "read_file", "write_file", "grep",
                         "glob", "ls", "web_search", "update_grimoire", "pass_turn"},
    "high_evolutionary":{"bash", "python", "read_file", "write_file", "edit_file",
                         "grep", "glob", "ls", "update_grimoire", "pass_turn"},
    "rika":             {"read_file", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn"},
    "vivy":             {"read_file", "write_file", "web_search", "web_fetch",
                         "update_grimoire", "pass_turn",
                         "diff_sessions", "verify_claim"},
    # Default for unrecognized spirits
    "_default":         {"web_search", "web_fetch", "read_file", "update_grimoire",
                         "pass_turn"},
}


def is_tool_permitted(spirit: str, tool_name: str) -> bool:
    """
    Check if a spirit is allowed to execute a given tool.

    Args:
        spirit: Pantheon folder name (e.g. "ryuzu", "codey_coderson")
        tool_name: The tool type being requested

    Returns:
        True if permitted, False if blocked.
    """
    perms = _SPIRIT_PERMISSIONS.get(spirit, _SPIRIT_PERMISSIONS["_default"])

    if "any" in perms:
        return True

    allowed = tool_name in perms
    if not allowed:
        logger.warning(
            f"MCP Gate: {spirit} attempted unauthorized tool '{tool_name}' — BLOCKED"
        )
    return allowed


def get_permitted_tools(spirit: str) -> set[str]:
    """Return the full set of tools a spirit is permitted to use."""
    perms = _SPIRIT_PERMISSIONS.get(spirit, _SPIRIT_PERMISSIONS["_default"])
    if "any" in perms:
        return {"any"}
    return set(perms)


def filter_tool_schemas(spirit: str, schemas: list[dict]) -> list[dict]:
    """
    Filter the FUNCTION_TOOL_SCHEMAS to only include tools the spirit
    is permitted to use. Prevents spirits from even seeing tools outside
    their domain, reducing prompt injection surface.

    Args:
        spirit: Pantheon folder name
        schemas: The full FUNCTION_TOOL_SCHEMAS list

    Returns:
        Filtered list of schemas for this spirit.
    """
    perms = get_permitted_tools(spirit)
    if "any" in perms:
        return schemas

    filtered = []
    for schema in schemas:
        fn = schema.get("function", {})
        tool_name = fn.get("name", "")
        if tool_name in perms:
            filtered.append(schema)

    logger.debug(
        f"MCP Gate: {spirit} sees {len(filtered)}/{len(schemas)} tools"
    )
    return filtered


def assert_tool_permitted(spirit: str, tool_name: str) -> None:
    """
    Raise a PermissionError if the spirit is not allowed to use the tool.
    Use this as a hard gate before executing any tool call.
    """
    if not is_tool_permitted(spirit, tool_name):
        raise PermissionError(
            f"Spirit '{spirit}' is not authorized to use tool '{tool_name}'. "
            f"This incident has been logged."
        )
