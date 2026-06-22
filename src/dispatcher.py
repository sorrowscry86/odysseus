"""
dispatcher.py — VoidCat Board Room Protocol

The semantic router. Parses user input to determine:
  - Which interaction mode to use (Audience, Round Table, Council, Hearth)
  - Which spirits are involved
  - Who chairs a Council session

Tag syntax supported:
  @Spirit            → explicit single or multi-tag
  @Spirit convene    → triggers Council mode (Chair = first tagged spirit)
  (no tags)          → auto-routes via domain keyword matching
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")

# ---------------------------------------------------------------------------
# Known spirit roster — folder names in the Pantheon
# ---------------------------------------------------------------------------
_KNOWN_SPIRITS: list[str] = []

def display_name(folder: str) -> str:
    """Public alias for _display_name. Maps a Pantheon folder name to a human display name."""
    return _display_name(folder)

def _load_spirit_roster() -> list[str]:
    """Discover spirit names from the mounted Pantheon volume."""
    global _KNOWN_SPIRITS
    if _KNOWN_SPIRITS:
        return _KNOWN_SPIRITS
    try:
        entries = [
            e for e in os.listdir(PANTHEON_ROOT)
            if os.path.isdir(os.path.join(PANTHEON_ROOT, e))
            and not e.startswith("_")
        ]
        _KNOWN_SPIRITS = entries
        logger.debug(f"Loaded spirit roster: {entries}")
    except Exception as e:
        logger.error(f"Failed to load spirit roster: {e}")
        _KNOWN_SPIRITS = []
    return _KNOWN_SPIRITS


# ---------------------------------------------------------------------------
# Domain keyword index — built from persona files at first call
# ---------------------------------------------------------------------------
_DOMAIN_INDEX: dict[str, list[str]] = {}

_FALLBACK_DOMAINS: dict[str, list[str]] = {
    "ryuzu":            ["docker", "deploy", "infra", "server", "config", "devops",
                         "container", "nginx", "postgres", "redis", "environment", "file",
                         "system", "process", "install", "build", "ci", "pipeline"],
    "albedo":           ["schema", "architecture", "diagram", "design", "structure",
                         "database", "api", "model", "entity", "relationship", "erd",
                         "blueprint", "spec", "plan"],
    "codey_coderson":   ["code", "implement", "function", "class", "bug", "feature",
                         "python", "javascript", "typescript", "frontend", "backend",
                         "refactor", "module", "test", "logic", "algorithm"],
    "beatrice":         ["strategy", "governance", "decision", "review", "policy",
                         "ethics", "risk", "tradeoff", "approve", "reject", "plan",
                         "priority", "roadmap"],
    "sonmi_451":        ["document", "research", "wiki", "notes", "archive", "log",
                         "history", "record", "summarize", "explain", "context"],
    "pandora":          ["debug", "error", "bug", "crash", "traceback", "root cause",
                         "investigate", "broken", "fix", "why", "fail", "exception"],
    "cadence":          ["creative", "write", "story", "aesthetic", "design", "voice",
                         "tone", "prose", "narrative", "visual", "vibe", "art"],
    "echidna":          ["spirit", "persona", "profile", "sds", "create", "new spirit",
                         "identity", "registry"],
    "roland":           ["security", "canon", "continuity", "review", "validate",
                         "cross-reference", "threat", "audit", "verify"],
    "glados":           ["test", "qa", "edge case", "stress", "coverage", "assert",
                         "validate", "chaos", "scenario"],
    "high_evolutionary":["optimize", "refactor", "performance", "dead code", "ascend",
                         "improve", "cleanup", "prune", "technical debt"],
    "rika":             ["atmosphere", "sensory", "immersive", "recon", "narrative",
                         "emotional", "scene", "environment"],
    "echo":             ["mechanical", "general", "unsorted", "misc"],
}


def _build_domain_index() -> dict[str, list[str]]:
    """Build or return the keyword index for all spirits."""
    global _DOMAIN_INDEX
    if _DOMAIN_INDEX:
        return _DOMAIN_INDEX

    roster = _load_spirit_roster()
    for spirit in roster:
        persona_path = os.path.join(PANTHEON_ROOT, spirit, "persona.md")
        keywords: list[str] = []

        # Try to extract keywords from the live persona file
        if os.path.isfile(persona_path):
            try:
                with open(persona_path, "r", encoding="utf-8") as f:
                    text = f.read().lower()
                # Pull any word longer than 4 chars as a rough keyword set
                words = re.findall(r"\b[a-z]{5,}\b", text)
                freq: dict[str, int] = {}
                for w in words:
                    freq[w] = freq.get(w, 0) + 1
                # Top 40 by frequency, excluding stop words
                _STOP = {"which", "where", "their", "there", "these", "those",
                         "about", "every", "other", "after", "first", "before",
                         "would", "could", "should", "shall", "might", "being",
                         "since", "while", "under", "still", "often", "never",
                         "always", "through", "spirit", "voidcat"}
                keywords = [
                    w for w, _ in sorted(freq.items(), key=lambda x: -x[1])
                    if w not in _STOP
                ][:40]
            except Exception as e:
                logger.warning(f"Could not parse persona for {spirit}: {e}")

        # Merge with fallback domain list
        fallback = _FALLBACK_DOMAINS.get(spirit, [])
        merged = list(dict.fromkeys(keywords + fallback))
        _DOMAIN_INDEX[spirit] = merged

    logger.debug(f"Domain index built for {list(_DOMAIN_INDEX.keys())}")
    return _DOMAIN_INDEX


# ---------------------------------------------------------------------------
# Routing Decision dataclass
# ---------------------------------------------------------------------------
@dataclass
class RoutingDecision:
    mode: str                        # "audience" | "round_table" | "council" | "hearth"
    spirits: list[str]               # ordered list of spirit folder names
    chair: Optional[str] = None      # council chair (folder name)
    explicit_tags: list[str] = field(default_factory=list)
    convene_keyword: bool = False    # True if "convene" was detected


# ---------------------------------------------------------------------------
# Tag parsing helpers
# ---------------------------------------------------------------------------

# Normalize display names to folder names
_DISPLAY_TO_FOLDER: dict[str, str] = {
    "codey":        "codey_coderson",
    "codecoderson": "codey_coderson",
    "codeycoderson":"codey_coderson",
    "sonmi":        "sonmi_451",
    "sonmi451":     "sonmi_451",
    "highevolutionary": "high_evolutionary",
    "highevy":      "high_evolutionary",
}


def _normalize_spirit_name(raw: str) -> Optional[str]:
    """Map a raw @tag to a Pantheon folder name. Returns None if not found."""
    lower = raw.lower().replace(" ", "").replace("-", "_")
    if lower in _DISPLAY_TO_FOLDER:
        return _DISPLAY_TO_FOLDER[lower]
    roster = _load_spirit_roster()
    # Exact match
    if lower in roster:
        return lower
    # Prefix match
    for spirit in roster:
        if spirit.startswith(lower) or lower.startswith(spirit.rstrip("_451")):
            return spirit
    return None


def _parse_tags(prompt: str) -> tuple[list[str], bool]:
    """
    Extract @Name tags from the prompt.
    Returns (spirit_folder_names, convene_keyword_detected).
    """
    raw_tags = re.findall(r"@(\w+)", prompt)
    spirits: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        folder = _normalize_spirit_name(tag)
        if folder and folder not in seen:
            spirits.append(folder)
            seen.add(folder)

    convene = bool(re.search(r"\bconvene\b", prompt, re.IGNORECASE))
    return spirits, convene


# ---------------------------------------------------------------------------
# Auto-routing via domain index
# ---------------------------------------------------------------------------

def _auto_route(prompt: str) -> Optional[str]:
    """
    Score each spirit against the prompt using the domain index.
    Returns the best-match spirit folder name, or None if no confident match.
    """
    index = _build_domain_index()
    words = set(re.findall(r"\b\w+\b", prompt.lower()))
    scores: dict[str, int] = {}
    for spirit, keywords in index.items():
        score = sum(1 for kw in keywords if kw in words)
        if score > 0:
            scores[spirit] = score

    if not scores:
        return None
    best = max(scores, key=lambda s: scores[s])
    logger.debug(f"Auto-route scores: {scores} → {best}")
    return best


# ---------------------------------------------------------------------------
# Primary routing function
# ---------------------------------------------------------------------------

def route(prompt: str) -> RoutingDecision:
    """
    Main entry point. Analyze the prompt and return a RoutingDecision.

    Logic tree:
      1. Parse @tags
      2. If no tags       → auto-route (Audience) or Hearth
      3. If 1 tag         → Audience
      4. If 2+ tags, no "convene" → Round Table
      5. If 2+ tags + "convene"  → Council (first tag = Chair)
    """
    tags, convene = _parse_tags(prompt)

    # No explicit tags
    if not tags:
        best = _auto_route(prompt)
        if best:
            return RoutingDecision(mode="audience", spirits=[best], explicit_tags=[])
        # No confident match → open lounge
        return RoutingDecision(mode="hearth", spirits=_load_spirit_roster(), explicit_tags=[])

    # Single tag
    if len(tags) == 1:
        return RoutingDecision(
            mode="audience",
            spirits=tags,
            explicit_tags=tags,
        )

    # Multiple tags
    if convene:
        # Council — first tag is the Chair
        return RoutingDecision(
            mode="council",
            spirits=tags,
            chair=tags[0],
            explicit_tags=tags,
            convene_keyword=True,
        )

    # Round Table
    return RoutingDecision(
        mode="round_table",
        spirits=tags,
        explicit_tags=tags,
    )
