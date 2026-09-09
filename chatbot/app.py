"""FastAPI app for the portfolio chatbot with layered security.

Endpoints:
- POST /chat        {session_id, message, page_lang} -> bot reply
- GET  /health      liveness + KB chunk count
- GET  /leads/count number of captured leads

Security:
- CORS locked to the portfolio domain only
- Per-IP rate limit (20 req/min) via RateLimiter
- Input length cap (1000 chars) + control-char sanitization
- Session TTL (2h) + hard turn cap (40) to bound abuse
- Secrets only via env vars (GROQ_API_KEY / GEMINI_API_KEY)
"""
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chatbot.engine import Engine, Session
from chatbot.kb_loader import load_knowledge_base
from chatbot.leads import append_lead
from chatbot.rag import build_index, retrieve
from chatbot.security import (
    RateLimiter,
    MAX_INPUT_LENGTH,
    MAX_SESSION_TURNS,
    SESSION_TTL_SECONDS,
    sanitize_input,
)

ALLOWED_ORIGINS = ["https://amaitoo.github.io"]
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KB_DIR = os.path.join(_PKG_DIR, "knowledge")
DEFAULT_PERSIST_DIR = os.path.join(_PKG_DIR, "data", "chroma_db")
DEFAULT_LEADS_PATH = os.path.join(_PKG_DIR, "data", "leads.jsonl")


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=MAX_INPUT_LENGTH)
    page_lang: Optional[str] = None


def create_app(
    kb_dir: str = DEFAULT_KB_DIR,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    leads_path: str = DEFAULT_LEADS_PATH,
    engine_override: Optional[Engine] = None,
    rate_limit_per_min: int = 20,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if _app.state.engine is None:
            chunks = load_knowledge_base(kb_dir)
            collection = build_index(chunks, persist_dir)
            _app.state.engine = Engine(collection=collection, leads_path=leads_path)
            _app.state.kb_chunks = len(chunks)
        yield

    app = FastAPI(title="Portfolio Chatbot API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    # App state: engine + sessions
    app.state.engine = engine_override
    app.state.kb_chunks = 0
    app.state.sessions: dict[str, dict] = {}
    app.state.leads_path = leads_path
    app.state.rate = RateLimiter(limit=rate_limit_per_min, per_seconds=60)

    @app.get("/health")
    def health():
        return {"status": "ok", "kb_chunks": app.state.kb_chunks}

    @app.get("/leads/count")
    def leads_count():
        try:
            with open(app.state.leads_path, encoding="utf-8") as f:
                n = sum(1 for _ in f)
        except FileNotFoundError:
            n = 0
        return {"count": n}

    @app.post("/chat")
    async def chat(req: ChatRequest, request: Request):
        ip = request.client.host if request.client else "unknown"

        # Rate limiting (before any processing)
        if not app.state.rate.allow(ip):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

        message = sanitize_input(req.message)
        session_id = sanitize_input(req.session_id)
        if not session_id:
            raise HTTPException(status_code=422, detail="session_id required")

        # Session lifecycle
        now = time.time()
        rec = app.state.sessions.get(session_id)
        if rec is None or (now - rec["ts"]) > SESSION_TTL_SECONDS:
            lang = req.page_lang if req.page_lang in ("ar", "en") else "ar"
            rec = {"session": Session(session_id, lang=lang), "ts": now, "turns": 0}
            app.state.sessions[session_id] = rec

        if rec["turns"] >= MAX_SESSION_TURNS:
            # Cap abuse: reset the session with a fresh greeting.
            lang = req.page_lang if req.page_lang in ("ar", "en") else "ar"
            rec["session"] = Session(session_id, lang=lang)
            rec["turns"] = 0
            rec["ts"] = now

        reply = app.state.engine.handle(rec["session"], message)
        rec["turns"] += 1
        rec["ts"] = now

        return {
            "messages": reply.messages,
            "quick_replies": reply.quick_replies,
            "whatsapp": reply.whatsapp,
            "state": rec["session"].state,
        }

    return app


app = create_app()