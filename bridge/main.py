"""
ZGX AI Bridge - FastAPI application.
Routes inference requests from ISV applications to on-prem vLLM.
"""

import json
import logging
import time

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import load_config
from .sessions import SessionStore
from .context import validate_context, build_system_prompt
from .inference import VLLMClient
from .metrics import MetricsCollector
from .auth import APIKeyAuth

# ── Setup ──────────────────────────────────────────────────────────

config = load_config()

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("zgx-bridge")

app = FastAPI(
    title="ZGX AI Bridge",
    version="0.1.0",
    description="On-prem AI middleware for ISV applications",
)

# CORS: allow widget from any origin (ISV app could be anywhere on LAN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Components
sessions = SessionStore(
    ttl_minutes=config.session_ttl_minutes,
    max_turns=config.session_max_turns,
)
vllm = VLLMClient(
    base_url=config.vllm_base_url,
    model=config.vllm_model,
    timeout_seconds=config.vllm_timeout_seconds,
)
metrics = MetricsCollector()
auth = APIKeyAuth(valid_keys=config.api_keys)


# ── Auth middleware ────────────────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    try:
        await auth(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    return await call_next(request)


# ── Request models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    context: dict | None = None


# ── Endpoints ──────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Bridge + vLLM health status."""
    vllm_status = await vllm.health_check()
    return {
        "bridge": "ok",
        "vllm_status": vllm_status.get("status"),
        "vllm_models": vllm_status.get("models", []),
        "config": {
            "model": config.vllm_model,
            "vllm_url": config.vllm_base_url,
        },
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Send a message with context. Returns SSE stream.
    """
    # Validate context
    ctx = validate_context(req.context, config.context_max_size_bytes)

    # Get or create session
    session = sessions.get_or_create(req.session_id)

    # Check turn limit
    if sessions.is_at_turn_limit(session):
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Session has reached the maximum of {config.session_max_turns} turns. "
                "Please start a new session.",
                "session_id": session.session_id,
            },
        )

    # Add user message to history
    session.add_user_message(req.message)

    # Build the full messages array for vLLM
    system_prompt = build_system_prompt(config.system_prompt_base, ctx)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(sessions.get_conversation_history(session))

    logger.info(
        "Chat request: session=%s, context_keys=%s, history_len=%d",
        session.session_id,
        list(ctx.keys()) if ctx else [],
        len(session.messages),
    )

    async def event_stream():
        full_text = ""
        try:
            async for chunk in vllm.stream_chat(messages):
                if chunk["type"] == "token":
                    full_text += chunk["content"]
                    yield f"data: {json.dumps(chunk)}\n\n"

                elif chunk["type"] == "done":
                    # Record the assistant's response in session history
                    session.add_assistant_message(full_text)

                    usage = chunk.get("usage", {})
                    latency = chunk.get("latency_ms", 0)

                    # Update session metrics
                    session.record_usage(
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )

                    # Update global metrics
                    metrics.record_request(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        latency_ms=latency,
                        session_id=session.session_id,
                    )

                    done_payload = {
                        "type": "done",
                        "usage": usage,
                        "latency_ms": latency,
                        "session_id": session.session_id,
                    }
                    yield f"data: {json.dumps(done_payload)}\n\n"

                elif chunk["type"] == "error":
                    metrics.record_error()
                    yield f"data: {json.dumps(chunk)}\n\n"

        except Exception as e:
            logger.error("Stream error: %s", e)
            metrics.record_error()
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal stream error.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/chat/{session_id}")
async def get_session_history(session_id: str):
    """Retrieve conversation history for a session."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session.session_id,
        "messages": session.messages,
        "created_at": session.created_at,
        "total_tokens": session.total_prompt_tokens + session.total_completion_tokens,
        "request_count": session.request_count,
    }


@app.get("/api/sessions")
async def list_sessions():
    """List active sessions (admin)."""
    return {"sessions": sessions.list_sessions()}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """End a session and clear its history."""
    deleted = sessions.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True, "session_id": session_id}


@app.get("/api/metrics")
async def get_metrics():
    """Token counts, latency stats, cost comparison."""
    return metrics.get_metrics(active_sessions=sessions.active_count)


# ── Lifecycle ──────────────────────────────────────────────────────

@app.on_event("shutdown")
async def shutdown():
    await vllm.close()
    logger.info("Bridge shut down.")


@app.on_event("startup")
async def startup():
    logger.info("ZGX AI Bridge starting on %s:%d", config.bridge_host, config.bridge_port)
    logger.info("vLLM target: %s (model: %s)", config.vllm_base_url, config.vllm_model)

    health = await vllm.health_check()
    if health["status"] == "ok":
        logger.info("vLLM connection verified. Models: %s", health.get("models"))
    else:
        logger.warning("vLLM not reachable at startup: %s. Bridge will retry on requests.", health)
