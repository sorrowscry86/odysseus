"""
sequential_engine.py — VoidCat Board Room Turn Manager

The core execution engine for all multi-spirit interaction modes.
Manages turn queues, context accumulation, and session state.

Modes handled:
  - round_table:  One full sequential pass through tagged spirits
  - council:      Autonomous loop with Chair controlling resolution
  - hearth:       Open-ended loop driven by relevance scoring

Each turn yields a TurnResult for the GUI to render as a spirit bubble.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional

from src.council_tools import execute_council_tool, get_council_tools_for_spirit
from src.dispatcher import RoutingDecision
from src.spirit_engine import get_spirit_context

logger = logging.getLogger(__name__)

PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")

# ---------------------------------------------------------------------------
# Default Council configuration
# ---------------------------------------------------------------------------
COUNCIL_DEFAULT_MAX_ROUNDS = 10
# Diminishing extension schedule: 1st extension = 5, 2nd = 4, 3rd = 3, etc.
_EXTENSION_SCHEDULE = [5, 4, 3, 2, 1]
# Pause between spirit turns so each bubble lands before the next one fires.
INTER_TURN_DELAY_S = 1.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Result of a single spirit's turn. Yielded to the GUI layer."""
    spirit: str                  # Folder name (e.g. "ryuzu")
    display_name: str            # Human-readable name
    mode: str                    # Which session mode produced this
    response: str                # The spirit's generated response
    round_num: int               # Which round this belongs to (1-indexed)
    is_final: bool = False       # True if this closes the session
    is_thinking: bool = False    # Pre-turn signal: spirit is about to generate
    resolution: Optional[str] = None  # Populated when propose_resolution fires
    dissenting_views: Optional[str] = None
    extension_reason: Optional[str] = None  # Why Chair requested extension
    passed_to: Optional[str] = None         # Spirit tagged in via pass_turn


@dataclass
class SessionState:
    """Live state for a multi-spirit session."""
    mode: str
    spirits: list[str]
    chair: Optional[str]
    turn_queue: list[str]
    context: list[dict]          # Accumulated chat messages
    round_num: int = 1
    extension_count: int = 0
    max_rounds: int = COUNCIL_DEFAULT_MAX_ROUNDS
    resolved: bool = False
    user_interjected: bool = False


# ---------------------------------------------------------------------------
# Display name helper
# ---------------------------------------------------------------------------

def _display_name(folder: str) -> str:
    """Convert a Pantheon folder name to a display name."""
    _MAP = {
        "codey_coderson":    "Codey Coderson",
        "sonmi_451":         "Sonmi-451",
        "high_evolutionary": "High Evolutionary",
    }
    if folder in _MAP:
        return _MAP[folder]
    return folder.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Tool call detection helpers
# ---------------------------------------------------------------------------

def _detect_pass_turn(response: str) -> Optional[str]:
    """
    Detect if the spirit used the pass_turn tool in their response.
    Returns the target spirit folder name, or None.
    Looks for patterns like: pass_turn(@Ryuzu) or [PASS_TURN: ryuzu]
    """
    import re
    from src.dispatcher import _normalize_spirit_name
    # Pattern: pass_turn(@Name) or pass_turn("Name")
    m = re.search(r'pass_turn\s*[\(\[]\s*["\']?@?(\w+)["\']?\s*[\)\]]', response, re.IGNORECASE)
    if m:
        return _normalize_spirit_name(m.group(1))
    # Pattern: [PASS_TURN: name]
    m = re.search(r'\[PASS_TURN:\s*(\w+)\]', response, re.IGNORECASE)
    if m:
        return _normalize_spirit_name(m.group(1))
    return None


def _detect_propose_resolution(response: str) -> Optional[dict]:
    """
    Detect if the Chair called propose_resolution.
    Returns {"summary": ..., "dissenting_views": ...} or None.
    """
    import re
    m = re.search(
        r'propose_resolution\s*[\(\[]\s*["\']?([\s\S]+?)["\']?\s*[\)\]]',
        response, re.IGNORECASE
    )
    if m:
        return {"summary": m.group(1).strip(), "dissenting_views": None}
    # Also detect explicit [RESOLUTION: ...] marker spirits may emit
    m = re.search(r'\[RESOLUTION:\s*([\s\S]+?)\]', response, re.IGNORECASE)
    if m:
        return {"summary": m.group(1).strip(), "dissenting_views": None}
    return None


def _detect_request_extension(response: str) -> Optional[dict]:
    """
    Detect if the Chair called request_extension.
    Returns {"reason": ..., "rounds": N} or None.
    """
    import re
    m = re.search(
        r'request_extension\s*[\(\[]\s*["\']?([\s\S]+?)["\']?\s*[\)\]]',
        response, re.IGNORECASE
    )
    if m:
        return {"reason": m.group(1).strip(), "rounds": None}
    m = re.search(r'\[EXTENSION:\s*([\s\S]+?)\]', response, re.IGNORECASE)
    if m:
        return {"reason": m.group(1).strip(), "rounds": None}
    return None


# ---------------------------------------------------------------------------
# Core generation function (pluggable)
# ---------------------------------------------------------------------------

_MAX_TOOL_ROUNDS = 3


async def _generate_response(
    spirit: str,
    context: list[dict],
    generate_fn: Callable,
    role: str = "panel",
) -> str:
    """
    Call the model generation function with the spirit's context injected.

    generate_fn signature: async (messages, tools=None) -> (str, list[dict])
    The spirit's persona/grimoire is prepended as a system message, followed
    by a behavioral directive that prevents name-tag echo and sets the role.
    role: "chair" for the council arbiter, "panel" for all other spirits.

    If the spirit has permitted tools, an agentic loop executes up to
    _MAX_TOOL_ROUNDS rounds of tool calls before returning the final text.
    """
    spirit_ctx = get_spirit_context(spirit)
    display = _display_name(spirit)
    messages: list[dict] = []

    system_parts = []
    if spirit_ctx:
        system_parts.append(spirit_ctx)

    # Prevents the model from echoing the [Name]: turn-marker format
    system_parts.append(
        f"You are {display}, speaking in a multi-spirit council deliberation.\n"
        f"Respond directly in your own voice. Do NOT begin your response with "
        f"'[{display}]:' or any name prefix — the '[Name]:' labels in the "
        f"conversation history are turn markers only, not text to continue.\n"
        f"Speak as yourself. Reference other spirits by name when addressing them directly."
    )
    if role == "chair":
        system_parts.append(
            "As Chair of this council, your role is to maintain order, acknowledge "
            "each spirit's arguments fairly, and guide the deliberation toward a "
            "resolution. You are the arbiter — not an advocate for any position. "
            "Summarize where the panel agrees and disagrees, mediate conflicts, "
            "and drive toward a decision when the time is right."
        )

    messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    messages.extend(context)

    tools = get_council_tools_for_spirit(spirit)
    tool_round = 0

    try:
        while True:
            content, tool_calls = await generate_fn(messages, tools=tools or None)

            if not tool_calls or tool_round >= _MAX_TOOL_ROUNDS:
                return content or ""

            # Execute each tool call and append results
            messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                raw_args = fn.get("arguments", {})
                if isinstance(raw_args, dict):
                    args = raw_args
                elif isinstance(raw_args, str):
                    import json as _json
                    try:
                        args = _json.loads(raw_args)
                    except (ValueError, _json.JSONDecodeError):
                        args = {}
                else:
                    args = {}
                result = await execute_council_tool(tool_name, args)
                tool_call_id = tc.get("id", tool_name)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result,
                })
                logger.info("Spirit %s used tool %s → %d chars", spirit, tool_name, len(result))

            tool_round += 1

    except Exception as e:
        logger.error(f"Generation failed for {spirit}: {e}")
        return f"[{_display_name(spirit)} encountered an error: {e}]"


# ---------------------------------------------------------------------------
# Round Table Mode
# ---------------------------------------------------------------------------

async def run_round_table(
    decision: RoutingDecision,
    initial_context: list[dict],
    generate_fn: Callable,
) -> AsyncGenerator[TurnResult, None]:
    """
    Round Table: one sequential pass through tagged spirits.
    Each spirit sees the full context including all previous spirits' responses.
    """
    context = list(initial_context)
    spirits = list(decision.spirits)

    for i, spirit in enumerate(spirits):
        display = _display_name(spirit)

        # Signal that this spirit is about to generate so the frontend can show
        # a named spinner bubble before the model call starts.
        yield TurnResult(
            spirit=spirit,
            display_name=display,
            mode="round_table",
            response="",
            round_num=i + 1,
            is_thinking=True,
        )

        # Build the call context.
        # For spirits after the first, append a user cue so the conversation
        # ends on a user-role message rather than an assistant-role message.
        # Without this, some models treat the next generation as a continuation
        # of the previous assistant turn and produce truncated/corrupted output.
        call_context = list(context)
        if i > 0:
            call_context.append({
                "role": "user",
                "content": f"[{display}], please share your perspective.",
            })

        response = await _generate_response(spirit, call_context, generate_fn)

        # Persist to context for subsequent spirits: include the cue message so
        # the context maintains proper user→assistant pairs throughout the session.
        if i > 0:
            context.append({
                "role": "user",
                "content": f"[{display}], please share your perspective.",
            })
        context.append({"role": "assistant", "content": f"[{display}]: {response}"})

        # Check for pass_turn
        passed_to = _detect_pass_turn(response)
        if passed_to and passed_to not in spirits:
            spirits.append(passed_to)

        is_final = (spirit == spirits[-1])
        yield TurnResult(
            spirit=spirit,
            display_name=display,
            mode="round_table",
            response=response,
            round_num=i + 1,
            is_final=is_final,
            passed_to=passed_to,
        )


# ---------------------------------------------------------------------------
# Council Mode
# ---------------------------------------------------------------------------

async def run_council(
    decision: RoutingDecision,
    initial_context: list[dict],
    generate_fn: Callable,
    max_rounds: int = COUNCIL_DEFAULT_MAX_ROUNDS,
    user_interject_fn: Optional[Callable] = None,
) -> AsyncGenerator[TurnResult, None]:
    """
    Council: autonomous multi-round deliberation with a Chair.

    The Chair speaks first each round to frame or synthesize.
    Panel members then respond in sequence.
    The Chair may call propose_resolution() to end the session,
    or request_extension() when the round cap is hit.
    """
    chair = decision.chair
    panel = [s for s in decision.spirits if s != chair]
    context = list(initial_context)
    round_num = 1
    extension_count = 0
    current_max = max_rounds

    while True:
        # ── Chair's turn ──
        chair_response = await _generate_response(chair, context, generate_fn, role="chair")
        chair_display = _display_name(chair)
        context.append({"role": "assistant", "content": f"[{chair_display}]: {chair_response}"})

        # Check for resolution
        resolution = _detect_propose_resolution(chair_response)
        if resolution:
            yield TurnResult(
                spirit=chair,
                display_name=chair_display,
                mode="council",
                response=chair_response,
                round_num=round_num,
                is_final=True,
                resolution=resolution["summary"],
                dissenting_views=resolution.get("dissenting_views"),
            )
            return

        yield TurnResult(
            spirit=chair,
            display_name=chair_display,
            mode="council",
            response=chair_response,
            round_num=round_num,
        )
        await asyncio.sleep(INTER_TURN_DELAY_S)

        # ── Panel members ──
        for spirit in panel:
            response = await _generate_response(spirit, context, generate_fn)
            display = _display_name(spirit)
            context.append({"role": "assistant", "content": f"[{display}]: {response}"})

            passed_to = _detect_pass_turn(response)
            if passed_to and passed_to not in panel and passed_to != chair:
                panel.append(passed_to)

            yield TurnResult(
                spirit=spirit,
                display_name=display,
                mode="council",
                response=response,
                round_num=round_num,
                passed_to=passed_to,
            )
            await asyncio.sleep(INTER_TURN_DELAY_S)

        # ── Round cap check ──
        if round_num >= current_max:
            # Force Chair to respond at the cap
            cap_prompt = (
                f"The deliberation has reached the round limit ({current_max} rounds). "
                f"You must either call propose_resolution() to present your unified plan, "
                f"or call request_extension(reason) to continue for additional rounds."
            )
            context.append({"role": "system", "content": cap_prompt})
            chair_cap_response = await _generate_response(chair, context, generate_fn, role="chair")
            context.append({"role": "assistant", "content": f"[{chair_display}]: {chair_cap_response}"})

            # Check for extension
            extension = _detect_request_extension(chair_cap_response)
            if extension:
                ext_idx = min(extension_count, len(_EXTENSION_SCHEDULE) - 1)
                extra_rounds = _EXTENSION_SCHEDULE[ext_idx]
                current_max += extra_rounds
                extension_count += 1
                logger.info(f"Council extension granted: +{extra_rounds} rounds (extension #{extension_count})")
                yield TurnResult(
                    spirit=chair,
                    display_name=chair_display,
                    mode="council",
                    response=chair_cap_response,
                    round_num=round_num,
                    extension_reason=extension["reason"],
                )
                round_num += 1
                continue

            # Check for resolution in cap response
            resolution = _detect_propose_resolution(chair_cap_response)
            yield TurnResult(
                spirit=chair,
                display_name=chair_display,
                mode="council",
                response=chair_cap_response,
                round_num=round_num,
                is_final=True,
                resolution=resolution["summary"] if resolution else "No consensus reached.",
                dissenting_views=resolution.get("dissenting_views") if resolution else None,
            )
            return

        round_num += 1


# ---------------------------------------------------------------------------
# Hearth Mode
# ---------------------------------------------------------------------------

async def run_hearth(
    spirits: list[str],
    initial_context: list[dict],
    generate_fn: Callable,
    max_turns: int = 20,
) -> AsyncGenerator[TurnResult, None]:
    """
    Hearth: open-ended organic conversation.
    No chair. No agenda. Relevance scorer picks who speaks next.
    Yields turns until no spirit is relevant or max_turns is hit.
    """
    from src.relevance_scorer import pick_next_speaker

    context = list(initial_context)
    last_speaker: Optional[str] = None
    turn_count = 0

    # Extract recent message strings for the scorer
    def _recent_texts() -> list[str]:
        return [m.get("content", "") for m in context[-5:]]

    while turn_count < max_turns:
        next_spirit = pick_next_speaker(
            spirits=spirits,
            recent_messages=_recent_texts(),
            last_speaker=last_speaker,
        )

        if next_spirit is None:
            if turn_count == 0:
                # Bootstrap: opening message (e.g. "lounge") carries no domain keywords,
                # so the scorer returns nothing. Always produce an opening turn.
                import random
                candidates = [s for s in spirits if s != last_speaker]
                if not candidates:
                    break
                next_spirit = random.choice(candidates)
            else:
                # Nobody has anything to say — the hearth goes quiet
                logger.debug("Hearth: no spirit scored above threshold. Going quiet.")
                break

        display = _display_name(next_spirit)
        yield TurnResult(
            spirit=next_spirit,
            display_name=display,
            mode="hearth",
            response="",
            round_num=turn_count + 1,
            is_thinking=True,
        )

        response = await _generate_response(next_spirit, context, generate_fn)
        context.append({"role": "assistant", "content": f"[{display}]: {response}"})

        passed_to = _detect_pass_turn(response)

        turn_count += 1
        is_final = (turn_count >= max_turns)

        yield TurnResult(
            spirit=next_spirit,
            display_name=display,
            mode="hearth",
            response=response,
            round_num=turn_count,
            is_final=is_final,
            passed_to=passed_to,
        )

        # If the spirit explicitly tagged someone, jump to them next
        if passed_to and passed_to in spirits:
            last_speaker = next_spirit
            # Inject the tagged spirit at the front by temporarily making them score highest
            # We do this by adding a hint message
            context.append({
                "role": "system",
                "content": f"[{display}] has passed the conversation to [{_display_name(passed_to)}]."
            })
            next_forced = passed_to
            forced_response = await _generate_response(next_forced, context, generate_fn)
            forced_display = _display_name(next_forced)
            context.append({"role": "assistant", "content": f"[{forced_display}]: {forced_response}"})
            turn_count += 1
            yield TurnResult(
                spirit=next_forced,
                display_name=forced_display,
                mode="hearth",
                response=forced_response,
                round_num=turn_count,
                is_final=(turn_count >= max_turns),
            )
            last_speaker = next_forced
        else:
            last_speaker = next_spirit
