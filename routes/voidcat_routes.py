"""
voidcat_routes.py — VoidCat Board Room API

Dedicated endpoints for the Spirit Communicator Board Room Protocol.
These routes sit alongside the standard Odysseus chat routes and do NOT
modify the core chat flow — zero risk to existing functionality.

Endpoints:
  POST /api/voidcat/dispatch        — Route a prompt and get a RoutingDecision
  POST /api/voidcat/round_table     — Execute a Round Table session
  POST /api/voidcat/council         — Execute a Council deliberation session
  POST /api/voidcat/hearth          — Execute an open Hearth session
  GET  /api/voidcat/spirits         — List available spirits from the Pantheon
  GET  /api/voidcat/spirit/{name}   — Get a single spirit's metadata
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.dispatcher import route, RoutingDecision, _load_spirit_roster
from src.sequential_engine import (
    run_round_table,
    run_council,
    run_hearth,
    COUNCIL_DEFAULT_MAX_ROUNDS,
    _display_name,
)
from src.spirit_engine import get_spirit_context
from src.mcp_bridge import get_permitted_tools

logger = logging.getLogger(__name__)

PANTHEON_ROOT = os.getenv("PANTHEON_ROOT", "/app/pantheon/01_Active_Profiles")

# Single pending convene set by the desktop launcher.
# Consumed once by the frontend on the next page load.
_pending_convene: dict = {}

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DispatchRequest(BaseModel):
    prompt: str

class BoardRoomRequest(BaseModel):
    prompt: str
    spirits: Optional[List[str]] = None   # override auto-dispatch
    chair: Optional[str] = None           # override for Council mode
    max_rounds: Optional[int] = COUNCIL_DEFAULT_MAX_ROUNDS
    endpoint_url: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None

# ---------------------------------------------------------------------------
# LLM generation shim
# Wraps the existing Odysseus LLM infrastructure.
# ---------------------------------------------------------------------------

def _resolve_headers(endpoint_url: str, owner: Optional[str] = None) -> dict:
    """Resolve auth headers for endpoint_url by looking up the stored API key.

    Queries ModelEndpoint rows for a URL match, then falls through to
    resolve_endpoint_runtime (which handles env-var fallbacks for OpenRouter,
    Anthropic, etc.) and builds the correct Authorization/x-api-key headers.
    """
    from src.endpoint_resolver import resolve_endpoint_runtime, build_headers, normalize_base
    from core.database import SessionLocal, ModelEndpoint as ME

    base = normalize_base(endpoint_url)
    db = SessionLocal()
    try:
        rows = db.query(ME).filter(ME.is_enabled == True).all()
        for row in rows:
            if normalize_base(row.base_url or "") == base:
                _, api_key = resolve_endpoint_runtime(row, owner=owner)
                return build_headers(api_key, base)
    except Exception as e:
        logger.warning("Could not resolve headers for %s: %s", endpoint_url, e)
    finally:
        db.close()
    # No matching stored endpoint — build_headers with no key so env-var
    # fallbacks (OPENROUTER_API_KEY, etc.) can still apply downstream.
    from src.endpoint_resolver import build_headers, normalize_base as _nb
    return build_headers(None, _nb(endpoint_url))


def _build_generate_fn(endpoint_url: str, model: str, headers: dict = None):
    """
    Build a generate function that calls the Odysseus LLM stack.
    Supports optional tool calling: when tools are provided the function
    returns (content: str, tool_calls: list); otherwise returns (str, []).
    """
    from src.llm_core import llm_call_async, llm_call_with_tools_async
    from src.text_helpers import strip_think

    async def generate(messages: List[Dict], tools: Optional[List[Dict]] = None) -> tuple[str, list]:
        try:
            if tools:
                content, tool_calls = await llm_call_with_tools_async(
                    endpoint_url, model, messages, tools, headers=headers or {}
                )
                return strip_think(content or "", prose=False, prompt_echo=True), tool_calls
            else:
                reply = await llm_call_async(
                    endpoint_url, model, messages, headers=headers or {}
                )
                return strip_think(reply or "", prose=False, prompt_echo=True), []
        except Exception as e:
            logger.error(f"VoidCat generate_fn failed: {e}")
            return f"[Error: {e}]", []

    return generate


# ---------------------------------------------------------------------------
# SSE formatting helper
# ---------------------------------------------------------------------------

def _sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# Router setup
# ---------------------------------------------------------------------------

def setup_voidcat_routes(session_manager) -> APIRouter:
    router = APIRouter()

    # ── GET /api/spirits ──────────────────────────────────────────
    @router.get("/api/spirits")
    async def get_spirits():
        """Return the spirit roster from the Pantheon mount."""
        try:
            from src.dispatcher import _load_spirit_roster, PANTHEON_ROOT
            roster = _load_spirit_roster()
            result = []
            for folder in roster:
                grimoire_path = os.path.join(PANTHEON_ROOT, folder, "grimoire.md")
                result.append({
                    "folder": folder,
                    "display_name": _display_name(folder),
                    "has_grimoire": os.path.isfile(grimoire_path),
                })
            return result
        except Exception as e:
            logger.warning(f"Failed to load spirit roster: {e}")
            return []

    # ── GET /api/voidcat/spirits ──────────────────────────────────────────
    @router.get("/api/voidcat/spirits")
    async def list_spirits():
        """Return all available spirits from the mounted Pantheon."""
        roster = _load_spirit_roster()
        spirits = []
        for folder in roster:
            avatar_path = f"/static/spirits/{folder}.jpg"
            spirits.append({
                "key": folder,
                "name": _display_name(folder),
                "avatar": avatar_path,
                "tools": sorted(get_permitted_tools(folder) - {"any"}),
            })
        return {"spirits": spirits}

    # ── GET /api/voidcat/spirit/{name} ────────────────────────────────────
    @router.get("/api/voidcat/spirit/{name}")
    async def get_spirit(name: str):
        """Return a single spirit's metadata and persona excerpt."""
        ctx = get_spirit_context(name)
        if ctx is None:
            raise HTTPException(404, f"Spirit '{name}' not found in Pantheon")
        return {
            "key": name,
            "name": _display_name(name),
            "avatar": f"/static/spirits/{name}.jpg",
            "context_preview": ctx[:500] + "…" if len(ctx) > 500 else ctx,
            "tools": sorted(get_permitted_tools(name) - {"any"}),
        }

    # ── POST /api/voidcat/convene-queue ──────────────────────────────────────
    @router.post("/api/voidcat/convene-queue")
    async def queue_convene(req: Request):
        """Store a pending Board Room convene set by the desktop launcher."""
        data = await req.json()
        _pending_convene.clear()
        _pending_convene.update({
            "prompt": data.get("prompt", ""),
            "spirits": data.get("spirits", ""),
            "ts": time.time(),
        })
        return {"ok": True}

    # ── GET /api/voidcat/convene-queue ────────────────────────────────────────
    @router.get("/api/voidcat/convene-queue")
    async def get_convene_queue():
        """Retrieve and clear any pending Board Room convene (consumed once)."""
        if not _pending_convene or time.time() - _pending_convene.get("ts", 0) > 30:
            return {"prompt": None}
        result = {
            "prompt": _pending_convene.get("prompt"),
            "spirits": _pending_convene.get("spirits", ""),
        }
        _pending_convene.clear()
        return result

    # ── POST /api/voidcat/dispatch ────────────────────────────────────────
    @router.post("/api/voidcat/dispatch")
    async def dispatch_prompt(req: DispatchRequest):
        """
        Analyze a prompt and return the Board Room routing decision.
        The frontend can use this to preview which mode/spirits will activate
        before starting the actual session.
        """
        decision = route(req.prompt)
        return {
            "mode": decision.mode,
            "spirits": decision.spirits,
            "spirit_names": [_display_name(s) for s in decision.spirits],
            "chair": decision.chair,
            "chair_name": _display_name(decision.chair) if decision.chair else None,
            "explicit_tags": decision.explicit_tags,
        }

    # ── POST /api/voidcat/audience ────────────────────────────────────────
    @router.post("/api/voidcat/audience")
    async def audience(req: BoardRoomRequest, request: Request):
        """
        Execute a single-spirit Audience session.
        Injects the spirit's persona/grimoire as a system prompt and streams
        a single TurnResult event — same SSE format as round_table/council/hearth.
        """
        if not req.endpoint_url or not req.model:
            raise HTTPException(400, "endpoint_url and model are required")

        spirit = (req.spirits or [])[0] if req.spirits else None
        if not spirit:
            decision = route(req.prompt)
            spirit = decision.spirits[0] if decision.spirits else None
        if not spirit:
            raise HTTPException(400, "Could not resolve a spirit for this audience session")

        headers = _resolve_headers(req.endpoint_url)
        generate_fn = _build_generate_fn(req.endpoint_url, req.model, headers)

        if req.session_id:
            try:
                sess = session_manager.get_session(req.session_id)
                if sess:
                    from core.models import ChatMessage
                    sess.add_message(ChatMessage("user", req.prompt))
                    session_manager.save_sessions()
            except Exception as se:
                logger.error(f"Failed to persist user prompt to DB: {se}")

        initial_context = [{"role": "user", "content": req.prompt}]

        async def stream():
            from src.sequential_engine import _generate_response, _display_name
            try:
                response = await _generate_response(spirit, initial_context, generate_fn)
                display = _display_name(spirit)

                if req.session_id:
                    try:
                        sess = session_manager.get_session(req.session_id)
                        if sess:
                            from core.models import ChatMessage
                            metadata = {
                                "spirit": spirit,
                                "character_name": display,
                                "mode": "audience",
                                "round_num": 1,
                            }
                            sess.add_message(ChatMessage("assistant", response, metadata=metadata))
                            session_manager.save_sessions()
                    except Exception as se:
                        logger.error(f"Failed to persist audience turn to DB: {se}")

                yield _sse("turn", {
                    "spirit": spirit,
                    "display_name": display,
                    "mode": "audience",
                    "response": response,
                    "round_num": 1,
                    "is_final": True,
                    "passed_to": None,
                })
                yield _sse("done", {"mode": "audience"})
            except Exception as e:
                logger.error(f"Audience stream error: {e}")
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(stream(), media_type="text/event-stream")

    # ── POST /api/voidcat/round_table ─────────────────────────────────────
    @router.post("/api/voidcat/round_table")
    async def round_table(req: BoardRoomRequest, request: Request):
        """
        Execute a Round Table session. Streams TurnResult events via SSE.
        """
        from src.auth_helpers import get_current_user
        from routes.session_routes import _verify_session_owner

        # Resolve model/endpoint
        if not req.endpoint_url or not req.model:
            raise HTTPException(400, "endpoint_url and model are required")

        headers = _resolve_headers(req.endpoint_url)
        generate_fn = _build_generate_fn(req.endpoint_url, req.model, headers)

        # Build the routing decision
        if req.spirits:
            decision = RoutingDecision(
                mode="round_table",
                spirits=req.spirits,
                explicit_tags=req.spirits,
            )
        else:
            decision = route(req.prompt)
            decision.mode = "round_table"

        # Persist user message to session history
        if req.session_id:
            try:
                sess = session_manager.get_session(req.session_id)
                if sess:
                    from core.models import ChatMessage
                    sess.add_message(ChatMessage("user", req.prompt))
                    session_manager.save_sessions()
            except Exception as se:
                logger.error(f"Failed to persist user prompt to DB: {se}")

        initial_context = [{"role": "user", "content": req.prompt}]

        async def stream():
            try:
                async for turn in run_round_table(decision, initial_context, generate_fn):
                    # Pre-turn thinking signal — tells the frontend which spirit is generating
                    if turn.is_thinking:
                        yield _sse("spirit_thinking", {
                            "spirit": turn.spirit,
                            "display_name": turn.display_name,
                            "mode": turn.mode,
                            "round_num": turn.round_num,
                        })
                        continue

                    # Persist turn to session history
                    if req.session_id:
                        try:
                            sess = session_manager.get_session(req.session_id)
                            if sess:
                                from core.models import ChatMessage
                                metadata = {
                                    "spirit": turn.spirit,
                                    "character_name": turn.display_name,
                                    "mode": turn.mode,
                                    "round_num": turn.round_num,
                                    "passed_to": turn.passed_to,
                                }
                                sess.add_message(ChatMessage("assistant", turn.response, metadata=metadata))
                                session_manager.save_sessions()
                        except Exception as se:
                            logger.error(f"Failed to persist round_table turn to DB: {se}")

                    yield _sse("turn", {
                        "spirit": turn.spirit,
                        "display_name": turn.display_name,
                        "mode": turn.mode,
                        "response": turn.response,
                        "round_num": turn.round_num,
                        "is_final": turn.is_final,
                        "passed_to": turn.passed_to,
                    })
                yield _sse("done", {"mode": "round_table"})
            except Exception as e:
                logger.error(f"Round Table stream error: {e}")
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(stream(), media_type="text/event-stream")

    # ── POST /api/voidcat/council ─────────────────────────────────────────
    @router.post("/api/voidcat/council")
    async def council(req: BoardRoomRequest, request: Request):
        """
        Execute a Council deliberation session. Streams TurnResult events via SSE.
        Chair is required.
        """
        if not req.endpoint_url or not req.model:
            raise HTTPException(400, "endpoint_url and model are required")

        # Build routing decision
        if req.spirits:
            chair = req.chair or req.spirits[0]
            decision = RoutingDecision(
                mode="council",
                spirits=req.spirits,
                chair=chair,
                explicit_tags=req.spirits,
                convene_keyword=True,
            )
        else:
            decision = route(req.prompt)
            if decision.mode != "council":
                raise HTTPException(400, "Prompt did not resolve to Council mode. Use @Name convene syntax or provide spirits list with a chair.")

        headers = _resolve_headers(req.endpoint_url)
        generate_fn = _build_generate_fn(req.endpoint_url, req.model, headers)

        # Persist user message to session history
        if req.session_id:
            try:
                sess = session_manager.get_session(req.session_id)
                if sess:
                    from core.models import ChatMessage
                    sess.add_message(ChatMessage("user", req.prompt))
                    session_manager.save_sessions()
            except Exception as se:
                logger.error(f"Failed to persist user prompt to DB: {se}")

        initial_context = [{"role": "user", "content": req.prompt}]
        max_rounds = req.max_rounds or COUNCIL_DEFAULT_MAX_ROUNDS

        async def stream():
            try:
                async for turn in run_council(decision, initial_context, generate_fn, max_rounds=max_rounds):
                    if turn.is_thinking:
                        yield _sse("spirit_thinking", {
                            "spirit": turn.spirit,
                            "display_name": turn.display_name,
                            "mode": turn.mode,
                            "round_num": turn.round_num,
                        })
                        continue

                    # Persist turn to session history
                    if req.session_id:
                        try:
                            sess = session_manager.get_session(req.session_id)
                            if sess:
                                from core.models import ChatMessage
                                metadata = {
                                    "spirit": turn.spirit,
                                    "character_name": turn.display_name,
                                    "mode": turn.mode,
                                    "round_num": turn.round_num,
                                    "passed_to": turn.passed_to,
                                }
                                if turn.resolution:
                                    metadata["resolution"] = turn.resolution
                                if turn.dissenting_views:
                                    metadata["dissenting_views"] = turn.dissenting_views
                                if turn.extension_reason:
                                    metadata["extension_reason"] = turn.extension_reason

                                sess.add_message(ChatMessage("assistant", turn.response, metadata=metadata))
                                session_manager.save_sessions()
                        except Exception as se:
                            logger.error(f"Failed to persist council turn to DB: {se}")

                    yield _sse("turn", {
                        "spirit": turn.spirit,
                        "display_name": turn.display_name,
                        "mode": turn.mode,
                        "response": turn.response,
                        "round_num": turn.round_num,
                        "is_final": turn.is_final,
                        "resolution": turn.resolution,
                        "dissenting_views": turn.dissenting_views,
                        "extension_reason": turn.extension_reason,
                        "passed_to": turn.passed_to,
                    })
                yield _sse("done", {"mode": "council"})
            except Exception as e:
                logger.error(f"Council stream error: {e}")
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(stream(), media_type="text/event-stream")

    # ── POST /api/voidcat/hearth ──────────────────────────────────────────
    @router.post("/api/voidcat/hearth")
    async def hearth(req: BoardRoomRequest, request: Request):
        """
        Execute a Hearth (open lounge) session. Streams TurnResult events via SSE.
        """
        if not req.endpoint_url or not req.model:
            raise HTTPException(400, "endpoint_url and model are required")

        headers = _resolve_headers(req.endpoint_url)
        generate_fn = _build_generate_fn(req.endpoint_url, req.model, headers)
        spirits = req.spirits or _load_spirit_roster()

        # Persist user message to session history
        if req.session_id:
            try:
                sess = session_manager.get_session(req.session_id)
                if sess:
                    from core.models import ChatMessage
                    sess.add_message(ChatMessage("user", req.prompt))
                    session_manager.save_sessions()
            except Exception as se:
                logger.error(f"Failed to persist user prompt to DB: {se}")

        initial_context = [{"role": "user", "content": req.prompt}]

        async def stream():
            try:
                async for turn in run_hearth(spirits, initial_context, generate_fn):
                    if turn.is_thinking:
                        yield _sse("spirit_thinking", {
                            "spirit": turn.spirit,
                            "display_name": turn.display_name,
                            "mode": turn.mode,
                            "round_num": turn.round_num,
                        })
                        continue

                    # Persist turn to session history
                    if req.session_id:
                        try:
                            sess = session_manager.get_session(req.session_id)
                            if sess:
                                from core.models import ChatMessage
                                metadata = {
                                    "spirit": turn.spirit,
                                    "character_name": turn.display_name,
                                    "mode": turn.mode,
                                    "round_num": turn.round_num,
                                    "passed_to": turn.passed_to,
                                }
                                sess.add_message(ChatMessage("assistant", turn.response, metadata=metadata))
                                session_manager.save_sessions()
                        except Exception as se:
                            logger.error(f"Failed to persist hearth turn to DB: {se}")

                    yield _sse("turn", {
                        "spirit": turn.spirit,
                        "display_name": turn.display_name,
                        "mode": turn.mode,
                        "response": turn.response,
                        "round_num": turn.round_num,
                        "is_final": turn.is_final,
                        "passed_to": turn.passed_to,
                    })
                yield _sse("done", {"mode": "hearth"})
            except Exception as e:
                logger.error(f"Hearth stream error: {e}")
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(stream(), media_type="text/event-stream")

    return router
