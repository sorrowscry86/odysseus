import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# The Pantheon is mounted into the container at /app/pantheon
PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")


def _assert_not_immutable(path: str) -> None:
    """Raise PermissionError if path targets persona.md — immutable by law."""
    if os.path.basename(path).lower() == "persona.md":
        raise PermissionError(
            f"persona.md is immutable — writes are forbidden: {path}"
        )

VOIDCAT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "update_grimoire",
            "description": "Update the Spirit's Grimoire with new knowledge or learnings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_name": {
                        "type": "string",
                        "description": "The name of the spirit (e.g., Ryuzu, Albedo, Codey)."
                    },
                    "knowledge_entry": {
                        "type": "string",
                        "description": "The new knowledge or learning to append to the grimoire."
                    }
                },
                "required": ["character_name", "knowledge_entry"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pass_turn",
            "description": "Tag in another Spirit to respond next in a multi-spirit session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_spirit": {
                        "type": "string",
                        "description": "Name of the Spirit to hand the conversation to."
                    },
                    "context_note": {
                        "type": "string",
                        "description": "Optional note explaining why you are tagging them in."
                    }
                },
                "required": ["target_spirit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_resolution",
            "description": "Chair-only (Council mode). End the deliberation and present a unified proposal to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The unified proposal or consensus summary."
                    },
                    "dissenting_views": {
                        "type": "string",
                        "description": "Optional. Any unresolved disagreements or minority positions."
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_extension",
            "description": "Chair-only (Council mode). Request additional deliberation rounds when the cap is reached without consensus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the panel needs more time to reach consensus."
                    },
                    "rounds": {
                        "type": "integer",
                        "description": "Optional. Requested additional rounds. Auto-capped by the diminishing schedule."
                    }
                },
                "required": ["reason"]
            }
        }
    },
]

def execute_update_grimoire(args: Dict[str, Any]) -> str:
    """
    Rides the wave to update the Spirit's grimoire.
    """
    character_name = args.get("character_name", "").strip()
    knowledge = args.get("knowledge_entry", "").strip()

    if not character_name or not knowledge:
        return "Error: Missing character_name or knowledge_entry."

    safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '_', '-')).strip().lower()
    if not safe_name:
        return "Error: Invalid character_name."
    spirit_dir = os.path.join(PANTHEON_ROOT, safe_name)

    if not os.path.isdir(spirit_dir):
        return f"Error: Spirit directory not found for {safe_name}."

    grimoire_path = os.path.join(spirit_dir, "grimoire.md")

    try:
        _assert_not_immutable(grimoire_path)  # Guard against persona.md writes
        # Append knowledge to grimoire
        with open(grimoire_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n### Session Learning\n- {knowledge}\n")
        return f"Success: Added learning to {safe_name}'s Grimoire."
    except Exception as e:
        logger.error(f"Bad karma updating grimoire for {safe_name}: {e}")
        return f"Error: Failed to update grimoire: {e}"
