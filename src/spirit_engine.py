import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# The Pantheon is mounted into the container at /app/pantheon
PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")

def get_spirit_context(character_name: str) -> Optional[str]:
    """
    Rides the wave into the Pantheon volume to fetch the Spirit's persona and grimoire.
    Injects them directly into the context stream.
    """
    if not character_name:
        return None

    # Mellow path normalization — lowercase for case-insensitive folder matching
    safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '_', '-')).strip().lower()
    if not safe_name:
        return None
    spirit_dir = os.path.join(PANTHEON_ROOT, safe_name)

    if not os.path.isdir(spirit_dir):
        logger.debug(f"Spirit directory not found for {safe_name} at {spirit_dir}")
        return None

    persona_path = os.path.join(spirit_dir, "persona.md")
    grimoire_path = os.path.join(spirit_dir, "grimoire.md")

    context_blocks = []
    
    if os.path.isfile(persona_path):
        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                context_blocks.append(f"--- {safe_name} Persona ---\n{f.read()}")
        except Exception as e:
            logger.error(f"Bad karma reading persona for {safe_name}: {e}")

    if os.path.isfile(grimoire_path):
        try:
            with open(grimoire_path, 'r', encoding='utf-8') as f:
                context_blocks.append(f"--- {safe_name} Grimoire ---\n{f.read()}")
        except Exception as e:
            logger.error(f"Bad karma reading grimoire for {safe_name}: {e}")

    if context_blocks:
        return "\n\n".join(context_blocks)
    return None
