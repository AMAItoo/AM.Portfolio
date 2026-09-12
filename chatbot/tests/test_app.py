"""Tests for the FastAPI app and its security hardening."""
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from chatbot.engine import Engine, Session
from chatbot.app import create_app
from chatbot.tests.test_engine import FakeCollection


@pytest.fixture
def fake_engine(tmp_path):
    return Engine(
        collection=FakeCollection(),
        retrieve_fn=lambda col, q, k=4: col.retrieve(q, k),
        leads_path=str(tmp_path / "leads.jsonl"),
        llm_fn=lambda query, context, lang: "ردّ مختصّ وملائم حسب السياق.",
    )


@pytest.fixture
def client(fake_engine, tmp_path):
    app = create_app(
        engine_override=fake_engine,
        leads_path=str(tmp_path / "leads.jsonl"),
        rate_limit_per_min=1000,  # high so other tests are unaffected
    )
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_chat_rejects_empty(client):
    resp = client.post("/chat", json={"session_id": "a", "message": ""})
    assert resp.status_code == 422


def test_chat_rejects_too_long(client):
    resp = client.post("/chat", json={"session_id": "a", "message": "x" * 1001})
    assert resp.status_code == 422


def test_chat_returns_messages_and_state(client):
    resp = client.post("/chat", json={"session_id": "b", "message": "start", "page_lang": "ar"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "ask_name"
    assert len(data["messages"]) > 0
    assert isinstance(data["quick_replies"], list)
    # WhatsApp handoff is always attached so the green button is always visible.
    assert data["whatsapp"] is not None
    assert "wa.me" in data["whatsapp"]["link"]


def test_session_turn_cap_and_reset(client):
    """41st turn in a session is refused with a polite reset."""
    known_state = "greet"
    for i in range(40):
        resp = client.post("/chat", json={"session_id": "turny", "message": f"{i}", "page_lang": "ar"})
        assert resp.status_code == 200, f"turn {i} failed"
        known_state = resp.json()["state"]
    resp = client.post("/chat", json={"session_id": "turny", "message": "keep going", "page_lang": "ar"})
    assert resp.status_code == 200
    data = resp.json()
    # After 40 turns the session should reset to a fresh greet.
    assert data["state"] == "ask_name"


def test_cors_allows_only_portfolio(client):
    resp = client.options(
        "/chat",
        headers={
            "Origin": "https://amaitoo.github.io",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "https://amaitoo.github.io"

    resp2 = client.options(
        "/chat",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp2.headers.get("access-control-allow-origin") is None


def test_rate_limit_429(tmp_path, fake_engine):
    app = create_app(
        engine_override=fake_engine,
        leads_path=str(tmp_path / "leads.jsonl"),
        rate_limit_per_min=20,
    )
    with TestClient(app) as c:
        last = None
        for i in range(21):
            resp = c.post("/chat", json={"session_id": f"rl{i}", "message": "hi", "page_lang": "ar"})
            last = resp.status_code
        assert last == 429


def test_leads_count_endpoint(client, tmp_path):
    resp = client.get("/leads/count")
    assert resp.status_code == 200
    assert "count" in resp.json()


def test_rate_limiter_units():
    from chatbot.security import RateLimiter
    limiter = RateLimiter(limit=3, per_seconds=60)
    for _ in range(3):
        assert limiter.allow("10.0.0.1") is True
    assert limiter.allow("10.0.0.1") is False
    assert limiter.allow("10.0.0.2") is True