"""
relevance_scorer.py — VoidCat Hearth Mode Relevance Engine

Lightweight, LLM-free keyword/domain scoring for the Open Lounge (Hearth) mode.
Determines which spirit should speak next based on recent conversation context.

No network calls. No model inference. Fast and cheap.
"""

import re
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")

# Minimum score for a spirit to "want to talk"
RELEVANCE_THRESHOLD = 2

# How many recent messages to consider when scoring
CONTEXT_WINDOW_MESSAGES = 5

# Cache of keyword sets per spirit
_KEYWORD_CACHE: dict[str, set[str]] = {}


def _load_spirit_keywords(spirit: str) -> set[str]:
    """
    Load and cache domain keywords for a spirit.
    Pulls from dispatcher's domain index if available, else reads persona directly.
    """
    if spirit in _KEYWORD_CACHE:
        return _KEYWORD_CACHE[spirit]

    keywords: set[str] = set()

    # Try importing the already-built domain index from dispatcher
    try:
        from src.dispatcher import _build_domain_index
        index = _build_domain_index()
        if spirit in index:
            keywords = set(index[spirit])
    except Exception:
        pass

    # Fallback: read persona directly
    if not keywords:
        persona_path = os.path.join(PANTHEON_ROOT, spirit, "persona.md")
        if os.path.isfile(persona_path):
            try:
                with open(persona_path, "r", encoding="utf-8") as f:
                    text = f.read().lower()
                words = re.findall(r"\b[a-z]{4,}\b", text)
                freq: dict[str, int] = {}
                for w in words:
                    freq[w] = freq.get(w, 0) + 1
                keywords = {
                    w for w, c in freq.items() if c >= 2
                }
            except Exception as e:
                logger.warning(f"Could not load keywords for {spirit}: {e}")

    _KEYWORD_CACHE[spirit] = keywords
    return keywords


def score_spirit(spirit: str, recent_messages: list[str]) -> int:
    """
    Score a spirit against recent conversation context.

    Args:
        spirit: Pantheon folder name (e.g. "ryuzu", "codey_coderson")
        recent_messages: List of recent message strings (most recent last)

    Returns:
        Integer relevance score. Higher = more relevant.
    """
    keywords = _load_spirit_keywords(spirit)
    if not keywords:
        return 0

    # Combine recent messages, weight more recent ones higher
    combined_words: dict[str, float] = {}
    n = len(recent_messages)
    for i, msg in enumerate(recent_messages[-CONTEXT_WINDOW_MESSAGES:]):
        weight = (i + 1) / n  # 0.2 → 1.0 scale from oldest to newest
        for word in re.findall(r"\b\w+\b", msg.lower()):
            combined_words[word] = combined_words.get(word, 0.0) + weight

    # Score = sum of weights for keyword matches
    score = sum(combined_words.get(kw, 0.0) for kw in keywords)
    return int(score * 10)  # Scale to integer for clean comparison


def rank_spirits(
    spirits: list[str],
    recent_messages: list[str],
    exclude: Optional[str] = None,
) -> list[tuple[str, int]]:
    """
    Rank all spirits by relevance against the recent conversation.

    Args:
        spirits: List of spirit folder names to consider
        recent_messages: Recent conversation context
        exclude: Spirit to exclude (e.g. the one who just spoke)

    Returns:
        List of (spirit_name, score) tuples, sorted highest first.
        Only spirits scoring above RELEVANCE_THRESHOLD are included.
    """
    results: list[tuple[str, int]] = []

    for spirit in spirits:
        if spirit == exclude:
            continue
        score = score_spirit(spirit, recent_messages)
        if score >= RELEVANCE_THRESHOLD:
            results.append((spirit, score))

    results.sort(key=lambda x: -x[1])
    logger.debug(f"Relevance scores: {results}")
    return results


def pick_next_speaker(
    spirits: list[str],
    recent_messages: list[str],
    last_speaker: Optional[str] = None,
) -> Optional[str]:
    """
    Pick the next spirit to speak in Hearth mode.
    Returns None if no spirit is relevant enough (thread goes quiet).

    Ties are broken by randomness for organic feel.
    """
    import random
    ranked = rank_spirits(spirits, recent_messages, exclude=last_speaker)
    if not ranked:
        return None

    # If there's a clear leader, pick them
    top_score = ranked[0][1]
    top_spirits = [s for s, sc in ranked if sc == top_score]

    # Random among tied top spirits for organic variation
    return random.choice(top_spirits)


def clear_cache() -> None:
    """Clear the keyword cache (call after persona files are updated)."""
    global _KEYWORD_CACHE
    _KEYWORD_CACHE = {}
    logger.debug("Relevance scorer keyword cache cleared.")
